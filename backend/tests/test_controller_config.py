"""Configuração do controlador: padrão seguro (modo seco) e validação do ambiente."""

import pytest

from pigeondome.controller_config import ControllerSettings
from pigeondome.domain.actuation import Mode

ENV_NAMES = [
    "CONTROLLER_MODE",
    "CONTROLLER_CAMERA_ID",
    "CONTROLLER_ACTUATOR_ID",
    "CONTROLLER_TICK_S",
    "CONTROLLER_PULSE_S",
    "CONTROLLER_MIN_DETECTIONS",
    "CONTROLLER_RETRY_GAP_S",
    "CONTROLLER_MAX_PULSES_PER_DAY",
    "CONTROLLER_UTC_OFFSET_HOURS",
    "CONTROLLER_QUIET_START",
    "CONTROLLER_QUIET_END",
    "CONTROLLER_EXPERIMENT_SEED",
]


@pytest.fixture(autouse=True)
def clean_controller_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def test_defaults_are_the_safe_dry_run() -> None:
    settings = ControllerSettings.from_env()
    assert settings.policy.mode is Mode.DRY_RUN
    assert (settings.camera_id, settings.actuator_id) == ("cam-sim-01", "act-sim-01")
    assert settings.tick_s == 1.0
    assert settings.policy.quiet_start_hour is None


def test_environment_overrides_are_applied(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONTROLLER_MODE", "experiment")
    monkeypatch.setenv("CONTROLLER_PULSE_S", "8")
    monkeypatch.setenv("CONTROLLER_MIN_DETECTIONS", "5")
    monkeypatch.setenv("CONTROLLER_RETRY_GAP_S", "60")
    monkeypatch.setenv("CONTROLLER_MAX_PULSES_PER_DAY", "10")
    monkeypatch.setenv("CONTROLLER_UTC_OFFSET_HOURS", "-5")
    monkeypatch.setenv("CONTROLLER_QUIET_START", "22")
    monkeypatch.setenv("CONTROLLER_QUIET_END", "5")
    monkeypatch.setenv("CONTROLLER_EXPERIMENT_SEED", "42")
    monkeypatch.setenv("CONTROLLER_ACTUATOR_ID", "act-casa-02")
    monkeypatch.setenv("CONTROLLER_TICK_S", "0.5")
    settings = ControllerSettings.from_env()
    policy = settings.policy
    assert policy.mode is Mode.EXPERIMENT
    assert (policy.pulse_s, policy.min_detections, policy.retry_gap_s) == (8, 5, 60.0)
    assert (policy.max_pulses_per_day, policy.utc_offset_hours) == (10, -5)
    assert (policy.quiet_start_hour, policy.quiet_end_hour) == (22, 5)
    assert policy.experiment_seed == 42
    assert (settings.actuator_id, settings.tick_s) == ("act-casa-02", 0.5)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("CONTROLLER_MODE", "turbo"),
        ("CONTROLLER_CAMERA_ID", "BAD_ID"),
        ("CONTROLLER_ACTUATOR_ID", "x"),
        ("CONTROLLER_TICK_S", "0.01"),
        ("CONTROLLER_TICK_S", "10"),
        ("CONTROLLER_PULSE_S", "11"),
        ("CONTROLLER_QUIET_START", "22"),
    ],
)
def test_invalid_environment_is_rejected(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError):  # noqa: PT011
        ControllerSettings.from_env()


def test_the_server_reports_an_invalid_environment_instead_of_starting() -> None:
    from pigeondome.controller_server import main

    assert main() == 2  # o conftest já removeu MQTT_PASSWORD
