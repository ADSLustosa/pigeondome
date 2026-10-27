"""Rota do quadro da câmera: repassa o JPEG e traduz as falhas em erros da API."""

from fastapi.testclient import TestClient

from pigeondome.adapters.api.app import create_app
from pigeondome.adapters.memory import InMemoryDetectionRepository
from pigeondome.application.ports import CameraNotConfiguredError, CameraUnavailableError
from pigeondome.domain.camera import Snapshot

JPEG = b"\xff\xd8\xff\xe0" + b"frame" * 20
SNAPSHOT = "/api/v1/devices/cam-sim-01/snapshot"
ORIGIN = "http://localhost:5173"


class FakeCameras:
    def __init__(self, failure: Exception | None = None) -> None:
        self.failure = failure
        self.asked: list[str] = []

    def fetch(self, device_id: str) -> Snapshot:
        self.asked.append(device_id)
        if self.failure is not None:
            raise self.failure
        return Snapshot(JPEG)


def make_client(cameras: FakeCameras | None, origins: tuple[str, ...] = ()) -> TestClient:
    return TestClient(create_app(InMemoryDetectionRepository(), origins, camera=cameras))


def test_the_snapshot_is_the_camera_jpeg_and_never_cached() -> None:
    cameras = FakeCameras()
    response = make_client(cameras).get(SNAPSHOT)
    assert response.status_code == 200
    assert response.content == JPEG
    assert response.headers["content-type"] == "image/jpeg"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert cameras.asked == ["cam-sim-01"]


def test_a_device_without_a_camera_is_404() -> None:
    response = make_client(FakeCameras(CameraNotConfiguredError("cam-sim-01"))).get(SNAPSHOT)
    assert response.status_code == 404
    body = response.json()
    assert body["type"] == "urn:pigeondome:erro:camera-nao-configurada"
    assert "cam-sim-01" in body["detail"]


def test_a_camera_that_fails_is_502_without_internal_details() -> None:
    failure = CameraUnavailableError("http://192.168.0.20/secret?token=abc")
    response = make_client(FakeCameras(failure)).get(SNAPSHOT)
    assert response.status_code == 502
    assert response.json()["type"] == "urn:pigeondome:erro:camera-indisponivel"
    assert "192.168" not in response.text
    assert "token" not in response.text


def test_an_invalid_device_id_is_rejected_before_reaching_the_camera() -> None:
    cameras = FakeCameras()
    response = make_client(cameras).get("/api/v1/devices/CAM/snapshot")
    assert response.status_code == 422
    assert cameras.asked == []


def test_an_app_without_cameras_has_no_snapshot_route() -> None:
    client = make_client(None)
    assert client.get(SNAPSHOT).status_code == 404
    assert "/api/v1/devices/{device_id}/snapshot" not in client.get("/openapi.json").json()["paths"]


def test_the_openapi_documents_the_jpeg_response() -> None:
    spec = make_client(FakeCameras()).get("/openapi.json").json()
    operation = spec["paths"]["/api/v1/devices/{device_id}/snapshot"]["get"]
    assert "image/jpeg" in operation["responses"]["200"]["content"]
    assert {"404", "502"} <= set(operation["responses"])


def test_the_snapshot_route_only_reads() -> None:
    assert make_client(FakeCameras()).post(SNAPSHOT).status_code == 405


def test_the_panel_origin_may_read_the_snapshot() -> None:
    client = make_client(FakeCameras(), (ORIGIN,))
    response = client.get(SNAPSHOT, headers={"Origin": ORIGIN})
    assert response.headers["access-control-allow-origin"] == ORIGIN
