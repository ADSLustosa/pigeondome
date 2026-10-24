"""Portas: o que a aplicação precisa do mundo externo, sem dizer como."""

from datetime import datetime, timedelta
from typing import Protocol

from pigeondome.domain.actuation import Mode
from pigeondome.domain.actuation_log import ActuatorEventRecord, DecisionRecord
from pigeondome.domain.models import Detection, DeviceSummary, SeriesPoint
from pigeondome.domain.status import ActuatorStateRecord, ControllerStatusRecord


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


class DecisionRepository(Protocol):
    def add(self, record: DecisionRecord) -> bool:
        """Grava a decisão. Devolve False se já existia (idempotência)."""
        ...

    def list_between(
        self, actuator_id: str, start: datetime, end: datetime
    ) -> list[DecisionRecord]:
        """Decisões do atuador em [start, end), ordenadas por tempo."""
        ...

    def count_triggered_between(
        self, actuator_id: str, start: datetime, end: datetime, mode: Mode
    ) -> int:
        """Quantos disparos em [start, end) contam para o orçamento do modo `mode`.

        Pulso real (veredito `pulse`) conta em qualquer modo: o atuador o recebeu de verdade.
        Disparo contrafactual (`would_pulse` do modo seco, controle do experimento) só conta
        no próprio modo: nada foi enviado, então não gasta orçamento nem intervalo do modo real.
        """
        ...

    def last_triggered_at(self, actuator_id: str, mode: Mode) -> datetime | None:
        """Instante do último disparo que conta para `mode` (mesma regra), ou None se nunca."""
        ...


class ActuatorEventRepository(Protocol):
    def add(self, record: ActuatorEventRecord) -> bool:
        """Grava o evento. Devolve False se já existia (QoS 1 pode duplicar mensagens)."""
        ...

    def list_between(
        self, actuator_id: str, start: datetime, end: datetime
    ) -> list[ActuatorEventRecord]:
        """Eventos do atuador em [start, end), ordenados por tempo."""
        ...


class ControllerFlags(Protocol):
    def kill_switch(self) -> bool:
        """True se a chave geral está ligada. Sem resposta confiável, a segura é True."""
        ...

    def set_kill_switch(self, enabled: bool, now: datetime) -> None:
        """Liga ou desliga a chave geral do controlador."""
        ...


class ActuatorStateRepository(Protocol):
    def save(self, record: ActuatorStateRecord) -> None:
        """Grava o último estado do atuador. Um registro mais antigo nunca sobrescreve um novo."""
        ...

    def get(self, actuator_id: str) -> ActuatorStateRecord | None:
        """O último estado gravado, ou None se o atuador nunca foi visto."""
        ...


class ControllerStatusRepository(Protocol):
    def save(self, record: ControllerStatusRecord) -> None:
        """Grava o estado do controlador. Um batimento mais antigo nunca sobrescreve um novo."""
        ...

    def get(self) -> ControllerStatusRecord | None:
        """O último estado gravado, ou None se o controlador nunca rodou."""
        ...
