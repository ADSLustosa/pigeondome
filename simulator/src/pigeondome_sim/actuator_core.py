"""Núcleo do atuador (gêmeo digital): máquina de estados pura, sem relógio nem E/S.

Todo o tempo entra como parâmetro (`Instant`), então cada regra de segurança pode ser testada de
forma determinística. Os limites pertencem ao atuador: nenhuma mensagem consegue alterá-los.
Na dúvida, a saída fica desligada (fail-safe).

O orçamento de pulsos pode ser guardado numa memória não volátil (`BudgetStore`), para sobreviver
a reinícios, e os eventos podem ser gravados num registro próprio (`EventJournal`), independente
de rede. Sem eles configurados, o comportamento é o de sempre (tudo em RAM).
"""

import contextlib
import math
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from pigeondome_sim.actuator_budget import BudgetRecord, BudgetStore, BudgetStoreError
from pigeondome_sim.actuator_journal import EventJournal, JournalEntry, JournalError


class State(StrEnum):
    SAFE_OFF = "safe_off"
    IDLE = "idle"
    PULSING = "pulsing"
    COOLDOWN = "cooldown"
    MAINTENANCE = "maintenance"
    FAULT = "fault"


class Fault(StrEnum):
    WATCHDOG = "watchdog"
    OVERCURRENT = "overcurrent"
    OVER_BUDGET = "over_budget"
    CLOCK_INVALID = "clock_invalid"
    SELF_TEST = "self_test"


class Reason(StrEnum):
    EXPIRED = "expired"
    DUPLICATE = "duplicate"
    BUSY = "busy"
    COOLDOWN = "cooldown"
    BUDGET_EXHAUSTED = "budget_exhausted"
    MAINTENANCE = "maintenance"
    FAULT = "fault"
    INVALID_COMMAND = "invalid_command"
    STOP_COMMAND = "stop_command"
    DISCONNECTED = "disconnected"
    WATCHDOG = "watchdog"


class EventType(StrEnum):
    COMMAND_ACCEPTED = "command_accepted"
    COMMAND_REJECTED = "command_rejected"
    PULSE_STARTED = "pulse_started"
    PULSE_FINISHED = "pulse_finished"
    PULSE_ABORTED = "pulse_aborted"


class Action(StrEnum):
    PULSE = "pulse"
    STOP = "stop"


@dataclass(frozen=True)
class Limits:
    """Limites de segurança: constantes do atuador, nunca parâmetros de comando."""

    max_pulse_s: int = 10
    max_ttl_s: int = 30
    cooldown_s: float = 30.0
    budget_s: float = 120.0
    budget_window_s: float = 3600.0
    watchdog_s: float = 5.0
    clock_skew_s: float = 5.0
    min_valid_time: datetime = datetime(2026, 1, 1, tzinfo=UTC)
    seen_capacity: int = 256


@dataclass(frozen=True)
class Instant:
    """O mesmo momento em dois relógios: monotônico (durações) e de parede (TTL, carimbos)."""

    mono_s: float
    wall: datetime


@dataclass(frozen=True)
class Command:
    command_id: str
    action: Action
    issued_at: datetime
    ttl_s: int
    duration_s: int | None = None


@dataclass(frozen=True)
class Event:
    type: EventType
    command_id: str | None
    at: datetime
    reason: Reason | None = None


@dataclass(frozen=True)
class Snapshot:
    """O que o atuador informa: já respeita as regras do contrato de estado."""

    online: bool
    state: State
    output_on: bool
    last_command_id: str | None
    fault: Fault | None
    budget_used_s_1h: int


