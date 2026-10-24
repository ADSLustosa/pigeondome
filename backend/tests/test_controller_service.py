"""Serviço do controlador: ler, decidir, registrar e comandar, tudo com repositórios em memória."""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from pigeondome.adapters.memory import InMemoryDetectionRepository
from pigeondome.adapters.memory_actuation import (
    InMemoryControllerFlags,
    InMemoryDecisionRepository,
)
from pigeondome.application.controller_service import CommandSendError, ControllerService
from pigeondome.application.ports import StorageError
from pigeondome.domain.actuation import (
    ActuatorStatus,
    Decision,
    Mode,
    PolicyConfig,
    Reason,
    Verdict,
)
from pigeondome.domain.actuation_log import DecisionRecord
from pigeondome.domain.models import Detection

NOW = datetime(2026, 10, 24, 15, 0, 0, tzinfo=UTC)  # 12:00 em Fortaleza
CAMERA = "cam-sim-01"
ACTUATOR = "act-sim-01"
UUID = "3f2b8c1e-7a4d-4e5b-9c6a-1d2e3f4a5b6c"
HOUR = timedelta(hours=1)


@dataclass
class FakeSender:
    fail: bool = False
    calls: list[tuple[str, int, datetime]] = field(default_factory=list)

    def send_pulse(self, actuator_id: str, duration_s: int, now: datetime) -> str:
        if self.fail:
            raise CommandSendError("sem conexão")
        self.calls.append((actuator_id, duration_s, now))
        return UUID


class FakeStatus:
    def __init__(self) -> None:
        self.value = ActuatorStatus(True, "idle", NOW)

    def current(self) -> ActuatorStatus:
        return self.value


class BrokenDetections:
    def list_between(self, device_id: str, start: datetime, end: datetime) -> list[Detection]:
        raise StorageError("banco fora")


class FlakyDecisions(InMemoryDecisionRepository):
    """Falha na primeira gravação e funciona nas seguintes."""

    def __init__(self) -> None:
        super().__init__()
        self.failures_left = 1

    def add(self, record: DecisionRecord) -> bool:
        if self.failures_left:
            self.failures_left -= 1
            raise StorageError("banco fora")
        return super().add(record)


class World:
    def __init__(
        self, policy: PolicyConfig, *, detections: Any = None, decisions: Any = None
    ) -> None:
        self.policy = policy
        self.detections = detections if detections is not None else InMemoryDetectionRepository()
        self.decisions = decisions if decisions is not None else InMemoryDecisionRepository()
        self.flags = InMemoryControllerFlags()
        self.sender = FakeSender()
        self.status = FakeStatus()
        self.presence = True
        self.service = self.make_service()

    def make_service(self) -> ControllerService:
        return ControllerService(
            self.policy,
            CAMERA,
            ACTUATOR,
            self.detections,
            self.decisions,
            self.flags,
            self.status,
            self.sender,
        )

    def preload(self, pigeons: int = 3) -> None:
        for age in range(1, 6):
            self.detections.add(Detection(CAMERA, NOW - timedelta(seconds=age), pigeons, 0.9))

    def step(self, seconds: float, service: ControllerService | None = None) -> Decision | None:
        now = NOW + timedelta(seconds=seconds)
        if self.presence:
            self.detections.add(Detection(CAMERA, now - timedelta(seconds=1), 3, 0.9))
        self.status.value = ActuatorStatus(True, "idle", now - timedelta(seconds=1))
        return (service or self.service).step(now)

    def records(self) -> list[DecisionRecord]:
        return self.decisions.list_between(ACTUATOR, NOW - HOUR, NOW + HOUR)  # type: ignore[no-any-return]


def test_dry_run_decides_and_records_but_never_commands() -> None:
    world = World(PolicyConfig(mode=Mode.DRY_RUN))
    world.preload()
    decision = world.step(0)
    assert decision is not None
    assert (decision.verdict, decision.reason) == (Verdict.WOULD_PULSE, Reason.DRY_RUN)
    assert world.sender.calls == []
    assert [(r.mode, r.verdict, r.command_id) for r in world.records()] == [
        (Mode.DRY_RUN, Verdict.WOULD_PULSE, None)
    ]


