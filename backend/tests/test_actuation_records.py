"""Registros da trilha do controlador: validação, conversão e regras puras."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest

from pigeondome.domain.actuation import (
    ActuatorStatus,
    Decision,
    Evidence,
    Mode,
    PolicyConfig,
    PolicyContext,
    Reason,
    Verdict,
    decide,
)
from pigeondome.domain.actuation_log import (
    ActuatorEventRecord,
    DecisionRecord,
    InvalidRecordError,
    decision_key,
    local_day_bounds,
    should_record,
)
from pigeondome.domain.models import Detection

NOW = datetime(2026, 10, 24, 15, 0, 0, tzinfo=UTC)  # 12:00 em Fortaleza
CAMERA = "cam-sim-01"
ACTUATOR = "act-sim-01"
UUID = "3f2b8c1e-7a4d-4e5b-9c6a-1d2e3f4a5b6c"
EMPTY = Evidence(0, 0, 0.0, None, False)


def skip(reason: Reason, detail: str = "") -> Decision:
    return Decision(Verdict.SKIP, reason, None, None, EMPTY, detail)


def test_a_record_can_be_built_from_a_real_decision() -> None:
    config = PolicyConfig(mode=Mode.LIVE)
    readings = [Detection(CAMERA, NOW - timedelta(seconds=1 + 5 * i), 3, 0.9) for i in range(4)]
    status = ActuatorStatus(True, "idle", NOW - timedelta(seconds=3))
    decision = decide(config, NOW, readings, status, PolicyContext())
    record = DecisionRecord.from_decision(
        decision,
        decided_at=NOW,
        camera_id=CAMERA,
        actuator_id=ACTUATOR,
        mode=Mode.LIVE,
        command_id=UUID,
    )
    assert (record.verdict, record.reason, record.triggered) == (
        Verdict.PULSE,
        Reason.EVIDENCE_CONFIRMED,
        True,
    )
    assert (record.readings, record.detections, record.duration_s) == (4, 4, 5)
    assert record.mean_confidence == pytest.approx(0.9)
    assert record.command_id == UUID


def valid_record(**changes: Any) -> DecisionRecord:
    base = DecisionRecord(
        decided_at=NOW,
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


@pytest.mark.parametrize(
    "changes",
    [
        {"decided_at": datetime(2026, 10, 24, 15, 0)},
        {"camera_id": "BAD_ID"},
        {"actuator_id": "x"},
        {"command_id": "not-a-uuid"},
        {"readings": -1, "detections": 0},
        {"detections": 5},
        {"mean_confidence": 1.5},
    ],
    ids=[
        "naive_datetime",
        "bad_camera_id",
        "bad_actuator_id",
        "bad_command_id",
        "negative_readings",
        "more_detections_than_readings",
        "confidence_out_of_range",
    ],
)
def test_inconsistent_decision_records_are_rejected(changes: dict[str, Any]) -> None:
    with pytest.raises(InvalidRecordError):
        valid_record(**changes)


def test_event_records_accept_the_contract_events_and_reject_the_rest() -> None:
    ok = ActuatorEventRecord(NOW, ACTUATOR, "pulse_started", UUID, None)
    assert ok.event == "pulse_started"
    for bad in (
        lambda: ActuatorEventRecord(NOW, ACTUATOR, "exploded", UUID, None),
        lambda: ActuatorEventRecord(datetime(2026, 10, 24), ACTUATOR, "pulse_started", None, None),
        lambda: ActuatorEventRecord(NOW, "X", "pulse_started", None, None),
        lambda: ActuatorEventRecord(NOW, ACTUATOR, "pulse_started", "nope", None),
    ):
        with pytest.raises(InvalidRecordError):
            bad()


@pytest.mark.parametrize(
    ("decision", "last_key", "expected"),
    [
        pytest.param(skip(Reason.RETRY_GAP), None, True, id="first_skip_is_recorded"),
        pytest.param(
            skip(Reason.RETRY_GAP), (Reason.RETRY_GAP, ""), False, id="same_skip_is_not_repeated"
        ),
        pytest.param(
            skip(Reason.RETRY_GAP), (Reason.STALE_DATA, ""), True, id="new_reason_is_recorded"
        ),
        pytest.param(
            skip(Reason.ACTUATOR_UNAVAILABLE, "offline"),
            (Reason.ACTUATOR_UNAVAILABLE, "cooldown"),
            True,
            id="new_detail_is_recorded",
        ),
        pytest.param(
            Decision(Verdict.PULSE, Reason.EVIDENCE_CONFIRMED, 5, None, EMPTY),
            (Reason.EVIDENCE_CONFIRMED, ""),
            True,
            id="every_trigger_is_recorded",
        ),
    ],
)
def test_only_triggers_and_changes_of_reason_are_recorded(
    decision: Decision, last_key: tuple[Reason, str] | None, expected: bool
) -> None:
    assert should_record(decision, last_key) is expected


def test_decision_key_is_the_reason_and_the_detail() -> None:
    assert decision_key(skip(Reason.ACTUATOR_UNAVAILABLE, "offline")) == (
        Reason.ACTUATOR_UNAVAILABLE,
        "offline",
    )


@pytest.mark.parametrize(
    ("now", "start", "end"),
    [
        pytest.param(
            NOW,
            datetime(2026, 10, 24, 3, 0, tzinfo=UTC),
            datetime(2026, 10, 25, 3, 0, tzinfo=UTC),
            id="midday",
        ),
        pytest.param(
            datetime(2026, 10, 24, 2, 59, 59, tzinfo=UTC),
            datetime(2026, 10, 23, 3, 0, tzinfo=UTC),
            datetime(2026, 10, 24, 3, 0, tzinfo=UTC),
            id="last_second_of_the_local_day",
        ),
        pytest.param(
            datetime(2026, 10, 24, 3, 0, tzinfo=UTC),
            datetime(2026, 10, 24, 3, 0, tzinfo=UTC),
            datetime(2026, 10, 25, 3, 0, tzinfo=UTC),
            id="local_midnight_starts_a_new_day",
        ),
    ],
)
def test_the_day_is_the_local_day(now: datetime, start: datetime, end: datetime) -> None:
    assert local_day_bounds(now, -3) == (start, end)


def test_day_bounds_follow_the_given_offset_and_accept_any_input_zone() -> None:
    assert local_day_bounds(NOW, 0) == (
        datetime(2026, 10, 24, 0, 0, tzinfo=UTC),
        datetime(2026, 10, 25, 0, 0, tzinfo=UTC),
    )
    local_input = NOW.astimezone(timezone(timedelta(hours=5)))
    assert local_day_bounds(local_input, -3) == local_day_bounds(NOW, -3)
