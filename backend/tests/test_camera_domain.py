"""Quadro da câmera e URL do quadro: regras de validação (sem rede)."""

import pytest

from pigeondome.domain.camera import (
    MAX_SNAPSHOT_BYTES,
    CameraTarget,
    InvalidSnapshotError,
    Snapshot,
    parse_camera_url,
)

JPEG = b"\xff\xd8\xff\xe0" + b"frame" * 20


def test_a_jpeg_is_accepted() -> None:
    assert Snapshot(JPEG).content == JPEG


@pytest.mark.parametrize("content", [b"", b"<html>oops</html>", b"\x89PNG\r\n", b"GIF89a"])
def test_anything_but_a_jpeg_is_rejected(content: bytes) -> None:
    with pytest.raises(InvalidSnapshotError, match="JPEG"):
        Snapshot(content)


def test_a_huge_frame_is_rejected() -> None:
    with pytest.raises(InvalidSnapshotError, match="tamanho"):
        Snapshot(JPEG + b"x" * MAX_SNAPSHOT_BYTES)


def test_the_size_limit_itself_is_accepted() -> None:
    exact = JPEG + b"x" * (MAX_SNAPSHOT_BYTES - len(JPEG))
    assert len(exact) == MAX_SNAPSHOT_BYTES
    assert Snapshot(exact).content == exact


def test_the_camera_url_is_split_for_the_request() -> None:
    target = parse_camera_url("http://192.168.0.20:8080/capture?token=abc")
    assert target == CameraTarget("192.168.0.20", 8080, "/capture?token=abc")


def test_the_camera_url_defaults_to_port_80_and_the_root_path() -> None:
    assert parse_camera_url("http://cam.local") == CameraTarget("cam.local", 80, "/")


@pytest.mark.parametrize(
    ("url", "reason"),
    [
        ("https://cam/x", "http"),
        ("ftp://cam/x", "http"),
        ("cam/x", "http"),
        ("http:///x", "endereço"),
        ("http://user:pw@cam/x", "usuário"),
        ("http://cam:99999/x", "inválida"),
    ],
)
def test_bad_urls_are_rejected_without_echoing_them(url: str, reason: str) -> None:
    with pytest.raises(ValueError, match=reason) as info:
        parse_camera_url(url)
    assert url not in str(info.value)
