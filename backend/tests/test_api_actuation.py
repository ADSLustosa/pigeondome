"""API de atuação: estado do atuador e do controlador, trilha e a chave geral (só liga)."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from pigeondome.adapters.api.actuation_routes import ActuationPorts, utc_now
from pigeondome.adapters.api.app import create_app
from pigeondome.adapters.memory import InMemoryDetectionRepository
from pigeondome.adapters.memory_actuation import (
    InMemoryActuatorEventRepository,
    InMemoryControllerFlags,
    InMemoryDecisionRepository,
)
from pigeondome.adapters.memory_status import (
    InMemoryActuatorStateRepository,
    InMemoryControllerStatusRepository,
)
from pigeondome.application.ports import StorageError
from pigeondome.application.status_use_cases import ListActuatorEvents, ListDecisions
from pigeondome.domain.actuation import Arm, Mode, Reason, Verdict
from pigeondome.domain.actuation_log import ActuatorEventRecord, DecisionRecord
from pigeondome.domain.status import ActuatorStateRecord, ControllerStatusRecord

NOW = datetime(2026, 10, 24, 22, 0, 0, tzinfo=UTC)
CAMERA = "cam-sim-01"
ACTUATOR = "act-sim-01"
UUID = "3f2b8c1e-7a4d-4e5b-9c6a-1d2e3f4a5b6c"
ORIGIN = "http://localhost:5173"
CONFIRM = {"X-Pigeondome-Action": "kill-switch-on"}
STATUS = f"/api/v1/actuators/{ACTUATOR}/status"
CONTROLLER = "/api/v1/controller"
DECISIONS = f"/api/v1/actuators/{ACTUATOR}/decisions"
EVENTS = f"/api/v1/actuators/{ACTUATOR}/events"
KILL_SWITCH = "/api/v1/controller/kill-switch"
PREFLIGHT = {
    "Origin": ORIGIN,
    "Access-Control-Request-Method": "POST",
    "Access-Control-Request-Headers": "X-Pigeondome-Action",
}


def ago(seconds: float) -> datetime:
    return NOW - timedelta(seconds=seconds)


def actuator_state(seconds_ago: float, **changes: Any) -> ActuatorStateRecord:
    base = ActuatorStateRecord(ACTUATOR, True, "idle", False, 5, ago(seconds_ago))
    return replace(base, **changes)


def controller_status(seconds_ago: float, **changes: Any) -> ControllerStatusRecord:
    base = ControllerStatusRecord(Mode.LIVE, CAMERA, ACTUATOR, ago(3600), ago(seconds_ago))
    return replace(base, **changes)


def decision(seconds_ago: float, **changes: Any) -> DecisionRecord:
    base = DecisionRecord(
        decided_at=ago(seconds_ago),
        camera_id=CAMERA,
        actuator_id=ACTUATOR,
        mode=Mode.LIVE,
        verdict=Verdict.PULSE,
        reason=Reason.EVIDENCE_CONFIRMED,
        detail="",
        arm=None,
        duration_s=5,
        command_id=UUID,
        readings=4,
        detections=4,
        mean_confidence=0.9,
        triggered=True,
    )
    return replace(base, **changes)


def make_event(seconds_ago: float, **changes: Any) -> ActuatorEventRecord:
    base = ActuatorEventRecord(ago(seconds_ago), ACTUATOR, "pulse_started", UUID, None)
    return replace(base, **changes)


class World:
    """Tudo em memória, com o relógio da API parado em NOW."""

    def __init__(self) -> None:
        self.actuators = InMemoryActuatorStateRepository()
        self.controller = InMemoryControllerStatusRepository()
        self.decisions = InMemoryDecisionRepository()
        self.events = InMemoryActuatorEventRepository()
        self.flags = InMemoryControllerFlags()

    def client(self, origins: tuple[str, ...] = ()) -> TestClient:
        ports = ActuationPorts(
            self.actuators, self.controller, self.decisions, self.events, self.flags
        )
        app = create_app(InMemoryDetectionRepository(), origins, ports, clock=lambda: NOW)
        return TestClient(app)


class BrokenFlags(InMemoryControllerFlags):
    def kill_switch(self) -> bool:
        raise StorageError("banco fora")

    def set_kill_switch(self, enabled: bool, now: datetime) -> None:
        raise StorageError("banco fora")


# --- estado do atuador --------------------------------------------------------------------


def test_an_actuator_never_seen_is_404() -> None:
    response = World().client().get(STATUS)
    assert response.status_code == 404
    assert response.json()["type"] == "urn:pigeondome:erro:atuador-desconhecido"


def test_a_fresh_actuator_state_is_returned_with_its_age() -> None:
    world = World()
    world.actuators.save(actuator_state(4))
    assert world.client().get(STATUS).json() == {
        "actuator_id": ACTUATOR,
        "online": True,
        "state": "idle",
        "output_on": False,
        "budget_used_s_1h": 5,
        "received_at": "2026-10-24T21:59:56Z",
        "age_s": 4.0,
        "stale": False,
    }


@pytest.mark.parametrize(("seconds", "stale"), [(0, False), (30, False), (30.5, True), (600, True)])
def test_an_online_actuator_goes_stale_after_thirty_seconds(seconds: float, stale: bool) -> None:
    world = World()
    world.actuators.save(actuator_state(seconds))
    assert world.client().get(STATUS).json()["stale"] is stale


def test_an_offline_actuator_is_a_fact_not_stale_data() -> None:
    world = World()
    world.actuators.save(actuator_state(600, online=False, state="safe_off"))
    body = world.client().get(STATUS).json()
    assert (body["online"], body["state"], body["stale"], body["age_s"]) == (
        False,
        "safe_off",
        False,
        600.0,
    )


def test_unreported_display_fields_come_back_as_null() -> None:
    world = World()
    world.actuators.save(actuator_state(1, output_on=None, budget_used_s_1h=None))
    body = world.client().get(STATUS).json()
    assert body["output_on"] is None
    assert body["budget_used_s_1h"] is None


def test_a_state_from_the_future_has_zero_age() -> None:
    world = World()
    world.actuators.save(actuator_state(-5))
    body = world.client().get(STATUS).json()
    assert (body["age_s"], body["stale"]) == (0.0, False)


def test_an_invalid_actuator_id_is_rejected() -> None:
    response = World().client().get("/api/v1/actuators/ACT/status")
    assert response.status_code == 422
    assert response.json()["type"] == "urn:pigeondome:erro:parametros-invalidos"


# --- estado do controlador ----------------------------------------------------------------


def test_a_controller_that_never_ran() -> None:
    assert World().client().get(CONTROLLER).json() == {
        "kill_switch": False,
        "running": False,
        "mode": None,
        "camera_id": None,
        "actuator_id": None,
        "started_at": None,
        "heartbeat_at": None,
        "age_s": None,
    }


def test_a_running_controller_reports_its_mode_and_heartbeat_age() -> None:
    world = World()
    world.controller.save(controller_status(3))
    body = world.client().get(CONTROLLER).json()
    assert (body["running"], body["mode"], body["age_s"]) == (True, "live", 3.0)
    assert body["started_at"] == "2026-10-24T21:00:00Z"
    assert (body["camera_id"], body["actuator_id"]) == (CAMERA, ACTUATOR)


@pytest.mark.parametrize(("seconds", "running"), [(15, True), (15.5, False)])
def test_the_controller_stops_running_after_fifteen_seconds(seconds: float, running: bool) -> None:
    world = World()
    world.controller.save(controller_status(seconds))
    assert world.client().get(CONTROLLER).json()["running"] is running


def test_a_stopped_controller_keeps_its_last_known_data() -> None:
    world = World()
    world.controller.save(controller_status(120))
    body = world.client().get(CONTROLLER).json()
    assert (body["running"], body["mode"], body["age_s"]) == (False, "live", 120.0)
    assert body["heartbeat_at"] == "2026-10-24T21:58:00Z"


def test_the_kill_switch_state_is_reported() -> None:
    world = World()
    world.flags.set_kill_switch(True, NOW)
    assert world.client().get(CONTROLLER).json()["kill_switch"] is True


# --- decisões -----------------------------------------------------------------------------


def test_decisions_default_to_the_last_24_hours() -> None:
    assert World().client().get(DECISIONS).json() == {
        "actuator_id": ACTUATOR,
        "start": "2026-10-23T22:00:00Z",
        "end": "2026-10-24T22:00:00Z",
        "limit": 100,
        "truncated": False,
        "decisions": [],
    }


def test_decisions_come_newest_first() -> None:
    world = World()
    for seconds in (300, 100, 200):
        world.decisions.add(decision(seconds))
    found = world.client().get(DECISIONS).json()["decisions"]
    assert [d["decided_at"] for d in found] == [
        "2026-10-24T21:58:20Z",
        "2026-10-24T21:56:40Z",
        "2026-10-24T21:55:00Z",
    ]


def test_a_decision_is_serialized_with_every_field() -> None:
    world = World()
    world.decisions.add(decision(10, mode=Mode.EXPERIMENT, arm=Arm.TREATMENT, detail="x"))
    (found,) = world.client().get(DECISIONS).json()["decisions"]
    assert found == {
        "decided_at": "2026-10-24T21:59:50Z",
        "camera_id": CAMERA,
        "mode": "experiment",
        "verdict": "pulse",
        "reason": "evidence_confirmed",
        "detail": "x",
        "arm": "treatment",
        "duration_s": 5,
        "command_id": UUID,
        "readings": 4,
        "detections": 4,
        "mean_confidence": 0.9,
        "triggered": True,
    }


def test_the_decision_limit_keeps_the_newest_and_flags_truncation() -> None:
    world = World()
    for seconds in (50, 40, 30, 20, 10):
        world.decisions.add(decision(seconds))
    client = world.client()
    body = client.get(DECISIONS, params={"limit": 2}).json()
    assert [d["decided_at"] for d in body["decisions"]] == [
        "2026-10-24T21:59:50Z",
        "2026-10-24T21:59:40Z",
    ]
    assert (body["limit"], body["truncated"]) == (2, True)
    complete = client.get(DECISIONS, params={"limit": 5}).json()
    assert (len(complete["decisions"]), complete["truncated"]) == (5, False)


def test_the_decision_window_is_half_open() -> None:
    world = World()
    for seconds in (50, 40, 30, 20, 10):
        world.decisions.add(decision(seconds))
    params = {"start": "2026-10-24T21:59:30Z", "end": "2026-10-24T21:59:50Z"}
    found = world.client().get(DECISIONS, params=params).json()["decisions"]
    assert [d["decided_at"] for d in found] == ["2026-10-24T21:59:40Z", "2026-10-24T21:59:30Z"]


def test_decisions_of_other_actuators_are_not_returned() -> None:
    world = World()
    world.decisions.add(decision(10, actuator_id="act-outro"))
    assert world.client().get(DECISIONS).json()["decisions"] == []


# --- eventos do atuador -------------------------------------------------------------------


def test_events_come_newest_first() -> None:
    world = World()
    for seconds, name in ((300, "pulse_started"), (100, "pulse_finished"), (200, "pulse_aborted")):
        world.events.add(make_event(seconds, event=name))
    found = world.client().get(EVENTS).json()["events"]
    assert [e["event"] for e in found] == ["pulse_finished", "pulse_aborted", "pulse_started"]


def test_an_event_is_serialized_with_every_field() -> None:
    world = World()
    world.events.add(make_event(10, event="pulse_aborted", reason_code="stop_command"))
    assert world.client().get(EVENTS).json()["events"] == [
        {
            "occurred_at": "2026-10-24T21:59:50Z",
            "event": "pulse_aborted",
            "command_id": UUID,
            "reason_code": "stop_command",
        }
    ]


def test_the_event_limit_keeps_the_newest_and_flags_truncation() -> None:
    world = World()
    for seconds in (50, 40, 30, 20, 10):
        world.events.add(make_event(seconds))
    client = world.client()
    body = client.get(EVENTS, params={"limit": 2}).json()
    assert [e["occurred_at"] for e in body["events"]] == [
        "2026-10-24T21:59:50Z",
        "2026-10-24T21:59:40Z",
    ]
    assert (body["limit"], body["truncated"]) == (2, True)
    assert client.get(EVENTS, params={"limit": 5}).json()["truncated"] is False


def test_the_event_window_is_half_open() -> None:
    world = World()
    for seconds in (50, 40, 30, 20, 10):
        world.events.add(make_event(seconds))
    params = {"start": "2026-10-24T21:59:30Z", "end": "2026-10-24T21:59:50Z"}
    found = world.client().get(EVENTS, params=params).json()["events"]
    assert [e["occurred_at"] for e in found] == ["2026-10-24T21:59:40Z", "2026-10-24T21:59:30Z"]


def test_events_of_other_actuators_are_not_returned() -> None:
    world = World()
    world.events.add(make_event(10, actuator_id="act-outro"))
    assert world.client().get(EVENTS).json()["events"] == []


# --- validação das consultas de trilha ----------------------------------------------------


@pytest.mark.parametrize("path", [DECISIONS, EVENTS])
def test_a_window_longer_than_seven_days_is_rejected(path: str) -> None:
    params = {"start": "2026-10-10T00:00:00Z", "end": "2026-10-24T00:00:00Z"}
    response = World().client().get(path, params=params)
    assert response.status_code == 422
    body = response.json()
    assert body["type"] == "urn:pigeondome:erro:janela-invalida"
    assert body["errors"][0]["code"] == "window_too_large"
    assert "7 dias" in body["errors"][0]["message"]


@pytest.mark.parametrize("path", [DECISIONS, EVENTS])
def test_a_window_of_exactly_seven_days_is_accepted(path: str) -> None:
    params = {"start": "2026-10-17T22:00:00Z", "end": "2026-10-24T22:00:00Z"}
    assert World().client().get(path, params=params).status_code == 200


@pytest.mark.parametrize("path", [DECISIONS, EVENTS])
def test_an_inverted_or_empty_window_is_rejected(path: str) -> None:
    client = World().client()
    inverted = {"start": "2026-10-24T21:00:00Z", "end": "2026-10-24T20:00:00Z"}
    empty = {"start": "2026-10-24T21:00:00Z", "end": "2026-10-24T21:00:00Z"}
    for params in (inverted, empty):
        response = client.get(path, params=params)
        assert response.status_code == 422
        assert response.json()["errors"][0]["code"] == "end_before_start"


@pytest.mark.parametrize("path", [DECISIONS, EVENTS])
def test_a_datetime_without_timezone_is_rejected(path: str) -> None:
    response = World().client().get(path, params={"start": "2026-10-24T21:00:00"})
    assert response.status_code == 422
    assert response.json()["errors"][0]["code"] == "missing_timezone"


@pytest.mark.parametrize("path", [DECISIONS, EVENTS])
def test_the_limit_must_be_between_1_and_500(path: str) -> None:
    client = World().client()
    for limit in (0, 501):
        response = client.get(path, params={"limit": limit})
        assert response.status_code == 422
        assert response.json()["errors"][0]["field"] == "limit"
    assert client.get(path, params={"limit": 500}).status_code == 200


# --- chave geral: só liga -----------------------------------------------------------------


def test_the_kill_switch_can_be_engaged_with_the_confirmation_header() -> None:
    world = World()
    response = world.client().post(KILL_SWITCH, headers=CONFIRM)
    assert response.status_code == 200
    assert response.json() == {"kill_switch": True}
    assert world.flags.kill_switch() is True


@pytest.mark.parametrize(
    "headers", [{}, {"X-Pigeondome-Action": "off"}, {"X-Pigeondome-Action": ""}]
)
def test_without_the_confirmation_the_kill_switch_stays_off(headers: dict[str, str]) -> None:
    world = World()
    response = world.client().post(KILL_SWITCH, headers=headers)
    assert response.status_code == 403
    assert response.json()["type"] == "urn:pigeondome:erro:acao-nao-confirmada"
    assert world.flags.kill_switch() is False


def test_engaging_twice_is_harmless() -> None:
    world = World()
    client = world.client()
    assert client.post(KILL_SWITCH, headers=CONFIRM).status_code == 200
    assert client.post(KILL_SWITCH, headers=CONFIRM).status_code == 200
    assert world.flags.kill_switch() is True


def test_the_api_has_no_way_to_turn_the_kill_switch_off() -> None:
    world = World()
    world.flags.set_kill_switch(True, NOW)
    client = world.client()
    spec = client.get("/openapi.json").json()
    writes = {
        (method, path)
        for path, operations in spec["paths"].items()
        for method in operations
        if method in {"post", "put", "patch", "delete"}
    }
    assert writes == {("post", KILL_SWITCH)}
    assert client.delete(KILL_SWITCH).status_code == 405
    assert client.put(KILL_SWITCH, headers=CONFIRM).status_code == 405
    assert world.flags.kill_switch() is True


# --- CORS ---------------------------------------------------------------------------------


def test_the_panel_origin_may_post_with_the_confirmation_header() -> None:
    response = World().client((ORIGIN,)).options(KILL_SWITCH, headers=PREFLIGHT)
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ORIGIN
    assert "POST" in response.headers["access-control-allow-methods"]
    assert "x-pigeondome-action" in response.headers["access-control-allow-headers"].lower()


def test_other_origins_and_methods_are_refused_in_preflight() -> None:
    client = World().client((ORIGIN,))
    other_origin = client.options(KILL_SWITCH, headers={**PREFLIGHT, "Origin": "https://x.example"})
    assert other_origin.status_code == 400
    delete = client.options(
        KILL_SWITCH, headers={**PREFLIGHT, "Access-Control-Request-Method": "DELETE"}
    )
    assert delete.status_code == 400


def test_a_read_only_app_still_refuses_post_in_preflight() -> None:
    client = TestClient(create_app(InMemoryDetectionRepository(), (ORIGIN,)))
    assert client.options("/api/v1/devices", headers=PREFLIGHT).status_code == 400


# --- falhas de banco e limites dos casos de uso -------------------------------------------


def test_storage_failures_are_503_without_internal_details() -> None:
    world = World()
    world.flags = BrokenFlags()
    client = world.client()
    for response in (client.get(CONTROLLER), client.post(KILL_SWITCH, headers=CONFIRM)):
        assert response.status_code == 503
        assert response.json()["type"] == "urn:pigeondome:erro:armazenamento-indisponivel"
        assert "banco fora" not in response.text


def test_the_list_use_cases_reject_a_non_positive_limit() -> None:
    with pytest.raises(ValueError, match="limite"):
        ListDecisions(InMemoryDecisionRepository()).execute(ACTUATOR, ago(60), NOW, 0)
    with pytest.raises(ValueError, match="limite"):
        ListActuatorEvents(InMemoryActuatorEventRepository()).execute(ACTUATOR, ago(60), NOW, 0)


# --- o relógio de produção ----------------------------------------------------------------


def test_the_default_clock_is_timezone_aware_and_current() -> None:
    # todos os outros testes injetam um relógio parado: este confere o que roda de verdade
    now = utc_now()
    assert now.tzinfo is not None
    assert abs((datetime.now(UTC) - now).total_seconds()) < 5
