"""Simulação do controlador: horas de decisões aleatórias, conferindo os limites a cada passo."""

import random
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from pigeondome.domain.actuation import (
    ActuatorStatus,
    Arm,
    Mode,
    PolicyConfig,
    PolicyContext,
    Verdict,
    decide,
)
from pigeondome.domain.models import Detection

CAMERA = "cam-sim-01"
LOCAL_TZ = timezone(timedelta(hours=-3))
START = datetime(2026, 10, 23, 3, 0, 0, tzinfo=UTC)  # 00:00 em Fortaleza
STEP_S = 10
STEPS = 4320  # 12 horas
SEEDS = range(6)
QUIET = (2, 4)  # horas locais de silêncio


def simulate(seed: int, base: PolicyConfig) -> tuple[int, int]:
    """Roda 12 h de decisões e devolve (disparos, pulsos reais), conferindo as invariantes."""
    config = replace(base, experiment_seed=seed)
    rng = random.Random(seed)  # noqa: S311
    recent: list[Detection] = []
    per_day: dict[date, int] = {}
    present = False
    phase_end = START
    camera_back = START
    actuator_back = START
    busy_until = START
    reported_at = START
    kill = False
    last_trigger: datetime | None = None
    triggers = pulses = 0

    for step in range(STEPS):
        now = START + timedelta(seconds=step * STEP_S)
        where = f"modo={config.mode} seed={seed} passo={step}"
        if now >= phase_end:
            present = rng.random() < 0.6
            phase_end = now + timedelta(seconds=rng.randint(60, 600))
        if rng.random() < 0.01:
            camera_back = now + timedelta(seconds=rng.randint(20, 120))
        if rng.random() < 0.005:
            actuator_back = now + timedelta(seconds=rng.randint(30, 200))
        if rng.random() < 0.003:
            kill = not kill
        if now >= camera_back:
            count = rng.randint(1, 12) if present else 0
            recent.append(Detection(CAMERA, now, count, rng.uniform(0.6, 1.0)))
        recent = [r for r in recent if r.timestamp > now - timedelta(seconds=60)]
        online = now >= actuator_back
        if online:
            reported_at = now - timedelta(seconds=rng.randint(0, 12))
        state = "cooldown" if now < busy_until else "idle"
        local = now.astimezone(LOCAL_TZ)

        status = ActuatorStatus(online, state, reported_at)
        context = PolicyContext(kill, per_day.get(local.date(), 0), last_trigger)
        decision = decide(config, now, recent, status, context)

        if decision.verdict is Verdict.PULSE:
            assert config.mode in (Mode.LIVE, Mode.EXPERIMENT), where
            assert not kill, where
            assert online and state == "idle", where
            assert config.mode is not Mode.EXPERIMENT or decision.arm is Arm.TREATMENT, where
        if config.mode is Mode.DRY_RUN:
            assert decision.verdict is not Verdict.PULSE, where
        if decision.triggered:
            evidence = decision.evidence
            assert config.mode is not Mode.OFF and not kill, where
            assert not QUIET[0] <= local.hour < QUIET[1], f"{where}: disparo em horário de silêncio"
            assert evidence.detections >= config.min_detections, where
            assert evidence.latest_has_pigeons, where
            assert evidence.mean_confidence >= config.min_confidence, where
            if last_trigger is not None:
                gap = (now - last_trigger).total_seconds()
                assert gap >= config.retry_gap_s, f"{where}: intervalo de {gap:.0f} s"
            per_day[local.date()] = per_day.get(local.date(), 0) + 1
            assert per_day[local.date()] <= config.max_pulses_per_day, f"{where}: orçamento"
            last_trigger = now
            triggers += 1
        if decision.verdict is Verdict.PULSE:
            pulses += 1
            busy_until = now + timedelta(seconds=(decision.duration_s or 0) + 30)
    return triggers, pulses


@pytest.mark.parametrize("mode", [Mode.OFF, Mode.DRY_RUN, Mode.LIVE, Mode.EXPERIMENT])
def test_limits_hold_in_simulated_half_days(mode: Mode) -> None:
    config = PolicyConfig(
        mode=mode,
        retry_gap_s=60.0,
        max_pulses_per_day=6,
        quiet_start_hour=QUIET[0],
        quiet_end_hour=QUIET[1],
    )
    results = [simulate(seed, config) for seed in SEEDS]
    triggers = sum(t for t, _ in results)
    pulses = sum(p for _, p in results)
    if mode is Mode.OFF:
        assert triggers == 0
    else:
        assert triggers > 10, f"a simulação quase não exercitou disparos ({triggers})"
    if mode in (Mode.LIVE, Mode.EXPERIMENT):
        assert pulses > 0
    if mode is Mode.DRY_RUN:
        assert pulses == 0
