"""Configuração lida do ambiente (12-Factor App)."""

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    user: str
    password: str = field(repr=False)
    device_id: str
    interval_s: float
    seed: int | None
    force_hour: int | None

    @classmethod
    def from_env(cls) -> "Settings":
        password = os.environ.get("MQTT_PASSWORD", "")
        if not password:
            raise ValueError("defina MQTT_PASSWORD (senha do usuário MQTT 'camera')")
        seed = os.environ.get("SIM_SEED")
        force_hour = os.environ.get("SIM_FORCE_HOUR")
        return cls(
            host=os.environ.get("MQTT_HOST", "localhost"),
            port=int(os.environ.get("MQTT_PORT", "1883")),
            user=os.environ.get("MQTT_USER", "camera"),
            password=password,
            device_id=os.environ.get("DEVICE_ID", "cam-sim-01"),
            interval_s=float(os.environ.get("SIM_INTERVAL_S", "5")),
            seed=int(seed) if seed else None,
            force_hour=int(force_hour) if force_hour else None,
        )
