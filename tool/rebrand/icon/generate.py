#!/usr/bin/env python3
"""Generates the fork's icon files from one geometry.

The mark is a roof over an X with a node at the crossing. Every output lands in
tool/rebrand/files/ under its repository path; rebrand.py copies those files
into the tree. Run this only after changing the icon, then commit the outputs.
Requires Inkscape (PNG rendering) and Pillow (ICO packing).
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
FILES = HERE.parent / "files"
INKSCAPE = os.environ.get("INKSCAPE", shutil.which("inkscape") or r"C:\Program Files\Inkscape\bin\inkscape.exe")

TEAL = "#109E92"
ORANGE = "#FF7A00"
WHITE = "#FFFFFF"
GREY = "#9AA0A6"

# Android adaptive icon space: 432 units = 108dp; the launcher shows the middle
# 288 units (72dp) and keeps the middle 264 units (66dp) inside every mask.
SIZE = 432
VISIBLE = (72, 72, 288, 288)
# Small icons (tray, 16-48 px) crop closer so the mark stays legible.
TIGHT = (106, 102, 220, 220)

STROKE = 22.2
ROOF = "M137.6,207.2 L216,128.8 L294.4,207.2"
CROSS = ("M171.6,207.2 L260.4,296", "M260.4,207.2 L171.6,296")
NODE = (216, 251.6, 17.8, 7.4)  # cx, cy, r, ring width


def mark_svg(background: str, stroke: str, node: str, rounded: float = 0,
             view: tuple[float, float, float, float] = (0, 0, SIZE, SIZE)) -> str:
    x, y, w, h = view
    cx, cy, r, ring = NODE
    radius = w * rounded
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x} {y} {w} {h}">
  <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{background}"/>
  <g fill="none" stroke="{stroke}" stroke-width="{STROKE}" stroke-linecap="round" stroke-linejoin="round">
    <path d="{ROOF}"/>
    <path d="{CROSS[0]}"/>
    <path d="{CROSS[1]}"/>
  </g>
  <circle cx="{cx}" cy="{cy}" r="{r}" fill="{node}" stroke="{background}" stroke-width="{ring}"/>
</svg>
"""


def stroke_path(data: str, color: str, width: float) -> str:
    return f"""  <path
      android:pathData="{data.replace(' ', '')}"
      android:strokeWidth="{width}"
      android:fillColor="#00000000"
      android:strokeColor="{color}"
      android:strokeLineCap="round"
      android:strokeLineJoin="round"/>
"""


def vector_drawable(size_dp: int) -> str:
    """Foreground mark as an Android VectorDrawable in the 432-unit space."""
    cx, cy, r, ring = NODE
    outer = r + ring / 2
    circle = (f"M{cx - outer},{cy}a{outer},{outer} 0,1 1,{2 * outer},0"
              f"a{outer},{outer} 0,1 1,{-2 * outer},0z")
    inner = r - ring / 2
    dot = (f"M{cx - inner},{cy}a{inner},{inner} 0,1 1,{2 * inner},0"
           f"a{inner},{inner} 0,1 1,{-2 * inner},0z")
    return (f"""<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="{size_dp}dp"
    android:height="{size_dp}dp"
    android:viewportWidth="{SIZE}"
    android:viewportHeight="{SIZE}">
"""
            + stroke_path(ROOF, WHITE, STROKE)
            + "".join(stroke_path(line, WHITE, STROKE) for line in CROSS)
            + f"""  <path android:fillColor="{TEAL}" android:pathData="{circle}"/>
  <path android:fillColor="{ORANGE}" android:pathData="{dot}"/>
</vector>
""")


def background_drawable() -> str:
    return f"""<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="108dp"
    android:height="108dp"
    android:viewportWidth="{SIZE}"
    android:viewportHeight="{SIZE}">
  <path android:fillColor="{TEAL}" android:pathData="M0,0h{SIZE}v{SIZE}h-{SIZE}z"/>
</vector>
"""


def render(svg: str, size: int) -> Image.Image:
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory, "icon.svg")
        target = Path(directory, "icon.png")
        source.write_text(svg, encoding="utf-8")
        subprocess.run([INKSCAPE, str(source), "--export-type=png",
                        f"--export-filename={target}", f"--export-width={size}",
                        f"--export-height={size}"], check=True, capture_output=True)
        image = Image.open(target)
        image.load()
        return image.convert("RGBA")


def ico(svg: str, sizes: list[int]) -> bytes:
    images = [render(svg, size) for size in sorted(sizes, reverse=True)]
    buffer = io.BytesIO()
    images[0].save(buffer, format="ICO", sizes=[image.size for image in images],
                   append_images=images[1:])
    return buffer.getvalue()


def write(path: str, data: bytes | str) -> None:
    target = FILES / path
    target.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        data = data.encode("utf-8")
    target.write_bytes(data)
    print(f"wrote {target.relative_to(HERE.parents[2]).as_posix()}")


def png(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def main() -> None:
    app = mark_svg(TEAL, WHITE, ORANGE, view=VISIBLE)
    tray_on = mark_svg(TEAL, WHITE, ORANGE, rounded=0.22, view=TIGHT)
    tray_off = mark_svg(WHITE, TEAL, GREY, rounded=0.22, view=TIGHT)
    (HERE / "icon.svg").write_text(mark_svg(TEAL, WHITE, ORANGE), encoding="utf-8")

    res = "android/app/src/main/res"
    write(f"{res}/drawable/ic_foreground.xml", vector_drawable(108))
    write(f"{res}/drawable/ic_background.xml", background_drawable())
    # Android 12 splash icons use the same 2/3 safe zone as adaptive icons.
    write(f"{res}/drawable/ic_splash_icon.xml", vector_drawable(288))
    write(f"{res}/drawable-nodpi/traffic_app_icon.png", png(render(app, 512)))
    write("assets/app_icon/blue.png", png(render(app, 512)))
    write("assets/logo.png", png(render(app, 1024)))
    write("windows/runner/resources/app_icon.ico", ico(app, [16, 24, 32, 48, 64, 128, 256]))
    tray_sizes = [16, 24, 32, 48, 64, 96, 128, 256]
    write("assets/icon/tray_running.ico", ico(tray_on, tray_sizes))
    write("assets/icon/tray_running.png", png(render(tray_on, 64)))
    write("assets/icon/tray_not_running.ico", ico(tray_off, tray_sizes))
    write("assets/icon/tray_not_running.png", png(render(tray_off, 64)))


if __name__ == "__main__":
    main()
