"""O tratador de mensagens grava o estado do atuador sem nunca afetar o controle."""

import json
from datetime import UTC, datetime
from typing import Any

import pytest

from pigeondome.adapters.actuator_mqtt import (
    ActuatorMessageHandler,
    ActuatorStateTracker,
    MessageOutcome,
    events_topic,
    state_topic,
)
from pigeondome.adapters.memory_actuation import InMemoryActuatorEventRepository
from pigeondome.adapters.memory_status import InMemoryActuatorStateRepository
from pigeondome.application.ports import ActuatorStateRepository, StorageError
from pigeondome.domain.status import ActuatorStateRecord

NOW = datetime(2026, 10, 24, 21, 0, 5, tzinfo=UTC)
ACTUATOR = "act-sim-01"
UUID = "3f2b8c1e-7a4d-4e5b-9c6a-1d2e3f4a5b6c"


class BrokenStates:
    def save(self, record: ActuatorStateRecord) -> None:
        raise StorageError("banco fora")

    def get(self, actuator_id: str) -> ActuatorStateRecord | None:
        return None


def state_payload(**changes: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "schema_version": 1,
        "device_id": ACTUATOR,
        "online": True,
        "state": "pulsing",
        "output_on": True,
        "last_command_id": UUID,
        "fault": None,
        "budget_used_s_1h": 5,
        "reported_at": "2026-10-24T21:00:00.000Z",
    }
    return {**base, **changes}


def encode(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload).encode()


def make_handler(
    states: ActuatorStateRepository | None,
) -> tuple[ActuatorMessageHandler, ActuatorStateTracker]:
    tracker = ActuatorStateTracker()
    handler = ActuatorMessageHandler(ACTUATOR, tracker, InMemoryActuatorEventRepository(), states)
    return handler, tracker


def test_a_state_message_is_saved_with_the_reception_time() -> None:
    states = InMemoryActuatorStateRepository()
    handler, tracker = make_handler(states)
    outcome = handler.handle(state_topic(ACTUATOR), encode(state_payload()), NOW)
    assert outcome is MessageOutcome.STATE_UPDATED
    assert states.get(ACTUATOR) == ActuatorStateRecord(ACTUATOR, True, "pulsing", True, 5, NOW)
    assert tracker.current().state == "pulsing"


def test_missing_display_fields_are_saved_as_none() -> None:
    states = InMemoryActuatorStateRepository()
    handler, _ = make_handler(states)
    payload = state_payload()
    del payload["output_on"]
    del payload["budget_used_s_1h"]
    handler.handle(state_topic(ACTUATOR), encode(payload), NOW)
    assert states.get(ACTUATOR) == ActuatorStateRecord(ACTUATOR, True, "pulsing", None, None, NOW)


@pytest.mark.parametrize(
    "changes",
    [
        {"budget_used_s_1h": True},
        {"budget_used_s_1h": 99999},
        {"budget_used_s_1h": -1},
        {"budget_used_s_1h": "5"},
        {"budget_used_s_1h": 5.5},
        {"output_on": "yes"},
    ],
)
def test_a_malformed_display_field_never_rejects_the_state(changes: dict[str, Any]) -> None:
    states = InMemoryActuatorStateRepository()
    handler, tracker = make_handler(states)
    outcome = handler.handle(state_topic(ACTUATOR), encode(state_payload(**changes)), NOW)
    assert outcome is MessageOutcome.STATE_UPDATED
    expected = ActuatorStateRecord(
        ACTUATOR,
        True,
        "pulsing",
        None if "output_on" in changes else True,
        None if "budget_used_s_1h" in changes else 5,
        NOW,
    )
    assert states.get(ACTUATOR) == expected
    assert tracker.current().state == "pulsing"


def test_a_database_failure_never_blocks_the_control_path() -> None:
    handler, tracker = make_handler(BrokenStates())
    outcome = handler.handle(state_topic(ACTUATOR), encode(state_payload()), NOW)
    assert outcome is MessageOutcome.STORAGE_ERROR
    current = tracker.current()
    assert (current.online, current.state, current.reported_at) == (True, "pulsing", NOW)


def test_a_rejected_state_is_neither_tracked_nor_saved() -> None:
    states = InMemoryActuatorStateRepository()
    handler, tracker = make_handler(states)
    outcome = handler.handle(state_topic(ACTUATOR), encode(state_payload(state="exploding")), NOW)
    assert outcome is MessageOutcome.REJECTED
    assert states.get(ACTUATOR) is None
    assert tracker.current().state == "unknown"


def test_events_do_not_touch_the_state_table() -> None:
    states = InMemoryActuatorStateRepository()
    handler, _ = make_handler(states)
    event = {
        "schema_version": 1,
        "device_id": ACTUATOR,
        "event": "pulse_started",
        "command_id": UUID,
        "at": "2026-10-24T21:00:00.000Z",
    }
    outcome = handler.handle(events_topic(ACTUATOR), encode(event), NOW)
    assert outcome is MessageOutcome.EVENT_STORED
    assert states.get(ACTUATOR) is None


def test_the_handler_still_works_without_a_state_repository() -> None:
    handler, tracker = make_handler(None)
    outcome = handler.handle(state_topic(ACTUATOR), encode(state_payload()), NOW)
    assert outcome is MessageOutcome.STATE_UPDATED
    assert tracker.current().state == "pulsing"
