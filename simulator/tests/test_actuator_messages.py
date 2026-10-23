"""Mensagens do atuador: o núcleo e os contratos JSON precisam concordar."""

import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from pigeondome_sim.actuator_core import (
    Action,
    ActuatorCore,
    Command,
    EventType,
    Fault,
    Instant,
    Limits,
    Reason,
    State,
)
from pigeondome_sim.actuator_messages import (
    command_from_message,
    event_message,
    iso_utc,
    state_message,
)

CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"
BASE = datetime(2026, 10, 23, 12, 0, 0, tzinfo=UTC)
UUID = "3f2b8c1e-7a4d-4e5b-9c6a-1d2e3f4a5b6c"


def load(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((CONTRACTS / f"{name}.schema.json").read_text("utf-8"))
    return data


def at(seconds: float) -> Instant:
    return Instant(mono_s=1000.0 + seconds, wall=BASE + timedelta(seconds=seconds))


def command(n: int, *, action: Action = Action.PULSE, issued: float = 0.0) -> Command:
    return Command(
        command_id=f"00000000-0000-4000-8000-{n:012d}",
        action=action,
        issued_at=BASE + timedelta(seconds=issued),
        ttl_s=10,
        duration_s=5 if action is Action.PULSE else None,
    )


def test_iso_utc_uses_milliseconds_and_the_z_suffix() -> None:
    moment = datetime(2026, 10, 23, 12, 0, 0, 123000, tzinfo=UTC)
    assert iso_utc(moment) == "2026-10-23T12:00:00.123Z"


def test_iso_utc_converts_other_time_zones() -> None:
    local = datetime(2026, 10, 23, 9, 0, 0, tzinfo=timezone(timedelta(hours=-3)))
    assert iso_utc(local) == "2026-10-23T12:00:00.000Z"


def test_valid_command_messages_become_core_commands() -> None:
    check = Draft202012Validator(load("command.v1"))
    base = {
        "schema_version": 1,
        "command_id": UUID,
        "device_id": "act-sim-01",
        "issued_at": "2026-10-23T12:00:00.000Z",
        "ttl_s": 10,
    }
    pulse = {**base, "action": "pulse", "duration_s": 5}
    stop = {**base, "action": "stop"}
    assert check.is_valid(pulse)
    assert check.is_valid(stop)
    parsed = command_from_message(pulse)
    assert (parsed.action, parsed.duration_s, parsed.ttl_s) == (Action.PULSE, 5, 10)
    assert parsed.issued_at == BASE
    assert command_from_message(stop).duration_s is None


def test_a_session_produces_messages_that_match_the_contracts() -> None:
    state_check = Draft202012Validator(load("actuator-state.v1"))
    event_check = Draft202012Validator(load("actuator-event.v1"))
    core = ActuatorCore()
    script = [
        (0, lambda: core.connection_restored(at(0))),
        (0, lambda: core.handle_command(command(1), at(0))),
        (1, lambda: core.handle_command(command(2, issued=1), at(1))),
        (2, lambda: core.handle_command(command(3, action=Action.STOP, issued=2), at(2))),
        (3, lambda: core.inject_fault(Fault.OVERCURRENT, at(3))),
        (4, lambda: core.connection_lost(at(4))),
    ]
    for seconds, step in script:
        events = step()
        snapshot = core.snapshot(at(seconds))
        assert state_check.is_valid(state_message("act-sim-01", snapshot, at(seconds).wall))
        for event in events:
            assert event_check.is_valid(event_message("act-sim-01", event)), event


def test_core_enums_and_limits_match_the_contracts() -> None:
    command_schema = load("command.v1")["properties"]
    state_schema = load("actuator-state.v1")["properties"]
    event_schema = load("actuator-event.v1")["properties"]
    limits = Limits()
    assert command_schema["duration_s"]["maximum"] == limits.max_pulse_s
    assert command_schema["ttl_s"]["maximum"] == limits.max_ttl_s
    assert state_schema["budget_used_s_1h"]["maximum"] == int(limits.budget_window_s)
    assert {a.value for a in Action} == set(command_schema["action"]["enum"])
    assert {s.value for s in State} == set(state_schema["state"]["enum"])
    assert {f.value for f in Fault} == set(state_schema["fault"]["enum"]) - {None}
    assert {e.value for e in EventType} == set(event_schema["event"]["enum"])
    assert {r.value for r in Reason} == set(event_schema["reason_code"]["enum"])
