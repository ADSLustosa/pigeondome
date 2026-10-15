"""Gerador de detecções simuladas.

O padrão por horário é uma SUPOSIÇÃO de modelagem, e não um dado real.
Ele será substituído pela linha de base medida na instalação física.
"""

import math
import random
from dataclasses import dataclass
from datetime import UTC, datetime

MAX_PIGEONS = 50
CONTRACT_VERSION = 1


def expected_rate(hour: int) -> float:
    """Média esperada de pombos por leitura, conforme a hora do dia."""
    if 6 <= hour <= 9:
        return 4.0
    if 10 <= hour <= 15:
        return 1.0
    if 16 <= hour <= 18:
        return 3.5
    return 0.0


@dataclass(frozen=True)
class Detection:
    device_id: str
    timestamp: datetime
    pigeon_count: int
    confidence: float

    def to_payload(self) -> dict[str, object]:
        """Converte para o formato do contrato detection.v1."""
        return {
            "schema_version": CONTRACT_VERSION,
            "device_id": self.device_id,
            "timestamp": self.timestamp.astimezone(UTC).isoformat(),
            "pigeon_count": self.pigeon_count,
            "confidence": self.confidence,
        }


class DetectionGenerator:
    def __init__(self, device_id: str, rng: random.Random) -> None:
        self._device_id = device_id
        self._rng = rng

    def _poisson(self, lam: float) -> int:
        """Amostra de Poisson (algoritmo de Knuth), adequada para médias pequenas."""
        if lam <= 0:
            return 0
        limit = math.exp(-lam)
        k = 0
        p = 1.0
        while True:
            p *= self._rng.random()
            if p <= limit:
                return k
            k += 1

    def generate(self, now: datetime, hour: int | None = None) -> Detection:
        """Gera uma leitura em `now`. `hour` força apenas o modelo (demonstrações)."""
        model_hour = now.hour if hour is None else hour
        count = min(self._poisson(expected_rate(model_hour)), MAX_PIGEONS)
        confidence = round(self._rng.uniform(0.75, 0.99), 2)
        return Detection(self._device_id, now, count, confidence)
