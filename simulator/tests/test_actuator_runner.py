"""Runner do atuador: a fiação com o paho-mqtt, testada com um cliente falso (sem broker)."""

import json
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import paho.mqtt.client as mqtt
import pytest

from pigeondome_sim import actuator_runner
from pigeondome_sim.actuator_core import Instant
from pigeondome_sim.actuator_messages import iso_utc
from pigeondome_sim.actuator_runner import ActuatorRunner, ActuatorSettings, main, system_clock
from pigeondome_sim.actuator_service import command_topic, events_topic, state_topic

DEVICE = "act-sim-01"
BASE = datetime(2026, 10, 23, 12, 0, 0, tzinfo=UTC)
CREDENTIAL = "not-a-real-credential"
ENV_NAMES = [
    "MQTT_HOST",
    "MQTT_PORT",
    "MQTT_USER",
    "MQTT_PASSWORD",
    "ACTUATOR_DEVICE_ID",
    "ACTUATOR_TICK_S",
    "ACTUATOR_HEARTBEAT_S",
    "ACTUATOR_STATE_DIR",
]
OK = SimpleNamespace(is_failure=False)
REFUSED = SimpleNamespace(is_failure=True)


class FakeInfo:
    def wait_for_publish(self, timeout: float | None = None) -> None:
        return None


class FakeClient:
    """Só o que o runner usa do paho-mqtt; os callbacks são chamados pelos testes."""

    def __init__(self) -> None:
        self.credentials: tuple[str, str] | None = None
        self.will: tuple[str, bytes, int, bool] | None = None
        self.subscribed: list[tuple[str, int]] = []
        self.published: list[tuple[str, bytes, int, bool]] = []
        self.connect_args: tuple[str, int, int] | None = None
        self.loop_started = False
        self.loop_stopped = False
        self.disconnected = False
        self.on_connect: Any = None
        self.on_disconnect: Any = None
        self.on_message: Any = None

    def username_pw_set(self, user: str, password: str) -> None:
        self.credentials = (user, password)

    def will_set(self, topic: str, payload: bytes, qos: int, retain: bool) -> None:
        self.will = (topic, payload, qos, retain)

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

    def publish(self, topic: str, payload: bytes, qos: int, retain: bool) -> FakeInfo:
        self.published.append((topic, payload, qos, retain))
        return FakeInfo()


class Clock:
    def __init__(self) -> None:
        self.seconds = 0.0

    def __call__(self) -> Instant:
        return Instant(1000.0 + self.seconds, BASE + timedelta(seconds=self.seconds))


class StopAfter:
    """Faz de conta de threading.Event: deixa o laço rodar N passadas e então manda parar."""

    def __init__(self, ticks: int) -> None:
        self._remaining = ticks

    def wait(self, timeout: float | None = None) -> bool:
        if self._remaining == 0:
            return True
        self._remaining -= 1
        return False


def settings(**changes: Any) -> ActuatorSettings:
    values: dict[str, Any] = {
        "host": "127.0.0.1",
        "port": 1883,
        "user": "actuator",
        "password": CREDENTIAL,
        "device_id": DEVICE,
        "tick_s": 0.5,
        "heartbeat_s": 10.0,
    }
    return ActuatorSettings(**{**values, **changes})


def make_runner(**changes: Any) -> tuple[ActuatorRunner, FakeClient, Clock]:
    client, clock = FakeClient(), Clock()
    return ActuatorRunner(settings(**changes), client=client, clock=clock), client, clock


def connect(client: FakeClient) -> None:
    client.on_connect(client, None, {}, OK, None)
    client.published.clear()


def pulse_payload(n: int = 1, seconds: int = 5) -> bytes:
    document = {
        "schema_version": 1,
        "command_id": f"00000000-0000-4000-8000-{n:012d}",
        "device_id": DEVICE,
        "action": "pulse",
        "duration_s": seconds,
        "issued_at": iso_utc(BASE),
        "ttl_s": 10,
    }
    return json.dumps(document).encode()


def deliver(client: FakeClient, payload: bytes) -> None:
    message = SimpleNamespace(topic=command_topic(DEVICE), payload=payload)
    client.on_message(client, None, message)


def decoded(client: FakeClient, topic: str) -> list[dict[str, Any]]:
    return [json.loads(p[1]) for p in client.published if p[0] == topic]


def clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


# --- configuração -----------------------------------------------------------------------


def test_settings_from_env_use_safe_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_env(monkeypatch)
    monkeypatch.setenv("MQTT_PASSWORD", CREDENTIAL)
    loaded = ActuatorSettings.from_env()
    assert (loaded.host, loaded.port, loaded.user) == ("127.0.0.1", 1883, "actuator")
    assert (loaded.device_id, loaded.tick_s, loaded.heartbeat_s) == (DEVICE, 0.5, 10.0)
    assert loaded.state_dir == ".pigeondome-state"
    assert CREDENTIAL not in repr(loaded)


