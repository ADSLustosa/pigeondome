"""Rota do quadro da câmera: a API repassa o JPEG mais recente ao painel.

A imagem nunca é gravada (nem em disco nem em banco): só passa por aqui. A API fala com a
câmera por um endereço da configuração, nunca por uma URL vinda do navegador.
"""

from typing import Annotated, Any

from fastapi import FastAPI, Path, Response

from pigeondome.adapters.api.errors import ApiError, ProblemDetails
from pigeondome.application.ports import (
    CameraNotConfiguredError,
    CameraSnapshots,
    CameraUnavailableError,
)
from pigeondome.domain.models import DEVICE_ID_PATTERN

DeviceIdPath = Annotated[str, Path(pattern=DEVICE_ID_PATTERN.pattern)]


def _problem(description: str) -> dict[str, Any]:
    """Documenta no OpenAPI o formato real dos erros (RFC 9457)."""
    return {"model": ProblemDetails, "description": description}


def register_camera_routes(app: FastAPI, cameras: CameraSnapshots) -> None:
    @app.get(
        "/api/v1/devices/{device_id}/snapshot",
        response_class=Response,
        tags=["câmera"],
        summary="Quadro mais recente da câmera (JPEG)",
        description=(
            "Repassa o quadro mais recente que a câmera entrega, sem guardá-lo. A resposta "
            "nunca vai para o cache. 404 significa que o dispositivo não tem câmera configurada; "
            "502, que a câmera não entregou um quadro válido a tempo."
        ),
        responses={
            200: {"content": {"image/jpeg": {}}, "description": "O quadro mais recente"},
            404: _problem("Câmera não configurada para este dispositivo"),
            502: _problem("A câmera não entregou um quadro válido"),
        },
    )
    def device_snapshot(device_id: DeviceIdPath) -> Response:
        try:
            snapshot = cameras.fetch(device_id)
        except CameraNotConfiguredError as exc:
            raise ApiError(
                404,
                "camera-nao-configurada",
                "Câmera não configurada",
                f"nenhuma câmera configurada para o dispositivo {device_id!r}",
            ) from exc
        except CameraUnavailableError as exc:
            raise ApiError(
                502,
                "camera-indisponivel",
                "Câmera indisponível",
                "não foi possível obter o quadro da câmera",
            ) from exc
        return Response(
            content=snapshot.content,
            media_type="image/jpeg",
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )
