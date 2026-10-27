"""Configuração das câmeras da API: de onde vem o quadro de cada dispositivo."""

import pytest

from pigeondome.config import ApiSettings, parse_camera_snapshots

URL = "http://127.0.0.1:8081/snapshot"


def test_cameras_are_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CAMERA_SNAPSHOT_URLS", raising=False)
    assert ApiSettings.from_env().camera_snapshots == {}


def test_the_camera_urls_come_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAMERA_SNAPSHOT_URLS", f"cam-sim-01={URL}")
    assert ApiSettings.from_env().camera_snapshots == {"cam-sim-01": URL}


def test_several_cameras_and_blank_items_are_accepted() -> None:
    raw = f"cam-aaa={URL}, ,cam-bbb=http://192.168.0.20:8080/capture?token=abc,"
    assert parse_camera_snapshots(raw) == {
        "cam-aaa": URL,
        "cam-bbb": "http://192.168.0.20:8080/capture?token=abc",
    }


def test_an_empty_value_means_no_cameras() -> None:
    assert parse_camera_snapshots("") == {}
    assert parse_camera_snapshots("  ") == {}


@pytest.mark.parametrize(
    "raw",
    [
        "cam-sim-01",
        f"CAM={URL}",
        f"={URL}",
        "cam-sim-01=https://127.0.0.1/x",
        "cam-sim-01=http://user:pw@127.0.0.1/x",
        f"cam-sim-01={URL},cam-sim-01=http://127.0.0.1:9/x",
    ],
)
def test_invalid_camera_settings_are_rejected(raw: str) -> None:
    with pytest.raises(ValueError, match="CAMERA_SNAPSHOT_URLS"):
        parse_camera_snapshots(raw)


def test_a_token_in_the_url_never_appears_in_the_error() -> None:
    with pytest.raises(ValueError, match="CAMERA_SNAPSHOT_URLS") as info:
        parse_camera_snapshots("cam-sim-01=https://host/x?token=SEGREDO")
    assert "SEGREDO" not in str(info.value)
