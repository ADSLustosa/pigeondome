"""Adaptadores em memória do estado do atuador e do controlador (testes e execução sem banco)."""

import threading

from pigeondome.domain.status import ActuatorStateRecord, ControllerStatusRecord


class InMemoryActuatorStateRepository:
    def __init__(self) -> None:
        self._items: dict[str, ActuatorStateRecord] = {}
        self._lock = threading.Lock()

    def save(self, record: ActuatorStateRecord) -> None:
        with self._lock:
            current = self._items.get(record.actuator_id)
            if current is None or current.received_at <= record.received_at:
                self._items[record.actuator_id] = record

    def get(self, actuator_id: str) -> ActuatorStateRecord | None:
        with self._lock:
            return self._items.get(actuator_id)


class InMemoryControllerStatusRepository:
    def __init__(self) -> None:
        self._item: ControllerStatusRecord | None = None
        self._lock = threading.Lock()

    def save(self, record: ControllerStatusRecord) -> None:
        with self._lock:
            if self._item is None or self._item.heartbeat_at <= record.heartbeat_at:
                self._item = record

    def get(self) -> ControllerStatusRecord | None:
        with self._lock:
            return self._item
