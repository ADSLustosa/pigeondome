"""Gera os banners do README e a imagem social a partir dos logos oficiais.

Os logos vêm de assets/brand/svg (kit de marca): o símbolo, a palavra e o descritor são os
do kit, sem redesenho. Os arcos do fundo nascem do centro da cúpula e só começam depois do
alcance do traço de voo somado à área de respiro do guia de marca (a altura do arco interno).

Uso, na raiz do repositório:  python scripts/build-brand-assets.py
"""

import math
import re
import sys
from pathlib import Path
from string import Template

ROOT = Path(__file__).resolve().parent.parent
SVG_DIR = ROOT / "assets" / "brand" / "svg"
OUT_DIR = ROOT / "assets" / "brand"

# Geometria do kit: o símbolo ocupa este grupo dentro do logo vertical.
GROUP = "translate(140.08 31.60) scale(1.4000)"
SYMBOL_X, SYMBOL_Y, SYMBOL_SCALE = 140.08, 31.60, 1.4
DOME_CENTER = (60.0, 76.0)  # centro dos arcos do símbolo, em unidades do símbolo
BIRD_TIP = (113.0, 11.0)  # ponta do traço de voo: o ponto mais distante do centro
BIRD_HALF_STROKE = 4.5 / 2
CLEAR_SPACE = 32.0  # altura do arco interno: a área de respiro que o guia exige

DOME_X = SYMBOL_X + DOME_CENTER[0] * SYMBOL_SCALE
DOME_Y = SYMBOL_Y + DOME_CENTER[1] * SYMBOL_SCALE
REACH = (
    math.hypot(BIRD_TIP[0] - DOME_CENTER[0], BIRD_TIP[1] - DOME_CENTER[1])
    + BIRD_HALF_STROKE
    + CLEAR_SPACE
) * SYMBOL_SCALE  # em unidades do logo vertical

LIGHT = {
    "bg0": "#F7F8FB",
    "bg1": "#E8EDF4",
    "accent": "#2F9E8F",
    "glow_op": "0.14",
    "border": "#D5DBE6",
    "arcs": (0.8, 0.62, 0.5, 0.4, 0.32),
}
DARK = {
    "bg0": "#151827",
    "bg1": "#1D2238",
    "accent": "#4FD1BF",
    "glow_op": "0.17",
    "border": "#2A3050",
    "arcs": (0.7, 0.55, 0.44, 0.35, 0.28),
}
STEPS = (1.0, 1.36, 1.78, 2.28, 2.86)
DOTS = [(0, 132), (1, 36), (1, 150), (2, 64), (3, 26), (3, 120)]

BANNER = {"W": 1200, "H": 380, "scale": 0.84, "stroke": 1.5, "dot_r": 3.4, "corner": 16}
SOCIAL = {"W": 1280, "H": 640, "scale": 1.22, "stroke": 2.2, "dot_r": 5.0, "corner": 0}

SCENE = Template("""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 $W $H" width="$W" height="$H" role="img" aria-label="Pigeondome — controle inteligente de pombos">
  <title>Pigeondome — controle inteligente de pombos</title>
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="$bg0"/><stop offset="1" stop-color="$bg1"/></linearGradient>
    <radialGradient id="glow" cx="$cx" cy="$cy" r="$glow_r" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="$accent" stop-opacity="$glow_op"/><stop offset="1" stop-color="$accent" stop-opacity="0"/></radialGradient>
    <linearGradient id="hz" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="$accent" stop-opacity="0"/><stop offset="0.5" stop-color="$accent" stop-opacity="0.5"/><stop offset="1" stop-color="$accent" stop-opacity="0"/></linearGradient>
    <clipPath id="round"><rect width="$W" height="$H" rx="$corner"/></clipPath>
    <style>
      @media (prefers-reduced-motion: no-preference) {
        .arc { animation: breathe 6s ease-in-out infinite; }
        .a2 { animation-delay: 0.6s; }
        .a3 { animation-delay: 1.2s; }
        .a4 { animation-delay: 1.8s; }
        .a5 { animation-delay: 2.4s; }
        @keyframes breathe { 0%, 100% { opacity: 0.55; } 50% { opacity: 1; } }
      }
    </style>
  </defs>
  <g clip-path="url(#round)">
    <rect width="$W" height="$H" fill="url(#bg)"/>
    <rect width="$W" height="$H" fill="url(#glow)"/>
    <rect x="0" y="$hy" width="$W" height="1.5" fill="url(#hz)"/>
    $arcs
    $dots
    <g transform="translate($lx $ly) scale($scale)">$logo</g>
  </g>
  $border_rect
</svg>
""")


