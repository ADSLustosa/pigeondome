"""Batimento do controlador: grava de tempos em tempos e tenta de novo se o banco falhar."""

from datetime import UTC, datetime, timedelta

from pigeondome.adapters.memory_status import InMemoryControllerStatusRepository
from pigeondome.application.heartbeat import ControllerHeartbeat
from pigeondome.application.ports import StorageError
from pigeondome.domain.actuation import Mode
from pigeondome.domain.status import ControllerStatusRecord

T0 = datetime(2026, 10, 24, 21, 0, 0, tzinfo=UTC)
CAMERA = "cam-sim-01"
ACTUATOR = "act-sim-01"


class CountingStatus(InMemoryControllerStatusRepository):
    """Conta as gravações e falha sob demanda."""

    def __init__(self) -> None:
        super().__init__()
        self.saves = 0
        self.failures_left = 0

    def save(self, record: ControllerStatusRecord) -> None:
        if self.failures_left:
            self.failures_left -= 1
            raise StorageError("banco fora")
        self.saves += 1
        super().save(record)


def at(seconds: float) -> datetime:
    return T0 + timedelta(seconds=seconds)


def make() -> tuple[ControllerHeartbeat, CountingStatus]:
    repository = CountingStatus()
    return ControllerHeartbeat(repository, Mode.LIVE, CAMERA, ACTUATOR, T0), repository


def test_the_first_beat_is_written_immediately() -> None:
    heartbeat, repository = make()
    heartbeat.beat(at(1))
    assert repository.get() == ControllerStatusRecord(Mode.LIVE, CAMERA, ACTUATOR, T0, at(1))


def test_beats_inside_the_interval_are_not_written() -> None:
    heartbeat, repository = make()
    for seconds in (1, 2, 5.9):
        heartbeat.beat(at(seconds))
    assert repository.saves == 1


def test_a_beat_after_the_interval_is_written_and_keeps_the_start_time() -> None:
    heartbeat, repository = make()
    heartbeat.beat(at(1))
    heartbeat.beat(at(6))  # exatamente 5 s depois: já vale
    assert repository.saves == 2
    assert repository.get() == ControllerStatusRecord(Mode.LIVE, CAMERA, ACTUATOR, T0, at(6))


def test_a_failed_write_is_retried_on_the_very_next_beat() -> None:
    heartbeat, repository = make()
    repository.failures_left = 1
    heartbeat.beat(at(1))
    assert repository.saves == 0
    heartbeat.beat(at(2))  # não espera o intervalo: o anterior não foi gravado
    assert repository.saves == 1