class ActuatorCore:
    """Máquina de estados do atuador. A saída só liga dentro de um pulso aceito."""

    def __init__(
        self,
        limits: Limits | None = None,
        store: BudgetStore | None = None,
        journal: EventJournal | None = None,
    ) -> None:
        self._limits = limits if limits is not None else Limits()
        self._store = store
        self._journal = journal
        self._budget_restored = False
        self._connected = False
        self._needs_reset = True  # recém-ligado: falta o autoteste da primeira conexão
        self._maintenance = False
        self._fault: Fault | None = None
        self._pulse_start: float | None = None
        self._pulse_end: float | None = None
        self._pulse_command_id: str | None = None
        self._cooldown_end: float | None = None
        self._intervals: list[tuple[float, float]] = []
        self._last_command_id: str | None = None
        self._seen: deque[str] = deque(maxlen=self._limits.seen_capacity)
        self._last_mono: float | None = None

    # --- leitura -------------------------------------------------------------------------

    @property
    def output_on(self) -> bool:
        return self._pulse_end is not None

    @property
    def state(self) -> State:
        """Estado atual. Chame `tick(now)` antes se o tempo passou desde a última chamada."""
        if not self._connected:
            return State.SAFE_OFF
        if self._fault is not None:
            return State.FAULT
        if self._maintenance:
            return State.MAINTENANCE
        if self._pulse_end is not None:
            return State.PULSING
        if self._cooldown_end is not None:
            return State.COOLDOWN
        return State.IDLE

    def budget_used_s(self, now: Instant) -> float:
        """Segundos com a saída ligada dentro da janela do orçamento (até `now`)."""
        window_start = now.mono_s - self._limits.budget_window_s
        used = 0.0
        for start, end in self._intervals:
            used += max(0.0, min(end, now.mono_s) - max(start, window_start))
        if self._pulse_start is not None:
            used += max(0.0, now.mono_s - max(self._pulse_start, window_start))
        return used

    def snapshot(self, now: Instant) -> Snapshot:
        state = self.state
        used = math.ceil(self.budget_used_s(now) - 1e-9)
        return Snapshot(
            online=self._connected,
            state=state,
            output_on=self.output_on,
            last_command_id=self._last_command_id,
            fault=self._fault if state is State.FAULT else None,
            budget_used_s_1h=min(int(self._limits.budget_window_s), max(0, used)),
        )

    # --- memória do orçamento -------------------------------------------------------------

    def restore_budget(self, now: Instant) -> None:
        """Recupera os pulsos da memória não volátil. Chame uma vez, ao ligar, antes de conectar.

        Memória ilegível: sem saber quanto foi gasto, o atuador entra em falha `self_test` (só
        sai com reset local) e a hora seguinte conta como orçamento esgotado, mesmo depois do
        reset. Pulso que parece estar no futuro (relógio que voltou, ou pulso interrompido com
        o fim previsto adiante) conta inteiro, como se tivesse terminado agora.
        """
        store = self._store
        if store is None or self._budget_restored:
            return
        self._budget_restored = True
        unreadable = False
        try:
            records = store.load()
        except BudgetStoreError:
            unreadable = True
            if self._fault is None:
                self._fault = Fault.SELF_TEST
            spent = timedelta(seconds=self._limits.budget_s)
            records = [BudgetRecord(start=now.wall - spent, end=now.wall)]
        window_start = now.mono_s - self._limits.budget_window_s
        intervals: list[tuple[float, float]] = []
        for record in records:
            duration = max(0.0, (record.end - record.start).total_seconds())
            age = max(0.0, (now.wall - record.end).total_seconds())
            end = now.mono_s - age
            if end > window_start:
                intervals.append((end - duration, end))
        intervals.sort()
        self._intervals = intervals
        if intervals:
            cooldown_end = intervals[-1][1] + self._limits.cooldown_s
            if cooldown_end > now.mono_s:
                self._cooldown_end = cooldown_end
        if unreadable:
            # Fixa a hipótese conservadora no disco, se der; se não der, a falha já está ativa.
            with contextlib.suppress(BudgetStoreError):
                self._persist(now)

    def _persist(self, now: Instant, extra: tuple[float, float] | None = None) -> None:
        """Grava os pulsos (e o `extra`, se houver) no relógio de parede; ou BudgetStoreError."""
        store = self._store
        if store is None:
            return
        pulses = list(self._intervals)
        if self._pulse_start is not None and self._pulse_end is not None:
            pulses.append((self._pulse_start, self._pulse_end))
        if extra is not None:
            pulses.append(extra)

        def wall(mono: float) -> datetime:
            return now.wall - timedelta(seconds=now.mono_s - mono)

        store.save([BudgetRecord(wall(start), wall(end)) for start, end in pulses])

    def _persist_or_fault(self, now: Instant) -> bool:
        """Grava; se falhar, o atuador entra em falha `self_test`. Devolve se gravou."""
        try:
            self._persist(now)
        except BudgetStoreError:
            if self._fault is None:
                self._fault = Fault.SELF_TEST
            return False
        return True

    # --- entradas ------------------------------------------------------------------------

    def tick(self, now: Instant) -> list[Event]:
        """Deixa o tempo passar: encerra pulsos e pausas e aciona o watchdog."""
        return self._begin(now)

    def handle_command(self, command: Command, now: Instant) -> list[Event]:
        events = self._begin(now)
        events.extend(self._process(command, now))
        return events

    def reject_invalid(self, now: Instant, command_id: str | None = None) -> list[Event]:
        """Registra uma mensagem ilegível (JSON quebrado, fora do contrato)."""
        events = self._begin(now)
        events.append(self._reject(command_id, Reason.INVALID_COMMAND, now))
        return events

    def connection_restored(self, now: Instant, *, self_test_ok: bool = True) -> list[Event]:
        events = self._begin(now)
        self._connected = True
        if self._needs_reset and not self._maintenance and self._fault is None:
            self._run_self_test(now, self_test_ok)
        return events

    def connection_lost(self, now: Instant) -> list[Event]:
        events = self._begin(now)
        self._connected = False
        events.extend(self._abort_if_pulsing(now, Reason.DISCONNECTED))
        return events

    def set_maintenance(self, active: bool, now: Instant) -> list[Event]:
        """Chave física de manutenção: ligada, força a saída a zero e recusa comandos."""
        events = self._begin(now)
        if active and not self._maintenance:
            self._maintenance = True
            events.extend(self._abort_if_pulsing(now, Reason.MAINTENANCE))
        elif not active and self._maintenance:
            self._maintenance = False
            self._run_self_test(now, True)
        return events

    def inject_fault(self, fault: Fault, now: Instant) -> list[Event]:
        """Falha detectada pelo hardware. Trava até `reset`; o primeiro código é mantido."""
        events = self._begin(now)
        events.extend(self._abort_if_pulsing(now, Reason.FAULT))
        if self._fault is None:
            self._fault = fault
        return events

    def reset(self, now: Instant, *, self_test_ok: bool = True) -> list[Event]:
        """Reset local (botão físico): limpa a falha e refaz o autoteste."""
        events = self._begin(now)
        if self._fault is not None:
            self._fault = None
            self._run_self_test(now, self_test_ok)
        return events

    # --- internos ------------------------------------------------------------------------

    def _begin(self, now: Instant) -> list[Event]:
        if self._last_mono is not None and now.mono_s < self._last_mono:
            raise ValueError("o relógio monotônico não pode retroceder")
        return self._advance(now)

    def _advance(self, now: Instant) -> list[Event]:
        events: list[Event] = []
        end = self._pulse_end
        previous = self._last_mono
        if end is not None and previous is not None:
            deadline = previous + self._limits.watchdog_s
            finished = end <= deadline and now.mono_s >= end
            stalled = end > deadline and now.mono_s > deadline
            if finished:
                events.append(self._finish_pulse(end, now))
            elif stalled:
                events.append(self._abort_pulse(deadline, now, Reason.WATCHDOG))
                if self._fault is None:
                    self._fault = Fault.WATCHDOG
        cooldown_end = self._cooldown_end
        if cooldown_end is not None and now.mono_s >= cooldown_end:
            self._cooldown_end = None
        window_start = now.mono_s - self._limits.budget_window_s
        self._intervals = [(s, e) for s, e in self._intervals if e > window_start]
        self._last_mono = now.mono_s
        return events

    def _process(self, command: Command, now: Instant) -> list[Event]:
        if command.action is Action.STOP:
            return self._stop(command, now)
        duration = command.duration_s
        limits = self._limits
        if (
            not command.command_id
            or command.issued_at.tzinfo is None
            or not 1 <= command.ttl_s <= limits.max_ttl_s
            or duration is None
            or not 1 <= duration <= limits.max_pulse_s
        ):
            return [self._reject(command.command_id or None, Reason.INVALID_COMMAND, now)]
        if command.command_id in self._seen:
            return [self._reject(command.command_id, Reason.DUPLICATE, now)]
        self._seen.append(command.command_id)
        skew = timedelta(seconds=limits.clock_skew_s)
        if command.issued_at > now.wall + skew:
            return [self._reject(command.command_id, Reason.INVALID_COMMAND, now)]
        if now.wall > command.issued_at + timedelta(seconds=command.ttl_s):
            return [self._reject(command.command_id, Reason.EXPIRED, now)]
        blocked = self._blocking_reason()
        if blocked is not None:
            return [self._reject(command.command_id, blocked, now)]
        if self.budget_used_s(now) + duration > limits.budget_s:
            return [self._reject(command.command_id, Reason.BUDGET_EXHAUSTED, now)]
        try:
            # Gravar ANTES de ligar: sem registro do pulso, não há pulso.
            self._persist(now, extra=(now.mono_s, now.mono_s + duration))
        except BudgetStoreError:
            if self._fault is None:
                self._fault = Fault.SELF_TEST
            return [self._reject(command.command_id, Reason.FAULT, now)]
        accepted = Event(EventType.COMMAND_ACCEPTED, command.command_id, now.wall)
        started = Event(EventType.PULSE_STARTED, command.command_id, now.wall)
        # Gravar o evento ANTES de ligar: sem registro do pulso, não há pulso.
        if not self._record([accepted, started]):
            return [self._reject(command.command_id, Reason.FAULT, now)]
        self._pulse_start = now.mono_s
        self._pulse_end = now.mono_s + duration
        self._pulse_command_id = command.command_id
        self._last_command_id = command.command_id
        return [accepted, started]

    def _stop(self, command: Command, now: Instant) -> list[Event]:
        """Parar é sempre aceito: sem validar validade, repetição nem formato."""
        self._last_command_id = command.command_id or None
        events = [
            self._emit(Event(EventType.COMMAND_ACCEPTED, command.command_id or None, now.wall))
        ]
        events.extend(self._abort_if_pulsing(now, Reason.STOP_COMMAND))
        return events

    def _blocking_reason(self) -> Reason | None:
        if not self._connected:
            return Reason.DISCONNECTED
        if self._fault is not None:
            return Reason.FAULT
        if self._maintenance:
            return Reason.MAINTENANCE
        if self._pulse_end is not None:
            return Reason.BUSY
        if self._cooldown_end is not None:
            return Reason.COOLDOWN
        return None

    def _run_self_test(self, now: Instant, ok: bool) -> None:
        if self._fault is not None:
            return
        if now.wall < self._limits.min_valid_time:
            self._fault = Fault.CLOCK_INVALID
        elif not ok:
            self._fault = Fault.SELF_TEST
        elif not self._persist_or_fault(now) or not self._check_journal():
            return
        else:
            self._needs_reset = False

    def _close_pulse(self, at_mono: float) -> str | None:
        command_id = self._pulse_command_id
        if self._pulse_start is not None:
            self._intervals.append((self._pulse_start, max(self._pulse_start, at_mono)))
        self._pulse_start = None
        self._pulse_end = None
        self._pulse_command_id = None
        self._cooldown_end = at_mono + self._limits.cooldown_s
        return command_id

    def _finish_pulse(self, at_mono: float, now: Instant) -> Event:
        command_id = self._close_pulse(at_mono)
        self._persist_or_fault(now)
        return self._emit(Event(EventType.PULSE_FINISHED, command_id, self._wall_at(now, at_mono)))

    def _abort_pulse(self, at_mono: float, now: Instant, reason: Reason) -> Event:
        command_id = self._close_pulse(at_mono)
        self._persist_or_fault(now)
        return self._emit(
            Event(EventType.PULSE_ABORTED, command_id, self._wall_at(now, at_mono), reason)
        )

    def _abort_if_pulsing(self, now: Instant, reason: Reason) -> list[Event]:
        if self._pulse_end is None:
            return []
        return [self._abort_pulse(now.mono_s, now, reason)]

    @staticmethod
    def _wall_at(now: Instant, mono_s: float) -> datetime:
        return now.wall - timedelta(seconds=now.mono_s - mono_s)

    def _reject(self, command_id: str | None, reason: Reason, now: Instant) -> Event:
        return self._emit(Event(EventType.COMMAND_REJECTED, command_id, now.wall, reason))

    # --- registro de eventos ---------------------------------------------------------------

    def _record(self, events: Sequence[Event]) -> bool:
        """Grava no registro. Se falhar, o atuador entra em falha `self_test`: sem registro, sem
        operação. Devolve se gravou. Só impede LIGAR; desligar nunca depende do registro."""
        journal = self._journal
        if journal is None:
            return True
        entries = [
            JournalEntry(
                event.type.value,
                event.command_id,
                event.at,
                event.reason.value if event.reason is not None else None,
            )
            for event in events
        ]
        try:
            journal.append(entries)
        except JournalError:
            if self._fault is None:
                self._fault = Fault.SELF_TEST
            return False
        return True

    def _emit(self, event: Event) -> Event:
        """Registra um evento que já aconteceu (a saída já está como está) e o devolve."""
        self._record([event])
        return event

    def _check_journal(self) -> bool:
        journal = self._journal
        if journal is None:
            return True
        try:
            journal.check()
        except JournalError:
            if self._fault is None:
                self._fault = Fault.SELF_TEST
            return False
        return True
