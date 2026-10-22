"""Ponto de entrada do backend: compõe adaptadores, casos de uso e o relatório periódico."""

import logging
import os
import sys
import time
from datetime import UTC, datetime, timedelta

import psycopg
from psycopg_pool import ConnectionPool

from pigeondome.adapters.contract import DetectionParser
from pigeondome.adapters.memory import InMemoryDetectionRepository
from pigeondome.adapters.mqtt import DetectionMessageHandler, MqttSubscriber
from pigeondome.adapters.postgres import PostgresDetectionRepository
from pigeondome.application.ports import DetectionRepository, StorageError
from pigeondome.application.use_cases import GetPresenceStats, IngestDetection
from pigeondome.config import DatabaseSettings, MqttSettings
from pigeondome.migrate import apply_migrations

log = logging.getLogger("pigeondome")
REPORT_EVERY_S = 10


def report(handler: DetectionMessageHandler, presence: GetPresenceStats) -> None:
    now = datetime.now(UTC)
    start = now - timedelta(minutes=5)
    end = now + timedelta(seconds=1)
    for device in handler.devices_snapshot():
        try:
            stats = presence.execute(device, start, end)
        except StorageError:
            log.warning("não foi possível medir a presença de %s: banco indisponível", device)
            continue
        log.info(
            "%s: leituras=%d presença=%.0f%% média=%.1f máx=%d",
            device,
            stats.readings,
            stats.presence_rate * 100,
            stats.mean_pigeons,
            stats.max_pigeons,
        )
    log.info(
        "contadores: aceitas=%d duplicadas=%d rejeitadas=%d falhas_de_gravação=%d",
        handler.accepted,
        handler.duplicates,
        handler.rejected,
        handler.storage_errors,
    )


def serve(settings: MqttSettings, repository: DetectionRepository) -> None:
    handler = DetectionMessageHandler(DetectionParser(), IngestDetection(repository))
    presence = GetPresenceStats(repository)
    subscriber = MqttSubscriber(settings, handler)
    subscriber.start()
    try:
        while True:
            time.sleep(REPORT_EVERY_S)
            report(handler, presence)
    except KeyboardInterrupt:
        log.info("encerrando")
    finally:
        subscriber.stop()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    storage = os.environ.get("PIGEONDOME_STORAGE", "postgres")
    db_settings: DatabaseSettings | None = None
    try:
        mqtt_settings = MqttSettings.from_env()
        if storage not in ("postgres", "memory"):
            raise ValueError("PIGEONDOME_STORAGE deve ser 'postgres' ou 'memory'")
        if storage == "postgres":
            db_settings = DatabaseSettings.from_env()
    except ValueError as exc:
        log.error("configuração inválida: %s", exc)
        return 2

    if db_settings is None:
        log.warning("armazenamento em memória: os dados serão perdidos ao encerrar")
        serve(mqtt_settings, InMemoryDetectionRepository())
        return 0

    try:
        for name in apply_migrations(db_settings.conninfo):
            log.info("migração aplicada: %s", name)
        pool = ConnectionPool(db_settings.conninfo, min_size=1, max_size=4, open=True)
        try:
            pool.wait(timeout=10)
            serve(mqtt_settings, PostgresDetectionRepository(pool))
        finally:
            pool.close()
    except psycopg.Error as exc:
        log.error("banco de dados indisponível: %s", exc)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
