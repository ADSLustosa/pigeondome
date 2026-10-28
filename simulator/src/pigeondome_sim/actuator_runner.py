"""Runner do atuador simulado: liga o serviço ao broker MQTT com paho-mqtt (a casca de E/S).

Toda a lógica vive no `ActuatorService` e no `ActuatorCore`; aqui só há conexão, callbacks e o
laço de `tick`. Roda como o papel MQTT 'actuator':  python -m pigeondome_sim.actuator_runner
"""

import contextlib
import logging
import os
import re
import signal
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

from pigeondome_sim.actuator_budget import FileBudgetStore
from pigeondome_sim.actuator_core import ActuatorCore, Instant
from pigeondome_sim.actuator_journal import FileEventJournal
from pigeondome_sim.actuator_service import ActuatorService, Publication, command_topic

log = logging.getLogger("pigeondome_sim.actuator")

DEVICE_ID_PATTERN = re.compile(r"^[a-z0-9-]{3,32}$")  # o mesmo do contrato; vira nome de arquivo
DEFAULT_STATE_DIR = ".pigeondome-state"


@dataclass(frozen=True)
class ActuatorSettings:
    host: str
    port: int
    user: str
    password: str = field(repr=False)
    device_id: str
    tick_s: float
    heartbeat_s: float
    # Pasta da memória não volátil (orçamento e registro de eventos). None: sem memória, o
    # orçamento vive em RAM e os eventos só saem pelo MQTT.
    state_dir: str | None = None

    @classmethod
    def from_env(cls) -> "ActuatorSettings":
        password = os.environ.get("MQTT_PASSWORD", "")
        if not password:
            raise ValueError("defina MQTT_PASSWORD (senha do usuário MQTT 'actuator')")
        tick_s = float(os.environ.get("ACTUATOR_TICK_S", "0.5"))
        heartbeat_s = float(os.environ.get("ACTUATOR_HEARTBEAT_S", "10"))
        if not 0 < tick_s <= 2:
            raise ValueError(
                "ACTUATOR_TICK_S precisa ficar entre 0 e 2 s (o watchdog do núcleo é de 5 s)"
            )
        if heartbeat_s <= 0:
            raise ValueError("ACTUATOR_HEARTBEAT_S precisa ser positivo")
        device_id = os.environ.get("ACTUATOR_DEVICE_ID", "act-sim-01")
        if not DEVICE_ID_PATTERN.fullmatch(device_id):
            raise ValueError("ACTUATOR_DEVICE_ID precisa seguir ^[a-z0-9-]{3,32}$")
        state_dir = os.environ.get("ACTUATOR_STATE_DIR", DEFAULT_STATE_DIR).strip()
        if not state_dir:
            raise ValueError("ACTUATOR_STATE_DIR não pode ser vazio")
        return cls(
            host=os.environ.get("MQTT_HOST", "127.0.0.1"),
            port=int(os.environ.get("MQTT_PORT", "1883")),
            user=os.environ.get("MQTT_USER", "actuator"),
            password=password,
            device_id=device_id,
            tick_s=tick_s,
            heartbeat_s=heartbeat_s,
            state_dir=state_dir,
        )


def system_clock() -> Instant:
    return Instant(mono_s=time.monotonic(), wall=datetime.now(UTC))


