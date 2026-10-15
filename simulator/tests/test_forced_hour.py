import random
from datetime import UTC, datetime

from pigeondome_sim.generator import DetectionGenerator

NIGHT = datetime(2026, 10, 14, 3, 0, tzinfo=UTC)


def test_forced_hour_changes_the_model_not_the_timestamp() -> None:
    detection = DetectionGenerator("cam-sim-01", random.Random(1)).generate(NIGHT, hour=8)
    assert detection.timestamp == NIGHT


def test_forced_hour_makes_pigeons_appear_at_night() -> None:
    counts = [
        DetectionGenerator("cam-sim-01", random.Random(seed)).generate(NIGHT, hour=8).pigeon_count
        for seed in range(50)
    ]
    assert max(counts) > 0
