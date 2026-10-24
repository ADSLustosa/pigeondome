"""Trilha do controlador: contrato dos adaptadores (memória e PostgreSQL) e erros de banco."""

from collections.abc import Iterator
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from psycopg_pool import ConnectionPool

from pigeondome.adapters.memory_actuation import (
    InMemoryActuatorEventRepository,
    InMemoryControllerFlags,
    InMemoryDecisionRepository,
)
from pigeondome.adapters.postgres_actuation import (
    PostgresActuatorEventRepository,
    PostgresControllerFlags,
    PostgresDecisionRepository,
)
from pigeondome.application.ports import (
    ActuatorEventRepository,
    ControllerFlags,
    DecisionRepository,
    StorageError,
)
from pigeondome.domain.actuation import Arm, Mode, Reason, Verdict
from pigeondome.domain.actuation_log import ActuatorEventRecord, DecisionRecord
from pigeondome.migrate import apply_migrations

T0 = datetime(2026, 10, 24, 15, 0, 0, tzinfo=UTC)
HOUR = timedelta(hours=1)
CAMERA = "cam-sim-01"
ACTUATOR = "act-sim-01"
UUID = "3f2b8c1e-7a4d-4e5b-9c6a-1d2e3f4a5b6c"


@dataclass
class Stores:
    decisions: DecisionRepository
    events: ActuatorEventRepository
    flags: ControllerFlags


@pytest.fixture
def pg_pool(pg_conninfo: str) -> Iterator[ConnectionPool[Any]]:
    apply_migrations(pg_conninfo)
    pool: ConnectionPool[Any] = ConnectionPool(pg_conninfo, min_size=1, max_size=2, open=True)
    try:
        yield pool
    finally:
        pool.close()


@pytest.fixture(params=["memory", "postgres"])
def stores(request: pytest.FixtureRequest) -> Stores:
    """Cada teste que usa esta fixture roda contra os DOIS adaptadores."""
    if request.param == "memory":
        return Stores(
            InMemoryDecisionRepository(),
            InMemoryActuatorEventRepository(),
            InMemoryControllerFlags(),
        )
    pool: ConnectionPool[Any] = request.getfixturevalue("pg_pool")
    return Stores(
        PostgresDecisionRepository(pool),
        PostgresActuatorEventRepository(pool),
        PostgresControllerFlags(pool),
    )


