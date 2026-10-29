"""Política do controlador de atuação: decide QUANDO acionar o atuador.

Núcleo puro (sem relógio, sem E/S): recebe as leituras recentes da câmera, o estado do atuador e
o histórico do controlador, e devolve uma decisão com o motivo e as evidências. As regras são
avaliadas em ordem fixa e a primeira que se aplica vence; o modo seco fica por último, para que
registre exatamente o que o modo real faria.
"""

import random
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum

from pigeondome.domain.models import Detection, PresenceReading


class Mode(StrEnum):
    OFF = "off"
    DRY_RUN = "dry_run"  # decide e registra, mas não aciona (o padrão)
    LIVE = "live"
    EXPERIMENT = "experiment"  # live, com blocos de controle sorteados


class Verdict(StrEnum):
    PULSE = "pulse"  # mandar o comando ao atuador
    WOULD_PULSE = "would_pulse"  # modo seco: o que teria feito
    SKIP = "skip"


class Reason(StrEnum):
    MODE_OFF = "mode_off"
    KILL_SWITCH = "kill_switch"
    STALE_DATA = "stale_data"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    QUIET_HOURS = "quiet_hours"
    ACTUATOR_UNAVAILABLE = "actuator_unavailable"
    RETRY_GAP = "retry_gap"
    DAILY_BUDGET = "daily_budget"
    EXPERIMENT_CONTROL = "experiment_control"
    DRY_RUN = "dry_run"
    EVIDENCE_CONFIRMED = "evidence_confirmed"


class EvidenceSource(StrEnum):
    """De onde vem a evidência de que há pombo. As regras de segurança valem para qualquer uma."""

    CAMERA = "camera"  # contagem de pombos e confiança, por imagem
    PRESENCE_SENSOR = "presence_sensor"  # só presente/ausente: não distingue pombo de pessoa


Reading = Detection | PresenceReading


class Arm(StrEnum):
    TREATMENT = "treatment"
    CONTROL = "control"


