"""Configuração do backend lida do ambiente (12-Factor App)."""

import os
from dataclasses import dataclass, field

from psycopg.conninfo import make_conninfo


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


@dataclass(frozen=True)
class DatabaseSettings:
    host: str
    port: int
    user: str
    dbname: str
    password: str = field(repr=False)

    @classmethod
    def from_env(cls) -> "DatabaseSettings":
        password = os.environ.get("POSTGRES_PASSWORD", "")
        if not password:
            raise ValueError("defina POSTGRES_PASSWORD (veja infra/.env)")
        return cls(
            host=os.environ.get("POSTGRES_HOST", "127.0.0.1"),
            port=int(os.environ.get("POSTGRES_PORT", "5433")),
            user=os.environ.get("POSTGRES_USER", "pigeon"),
            dbname=os.environ.get("POSTGRES_DB", "pigeondome"),
            password=password,
        )

    @property
    def conninfo(self) -> str:
        return make_conninfo(
            host=self.host,
            port=self.port,
            user=self.user,
            dbname=self.dbname,
            password=self.password,
            connect_timeout=5,
        )
