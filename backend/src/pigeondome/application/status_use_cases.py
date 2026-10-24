"""Casos de uso de leitura do estado do atuador e do controlador, e da chave geral."""

from dataclasses import dataclass
from datetime import datetime

from pigeondome.application.ports import (
    ActuatorEventRepository,
    ActuatorStateRepository,
    ControllerFlags,
    ControllerStatusRepository,
    DecisionRepository,
)
from pigeondome.domain import freshness
from pigeondome.domain.actuation_log import ActuatorEventRecord, DecisionRecord
from pigeondome.domain.status import ActuatorStateRecord, ControllerStatusRecord


@dataclass(frozen=True)
class ActuatorView:
    """O último estado do atuador, com a idade e o veredito de frescor já calculados."""

    record: ActuatorStateRecord
    age_s: float
    stale: bool


@dataclass(frozen=True)
class ControllerView:
    """O controlador como o painel o enxerga: chave geral, se está vivo e o último batimento."""

    kill_switch: bool
    running: bool
    record: ControllerStatusRecord | None
    age_s: float | None


class GetActuatorStatus:
    def __init__(self, states: ActuatorStateRepository) -> None:
        self._states = states

    def execute(self, actuator_id: str, now: datetime) -> ActuatorView | None:
        """None se o atuador nunca foi visto pelo controlador."""
        record = self._states.get(actuator_id)
        if record is None:
            return None
        return ActuatorView(
            record,
            freshness.age_s(record.received_at, now),
            freshness.actuator_is_stale(record, now),
        )


class GetControllerStatus:
    def __init__(self, status: ControllerStatusRepository, flags: ControllerFlags) -> None:
        self._status = status
        self._flags = flags

    def execute(self, now: datetime) -> ControllerView:
        record = self._status.get()
        return ControllerView(
            kill_switch=self._flags.kill_switch(),
            running=freshness.controller_is_running(record, now),
            record=record,
            age_s=None if record is None else freshness.age_s(record.heartbeat_at, now),
        )


class ListDecisions:
    """As decisões mais recentes do controlador numa janela, da mais nova para a mais antiga."""

    def __init__(self, decisions: DecisionRepository) -> None:
        self._decisions = decisions

    def execute(
        self, actuator_id: str, start: datetime, end: datetime, limit: int
    ) -> tuple[list[DecisionRecord], bool]:
        """Devolve as `limit` mais recentes e se havia mais registros do que isso."""
        if limit < 1:
            raise ValueError("o limite precisa ser positivo")
        found = self._decisions.list_between(actuator_id, start, end)
        return list(reversed(found[-limit:])), len(found) > limit


class ListActuatorEvents:
    """Os eventos mais recentes do atuador numa janela, do mais novo para o mais antigo."""

    def __init__(self, events: ActuatorEventRepository) -> None:
        self._events = events

    def execute(
        self, actuator_id: str, start: datetime, end: datetime, limit: int
    ) -> tuple[list[ActuatorEventRecord], bool]:
        """Devolve os `limit` mais recentes e se havia mais registros do que isso."""
        if limit < 1:
            raise ValueError("o limite precisa ser positivo")
        found = self._events.list_between(actuator_id, start, end)
        return list(reversed(found[-limit:])), len(found) > limit


class EngageKillSwitch:
    """Liga a chave geral. Não existe o caso de uso inverso: desligar é só pelo script local."""

    def __init__(self, flags: ControllerFlags) -> None:
        self._flags = flags

    def execute(self, now: datetime) -> None:
        self._flags.set_kill_switch(True, now)
