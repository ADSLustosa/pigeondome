"""Teste aleatório (fuzz) do núcleo do atuador: invariantes de segurança em milhares de passos.

Cada sessão é reproduzível pela semente. A cada passo, o estado e os eventos produzidos são
validados contra os contratos; no fim, a linha do tempo da saída é reconstruída e conferida.

Dois perfis de limites: o padrão e um "apertado" (orçamento pequeno numa janela curta), que
força o orçamento a esgotar e a janela a deslizar, coisas que o perfil padrão quase não toca.
"""

import json
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from pigeondome_sim.actuator_core import (
    Action,
    ActuatorCore,
    Command,
    Event,
    EventType,
    Fault,
    Instant,
    Limits,
    Reason,
    State,
)
from pigeondome_sim.actuator_messages import event_message, state_message

CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"
STATE_CHECK = Draft202012Validator(
    json.loads((CONTRACTS / "actuator-state.v1.schema.json").read_text("utf-8"))
)
EVENT_CHECK = Draft202012Validator(
    json.loads((CONTRACTS / "actuator-event.v1.schema.json").read_text("utf-8"))
)
BASE = datetime(2026, 10, 23, 12, 0, 0, tzinfo=UTC)
MONO0 = 1000.0
EPS = 1e-6
SEEDS = range(25)
STEPS = 250
GAPS = [0.0, 0.2, 1.0, 3.0, 5.0, 12.0, 31.0, 90.0]
GAP_WEIGHTS = [3, 6, 5, 3, 2, 1, 1, 1]
OPERATIONS = [
    "pulse",
    "stop",
    "tick",
    "lost",
    "restored",
    "maint_on",
    "maint_off",
    "fault",
    "reset",
]
OPERATION_WEIGHTS = [40, 6, 25, 4, 12, 3, 3, 2, 8]
DEFAULT_LIMITS = Limits()
TIGHT_LIMITS = Limits(cooldown_s=8.0, budget_s=30.0, budget_window_s=300.0)


def instant(mono: float) -> Instant:
    return Instant(mono_s=mono, wall=BASE + timedelta(seconds=mono - MONO0))


def random_command(rng: random.Random, now: Instant, counter: int, recent: list[str]) -> Command:
    action = Action.STOP if rng.random() < 0.15 else Action.PULSE
    repeated = bool(recent) and rng.random() < 0.1
    command_id = rng.choice(recent) if repeated else f"00000000-0000-4000-8000-{counter:012d}"
    ttl_s = rng.choice([5, 10, 30]) if rng.random() < 0.95 else rng.choice([0, 31])
    duration = rng.choice([1, 3, 5, 10]) if rng.random() < 0.95 else rng.choice([0, 11])
    age = rng.uniform(-3.0, 8.0)  # positivo = emitido no passado
    roll = rng.random()
    if roll < 0.05:
        age = -30.0  # do futuro, além da tolerância do relógio
    elif roll < 0.10:
        age = 60.0  # vencido
    recent.append(command_id)
    del recent[:-5]
    return Command(
        command_id=command_id,
        action=action,
        issued_at=now.wall - timedelta(seconds=age),
        ttl_s=ttl_s,
        duration_s=duration if action is Action.PULSE else None,
    )


def apply_operation(
    core: ActuatorCore, rng: random.Random, now: Instant, counter: int, recent: list[str]
) -> list[Event]:
    operation = rng.choices(OPERATIONS, weights=OPERATION_WEIGHTS)[0]
    if operation in ("pulse", "stop"):
        command = random_command(rng, now, counter, recent)
        if operation == "stop":
            command = Command(command.command_id, Action.STOP, command.issued_at, command.ttl_s)
        return core.handle_command(command, now)
    if operation == "lost":
        return core.connection_lost(now)
    if operation == "restored":
        return core.connection_restored(now, self_test_ok=rng.random() > 0.1)
    if operation == "maint_on":
        return core.set_maintenance(True, now)
    if operation == "maint_off":
        return core.set_maintenance(False, now)
    if operation == "fault":
        return core.inject_fault(rng.choice(list(Fault)), now)
    if operation == "reset":
        return core.reset(now, self_test_ok=rng.random() > 0.1)
    return core.tick(now)


