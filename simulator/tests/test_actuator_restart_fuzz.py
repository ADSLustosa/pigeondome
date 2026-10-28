"""Teste aleatório do atuador COM reinícios: o orçamento tem de atravessá-los.

Mesmo método do `test_actuator_fuzz`, mais três coisas sorteadas: queda de energia no meio de um
pulso (o hardware desliga a saída, o software perde a RAM), memória ilegível ao religar e gravação
que falha. A linha do tempo é reconstruída ao longo de TODOS os boots, então um reinício que
esquecesse o orçamento estouraria a janela e o teste falharia.
"""

import random
from datetime import timedelta

import pytest

from pigeondome_sim.actuator_budget import (
    BudgetCorruptError,
    BudgetStoreError,
    InMemoryBudgetStore,
)
from pigeondome_sim.actuator_core import (
    ActuatorCore,
    Event,
    EventType,
    Fault,
    Instant,
    Limits,
    Reason,
    State,
)

from .test_actuator_fuzz import (
    BASE,
    DEFAULT_LIMITS,
    EPS,
    GAP_WEIGHTS,
    GAPS,
    MONO0,
    SEEDS,
    STEPS,
    TIGHT_LIMITS,
    apply_operation,
    check_step,
    check_timeline,
)

DOWNTIMES = [0.5, 5.0, 40.0, 400.0, 4000.0]


class Totals:
    def __init__(self) -> None:
        self.pulses = 0
        self.blocked = 0
        self.restarts = 0
        self.mid_pulse_crashes = 0
        self.unreadable = 0


def run_session(seed: int, limits: Limits, totals: Totals, *, forgetful: bool = False) -> None:
    """Uma sessão com reinícios. `forgetful` quebra de propósito: o reinício esquece o orçamento."""
    rng = random.Random(seed)
    store = InMemoryBudgetStore()
    t = 0.0  # segundos desde BASE: o relógio de parede, que atravessa os reinícios
    boot_t, epoch = 0.0, MONO0  # o relógio monotônico recomeça a cada boot, de outro ponto

    def instant(moment: float) -> Instant:
        return Instant(epoch + (moment - boot_t), BASE + timedelta(seconds=moment))

    core = ActuatorCore(limits, store)
    core.restore_budget(instant(t))
    log: list[Event] = list(core.connection_restored(instant(t)))
    recent: list[str] = []
    for step in range(STEPS):
        t += rng.choices(GAPS, weights=GAP_WEIGHTS)[0]
        now = instant(t)
        where = f"seed={seed} passo={step}"
        roll = rng.random()
        if roll < 0.03:
            log.extend(core.tick(now))
            if core.output_on:  # a queda de energia desliga a saída; o software não fecha nada
                log.append(Event(EventType.PULSE_ABORTED, None, now.wall, Reason.DISCONNECTED))
                totals.mid_pulse_crashes += 1
            t += rng.choice(DOWNTIMES)
            boot_t, epoch = t, rng.uniform(0.0, 5000.0)
            unreadable = rng.random() < 0.2
            if unreadable:
                store.fail_load = BudgetCorruptError("arquivo corrompido")
            core = ActuatorCore(limits, None if forgetful else store)
            now = instant(t)
            core.restore_budget(now)
            store.fail_load = None
            events = core.connection_restored(now)
            log.extend(events)
            totals.restarts += 1
            if unreadable and not forgetful:
                totals.unreadable += 1
                assert core.state is State.FAULT, f"{where}: memória ilegível sem falha"
                assert core.snapshot(now).fault is Fault.SELF_TEST, where
            check_step(core, now, events, f"{where} (reinício)", limits)
            continue
        if roll < 0.05:
            store.fail_save = None if store.fail_save else BudgetStoreError("disco cheio")
        events = apply_operation(core, rng, now, step + 1, recent)
        log.extend(events)
        check_step(core, now, events, where, limits)
        if core.output_on and not forgetful:  # gravar antes de ligar
            covered = any(
                r.start <= now.wall + timedelta(seconds=EPS)
                and r.end >= now.wall - timedelta(seconds=EPS)
                for r in store.load()
            )
            assert covered, f"{where}: saída ligada sem o pulso gravado"
    totals.pulses += check_timeline(log, seed, limits)
    totals.blocked += sum(
        1
        for event in log
        if event.type is EventType.COMMAND_REJECTED and event.reason is Reason.BUDGET_EXHAUSTED
    )


@pytest.mark.parametrize(
    ("limits", "must_hit_the_budget"),
    [
        pytest.param(DEFAULT_LIMITS, False, id="limites_padrao"),
        pytest.param(TIGHT_LIMITS, True, id="orcamento_apertado"),
    ],
)
def test_the_budget_survives_random_restarts(limits: Limits, must_hit_the_budget: bool) -> None:
    totals = Totals()
    for seed in SEEDS:
        run_session(seed, limits, totals)
    assert totals.pulses > 40, f"o fuzz quase não exercitou pulsos ({totals.pulses})"
    assert totals.restarts > 100, "poucos reinícios sorteados"
    assert totals.mid_pulse_crashes > 0, "nenhuma queda no meio de um pulso"
    assert totals.unreadable > 0, "nenhuma memória ilegível sorteada"
    if must_hit_the_budget:
        assert totals.blocked > 0, "o perfil apertado deveria esgotar o orçamento"


def test_the_harness_catches_a_restart_that_forgets_the_budget() -> None:
    """Prova de que o teste acima tem força: um reinício sem memória esquece pausa e orçamento."""
    with pytest.raises(AssertionError):
        for seed in SEEDS:
            run_session(seed, TIGHT_LIMITS, Totals(), forgetful=True)
