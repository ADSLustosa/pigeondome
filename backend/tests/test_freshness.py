"""Frescor dos dados de estado: quando o painel deve desconfiar do que o banco guarda."""

from datetime import UTC, datetime, timedelta

import pytest

from pigeondome.domain import freshness
from pigeondome.domain.actuation import Mode, PolicyConfig
from pigeondome.domain.status import ActuatorStateRecord, ControllerStatusRecord

NOW = datetime(2026, 10, 24, 22, 0, 0, tzinfo=UTC)
ACTUATOR = "act-sim-01"
CAMERA = "cam-sim-01"


def ago(seconds: float) -> datetime:
    return NOW - timedelta(seconds=seconds)


def actuator(seconds_ago: float, *, online: bool = True) -> ActuatorStateRecord:
    state = "idle" if online else "safe_off"
    return ActuatorStateRecord(ACTUATOR, online, state, False, 0, ago(seconds_ago))


def controller(seconds_ago: float) -> ControllerStatusRecord:
    return ControllerStatusRecord(Mode.LIVE, CAMERA, ACTUATOR, ago(3600), ago(seconds_ago))


def test_the_actuator_limit_is_the_one_the_controller_policy_uses() -> None:
    assert PolicyConfig().max_actuator_report_age_s == freshness.ACTUATOR_STALE_AFTER_S


def test_age_is_never_negative() -> None:
    assert freshness.age_s(ago(-5), NOW) == 0.0
    assert freshness.age_s(ago(12.5), NOW) == 12.5


@pytest.mark.parametrize(("seconds", "stale"), [(0, False), (30, False), (30.1, True)])
def test_an_online_actuator_goes_stale_after_the_limit(seconds: float, stale: bool) -> None:
    assert freshness.actuator_is_stale(actuator(seconds), NOW) is stale


@pytest.mark.parametrize("seconds", [0, 3600])
def test_an_offline_actuator_is_never_stale(seconds: float) -> None:
    assert freshness.actuator_is_stale(actuator(seconds, online=False), NOW) is False


def test_a_controller_without_a_record_never_ran() -> None:
    assert freshness.controller_is_running(None, NOW) is False


@pytest.mark.parametrize(("seconds", "running"), [(0, True), (15, True), (15.1, False)])
def test_a_controller_runs_while_its_heartbeat_is_recent(seconds: float, running: bool) -> None:
    assert freshness.controller_is_running(controller(seconds), NOW) is running
