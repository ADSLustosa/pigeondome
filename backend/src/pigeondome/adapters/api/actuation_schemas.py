"""Contratos de resposta da API de atuação: o que o painel enxerga do atuador e do controlador."""

from datetime import datetime

from pydantic import BaseModel, Field


class ActuatorStatusOut(BaseModel):
    actuator_id: str
    online: bool = Field(description="False quando o broker declarou o atuador fora do ar")
    state: str = Field(description="safe_off, idle, pulsing, cooldown, maintenance ou fault")
    output_on: bool | None = Field(description="saída ligada agora; null se não informado")
    budget_used_s_1h: int | None = Field(
        description="segundos de saída ligada na última hora; null se não informado"
    )
    received_at: datetime = Field(description="quando o controlador recebeu a mensagem (UTC)")
    age_s: float = Field(ge=0, description="segundos desde a recepção")
    stale: bool = Field(
        description="consta como online, mas não manda mensagem há mais de 30 s: dado não confiável"
    )


class ControllerOut(BaseModel):
    kill_switch: bool = Field(description="chave geral ligada: o controlador não comanda nada")
    running: bool = Field(description="o último batimento tem no máximo 15 s")
    mode: str | None = Field(description="off, dry_run, live ou experiment; null se nunca rodou")
    camera_id: str | None
    actuator_id: str | None
    started_at: datetime | None = Field(description="início do processo do controlador atual")
    heartbeat_at: datetime | None = Field(description="último batimento gravado")
    age_s: float | None = Field(description="segundos desde o último batimento")


class DecisionOut(BaseModel):
    decided_at: datetime
    camera_id: str
    mode: str = Field(description="off, dry_run, live ou experiment, na hora da decisão")
    verdict: str = Field(description="pulse (comando enviado), would_pulse (modo seco) ou skip")
    reason: str = Field(description="motivo estável da decisão, ex.: evidence_confirmed")
    detail: str
    arm: str | None = Field(description="treatment ou control; só no modo experimento")
    duration_s: int | None
    command_id: str | None
    readings: int
    detections: int = Field(description="leituras COM pombo dentro da janela de evidência")
    mean_confidence: float
    triggered: bool = Field(
        description="todas as condições foram atendidas (real, seco ou controle)"
    )


class DecisionsOut(BaseModel):
    actuator_id: str
    start: datetime
    end: datetime
    limit: int
    truncated: bool = Field(description="havia mais decisões na janela do que o limite")
    decisions: list[DecisionOut] = Field(description="da mais recente para a mais antiga")


class EventOut(BaseModel):
    occurred_at: datetime
    event: str = Field(description="command_accepted, command_rejected, pulse_started, ...")
    command_id: str | None
    reason_code: str | None


class EventsOut(BaseModel):
    actuator_id: str
    start: datetime
    end: datetime
    limit: int
    truncated: bool = Field(description="havia mais eventos na janela do que o limite")
    events: list[EventOut] = Field(description="do mais recente para o mais antigo")


class KillSwitchOut(BaseModel):
    kill_switch: bool
