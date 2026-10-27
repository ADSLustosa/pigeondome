"""API HTTP de leitura (adaptador de entrada): expõe as medições de presença."""

import math
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal

from fastapi import FastAPI, Path, Query
from fastapi.middleware.cors import CORSMiddleware

from pigeondome import __version__
from pigeondome.adapters.api.actuation_routes import (
    ACTION_HEADER,
    ActuationPorts,
    register_actuation_routes,
    utc_now,
)
from pigeondome.adapters.api.camera_routes import register_camera_routes
from pigeondome.adapters.api.errors import (
    ApiError,
    FieldError,
    ProblemDetails,
    register_error_handlers,
)
from pigeondome.adapters.api.schemas import (
    DeviceOut,
    HealthOut,
    PresenceOut,
    SeriesOut,
    SeriesPointOut,
)
from pigeondome.application.ports import CameraSnapshots, DetectionRepository
from pigeondome.application.use_cases import GetPresenceSeries, GetPresenceStats, ListDevices
from pigeondome.domain.models import DEVICE_ID_PATTERN

DEFAULT_WINDOW = timedelta(minutes=5)
DEFAULT_SERIES_WINDOW = timedelta(hours=1)
MAX_WINDOW = timedelta(days=31)
MAX_SERIES_POINTS = 500

BucketName = Literal["1m", "5m", "15m", "1h", "1d"]
BUCKETS: dict[str, timedelta] = {
    "1m": timedelta(minutes=1),
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "1h": timedelta(hours=1),
    "1d": timedelta(days=1),
}

DeviceIdPath = Annotated[str, Path(pattern=DEVICE_ID_PATTERN.pattern)]
StartQuery = Annotated[
    datetime | None,
    Query(description="início (ISO 8601 com fuso, ex.: 2026-10-22T22:00:00Z)"),
]
EndQuery = Annotated[datetime | None, Query(description="fim (padrão: agora)")]


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


def _resolve_window(
    start: datetime | None, end: datetime | None, default: timedelta
) -> tuple[datetime, datetime]:
    """Aplica os padrões e as regras de janela comuns a todos os endpoints de presença."""
    end = end or datetime.now(UTC)
    start = start or end - default
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
    return start, end


def create_app(
    repository: DetectionRepository,
    allowed_origins: Sequence[str] = (),
    actuation: ActuationPorts | None = None,
    clock: Callable[[], datetime] = utc_now,
    camera: CameraSnapshots | None = None,
) -> FastAPI:
    app = FastAPI(
        title="Pigeondome API",
        version=__version__,
        description="Medições de presença de pombos (somente leitura).",
    )
    if allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(allowed_origins),
            # com as rotas de atuação, o painel também pode fazer o POST que liga a chave geral
            allow_methods=["GET", "POST"] if actuation is not None else ["GET"],
            allow_headers=[ACTION_HEADER] if actuation is not None else [],
        )
    register_error_handlers(app)
    if actuation is not None:
        register_actuation_routes(app, actuation, clock)
    if camera is not None:
        register_camera_routes(app, camera)

    presence = GetPresenceStats(repository)
    series_use_case = GetPresenceSeries(repository)
    devices = ListDevices(repository)

    def require_known_device(device_id: str) -> None:
        if device_id not in {d.device_id for d in devices.execute()}:
            raise ApiError(
                404,
                "dispositivo-desconhecido",
                "Dispositivo desconhecido",
                f"nenhum dado recebido do dispositivo {device_id!r}",
            )

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
        device_id: DeviceIdPath,
        start: StartQuery = None,
        end: EndQuery = None,
    ) -> PresenceOut:
        start, end = _resolve_window(start, end, DEFAULT_WINDOW)
        require_known_device(device_id)
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

    @app.get(
        "/api/v1/devices/{device_id}/presence/series",
        response_model=SeriesOut,
        tags=["presença"],
        summary="Presença de pombos agrupada em intervalos de tempo (para gráficos)",
        description=(
            "Cada ponto resume um intervalo. Só aparecem intervalos COM leituras: "
            "a ausência de um ponto significa ausência de medição (câmera offline), "
            "e não zero pombos."
        ),
        responses={
            404: _problem("Dispositivo desconhecido"),
            422: _problem("Parâmetros inválidos, janela inválida ou pontos demais"),
            503: _problem("Armazenamento indisponível"),
        },
    )
    def device_presence_series(
        device_id: DeviceIdPath,
        start: StartQuery = None,
        end: EndQuery = None,
        bucket: Annotated[BucketName, Query(description="tamanho do intervalo")] = "5m",
    ) -> SeriesOut:
        start, end = _resolve_window(start, end, DEFAULT_SERIES_WINDOW)
        step = BUCKETS[bucket]
        points = math.ceil((end - start) / step)
        if points > MAX_SERIES_POINTS:
            raise _invalid_window(
                f"a janela geraria {points} pontos; o máximo é {MAX_SERIES_POINTS} "
                "(use um intervalo maior)",
                "bucket",
                "too_many_points",
            )
        require_known_device(device_id)
        found = series_use_case.execute(device_id, start, end, step)
        return SeriesOut(
            device_id=device_id,
            start=start,
            end=end,
            bucket=bucket,
            points=[
                SeriesPointOut(
                    bucket_start=p.bucket_start,
                    readings=p.readings,
                    readings_with_pigeons=p.readings_with_pigeons,
                    presence_rate=p.presence_rate,
                    mean_pigeons=p.mean_pigeons,
                    max_pigeons=p.max_pigeons,
                )
                for p in found
            ],
        )

    return app
