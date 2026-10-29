"""Política com sensor de presença como fonte da evidência (ADR 0009).

O sensor só diz "presente" ou "ausente": não sabe se é pombo, outra ave ou pessoa. Estes testes
conferem que a política aceita essa fonte SEM afrouxar nenhuma regra de segurança.
"""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from pigeondome.domain.actuation import (
    ActuatorStatus,
    Arm,
    Decision,
    EvidenceSource,
    Mode,
    PolicyConfig,
    PolicyContext,
    Reason,
    Verdict,
    decide,
    gather_evidence,
)
from pigeondome.domain.models import Detection, InvalidDetectionError, PresenceReading

SENSOR = "pir-sim-01"
NOW = datetime(2026, 10, 23, 15, 0, 0, tzinfo=UTC)  # 12:00 em Fortaleza
LIVE = PolicyConfig(mode=Mode.LIVE, source=EvidenceSource.PRESENCE_SENSOR)


def sensor_readings(
    pattern: str = "+++++", *, spacing: float = 5.0, latest_age: float = 1.0, now: datetime = NOW
) -> list[PresenceReading]:
    """Uma leitura por caractere, da MAIS ANTIGA para a mais recente: '+' presente, '-' ausente."""
    last = len(pattern) - 1
    return [
        PresenceReading(
            SENSOR, now - timedelta(seconds=latest_age + (last - i) * spacing), c == "+"
        )
        for i, c in enumerate(pattern)
    ]


def idle(now: datetime = NOW) -> ActuatorStatus:
    return ActuatorStatus(online=True, state="idle", reported_at=now - timedelta(seconds=3))


def run(
    config: PolicyConfig = LIVE,
    *,
    data: list[PresenceReading] | list[Detection] | None = None,
    actuator: ActuatorStatus | None = None,
    context: PolicyContext | None = None,
    now: datetime = NOW,
) -> Decision:
    return decide(
        config,
        now,
        sensor_readings(now=now) if data is None else data,
        actuator if actuator is not None else idle(now),
        context if context is not None else PolicyContext(),
    )


def test_default_source_is_still_the_camera() -> None:
    assert PolicyConfig().source is EvidenceSource.CAMERA


def test_confirmed_presence_triggers_a_pulse() -> None:
    decision = run()
    assert (decision.verdict, decision.reason) == (Verdict.PULSE, Reason.EVIDENCE_CONFIRMED)
    assert decision.evidence.source is EvidenceSource.PRESENCE_SENSOR
    assert decision.evidence.detections == 5


def test_sensor_has_no_confidence_and_the_policy_ignores_it() -> None:
    decision = run(
        PolicyConfig(mode=Mode.LIVE, source=EvidenceSource.PRESENCE_SENSOR, min_confidence=1.0)
    )
    assert decision.verdict is Verdict.PULSE
    assert decision.evidence.mean_confidence == 0.0


@pytest.mark.parametrize(
    ("pattern", "expected"),
    [
        ("++", Reason.INSUFFICIENT_EVIDENCE),  # poucas leituras positivas
        ("+++", Reason.EVIDENCE_CONFIRMED),  # exatamente o mínimo
        ("+-+-+-", Reason.INSUFFICIENT_EVIDENCE),  # três positivas, mas a mais recente é ausente
        ("+-+-+", Reason.EVIDENCE_CONFIRMED),  # intercaladas: contam só as positivas
        ("+++-", Reason.INSUFFICIENT_EVIDENCE),  # a presença acabou: não pulsa
        ("-----", Reason.INSUFFICIENT_EVIDENCE),
    ],
)
def test_confirmation_needs_enough_positives_and_a_present_latest(
    pattern: str, expected: Reason
) -> None:
    assert run(data=sensor_readings(pattern)).reason is expected


def test_minimum_positives_is_configurable() -> None:
    config = PolicyConfig(
        mode=Mode.LIVE, source=EvidenceSource.PRESENCE_SENSOR, presence_min_positive=1
    )
    assert run(config, data=sensor_readings("+")).verdict is Verdict.PULSE
    strict = PolicyConfig(
        mode=Mode.LIVE, source=EvidenceSource.PRESENCE_SENSOR, presence_min_positive=6
    )
    assert run(strict, data=sensor_readings("+++++")).reason is Reason.INSUFFICIENT_EVIDENCE


def test_readings_outside_the_window_do_not_count() -> None:
    old = sensor_readings("++++", spacing=20.0)  # só 2 caem nos últimos 30 s
    assert run(data=old).reason is Reason.INSUFFICIENT_EVIDENCE


