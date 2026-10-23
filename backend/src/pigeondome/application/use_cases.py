"""Casos de uso: orquestram o domínio por meio das portas."""

from datetime import datetime

from pigeondome.application.ports import DetectionRepository
from pigeondome.domain.models import Detection, DeviceSummary, PresenceStats


class IngestDetection:
    def __init__(self, repository: DetectionRepository) -> None:
        self._repository = repository

    def execute(self, detection: Detection) -> bool:
        """Devolve True se a detecção era nova, False se era duplicada."""
        return self._repository.add(detection)


class GetPresenceStats:
    def __init__(self, repository: DetectionRepository) -> None:
        self._repository = repository

    def execute(self, device_id: str, start: datetime, end: datetime) -> PresenceStats:
        if end <= start:
            raise ValueError("a janela precisa ter fim posterior ao início")
        detections = self._repository.list_between(device_id, start, end)
        readings = len(detections)
        if readings == 0:
            return PresenceStats(device_id, 0, 0, 0.0, 0)
        counts = [d.pigeon_count for d in detections]
        return PresenceStats(
            device_id=device_id,
            readings=readings,
            readings_with_pigeons=sum(1 for d in detections if d.has_pigeons),
            mean_pigeons=sum(counts) / readings,
            max_pigeons=max(counts),
        )


class ListDevices:
    def __init__(self, repository: DetectionRepository) -> None:
        self._repository = repository

    def execute(self) -> list[DeviceSummary]:
        return self._repository.list_devices()
