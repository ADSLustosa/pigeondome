"""Núcleo do atuador: cada regra de segurança, uma por vez."""

from datetime import UTC, datetime, timedelta

import pytest

from pigeondome_sim.actuator_core import (
    Action,
    ActuatorCore,
    Command,
    Event,
    EventType,
    Fault,
    Instant,
    Reason,
    State,
)

BASE = datetime(2026, 10, 23, 12, 0, 0, tzinfo=UTC)
MONO0 = 1000.0


def at(seconds: float) -> Instant:
    return Instant(mono_s=MONO0 + seconds, wall=BASE + timedelta(seconds=seconds))


def command(
    n: int,
    *,
    action: Action = Action.PULSE,
    duration: int | None = 5,
    ttl: int = 10,
    issued: float = 0.0,
) -> Command:
    return Command(
        command_id=f"00000000-0000-4000-8000-{n:012d}",
        action=action,
        issued_at=BASE + timedelta(seconds=issued),
        ttl_s=ttl,
        duration_s=duration if action is Action.PULSE else None,
    )


def online_core() -> ActuatorCore:
    core = ActuatorCore()
    core.connection_restored(at(0))
    return core


def kinds(events: list[Event]) -> list[EventType]:
    return [event.type for event in events]


def rejection(events: list[Event]) -> Reason | None:
    """Motivo da recusa (a última do lote, pois o tempo pode ter encerrado um pulso antes)."""
    assert events[-1].type is EventType.COMMAND_REJECTED
    return events[-1].reason


STARTED = [EventType.COMMAND_ACCEPTED, EventType.PULSE_STARTED]


def test_starts_in_safe_off_and_becomes_idle_when_the_self_test_passes() -> None:
    core = ActuatorCore()
    assert core.state is State.SAFE_OFF
    assert not core.output_on
    core.connection_restored(at(0))
    assert core.state is State.IDLE
    assert core.snapshot(at(0)).online


def test_accepted_pulse_turns_the_output_on() -> None:
    core = online_core()
    events = core.handle_command(command(1), at(0))
    assert kinds(events) == STARTED
    assert core.state is State.PULSING
    assert core.output_on
    assert core.snapshot(at(0)).last_command_id == command(1).command_id


def test_pulse_ends_at_the_planned_time_and_the_cooldown_starts() -> None:
    core = online_core()
    core.handle_command(command(1), at(0))
    assert core.tick(at(4)) == []
    assert core.state is State.PULSING
    events = core.tick(at(6))
    assert kinds(events) == [EventType.PULSE_FINISHED]
    assert events[0].at == BASE + timedelta(seconds=5)
    assert core.state is State.COOLDOWN
    assert not core.output_on


def test_cooldown_blocks_new_pulses_until_it_ends() -> None:
    core = online_core()
    core.handle_command(command(1), at(0))  # termina em 5 s; pausa até 35 s
    assert rejection(core.handle_command(command(2, issued=20), at(20))) is Reason.COOLDOWN
    assert kinds(core.handle_command(command(3, issued=36), at(36))) == STARTED


def test_second_pulse_while_pulsing_is_busy() -> None:
    core = online_core()
    core.handle_command(command(1, duration=10), at(0))
    assert rejection(core.handle_command(command(2, issued=1), at(1))) is Reason.BUSY
    assert core.state is State.PULSING


def test_command_is_valid_until_its_ttl_and_expired_afterwards() -> None:
    on_time = online_core().handle_command(command(1, ttl=10, issued=0), at(10))
    assert kinds(on_time) == STARTED
    late = online_core().handle_command(command(2, ttl=10, issued=0), at(10.5))
    assert rejection(late) is Reason.EXPIRED


def test_command_from_the_future_is_rejected_beyond_the_clock_skew() -> None:
    far = online_core().handle_command(command(1, issued=60), at(0))
    assert rejection(far) is Reason.INVALID_COMMAND
    near = online_core().handle_command(command(2, issued=3), at(0))
    assert kinds(near) == STARTED


def test_repeated_command_id_is_rejected_even_after_the_cooldown() -> None:
    core = online_core()
    core.handle_command(command(1), at(0))
    events = core.handle_command(command(1, issued=40), at(40))
    assert rejection(events) is Reason.DUPLICATE


