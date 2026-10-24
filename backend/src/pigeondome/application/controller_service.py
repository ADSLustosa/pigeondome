"""Serviço do controlador: a cada passo lê, decide, registra e, só se for o caso, comanda."""

import logging
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Protocol

from pigeondome.application.actuation_use_cases import LoadPolicyContext
from pigeondome.application.ports import (
    ControllerFlags,
    DecisionRepository,
    DetectionRepository,
    StorageError,
)
from pigeondome.domain.actuation import (
    ActuatorStatus,
    Decision,
    PolicyConfig,
    PolicyContext,
    Reason,
    Verdict,
    decide,
)
from pigeondome.domain.actuation_log import (
    DecisionRecord,
    decision_key,
    local_day_bounds,
    should_record,
)

log = logging.getLogger("pigeondome.controller")


class CommandSendError(Exception):
    """O comando não pôde ser enviado ao atuador (por exemplo, sem conexão com o broker)."""


class CommandSender(Protocol):
    def send_pulse(self, actuator_id: str, duration_s: int, now: datetime) -> str:
        """Envia um pulso e devolve o command_id. Levanta CommandSendError se não enviar."""
        ...


class ActuatorStatusSource(Protocol):
    def current(self) -> ActuatorStatus:
        """O último estado conhecido do atuador."""
        ...


class ControllerService:
    def __init__(
        self,
        policy: PolicyConfig,
        camera_id: str,
        actuator_id: str,
        detections: DetectionRepository,
        decisions: DecisionRepository,
        flags: ControllerFlags,
        status: ActuatorStatusSource,
        sender: CommandSender,
    ) -> None:
        self._policy = policy
        self._camera_id = camera_id
        self._actuator_id = actuator_id
        self._detections = detections
        self._decisions = decisions
        self._status = status
        self._sender = sender
        self._context = LoadPolicyContext(decisions, flags, policy.utc_offset_hours, policy.mode)
        self._last_key: tuple[Reason, str] | None = None
        self._own_triggers: list[datetime] = []

    def step(self, now: datetime) -> Decision | None:
        """Um passo do controlador. Devolve a decisão tomada, ou None se não deu para decidir."""
        lookback = timedelta(seconds=self._policy.window_s + 1)
        try:
            readings = self._detections.list_between(
                self._camera_id, now - lookback, now + timedelta(seconds=1)
            )
            context = self._with_own_history(self._context.execute(self._actuator_id, now), now)
        except StorageError:
            log.warning("sem acesso ao banco: nenhuma decisão neste passo")
            return None
        decision = decide(self._policy, now, readings, self._status.current(), context)
        command_id: str | None = None
        if decision.verdict is Verdict.PULSE:
            decision, command_id = self._send(decision, now)
        if decision.triggered:
            self._own_triggers.append(now)
        self._record(decision, now, command_id)
        return decision

    def _with_own_history(self, context: PolicyContext, now: datetime) -> PolicyContext:
        """Soma o que ESTE processo disparou, se a gravação falhou: nunca pulsar em dobro."""
        day_start, day_end = local_day_bounds(now, self._policy.utc_offset_hours)
        self._own_triggers = [t for t in self._own_triggers if t >= now - timedelta(days=1)]
        own_today = sum(1 for t in self._own_triggers if day_start <= t < day_end)
        known = [t for t in (context.last_pulse_at, *self._own_triggers) if t is not None]
        return replace(
            context,
            pulses_today=max(context.pulses_today, own_today),
            last_pulse_at=max(known, default=None),
        )

    def _send(self, decision: Decision, now: datetime) -> tuple[Decision, str | None]:
        try:
            command_id = self._sender.send_pulse(self._actuator_id, self._policy.pulse_s, now)
        except CommandSendError:
            log.warning("comando não enviado: sem conexão com o broker")
            failed = replace(
                decision,
                verdict=Verdict.SKIP,
                reason=Reason.ACTUATOR_UNAVAILABLE,
                duration_s=None,
                detail="send_failed",
            )
            return failed, None
        return decision, command_id

    def _record(self, decision: Decision, now: datetime, command_id: str | None) -> None:
        if not should_record(decision, self._last_key):
            return
        record = DecisionRecord.from_decision(
            decision,
            decided_at=now,
            camera_id=self._camera_id,
            actuator_id=self._actuator_id,
            mode=self._policy.mode,
            command_id=command_id,
        )
        try:
            self._decisions.add(record)
        except StorageError:
            log.warning("decisão não gravada: banco indisponível")
            return  # a chave não é atualizada: o próximo passo tenta gravar de novo
        self._last_key = decision_key(decision)
        log.info(
            "decisão: %s/%s %s (leituras=%d com_pombo=%d confiança=%.2f)",
            decision.verdict.value,
            decision.reason.value,
            decision.detail,
            decision.evidence.readings,
            decision.evidence.detections,
            decision.evidence.mean_confidence,
        )
