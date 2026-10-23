"""Contratos de atuação (comando, estado e evento): validade e regras de segurança."""

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"
NAMES = ["command.v1", "actuator-state.v1", "actuator-event.v1"]
UUID = "3f2b8c1e-7a4d-4e5b-9c6a-1d2e3f4a5b6c"
NOW = "2026-10-23T02:10:00Z"


def load(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((CONTRACTS / f"{name}.schema.json").read_text("utf-8"))
    return data


def validator(name: str) -> Draft202012Validator:
    return Draft202012Validator(load(name))


def without(document: dict[str, Any], *keys: str) -> dict[str, Any]:
    return {key: value for key, value in document.items() if key not in keys}


def pulse(**changes: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "schema_version": 1,
        "command_id": UUID,
        "device_id": "act-sim-01",
        "action": "pulse",
        "duration_s": 5,
        "issued_at": NOW,
        "ttl_s": 10,
    }
    return {**base, **changes}


def state(**changes: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "schema_version": 1,
        "device_id": "act-sim-01",
        "online": True,
        "state": "idle",
        "output_on": False,
        "last_command_id": None,
        "fault": None,
        "budget_used_s_1h": 0,
        "reported_at": NOW,
    }
    return {**base, **changes}


def event(**changes: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "schema_version": 1,
        "device_id": "act-sim-01",
        "event": "pulse_started",
        "command_id": UUID,
        "at": NOW,
    }
    return {**base, **changes}


@pytest.mark.parametrize("name", NAMES)
def test_schemas_are_valid_json_schema(name: str) -> None:
    Draft202012Validator.check_schema(load(name))


def test_device_id_pattern_matches_the_detection_contract() -> None:
    expected = load("detection.v1")["properties"]["device_id"]["pattern"]
    for name in NAMES:
        assert load(name)["properties"]["device_id"]["pattern"] == expected


# --- comando ---------------------------------------------------------------------------


def test_valid_commands_are_accepted() -> None:
    check = validator("command.v1")
    assert check.is_valid(pulse())
    assert check.is_valid(without(pulse(action="stop"), "duration_s"))
    reason = {"trigger": "detection", "pigeon_count": 4}
    assert check.is_valid(pulse(duration_s=10, ttl_s=30, reason=reason))


@pytest.mark.parametrize(
    "document",
    [
        pytest.param(pulse(duration_s=0), id="duration_zero"),
        pytest.param(pulse(duration_s=11), id="duration_above_limit"),
        pytest.param(pulse(ttl_s=0), id="ttl_zero"),
        pytest.param(pulse(ttl_s=31), id="ttl_above_limit"),
        pytest.param(pulse(action="set_voltage"), id="unknown_action"),
        pytest.param(pulse(voltage=48), id="extra_field_voltage"),
        pytest.param(pulse(issued_at="2026-10-23T02:10:00-03:00"), id="non_utc_time"),
        pytest.param(pulse(command_id="not-a-uuid"), id="bad_uuid"),
        pytest.param(pulse(device_id="BAD_ID"), id="bad_device_id"),
        pytest.param(pulse(schema_version=2), id="wrong_version"),
        pytest.param(without(pulse(), "duration_s"), id="pulse_without_duration"),
        pytest.param(pulse(action="stop"), id="stop_with_duration"),
    ],
)
def test_unsafe_or_malformed_commands_are_rejected(document: dict[str, Any]) -> None:
    assert not validator("command.v1").is_valid(document)


# --- estado ----------------------------------------------------------------------------


def test_valid_states_are_accepted() -> None:
    check = validator("actuator-state.v1")
    assert check.is_valid(state())
    assert check.is_valid(state(state="pulsing", output_on=True, last_command_id=UUID))
    assert check.is_valid(state(state="fault", fault="watchdog"))
    assert check.is_valid(state(online=False, state="safe_off"))


@pytest.mark.parametrize(
    "document",
    [
        pytest.param(state(output_on=True), id="output_on_while_idle"),
        pytest.param(state(state="cooldown", output_on=True), id="output_on_while_cooldown"),
        pytest.param(state(state="fault"), id="fault_state_without_code"),
        pytest.param(state(fault="watchdog"), id="code_without_fault_state"),
        pytest.param(state(online=False, state="pulsing", output_on=True), id="offline_but_on"),
        pytest.param(state(online=False), id="offline_but_not_safe_off"),
        pytest.param(state(state="armed"), id="unknown_state"),
        pytest.param(state(budget_used_s_1h=-1), id="budget_negative"),
        pytest.param(state(budget_used_s_1h=3601), id="budget_above_one_hour"),
    ],
)
def test_unsafe_states_are_rejected(document: dict[str, Any]) -> None:
    assert not validator("actuator-state.v1").is_valid(document)


# --- evento ----------------------------------------------------------------------------


def test_valid_events_are_accepted() -> None:
    check = validator("actuator-event.v1")
    assert check.is_valid(event())
    assert check.is_valid(event(event="command_accepted"))
    assert check.is_valid(event(event="command_rejected", reason_code="expired"))
    assert check.is_valid(event(event="pulse_aborted", reason_code="disconnected"))
    assert check.is_valid(
        event(event="command_rejected", command_id=None, reason_code="invalid_command")
    )


@pytest.mark.parametrize(
    "document",
    [
        pytest.param(event(event="command_rejected"), id="rejected_without_reason"),
        pytest.param(event(reason_code="busy"), id="started_with_reason"),
        pytest.param(event(event="command_rejected", reason_code="whatever"), id="unknown_reason"),
        pytest.param(without(event(), "at"), id="missing_timestamp"),
    ],
)
def test_malformed_events_are_rejected(document: dict[str, Any]) -> None:
    assert not validator("actuator-event.v1").is_valid(document)