def test_settings_accept_another_state_folder(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_env(monkeypatch)
    monkeypatch.setenv("MQTT_PASSWORD", CREDENTIAL)
    monkeypatch.setenv("ACTUATOR_STATE_DIR", "/var/lib/pigeondome")
    assert ActuatorSettings.from_env().state_dir == "/var/lib/pigeondome"


@pytest.mark.parametrize("name", ["../fora", "a", "MAIÚSCULA", "com espaço", "x" * 33, "a/b"])
def test_settings_reject_a_device_id_that_would_become_a_bad_file_name(
    monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    clear_env(monkeypatch)
    monkeypatch.setenv("MQTT_PASSWORD", CREDENTIAL)
    monkeypatch.setenv("ACTUATOR_DEVICE_ID", name)
    with pytest.raises(ValueError, match="ACTUATOR_DEVICE_ID"):
        ActuatorSettings.from_env()


def test_settings_reject_an_empty_state_folder(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_env(monkeypatch)
    monkeypatch.setenv("MQTT_PASSWORD", CREDENTIAL)
    monkeypatch.setenv("ACTUATOR_STATE_DIR", "  ")
    with pytest.raises(ValueError, match="ACTUATOR_STATE_DIR"):
        ActuatorSettings.from_env()


def test_settings_require_the_password(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_env(monkeypatch)
    with pytest.raises(ValueError, match="MQTT_PASSWORD"):
        ActuatorSettings.from_env()


@pytest.mark.parametrize("tick", ["0", "-1", "3"])
def test_settings_reject_a_tick_that_would_trip_the_watchdog(
    monkeypatch: pytest.MonkeyPatch, tick: str
) -> None:
    clear_env(monkeypatch)
    monkeypatch.setenv("MQTT_PASSWORD", CREDENTIAL)
    monkeypatch.setenv("ACTUATOR_TICK_S", tick)
    with pytest.raises(ValueError, match="ACTUATOR_TICK_S"):
        ActuatorSettings.from_env()


def test_settings_reject_a_non_positive_heartbeat(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_env(monkeypatch)
    monkeypatch.setenv("MQTT_PASSWORD", CREDENTIAL)
    monkeypatch.setenv("ACTUATOR_HEARTBEAT_S", "0")
    with pytest.raises(ValueError, match="ACTUATOR_HEARTBEAT_S"):
        ActuatorSettings.from_env()


# --- fiação com o cliente MQTT ------------------------------------------------------------


def test_runner_configures_credentials_will_and_callbacks() -> None:
    _, client, _ = make_runner()
    assert client.credentials == ("actuator", CREDENTIAL)
    assert client.will is not None
    topic, payload, qos, retain = client.will
    assert (topic, qos, retain) == (state_topic(DEVICE), 1, True)
    last_will = json.loads(payload)
    assert (last_will["online"], last_will["state"]) == (False, "safe_off")
    assert client.on_connect and client.on_disconnect and client.on_message


def test_connecting_subscribes_to_commands_and_publishes_the_retained_state() -> None:
    _, client, _ = make_runner()
    client.on_connect(client, None, {}, OK, None)
    assert client.subscribed == [(command_topic(DEVICE), 1)]
    assert [p[0] for p in client.published] == [state_topic(DEVICE)]
    assert client.published[0][3] is True  # retain
    assert decoded(client, state_topic(DEVICE))[0]["state"] == "idle"


def test_refused_connection_does_nothing() -> None:
    _, client, _ = make_runner()
    client.on_connect(client, None, {}, REFUSED, None)
    assert client.subscribed == []
    assert client.published == []


def test_command_message_starts_a_pulse_and_publishes_events_and_state() -> None:
    _, client, _ = make_runner()
    connect(client)
    deliver(client, pulse_payload())
    events = decoded(client, events_topic(DEVICE))
    assert [e["event"] for e in events] == ["command_accepted", "pulse_started"]
    assert decoded(client, state_topic(DEVICE))[-1]["state"] == "pulsing"


def test_step_publishes_the_end_of_the_pulse_and_heartbeats() -> None:
    runner, client, clock = make_runner()
    connect(client)
    deliver(client, pulse_payload(seconds=5))
    client.published.clear()
    clock.seconds = 6
    runner.step()
    assert [e["event"] for e in decoded(client, events_topic(DEVICE))] == ["pulse_finished"]
    assert decoded(client, state_topic(DEVICE))[-1]["state"] == "cooldown"
    client.published.clear()
    runner.step()
    assert client.published == []  # nada mudou: nada a publicar
    runner.step(heartbeat=True)
    assert len(decoded(client, state_topic(DEVICE))) == 1


def test_disconnection_cuts_the_pulse_and_the_event_is_published_after_reconnecting() -> None:
    _, client, clock = make_runner()
    connect(client)
    deliver(client, pulse_payload(seconds=10))
    client.published.clear()
    clock.seconds = 3
    client.on_disconnect(client, None, None, REFUSED, None)  # conexão perdida
    assert client.published == []
    clock.seconds = 5
    client.on_connect(client, None, {}, OK, None)
    events = decoded(client, events_topic(DEVICE))
    assert [(e["event"], e["reason_code"]) for e in events] == [("pulse_aborted", "disconnected")]
    client.on_disconnect(client, None, None, OK, None)  # desconexão limpa


# --- memória do orçamento: o atuador reinicia ---------------------------------------------


class RebootedClock(Clock):
    """Outro boot: o relógio monotônico recomeça de outro ponto; o de parede segue."""

    def __call__(self) -> Instant:
        instant = super().__call__()
        return Instant(instant.mono_s - 900.0, instant.wall)


def test_a_restarted_runner_remembers_what_the_previous_one_spent(tmp_path: Path) -> None:
    _, first_client, _ = make_runner(state_dir=str(tmp_path))
    connect(first_client)
    deliver(first_client, pulse_payload(seconds=10))
    assert (tmp_path / f"actuator-{DEVICE}.json").exists()

    client = FakeClient()
    second_clock = RebootedClock()
    second_clock.seconds = 3  # o atuador caiu aos 2 s de pulso e voltou 1 s depois
    ActuatorRunner(settings(state_dir=str(tmp_path)), client=client, clock=second_clock)
    client.on_connect(client, None, {}, OK, None)
    state = decoded(client, state_topic(DEVICE))[-1]
    assert state["budget_used_s_1h"] == 10  # os 10 s previstos, não os 2 s que ele ligou
    assert state["state"] == "cooldown"


def test_a_corrupt_memory_file_is_reported_as_a_self_test_fault(tmp_path: Path) -> None:
    (tmp_path / f"actuator-{DEVICE}.json").write_text("{isto nao e json", encoding="utf-8")
    _, client, _ = make_runner(state_dir=str(tmp_path))
    client.on_connect(client, None, {}, OK, None)
    state = decoded(client, state_topic(DEVICE))[-1]
    assert (state["state"], state["fault"]) == ("fault", "self_test")
    assert list(tmp_path.glob("*.corrupt-*"))  # guardado à parte para análise


def test_without_a_state_folder_nothing_is_written(tmp_path: Path) -> None:
    _, client, _ = make_runner()  # state_dir=None: tudo em RAM, como antes
    connect(client)
    deliver(client, pulse_payload())
    assert list(tmp_path.iterdir()) == []


# --- laço principal e encerramento ----------------------------------------------------------


def test_run_connects_loops_and_shuts_down_cleanly() -> None:
    runner, client, _ = make_runner()
    runner.run(StopAfter(0))  # type: ignore[arg-type]
    assert client.connect_args == ("127.0.0.1", 1883, 15)
    assert client.loop_started and client.loop_stopped and client.disconnected
    final = json.loads(client.published[-1][1])
    assert (final["online"], final["state"]) == (False, "safe_off")
    assert client.published[-1][3] is True  # estado final retido


def test_run_ticks_until_stopped_and_cuts_a_running_pulse_on_shutdown() -> None:
    runner, client, _ = make_runner(heartbeat_s=0.0)
    connect(client)
    deliver(client, pulse_payload(seconds=10))
    client.published.clear()
    runner.run(StopAfter(2))  # type: ignore[arg-type]
    names = [e["event"] for e in decoded(client, events_topic(DEVICE))]
    assert names == ["pulse_aborted"]  # o encerramento aborta o pulso em andamento
    assert [p[0] for p in client.published].count(state_topic(DEVICE)) == 3  # 2 passadas + final


def test_main_reports_a_missing_password(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_env(monkeypatch)
    assert main() == 2


def test_main_runs_the_runner_until_it_returns(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_env(monkeypatch)
    monkeypatch.setenv("MQTT_PASSWORD", CREDENTIAL)
    ran: list[bool] = []

    class FakeRunner:
        def __init__(self, loaded: ActuatorSettings) -> None:
            self.loaded = loaded

        def run(self, stop: threading.Event) -> None:
            ran.append(True)

    monkeypatch.setattr(actuator_runner, "ActuatorRunner", FakeRunner)
    monkeypatch.setattr(actuator_runner.signal, "signal", lambda *args: None)
    assert main() == 0
    assert ran == [True]


def test_system_clock_reads_a_monotonic_clock_and_an_aware_utc_wall_clock() -> None:
    first = system_clock()
    second = system_clock()
    assert second.mono_s >= first.mono_s
    assert first.wall.utcoffset() == timedelta(0)


def test_default_client_is_a_real_paho_client_that_accepts_our_configuration() -> None:
    runner = ActuatorRunner(settings())  # sem cliente falso: configura um mqtt.Client de verdade
    assert isinstance(runner._client, mqtt.Client)