MALFORMED = [
    pytest.param(command(1, duration=None), id="pulse_without_duration"),
    pytest.param(command(2, duration=0), id="duration_zero"),
    pytest.param(command(3, duration=11), id="duration_above_limit"),
    pytest.param(command(4, ttl=0), id="ttl_zero"),
    pytest.param(command(5, ttl=31), id="ttl_above_limit"),
    pytest.param(Command("", Action.PULSE, BASE, 10, 5), id="empty_id"),
    pytest.param(
        Command(command(6).command_id, Action.PULSE, datetime(2026, 10, 23, 12), 10, 5),
        id="naive_datetime",
    ),
]


@pytest.mark.parametrize("bad", MALFORMED)
def test_malformed_commands_are_rejected_and_never_turn_the_output_on(bad: Command) -> None:
    core = online_core()
    events = core.handle_command(bad, at(0))
    assert rejection(events) is Reason.INVALID_COMMAND
    assert not core.output_on


def test_stop_aborts_a_running_pulse_immediately() -> None:
    core = online_core()
    core.handle_command(command(1, duration=10), at(0))
    events = core.handle_command(command(2, action=Action.STOP, issued=2), at(2))
    assert kinds(events) == [EventType.COMMAND_ACCEPTED, EventType.PULSE_ABORTED]
    assert events[1].reason is Reason.STOP_COMMAND
    assert not core.output_on
    assert core.state is State.COOLDOWN


def test_stop_while_idle_is_accepted_and_changes_nothing() -> None:
    core = online_core()
    events = core.handle_command(command(1, action=Action.STOP), at(0))
    assert kinds(events) == [EventType.COMMAND_ACCEPTED]
    assert core.state is State.IDLE


def test_stop_is_accepted_even_when_malformed_expired_or_repeated() -> None:
    core = online_core()
    sloppy = Command("not-even-a-uuid", Action.STOP, datetime(2020, 1, 1), 0)
    assert kinds(core.handle_command(sloppy, at(0))) == [EventType.COMMAND_ACCEPTED]
    assert kinds(core.handle_command(sloppy, at(1))) == [EventType.COMMAND_ACCEPTED]


def test_hourly_budget_blocks_the_pulse_that_would_exceed_it() -> None:
    core = online_core()
    for n in range(12):  # 12 pulsos de 10 s, um a cada 40 s = 120 s ligados
        start = n * 40
        events = core.handle_command(command(n + 1, duration=10, issued=start), at(start))
        assert EventType.PULSE_STARTED in kinds(events)
        core.tick(at(start + 5))  # o controlador "respira" dentro do limite do watchdog
    blocked = core.handle_command(command(100, duration=10, issued=480), at(480))
    assert rejection(blocked) is Reason.BUDGET_EXHAUSTED
    later = core.handle_command(command(101, duration=10, issued=4000), at(4000))
    assert EventType.PULSE_STARTED in kinds(later)


def test_disconnection_aborts_the_pulse_and_reports_safe_off() -> None:
    core = online_core()
    core.handle_command(command(1, duration=10), at(0))
    events = core.connection_lost(at(3))
    assert kinds(events) == [EventType.PULSE_ABORTED]
    assert events[0].reason is Reason.DISCONNECTED
    snapshot = core.snapshot(at(3))
    assert (snapshot.online, snapshot.state, snapshot.output_on) == (False, State.SAFE_OFF, False)
    assert snapshot.fault is None
    assert rejection(core.handle_command(command(2, issued=4), at(4))) is Reason.DISCONNECTED
    core.connection_restored(at(5))
    assert core.state is State.COOLDOWN  # a pausa continua valendo depois de reconectar
    core.tick(at(40))
    assert core.state is State.IDLE


