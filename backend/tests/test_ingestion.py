import json
from datetime import UTC, datetime, timedelta

import pytest

from pigeondome.adapters.contract import MAX_MESSAGE_BYTES, DetectionParser, InvalidMessageError
from pigeondome.adapters.memory import InMemoryDetectionRepository
from pigeondome.adapters.mqtt import DetectionMessageHandler, Outcome
from pigeondome.application.use_cases import GetPresenceStats, IngestDetection

PARSER = DetectionParser()
TOPIC = "pigeondome/v1/cam-sim-01/detections"


def message(**overrides: object) -> bytes:
    payload = {
        "schema_version": 1,
        "device_id": "cam-sim-01",
        "timestamp": "2026-10-14T08:00:00+00:00",
        "pigeon_count": 3,
        "confidence": 0.9,
        **overrides,
    }
    return json.dumps(payload).encode()


def test_valid_message_becomes_detection() -> None:
    detection = PARSER.parse(TOPIC, message())
    assert (detection.device_id, detection.pigeon_count, detection.confidence) == (
        "cam-sim-01",
        3,
        0.9,
    )
    assert detection.timestamp.tzinfo is not None


@pytest.mark.parametrize(
    "override",
    [
        {"pigeon_count": 999},
        {"pigeon_count": "3"},
        {"confidence": 2},
        {"schema_version": 2},
        {"image_base64": "AAAA"},  # privacidade: o contrato proíbe imagens
        {"timestamp": "ontem"},
        {"timestamp": "2026-10-14T08:00:00"},  # sem fuso horário
    ],
)
def test_invalid_payload_is_rejected(override: dict[str, object]) -> None:
    with pytest.raises(InvalidMessageError):
        PARSER.parse(TOPIC, message(**override))


def test_missing_field_is_rejected() -> None:
    payload = json.loads(message())
    del payload["device_id"]
    with pytest.raises(InvalidMessageError):
        PARSER.parse(TOPIC, json.dumps(payload).encode())


@pytest.mark.parametrize(
    "raw",
    [
        b"not json",
        b"\xff\xfe",
        b"[]",
        b"null",
        b"[" * 3000,  # aninhamento profundo: RecursionError
        b" " * (MAX_MESSAGE_BYTES + 1),  # grande demais
    ],
)
def test_garbage_is_rejected(raw: bytes) -> None:
    with pytest.raises(InvalidMessageError):
        PARSER.parse(TOPIC, raw)


def test_device_in_topic_must_match_payload() -> None:
    with pytest.raises(InvalidMessageError, match="difere"):
        PARSER.parse("pigeondome/v1/cam-outra/detections", message())


@pytest.mark.parametrize(
    "topic",
    ["pigeondome/v1/cam-sim-01/status", "outro/v1/x/detections", "pigeondome/v1/detections"],
)
def test_unexpected_topic_is_rejected(topic: str) -> None:
    with pytest.raises(InvalidMessageError):
        PARSER.parse(topic, message())


def test_handler_counts_each_outcome() -> None:
    repo = InMemoryDetectionRepository()
    handler = DetectionMessageHandler(PARSER, IngestDetection(repo))
    assert handler.handle(TOPIC, message()) is Outcome.ACCEPTED
    assert handler.handle(TOPIC, message()) is Outcome.DUPLICATE
    assert handler.handle(TOPIC, b"lixo") is Outcome.REJECTED
    assert (handler.accepted, handler.duplicates, handler.rejected) == (1, 1, 1)
    assert handler.devices_snapshot() == ["cam-sim-01"]


def test_rejected_message_never_reaches_repository() -> None:
    repo = InMemoryDetectionRepository()
    handler = DetectionMessageHandler(PARSER, IngestDetection(repo))
    handler.handle(TOPIC, message(pigeon_count=999))
    start = datetime(2026, 10, 14, tzinfo=UTC)
    stats = GetPresenceStats(repo).execute("cam-sim-01", start, start + timedelta(days=1))
    assert stats.readings == 0
