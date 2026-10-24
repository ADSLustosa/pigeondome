"""Ponte MQTT do controlador: estado e eventos do atuador entram, comandos saem."""

import json
import logging
import threading
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

from pigeondome.application.controller_service import CommandSendError
from pigeondome.application.ports import ActuatorEventRepository, StorageError
from pigeondome.config import MqttSettings
from pigeondome.domain.actuation import ActuatorStatus
from pigeondome.domain.actuation_log import ActuatorEventRecord

log = logging.getLogger("pigeondome.controller")

COMMAND_TTL_S = 10
MAX_PAYLOAD_BYTES = 4096
ACTUATOR_STATES = frozenset({"safe_off", "idle", "pulsing", "cooldown", "maintenance", "fault"})


def command_topic(actuator_id: str) -> str:
    return f"pigeondome/v1/{actuator_id}/commands"


def state_topic(actuator_id: str) -> str:
    return f"pigeondome/v1/{actuator_id}/actuator/state"


def events_topic(actuator_id: str) -> str:
    return f"pigeondome/v1/{actuator_id}/actuator/events"


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _load_object(raw: bytes) -> dict[str, Any] | None:
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def build_pulse_command(
    actuator_id: str, duration_s: int, now: datetime, command_id: str | None = None
) -> dict[str, Any]:
    """Monta um comando que obedece ao contrato command.v1."""
    issued_at = now.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    return {
        "schema_version": 1,
        "command_id": command_id or str(uuid.uuid4()),
        "device_id": actuator_id,
        "action": "pulse",
        "duration_s": duration_s,
        "issued_at": issued_at,
        "ttl_s": COMMAND_TTL_S,
        "reason": {"trigger": "detection"},
    }


class ActuatorStateTracker:
    """Último estado conhecido do atuador (thread-safe). Antes de qualquer mensagem: offline."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._status = ActuatorStatus(online=False, state="unknown", reported_at=None)

    def update(self, *, online: bool, state: str, received_at: datetime) -> None:
        with self._lock:
            self._status = ActuatorStatus(online, state, received_at)

    def current(self) -> ActuatorStatus:
        with self._lock:
            return self._status


class MessageOutcome(Enum):
    STATE_UPDATED = "state_updated"
    EVENT_STORED = "event_stored"
    EVENT_DUPLICATE = "event_duplicate"
    REJECTED = "rejected"
    STORAGE_ERROR = "storage_error"
    IGNORED = "ignored"


class ActuatorMessageHandler:
    def __init__(
        self, actuator_id: str, tracker: ActuatorStateTracker, events: ActuatorEventRepository
    ) -> None:
        self._actuator_id = actuator_id
        self._tracker = tracker
        self._events = events

    def handle(self, topic: str, raw: bytes, now: datetime) -> MessageOutcome:
        if topic not in (state_topic(self._actuator_id), events_topic(self._actuator_id)):
            return MessageOutcome.IGNORED
        data = _load_object(raw) if len(raw) <= MAX_PAYLOAD_BYTES else None
        if data is None or data.get("device_id") != self._actuator_id:
            # %r evita que conteúdo vindo da rede forje linhas de log
            log.warning("mensagem do atuador rejeitada em %r: %r", topic, raw[:200])
            return MessageOutcome.REJECTED
        if topic == state_topic(self._actuator_id):
            return self._handle_state(data, now)
        return self._handle_event(data)

    def _handle_state(self, data: dict[str, Any], now: datetime) -> MessageOutcome:
        online = data.get("online")
        state = data.get("state")
        if (
            not isinstance(online, bool)
            or not isinstance(state, str)
            or state not in ACTUATOR_STATES
        ):
            log.warning("estado do atuador rejeitado: %r", data)
            return MessageOutcome.REJECTED
        # O frescor é medido na RECEPÇÃO, com o relógio do controlador (não o do atuador).
        self._tracker.update(online=online, state=state, received_at=now)
        return MessageOutcome.STATE_UPDATED

    def _handle_event(self, data: dict[str, Any]) -> MessageOutcome:
        event = data.get("event")
        occurred = data.get("at")
        command_id = data.get("command_id")
        reason_code = data.get("reason_code")
        if (
            not isinstance(event, str)
            or not isinstance(occurred, str)
            or (command_id is not None and not isinstance(command_id, str))
            or (reason_code is not None and not isinstance(reason_code, str))
        ):
            log.warning("evento do atuador rejeitado: %r", data)
            return MessageOutcome.REJECTED
        try:
            record = ActuatorEventRecord(
                datetime.fromisoformat(occurred), self._actuator_id, event, command_id, reason_code
            )
        except ValueError:  # inclui InvalidRecordError
            log.warning("evento do atuador rejeitado: %r", data)
            return MessageOutcome.REJECTED
        try:
            stored = self._events.add(record)
        except StorageError:
            log.warning("evento do atuador não gravado: banco indisponível")
            return MessageOutcome.STORAGE_ERROR
        return MessageOutcome.EVENT_STORED if stored else MessageOutcome.EVENT_DUPLICATE


class ControllerMqtt:
    """Cliente MQTT do controlador: assina estado e eventos do atuador e publica comandos."""

    def __init__(
        self,
        settings: MqttSettings,
        actuator_id: str,
        handler: ActuatorMessageHandler,
        *,
        client: Any | None = None,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._settings = settings
        self._actuator_id = actuator_id
        self._handler = handler
        self._clock = clock
        # Id próprio e sessão LIMPA: o ingestor usa "pigeondome-backend" (sessão persistente),
        # e dois clientes com o mesmo id derrubariam um ao outro. Comandos nunca ficam represados.
        self._client: Any = (
            client
            if client is not None
            else mqtt.Client(
                CallbackAPIVersion.VERSION2, client_id="pigeondome-controller", clean_session=True
            )
        )
        self._client.username_pw_set(settings.user, settings.password)
        self._client.reconnect_delay_set(min_delay=1, max_delay=30)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

    def _on_connect(
        self, client: Any, userdata: Any, flags: Any, reason_code: Any, properties: Any
    ) -> None:
        if reason_code.is_failure:
            log.error("conexão recusada: %s", reason_code)
            return
        for topic in (state_topic(self._actuator_id), events_topic(self._actuator_id)):
            client.subscribe(topic, qos=1)  # sessão limpa: assinar a cada conexão
        log.info("conectado ao broker; acompanhando o atuador %s", self._actuator_id)

    def _on_disconnect(
        self, client: Any, userdata: Any, flags: Any, reason_code: Any, properties: Any
    ) -> None:
        if reason_code.is_failure:
            log.warning("conexão perdida (%s); sem comandos até reconectar", reason_code)

    def _on_message(self, client: Any, userdata: Any, message: Any) -> None:
        self._handler.handle(message.topic, bytes(message.payload), self._clock())

    def send_pulse(self, actuator_id: str, duration_s: int, now: datetime) -> str:
        if not self._client.is_connected():
            raise CommandSendError("sem conexão com o broker")
        command = build_pulse_command(actuator_id, duration_s, now)
        payload = json.dumps(command, separators=(",", ":"))
        info = self._client.publish(command_topic(actuator_id), payload, qos=1)
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            raise CommandSendError(f"falha ao publicar o comando (código {info.rc})")
        command_id: str = command["command_id"]
        return command_id

    def start(self) -> None:
        self._client.connect_async(self._settings.host, self._settings.port, keepalive=15)
        self._client.loop_start()

    def stop(self) -> None:
        self._client.disconnect()
        self._client.loop_stop()
