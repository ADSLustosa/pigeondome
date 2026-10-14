"""Modelo de domínio: sem dependência de MQTT, banco ou framework web."""

import re
from dataclasses import dataclass
from datetime import datetime

DEVICE_ID_PATTERN = re.compile(r"^[a-z0-9-]{3,32}$")
MAX_PIGEONS = 50


class InvalidDetectionError(ValueError):
    """Violação de uma regra do domínio ao criar uma detecção."""


@dataclass(frozen=True)
class Detection:
    """Uma leitura de câmera: quantos pombos foram vistos em um instante."""

    device_id: str
    timestamp: datetime
    pigeon_count: int
    confidence: float

    def __post_init__(self) -> None:
        if not DEVICE_ID_PATTERN.fullmatch(self.device_id):
            raise InvalidDetectionError(f"device_id inválido: {self.device_id!r}")
        if self.timestamp.tzinfo is None:
            raise InvalidDetectionError("timestamp precisa ter fuso horário")
        if not 0 <= self.pigeon_count <= MAX_PIGEONS:
            raise InvalidDetectionError(f"pigeon_count fora de 0..{MAX_PIGEONS}")
        if not 0.0 <= self.confidence <= 1.0:
            raise InvalidDetectionError("confidence fora de 0..1")

    @property
    def has_pigeons(self) -> bool:
        return self.pigeon_count > 0


@dataclass(frozen=True)
class PresenceStats:
    """Resumo de presença de pombos em uma janela de tempo."""

    device_id: str
    readings: int
    readings_with_pigeons: int
    mean_pigeons: float
    max_pigeons: int

    @property
    def presence_rate(self) -> float:
        """Fração das leituras em que havia pelo menos um pombo."""
        return self.readings_with_pigeons / self.readings if self.readings else 0.0
