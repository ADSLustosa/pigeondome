"""Rotas de atuação da API: estado do atuador e do controlador, trilha e a chave geral.

A chave geral só pode ser LIGADA por aqui. Parar o sistema é sempre seguro; armá-lo de novo
exige estar na máquina do banco (scripts/kill-switch.ps1 off), nunca pela rede.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import FastAPI, Header, Path, Query

from pigeondome.adapters.api.actuation_schemas import (
    ActuatorStatusOut,
    ControllerOut,
    DecisionOut,
    DecisionsOut,
    EventOut,
    EventsOut,
    KillSwitchOut,
)
from pigeondome.adapters.api.errors import ApiError, FieldError, ProblemDetails
from pigeondome.application.ports import (
    ActuatorEventRepository,
    ActuatorStateRepository,
    ControllerFlags,
    ControllerStatusRepository,
    DecisionRepository,
)
from pigeondome.application.status_use_cases import (
    EngageKillSwitch,
    GetActuatorStatus,
    GetControllerStatus,
    ListActuatorEvents,
    ListDecisions,
)
from pigeondome.domain.actuation_log import ActuatorEventRecord, DecisionRecord
from pigeondome.domain.models import DEVICE_ID_PATTERN

# Um POST simples não dispara preflight de CORS: qualquer página aberta no navegador poderia
# dispará-lo. Exigir um cabeçalho próprio força o preflight, e só a origem do painel o passa.
ACTION_HEADER = "X-Pigeondome-Action"
ACTION_VALUE = "kill-switch-on"

DEFAULT_LOG_WINDOW = timedelta(hours=24)
MAX_LOG_WINDOW = timedelta(days=7)
DEFAULT_LIMIT = 100
MAX_LIMIT = 500

ActuatorIdPath = Annotated[str, Path(pattern=DEVICE_ID_PATTERN.pattern)]
StartQuery = Annotated[
    datetime | None,
    Query(description="início (ISO 8601 com fuso, ex.: 2026-10-24T21:00:00Z)"),
]
EndQuery = Annotated[datetime | None, Query(description="fim (padrão: agora)")]
LimitQuery = Annotated[
    int,
    Query(ge=1, le=MAX_LIMIT, description="máximo de registros: os mais recentes"),
]


@dataclass(frozen=True)
class ActuationPorts:
    """Tudo que a API precisa para ler (e ligar a chave geral) da trilha do controlador."""

    actuators: ActuatorStateRepository
    controller: ControllerStatusRepository
    decisions: DecisionRepository
    events: ActuatorEventRepository
    flags: ControllerFlags


def utc_now() -> datetime:
    return datetime.now(UTC)


def _problem(description: str) -> dict[str, Any]:
    """Documenta no OpenAPI o formato real dos erros (RFC 9457)."""
    return {"model": ProblemDetails, "description": description}


def _invalid_window(message: str, field: str, code: str) -> ApiError:
    return ApiError(
        422,
        "janela-invalida",
        "Janela de tempo inválida",
        message,
        [FieldError(field=field, message=message, code=code)],
    )


def _resolve_log_window(
    start: datetime | None, end: datetime | None, now: datetime
) -> tuple[datetime, datetime]:
    """Janela das consultas de trilha: padrão de 24 h até agora, no máximo 7 dias."""
    end = end or now
    start = start or end - DEFAULT_LOG_WINDOW
    for name, value in (("start", start), ("end", end)):
        if value.tzinfo is None:
            message = f"{name} precisa ter fuso horário (ex.: 2026-10-24T21:00:00Z)"
            raise ApiError(
                422,
                "parametros-invalidos",
                "Parâmetros inválidos",
                message,
                [FieldError(field=name, message=message, code="missing_timezone")],
            )
    if end <= start:
        raise _invalid_window("end precisa ser posterior a start", "end", "end_before_start")
    if end - start > MAX_LOG_WINDOW:
        message = "a janela máxima desta consulta é de 7 dias"
        raise _invalid_window(message, "end", "window_too_large")
    return start, end


def _decision_out(record: DecisionRecord) -> DecisionOut:
    return DecisionOut(
        decided_at=record.decided_at,
        camera_id=record.camera_id,
        mode=record.mode.value,
        verdict=record.verdict.value,
        reason=record.reason.value,
        detail=record.detail,
        arm=record.arm.value if record.arm is not None else None,
        duration_s=record.duration_s,
        command_id=record.command_id,
        readings=record.readings,
        detections=record.detections,
        mean_confidence=record.mean_confidence,
        triggered=record.triggered,
    )


def _event_out(record: ActuatorEventRecord) -> EventOut:
    return EventOut(
        occurred_at=record.occurred_at,
        event=record.event,
        command_id=record.command_id,
        reason_code=record.reason_code,
    )


def register_actuation_routes(
    app: FastAPI, ports: ActuationPorts, clock: Callable[[], datetime]
) -> None:
    actuator_status = GetActuatorStatus(ports.actuators)
    controller_status = GetControllerStatus(ports.controller, ports.flags)
    decisions = ListDecisions(ports.decisions)
    events = ListActuatorEvents(ports.events)
    engage = EngageKillSwitch(ports.flags)

    @app.get(
        "/api/v1/actuators/{actuator_id}/status",
        response_model=ActuatorStatusOut,
        tags=["atuação"],
        summary="Último estado conhecido do atuador",
        description=(
            "O estado vem da última mensagem que o controlador recebeu, com a hora da "
            "RECEPÇÃO. `stale` indica um atuador que consta como online mas não manda "
            "mensagem há mais de 30 s: o dado não é confiável. Um atuador offline (aviso do "
            "broker) não é `stale`: é um fato, e `age_s` diz há quanto tempo."
        ),
        responses={
            404: _problem("Atuador nunca visto pelo controlador"),
            503: _problem("Armazenamento indisponível"),
        },
    )
    def get_actuator_status(actuator_id: ActuatorIdPath) -> ActuatorStatusOut:
        view = actuator_status.execute(actuator_id, clock())
        if view is None:
            raise ApiError(
                404,
                "atuador-desconhecido",
                "Atuador desconhecido",
                f"nenhum estado recebido do atuador {actuator_id!r}",
            )
        record = view.record
        return ActuatorStatusOut(
            actuator_id=record.actuator_id,
            online=record.online,
            state=record.state,
            output_on=record.output_on,
            budget_used_s_1h=record.budget_used_s_1h,
            received_at=record.received_at,
            age_s=view.age_s,
            stale=view.stale,
        )

    @app.get(
        "/api/v1/controller",
        response_model=ControllerOut,
        tags=["atuação"],
        summary="Estado do controlador e da chave geral",
        description=(
            "`running` só é verdadeiro com batimento de até 15 s. A linha do controlador "
            "continua no banco depois que ele para: só a idade do batimento diz se está vivo."
        ),
        responses={503: _problem("Armazenamento indisponível")},
    )
    def get_controller() -> ControllerOut:
        view = controller_status.execute(clock())
        record = view.record
        return ControllerOut(
            kill_switch=view.kill_switch,
            running=view.running,
            mode=record.mode.value if record is not None else None,
            camera_id=record.camera_id if record is not None else None,
            actuator_id=record.actuator_id if record is not None else None,
            started_at=record.started_at if record is not None else None,
            heartbeat_at=record.heartbeat_at if record is not None else None,
            age_s=view.age_s,
        )

    @app.get(
        "/api/v1/actuators/{actuator_id}/decisions",
        response_model=DecisionsOut,
        tags=["atuação"],
        summary="Decisões do controlador, as mais recentes primeiro",
        description=(
            "Só os disparos e as mudanças de motivo são gravados: um período longo sem linhas "
            "significa que nada mudou, e não que o controlador parou (veja /controller)."
        ),
        responses={
            422: _problem("Parâmetros inválidos ou janela de tempo inválida"),
            503: _problem("Armazenamento indisponível"),
        },
    )
    def list_decisions(
        actuator_id: ActuatorIdPath,
        start: StartQuery = None,
        end: EndQuery = None,
        limit: LimitQuery = DEFAULT_LIMIT,
    ) -> DecisionsOut:
        start, end = _resolve_log_window(start, end, clock())
        found, truncated = decisions.execute(actuator_id, start, end, limit)
        return DecisionsOut(
            actuator_id=actuator_id,
            start=start,
            end=end,
            limit=limit,
            truncated=truncated,
            decisions=[_decision_out(record) for record in found],
        )

    @app.get(
        "/api/v1/actuators/{actuator_id}/events",
        response_model=EventsOut,
        tags=["atuação"],
        summary="Eventos relatados pelo atuador, os mais recentes primeiro",
        responses={
            422: _problem("Parâmetros inválidos ou janela de tempo inválida"),
            503: _problem("Armazenamento indisponível"),
        },
    )
    def list_events(
        actuator_id: ActuatorIdPath,
        start: StartQuery = None,
        end: EndQuery = None,
        limit: LimitQuery = DEFAULT_LIMIT,
    ) -> EventsOut:
        start, end = _resolve_log_window(start, end, clock())
        found, truncated = events.execute(actuator_id, start, end, limit)
        return EventsOut(
            actuator_id=actuator_id,
            start=start,
            end=end,
            limit=limit,
            truncated=truncated,
            events=[_event_out(record) for record in found],
        )

    @app.post(
        "/api/v1/controller/kill-switch",
        response_model=KillSwitchOut,
        tags=["atuação"],
        summary="Liga a chave geral: o controlador para de comandar o atuador",
        description=(
            "Só LIGA a chave, e é idempotente: parar o sistema é sempre seguro. Para "
            "desligá-la (voltar a permitir pulsos) use scripts/kill-switch.ps1 off, na máquina "
            "do banco. Exige o cabeçalho X-Pigeondome-Action: kill-switch-on."
        ),
        responses={
            403: _problem("Cabeçalho de confirmação ausente ou incorreto"),
            503: _problem("Armazenamento indisponível"),
        },
    )
    def engage_kill_switch(
        confirmation: Annotated[
            str | None,
            Header(alias=ACTION_HEADER, description="precisa ser kill-switch-on"),
        ] = None,
    ) -> KillSwitchOut:
        if confirmation != ACTION_VALUE:
            raise ApiError(
                403,
                "acao-nao-confirmada",
                "Ação não confirmada",
                f"envie o cabeçalho {ACTION_HEADER}: {ACTION_VALUE} para ligar a chave geral",
            )
        engage.execute(clock())
        return KillSwitchOut(kill_switch=True)
