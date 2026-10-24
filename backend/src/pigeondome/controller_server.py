"""Processo do controlador: lê detecções, decide e, conforme o modo, comanda o atuador."""

import logging
import signal
import sys
import threading
from datetime import UTC, datetime

import psycopg
from psycopg_pool import ConnectionPool

from pigeondome.adapters.actuator_mqtt import (
    ActuatorMessageHandler,
    ActuatorStateTracker,
    ControllerMqtt,
)
from pigeondome.adapters.postgres import PostgresDetectionRepository
from pigeondome.adapters.postgres_actuation import (
    PostgresActuatorEventRepository,
    PostgresControllerFlags,
    PostgresDecisionRepository,
)
from pigeondome.application.controller_service import ControllerService
from pigeondome.config import DatabaseSettings, MqttSettings
from pigeondome.controller_config import ControllerSettings
from pigeondome.domain.actuation import Mode
from pigeondome.migrate import apply_migrations

log = logging.getLogger("pigeondome.controller")

BANNERS = {
    Mode.OFF: "modo OFF: o controlador só observa, sem decidir acionar",
    Mode.DRY_RUN: "MODO SECO: decide e registra, mas NENHUM comando será enviado ao atuador",
    Mode.LIVE: "MODO REAL: comandos de pulso serão enviados ao atuador",
    Mode.EXPERIMENT: "MODO EXPERIMENTO: comandos reais só nos blocos de tratamento sorteados",
}


def serve(settings: ControllerSettings, mqtt_settings: MqttSettings, pool: ConnectionPool) -> None:
    tracker = ActuatorStateTracker()
    handler = ActuatorMessageHandler(
        settings.actuator_id, tracker, PostgresActuatorEventRepository(pool)
    )
    bridge = ControllerMqtt(mqtt_settings, settings.actuator_id, handler)
    service = ControllerService(
        settings.policy,
        settings.camera_id,
        settings.actuator_id,
        PostgresDetectionRepository(pool),
        PostgresDecisionRepository(pool),
        PostgresControllerFlags(pool),
        tracker,
        bridge,
    )
    log.warning(
        "%s (câmera=%s, atuador=%s)",
        BANNERS[settings.policy.mode],
        settings.camera_id,
        settings.actuator_id,
    )
    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    bridge.start()
    try:
        while not stop.wait(settings.tick_s):
            try:
                service.step(datetime.now(UTC))
            except Exception:  # um passo com defeito não derruba o controlador (e não aciona nada)
                log.exception("falha inesperada em um passo do controlador")
    finally:
        bridge.stop()
        log.info("encerrando")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        mqtt_settings = MqttSettings.from_env()
        db_settings = DatabaseSettings.from_env()
        settings = ControllerSettings.from_env()
    except ValueError as exc:
        log.error("configuração inválida: %s", exc)
        return 2
    try:
        for name in apply_migrations(db_settings.conninfo):
            log.info("migração aplicada: %s", name)
        pool = ConnectionPool(db_settings.conninfo, min_size=1, max_size=4, open=True)
        try:
            pool.wait(timeout=10)
            serve(settings, mqtt_settings, pool)
        finally:
            pool.close()
    except psycopg.Error as exc:
        log.error("banco de dados indisponível: %s", exc)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