def test_maintenance_forces_the_output_off_and_blocks_commands() -> None:
    core = online_core()
    core.handle_command(command(1, duration=10), at(0))
    events = core.set_maintenance(True, at(2))
    assert kinds(events) == [EventType.PULSE_ABORTED]
    assert events[0].reason is Reason.MAINTENANCE
    assert core.state is State.MAINTENANCE
    assert not core.output_on
    assert core.set_maintenance(True, at(3)) == []
    assert rejection(core.handle_command(command(2, issued=3), at(3))) is Reason.MAINTENANCE
    assert core.set_maintenance(False, at(4)) == []
    assert core.state is State.COOLDOWN
    core.tick(at(40))
    assert core.state is State.IDLE
    assert core.set_maintenance(False, at(41)) == []  # soltar de novo não muda nada


def test_boots_into_maintenance_when_the_switch_is_already_on() -> None:
    core = ActuatorCore()
    core.set_maintenance(True, at(0))
    core.connection_restored(at(1))
    assert core.state is State.MAINTENANCE
    core.set_maintenance(False, at(2))
    assert core.state is State.IDLE


def test_fault_latches_until_a_local_reset() -> None:
    core = online_core()
    core.handle_command(command(1, duration=10), at(0))
    events = core.inject_fault(Fault.OVERCURRENT, at(2))
    assert kinds(events) == [EventType.PULSE_ABORTED]
    assert events[0].reason is Reason.FAULT
    assert core.state is State.FAULT
    assert core.snapshot(at(2)).fault is Fault.OVERCURRENT
    assert core.inject_fault(Fault.WATCHDOG, at(3)) == []
    assert core.snapshot(at(3)).fault is Fault.OVERCURRENT  # mantém o primeiro código
    assert rejection(core.handle_command(command(2, issued=4), at(4))) is Reason.FAULT
    assert core.reset(at(5)) == []
    assert core.state is State.COOLDOWN
    core.tick(at(40))
    assert core.state is State.IDLE
    assert core.reset(at(41)) == []  # sem falha, nada a fazer


def test_watchdog_cuts_a_pulse_when_the_controller_stalls() -> None:
    core = online_core()
    core.handle_command(command(1, duration=10), at(0))
    events = core.tick(at(20))  # ninguém chamou o núcleo por 20 s (o limite é 5 s)
    assert kinds(events) == [EventType.PULSE_ABORTED]
    assert events[0].reason is Reason.WATCHDOG
    assert events[0].at == BASE + timedelta(seconds=5)
    assert core.state is State.FAULT
    assert core.snapshot(at(20)).fault is Fault.WATCHDOG


def test_a_pulse_that_ended_before_the_stall_is_not_a_fault() -> None:
    core = online_core()
    core.handle_command(command(1, duration=3), at(0))
    events = core.tick(at(20))
    assert kinds(events) == [EventType.PULSE_FINISHED]
    assert core.snapshot(at(20)).fault is None


def test_clock_before_the_minimum_latches_clock_invalid_until_it_is_fixed() -> None:
    core = ActuatorCore()
    wrong = Instant(MONO0, datetime(2020, 1, 1, tzinfo=UTC))
    core.connection_restored(wrong)
    assert core.state is State.FAULT
    assert core.snapshot(wrong).fault is Fault.CLOCK_INVALID
    core.reset(wrong)
    assert core.state is State.FAULT
    core.reset(at(0))
    assert core.state is State.IDLE


def test_failed_self_test_latches_a_fault() -> None:
    core = ActuatorCore()
    core.connection_restored(at(0), self_test_ok=False)
    assert core.state is State.FAULT
    assert core.snapshot(at(0)).fault is Fault.SELF_TEST


def test_monotonic_clock_cannot_go_backwards() -> None:
    core = online_core()
    core.tick(at(10))
    with pytest.raises(ValueError, match="retroceder"):
        core.tick(at(5))


def test_unreadable_message_is_reported_as_an_invalid_command() -> None:
    events = online_core().reject_invalid(at(0))
    assert rejection(events) is Reason.INVALID_COMMAND
    assert events[0].command_id is None


def test_snapshot_reports_the_seconds_used_in_the_last_hour() -> None:
    core = online_core()
    core.handle_command(command(1, duration=5), at(0))
    assert core.snapshot(at(2)).budget_used_s_1h == 2
    core.tick(at(6))
    assert core.snapshot(at(6)).budget_used_s_1h == 5
