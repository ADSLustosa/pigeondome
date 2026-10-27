"""Quadro simulado da câmera: um desenho que mostra a MESMA contagem de pombos publicada.

É uma imagem sintética (gêmeo digital do sensor), nunca uma foto: o rótulo "SIMULADA" fica
sempre no topo. Tudo é determinístico: dados a contagem e o instante, o desenho é o mesmo.
"""

import io
import math
import threading
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

WIDTH = 320
HEIGHT = 240
HORIZON = 150  # onde o céu termina e o telhado começa
BAR_HEIGHT = 14
ROW_FEET = (182, 200, 218)  # linhas em que os pombos pousam (altura dos pés)
PER_ROW = 20
SLOTS = PER_ROW * len(ROW_FEET)  # 60 lugares: cabe o máximo de pombos do gerador (50)
SPREAD = 15  # distância horizontal entre lugares vizinhos
MARGIN_LEFT = 16

Color = tuple[int, int, int]
NIGHT: Color = (22, 32, 64)
DAWN: Color = (236, 160, 112)
DAY: Color = (128, 188, 236)
DUSK: Color = (232, 140, 96)
ROOF: Color = (104, 96, 92)
LEDGE: Color = (72, 66, 64)
BODY: Color = (122, 128, 140)
WING: Color = (92, 98, 110)
NECK: Color = (84, 128, 136)
BEAK: Color = (214, 150, 70)
EYE: Color = (20, 20, 20)
BAR: Color = (0, 0, 0)
TEXT: Color = (255, 255, 255)


def sky_color(hour: float) -> Color:
    """Cor do céu conforme a hora do dia (0 a 24)."""
    if hour < 5 or hour >= 19:
        return NIGHT
    if hour < 7:
        return DAWN
    if hour < 17:
        return DAY
    return DUSK


def pigeon_position(index: int) -> tuple[int, int]:
    """Lugar (x, altura dos pés) do pombo `index`: espalhados de forma fixa, sem sorteio."""
    slot = (index * 37) % SLOTS  # 37 e 60 são primos entre si: nenhum lugar se repete
    row, col = divmod(slot, PER_ROW)
    jitter_x = (index * 53) % 7 - 3
    jitter_y = (index * 29) % 5 - 2
    return MARGIN_LEFT + col * SPREAD + jitter_x, ROW_FEET[row] + jitter_y


def _draw_pigeon(draw: ImageDraw.ImageDraw, x: float, y: float) -> None:
    draw.line([(x - 2, y - 2), (x - 2, y + 2)], fill=BEAK, width=1)
    draw.line([(x + 3, y - 2), (x + 3, y + 2)], fill=BEAK, width=1)
    draw.polygon([(x - 8, y - 9), (x - 12, y - 6), (x - 8, y - 5)], fill=WING)
    draw.ellipse([x - 8, y - 13, x + 7, y - 2], fill=BODY)
    draw.ellipse([x - 6, y - 12, x + 3, y - 5], fill=WING)
    draw.ellipse([x + 3, y - 18, x + 10, y - 10], fill=NECK)
    draw.polygon([(x + 10, y - 15), (x + 14, y - 14), (x + 10, y - 13)], fill=BEAK)
    draw.point((x + 7, y - 15), fill=EYE)


class LatestScene:
    """A contagem mais recente publicada, compartilhada entre quem publica e quem desenha."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._count: int | None = None

    def update(self, count: int) -> None:
        with self._lock:
            self._count = count

    def count(self) -> int | None:
        with self._lock:
            return self._count


class FrameRenderer:
    def __init__(self) -> None:
        self._font = ImageFont.load_default()

    def render(self, count: int | None, moment: datetime) -> bytes:
        """Um quadro JPEG com `count` pombos. `None` = ainda sem nenhuma leitura."""
        hour = moment.hour + moment.minute / 60
        image = Image.new("RGB", (WIDTH, HEIGHT), sky_color(hour))
        draw = ImageDraw.Draw(image)
        draw.rectangle([0, HORIZON, WIDTH, HEIGHT], fill=ROOF)
        draw.rectangle([0, HORIZON, WIDTH, HORIZON + 4], fill=LEDGE)
        seconds = moment.timestamp()
        for index in range(min(count or 0, SLOTS)):
            x, y = pigeon_position(index)
            bob = math.sin(seconds * 2.0 + index) * 1.5  # cada pombo balança em outro ritmo
            _draw_pigeon(draw, x, y + bob)
        self._draw_bar(draw, count, moment)
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=80)
        return buffer.getvalue()

    def _draw_bar(self, draw: ImageDraw.ImageDraw, count: int | None, moment: datetime) -> None:
        draw.rectangle([0, 0, WIDTH, BAR_HEIGHT - 1], fill=BAR)
        if count is None:
            label = "SIMULADA  aguardando leitura"
        else:
            label = f"SIMULADA  {count} {'pombo' if count == 1 else 'pombos'}"
        draw.text((4, 2), label, fill=TEXT, font=self._font)
        stamp = moment.strftime("%H:%M:%S")
        stamp_width = draw.textlength(stamp, font=self._font)
        draw.text((WIDTH - 4 - stamp_width, 2), stamp, fill=TEXT, font=self._font)
