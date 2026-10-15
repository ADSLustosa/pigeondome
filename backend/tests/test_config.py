import pytest

from pigeondome.config import MqttSettings


def test_settings_require_password(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MQTT_PASSWORD", raising=False)
    with pytest.raises(ValueError, match="MQTT_PASSWORD"):
        MqttSettings.from_env()


def test_password_never_appears_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MQTT_PASSWORD", "segredo-super-secreto")
    assert "segredo-super-secreto" not in repr(MqttSettings.from_env())
