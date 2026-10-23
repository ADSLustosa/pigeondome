import json
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from starlette.exceptions import HTTPException as StarletteHTTPException

from pigeondome.adapters.api.app import create_app
from pigeondome.adapters.memory import InMemoryDetectionRepository
from pigeondome.application.ports import StorageError
from pigeondome.domain.models import Detection

T0 = datetime(2026, 10, 22, 22, 0, tzinfo=UTC)
PRESENCE = "/api/v1/devices/cam-sim-01/presence"
URN = "urn:pigeondome:erro:"
PROBLEM_MEDIA_TYPE = "application/problem+json"


def make_client(**kwargs: bool) -> TestClient:
    repo = InMemoryDetectionRepository()
    repo.add(Detection("cam-sim-01", T0, 3, 0.9))
    return TestClient(create_app(repo), **kwargs)


class BrokenRepository:
    def __init__(self, error: Exception) -> None:
        self._error = error

    def add(self, detection: Detection) -> bool:
        raise self._error

    def list_between(self, device_id: str, start: datetime, end: datetime) -> list[Detection]:
        raise self._error

    def list_devices(self) -> list[Detection]:
        raise self._error


def assert_problem(response, status: int, type_: str) -> dict:
    assert response.status_code == status
    assert response.headers["content-type"].startswith(PROBLEM_MEDIA_TYPE)
    body = response.json()
    assert body["status"] == status
    assert body["type"] == type_
    assert {"title", "detail", "instance"} <= body.keys()
    return body


def test_unknown_device_is_a_problem_details_document() -> None:
    path = "/api/v1/devices/nao-existe/presence"
    body = assert_problem(make_client().get(path), 404, URN + "dispositivo-desconhecido")
    assert body["instance"] == path


def test_validation_errors_are_normalized_and_never_echo_input() -> None:
    response = make_client().get(PRESENCE, params={"start": "agora-mesmo"})
    body = assert_problem(response, 422, URN + "parametros-invalidos")
    assert [error["field"] for error in body["errors"]] == ["start"]
    assert "agora-mesmo" not in response.text


def test_path_validation_error_names_the_parameter() -> None:
    response = make_client().get("/api/v1/devices/BAD_ID/presence")
    body = assert_problem(response, 422, URN + "parametros-invalidos")
    assert body["errors"][0]["field"] == "device_id"


def test_domain_rule_errors_share_the_same_shape() -> None:
    response = make_client().get(PRESENCE, params={"start": "2026-10-22T22:00:00"})
    body = assert_problem(response, 422, URN + "parametros-invalidos")
    assert body["errors"][0]["field"] == "start"
    assert body["errors"][0]["code"] == "missing_timezone"


def test_window_rules_have_their_own_type() -> None:
    params = {"start": "2026-01-01T00:00:00Z", "end": "2026-10-22T00:00:00Z"}
    body = assert_problem(make_client().get(PRESENCE, params=params), 422, URN + "janela-invalida")
    assert body["errors"][0]["code"] == "window_too_large"


def test_unknown_route_is_problem_details() -> None:
    body = assert_problem(make_client().get("/nao-existe"), 404, "about:blank")
    assert body["instance"] == "/nao-existe"


def test_method_not_allowed_is_problem_details() -> None:
    assert_problem(make_client().post("/health"), 405, "about:blank")


def test_storage_failure_is_503_without_leaking_details() -> None:
    client = TestClient(create_app(BrokenRepository(StorageError("host=10.0.0.5"))))
    body = assert_problem(client.get("/api/v1/devices"), 503, URN + "armazenamento-indisponivel")
    assert "10.0.0.5" not in json.dumps(body)


def test_unexpected_error_is_500_without_leaking_details() -> None:
    client = TestClient(
        create_app(BrokenRepository(RuntimeError("senha=segredo"))),
        raise_server_exceptions=False,
    )
    response = client.get("/api/v1/devices")
    assert_problem(response, 500, URN + "erro-interno")
    assert "segredo" not in response.text


def test_openapi_documents_problem_details() -> None:
    spec = make_client().get("/openapi.json").json()
    assert "ProblemDetails" in spec["components"]["schemas"]
    responses = spec["paths"]["/api/v1/devices/{device_id}/presence"]["get"]["responses"]
    assert "ProblemDetails" in json.dumps(responses["404"])
    assert "ProblemDetails" in json.dumps(responses["422"])


def test_unusual_http_status_still_produces_problem_details() -> None:
    app = create_app(InMemoryDetectionRepository())

    @app.get("/status-incomum")
    def unusual() -> None:
        raise StarletteHTTPException(status_code=599, detail="incomum")

    body = assert_problem(TestClient(app).get("/status-incomum"), 599, "about:blank")
    assert body["title"] == "Erro"
