import pytest

from pigeondome.config import MqttSettings


def test_settings_require_password() -> None:
    with pytest.raises(ValueError, match="MQTT_PASSWORD"):
        MqttSettings.from_env()


def test_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MQTT_PASSWORD", "segredo")
    settings = MqttSettings.from_env()
    assert (settings.host, settings.port, settings.user) == ("localhost", 1883, "backend")


def test_password_never_appears_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MQTT_PASSWORD", "segredo-super-secreto")
    assert "segredo-super-secreto" not in repr(MqttSettings.from_env())
