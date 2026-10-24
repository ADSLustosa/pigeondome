"""Casos de uso do controlador: montam o contexto da política a partir da trilha gravada."""

from datetime import datetime

from pigeondome.application.ports import ControllerFlags, DecisionRepository
from pigeondome.domain.actuation import PolicyContext
from pigeondome.domain.actuation_log import local_day_bounds


class LoadPolicyContext:
    """Chave geral, pulsos de hoje e último disparo, tudo lido do banco.

    Por ser derivado do banco (e não da memória do processo), reiniciar o controlador não
    reseta o orçamento do dia nem o intervalo mínimo entre disparos.
    """

    def __init__(
        self, decisions: DecisionRepository, flags: ControllerFlags, utc_offset_hours: int
    ) -> None:
        self._decisions = decisions
        self._flags = flags
        self._utc_offset_hours = utc_offset_hours

    def execute(self, actuator_id: str, now: datetime) -> PolicyContext:
        start, end = local_day_bounds(now, self._utc_offset_hours)
        return PolicyContext(
            kill_switch=self._flags.kill_switch(),
            pulses_today=self._decisions.count_triggered_between(actuator_id, start, end),
            last_pulse_at=self._decisions.last_triggered_at(actuator_id),
        )
