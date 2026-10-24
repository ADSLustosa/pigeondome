"""Adaptadores em memória da trilha do controlador (testes e execução sem banco)."""

import threading
from datetime import datetime

from pigeondome.domain.actuation_log import ActuatorEventRecord, DecisionRecord


class InMemoryDecisionRepository:
    def __init__(self) -> None:
        self._items: dict[tuple[str, str, datetime], DecisionRecord] = {}
        self._lock = threading.Lock()

    def add(self, record: DecisionRecord) -> bool:
        key = (record.actuator_id, record.camera_id, record.decided_at)
        with self._lock:
            if key in self._items:
                return False
            self._items[key] = record
            return True

    def _of(self, actuator_id: str) -> list[DecisionRecord]:
        with self._lock:
            return [r for r in self._items.values() if r.actuator_id == actuator_id]

    def list_between(
        self, actuator_id: str, start: datetime, end: datetime
    ) -> list[DecisionRecord]:
        found = [r for r in self._of(actuator_id) if start <= r.decided_at < end]
        return sorted(found, key=lambda r: (r.decided_at, r.camera_id))

    def count_triggered_between(self, actuator_id: str, start: datetime, end: datetime) -> int:
        return sum(1 for r in self.list_between(actuator_id, start, end) if r.triggered)

    def last_triggered_at(self, actuator_id: str) -> datetime | None:
        times = [r.decided_at for r in self._of(actuator_id) if r.triggered]
        return max(times) if times else None


class InMemoryActuatorEventRepository:
    def __init__(self) -> None:
        self._items: dict[tuple[str, datetime, str], ActuatorEventRecord] = {}
        self._lock = threading.Lock()

    def add(self, record: ActuatorEventRecord) -> bool:
        key = (record.actuator_id, record.occurred_at, record.event)
        with self._lock:
            if key in self._items:
                return False
            self._items[key] = record
            return True

    def list_between(
        self, actuator_id: str, start: datetime, end: datetime
    ) -> list[ActuatorEventRecord]:
        with self._lock:
            items = list(self._items.values())
        found = [r for r in items if r.actuator_id == actuator_id and start <= r.occurred_at < end]
        return sorted(found, key=lambda r: (r.occurred_at, r.event))


class InMemoryControllerFlags:
    def __init__(self, kill_switch: bool = False) -> None:
        self._kill_switch = kill_switch
        self._lock = threading.Lock()

    def kill_switch(self) -> bool:
        with self._lock:
            return self._kill_switch

    def set_kill_switch(self, enabled: bool, now: datetime) -> None:
        with self._lock:
            self._kill_switch = enabled
