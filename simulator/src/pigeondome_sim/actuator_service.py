"""Serviço do atuador: traduz mensagens MQTT em chamadas ao núcleo, sem tocar na rede.

Cada método devolve as publicações a fazer (`Publication`). Quem faz a E/S de verdade (o runner
com paho-mqtt) só entrega as mensagens recebidas e publica o que o serviço mandar, o que deixa
toda a lógica testável sem broker, sem threads e sem relógio.
"""

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, TypeGuard

from pigeondome_sim.actuator_core import (
    Action,
    ActuatorCore,
    Command,
    Event,
    Fault,
    Instant,
    Snapshot,
    State,
)
from pigeondome_sim.actuator_messages import event_message, state_message

UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
UTC_TIME_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?Z")
ALLOWED_KEYS = frozenset(
    {
        "schema_version",
        "command_id",
        "device_id",
        "action",
        "duration_s",
        "issued_at",
        "ttl_s",
        "reason",
    }
)
REASON_KEYS = frozenset({"trigger", "pigeon_count"})
TRIGGERS = frozenset({"detection", "manual", "test"})
LONG_AGO = datetime(1970, 1, 1, tzinfo=UTC)


def command_topic(device_id: str) -> str:
    return f"pigeondome/v1/{device_id}/commands"


def state_topic(device_id: str) -> str:
    return f"pigeondome/v1/{device_id}/actuator/state"


def events_topic(device_id: str) -> str:
    return f"pigeondome/v1/{device_id}/actuator/events"


@dataclass(frozen=True)
class Publication:
    topic: str
    payload: bytes
    qos: int
    retain: bool


def _is_int(value: object) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool)


def _load_object(payload: bytes) -> dict[str, Any] | None:
    try:
        data = json.loads(payload)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _valid_reason(reason: object) -> bool:
    if not isinstance(reason, dict) or set(reason) - REASON_KEYS:
        return False
    trigger = reason.get("trigger")
    if not isinstance(trigger, str) or trigger not in TRIGGERS:
        return False
    count = reason.get("pigeon_count", 0)
    return _is_int(count) and 0 <= count <= 50


def guess_command_id(payload: bytes) -> str | None:
    """Melhor esforço para identificar o comando de uma mensagem recusada (auditoria)."""
    data = _load_object(payload)
    command_id = data.get("command_id") if data is not None else None
    if isinstance(command_id, str) and UUID_RE.fullmatch(command_id):
        return command_id
    return None


def parse_command(payload: bytes, device_id: str) -> Command | None:
    """Converte a mensagem em comando; `None` se ela não obedece ao contrato.

    Exceção deliberada (fail-safe): qualquer objeto com "action": "stop" vira um comando de
    parada, mesmo malformado, porque recusar um pedido de parada seria o pior erro possível.
    """
    data = _load_object(payload)
    if data is None:
        return None
    if data.get("action") == "stop":
        command_id = data.get("command_id")
        return Command(command_id if isinstance(command_id, str) else "", Action.STOP, LONG_AGO, 0)
    return _parse_pulse(data, device_id)


def _parse_pulse(data: dict[str, Any], device_id: str) -> Command | None:
    if set(data) - ALLOWED_KEYS:
        return None  # nenhum campo fora do contrato (ex.: voltage)
    if data.get("schema_version") != 1 or data.get("device_id") != device_id:
        return None
    if data.get("action") != "pulse":
        return None
    command_id = data.get("command_id")
    issued_at = data.get("issued_at")
    if not isinstance(command_id, str) or not UUID_RE.fullmatch(command_id):
        return None
    if not isinstance(issued_at, str) or not UTC_TIME_RE.fullmatch(issued_at):
        return None
    ttl_s = data.get("ttl_s")
    duration_s = data.get("duration_s")
    if not _is_int(ttl_s) or not (duration_s is None or _is_int(duration_s)):
        return None
    if "reason" in data and not _valid_reason(data["reason"]):
        return None
    try:
        moment = datetime.fromisoformat(issued_at)
    except ValueError:
        return None
    # Os limites (duração, TTL) são do núcleo: ele recusa com o command_id para a auditoria.
    return Command(command_id, Action.PULSE, moment, ttl_s, duration_s)


