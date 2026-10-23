"""API HTTP de leitura (adaptador de entrada): expõe as medições de presença."""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import FastAPI, HTTPException, Path, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from pigeondome import __version__
from pigeondome.adapters.api.schemas import DeviceOut, HealthOut, PresenceOut
from pigeondome.application.ports import DetectionRepository, StorageError
from pigeondome.application.use_cases import GetPresenceStats, ListDevices
from pigeondome.domain.models import DEVICE_ID_PATTERN

DEFAULT_WINDOW = timedelta(minutes=5)
MAX_WINDOW = timedelta(days=31)


def create_app(repository: DetectionRepository, allowed_origins: Sequence[str] = ()) -> FastAPI:
    app = FastAPI(
        title="Pigeondome API",
        version=__version__,
        description="Medições de presença de pombos (somente leitura).",
    )
    if allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(allowed_origins),
            allow_methods=["GET"],
            allow_headers=[],
        )

    presence = GetPresenceStats(repository)
    devices = ListDevices(repository)

    @app.exception_handler(StorageError)
    async def storage_error_handler(request: Request, exc: StorageError) -> JSONResponse:
        # nunca devolver detalhes internos (host, tabela, erro do driver) ao cliente
        return JSONResponse(status_code=503, content={"detail": "armazenamento indisponível"})

    @app.get("/health", response_model=HealthOut, tags=["infra"])
    def health() -> HealthOut:
        return HealthOut(status="ok")

    @app.get("/api/v1/devices", response_model=list[DeviceOut], tags=["dispositivos"])
    def list_known_devices() -> list[DeviceOut]:
        return [
            DeviceOut(
                device_id=d.device_id, readings=d.readings, last_detected_at=d.last_detected_at
            )
            for d in devices.execute()
        ]

    @app.get(
        "/api/v1/devices/{device_id}/presence",
        response_model=PresenceOut,
        tags=["presença"],
        summary="Presença de pombos em uma janela de tempo",
    )
    def device_presence(
        device_id: Annotated[str, Path(pattern=DEVICE_ID_PATTERN.pattern)],
        start: Annotated[
            datetime | None,
            Query(description="início (ISO 8601 com fuso, ex.: 2026-10-22T22:00:00Z)"),
        ] = None,
        end: Annotated[datetime | None, Query(description="fim (padrão: agora)")] = None,
    ) -> PresenceOut:
        end = end or datetime.now(UTC)
        start = start or end - DEFAULT_WINDOW
        for name, value in (("start", start), ("end", end)):
            if value.tzinfo is None:
                raise HTTPException(
                    status_code=422,
                    detail=f"{name} precisa ter fuso horário (ex.: 2026-10-22T22:00:00Z)",
                )
        if end <= start:
            raise HTTPException(status_code=422, detail="end precisa ser posterior a start")
        if end - start > MAX_WINDOW:
            raise HTTPException(status_code=422, detail="a janela máxima é de 31 dias")
        if device_id not in {d.device_id for d in devices.execute()}:
            raise HTTPException(status_code=404, detail="dispositivo desconhecido")

        stats = presence.execute(device_id, start, end)
        return PresenceOut(
            device_id=stats.device_id,
            start=start,
            end=end,
            readings=stats.readings,
            readings_with_pigeons=stats.readings_with_pigeons,
            presence_rate=stats.presence_rate,
            mean_pigeons=stats.mean_pigeons,
            max_pigeons=stats.max_pigeons,
        )

    return app
