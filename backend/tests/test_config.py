import pytest

from pigeondome.config import DatabaseSettings, MqttSettings


def test_mqtt_settings_require_password() -> None:
    with pytest.raises(ValueError, match="MQTT_PASSWORD"):
        MqttSettings.from_env()


def test_mqtt_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MQTT_PASSWORD", "segredo")
    settings = MqttSettings.from_env()
    assert (settings.host, settings.port, settings.user) == ("localhost", 1883, "backend")


def test_mqtt_password_never_appears_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MQTT_PASSWORD", "segredo-super-secreto")
    assert "segredo-super-secreto" not in repr(MqttSettings.from_env())


def test_database_settings_require_password() -> None:
    with pytest.raises(ValueError, match="POSTGRES_PASSWORD"):
        DatabaseSettings.from_env()


def test_database_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTGRES_PASSWORD", "segredo")
    settings = DatabaseSettings.from_env()
    assert (settings.host, settings.port, settings.user, settings.dbname) == (
        "127.0.0.1",
        5433,
        "pigeon",
        "pigeondome",
    )


def test_database_password_never_appears_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTGRES_PASSWORD", "segredo-super-secreto")
    assert "segredo-super-secreto" not in repr(DatabaseSettings.from_env())