def test_only_changes_of_reason_are_recorded_after_a_trigger() -> None:
    world = World(PolicyConfig(mode=Mode.DRY_RUN))
    world.preload()
    for seconds in range(5):
        world.step(seconds)
    reasons = [r.reason for r in world.records()]
    assert reasons == [Reason.DRY_RUN, Reason.RETRY_GAP]  # os 3 retry_gap seguintes não repetem


def test_live_sends_the_pulse_and_records_the_command_id() -> None:
    world = World(PolicyConfig(mode=Mode.LIVE))
    world.preload()
    decision = world.step(0)
    assert decision is not None and decision.verdict is Verdict.PULSE
    assert world.sender.calls == [(ACTUATOR, 5, NOW)]
    (record,) = world.records()
    assert (record.verdict, record.command_id, record.triggered) == (Verdict.PULSE, UUID, True)
    second = world.step(1)
    assert second is not None and second.reason is Reason.RETRY_GAP
    assert len(world.sender.calls) == 1


def test_a_failed_send_is_not_a_trigger_and_the_next_step_tries_again() -> None:
    world = World(PolicyConfig(mode=Mode.LIVE))
    world.preload()
    world.sender.fail = True
    failed = world.step(0)
    assert failed is not None
    assert (failed.verdict, failed.reason, failed.detail) == (
        Verdict.SKIP,
        Reason.ACTUATOR_UNAVAILABLE,
        "send_failed",
    )
    assert not failed.triggered
    world.sender.fail = False
    retried = world.step(1)
    assert retried is not None and retried.verdict is Verdict.PULSE
    assert len(world.sender.calls) == 1


def test_without_the_database_no_decision_is_made() -> None:
    world = World(PolicyConfig(mode=Mode.LIVE), detections=BrokenDetections())
    world.presence = False  # o auxiliar não grava leituras novas: só o list_between quebra
    assert world.step(0) is None
    assert world.sender.calls == []
    assert world.records() == []


def test_a_failed_write_never_leads_to_a_second_pulse() -> None:
    world = World(PolicyConfig(mode=Mode.LIVE), decisions=FlakyDecisions())
    world.preload()
    first = world.step(0)
    assert first is not None and first.verdict is Verdict.PULSE
    assert world.records() == []  # a gravação falhou, mas o pulso saiu
    second = world.step(1)
    assert second is not None and second.reason is Reason.RETRY_GAP  # lembra do próprio disparo
    assert len(world.sender.calls) == 1


def test_the_kill_switch_stops_commands_and_is_recorded() -> None:
    world = World(PolicyConfig(mode=Mode.LIVE))
    world.preload()
    world.flags.set_kill_switch(True, NOW)
    decision = world.step(0)
    assert decision is not None and decision.reason is Reason.KILL_SWITCH
    assert world.sender.calls == []
    assert [r.reason for r in world.records()] == [Reason.KILL_SWITCH]


def test_a_quiet_garden_records_a_single_line() -> None:
    world = World(PolicyConfig(mode=Mode.LIVE))
    world.presence = False
    world.preload(pigeons=0)
    for seconds in range(5):
        world.step(seconds)
    assert [r.reason for r in world.records()] == [Reason.INSUFFICIENT_EVIDENCE]


def test_the_daily_budget_survives_a_restart() -> None:
    policy = PolicyConfig(mode=Mode.LIVE, retry_gap_s=0.0, max_pulses_per_day=1)
    world = World(policy)
    world.preload()
    first = world.step(0)
    assert first is not None and first.verdict is Verdict.PULSE
    restarted = world.make_service()  # processo novo, mesma trilha no banco
    second = world.step(10, restarted)
    assert second is not None and second.reason is Reason.DAILY_BUDGET
    assert len(world.sender.calls) == 1
