from datetime import UTC, datetime, timedelta

import pytest

from pigeondome.adapters.memory import InMemoryDetectionRepository
from pigeondome.application.use_cases import GetPresenceStats, IngestDetection
from pigeondome.domain.models import Detection

T0 = datetime(2026, 10, 14, 8, 0, tzinfo=UTC)
DEVICE = "cam-sim-01"


def det(minutes: int, count: int, device: str = DEVICE) -> Detection:
    return Detection(device, T0 + timedelta(minutes=minutes), count, 0.9)


def stats(repo: InMemoryDetectionRepository, minutes: int = 10, device: str = DEVICE):  # noqa: ANN201
    return GetPresenceStats(repo).execute(device, T0, T0 + timedelta(minutes=minutes))


def test_ingest_is_idempotent() -> None:
    repo = InMemoryDetectionRepository()
    ingest = IngestDetection(repo)
    assert ingest.execute(det(0, 3)) is True
    assert ingest.execute(det(0, 3)) is False
    assert stats(repo).readings == 1


def test_stats_for_empty_window() -> None:
    result = stats(InMemoryDetectionRepository())
    assert (result.readings, result.mean_pigeons, result.presence_rate) == (0, 0.0, 0.0)


def test_stats_values() -> None:
    repo = InMemoryDetectionRepository()
    for minute, count in [(0, 0), (1, 4), (2, 2), (3, 0)]:
        repo.add(det(minute, count))
    result = stats(repo)
    assert result.readings == 4
    assert result.readings_with_pigeons == 2
    assert result.mean_pigeons == 1.5
    assert result.max_pigeons == 4
    assert result.presence_rate == 0.5


def test_window_is_half_open() -> None:
    repo = InMemoryDetectionRepository()
    repo.add(det(0, 1))
    repo.add(det(10, 9))  # exatamente no fim: fora da janela
    result = stats(repo, minutes=10)
    assert (result.readings, result.max_pigeons) == (1, 1)


def test_other_devices_are_ignored() -> None:
    repo = InMemoryDetectionRepository()
    repo.add(det(0, 5, device="cam-outra"))
    assert stats(repo).readings == 0


def test_invalid_window_is_rejected() -> None:
    with pytest.raises(ValueError, match="janela"):
        GetPresenceStats(InMemoryDetectionRepository()).execute(DEVICE, T0, T0)
