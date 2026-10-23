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


class SeriesPointOut(BaseModel):
    bucket_start: datetime = Field(description="início do intervalo (UTC)")
    readings: int
    readings_with_pigeons: int
    presence_rate: float = Field(ge=0, le=1)
    mean_pigeons: float
    max_pigeons: int


class SeriesOut(BaseModel):
    device_id: str
    start: datetime
    end: datetime
    bucket: str = Field(description="tamanho do intervalo: 1m, 5m, 15m, 1h ou 1d")
    points: list[SeriesPointOut] = Field(
        description="só intervalos COM leituras: ausência de ponto = ausência de medição"
    )