def _dumps(message: dict[str, Any]) -> bytes:
    return json.dumps(message, separators=(",", ":")).encode("utf-8")


class ActuatorService:
    """Liga o núcleo aos tópicos MQTT. Sem rede: cada método devolve as publicações a fazer."""

    def __init__(self, device_id: str, core: ActuatorCore | None = None) -> None:
        self._device_id = device_id
        self._core = core if core is not None else ActuatorCore()
        self._connected = False
        self._pending: list[Event] = []  # eventos ocorridos offline, publicados ao reconectar
        self._last_key: tuple[object, ...] | None = None

    def restore_budget(self, now: Instant) -> None:
        """Recupera o orçamento gravado. Chame uma vez, ao ligar, antes de conectar ao broker."""
        self._core.restore_budget(now)

    def will(self, now: Instant) -> Publication:
        """Última vontade (LWT): o broker publica isto se a conexão cair sem despedida."""
        offline = Snapshot(
            online=False,
            state=State.SAFE_OFF,
            output_on=False,
            last_command_id=None,
            fault=None,
            budget_used_s_1h=0,
        )
        return self._state_publication(offline, now)

    def on_connected(self, now: Instant) -> list[Publication]:
        self._connected = True
        events = [*self._pending, *self._core.connection_restored(now)]
        self._pending.clear()
        return self._outputs(events, now, force_state=True)

    def on_disconnected(self, now: Instant) -> list[Publication]:
        self._connected = False
        self._pending.extend(self._core.connection_lost(now))
        return []

    def shutdown(self, now: Instant) -> list[Publication]:
        """Encerramento limpo: aborta o pulso e publica o estado final (o LWT não dispara)."""
        topic = events_topic(self._device_id)
        publications = [
            Publication(topic, _dumps(event_message(self._device_id, event)), 1, False)
            for event in self._core.connection_lost(now)
        ]
        publications.append(self.will(now))
        self._connected = False
        return publications

    def on_message(self, topic: str, payload: bytes, now: Instant) -> list[Publication]:
        if topic != command_topic(self._device_id):
            return []
        command = parse_command(payload, self._device_id)
        if command is None:
            events = self._core.reject_invalid(now, guess_command_id(payload))
        else:
            events = self._core.handle_command(command, now)
        return self._outputs(events, now)

    def tick(self, now: Instant, *, heartbeat: bool = False) -> list[Publication]:
        """Chame com frequência (o watchdog do núcleo é de 5 s). `heartbeat` força o estado."""
        return self._outputs(self._core.tick(now), now, force_state=heartbeat)

    # Entradas locais (chave de manutenção, sensores, botão de reset), simuladas no gêmeo digital.

    def set_maintenance(self, active: bool, now: Instant) -> list[Publication]:
        return self._outputs(self._core.set_maintenance(active, now), now)

    def inject_fault(self, fault: Fault, now: Instant) -> list[Publication]:
        return self._outputs(self._core.inject_fault(fault, now), now)

    def reset(self, now: Instant) -> list[Publication]:
        return self._outputs(self._core.reset(now), now)

    def _outputs(
        self, events: list[Event], now: Instant, *, force_state: bool = False
    ) -> list[Publication]:
        if not self._connected:
            self._pending.extend(events)
            return []
        topic = events_topic(self._device_id)
        publications = [
            Publication(topic, _dumps(event_message(self._device_id, event)), 1, False)
            for event in events
        ]
        snapshot = self._core.snapshot(now)
        key = (
            snapshot.online,
            snapshot.state,
            snapshot.output_on,
            snapshot.last_command_id,
            snapshot.fault,
        )
        if force_state or key != self._last_key:
            self._last_key = key
            publications.append(self._state_publication(snapshot, now))
        return publications

    def _state_publication(self, snapshot: Snapshot, now: Instant) -> Publication:
        message = state_message(self._device_id, snapshot, now.wall)
        return Publication(state_topic(self._device_id), _dumps(message), 1, True)
