"""Configuração do backend lida do ambiente (12-Factor App)."""

import os
from collections.abc import Mapping
from dataclasses import dataclass, field

from psycopg.conninfo import make_conninfo

from pigeondome.domain.camera import parse_camera_url
from pigeondome.domain.models import DEVICE_ID_PATTERN


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


def parse_camera_snapshots(raw: str) -> dict[str, str]:
    """Lê "dispositivo=URL,dispositivo=URL": de onde a API busca o quadro de cada câmera.

    Os erros citam o dispositivo, nunca a URL, que pode carregar um token.
    """
    urls: dict[str, str] = {}
    for raw_item in raw.split(","):
        item = raw_item.strip()
        if not item:
            continue
        device_id, separator, url = item.partition("=")
        device_id = device_id.strip()
        if not separator or not DEVICE_ID_PATTERN.fullmatch(device_id):
            raise ValueError("CAMERA_SNAPSHOT_URLS: use dispositivo=URL, com identificador válido")
        if device_id in urls:
            raise ValueError(f"CAMERA_SNAPSHOT_URLS: {device_id} aparece mais de uma vez")
        try:
            parse_camera_url(url.strip())
        except ValueError as exc:
            raise ValueError(f"CAMERA_SNAPSHOT_URLS: URL de {device_id}: {exc}") from exc
        urls[device_id] = url.strip()
    return urls


@dataclass(frozen=True)
class ApiSettings:
    host: str
    port: int
    allowed_origins: tuple[str, ...]
    # dispositivo -> URL do quadro (vazio: a API não oferece imagem)
    camera_snapshots: Mapping[str, str] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "ApiSettings":
        origins = os.environ.get(
            "API_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        )
        return cls(
            host=os.environ.get("API_HOST", "127.0.0.1"),
            port=int(os.environ.get("API_PORT", "8000")),
            allowed_origins=tuple(o.strip() for o in origins.split(",") if o.strip()),
            camera_snapshots=parse_camera_snapshots(os.environ.get("CAMERA_SNAPSHOT_URLS", "")),
        )
