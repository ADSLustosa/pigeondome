import logging
import random
import sys
import time
from datetime import datetime

from pigeondome_sim.config import Settings
from pigeondome_sim.generator import DetectionGenerator
from pigeondome_sim.publisher import CameraPublisher


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        settings = Settings.from_env()
    except ValueError as exc:
        logging.error("configuração inválida: %s", exc)
        return 2

    generator = DetectionGenerator(settings.device_id, random.Random(settings.seed))
    publisher = CameraPublisher(settings)
    publisher.start()
    try:
        while True:
            now = datetime.now().astimezone()
            if settings.force_hour is not None:
                now = now.replace(hour=settings.force_hour)
            publisher.publish_detection(generator.generate(now))
            time.sleep(settings.interval_s)
    except KeyboardInterrupt:
        logging.info("encerrando")
    finally:
        publisher.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
