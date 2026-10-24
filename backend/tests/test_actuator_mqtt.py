"""Ponte MQTT do controlador: mensagens do atuador, comando de pulso e a fiação com o paho."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import paho.mqtt.client as mqtt
import pytest
from jsonschema import Draft202012Validator

from pigeondome.adapters.actuator_mqtt import (
    ActuatorMessageHandler,
    ActuatorStateTracker,
    ControllerMqtt,
    MessageOutcome,
    build_pulse_command,
    command_topic,
    events_topic,
    state_topic,
)
from pigeondome.adapters.memory_actuation import InMemoryActuatorEventRepository
from pigeondome.application.controller_service import CommandSendError
from pigeondome.application.ports import StorageError
from pigeondome.config import MqttSettings
from pigeondome.domain.actuation import ActuatorStatus
from pigeondome.domain.actuation_log import ActuatorEventRecord

ACTUATOR = "act-sim-01"
NOW = datetime(2026, 10, 24, 15, 0, 0, tzinfo=UTC)
UUID = "3f2b8c1e-7a4d-4e5b-9c6a-1d2e3f4a5b6c"
CREDENTIAL = "not-a-real-credential"
CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"
OK = SimpleNamespace(is_failure=False)
REFUSED = SimpleNamespace(is_failure=True)


def state_payload(**changes: Any) -> bytes:
    base: dict[str, Any] = {"device_id": ACTUATOR, "online": True, "state": "idle"}
    return json.dumps({**base, **changes}).encode()


def event_payload(**changes: Any) -> bytes:
    base: dict[str, Any] = {
        "device_id": ACTUATOR,
        "event": "pulse_started",
        "command_id": UUID,
        "at": "2026-10-24T14:59:58.000Z",
    }
    return json.dumps({**base, **changes}).encode()


def make_handler() -> tuple[ActuatorMessageHandler, ActuatorStateTracker, Any]:
    tracker = ActuatorStateTracker()
    events = InMemoryActuatorEventRepository()
    return ActuatorMessageHandler(ACTUATOR, tracker, events), tracker, events


def test_the_tracker_starts_offline_until_the_actuator_speaks() -> None:
    assert ActuatorStateTracker().current() == ActuatorStatus(False, "unknown", None)


def test_a_valid_state_updates_the_tracker_with_the_reception_time() -> None:
    handler, tracker, _ = make_handler()
    outcome = handler.handle(state_topic(ACTUATOR), state_payload(), NOW)
    assert outcome is MessageOutcome.STATE_UPDATED
    assert tracker.current() == ActuatorStatus(True, "idle", NOW)


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(b"{not json", id="broken_json"),
        pytest.param(b"[]", id="not_an_object"),
        pytest.param(state_payload(state="armed"), id="unknown_state"),
        pytest.param(state_payload(state=["idle"]), id="unhashable_state"),
        pytest.param(state_payload(online="yes"), id="online_not_boolean"),
        pytest.param(state_payload(device_id="act-outro"), id="other_device"),
        pytest.param(b"x" * 5000, id="too_large"),
    ],
)
def test_odd_state_messages_are_rejected_and_change_nothing(payload: bytes) -> None:
    handler, tracker, _ = make_handler()
    assert handler.handle(state_topic(ACTUATOR), payload, NOW) is MessageOutcome.REJECTED
    assert tracker.current().online is False


def test_events_are_stored_once() -> None:
    handler, _, events = make_handler()
    assert (
        handler.handle(events_topic(ACTUATOR), event_payload(), NOW) is MessageOutcome.EVENT_STORED
    )
    assert (
        handler.handle(events_topic(ACTUATOR), event_payload(), NOW)
        is MessageOutcome.EVENT_DUPLICATE
    )
    found = events.list_between(ACTUATOR, NOW - timedelta(hours=1), NOW + timedelta(hours=1))
    assert found == [
        ActuatorEventRecord(
            datetime(2026, 10, 24, 14, 59, 58, tzinfo=UTC), ACTUATOR, "pulse_started", UUID, None
        )
    ]


def test_rejected_events_carry_their_reason_code_when_present() -> None:
    handler, _, events = make_handler()
    payload = event_payload(event="command_rejected", command_id=None, reason_code="cooldown")
    assert handler.handle(events_topic(ACTUATOR), payload, NOW) is MessageOutcome.EVENT_STORED
    (stored,) = events.list_between(ACTUATOR, NOW - timedelta(hours=1), NOW + timedelta(hours=1))
    assert (stored.command_id, stored.reason_code) == (None, "cooldown")


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(event_payload(event="exploded"), id="unknown_event"),
        pytest.param(event_payload(at="ontem"), id="bad_time"),
        pytest.param(event_payload(at="2026-10-24T14:59:58"), id="naive_time"),
        pytest.param(event_payload(command_id="nope"), id="bad_command_id"),
        pytest.param(event_payload(command_id=7), id="command_id_not_text"),
        pytest.param(event_payload(reason_code=5), id="reason_code_not_text"),
        pytest.param(event_payload(event=None), id="event_missing"),
        pytest.param(event_payload(device_id="act-outro"), id="other_device"),
    ],
)
def test_odd_events_are_rejected(payload: bytes) -> None:
    handler, _, events = make_handler()
    assert handler.handle(events_topic(ACTUATOR), payload, NOW) is MessageOutcome.REJECTED
    assert events.list_between(ACTUATOR, NOW - timedelta(days=1), NOW + timedelta(days=1)) == []


def test_a_storage_failure_never_crashes_the_handler() -> None:
    class Broken:
        def add(self, record: ActuatorEventRecord) -> bool:
            raise StorageError("banco fora")

    handler = ActuatorMessageHandler(ACTUATOR, ActuatorStateTracker(), Broken())  # type: ignore[arg-type]
    outcome = handler.handle(events_topic(ACTUATOR), event_payload(), NOW)
    assert outcome is MessageOutcome.STORAGE_ERROR


def test_other_topics_are_ignored() -> None:
    handler, tracker, _ = make_handler()
    assert handler.handle("pigeondome/v1/outro/actuator/state", state_payload(), NOW) is (
        MessageOutcome.IGNORED
    )
    assert tracker.current().online is False


def test_the_pulse_command_obeys_the_contract() -> None:
    schema = json.loads((CONTRACTS / "command.v1.schema.json").read_text("utf-8"))
    check = Draft202012Validator(schema)
    command = build_pulse_command(ACTUATOR, 5, NOW)
    assert check.is_valid(command)
    assert command["issued_at"] == "2026-10-24T15:00:00.000Z"
    assert (command["action"], command["ttl_s"], command["duration_s"]) == ("pulse", 10, 5)
    assert build_pulse_command(ACTUATOR, 5, NOW)["command_id"] != command["command_id"]
    assert build_pulse_command(ACTUATOR, 5, NOW, command_id=UUID)["command_id"] == UUID


# --- fiação com o cliente MQTT -------------------------------------------------------------


class FakeClient:
    def __init__(self) -> None:
        self.credentials: tuple[str, str] | None = None
        self.subscribed: list[tuple[str, int]] = []
        self.published: list[tuple[str, str, int]] = []
        self.connect_args: tuple[str, int, int] | None = None
        self.connected = True
        self.rc = 0
        self.loop_started = False
        self.loop_stopped = False
        self.disconnected = False
        self.on_connect: Any = None
        self.on_disconnect: Any = None
        self.on_message: Any = None

    def username_pw_set(self, user: str, password: str) -> None:
        self.credentials = (user, password)

    def reconnect_delay_set(self, min_delay: int, max_delay: int) -> None:
        return None

    def connect_async(self, host: str, port: int, keepalive: int) -> None:
        self.connect_args = (host, port, keepalive)

    def loop_start(self) -> None:
        self.loop_started = True

    def loop_stop(self) -> None:
        self.loop_stopped = True

    def disconnect(self) -> None:
        self.disconnected = True

    def subscribe(self, topic: str, qos: int) -> None:
        self.subscribed.append((topic, qos))

    def is_connected(self) -> bool:
        return self.connected

    def publish(self, topic: str, payload: str, qos: int) -> SimpleNamespace:
        self.published.append((topic, payload, qos))
        return SimpleNamespace(rc=self.rc)


def make_bridge() -> tuple[ControllerMqtt, FakeClient, ActuatorStateTracker]:
    handler, tracker, _ = make_handler()
    client = FakeClient()
    settings = MqttSettings("127.0.0.1", 1883, "backend", CREDENTIAL)
    return (
        ControllerMqtt(settings, ACTUATOR, handler, client=client, clock=lambda: NOW),
        client,
        tracker,
    )


def test_the_bridge_authenticates_and_subscribes_on_every_connection() -> None:
    _, client, _ = make_bridge()
    assert client.credentials == ("backend", CREDENTIAL)
    client.on_connect(client, None, {}, OK, None)
    assert client.subscribed == [(state_topic(ACTUATOR), 1), (events_topic(ACTUATOR), 1)]
    client.subscribed.clear()
    client.on_connect(client, None, {}, REFUSED, None)
    assert client.subscribed == []


def test_incoming_messages_reach_the_handler_with_the_reception_time() -> None:
    _, client, tracker = make_bridge()
    message = SimpleNamespace(topic=state_topic(ACTUATOR), payload=state_payload(state="cooldown"))
    client.on_message(client, None, message)
    assert tracker.current() == ActuatorStatus(True, "cooldown", NOW)


def test_send_pulse_publishes_a_valid_command_and_returns_its_id() -> None:
    bridge, client, _ = make_bridge()
    command_id = bridge.send_pulse(ACTUATOR, 5, NOW)
    ((topic, payload, qos),) = client.published
    assert (topic, qos) == (command_topic(ACTUATOR), 1)
    assert json.loads(payload)["command_id"] == command_id


def test_send_pulse_fails_loudly_without_a_connection_or_on_a_publish_error() -> None:
    bridge, client, _ = make_bridge()
    client.connected = False
    with pytest.raises(CommandSendError):
        bridge.send_pulse(ACTUATOR, 5, NOW)
    client.connected = True
    client.rc = 4
    with pytest.raises(CommandSendError):
        bridge.send_pulse(ACTUATOR, 5, NOW)
    assert client.published != []  # tentou publicar, mas o broker recusou


def test_start_and_stop_drive_the_client_loop() -> None:
    bridge, client, _ = make_bridge()
    bridge.start()
    assert client.connect_args == ("127.0.0.1", 1883, 15)
    assert client.loop_started
    bridge.stop()
    assert client.disconnected and client.loop_stopped
    client.on_disconnect(client, None, None, REFUSED, None)
    client.on_disconnect(client, None, None, OK, None)


def test_without_a_fake_the_bridge_configures_a_real_paho_client() -> None:
    handler, _, _ = make_handler()
    settings = MqttSettings("127.0.0.1", 1883, "backend", CREDENTIAL)
    bridge = ControllerMqtt(settings, ACTUATOR, handler)
    assert isinstance(bridge._client, mqtt.Client)
    # o relógio padrão também precisa funcionar (uma mensagem de outro tópico é ignorada)
    bridge._on_message(None, None, SimpleNamespace(topic="outro/topico", payload=b"{}"))
