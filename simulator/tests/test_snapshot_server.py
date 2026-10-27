"""Servidor do quadro simulado: HTTP de verdade, só em localhost."""

import http.client
from collections.abc import Iterator

import pytest

from pigeondome_sim.snapshot_server import HOST, SnapshotServer, start_snapshot_server

JPEG = b"\xff\xd8\xff\xe0frame"


def request(server: SnapshotServer, method: str, path: str) -> tuple[int, dict[str, str], bytes]:
    connection = http.client.HTTPConnection(HOST, server.port, timeout=5)
    try:
        connection.request(method, path)
        response = connection.getresponse()
        headers = {name.lower(): value for name, value in response.getheaders()}
        return response.status, headers, response.read()
    finally:
        connection.close()


@pytest.fixture
def server() -> Iterator[SnapshotServer]:
    running = SnapshotServer(0, lambda: JPEG)
    running.start()
    try:
        yield running
    finally:
        running.stop()


def test_the_snapshot_is_the_jpeg_and_never_cached(server: SnapshotServer) -> None:
    status, headers, body = request(server, "GET", "/snapshot")
    assert (status, body) == (200, JPEG)
    assert headers["content-type"] == "image/jpeg"
    assert headers["cache-control"] == "no-store"
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["server"] == "pigeondome-sim"


def test_a_query_string_is_ignored(server: SnapshotServer) -> None:
    assert request(server, "GET", "/snapshot?t=123")[0] == 200


def test_health_answers_ok(server: SnapshotServer) -> None:
    assert request(server, "GET", "/health")[::2] == (200, b"ok")


def test_an_unknown_path_is_404(server: SnapshotServer) -> None:
    assert request(server, "GET", "/outra-coisa")[0] == 404


def test_other_methods_are_not_supported(server: SnapshotServer) -> None:
    assert request(server, "POST", "/snapshot")[0] == 501


def test_a_failure_drawing_the_frame_is_a_500_without_details() -> None:
    def broken() -> bytes:
        raise RuntimeError("segredo interno")

    failing = SnapshotServer(0, broken)
    failing.start()
    try:
        status, _, body = request(failing, "GET", "/snapshot")
    finally:
        failing.stop()
    assert status == 500
    assert b"segredo" not in body


def test_the_server_only_listens_on_localhost(server: SnapshotServer) -> None:
    assert server.host == HOST == "127.0.0.1"


def test_stopping_a_server_that_never_started_does_not_hang() -> None:
    SnapshotServer(0, lambda: JPEG).stop()


def test_a_busy_port_turns_the_image_off_instead_of_crashing(server: SnapshotServer) -> None:
    assert start_snapshot_server(server.port, lambda: JPEG) is None


def test_the_helper_starts_a_working_server() -> None:
    started = start_snapshot_server(0, lambda: JPEG)
    assert started is not None
    try:
        assert request(started, "GET", "/health")[0] == 200
    finally:
        started.stop()
