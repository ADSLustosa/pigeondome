"""Testes de contrato: todo adaptador da porta DetectionRepository precisa passar neles."""

from datetime import UTC, datetime, timedelta

from pigeondome.application.ports import DetectionRepository
from pigeondome.domain.models import Detection

T0 = datetime(2026, 10, 14, 8, 0, tzinfo=UTC)
DEVICE = "cam-sim-01"
HOUR = timedelta(hours=1)


def det(minutes: int, count: int, device: str = DEVICE, confidence: float = 0.9) -> Detection:
    return Detection(device, T0 + timedelta(minutes=minutes), count, confidence)


def test_add_is_idempotent(repository: DetectionRepository) -> None:
    assert repository.add(det(0, 3)) is True
    assert repository.add(det(0, 3)) is False
    assert len(repository.list_between(DEVICE, T0, T0 + HOUR)) == 1


def test_roundtrip_preserves_every_value(repository: DetectionRepository) -> None:
    original = det(5, 7, confidence=0.87)
    repository.add(original)
    assert repository.list_between(DEVICE, T0, T0 + HOUR) == [original]


def test_list_is_ordered_by_time(repository: DetectionRepository) -> None:
    for minute, count in [(3, 1), (1, 2), (2, 3)]:
        repository.add(det(minute, count))
    found = repository.list_between(DEVICE, T0, T0 + HOUR)
    assert [d.pigeon_count for d in found] == [2, 3, 1]


def test_window_is_half_open(repository: DetectionRepository) -> None:
    repository.add(det(0, 1))
    repository.add(det(10, 9))  # exatamente no fim: fora da janela
    found = repository.list_between(DEVICE, T0, T0 + timedelta(minutes=10))
    assert [d.pigeon_count for d in found] == [1]


def test_other_devices_are_ignored(repository: DetectionRepository) -> None:
    repository.add(det(0, 5, device="cam-outra"))
    assert repository.list_between(DEVICE, T0, T0 + HOUR) == []


def test_list_devices_is_empty_without_data(repository: DetectionRepository) -> None:
    assert repository.list_devices() == []


def test_list_devices_summarizes_each_device(repository: DetectionRepository) -> None:
    repository.add(det(0, 1))
    repository.add(det(5, 2))
    repository.add(det(1, 3, device="cam-outra"))
    summary = {d.device_id: d for d in repository.list_devices()}
    assert sorted(summary) == ["cam-outra", "cam-sim-01"]
    assert summary["cam-sim-01"].readings == 2
    assert summary["cam-sim-01"].last_detected_at == T0 + timedelta(minutes=5)