def read_logo(name):
    text = (SVG_DIR / name).read_text(encoding="utf-8")
    box = re.search(r'viewBox="0 0 ([0-9.]+) ([0-9.]+)"', text)
    body = re.search(r"<svg[^>]*>(.*)</svg>\s*$", text, re.DOTALL)
    if not box or not body or GROUP not in text:
        sys.exit(f"{name}: formato inesperado (viewBox e grupo do símbolo)")
    inner = re.sub(r"<title>.*?</title>", "", body.group(1), flags=re.DOTALL)
    return float(box.group(1)), float(box.group(2)), inner.strip()


def compose(theme, logo, W, H, scale, stroke, dot_r, corner):
    logo_w, logo_h, inner = logo
    lx, ly = (W - logo_w * scale) / 2, (H - logo_h * scale) / 2
    cx, cy = lx + DOME_X * scale, ly + DOME_Y * scale
    first = REACH * scale
    radii = [round(first * k) for k in STEPS]
    arcs = []
    for i, r in enumerate(radii):
        arcs.append(
            f'<path class="arc a{i + 1}" d="M{cx - r:.1f} {cy:.1f}A{r} {r} 0 0 1 {cx + r:.1f} {cy:.1f}" '
            f'fill="none" stroke="{theme["accent"]}" stroke-width="{stroke}" stroke-opacity="{theme["arcs"][i]}"/>'
        )
    dots = []
    for index, degrees in DOTS:
        angle = math.radians(degrees)
        x, y = cx + radii[index] * math.cos(angle), cy - radii[index] * math.sin(angle)
        if not (12 < x < W - 12 and 12 < y < H - 12):
            continue
        dots.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{dot_r * 2.6:.1f}" fill="{theme["accent"]}" opacity="0.16"/>'
        )
        dots.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{dot_r}" fill="{theme["accent"]}"/>'
        )
    border = (
        f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="{corner}" fill="none" stroke="{theme["border"]}"/>'
        if corner
        else ""
    )
    return SCENE.substitute(
        bg0=theme["bg0"],
        bg1=theme["bg1"],
        accent=theme["accent"],
        glow_op=theme["glow_op"],
        W=W,
        H=H,
        cx=f"{cx:.1f}",
        cy=f"{cy:.1f}",
        glow_r=round(W * 0.34),
        corner=corner,
        hy=f"{cy - 0.75:.1f}",
        arcs="\n    ".join(arcs),
        dots="\n    ".join(dots),
        lx=f"{lx:.1f}",
        ly=f"{ly:.1f}",
        scale=scale,
        logo=inner,
        border_rect=border,
    )


def main():
    light = read_logo("pigeondome-logo-vertical.svg")
    dark = read_logo("pigeondome-logo-vertical-negativo.svg")
    outputs = {
        "banner-light.svg": compose(LIGHT, light, **BANNER),
        "banner-dark.svg": compose(DARK, dark, **BANNER),
        "social-preview.svg": compose(DARK, dark, **SOCIAL),
    }
    for name, content in outputs.items():
        (OUT_DIR / name).write_text(content, encoding="utf-8", newline="\n")
        print(f"{name}  {len(content) // 1024} KB")
    print(f"primeiro arco do banner: raio {round(REACH * BANNER['scale'])}")


if __name__ == "__main__":
    main()