def test_silent_sensor_is_stale_data_not_absence() -> None:
    """Sem leituras (sensor parado) não é "ausente": é dado velho, e a política não age."""
    assert run(data=[]).reason is Reason.STALE_DATA
    assert run(data=sensor_readings("+++++", latest_age=20.0)).reason is Reason.STALE_DATA


def test_sensor_ignores_camera_readings() -> None:
    camera = [Detection("cam-sim-01", NOW - timedelta(seconds=1 + i), 3, 0.95) for i in range(5)]
    assert run(data=camera).reason is Reason.STALE_DATA


def test_camera_ignores_sensor_readings() -> None:
    camera_config = PolicyConfig(mode=Mode.LIVE)
    assert run(camera_config, data=sensor_readings("+++++")).reason is Reason.STALE_DATA


def test_mixed_readings_only_count_the_configured_source() -> None:
    camera = [Detection("cam-sim-01", NOW - timedelta(seconds=1 + i), 3, 0.95) for i in range(5)]
    mixed = [*sensor_readings("++"), *camera]  # 2 positivas do sensor: abaixo do mínimo
    assert run(data=mixed).reason is Reason.INSUFFICIENT_EVIDENCE
    assert run(PolicyConfig(mode=Mode.LIVE), data=mixed).verdict is Verdict.PULSE


def test_gather_evidence_reports_the_source() -> None:
    sensor = gather_evidence(LIVE, NOW, sensor_readings("++-"))
    assert (sensor.readings, sensor.detections, sensor.latest_has_pigeons) == (3, 2, False)
    assert sensor.source is EvidenceSource.PRESENCE_SENSOR
    assert gather_evidence(PolicyConfig(), NOW, []).source is EvidenceSource.CAMERA


# Toda regra de segurança continua valendo com o sensor, e na mesma ordem.
@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"context": PolicyContext(kill_switch=True)}, Reason.KILL_SWITCH),
        (
            {"actuator": ActuatorStatus(online=False, state="idle", reported_at=None)},
            Reason.ACTUATOR_UNAVAILABLE,
        ),
        (
            {"context": PolicyContext(last_pulse_at=NOW - timedelta(seconds=30))},
            Reason.RETRY_GAP,
        ),
        ({"context": PolicyContext(pulses_today=40)}, Reason.DAILY_BUDGET),
    ],
)
def test_safety_rules_still_block_the_sensor(kwargs: dict[str, object], expected: Reason) -> None:
    assert run(**kwargs).reason is expected  # type: ignore[arg-type]


def test_quiet_hours_still_block_the_sensor() -> None:
    config = PolicyConfig(
        mode=Mode.LIVE,
        source=EvidenceSource.PRESENCE_SENSOR,
        quiet_start_hour=11,
        quiet_end_hour=13,
    )
    assert run(config).reason is Reason.QUIET_HOURS


def test_dry_run_is_still_the_default_mode_with_the_sensor() -> None:
    config = PolicyConfig(source=EvidenceSource.PRESENCE_SENSOR)
    decision = run(config)
    assert (decision.verdict, decision.reason) == (Verdict.WOULD_PULSE, Reason.DRY_RUN)


def test_experiment_control_blocks_the_sensor_too() -> None:
    config = PolicyConfig(
        mode=Mode.EXPERIMENT, source=EvidenceSource.PRESENCE_SENSOR, experiment_seed=1
    )
    arms = set()
    for hour in range(0, 24, 6):
        moment = datetime(2026, 10, 23, hour, 30, tzinfo=timezone(timedelta(hours=-3)))
        decision = run(config, now=moment)
        assert decision.reason in {Reason.EXPERIMENT_CONTROL, Reason.EVIDENCE_CONFIRMED}
        arms.add(decision.arm)
    assert arms == {Arm.TREATMENT, Arm.CONTROL}


def test_invalid_minimum_positives_is_rejected() -> None:
    with pytest.raises(ValueError, match="presence_min_positive"):
        PolicyConfig(presence_min_positive=0)


def test_presence_reading_validates_identity_and_time() -> None:
    PresenceReading(SENSOR, NOW, True)
    with pytest.raises(InvalidDetectionError):
        PresenceReading("X", NOW, True)
    with pytest.raises(InvalidDetectionError):
        PresenceReading(SENSOR, datetime(2026, 10, 23, 15, 0, 0), True)  # noqa: DTZ001