class ActuatorRunner:
    def __init__(
        self,
        settings: ActuatorSettings,
        *,
        client: Any | None = None,
        clock: Callable[[], Instant] = system_clock,
        service: ActuatorService | None = None,
    ) -> None:
        self._settings = settings
        self._clock = clock
        self._service = service if service is not None else self._new_service(settings)
        # Antes de conectar (e de montar a última vontade): recupera o orçamento gravado.
        self._service.restore_budget(self._clock())
        # Os callbacks do paho rodam em outra thread; o lock também mantém a ORDEM das
        # publicações (o estado retido nunca pode chegar ao broker fora de ordem).
        self._lock = threading.Lock()
        self._client: Any = client if client is not None else self._new_client()
        self._configure()

    @staticmethod
    def _new_service(settings: ActuatorSettings) -> ActuatorService:
        store = None
        journal = None
        if settings.state_dir is not None:
            folder = Path(settings.state_dir)
            name = f"actuator-{settings.device_id}"
            store = FileBudgetStore(folder / f"{name}.json", settings.device_id)
            journal = FileEventJournal(folder / f"{name}-events.jsonl", settings.device_id)
        return ActuatorService(settings.device_id, ActuatorCore(store=store, journal=journal))

    def _new_client(self) -> mqtt.Client:
        # Sessão limpa: o broker não guarda comandos para um atuador desligado.
        return mqtt.Client(CallbackAPIVersion.VERSION2, client_id=self._settings.device_id)

    def _configure(self) -> None:
        client = self._client
        client.username_pw_set(self._settings.user, self._settings.password)
        will = self._service.will(self._clock())
        client.will_set(will.topic, will.payload, qos=will.qos, retain=will.retain)
        client.reconnect_delay_set(min_delay=1, max_delay=30)
        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        client.on_message = self._on_message

    # --- callbacks do paho (thread da rede) ---------------------------------------------

    def _on_connect(
        self, client: Any, userdata: Any, flags: Any, reason_code: Any, properties: Any
    ) -> None:
        if reason_code.is_failure:
            log.error("conexão recusada: %s", reason_code)
            return
        topic = command_topic(self._settings.device_id)
        client.subscribe(topic, qos=1)  # sessão limpa: assinar a cada conexão
        with self._lock:
            self._send(self._service.on_connected(self._clock()))
        log.info("conectado ao broker; assinando %s", topic)

    def _on_disconnect(
        self, client: Any, userdata: Any, flags: Any, reason_code: Any, properties: Any
    ) -> None:
        with self._lock:
            self._service.on_disconnected(self._clock())
        if reason_code.is_failure:
            log.warning("conexão perdida (%s); a saída foi desligada", reason_code)
        else:
            log.info("desconectado")

    def _on_message(self, client: Any, userdata: Any, message: Any) -> None:
        with self._lock:
            publications = self._service.on_message(
                message.topic, bytes(message.payload), self._clock()
            )
            self._send(publications)

    # --- laço principal -----------------------------------------------------------------

    def step(self, *, heartbeat: bool = False) -> None:
        """Uma passada do laço: deixa o tempo passar no núcleo e publica o que mudou."""
        with self._lock:
            self._send(self._service.tick(self._clock(), heartbeat=heartbeat))

    def run(self, stop: threading.Event) -> None:
        self._client.connect_async(self._settings.host, self._settings.port, keepalive=15)
        self._client.loop_start()
        next_heartbeat = time.monotonic() + self._settings.heartbeat_s
        try:
            while not stop.wait(self._settings.tick_s):
                due = time.monotonic() >= next_heartbeat
                if due:
                    next_heartbeat += self._settings.heartbeat_s
                self.step(heartbeat=due)
        finally:
            self._shutdown()

    def _shutdown(self) -> None:
        with self._lock:
            infos = self._send(self._service.shutdown(self._clock()))
        for info in infos:
            with contextlib.suppress(RuntimeError, ValueError):
                info.wait_for_publish(timeout=2)
        self._client.disconnect()
        self._client.loop_stop()

    def _send(self, publications: list[Publication]) -> list[Any]:
        infos = []
        for publication in publications:
            log.info("%s %s", publication.topic, publication.payload.decode("utf-8"))
            infos.append(
                self._client.publish(
                    publication.topic,
                    publication.payload,
                    qos=publication.qos,
                    retain=publication.retain,
                )
            )
        return infos


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        settings = ActuatorSettings.from_env()
    except ValueError as exc:
        logging.error("configuração inválida: %s", exc)
        return 2
    runner = ActuatorRunner(settings)
    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    runner.run(stop)
    logging.info("encerrando")
    return 0


if __name__ == "__main__":
    sys.exit(main())
