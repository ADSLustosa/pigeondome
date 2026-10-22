"""Entrada MQTT: o handler decide o que fazer, o subscriber só adapta o paho."""

import logging
from enum import Enum
from typing import Any

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

from pigeondome.adapters.contract import DetectionParser, InvalidMessageError
from pigeondome.application.ports import StorageError
from pigeondome.application.use_cases import IngestDetection
from pigeondome.config import MqttSettings

log = logging.getLogger("pigeondome")

DETECTIONS_FILTER = "pigeondome/v1/+/detections"


class Outcome(Enum):
    ACCEPTED = "accepted"
    DUPLICATE = "duplicate"
    REJECTED = "rejected"
    STORAGE_ERROR = "storage_error"


class DetectionMessageHandler:
    def __init__(self, parser: DetectionParser, ingest: IngestDetection) -> None:
        self._parser = parser
        self._ingest = ingest
        self.accepted = 0
        self.duplicates = 0
        self.rejected = 0
        self.storage_errors = 0
        self._devices: set[str] = set()

    def handle(self, topic: str, raw: bytes) -> Outcome:
        try:
            detection = self._parser.parse(topic, raw)
        except InvalidMessageError as exc:
            self.rejected += 1
            # %r evita que conteúdo vindo da rede forje linhas de log
            log.warning("mensagem rejeitada em %r: %r", topic, str(exc))
            return Outcome.REJECTED
        self._devices.add(detection.device_id)
        try:
            is_new = self._ingest.execute(detection)
        except StorageError:
            # uma falha de banco nunca pode derrubar a thread de rede do paho
            self.storage_errors += 1
            log.exception("falha ao gravar detecção de %r", detection.device_id)
            return Outcome.STORAGE_ERROR
        if is_new:
            self.accepted += 1
            return Outcome.ACCEPTED
        self.duplicates += 1
        return Outcome.DUPLICATE

    def devices_snapshot(self) -> list[str]:
        return sorted(self._devices)


class MqttSubscriber:
    def __init__(self, settings: MqttSettings, handler: DetectionMessageHandler) -> None:
        self._settings = settings
        self._handler = handler
        # Sessão persistente: se o backend cair, o broker guarda as mensagens QoS 1.
        self._client = mqtt.Client(
            CallbackAPIVersion.VERSION2, client_id="pigeondome-backend", clean_session=False
        )
        self._client.username_pw_set(settings.user, settings.password)
        self._client.reconnect_delay_set(min_delay=1, max_delay=30)
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message

    def _on_connect(
        self, client: Any, userdata: Any, flags: Any, reason_code: Any, properties: Any
    ) -> None:
        if reason_code.is_failure:
            log.error("conexão recusada: %s", reason_code)
            return
        log.info("conectado ao broker; assinando %s", DETECTIONS_FILTER)
        client.subscribe(DETECTIONS_FILTER, qos=1)

    def _on_message(self, client: Any, userdata: Any, message: Any) -> None:
        self._handler.handle(message.topic, bytes(message.payload))

    def start(self) -> None:
        self._client.connect_async(self._settings.host, self._settings.port, keepalive=15)
        self._client.loop_start()

    def stop(self) -> None:
        self._client.disconnect()
        self._client.loop_stop()
