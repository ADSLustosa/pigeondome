from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from pigeondome.adapters.api.app import create_app
from pigeondome.adapters.memory import InMemoryDetectionRepository
from pigeondome.application.ports import StorageError
from pigeondome.domain.models import Detection

T0 = datetime(2026, 10, 22, 22, 0, tzinfo=UTC)
ORIGIN = "http://localhost:5173"
PRESENCE = "/api/v1/devices/cam-sim-01/presence"


def seeded() -> InMemoryDetectionRepository:
    repo = InMemoryDetectionRepository()
    for minute, count in [(0, 0), (1, 4), (2, 2), (3, 0)]:
        repo.add(Detection("cam-sim-01", T0 + timedelta(minutes=minute), count, 0.9))
    return repo


def make_client(
    repo: InMemoryDetectionRepository | None = None, origins: tuple[str, ...] = ()
) -> TestClient:
    return TestClient(create_app(repo or InMemoryDetectionRepository(), origins))


WINDOW = {"start": "2026-10-22T22:00:00Z", "end": "2026-10-22T22:10:00Z"}


def test_health() -> None:
    response = make_client().get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_devices_empty() -> None:
    assert make_client().get("/api/v1/devices").json() == []


def test_devices_lists_known_devices() -> None:
    body = make_client(seeded()).get("/api/v1/devices").json()
    assert [(d["device_id"], d["readings"]) for d in body] == [("cam-sim-01", 4)]


def test_presence_values() -> None:
    response = make_client(seeded()).get(PRESENCE, params=WINDOW)
    assert response.status_code == 200
    body = response.json()
    assert body["readings"] == 4
    assert body["readings_with_pigeons"] == 2
    assert body["presence_rate"] == 0.5
    assert body["mean_pigeons"] == 1.5
    assert body["max_pigeons"] == 4


def test_unknown_device_is_404() -> None:
    response = make_client(seeded()).get("/api/v1/devices/nao-existe/presence", params=WINDOW)
    assert response.status_code == 404


def test_invalid_device_id_is_422() -> None:
    response = make_client(seeded()).get("/api/v1/devices/BAD_ID/presence", params=WINDOW)
    assert response.status_code == 422


def test_datetime_without_timezone_is_422() -> None:
    response = make_client(seeded()).get(PRESENCE, params={"start": "2026-10-22T22:00:00"})
    assert response.status_code == 422
    assert "fuso" in response.json()["detail"]


def test_end_must_follow_start() -> None:
    params = {"start": "2026-10-22T22:10:00Z", "end": "2026-10-22T22:00:00Z"}
    assert make_client(seeded()).get(PRESENCE, params=params).status_code == 422


def test_window_is_capped_at_31_days() -> None:
    params = {"start": "2026-01-01T00:00:00Z", "end": "2026-10-22T00:00:00Z"}
    assert make_client(seeded()).get(PRESENCE, params=params).status_code == 422


def test_default_window_is_the_last_five_minutes() -> None:
    repo = InMemoryDetectionRepository()
    now = datetime.now(UTC)
    repo.add(Detection("cam-sim-01", now - timedelta(minutes=1), 3, 0.9))
    repo.add(Detection("cam-sim-01", now - timedelta(minutes=10), 5, 0.9))
    body = make_client(repo).get(PRESENCE).json()
    assert body["readings"] == 1


class BrokenRepository:
    def add(self, detection: Detection) -> bool:
        raise StorageError("host=10.0.0.5 senha=segredo")

    def list_between(self, device_id: str, start: datetime, end: datetime) -> list[Detection]:
        raise StorageError("host=10.0.0.5 senha=segredo")

    def list_devices(self) -> list[Detection]:
        raise StorageError("host=10.0.0.5 senha=segredo")


def test_storage_failure_becomes_503_without_leaking_details() -> None:
    client = TestClient(create_app(BrokenRepository()))  # type: ignore[arg-type]
    response = client.get("/api/v1/devices")
    assert response.status_code == 503
    assert "10.0.0.5" not in response.text
    assert "segredo" not in response.text


def test_cors_allows_only_configured_origins() -> None:
    client = make_client(origins=(ORIGIN,))
    allowed = client.get("/health", headers={"Origin": ORIGIN})
    other = client.get("/health", headers={"Origin": "https://malicioso.example"})
    assert allowed.headers.get("access-control-allow-origin") == ORIGIN
    assert "access-control-allow-origin" not in other.headers


def test_openapi_documents_the_endpoints() -> None:
    paths = make_client().get("/openapi.json").json()["paths"]
    assert "/api/v1/devices" in paths
    assert "/api/v1/devices/{device_id}/presence" in paths
