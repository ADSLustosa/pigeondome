"""Política do controlador: cada regra, uma por vez, e a ordem entre elas."""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from pigeondome.domain.actuation import (
    ActuatorStatus,
    Arm,
    Decision,
    Evidence,
    Mode,
    PolicyConfig,
    PolicyContext,
    Reason,
    Verdict,
    decide,
    experiment_arm,
    gather_evidence,
)
from pigeondome.domain.models import Detection

CAMERA = "cam-sim-01"
LOCAL_TZ = timezone(timedelta(hours=-3))  # Fortaleza
NOW = datetime(2026, 10, 23, 15, 0, 0, tzinfo=UTC)  # 12:00 em Fortaleza
LIVE = PolicyConfig(mode=Mode.LIVE)


def readings(
    now: datetime = NOW,
    *,
    count: int = 4,
    pigeons: int = 3,
    confidence: float = 0.9,
    spacing: float = 5.0,
    latest_age: float = 1.0,
) -> list[Detection]:
    """`count` leituras espaçadas de `spacing` s; a mais recente tem `latest_age` s de idade."""
    return [
        Detection(CAMERA, now - timedelta(seconds=latest_age + i * spacing), pigeons, confidence)
        for i in range(count)
    ]


def idle(now: datetime = NOW) -> ActuatorStatus:
    return ActuatorStatus(online=True, state="idle", reported_at=now - timedelta(seconds=3))


def run(
    config: PolicyConfig = LIVE,
    *,
    now: datetime = NOW,
    data: list[Detection] | None = None,
    actuator: ActuatorStatus | None = None,
    context: PolicyContext | None = None,
) -> Decision:
    return decide(
        config,
        now,
        readings(now) if data is None else data,
        actuator if actuator is not None else idle(now),
        context if context is not None else PolicyContext(),
    )


def at_local(hour: int, minute: int = 30) -> datetime:
    return datetime(2026, 10, 23, hour, minute, tzinfo=LOCAL_TZ)


def test_defaults_are_conservative() -> None:
    config = PolicyConfig()
    assert config.mode is Mode.DRY_RUN  # nunca liga sozinho
    assert config.pulse_s == 5
    assert config.quiet_start_hour is None


def test_confirmed_presence_triggers_a_pulse() -> None:
    decision = run()
    assert (decision.verdict, decision.reason) == (Verdict.PULSE, Reason.EVIDENCE_CONFIRMED)
    assert decision.duration_s == 5
    assert decision.triggered
    assert decision.arm is None
    assert decision.evidence.detections == 4
    assert decision.evidence.mean_confidence == pytest.approx(0.9)


def test_dry_run_reports_what_it_would_have_done() -> None:
    decision = run(PolicyConfig(mode=Mode.DRY_RUN))
    assert (decision.verdict, decision.reason) == (Verdict.WOULD_PULSE, Reason.DRY_RUN)
    assert decision.duration_s == 5
    assert decision.triggered


@pytest.mark.parametrize(
    ("config", "context", "reason"),
    [
        pytest.param(PolicyConfig(mode=Mode.OFF), PolicyContext(), Reason.MODE_OFF, id="mode_off"),
        pytest.param(LIVE, PolicyContext(kill_switch=True), Reason.KILL_SWITCH, id="kill_switch"),
    ],
)
def test_mode_off_and_the_kill_switch_stop_everything(
    config: PolicyConfig, context: PolicyContext, reason: Reason
) -> None:
    decision = run(config, context=context)
    assert (decision.verdict, decision.reason) == (Verdict.SKIP, reason)
    assert decision.duration_s is None
    assert not decision.triggered


@pytest.mark.parametrize(
    "data",
    [[], readings(latest_age=20.0)],
    ids=["no_readings", "latest_reading_too_old"],
)
def test_missing_or_old_data_is_never_acted_upon(data: list[Detection]) -> None:
    assert run(data=data).reason is Reason.STALE_DATA


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(readings(count=2), id="too_few_detections"),
        pytest.param(readings(confidence=0.5), id="low_confidence"),
        pytest.param(readings(pigeons=0), id="no_pigeons_at_all"),
        pytest.param(
            [Detection(CAMERA, NOW - timedelta(seconds=1), 0, 0.9), *readings(latest_age=6.0)],
            id="presence_already_ended",
        ),
    ],
)
def test_weak_evidence_is_not_enough(data: list[Detection]) -> None:
    decision = run(data=data)
    assert (decision.verdict, decision.reason) == (Verdict.SKIP, Reason.INSUFFICIENT_EVIDENCE)


def test_mean_confidence_only_counts_readings_with_pigeons() -> None:
    zeros = [Detection(CAMERA, NOW - timedelta(seconds=2 + i), 0, 0.1) for i in range(3)]
    evidence = gather_evidence(LIVE, NOW, [*readings(), *zeros])
    assert evidence.mean_confidence == pytest.approx(0.9)
    assert evidence.latest_has_pigeons
    assert evidence.readings == 7


