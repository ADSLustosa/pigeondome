"""Adaptadores PostgreSQL da trilha do controlador (decisões, eventos e chave geral)."""

from datetime import datetime
from typing import Any, LiteralString

import psycopg
from psycopg_pool import ConnectionPool

from pigeondome.application.ports import StorageError
from pigeondome.domain.actuation import Arm, Mode, Reason, Verdict
from pigeondome.domain.actuation_log import ActuatorEventRecord, DecisionRecord

_INSERT_DECISION: LiteralString = (
    "INSERT INTO actuation_decisions (decided_at, camera_id, actuator_id, mode, verdict, reason, "
    "detail, arm, duration_s, command_id, readings, detections, mean_confidence, triggered) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
    "ON CONFLICT (actuator_id, camera_id, decided_at) DO NOTHING"
)
_SELECT_DECISIONS: LiteralString = (
    "SELECT decided_at, camera_id, actuator_id, mode, verdict, reason, detail, arm, duration_s, "
    "command_id, readings, detections, mean_confidence, triggered FROM actuation_decisions "
    "WHERE actuator_id = %s AND decided_at >= %s AND decided_at < %s "
    "ORDER BY decided_at, camera_id"
)
# Um disparo conta para o modo atual se foi um pulso real (sempre) ou se é do próprio modo
# (contrafactuais: would_pulse do modo seco e controles do experimento). É a mesma regra de
# _counts_for em memory_actuation.py; o teste de contrato roda os dois adaptadores.
_COUNT_TRIGGERED: LiteralString = (
    "SELECT count(*) FROM actuation_decisions "
    "WHERE actuator_id = %s AND triggered AND (verdict = 'pulse' OR mode = %s) "
    "AND decided_at >= %s AND decided_at < %s"
)
_LAST_TRIGGERED: LiteralString = (
    "SELECT max(decided_at) FROM actuation_decisions "
    "WHERE actuator_id = %s AND triggered AND (verdict = 'pulse' OR mode = %s)"
)
_INSERT_EVENT: LiteralString = (
    "INSERT INTO actuator_events (occurred_at, actuator_id, event, command_id, reason_code) "
    "VALUES (%s, %s, %s, %s, %s) ON CONFLICT (actuator_id, occurred_at, event) DO NOTHING"
)
_SELECT_EVENTS: LiteralString = (
    "SELECT occurred_at, actuator_id, event, command_id, reason_code FROM actuator_events "
    "WHERE actuator_id = %s AND occurred_at >= %s AND occurred_at < %s "
    "ORDER BY occurred_at, event"
)
_GET_KILL_SWITCH: LiteralString = "SELECT kill_switch FROM controller_flags WHERE id = 1"
_SET_KILL_SWITCH: LiteralString = (
    "UPDATE controller_flags SET kill_switch = %s, updated_at = %s WHERE id = 1"
)


def _decision_from_row(row: tuple[Any, ...]) -> DecisionRecord:
    return DecisionRecord(
        decided_at=row[0],
        camera_id=row[1],
        actuator_id=row[2],
        mode=Mode(row[3]),
        verdict=Verdict(row[4]),
        reason=Reason(row[5]),
        detail=row[6],
        arm=Arm(row[7]) if row[7] is not None else None,
        duration_s=row[8],
        command_id=str(row[9]) if row[9] is not None else None,
        readings=row[10],
        detections=row[11],
        mean_confidence=row[12],
        triggered=row[13],
    )


class PostgresDecisionRepository:
    def __init__(self, pool: ConnectionPool[Any]) -> None:
        self._pool = pool

    def add(self, record: DecisionRecord) -> bool:
        params = (
            record.decided_at,
            record.camera_id,
            record.actuator_id,
            record.mode.value,
            record.verdict.value,
            record.reason.value,
            record.detail,
            record.arm.value if record.arm is not None else None,
            record.duration_s,
            record.command_id,
            record.readings,
            record.detections,
            record.mean_confidence,
            record.triggered,
        )
        try:
            with self._pool.connection() as conn:
                cursor = conn.execute(_INSERT_DECISION, params)
                inserted: int = cursor.rowcount
                return inserted == 1
        except psycopg.Error as exc:
            raise StorageError("falha ao gravar a decisão") from exc

    def list_between(
        self, actuator_id: str, start: datetime, end: datetime
    ) -> list[DecisionRecord]:
        try:
            with self._pool.connection() as conn:
                rows = conn.execute(_SELECT_DECISIONS, (actuator_id, start, end)).fetchall()
        except psycopg.Error as exc:
            raise StorageError("falha ao consultar as decisões") from exc
        return [_decision_from_row(row) for row in rows]

    def count_triggered_between(
        self, actuator_id: str, start: datetime, end: datetime, mode: Mode
    ) -> int:
        params = (actuator_id, mode.value, start, end)
        try:
            with self._pool.connection() as conn:
                row = conn.execute(_COUNT_TRIGGERED, params).fetchone()
        except psycopg.Error as exc:
            raise StorageError("falha ao contar os disparos") from exc
        count: int = row[0] if row else 0
        return count

    def last_triggered_at(self, actuator_id: str, mode: Mode) -> datetime | None:
        try:
            with self._pool.connection() as conn:
                row = conn.execute(_LAST_TRIGGERED, (actuator_id, mode.value)).fetchone()
        except psycopg.Error as exc:
            raise StorageError("falha ao consultar o último disparo") from exc
        last: datetime | None = row[0] if row else None
        return last


class PostgresActuatorEventRepository:
    def __init__(self, pool: ConnectionPool[Any]) -> None:
        self._pool = pool

    def add(self, record: ActuatorEventRecord) -> bool:
        params = (
            record.occurred_at,
            record.actuator_id,
            record.event,
            record.command_id,
            record.reason_code,
        )
        try:
            with self._pool.connection() as conn:
                cursor = conn.execute(_INSERT_EVENT, params)
                inserted: int = cursor.rowcount
                return inserted == 1
        except psycopg.Error as exc:
            raise StorageError("falha ao gravar o evento do atuador") from exc

    def list_between(
        self, actuator_id: str, start: datetime, end: datetime
    ) -> list[ActuatorEventRecord]:
        try:
            with self._pool.connection() as conn:
                rows = conn.execute(_SELECT_EVENTS, (actuator_id, start, end)).fetchall()
        except psycopg.Error as exc:
            raise StorageError("falha ao consultar os eventos do atuador") from exc
        return [
            ActuatorEventRecord(
                occurred_at=r[0],
                actuator_id=r[1],
                event=r[2],
                command_id=str(r[3]) if r[3] is not None else None,
                reason_code=r[4],
            )
            for r in rows
        ]


class PostgresControllerFlags:
    def __init__(self, pool: ConnectionPool[Any]) -> None:
        self._pool = pool

    def kill_switch(self) -> bool:
        try:
            with self._pool.connection() as conn:
                row = conn.execute(_GET_KILL_SWITCH).fetchone()
        except psycopg.Error as exc:
            raise StorageError("falha ao ler a chave geral") from exc
        # sem a linha, a resposta segura é "ligada": na dúvida, nada de pulsos
        return row is None or bool(row[0])

    def set_kill_switch(self, enabled: bool, now: datetime) -> None:
        try:
            with self._pool.connection() as conn:
                conn.execute(_SET_KILL_SWITCH, (enabled, now))
        except psycopg.Error as exc:
            raise StorageError("falha ao gravar a chave geral") from exc
