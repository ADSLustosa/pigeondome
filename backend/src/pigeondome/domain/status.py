"""Último estado conhecido do atuador e do controlador: o que o painel mostra.

Puro: sem banco e sem relógio. Cada registro guarda a hora da RECEPÇÃO (pelo relógio do
controlador), e a API compara essa hora com o presente para decidir se o dado está velho.
"""

from dataclasses import dataclass
from datetime import datetime

from pigeondome.domain.actuation import Mode
from pigeondome.domain.actuation_log import InvalidRecordError
from pigeondome.domain.models import DEVICE_ID_PATTERN

# Estados do contrato actuator-state.v1 (o CHECK da migração 0003 repete esta lista).
ACTUATOR_STATES = frozenset({"safe_off", "idle", "pulsing", "cooldown", "maintenance", "fault"})
MAX_BUDGET_S = 3600  # uma hora inteira com a saída ligada: o teto físico de budget_used_s_1h


def _check_moment(name: str, moment: datetime) -> None:
    if moment.tzinfo is None:
        raise InvalidRecordError(f"{name} precisa ter fuso horário")


def _check_device_id(name: str, value: str) -> None:
    if not DEVICE_ID_PATTERN.fullmatch(value):
        raise InvalidRecordError(f"{name} inválido: {value!r}")


@dataclass(frozen=True)
class ActuatorStateRecord:
    """O último estado do atuador, como o controlador o recebeu."""

    actuator_id: str
    online: bool
    state: str
    output_on: bool | None
    budget_used_s_1h: int | None
    received_at: datetime

    def __post_init__(self) -> None:
        _check_moment("received_at", self.received_at)
        _check_device_id("actuator_id", self.actuator_id)
        if self.state not in ACTUATOR_STATES:
            raise InvalidRecordError(f"estado desconhecido: {self.state!r}")
        if self.budget_used_s_1h is not None and not 0 <= self.budget_used_s_1h <= MAX_BUDGET_S:
            raise InvalidRecordError(f"budget_used_s_1h fora de 0..{MAX_BUDGET_S}")


@dataclass(frozen=True)
class ControllerStatusRecord:
    """O controlador em execução: em que modo está e quando bateu o coração pela última vez."""

    mode: Mode
    camera_id: str
    actuator_id: str
    started_at: datetime
    heartbeat_at: datetime

    def __post_init__(self) -> None:
        _check_moment("started_at", self.started_at)
        _check_moment("heartbeat_at", self.heartbeat_at)
        _check_device_id("camera_id", self.camera_id)
        _check_device_id("actuator_id", self.actuator_id)
