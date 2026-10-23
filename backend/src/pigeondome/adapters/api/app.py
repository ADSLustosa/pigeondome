"""API HTTP de leitura (adaptador de entrada): expõe as medições de presença."""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import FastAPI, Path, Query
from fastapi.middleware.cors import CORSMiddleware

from pigeondome import __version__
from pigeondome.adapters.api.errors import (
    ApiError,
    FieldError,
    ProblemDetails,
    register_error_handlers,
)
from pigeondome.adapters.api.schemas import DeviceOut, HealthOut, PresenceOut
from pigeondome.application.ports import DetectionRepository
from pigeondome.application.use_cases import GetPresenceStats, ListDevices
from pigeondome.domain.models import DEVICE_ID_PATTERN

DEFAULT_WINDOW = timedelta(minutes=5)
MAX_WINDOW = timedelta(days=31)


def _problem(description: str) -> dict[str, Any]:
    """Documenta no OpenAPI o formato real dos erros (RFC 9457)."""
    return {"model": ProblemDetails, "description": description}


def _invalid_window(message: str, field: str, code: str) -> ApiError:
    return ApiError(
        422,
        "janela-invalida",
        "Janela de tempo inválida",
        message,
        [FieldError(field=field, message=message, code=code)],
    )


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
    register_error_handlers(app)

    presence = GetPresenceStats(repository)
    devices = ListDevices(repository)

    @app.get("/health", response_model=HealthOut, tags=["infra"])
    def health() -> HealthOut:
        return HealthOut(status="ok")

    @app.get(
        "/api/v1/devices",
        response_model=list[DeviceOut],
        tags=["dispositivos"],
        responses={503: _problem("Armazenamento indisponível")},
    )
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
        responses={
            404: _problem("Dispositivo desconhecido"),
            422: _problem("Parâmetros inválidos ou janela de tempo inválida"),
            503: _problem("Armazenamento indisponível"),
        },
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
                message = f"{name} precisa ter fuso horário (ex.: 2026-10-22T22:00:00Z)"
                raise ApiError(
                    422,
                    "parametros-invalidos",
                    "Parâmetros inválidos",
                    message,
                    [FieldError(field=name, message=message, code="missing_timezone")],
                )
        if end <= start:
            raise _invalid_window("end precisa ser posterior a start", "end", "end_before_start")
        if end - start > MAX_WINDOW:
            raise _invalid_window("a janela máxima é de 31 dias", "end", "window_too_large")
        if device_id not in {d.device_id for d in devices.execute()}:
            raise ApiError(
                404,
                "dispositivo-desconhecido",
                "Dispositivo desconhecido",
                f"nenhum dado recebido do dispositivo {device_id!r}",
            )

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