@dataclass(frozen=True)
class PolicyConfig:
    """Parâmetros da política. Os padrões são conservadores: o modo inicial é o seco."""

    mode: Mode = Mode.DRY_RUN
    pulse_s: int = 5
    window_s: float = 30.0
    min_detections: int = 3
    min_confidence: float = 0.7
    source: EvidenceSource = EvidenceSource.CAMERA
    presence_min_positive: int = 3  # sensor: leituras "presente" na janela para confirmar
    max_data_age_s: float = 15.0
    max_actuator_report_age_s: float = 30.0
    retry_gap_s: float = 120.0
    max_pulses_per_day: int = 40
    utc_offset_hours: int = -3
    quiet_start_hour: int | None = None
    quiet_end_hour: int | None = None
    experiment_block_hours: int = 6
    experiment_seed: int = 0

    def __post_init__(self) -> None:
        if not 1 <= self.pulse_s <= 10:
            raise ValueError("pulse_s precisa ficar entre 1 e 10 s (limite do atuador)")
        if self.min_detections < 1:
            raise ValueError("min_detections precisa ser pelo menos 1")
        if self.presence_min_positive < 1:
            raise ValueError("presence_min_positive precisa ser pelo menos 1")
        if not 0.0 <= self.min_confidence <= 1.0:
            raise ValueError("min_confidence precisa ficar entre 0 e 1")
        if min(self.window_s, self.max_data_age_s, self.max_actuator_report_age_s) <= 0:
            raise ValueError("janelas e idades máximas precisam ser positivas")
        if self.retry_gap_s < 0 or self.max_pulses_per_day < 0:
            raise ValueError("intervalo mínimo e orçamento diário não podem ser negativos")
        hours = self.experiment_block_hours
        if not 1 <= hours <= 12 or 24 % hours != 0 or (24 // hours) % 2 != 0:
            raise ValueError("experiment_block_hours precisa dividir o dia em blocos pares")
        quiet = (self.quiet_start_hour, self.quiet_end_hour)
        if (quiet[0] is None) != (quiet[1] is None):
            raise ValueError("a janela de silêncio precisa ter início e fim")
        if any(hour is not None and not 0 <= hour <= 23 for hour in quiet):
            raise ValueError("as horas da janela de silêncio vão de 0 a 23")


@dataclass(frozen=True)
class ActuatorStatus:
    """O que o controlador sabe do atuador (a última mensagem de estado recebida)."""

    online: bool
    state: str
    reported_at: datetime | None


@dataclass(frozen=True)
class PolicyContext:
    """Memória do controlador: chave geral e histórico dos disparos."""

    kill_switch: bool = False
    pulses_today: int = 0
    last_pulse_at: datetime | None = None


@dataclass(frozen=True)
class Evidence:
    """Resumo da janela. Com o sensor, "com pombo" significa "com presença" e a confiança não
    se aplica (fica em 0 e a política a ignora)."""

    readings: int
    detections: int  # leituras COM pombo (câmera) ou COM presença (sensor) dentro da janela
    mean_confidence: float  # só das leituras positivas; sempre 0 no sensor
    latest_age_s: float | None  # idade da leitura mais recente, positiva ou não
    latest_has_pigeons: bool  # a leitura mais recente é positiva
    source: EvidenceSource = EvidenceSource.CAMERA


@dataclass(frozen=True)
class Decision:
    verdict: Verdict
    reason: Reason
    duration_s: int | None
    arm: Arm | None
    evidence: Evidence
    detail: str = ""

    @property
    def triggered(self) -> bool:
        """Verdadeiro quando TODAS as condições foram atendidas (agiria, ou teria agido)."""
        return self.verdict is not Verdict.SKIP or self.reason is Reason.EXPERIMENT_CONTROL


def _observations(
    source: EvidenceSource, readings: Sequence[Reading]
) -> list[tuple[datetime, bool, float]]:
    """(instante, positiva?, confiança) só das leituras da fonte configurada.

    Leituras de outra fonte são ignoradas: um sensor nunca confirma o que a câmera não viu, nem
    o contrário, e uma troca de fonte não reaproveita dados da fonte antiga.
    """
    if source is EvidenceSource.CAMERA:
        return [
            (r.timestamp, r.has_pigeons, r.confidence) for r in readings if isinstance(r, Detection)
        ]
    return [(r.timestamp, r.present, 0.0) for r in readings if isinstance(r, PresenceReading)]


def gather_evidence(config: PolicyConfig, now: datetime, readings: Sequence[Reading]) -> Evidence:
    window_start = now - timedelta(seconds=config.window_s)
    recent = sorted(
        (o for o in _observations(config.source, readings) if window_start <= o[0] <= now),
        key=lambda o: o[0],
    )
    positive = [o for o in recent if o[1]]
    mean_confidence = sum(o[2] for o in positive) / len(positive) if positive else 0.0
    latest = recent[-1] if recent else None
    return Evidence(
        readings=len(recent),
        detections=len(positive),
        mean_confidence=mean_confidence,
        latest_age_s=(now - latest[0]).total_seconds() if latest else None,
        latest_has_pigeons=latest[1] if latest else False,
        source=config.source,
    )


def evidence_is_sufficient(config: PolicyConfig, evidence: Evidence) -> bool:
    """A câmera exige contagem e confiança; o sensor, só leituras de presença suficientes.

    Nos dois casos a leitura mais recente precisa ser positiva: a presença acabou, não pulsa.
    """
    if not evidence.latest_has_pigeons:
        return False
    if config.source is EvidenceSource.PRESENCE_SENSOR:
        return evidence.detections >= config.presence_min_positive
    return (
        evidence.detections >= config.min_detections
        and evidence.mean_confidence >= config.min_confidence
    )


def experiment_arm(config: PolicyConfig, now: datetime) -> Arm:
    """Braço do experimento em `now`: metade dos blocos de cada dia recebe o tratamento.

    A escolha é determinista (semente + data local), reproduzível e balanceada dentro do dia, o
    que protege a comparação contra o efeito da hora do dia.
    """
    local = now.astimezone(timezone(timedelta(hours=config.utc_offset_hours)))
    blocks = 24 // config.experiment_block_hours
    order = list(range(blocks))
    rng = random.Random(f"{config.experiment_seed}:{local.date().isoformat()}")  # noqa: S311
    rng.shuffle(order)
    treated = set(order[: blocks // 2])
    block = local.hour // config.experiment_block_hours
    return Arm.TREATMENT if block in treated else Arm.CONTROL


def in_quiet_hours(config: PolicyConfig, local_hour: int) -> bool:
    start, end = config.quiet_start_hour, config.quiet_end_hour
    if start is None or end is None:
        return False
    if start <= end:
        return start <= local_hour < end
    return local_hour >= start or local_hour < end  # a janela atravessa a meia-noite


def actuator_problem(config: PolicyConfig, now: datetime, actuator: ActuatorStatus) -> str | None:
    """Por que o atuador não pode receber um pulso agora (None = disponível)."""
    if not actuator.online:
        return "offline"
    if actuator.reported_at is None:
        return "stale_report"
    if (now - actuator.reported_at).total_seconds() > config.max_actuator_report_age_s:
        return "stale_report"
    if actuator.state != "idle":
        return actuator.state
    return None


def decide(
    config: PolicyConfig,
    now: datetime,
    readings: Sequence[Reading],
    actuator: ActuatorStatus,
    context: PolicyContext,
) -> Decision:
    evidence = gather_evidence(config, now, readings)
    arm = experiment_arm(config, now) if config.mode is Mode.EXPERIMENT else None

    def skip(reason: Reason, detail: str = "") -> Decision:
        return Decision(Verdict.SKIP, reason, None, arm, evidence, detail)

    if config.mode is Mode.OFF:
        return skip(Reason.MODE_OFF)
    if context.kill_switch:
        return skip(Reason.KILL_SWITCH)
    if evidence.latest_age_s is None or evidence.latest_age_s > config.max_data_age_s:
        return skip(Reason.STALE_DATA)
    if not evidence_is_sufficient(config, evidence):
        return skip(Reason.INSUFFICIENT_EVIDENCE)
    local = now.astimezone(timezone(timedelta(hours=config.utc_offset_hours)))
    if in_quiet_hours(config, local.hour):
        return skip(Reason.QUIET_HOURS)
    problem = actuator_problem(config, now, actuator)
    if problem is not None:
        return skip(Reason.ACTUATOR_UNAVAILABLE, problem)
    since_last = (
        (now - context.last_pulse_at).total_seconds() if context.last_pulse_at is not None else None
    )
    if since_last is not None and since_last < config.retry_gap_s:
        return skip(Reason.RETRY_GAP)
    if context.pulses_today >= config.max_pulses_per_day:
        return skip(Reason.DAILY_BUDGET)
    if arm is Arm.CONTROL:
        return skip(Reason.EXPERIMENT_CONTROL)
    if config.mode is Mode.DRY_RUN:
        return Decision(Verdict.WOULD_PULSE, Reason.DRY_RUN, config.pulse_s, arm, evidence)
    return Decision(Verdict.PULSE, Reason.EVIDENCE_CONFIRMED, config.pulse_s, arm, evidence)
