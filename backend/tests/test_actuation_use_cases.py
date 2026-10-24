"""Contexto da política montado a partir da trilha gravada."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from pigeondome.adapters.memory_actuation import (
    InMemoryControllerFlags,
    InMemoryDecisionRepository,
)
from pigeondome.application.actuation_use_cases import LoadPolicyContext
from pigeondome.domain.actuation import Mode, PolicyContext, Reason, Verdict
from pigeondome.domain.actuation_log import DecisionRecord

NOW = datetime(2026, 10, 24, 15, 0, 0, tzinfo=UTC)  # 12:00 em Fortaleza
ACTUATOR = "act-sim-01"
UUID = "3f2b8c1e-7a4d-4e5b-9c6a-1d2e3f4a5b6c"


def record(when: datetime, *, triggered: bool = True, actuator: str = ACTUATOR) -> DecisionRecord:
    base = DecisionRecord(
        decided_at=when,
        camera_id="cam-sim-01",
        actuator_id=actuator,
        mode=Mode.LIVE,
        verdict=Verdict.PULSE if triggered else Verdict.SKIP,
        reason=Reason.EVIDENCE_CONFIRMED if triggered else Reason.RETRY_GAP,
        detail="",
        arm=None,
        duration_s=5 if triggered else None,
        command_id=UUID if triggered else None,
        readings=4,
        detections=4,
        mean_confidence=0.9,
        triggered=triggered,
    )
    return replace(base)


def load(
    decisions: InMemoryDecisionRepository,
    flags: InMemoryControllerFlags | None = None,
    mode: Mode = Mode.LIVE,
) -> PolicyContext:
    use_case = LoadPolicyContext(decisions, flags or InMemoryControllerFlags(), -3, mode)
    return use_case.execute(ACTUATOR, NOW)


def test_a_fresh_system_has_a_clean_context() -> None:
    assert load(InMemoryDecisionRepository()) == PolicyContext(False, 0, None)


def test_only_todays_triggers_count_against_the_daily_budget() -> None:
    decisions = InMemoryDecisionRepository()
    decisions.add(record(datetime(2026, 10, 24, 2, 59, 59, tzinfo=UTC)))  # ontem, 23:59:59 local
    decisions.add(record(datetime(2026, 10, 24, 3, 0, 0, tzinfo=UTC)))  # hoje, 00:00 local
    decisions.add(record(NOW - timedelta(seconds=60)))
    decisions.add(record(NOW - timedelta(seconds=30), triggered=False))  # skip não conta
    decisions.add(record(NOW - timedelta(seconds=20), actuator="act-outro"))  # outro atuador
    context = load(decisions)
    assert context.pulses_today == 2
    assert context.last_pulse_at == NOW - timedelta(seconds=60)


def test_the_last_trigger_is_reported_even_when_it_was_yesterday() -> None:
    decisions = InMemoryDecisionRepository()
    yesterday = datetime(2026, 10, 24, 2, 0, 0, tzinfo=UTC)
    decisions.add(record(yesterday))
    context = load(decisions)
    assert context.pulses_today == 0
    assert context.last_pulse_at == yesterday


def test_the_kill_switch_comes_from_the_flags() -> None:
    flags = InMemoryControllerFlags()
    assert load(InMemoryDecisionRepository(), flags).kill_switch is False
    flags.set_kill_switch(True, NOW)
    assert load(InMemoryDecisionRepository(), flags).kill_switch is True


def test_counterfactual_triggers_only_count_in_their_own_mode() -> None:
    decisions = InMemoryDecisionRepository()
    rehearsal = replace(
        record(NOW - timedelta(seconds=30)),
        mode=Mode.DRY_RUN,
        verdict=Verdict.WOULD_PULSE,
        reason=Reason.DRY_RUN,
        command_id=None,
    )
    decisions.add(rehearsal)
    assert load(decisions, mode=Mode.LIVE) == PolicyContext(False, 0, None)
    in_dry_run = load(decisions, mode=Mode.DRY_RUN)
    assert (in_dry_run.pulses_today, in_dry_run.last_pulse_at) == (1, rehearsal.decided_at)
