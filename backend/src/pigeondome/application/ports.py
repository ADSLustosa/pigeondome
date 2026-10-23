"""Portas: o que a aplicação precisa do mundo externo, sem dizer como."""

from datetime import datetime, timedelta
from typing import Protocol

from pigeondome.domain.models import Detection, DeviceSummary, SeriesPoint


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

    def series(
        self, device_id: str, start: datetime, end: datetime, bucket: timedelta
    ) -> list[SeriesPoint]:
        """Leituras agregadas em intervalos de `bucket`, alinhados ao início da janela.

        Só aparecem intervalos COM leituras: a ausência de um ponto significa ausência de
        medição (câmera offline), e não zero pombos.
        """
        ...
