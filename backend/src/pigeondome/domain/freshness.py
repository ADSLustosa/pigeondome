"""Frescor dos dados de estado: quando o painel deve desconfiar do que o banco guarda.

Puro: sem banco e sem relógio. A hora vem de fora e é comparada com a hora da RECEPÇÃO
gravada pelo controlador.
"""

from datetime import datetime

from pigeondome.domain.actuation import PolicyConfig
from pigeondome.domain.status import ActuatorStateRecord, ControllerStatusRecord

# O atuador publica o estado a cada 10 s. O limite de "velho" é o mesmo da política do
# controlador (max_actuator_report_age_s): painel e controlador concordam sobre o que é velho.
ACTUATOR_STALE_AFTER_S = PolicyConfig().max_actuator_report_age_s

# O controlador bate o coração a cada 5 s e o ciclo dele é de 1 s: 15 s tolera dois
# batimentos perdidos antes de o painel dizer que ele parou.
CONTROLLER_STALE_AFTER_S = 15.0


def age_s(moment: datetime, now: datetime) -> float:
    """Segundos desde `moment`. Nunca negativo: diferença de relógios não vira idade futura."""
    return max(0.0, (now - moment).total_seconds())


def actuator_is_stale(record: ActuatorStateRecord, now: datetime) -> bool:
    """Dado velho: o atuador consta como online, mas não manda mensagem há tempo demais.

    Um atuador OFFLINE não é velho: o aviso do broker é um fato, e a idade só diz há quanto
    tempo ele caiu.
    """
    return record.online and age_s(record.received_at, now) > ACTUATOR_STALE_AFTER_S


def controller_is_running(record: ControllerStatusRecord | None, now: datetime) -> bool:
    """O controlador está vivo se o último batimento é recente. Sem registro, nunca rodou."""
    return record is not None and age_s(record.heartbeat_at, now) <= CONTROLLER_STALE_AFTER_S
