"""Publicação MQTT: status com Last Will e detecções com QoS 1."""

import json
import logging
from typing import Any

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

from pigeondome_sim.config import Settings
from pigeondome_sim.generator import Detection

log = logging.getLogger("pigeondome_sim")


def detections_topic(device_id: str) -> str:
    return f"pigeondome/v1/{device_id}/detections"


def status_topic(device_id: str) -> str:
    return f"pigeondome/v1/{device_id}/status"


def status_payload(state: str) -> str:
    return json.dumps({"state": state})


class CameraPublisher:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._status_topic = status_topic(settings.device_id)
        self._detections_topic = detections_topic(settings.device_id)
        self._client = mqtt.Client(
            CallbackAPIVersion.VERSION2, client_id=f"{settings.device_id}-sim"
        )
        self._client.username_pw_set(settings.user, settings.password)
        # Se a conexão cair sem aviso, o PRÓPRIO broker publica "offline".
        self._client.will_set(self._status_topic, status_payload("offline"), qos=1, retain=True)
        self._client.reconnect_delay_set(min_delay=1, max_delay=30)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect

    def _on_connect(
        self, client: Any, userdata: Any, flags: Any, reason_code: Any, properties: Any
    ) -> None:
        if reason_code.is_failure:
            log.error("conexão recusada: %s", reason_code)
            return
        log.info("conectado ao broker")
        client.publish(self._status_topic, status_payload("online"), qos=1, retain=True)

    def _on_disconnect(
        self, client: Any, userdata: Any, flags: Any, reason_code: Any, properties: Any
    ) -> None:
        log.warning("desconectado (%s); reconectando automaticamente", reason_code)

    def start(self) -> None:
        self._client.connect_async(self._settings.host, self._settings.port)
        self._client.loop_start()

    def publish_detection(self, detection: Detection) -> None:
        payload = json.dumps(detection.to_payload())
        self._client.publish(self._detections_topic, payload, qos=1)
        log.info("publicado: %s", payload)

    def stop(self) -> None:
        # Desconexão limpa NÃO dispara o Last Will, então avisamos manualmente.
        self._client.publish(self._status_topic, status_payload("offline"), qos=1, retain=True)
        self._client.loop_stop()
        self._client.disconnect()
