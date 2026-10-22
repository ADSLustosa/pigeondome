import json
from datetime import datetime

from pigeondome.adapters.contract import DetectionParser
from pigeondome.adapters.mqtt import DetectionMessageHandler, Outcome
from pigeondome.application.ports import StorageError
from pigeondome.application.use_cases import IngestDetection
from pigeondome.domain.models import Detection


class BrokenRepository:
    def add(self, detection: Detection) -> bool:
        raise StorageError("banco fora do ar")

    def list_between(self, device_id: str, start: datetime, end: datetime) -> list[Detection]:
        raise StorageError("banco fora do ar")


def test_storage_failure_is_counted_and_never_raised() -> None:
    handler = DetectionMessageHandler(DetectionParser(), IngestDetection(BrokenRepository()))
    payload = {
        "schema_version": 1,
        "device_id": "cam-sim-01",
        "timestamp": "2026-10-14T08:00:00+00:00",
        "pigeon_count": 3,
        "confidence": 0.9,
    }
    topic = "pigeondome/v1/cam-sim-01/detections"
    assert handler.handle(topic, json.dumps(payload).encode()) is Outcome.STORAGE_ERROR
    assert handler.storage_errors == 1
    assert handler.accepted == 0
