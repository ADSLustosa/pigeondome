"""Quadro simulado: desenha a contagem publicada, de forma determinística."""

import io
from datetime import datetime

import pytest
from PIL import Image, ImageChops

from pigeondome_sim.frame import (
    DAWN,
    DAY,
    DUSK,
    HEIGHT,
    HORIZON,
    NIGHT,
    SLOTS,
    WIDTH,
    FrameRenderer,
    LatestScene,
    pigeon_position,
    sky_color,
)

MOMENT = datetime(2026, 10, 24, 9, 30, 15)


def decode(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data))


def test_the_frame_is_a_jpeg_of_the_expected_size() -> None:
    data = FrameRenderer().render(3, MOMENT)
    assert data.startswith(b"\xff\xd8\xff")
    image = decode(data)
    assert (image.format, image.size) == ("JPEG", (WIDTH, HEIGHT))


def test_the_number_of_pigeons_changes_the_picture() -> None:
    renderer = FrameRenderer()
    empty = decode(renderer.render(0, MOMENT)).convert("RGB")
    crowded = decode(renderer.render(10, MOMENT)).convert("RGB")
    # abaixo da faixa do rótulo: só os pombos podem fazer diferença
    area = (0, 32, WIDTH, HEIGHT)
    assert ImageChops.difference(empty.crop(area), crowded.crop(area)).getbbox() is not None


def test_the_same_count_and_moment_draw_the_same_frame() -> None:
    renderer = FrameRenderer()
    assert renderer.render(5, MOMENT) == renderer.render(5, MOMENT)


def test_pigeons_stand_on_distinct_places_inside_the_frame() -> None:
    positions = [pigeon_position(index) for index in range(SLOTS)]
    assert len(set(positions)) == SLOTS
    for x, y in positions:
        assert x - 12 >= 0 and x + 14 < WIDTH
        assert y - 18 > HORIZON and y + 4 < HEIGHT


def test_more_pigeons_than_places_never_breaks_the_frame() -> None:
    assert decode(FrameRenderer().render(500, MOMENT)).size == (WIDTH, HEIGHT)


def test_a_frame_without_any_reading_is_different_from_zero_pigeons() -> None:
    renderer = FrameRenderer()
    assert renderer.render(None, MOMENT) != renderer.render(0, MOMENT)


def test_the_label_handles_the_singular() -> None:
    assert decode(FrameRenderer().render(1, MOMENT)).size == (WIDTH, HEIGHT)


@pytest.mark.parametrize(
    ("hour", "expected"),
    [
        (0, NIGHT),
        (4, NIGHT),
        (5, DAWN),
        (6, DAWN),
        (7, DAY),
        (12, DAY),
        (16, DAY),
        (17, DUSK),
        (18, DUSK),
        (19, NIGHT),
        (23, NIGHT),
    ],
)
def test_the_sky_follows_the_hour(hour: float, expected: tuple[int, int, int]) -> None:
    assert sky_color(hour) == expected


def test_the_sky_in_the_picture_has_the_color_of_the_hour() -> None:
    noon = datetime(2026, 10, 24, 12, 0, 0)
    pixel = decode(FrameRenderer().render(0, noon)).getpixel((160, 60))
    assert isinstance(pixel, tuple)
    assert all(abs(got - want) <= 8 for got, want in zip(pixel, DAY, strict=True))


def test_the_scene_starts_without_a_reading() -> None:
    assert LatestScene().count() is None


def test_the_scene_keeps_the_latest_count() -> None:
    scene = LatestScene()
    scene.update(4)
    scene.update(7)
    assert scene.count() == 7