def test_readings_outside_the_window_or_in_the_future_are_ignored() -> None:
    noise = [
        Detection(CAMERA, NOW + timedelta(seconds=10), 5, 0.99),
        Detection(CAMERA, NOW - timedelta(seconds=100), 5, 0.99),
    ]
    assert gather_evidence(LIVE, NOW, [*readings(), *noise]).readings == 4


@pytest.mark.parametrize(
    ("hour", "quiet"),
    [(22, True), (23, True), (0, True), (4, True), (5, False), (12, False), (21, False)],
)
def test_quiet_hours_can_wrap_around_midnight(hour: int, quiet: bool) -> None:
    config = PolicyConfig(mode=Mode.LIVE, quiet_start_hour=22, quiet_end_hour=5)
    decision = run(config, now=at_local(hour))
    assert (decision.reason is Reason.QUIET_HOURS) == quiet
    if not quiet:
        assert decision.verdict is Verdict.PULSE


@pytest.mark.parametrize(
    ("hour", "quiet"), [(8, False), (9, True), (12, True), (16, True), (17, False)]
)
def test_quiet_hours_without_wrapping(hour: int, quiet: bool) -> None:
    config = PolicyConfig(mode=Mode.LIVE, quiet_start_hour=9, quiet_end_hour=17)
    assert (run(config, now=at_local(hour)).reason is Reason.QUIET_HOURS) == quiet


@pytest.mark.parametrize(
    ("status", "detail"),
    [
        pytest.param(
            ActuatorStatus(False, "idle", NOW - timedelta(seconds=3)), "offline", id="off"
        ),
        pytest.param(ActuatorStatus(True, "idle", None), "stale_report", id="never_reported"),
        pytest.param(
            ActuatorStatus(True, "idle", NOW - timedelta(seconds=31)), "stale_report", id="old"
        ),
        pytest.param(
            ActuatorStatus(True, "cooldown", NOW - timedelta(seconds=3)), "cooldown", id="cooldown"
        ),
        pytest.param(
            ActuatorStatus(True, "pulsing", NOW - timedelta(seconds=3)), "pulsing", id="pulsing"
        ),
        pytest.param(
            ActuatorStatus(True, "fault", NOW - timedelta(seconds=3)), "fault", id="fault"
        ),
        pytest.param(
            ActuatorStatus(True, "maintenance", NOW - timedelta(seconds=3)),
            "maintenance",
            id="maintenance",
        ),
        pytest.param(
            ActuatorStatus(True, "safe_off", NOW - timedelta(seconds=3)), "safe_off", id="safe_off"
        ),
        pytest.param(
            ActuatorStatus(True, "idle", NOW - timedelta(seconds=30)), None, id="fresh_at_the_limit"
        ),
    ],
)
def test_actuator_must_be_online_fresh_and_idle(status: ActuatorStatus, detail: str | None) -> None:
    decision = run(actuator=status)
    if detail is None:
        assert decision.verdict is Verdict.PULSE
    else:
        assert (decision.reason, decision.detail) == (Reason.ACTUATOR_UNAVAILABLE, detail)
        assert not decision.triggered


@pytest.mark.parametrize(
    ("seconds_ago", "blocked"), [(10, True), (119, True), (120, False), (500, False)]
)
def test_minimum_gap_between_triggers(seconds_ago: float, blocked: bool) -> None:
    context = PolicyContext(last_pulse_at=NOW - timedelta(seconds=seconds_ago))
    decision = run(context=context)
    assert (decision.reason is Reason.RETRY_GAP) == blocked


@pytest.mark.parametrize(
    ("pulses_today", "limit", "blocked"),
    [(40, 40, True), (39, 40, False), (0, 0, True), (5, 6, False)],
)
def test_daily_budget(pulses_today: int, limit: int, blocked: bool) -> None:
    config = PolicyConfig(mode=Mode.LIVE, max_pulses_per_day=limit)
    decision = run(config, context=PolicyContext(pulses_today=pulses_today))
    assert (decision.reason is Reason.DAILY_BUDGET) == blocked


OFFLINE = ActuatorStatus(False, "idle", None)
QUIET_ALL_DAY = PolicyConfig(mode=Mode.LIVE, quiet_start_hour=0, quiet_end_hour=23)


