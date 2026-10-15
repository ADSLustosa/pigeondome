import logging
import sys
import time
from datetime import UTC, datetime, timedelta

from pigeondome.adapters.contract import DetectionParser
from pigeondome.adapters.memory import InMemoryDetectionRepository
from pigeondome.adapters.mqtt import DetectionMessageHandler, MqttSubscriber
from pigeondome.application.use_cases import GetPresenceStats, IngestDetection
from pigeondome.config import MqttSettings

log = logging.getLogger("pigeondome")
REPORT_EVERY_S = 10


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        settings = MqttSettings.from_env()
    except ValueError as exc:
        log.error("configuração inválida: %s", exc)
        return 2

    # Trocar este adaptador pelo PostgreSQL será a única mudança na composição.
    repository = InMemoryDetectionRepository()
    handler = DetectionMessageHandler(DetectionParser(), IngestDetection(repository))
    presence = GetPresenceStats(repository)
    subscriber = MqttSubscriber(settings, handler)
    subscriber.start()
    try:
        while True:
            time.sleep(REPORT_EVERY_S)
            now = datetime.now(UTC)
            for device in handler.devices_snapshot():
                stats = presence.execute(
                    device, now - timedelta(minutes=5), now + timedelta(seconds=1)
                )
                log.info(
                    "%s: leituras=%d presença=%.0f%% média=%.1f máx=%d",
                    device,
                    stats.readings,
                    stats.presence_rate * 100,
                    stats.mean_pigeons,
                    stats.max_pigeons,
                )
            log.info(
                "contadores: aceitas=%d duplicadas=%d rejeitadas=%d",
                handler.accepted,
                handler.duplicates,
                handler.rejected,
            )
    except KeyboardInterrupt:
        log.info("encerrando")
    finally:
        subscriber.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