def check_step(
    core: ActuatorCore, now: Instant, events: list[Event], where: str, limits: Limits
) -> None:
    snapshot = core.snapshot(now)
    if snapshot.output_on:
        assert snapshot.online, f"{where}: saída ligada offline"
        assert snapshot.state is State.PULSING, f"{where}: saída fora de pulsing"
    if not snapshot.online:
        assert snapshot.state is State.SAFE_OFF, f"{where}: offline fora de safe_off"
        assert not snapshot.output_on and snapshot.fault is None, f"{where}: offline com saída"
    assert (snapshot.state is State.FAULT) == (snapshot.fault is not None), where
    assert core.budget_used_s(now) <= limits.budget_s + EPS, f"{where}: orçamento estourado"
    state_errors = [
        error.message
        for error in STATE_CHECK.iter_errors(state_message("act-sim-01", snapshot, now.wall))
    ]
    assert not state_errors, f"{where}: estado fora do contrato: {state_errors}"
    for event in events:
        has_reason = event.type in (EventType.COMMAND_REJECTED, EventType.PULSE_ABORTED)
        assert (event.reason is not None) == has_reason, f"{where}: motivo do evento {event}"
        message = event_message("act-sim-01", event)
        event_errors = [error.message for error in EVENT_CHECK.iter_errors(message)]
        assert not event_errors, f"{where}: evento fora do contrato: {event_errors}"


def check_timeline(log: list[Event], seed: int, limits: Limits) -> int:
    """Reconstrói quando a saída esteve ligada e confere os limites físicos."""
    intervals: list[tuple[float, float]] = []
    start: float | None = None
    for event in log:
        moment = (event.at - BASE).total_seconds()
        if event.type is EventType.PULSE_STARTED:
            assert start is None, f"seed={seed}: pulso iniciado com outro ativo"
            start = moment
        elif event.type in (EventType.PULSE_FINISHED, EventType.PULSE_ABORTED):
            assert start is not None, f"seed={seed}: pulso encerrado sem ter começado"
            intervals.append((start, moment))
            start = None
    for begin, end in intervals:
        assert end - begin <= limits.max_pulse_s + EPS, f"seed={seed}: pulso longo demais"
    for previous, current in zip(intervals, intervals[1:], strict=False):
        pause = current[0] - previous[1]
        assert pause >= limits.cooldown_s - EPS, f"seed={seed}: pausa de {pause:.1f} s"
    for _, end in intervals:
        window_start = end - limits.budget_window_s
        used = sum(max(0.0, min(e, end) - max(s, window_start)) for s, e in intervals)
        assert used <= limits.budget_s + EPS, f"seed={seed}: {used:.1f} s na janela"
    return len(intervals)


def run_session(seed: int, limits: Limits) -> tuple[int, int]:
    """Roda uma sessão aleatória e devolve (pulsos, recusas por orçamento)."""
    rng = random.Random(seed)
    core = ActuatorCore(limits)
    mono = MONO0
    log = list(core.connection_restored(instant(mono)))
    recent: list[str] = []
    for step in range(STEPS):
        mono += rng.choices(GAPS, weights=GAP_WEIGHTS)[0]
        now = instant(mono)
        events = apply_operation(core, rng, now, step + 1, recent)
        log.extend(events)
        check_step(core, now, events, f"seed={seed} passo={step}", limits)
    pulses = check_timeline(log, seed, limits)
    blocked = sum(
        1
        for event in log
        if event.type is EventType.COMMAND_REJECTED and event.reason is Reason.BUDGET_EXHAUSTED
    )
    return pulses, blocked


@pytest.mark.parametrize(
    ("limits", "must_hit_the_budget"),
    [
        pytest.param(DEFAULT_LIMITS, False, id="limites_padrao"),
        pytest.param(TIGHT_LIMITS, True, id="orcamento_apertado"),
    ],
)
def test_safety_invariants_hold_in_random_sessions(
    limits: Limits, must_hit_the_budget: bool
) -> None:
    results = [run_session(seed, limits) for seed in SEEDS]
    pulses = sum(count for count, _ in results)
    blocked = sum(count for _, count in results)
    assert pulses > 40, f"o fuzz quase não exercitou pulsos ({pulses})"
    if must_hit_the_budget:
        assert blocked > 0, "o perfil apertado deveria esgotar o orçamento em alguma sessão"