def decision(
    seconds: int = 0, *, triggered: bool = True, actuator: str = ACTUATOR, **changes: Any
) -> DecisionRecord:
    base = DecisionRecord(
        decided_at=T0 + timedelta(seconds=seconds),
        camera_id=CAMERA,
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
    return replace(base, **changes)


def event(
    seconds: int = 0, *, name: str = "pulse_started", actuator: str = ACTUATOR, **changes: Any
) -> ActuatorEventRecord:
    base = ActuatorEventRecord(T0 + timedelta(seconds=seconds), actuator, name, UUID, None)
    return replace(base, **changes)


# --- decisões ---------------------------------------------------------------------------


def test_decision_add_is_idempotent(stores: Stores) -> None:
    assert stores.decisions.add(decision(0)) is True
    assert stores.decisions.add(decision(0)) is False
    assert len(stores.decisions.list_between(ACTUATOR, T0, T0 + HOUR)) == 1


def test_decision_roundtrip_preserves_every_value(stores: Stores) -> None:
    treated = decision(1, mode=Mode.EXPERIMENT, arm=Arm.TREATMENT, detail="x")
    control = decision(
        2,
        mode=Mode.EXPERIMENT,
        arm=Arm.CONTROL,
        verdict=Verdict.SKIP,
        reason=Reason.EXPERIMENT_CONTROL,
        duration_s=None,
        command_id=None,
        mean_confidence=0.87,
    )
    stores.decisions.add(treated)
    stores.decisions.add(control)
    assert stores.decisions.list_between(ACTUATOR, T0, T0 + HOUR) == [treated, control]


def test_decisions_are_ordered_inside_a_half_open_window(stores: Stores) -> None:
    for seconds in (30, 10, 20, 60):  # 60 s é exatamente o fim da janela: fica de fora
        stores.decisions.add(decision(seconds))
    found = stores.decisions.list_between(ACTUATOR, T0, T0 + timedelta(seconds=60))
    assert [d.decided_at for d in found] == [T0 + timedelta(seconds=s) for s in (10, 20, 30)]


def test_other_actuators_are_ignored(stores: Stores) -> None:
    stores.decisions.add(decision(0, actuator="act-outro"))
    assert stores.decisions.list_between(ACTUATOR, T0, T0 + HOUR) == []
    assert stores.decisions.count_triggered_between(ACTUATOR, T0, T0 + HOUR, Mode.LIVE) == 0
    assert stores.decisions.last_triggered_at(ACTUATOR, Mode.LIVE) is None


def test_count_triggered_ignores_skips_and_respects_the_window(stores: Stores) -> None:
    stores.decisions.add(decision(0))
    stores.decisions.add(decision(10, triggered=False))
    stores.decisions.add(decision(20))
    stores.decisions.add(decision(60))  # fim da janela: fora
    window_end = T0 + timedelta(seconds=60)
    assert stores.decisions.count_triggered_between(ACTUATOR, T0, window_end, Mode.LIVE) == 2


def test_last_triggered_at_ignores_skips(stores: Stores) -> None:
    assert stores.decisions.last_triggered_at(ACTUATOR, Mode.LIVE) is None
    stores.decisions.add(decision(10))
    stores.decisions.add(decision(50))
    stores.decisions.add(decision(90, triggered=False))
    assert stores.decisions.last_triggered_at(ACTUATOR, Mode.LIVE) == T0 + timedelta(seconds=50)


# --- o modo entra na conta: contrafactuais só valem no próprio modo ----------------------------


def triggers(stores: Stores, mode: Mode) -> tuple[int, datetime | None]:
    """Disparos do dia e o último, do ponto de vista de `mode`."""
    count = stores.decisions.count_triggered_between(ACTUATOR, T0, T0 + HOUR, mode)
    return count, stores.decisions.last_triggered_at(ACTUATOR, mode)


def test_dry_run_would_pulse_does_not_count_for_live(stores: Stores) -> None:
    rehearsal = decision(
        30,
        mode=Mode.DRY_RUN,
        verdict=Verdict.WOULD_PULSE,
        reason=Reason.DRY_RUN,
        command_id=None,
    )
    stores.decisions.add(rehearsal)
    assert triggers(stores, Mode.LIVE) == (0, None)
    assert triggers(stores, Mode.DRY_RUN) == (1, T0 + timedelta(seconds=30))
    stores.decisions.add(decision(0))  # pulso real, mais antigo que o ensaio
    assert triggers(stores, Mode.LIVE) == (1, T0)
    assert triggers(stores, Mode.DRY_RUN) == (2, T0 + timedelta(seconds=30))


def test_experiment_control_does_not_count_for_live_but_the_treated_pulse_does(
    stores: Stores,
) -> None:
    treated = decision(0, mode=Mode.EXPERIMENT, arm=Arm.TREATMENT)
    control = decision(
        30,
        mode=Mode.EXPERIMENT,
        arm=Arm.CONTROL,
        verdict=Verdict.SKIP,
        reason=Reason.EXPERIMENT_CONTROL,
        duration_s=None,
        command_id=None,
    )
    stores.decisions.add(treated)
    stores.decisions.add(control)
    assert triggers(stores, Mode.LIVE) == (1, T0)
    assert triggers(stores, Mode.EXPERIMENT) == (2, T0 + timedelta(seconds=30))


def test_real_pulses_count_in_every_mode(stores: Stores) -> None:
    stores.decisions.add(decision(0))
    for mode in Mode:
        assert triggers(stores, mode) == (1, T0)


# --- eventos do atuador -------------------------------------------------------------------


def test_event_add_is_idempotent(stores: Stores) -> None:
    assert stores.events.add(event(0)) is True
    assert stores.events.add(event(0)) is False
    assert len(stores.events.list_between(ACTUATOR, T0, T0 + HOUR)) == 1


def test_event_roundtrip_preserves_nulls_and_reasons(stores: Stores) -> None:
    started = event(1)
    rejected = event(5, name="command_rejected", command_id=None, reason_code="cooldown")
    stores.events.add(started)
    stores.events.add(rejected)
    assert stores.events.list_between(ACTUATOR, T0, T0 + HOUR) == [started, rejected]


def test_events_are_ordered_by_time_then_name_inside_a_half_open_window(stores: Stores) -> None:
    stores.events.add(event(5, name="pulse_started"))
    stores.events.add(event(5, name="command_accepted"))
    stores.events.add(event(2, name="pulse_finished"))
    stores.events.add(event(10, name="pulse_started"))  # fim da janela: fora
    found = stores.events.list_between(ACTUATOR, T0, T0 + timedelta(seconds=10))
    assert [e.event for e in found] == ["pulse_finished", "command_accepted", "pulse_started"]


def test_events_of_other_actuators_are_ignored(stores: Stores) -> None:
    stores.events.add(event(0, actuator="act-outro"))
    assert stores.events.list_between(ACTUATOR, T0, T0 + HOUR) == []


# --- chave geral --------------------------------------------------------------------------


def test_kill_switch_starts_off_and_can_be_flipped(stores: Stores) -> None:
    assert stores.flags.kill_switch() is False
    stores.flags.set_kill_switch(True, T0)
    assert stores.flags.kill_switch() is True
    stores.flags.set_kill_switch(False, T0 + timedelta(seconds=1))
    assert stores.flags.kill_switch() is False


def test_a_missing_flags_row_means_the_kill_switch_is_on(pg_pool: ConnectionPool[Any]) -> None:
    with pg_pool.connection() as conn:
        conn.execute("DELETE FROM controller_flags")
    assert PostgresControllerFlags(pg_pool).kill_switch() is True


# --- erros de banco viram StorageError (não precisa de banco: o pool nem foi aberto) -----------

FAILING_CALLS = {
    "decision_add": lambda pool: PostgresDecisionRepository(pool).add(decision(0)),
    "decision_list": lambda pool: PostgresDecisionRepository(pool).list_between(
        ACTUATOR, T0, T0 + HOUR
    ),
    "decision_count": lambda pool: PostgresDecisionRepository(pool).count_triggered_between(
        ACTUATOR, T0, T0 + HOUR, Mode.LIVE
    ),
    "decision_last": lambda pool: PostgresDecisionRepository(pool).last_triggered_at(
        ACTUATOR, Mode.LIVE
    ),
    "event_add": lambda pool: PostgresActuatorEventRepository(pool).add(event(0)),
    "event_list": lambda pool: PostgresActuatorEventRepository(pool).list_between(
        ACTUATOR, T0, T0 + HOUR
    ),
    "flags_read": lambda pool: PostgresControllerFlags(pool).kill_switch(),
    "flags_write": lambda pool: PostgresControllerFlags(pool).set_kill_switch(True, T0),
}


@pytest.mark.parametrize("name", list(FAILING_CALLS))
def test_database_failures_become_storage_errors(name: str) -> None:
    pool: ConnectionPool[Any] = ConnectionPool(
        "host=127.0.0.1 port=1 connect_timeout=1", open=False
    )
    with pytest.raises(StorageError):
        FAILING_CALLS[name](pool)
