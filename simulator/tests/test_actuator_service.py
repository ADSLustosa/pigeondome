"""Serviço do atuador: mensagens MQTT entram, publicações saem; nada de rede."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from pigeondome_sim.actuator_core import Action, Fault, Instant
from pigeondome_sim.actuator_messages import iso_utc
from pigeondome_sim.actuator_service import (
    ActuatorService,
    Publication,
    command_topic,
    events_topic,
    parse_command,
    state_topic,
)

DEVICE = "act-sim-01"
BASE = datetime(2026, 10, 23, 12, 0, 0, tzinfo=UTC)
CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"


def schema(name: str) -> Draft202012Validator:
    return Draft202012Validator(json.loads((CONTRACTS / f"{name}.schema.json").read_text("utf-8")))


COMMAND_CHECK = schema("command.v1")
STATE_CHECK = schema("actuator-state.v1")
EVENT_CHECK = schema("actuator-event.v1")


def at(seconds: float) -> Instant:
    return Instant(mono_s=1000.0 + seconds, wall=BASE + timedelta(seconds=seconds))


def pulse_doc(n: int = 1, **changes: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "schema_version": 1,
        "command_id": f"00000000-0000-4000-8000-{n:012d}",
        "device_id": DEVICE,
        "action": "pulse",
        "duration_s": 5,
        "issued_at": iso_utc(BASE),
        "ttl_s": 10,
    }
    return {**base, **changes}


def without_duration(document: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in document.items() if key != "duration_s"}


def send(
    service: ActuatorService, message: dict[str, Any] | bytes, seconds: float
) -> list[Publication]:
    payload = message if isinstance(message, bytes) else json.dumps(message).encode()
    return service.on_message(command_topic(DEVICE), payload, at(seconds))


def online_service() -> ActuatorService:
    service = ActuatorService(DEVICE)
    service.on_connected(at(0))
    return service


def decode(publication: Publication) -> dict[str, Any]:
    message: dict[str, Any] = json.loads(publication.payload)
    return message


def events_of(publications: list[Publication]) -> list[dict[str, Any]]:
    found = [decode(p) for p in publications if p.topic == events_topic(DEVICE)]
    for event in found:
        assert EVENT_CHECK.is_valid(event), event
    return found


def states_of(publications: list[Publication]) -> list[dict[str, Any]]:
    found = [decode(p) for p in publications if p.topic == state_topic(DEVICE)]
    for state in found:
        assert STATE_CHECK.is_valid(state), state
    return found


def names(publications: list[Publication]) -> list[str]:
    return [event["event"] for event in events_of(publications)]


def test_connecting_publishes_a_retained_idle_state() -> None:
    published = ActuatorService(DEVICE).on_connected(at(0))
    assert len(published) == 1
    assert (published[0].topic, published[0].qos, published[0].retain) == (
        state_topic(DEVICE),
        1,
        True,
    )
    state = states_of(published)[0]
    assert (state["online"], state["state"], state["output_on"]) == (True, "idle", False)


def test_accepted_pulse_publishes_events_and_the_new_state() -> None:
    service = online_service()
    published = send(service, pulse_doc(1), 0)
    assert names(published) == ["command_accepted", "pulse_started"]
    (state,) = states_of(published)
    assert (state["state"], state["output_on"]) == ("pulsing", True)
    assert state["last_command_id"] == pulse_doc(1)["command_id"]


def test_state_is_only_republished_when_it_changes_or_on_heartbeat() -> None:
    service = online_service()
    send(service, pulse_doc(1), 0)
    assert service.tick(at(1)) == []
    assert len(states_of(service.tick(at(2), heartbeat=True))) == 1
    published = service.tick(at(6))
    assert names(published) == ["pulse_finished"]
    assert states_of(published)[0]["state"] == "cooldown"


def test_messages_on_other_topics_are_ignored() -> None:
    service = online_service()
    payload = json.dumps(pulse_doc(1)).encode()
    assert service.on_message("pigeondome/v1/outro/commands", payload, at(0)) == []
    assert service.on_message(state_topic(DEVICE), payload, at(0)) == []


@pytest.mark.parametrize(
    "payload",
    [b"{not json", b"[]", b"123", b'"stop"', b"\xff\xfe\xfd"],
    ids=["broken_json", "list", "number", "string", "not_utf8"],
)
def test_unreadable_messages_are_rejected_with_an_event(payload: bytes) -> None:
    service = online_service()
    (event,) = events_of(send(service, payload, 0))
    assert event["event"] == "command_rejected"
    assert event["reason_code"] == "invalid_command"
    assert event["command_id"] is None


def test_command_with_an_extra_field_is_rejected_and_keeps_its_id() -> None:
    service = online_service()
    document = pulse_doc(7, voltage=48)
    published = send(service, document, 0)
    (event,) = events_of(published)
    assert event["reason_code"] == "invalid_command"
    assert event["command_id"] == document["command_id"]
    assert states_of(published) == []  # nada mudou: a saída continua desligada


def test_stop_with_garbage_still_stops_the_output() -> None:
    service = online_service()
    send(service, pulse_doc(1, duration_s=10), 0)
    published = send(service, b'{"action": "stop", "ttl_s": "banana"}', 2)
    assert names(published) == ["command_accepted", "pulse_aborted"]
    assert events_of(published)[1]["reason_code"] == "stop_command"
    (state,) = states_of(published)
    assert (state["state"], state["output_on"]) == ("cooldown", False)


def test_events_while_offline_are_delivered_after_reconnecting() -> None:
    service = online_service()
    send(service, pulse_doc(1, duration_s=10), 0)
    assert service.on_disconnected(at(3)) == []
    assert service.tick(at(4)) == []
    published = service.on_connected(at(5))
    (event,) = events_of(published)
    assert (event["event"], event["reason_code"]) == ("pulse_aborted", "disconnected")
    (state,) = states_of(published)
    assert (state["online"], state["state"]) == (True, "cooldown")


def test_will_message_declares_the_actuator_offline_and_safe() -> None:
    will = ActuatorService(DEVICE).will(at(0))
    assert (will.topic, will.qos, will.retain) == (state_topic(DEVICE), 1, True)
    (state,) = states_of([will])
    assert (state["online"], state["state"], state["output_on"]) == (False, "safe_off", False)


def test_local_maintenance_switch_is_published() -> None:
    service = online_service()
    (state,) = states_of(service.set_maintenance(True, at(1)))
    assert state["state"] == "maintenance"


def test_local_fault_and_reset_are_published() -> None:
    service = online_service()
    published = states_of(service.inject_fault(Fault.OVERCURRENT, at(1)))
    assert [(s["state"], s["fault"]) for s in published] == [("fault", "overcurrent")]
    published = states_of(service.reset(at(2)))
    assert [(s["state"], s["fault"]) for s in published] == [("idle", None)]


def test_parse_command_builds_a_command_from_a_valid_message() -> None:
    command = parse_command(json.dumps(pulse_doc(3)).encode(), DEVICE)
    assert command is not None
    assert (command.action, command.duration_s, command.ttl_s) == (Action.PULSE, 5, 10)
    assert command.issued_at == BASE
    assert command.command_id == pulse_doc(3)["command_id"]


ALIGNMENT = [
    pytest.param(pulse_doc(), id="valid_pulse"),
    pytest.param(pulse_doc(reason={"trigger": "detection", "pigeon_count": 4}), id="valid_reason"),
    pytest.param(pulse_doc(duration_s=10, ttl_s=30), id="valid_at_the_limits"),
    pytest.param(without_duration(pulse_doc(action="stop")), id="valid_stop"),
    pytest.param(pulse_doc(action="stop"), id="stop_with_duration_is_still_a_stop"),
    pytest.param(pulse_doc(duration_s=0), id="duration_zero"),
    pytest.param(pulse_doc(duration_s=11), id="duration_above_limit"),
    pytest.param(pulse_doc(ttl_s=0), id="ttl_zero"),
    pytest.param(pulse_doc(ttl_s=31), id="ttl_above_limit"),
    pytest.param(pulse_doc(action="set_voltage"), id="unknown_action"),
    pytest.param(pulse_doc(voltage=48), id="extra_field_voltage"),
    pytest.param(pulse_doc(issued_at="2026-10-23T12:00:00-03:00"), id="non_utc_time"),
    pytest.param(pulse_doc(command_id="not-a-uuid"), id="bad_uuid"),
    pytest.param(pulse_doc(device_id="BAD_ID"), id="bad_device_id"),
    pytest.param(pulse_doc(schema_version=2), id="wrong_version"),
    pytest.param(without_duration(pulse_doc()), id="pulse_without_duration"),
    pytest.param(pulse_doc(ttl_s=True), id="boolean_ttl"),
    pytest.param(pulse_doc(duration_s=5.5), id="fractional_duration"),
    pytest.param(pulse_doc(reason={"trigger": "hack"}), id="reason_unknown_trigger"),
    pytest.param(pulse_doc(reason={"trigger": "test", "x": 1}), id="reason_extra_key"),
    pytest.param(pulse_doc(reason=None), id="reason_null"),
    pytest.param(pulse_doc(reason={"trigger": []}), id="reason_unhashable_trigger"),
]


@pytest.mark.parametrize("document", ALIGNMENT)
def test_parser_and_the_contract_agree(document: dict[str, Any]) -> None:
    """A pilha inteira só aceita o que o contrato aceita (stop é a exceção deliberada)."""
    expected = COMMAND_CHECK.is_valid(document) or document.get("action") == "stop"
    accepted = "command_accepted" in names(send(online_service(), document, 0))
    assert accepted == expected


def test_clean_shutdown_aborts_the_pulse_and_publishes_the_final_offline_state() -> None:
    service = online_service()
    send(service, pulse_doc(1, duration_s=10), 0)
    published = service.shutdown(at(3))
    (event,) = events_of(published)
    assert (event["event"], event["reason_code"]) == ("pulse_aborted", "disconnected")
    (state,) = states_of(published)
    assert (state["online"], state["state"], state["output_on"]) == (False, "safe_off", False)
    assert published[-1].retain
    assert service.tick(at(4)) == []  # depois do encerramento nada mais é publicado


def test_impossible_date_that_matches_the_text_pattern_is_rejected() -> None:
    service = online_service()
    document = pulse_doc(1, issued_at="2026-13-45T12:00:00Z")
    (event,) = events_of(send(service, document, 0))
    assert event["reason_code"] == "invalid_command"
