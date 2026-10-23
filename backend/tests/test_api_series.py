from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from pigeondome.adapters.api.app import create_app
from pigeondome.adapters.memory import InMemoryDetectionRepository
from pigeondome.application.use_cases import GetPresenceSeries
from pigeondome.domain.models import Detection

T0 = datetime(2026, 10, 22, 22, 0, tzinfo=UTC)
SERIES = "/api/v1/devices/cam-sim-01/presence/series"
WINDOW = {"start": "2026-10-22T22:00:00Z", "end": "2026-10-22T22:10:00Z"}


def make_client() -> TestClient:
    repo = InMemoryDetectionRepository()
    for minute, count in [(0, 0), (1, 4), (2, 2), (6, 6)]:
        repo.add(Detection("cam-sim-01", T0 + timedelta(minutes=minute), count, 0.9))
    return TestClient(create_app(repo))


def test_series_returns_aggregated_points() -> None:
    response = make_client().get(SERIES, params={**WINDOW, "bucket": "5m"})
    assert response.status_code == 200
    body = response.json()
    assert body["bucket"] == "5m"
    first, second = body["points"]
    assert first["bucket_start"] == "2026-10-22T22:00:00Z"
    assert (first["readings"], first["readings_with_pigeons"], first["max_pigeons"]) == (3, 2, 4)
    assert first["mean_pigeons"] == 2.0
    assert abs(first["presence_rate"] - 2 / 3) < 1e-9
    assert second["bucket_start"] == "2026-10-22T22:05:00Z"
    assert second["readings"] == 1


def test_default_bucket_is_five_minutes() -> None:
    assert make_client().get(SERIES, params=WINDOW).json()["bucket"] == "5m"


def test_unsupported_bucket_is_rejected_with_the_field_name() -> None:
    response = make_client().get(SERIES, params={**WINDOW, "bucket": "7m"})
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "bucket"


def test_too_many_points_is_rejected_with_guidance() -> None:
    params = {"start": "2026-10-01T00:00:00Z", "end": "2026-10-22T00:00:00Z", "bucket": "1m"}
    response = make_client().get(SERIES, params=params)
    assert response.status_code == 422
    body = response.json()
    assert body["type"] == "urn:pigeondome:erro:janela-invalida"
    assert body["errors"][0]["code"] == "too_many_points"
    assert "intervalo maior" in body["errors"][0]["message"]


def test_unknown_device_is_404() -> None:
    path = "/api/v1/devices/nao-existe/presence/series"
    assert make_client().get(path, params=WINDOW).status_code == 404


def test_datetime_without_timezone_is_422() -> None:
    response = make_client().get(SERIES, params={"start": "2026-10-22T22:00:00"})
    assert response.status_code == 422
    assert response.json()["errors"][0]["code"] == "missing_timezone"


def test_openapi_lists_the_series_endpoint_and_its_bucket_values() -> None:
    spec = make_client().get("/openapi.json").json()
    operation = spec["paths"]["/api/v1/devices/{device_id}/presence/series"]["get"]
    assert '"15m"' in str(operation["parameters"]).replace("'", '"')


def test_series_use_case_rejects_a_non_positive_bucket() -> None:
    use_case = GetPresenceSeries(InMemoryDetectionRepository())
    with pytest.raises(ValueError, match="bucket"):
        use_case.execute("cam-sim-01", T0, T0 + timedelta(hours=1), timedelta(0))


def test_series_use_case_rejects_an_inverted_window() -> None:
    use_case = GetPresenceSeries(InMemoryDetectionRepository())
    with pytest.raises(ValueError, match="janela"):
        use_case.execute("cam-sim-01", T0, T0, timedelta(minutes=5))
