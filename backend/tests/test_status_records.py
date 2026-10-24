"""Registros de estado do atuador e do controlador: regras de validação (sem banco)."""

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import pytest

from pigeondome.domain.actuation import Mode
from pigeondome.domain.actuation_log import InvalidRecordError
from pigeondome.domain.status import ActuatorStateRecord, ControllerStatusRecord

T0 = datetime(2026, 10, 24, 21, 0, 0, tzinfo=UTC)
NAIVE = datetime(2026, 10, 24, 21, 0, 0)


def actuator_state() -> ActuatorStateRecord:
    return ActuatorStateRecord("act-sim-01", True, "idle", False, 5, T0)


def controller_status() -> ControllerStatusRecord:
    return ControllerStatusRecord(Mode.LIVE, "cam-sim-01", "act-sim-01", T0, T0)


def test_a_valid_actuator_state_is_accepted() -> None:
    assert actuator_state().state == "idle"


def test_the_display_fields_may_be_missing() -> None:
    record = ActuatorStateRecord("act-sim-01", False, "safe_off", None, None, T0)
    assert (record.output_on, record.budget_used_s_1h) == (None, None)


@pytest.mark.parametrize(
    "changes",
    [
        {"actuator_id": "ACT"},
        {"actuator_id": "a"},
        {"state": "exploding"},
        {"budget_used_s_1h": -1},
        {"budget_used_s_1h": 3601},
        {"received_at": NAIVE},
    ],
)
def test_invalid_actuator_states_are_rejected(changes: dict[str, Any]) -> None:
    with pytest.raises(InvalidRecordError):
        replace(actuator_state(), **changes)


def test_a_valid_controller_status_is_accepted() -> None:
    assert controller_status().mode is Mode.LIVE


@pytest.mark.parametrize(
    "changes",
    [{"camera_id": "CAM"}, {"actuator_id": "x"}, {"started_at": NAIVE}, {"heartbeat_at": NAIVE}],
)
def test_invalid_controller_statuses_are_rejected(changes: dict[str, Any]) -> None:
    with pytest.raises(InvalidRecordError):
        replace(controller_status(), **changes)
