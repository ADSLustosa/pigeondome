import pytest

from pigeondome.config import ApiSettings


def test_api_defaults() -> None:
    settings = ApiSettings.from_env()
    assert (settings.host, settings.port) == ("127.0.0.1", 8000)
    assert "http://localhost:5173" in settings.allowed_origins


def test_api_origins_are_split_and_trimmed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_ALLOWED_ORIGINS", " https://a.example , https://b.example ,")
    assert ApiSettings.from_env().allowed_origins == ("https://a.example", "https://b.example")
