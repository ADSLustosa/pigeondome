"""Portas: o que a aplicação precisa do mundo externo, sem dizer como."""

from datetime import datetime
from typing import Protocol

from pigeondome.domain.models import Detection, DeviceSummary


class StorageError(Exception):
    """Falha de armazenamento (banco indisponível etc.), independente da tecnologia."""


class DetectionRepository(Protocol):
    def add(self, detection: Detection) -> bool:
        """Grava a detecção. Devolve False se já existia (idempotência)."""
        ...

    def list_between(self, device_id: str, start: datetime, end: datetime) -> list[Detection]:
        """Detecções do dispositivo em [start, end), ordenadas por tempo."""
        ...

    def list_devices(self) -> list[DeviceSummary]:
        """Um resumo por dispositivo já visto, ordenado pelo identificador."""
        ...
