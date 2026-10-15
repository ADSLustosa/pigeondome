"""Configuração do backend lida do ambiente (12-Factor App)."""

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class MqttSettings:
    host: str
    port: int
    user: str
    password: str = field(repr=False)

    @classmethod
    def from_env(cls) -> "MqttSettings":
        password = os.environ.get("MQTT_PASSWORD", "")
        if not password:
            raise ValueError("defina MQTT_PASSWORD (senha do usuário MQTT 'backend')")
        return cls(
            host=os.environ.get("MQTT_HOST", "localhost"),
            port=int(os.environ.get("MQTT_PORT", "1883")),
            user=os.environ.get("MQTT_USER", "backend"),
            password=password,
        )
