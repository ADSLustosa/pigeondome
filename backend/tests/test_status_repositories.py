"""Estado do atuador e do controlador: contrato dos adaptadores (memória e PostgreSQL)."""

from collections.abc import Iterator
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg
import pytest
from psycopg_pool import ConnectionPool

from pigeondome.adapters.memory_status import (
    InMemoryActuatorStateRepository,
    InMemoryControllerStatusRepository,
)
from pigeondome.adapters.postgres_status import (
    PostgresActuatorStateRepository,
    PostgresControllerStatusRepository,
)
from pigeondome.application.ports import (
    ActuatorStateRepository,
    ControllerStatusRepository,
    StorageError,
)
from pigeondome.domain.actuation import Mode
from pigeondome.domain.status import ACTUATOR_STATES, ActuatorStateRecord, ControllerStatusRecord
from pigeondome.migrate import apply_migrations

T0 = datetime(2026, 10, 24, 21, 0, 0, tzinfo=UTC)
CAMERA = "cam-sim-01"
ACTUATOR = "act-sim-01"


@dataclass
class Stores:
    actuators: ActuatorStateRepository
    controller: ControllerStatusRepository


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
        return Stores(InMemoryActuatorStateRepository(), InMemoryControllerStatusRepository())
    pool: ConnectionPool[Any] = request.getfixturevalue("pg_pool")
    return Stores(PostgresActuatorStateRepository(pool), PostgresControllerStatusRepository(pool))


def actuator_state(seconds: int = 0, **changes: Any) -> ActuatorStateRecord:
    base = ActuatorStateRecord(ACTUATOR, True, "idle", False, 5, T0 + timedelta(seconds=seconds))
    return replace(base, **changes)


def controller_status(seconds: int = 0, **changes: Any) -> ControllerStatusRecord:
    base = ControllerStatusRecord(Mode.LIVE, CAMERA, ACTUATOR, T0, T0 + timedelta(seconds=seconds))
    return replace(base, **changes)


# --- estado do atuador --------------------------------------------------------------------


def test_an_unknown_actuator_has_no_state(stores: Stores) -> None:
    assert stores.actuators.get(ACTUATOR) is None


def test_actuator_state_roundtrip_preserves_nulls(stores: Stores) -> None:
    full = actuator_state(0)
    stores.actuators.save(full)
    assert stores.actuators.get(ACTUATOR) == full
    sparse = actuator_state(
        1, state="safe_off", online=False, output_on=None, budget_used_s_1h=None
    )
    stores.actuators.save(sparse)
    assert stores.actuators.get(ACTUATOR) == sparse


def test_the_latest_actuator_state_wins(stores: Stores) -> None:
    stores.actuators.save(actuator_state(0))
    latest = actuator_state(10, state="cooldown")
    stores.actuators.save(latest)
    assert stores.actuators.get(ACTUATOR) == latest


def test_an_older_actuator_state_never_overwrites_a_newer_one(stores: Stores) -> None:
    newer = actuator_state(10, state="pulsing", output_on=True)
    stores.actuators.save(newer)
    stores.actuators.save(actuator_state(5))
    assert stores.actuators.get(ACTUATOR) == newer


def test_each_actuator_keeps_its_own_state(stores: Stores) -> None:
    other = actuator_state(0, actuator_id="act-outro", state="fault")
    stores.actuators.save(other)
    assert stores.actuators.get(ACTUATOR) is None
    stores.actuators.save(actuator_state(0))
    assert stores.actuators.get("act-outro") == other


# --- estado do controlador ----------------------------------------------------------------


def test_a_controller_that_never_ran_has_no_status(stores: Stores) -> None:
    assert stores.controller.get() is None


def test_controller_status_roundtrip(stores: Stores) -> None:
    status = controller_status(0, mode=Mode.EXPERIMENT)
    stores.controller.save(status)
    assert stores.controller.get() == status


def test_the_heartbeat_advances_and_keeps_the_start_time(stores: Stores) -> None:
    stores.controller.save(controller_status(0))
    stores.controller.save(controller_status(5))
    assert stores.controller.get() == controller_status(5)


def test_an_older_heartbeat_never_overwrites_a_newer_one(stores: Stores) -> None:
    stores.controller.save(controller_status(10))
    stores.controller.save(controller_status(5))
    assert stores.controller.get() == controller_status(10)


def test_a_restarted_controller_replaces_the_previous_one(stores: Stores) -> None:
    stores.controller.save(controller_status(10))
    restarted = controller_status(20, mode=Mode.DRY_RUN, started_at=T0 + timedelta(seconds=15))
    stores.controller.save(restarted)
    assert stores.controller.get() == restarted


# --- regras do próprio banco ----------------------------------------------------------------


def test_every_state_of_the_contract_is_accepted_by_the_table(pg_pool: ConnectionPool[Any]) -> None:
    repository = PostgresActuatorStateRepository(pg_pool)
    for number, state in enumerate(sorted(ACTUATOR_STATES)):
        repository.save(actuator_state(number, state=state))
        saved = repository.get(ACTUATOR)
        assert saved is not None and saved.state == state


def test_the_tables_enforce_their_own_rules(pg_pool: ConnectionPool[Any]) -> None:
    with pytest.raises(psycopg.errors.CheckViolation), pg_pool.connection() as conn:
        conn.execute(
            "INSERT INTO actuator_state (actuator_id, online, state, received_at) "
            "VALUES ('act-sim-01', true, 'exploding', now())"
        )
    with pytest.raises(psycopg.errors.CheckViolation), pg_pool.connection() as conn:
        conn.execute(
            "INSERT INTO controller_status "
            "(id, mode, camera_id, actuator_id, started_at, heartbeat_at) "
            "VALUES (2, 'live', 'cam-sim-01', 'act-sim-01', now(), now())"
        )


# --- erros de banco viram StorageError (não precisa de banco: o pool nem foi aberto) -----------

FAILING_CALLS = {
    "actuator_save": lambda pool: PostgresActuatorStateRepository(pool).save(actuator_state()),
    "actuator_get": lambda pool: PostgresActuatorStateRepository(pool).get(ACTUATOR),
    "controller_save": lambda pool: PostgresControllerStatusRepository(pool).save(
        controller_status()
    ),
    "controller_get": lambda pool: PostgresControllerStatusRepository(pool).get(),
}


@pytest.mark.parametrize("name", list(FAILING_CALLS))
def test_database_failures_become_storage_errors(name: str) -> None:
    pool: ConnectionPool[Any] = ConnectionPool(
        "host=127.0.0.1 port=1 connect_timeout=1", open=False
    )
    with pytest.raises(StorageError):
        FAILING_CALLS[name](pool)
