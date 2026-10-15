import pytest

ENV_VARS = ["MQTT_HOST", "MQTT_PORT", "MQTT_USER", "MQTT_PASSWORD"]


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Testes não podem depender das variáveis de ambiente de quem os executa."""
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)
