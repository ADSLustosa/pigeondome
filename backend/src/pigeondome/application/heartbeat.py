"""Batimento do controlador: avisa o painel, de tempos em tempos, que o processo está vivo."""

import logging
from datetime import datetime

from pigeondome.application.ports import ControllerStatusRepository, StorageError
from pigeondome.domain.actuation import Mode
from pigeondome.domain.status import ControllerStatusRecord

log = logging.getLogger("pigeondome.controller")


class ControllerHeartbeat:
    """Grava no máximo uma vez a cada `interval_s`: o ciclo do controlador é mais rápido."""

    def __init__(
        self,
        repository: ControllerStatusRepository,
        mode: Mode,
        camera_id: str,
        actuator_id: str,
        started_at: datetime,
        interval_s: float = 5.0,
    ) -> None:
        self._repository = repository
        self._mode = mode
        self._camera_id = camera_id
        self._actuator_id = actuator_id
        self._started_at = started_at
        self._interval_s = interval_s
        self._last: datetime | None = None

    def beat(self, now: datetime) -> None:
        if self._last is not None and (now - self._last).total_seconds() < self._interval_s:
            return
        record = ControllerStatusRecord(
            self._mode, self._camera_id, self._actuator_id, self._started_at, now
        )
        try:
            self._repository.save(record)
        except StorageError:
            log.warning("batimento não gravado: banco indisponível")
            return  # o relógio do intervalo não avança: o próximo passo tenta de novo
        self._last = now
