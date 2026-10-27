"""Adaptador HTTP da câmera, testado contra uma câmera de mentira num servidor de verdade."""

import contextlib
import socket
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from pigeondome.adapters.http_camera import HttpCameraSnapshots
from pigeondome.application.ports import CameraNotConfiguredError, CameraUnavailableError
from pigeondome.domain.camera import MAX_SNAPSHOT_BYTES

JPEG = b"\xff\xd8\xff\xe0" + b"frame" * 20
DEVICE = "cam-sim-01"


class FakeCamera:
    """Uma câmera de mentira: responde o que o teste mandar, num HTTP de verdade."""

    def __init__(self) -> None:
        self.status = 200
        self.body = JPEG
        self.requests: list[str] = []
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                owner.requests.append(self.path)
                self.send_response(owner.status)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(owner.body)))
                self.end_headers()
                with contextlib.suppress(OSError):
                    self.wfile.write(owner.body)

            def log_message(self, format: str, *args: object) -> None:
                pass

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_address[1]}/capture?token=abc"

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)


@pytest.fixture
def camera() -> Iterator[FakeCamera]:
    fake = FakeCamera()
    try:
        yield fake
    finally:
        fake.close()


def test_fetch_returns_the_jpeg_the_camera_serves(camera: FakeCamera) -> None:
    cameras = HttpCameraSnapshots({DEVICE: camera.url})
    assert cameras.fetch(DEVICE).content == JPEG
    assert camera.requests == ["/capture?token=abc"]


def test_a_device_without_a_camera_is_reported_and_nothing_is_requested(
    camera: FakeCamera,
) -> None:
    cameras = HttpCameraSnapshots({DEVICE: camera.url})
    with pytest.raises(CameraNotConfiguredError):
        cameras.fetch("cam-outra")
    assert camera.requests == []


def test_with_no_cameras_configured_every_device_is_unknown() -> None:
    with pytest.raises(CameraNotConfiguredError):
        HttpCameraSnapshots({}).fetch(DEVICE)


def test_an_error_status_from_the_camera_is_unavailable(camera: FakeCamera) -> None:
    camera.status = 500
    with pytest.raises(CameraUnavailableError):
        HttpCameraSnapshots({DEVICE: camera.url}).fetch(DEVICE)


def test_a_response_that_is_not_a_jpeg_is_unavailable(camera: FakeCamera) -> None:
    camera.body = b"<html>login</html>"
    with pytest.raises(CameraUnavailableError):
        HttpCameraSnapshots({DEVICE: camera.url}).fetch(DEVICE)


def test_a_huge_response_is_unavailable(camera: FakeCamera) -> None:
    camera.body = JPEG + b"x" * MAX_SNAPSHOT_BYTES
    with pytest.raises(CameraUnavailableError):
        HttpCameraSnapshots({DEVICE: camera.url}).fetch(DEVICE)


def test_a_camera_that_is_down_is_unavailable() -> None:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    # a porta acabou de ser liberada e ninguém escuta nela: a conexão é recusada
    cameras = HttpCameraSnapshots({DEVICE: f"http://127.0.0.1:{port}/x"}, timeout_s=1.0)
    with pytest.raises(CameraUnavailableError):
        cameras.fetch(DEVICE)


def test_the_total_time_limit_is_enforced(camera: FakeCamera) -> None:
    calls = {"count": 0}

    def jumping_clock() -> float:
        calls["count"] += 1
        return 0.0 if calls["count"] == 1 else 1000.0

    cameras = HttpCameraSnapshots({DEVICE: camera.url}, clock=jumping_clock)
    with pytest.raises(CameraUnavailableError):
        cameras.fetch(DEVICE)


def test_an_invalid_camera_url_fails_at_construction() -> None:
    with pytest.raises(ValueError, match="http"):
        HttpCameraSnapshots({DEVICE: "https://cam.local/x"})
