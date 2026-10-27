import logging
import random
import sys
import time
from datetime import datetime

from pigeondome_sim.config import Settings
from pigeondome_sim.frame import FrameRenderer, LatestScene
from pigeondome_sim.generator import DetectionGenerator
from pigeondome_sim.publisher import CameraPublisher
from pigeondome_sim.snapshot_server import SnapshotServer, start_snapshot_server


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        settings = Settings.from_env()
    except ValueError as exc:
        logging.error("configuração inválida: %s", exc)
        return 2

    generator = DetectionGenerator(settings.device_id, random.Random(settings.seed))
    publisher = CameraPublisher(settings)
    # o quadro é desenhado sob demanda com a contagem mais recente: imagem e número coincidem
    scene = LatestScene()
    renderer = FrameRenderer()
    server: SnapshotServer | None = None
    if settings.snapshot_port > 0:
        server = start_snapshot_server(
            settings.snapshot_port,
            lambda: renderer.render(scene.count(), datetime.now().astimezone()),
        )
    publisher.start()
    try:
        while True:
            now = datetime.now().astimezone()
            detection = generator.generate(now, settings.force_hour)
            scene.update(detection.pigeon_count)
            publisher.publish_detection(detection)
            time.sleep(settings.interval_s)
    except KeyboardInterrupt:
        logging.info("encerrando")
    finally:
        publisher.stop()
        if server is not None:
            server.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
