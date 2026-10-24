"""Adaptadores PostgreSQL do último estado do atuador e do controlador."""

from typing import Any, LiteralString

import psycopg
from psycopg_pool import ConnectionPool

from pigeondome.application.ports import StorageError
from pigeondome.domain.actuation import Mode
from pigeondome.domain.status import ActuatorStateRecord, ControllerStatusRecord

# A guarda WHERE impede que um registro mais antigo sobrescreva um mais novo.
_SAVE_ACTUATOR: LiteralString = (
    "INSERT INTO actuator_state "
    "(actuator_id, online, state, output_on, budget_used_s_1h, received_at) "
    "VALUES (%s, %s, %s, %s, %s, %s) "
    "ON CONFLICT (actuator_id) DO UPDATE SET online = EXCLUDED.online, "
    "state = EXCLUDED.state, output_on = EXCLUDED.output_on, "
    "budget_used_s_1h = EXCLUDED.budget_used_s_1h, received_at = EXCLUDED.received_at "
    "WHERE actuator_state.received_at <= EXCLUDED.received_at"
)
_GET_ACTUATOR: LiteralString = (
    "SELECT actuator_id, online, state, output_on, budget_used_s_1h, received_at "
    "FROM actuator_state WHERE actuator_id = %s"
)
_SAVE_CONTROLLER: LiteralString = (
    "INSERT INTO controller_status "
    "(id, mode, camera_id, actuator_id, started_at, heartbeat_at) "
    "VALUES (1, %s, %s, %s, %s, %s) "
    "ON CONFLICT (id) DO UPDATE SET mode = EXCLUDED.mode, camera_id = EXCLUDED.camera_id, "
    "actuator_id = EXCLUDED.actuator_id, started_at = EXCLUDED.started_at, "
    "heartbeat_at = EXCLUDED.heartbeat_at "
    "WHERE controller_status.heartbeat_at <= EXCLUDED.heartbeat_at"
)
_GET_CONTROLLER: LiteralString = (
    "SELECT mode, camera_id, actuator_id, started_at, heartbeat_at "
    "FROM controller_status WHERE id = 1"
)


class PostgresActuatorStateRepository:
    def __init__(self, pool: ConnectionPool[Any]) -> None:
        self._pool = pool

    def save(self, record: ActuatorStateRecord) -> None:
        params = (
            record.actuator_id,
            record.online,
            record.state,
            record.output_on,
            record.budget_used_s_1h,
            record.received_at,
        )
        try:
            with self._pool.connection() as conn:
                conn.execute(_SAVE_ACTUATOR, params)
        except psycopg.Error as exc:
            raise StorageError("falha ao gravar o estado do atuador") from exc

    def get(self, actuator_id: str) -> ActuatorStateRecord | None:
        try:
            with self._pool.connection() as conn:
                row = conn.execute(_GET_ACTUATOR, (actuator_id,)).fetchone()
        except psycopg.Error as exc:
            raise StorageError("falha ao consultar o estado do atuador") from exc
        if row is None:
            return None
        return ActuatorStateRecord(
            actuator_id=row[0],
            online=row[1],
            state=row[2],
            output_on=row[3],
            budget_used_s_1h=row[4],
            received_at=row[5],
        )


class PostgresControllerStatusRepository:
    def __init__(self, pool: ConnectionPool[Any]) -> None:
        self._pool = pool

    def save(self, record: ControllerStatusRecord) -> None:
        params = (
            record.mode.value,
            record.camera_id,
            record.actuator_id,
            record.started_at,
            record.heartbeat_at,
        )
        try:
            with self._pool.connection() as conn:
                conn.execute(_SAVE_CONTROLLER, params)
        except psycopg.Error as exc:
            raise StorageError("falha ao gravar o estado do controlador") from exc

    def get(self) -> ControllerStatusRecord | None:
        try:
            with self._pool.connection() as conn:
                row = conn.execute(_GET_CONTROLLER).fetchone()
        except psycopg.Error as exc:
            raise StorageError("falha ao consultar o estado do controlador") from exc
        if row is None:
            return None
        return ControllerStatusRecord(
            mode=Mode(row[0]),
            camera_id=row[1],
            actuator_id=row[2],
            started_at=row[3],
            heartbeat_at=row[4],
        )
