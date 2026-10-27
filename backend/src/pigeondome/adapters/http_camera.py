"""Câmeras acessadas por HTTP: a API busca o quadro mais recente (snapshot) de cada uma."""

import http.client
import logging
import time
from collections.abc import Callable, Mapping

from pigeondome.application.ports import CameraNotConfiguredError, CameraUnavailableError
from pigeondome.domain.camera import (
    MAX_SNAPSHOT_BYTES,
    CameraTarget,
    InvalidSnapshotError,
    Snapshot,
    parse_camera_url,
)

log = logging.getLogger("pigeondome")

CHUNK_BYTES = 64 * 1024


class HttpCameraSnapshots:
    """Busca o quadro por HTTP, com limite de tempo TOTAL e de tamanho.

    Só consulta endereços da configuração, nunca uma URL vinda do navegador: a API não vira um
    repassador de requisições para qualquer lugar. Os logs citam o dispositivo, nunca a URL.
    """

    def __init__(
        self,
        urls: Mapping[str, str],
        timeout_s: float = 2.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._targets = {device_id: parse_camera_url(url) for device_id, url in urls.items()}
        self._timeout_s = timeout_s
        self._clock = clock

    def fetch(self, device_id: str) -> Snapshot:
        target = self._targets.get(device_id)
        if target is None:
            raise CameraNotConfiguredError(device_id)
        try:
            body = self._download(target)
        except (OSError, http.client.HTTPException) as exc:
            log.warning("câmera %s não entregou o quadro: %s", device_id, type(exc).__name__)
            raise CameraUnavailableError(device_id) from exc
        try:
            return Snapshot(body)
        except InvalidSnapshotError as exc:
            log.warning("câmera %s enviou um quadro inválido: %s", device_id, exc)
            raise CameraUnavailableError(device_id) from exc

    def _download(self, target: CameraTarget) -> bytes:
        deadline = self._clock() + self._timeout_s
        connection = http.client.HTTPConnection(target.host, target.port, timeout=self._timeout_s)
        try:
            connection.request("GET", target.path, headers={"Accept": "image/jpeg"})
            response = connection.getresponse()
            if response.status != 200:
                raise http.client.HTTPException(f"status {response.status}")
            chunks: list[bytes] = []
            size = 0
            while chunk := response.read(CHUNK_BYTES):
                size += len(chunk)
                if size > MAX_SNAPSHOT_BYTES:
                    raise http.client.HTTPException("quadro grande demais")
                chunks.append(chunk)
                if self._clock() >= deadline:
                    raise TimeoutError("tempo total esgotado")
            return b"".join(chunks)
        finally:
            connection.close()
