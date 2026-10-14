import pytest

from pigeondome_sim.config import Settings


def test_settings_require_password(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MQTT_PASSWORD", raising=False)
    with pytest.raises(ValueError):
        Settings.from_env()


def test_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MQTT_PASSWORD", "segredo")
    settings = Settings.from_env()
    assert (settings.host, settings.port, settings.user) == ("localhost", 1883, "camera")


def test_password_never_appears_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MQTT_PASSWORD", "segredo-super-secreto")
    assert "segredo-super-secreto" not in repr(Settings.from_env())
