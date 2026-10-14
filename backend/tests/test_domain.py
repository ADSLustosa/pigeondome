from datetime import UTC, datetime

import pytest

from pigeondome.domain.models import Detection, InvalidDetectionError

NOW = datetime(2026, 10, 14, 8, 0, tzinfo=UTC)


def make(
    device_id: str = "cam-sim-01",
    pigeon_count: int = 3,
    confidence: float = 0.9,
) -> Detection:
    return Detection(device_id, NOW, pigeon_count, confidence)


def test_valid_detection_is_created() -> None:
    assert make().has_pigeons is True
    assert make(pigeon_count=0).has_pigeons is False


@pytest.mark.parametrize(
    "kwargs",
    [
        {"device_id": "Cam 01"},
        {"device_id": "ab"},
        {"pigeon_count": -1},
        {"pigeon_count": 51},
        {"confidence": 1.5},
        {"confidence": -0.1},
    ],
)
def test_invalid_detection_is_rejected(kwargs: dict[str, object]) -> None:
    with pytest.raises(InvalidDetectionError):
        make(**kwargs)  # type: ignore[arg-type]


def test_naive_timestamp_is_rejected() -> None:
    with pytest.raises(InvalidDetectionError):
        Detection("cam-sim-01", datetime(2026, 10, 14, 8, 0), 1, 0.9)  # noqa: DTZ001
