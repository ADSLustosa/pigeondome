"""Contratos de resposta da API: o que o dashboard enxerga."""

from datetime import datetime

from pydantic import BaseModel, Field


class HealthOut(BaseModel):
    status: str


class DeviceOut(BaseModel):
    device_id: str
    readings: int = Field(description="total de leituras armazenadas")
    last_detected_at: datetime = Field(description="instante da leitura mais recente (UTC)")


class PresenceOut(BaseModel):
    device_id: str
    start: datetime
    end: datetime
    readings: int = Field(description="leituras dentro da janela")
    readings_with_pigeons: int
    presence_rate: float = Field(
        ge=0, le=1, description="fração das leituras com pelo menos um pombo"
    )
    mean_pigeons: float
    max_pigeons: int