@pytest.mark.parametrize(
    ("config", "data", "actuator", "context", "expected"),
    [
        pytest.param(
            LIVE,
            [],
            OFFLINE,
            PolicyContext(kill_switch=True, pulses_today=99),
            Reason.KILL_SWITCH,
            id="kill_switch_beats_everything",
        ),
        pytest.param(
            LIVE, [], OFFLINE, PolicyContext(), Reason.STALE_DATA, id="stale_data_beats_the_rest"
        ),
        pytest.param(
            LIVE,
            readings(count=1),
            OFFLINE,
            PolicyContext(),
            Reason.INSUFFICIENT_EVIDENCE,
            id="evidence_beats_the_actuator",
        ),
        pytest.param(
            QUIET_ALL_DAY,
            None,
            OFFLINE,
            PolicyContext(),
            Reason.QUIET_HOURS,
            id="quiet_hours_beat_the_actuator",
        ),
        pytest.param(
            LIVE,
            None,
            OFFLINE,
            PolicyContext(last_pulse_at=NOW - timedelta(seconds=10), pulses_today=99),
            Reason.ACTUATOR_UNAVAILABLE,
            id="actuator_beats_gap_and_budget",
        ),
        pytest.param(
            LIVE,
            None,
            None,
            PolicyContext(last_pulse_at=NOW - timedelta(seconds=10), pulses_today=99),
            Reason.RETRY_GAP,
            id="gap_beats_budget",
        ),
    ],
)
def test_rules_are_evaluated_in_a_fixed_order(
    config: PolicyConfig,
    data: list[Detection] | None,
    actuator: ActuatorStatus | None,
    context: PolicyContext,
    expected: Reason,
) -> None:
    assert run(config, data=data, actuator=actuator, context=context).reason is expected


def hour_in_arm(config: PolicyConfig, arm: Arm) -> datetime:
    day = datetime(2026, 10, 23, tzinfo=LOCAL_TZ)
    for hour in range(24):
        moment = day + timedelta(hours=hour, minutes=30)
        if experiment_arm(config, moment) is arm:
            return moment
    raise AssertionError(f"nenhum bloco do braço {arm} nesse dia")


def test_experiment_arms_are_deterministic_and_balanced_every_day() -> None:
    config = PolicyConfig(mode=Mode.EXPERIMENT, experiment_seed=7)
    for day in range(30):
        base = datetime(2026, 10, 1, tzinfo=LOCAL_TZ) + timedelta(days=day)
        arms = [experiment_arm(config, base + timedelta(hours=hour)) for hour in range(24)]
        assert arms == [experiment_arm(config, base + timedelta(hours=h)) for h in range(24)]
        blocks = [arms[start] for start in range(0, 24, 6)]
        assert blocks.count(Arm.TREATMENT) == 2
        assert blocks.count(Arm.CONTROL) == 2
        for start in range(0, 24, 6):
            assert len(set(arms[start : start + 6])) == 1  # o bloco inteiro tem o mesmo braço


def test_experiment_seeds_change_the_assignment() -> None:
    first = PolicyConfig(experiment_seed=1)
    second = PolicyConfig(experiment_seed=2)
    moments = [
        datetime(2026, 10, 1, tzinfo=LOCAL_TZ) + timedelta(days=day, hours=hour)
        for day in range(30)
        for hour in range(0, 24, 6)
    ]
    assert any(experiment_arm(first, m) is not experiment_arm(second, m) for m in moments)


def test_experiment_mode_acts_in_treatment_blocks_and_records_control_triggers() -> None:
    config = PolicyConfig(mode=Mode.EXPERIMENT, experiment_seed=7)
    treated = run(config, now=hour_in_arm(config, Arm.TREATMENT))
    assert (treated.verdict, treated.arm) == (Verdict.PULSE, Arm.TREATMENT)
    control = run(config, now=hour_in_arm(config, Arm.CONTROL))
    assert (control.verdict, control.reason) == (Verdict.SKIP, Reason.EXPERIMENT_CONTROL)
    assert control.arm is Arm.CONTROL
    assert control.triggered  # conta no orçamento e no intervalo, como o tratamento
    assert control.evidence.detections >= 3


@pytest.mark.parametrize(
    ("verdict", "reason", "expected"),
    [
        (Verdict.PULSE, Reason.EVIDENCE_CONFIRMED, True),
        (Verdict.WOULD_PULSE, Reason.DRY_RUN, True),
        (Verdict.SKIP, Reason.EXPERIMENT_CONTROL, True),
        (Verdict.SKIP, Reason.RETRY_GAP, False),
    ],
)
def test_triggered_means_every_condition_was_met(
    verdict: Verdict, reason: Reason, expected: bool
) -> None:
    assert (
        Decision(verdict, reason, None, None, Evidence(0, 0, 0.0, None, False)).triggered
        is expected
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"pulse_s": 0},
        {"pulse_s": 11},
        {"min_detections": 0},
        {"min_confidence": 1.5},
        {"window_s": 0},
        {"retry_gap_s": -1},
        {"max_pulses_per_day": -1},
        {"experiment_block_hours": 8},
        {"experiment_block_hours": 0},
        {"quiet_start_hour": 22},
        {"quiet_start_hour": 22, "quiet_end_hour": 24},
    ],
)
def test_invalid_configuration_is_rejected(changes: dict[str, int]) -> None:
    with pytest.raises(ValueError):  # noqa: PT011
        PolicyConfig(**changes)  # type: ignore[arg-type]
