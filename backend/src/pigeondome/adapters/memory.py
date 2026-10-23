"""Adaptador em memória da porta DetectionRepository (testes e demonstrações)."""

import threading
from datetime import datetime

from pigeondome.domain.models import Detection, DeviceSummary


class InMemoryDetectionRepository:
    def __init__(self) -> None:
        self._items: dict[tuple[str, datetime], Detection] = {}
        # O paho entrega mensagens em outra thread: o acesso precisa ser serializado.
        self._lock = threading.Lock()

    def add(self, detection: Detection) -> bool:
        key = (detection.device_id, detection.timestamp)
        with self._lock:
            if key in self._items:
                return False
            self._items[key] = detection
            return True

    def list_between(self, device_id: str, start: datetime, end: datetime) -> list[Detection]:
        with self._lock:
            found = [
                d
                for d in self._items.values()
                if d.device_id == device_id and start <= d.timestamp < end
            ]
        return sorted(found, key=lambda d: d.timestamp)

    def list_devices(self) -> list[DeviceSummary]:
        with self._lock:
            items = list(self._items.values())
        by_device: dict[str, list[Detection]] = {}
        for detection in items:
            by_device.setdefault(detection.device_id, []).append(detection)
        return [
            DeviceSummary(device_id, len(found), max(d.timestamp for d in found))
            for device_id, found in sorted(by_device.items())
        ]
