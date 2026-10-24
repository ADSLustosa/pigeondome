"""Registros da trilha do controlador: o que foi decidido e o que o atuador relatou.

Puro: sem banco e sem relógio. Os adaptadores de armazenamento só gravam e leem estes registros.
"""

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone

from pigeondome.domain.actuation import Arm, Decision, Mode, Reason, Verdict
from pigeondome.domain.models import DEVICE_ID_PATTERN

UUID_PATTERN = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
ACTUATOR_EVENTS = frozenset(
    {"command_accepted", "command_rejected", "pulse_started", "pulse_finished", "pulse_aborted"}
)


class InvalidRecordError(ValueError):
    """Violação de uma regra ao criar um registro da trilha."""


def _check_identity(moment: datetime, ids: dict[str, str], command_id: str | None) -> None:
    if moment.tzinfo is None:
        raise InvalidRecordError("o instante precisa ter fuso horário")
    for name, value in ids.items():
        if not DEVICE_ID_PATTERN.fullmatch(value):
            raise InvalidRecordError(f"{name} inválido: {value!r}")
    if command_id is not None and not UUID_PATTERN.fullmatch(command_id):
        raise InvalidRecordError(f"command_id inválido: {command_id!r}")


@dataclass(frozen=True)
class DecisionRecord:
    """Uma decisão da política, com o contexto necessário para auditar e analisar depois."""

    decided_at: datetime
    camera_id: str
    actuator_id: str
    mode: Mode
    verdict: Verdict
    reason: Reason
    detail: str
    arm: Arm | None
    duration_s: int | None
    command_id: str | None
    readings: int
    detections: int
    mean_confidence: float
    triggered: bool

    def __post_init__(self) -> None:
        ids = {"camera_id": self.camera_id, "actuator_id": self.actuator_id}
        _check_identity(self.decided_at, ids, self.command_id)
        if self.readings < 0 or not 0 <= self.detections <= self.readings:
            raise InvalidRecordError("contagens inconsistentes: 0 <= detections <= readings")
        if not 0.0 <= self.mean_confidence <= 1.0:
            raise InvalidRecordError("mean_confidence fora de 0..1")

    @classmethod
    def from_decision(
        cls,
        decision: Decision,
        *,
        decided_at: datetime,
        camera_id: str,
        actuator_id: str,
        mode: Mode,
        command_id: str | None = None,
    ) -> "DecisionRecord":
        return cls(
            decided_at=decided_at,
            camera_id=camera_id,
            actuator_id=actuator_id,
            mode=mode,
            verdict=decision.verdict,
            reason=decision.reason,
            detail=decision.detail,
            arm=decision.arm,
            duration_s=decision.duration_s,
            command_id=command_id,
            readings=decision.evidence.readings,
            detections=decision.evidence.detections,
            mean_confidence=decision.evidence.mean_confidence,
            triggered=decision.triggered,
        )


@dataclass(frozen=True)
class ActuatorEventRecord:
    """Um evento relatado pelo atuador (contrato actuator-event.v1), para auditoria."""

    occurred_at: datetime
    actuator_id: str
    event: str
    command_id: str | None
    reason_code: str | None

    def __post_init__(self) -> None:
        _check_identity(self.occurred_at, {"actuator_id": self.actuator_id}, self.command_id)
        if self.event not in ACTUATOR_EVENTS:
            raise InvalidRecordError(f"evento desconhecido: {self.event!r}")


def decision_key(decision: Decision) -> tuple[Reason, str]:
    """O que identifica o 'estado' de uma decisão de pular: o motivo e o detalhe."""
    return decision.reason, decision.detail


def should_record(decision: Decision, last_key: tuple[Reason, str] | None) -> bool:
    """Todo disparo é gravado; os `skip` só quando o motivo (ou o detalhe) muda."""
    return decision.triggered or decision_key(decision) != last_key


def local_day_bounds(now: datetime, utc_offset_hours: int) -> tuple[datetime, datetime]:
    """Início e fim (em UTC) do dia LOCAL que contém `now`."""
    zone = timezone(timedelta(hours=utc_offset_hours))
    start = now.astimezone(zone).replace(hour=0, minute=0, second=0, microsecond=0)
    return start.astimezone(UTC), (start + timedelta(days=1)).astimezone(UTC)
