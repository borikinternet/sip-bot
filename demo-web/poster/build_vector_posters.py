"""Build two standalone, print-ready SVG posters from the traced illustration.

The deliverables contain only SVG paths, shapes, and gradients. In particular,
the illustration, Cyrillic lettering, and QR modules are all actual vector paths.
"""

from pathlib import Path
import re
import sys

import qrcode
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont


HERE = Path(__file__).resolve().parent
ART_PATHS = {
    "dark": HERE / "vasilisa-art-traced.svg",
    "light": HERE / "vasilisa-light-art-traced.svg",
}
URL = "https://demo.libnas.ru/"


def art_paths(theme: str) -> str:
    source = ART_PATHS[theme].read_text(encoding="utf-8")
    body = source.split("<svg", 1)[1].split(">", 1)[1].rsplit("</svg>", 1)[0]
    if "<image" in body or "foreignObject" in body:
        raise ValueError("Traced illustration is not fully vector")
    return body


def outlined_text(value: str, x: float, baseline: float, size: float, color: str,
                  font: TTFont, tracking: float = 0) -> str:
    units = font["head"].unitsPerEm
    glyph_set = font.getGlyphSet()
    cmap = font.getBestCmap()
    scale = size / units
    cursor = 0
    paths = []
    for char in value:
        glyph_name = cmap[ord(char)]
        pen = SVGPathPen(glyph_set)
        glyph_set[glyph_name].draw(pen)
        d = pen.getCommands()
        if d:
            paths.append(f'<path d="{d}" transform="translate({cursor:.2f} 0)"/>')
        cursor += font["hmtx"][glyph_name][0] + tracking / scale
    return (f'<g fill="{color}" transform="translate({x} {baseline}) '
            f'scale({scale:.7f} {-scale:.7f})">' + "".join(paths) + "</g>")


def qr_paths(qr_x: int = 78, qr_y: int = 1007) -> str:
    qr = qrcode.QRCode(version=3, error_correction=qrcode.constants.ERROR_CORRECT_H,
                       mask_pattern=2, border=0, box_size=1)
    qr.add_data(URL)
    qr.make(fit=False)
    matrix = qr.get_matrix()
    if len(matrix) != 29:
        raise ValueError("Unexpected QR version")
    runs = []
    for y, row in enumerate(matrix):
        x = 0
        while x < len(row):
            if not row[x]:
                x += 1
                continue
            end = x + 1
            while end < len(row) and row[end]:
                end += 1
            runs.append(f"M{x + 4} {y + 4}h{end - x}v1h-{end - x}z")
            x = end
    return (f'<g transform="translate({qr_x} {qr_y}) scale(7.25)" shape-rendering="crispEdges">'
            '<rect width="37" height="37" fill="#fff"/>'
            f'<path d="{" ".join(runs)}" fill="#10101b"/></g>')


def main() -> None:
    heavy = TTFont(r"C:\Windows\Fonts\ariblk.ttf")
    bold = TTFont(r"C:\Windows\Fonts\arialbd.ttf")
    themes = ("light",) if "--light-only" in sys.argv else ("dark", "light")
    for theme in themes:
        light = theme == "light"
        art = art_paths(theme)
        ink = "#241D48" if light else "#FFFFFF"
        accent = "#4A318C" if light else "#D9F8FF"
        card_ink = "#23234B"
        qr = qr_paths(75, 1040) if light else qr_paths()
        footer = ([outlined_text("demo.libnas.ru", 124, 1393, 24,
                                 "#302A5A", bold)] if light else [
            outlined_text("Сканируй и звони", 81, 1338, 27, card_ink, heavy),
            outlined_text("demo.libnas.ru", 137, 1382, 21, "#3A3D71", bold),
        ])
        parts = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<svg xmlns="http://www.w3.org/2000/svg" width="280mm" height="420mm" viewBox="0 0 1024 1536" role="img" aria-label="Спроси Василису — и страницы заговорят. Сканируй и звони: demo.libnas.ru">',
            '<title>Спроси Василису — и страницы заговорят</title>',
            '<g id="vector-illustration">', art, '</g>',
            outlined_text("СПРОСИ", 50, 141, 68, ink, heavy),
            outlined_text("ВАСИЛИСУ", 50, 215, 68, ink, heavy),
            outlined_text("И страницы", 51, 301, 34, accent, bold),
            outlined_text("заговорят!", 51, 343, 34, accent, bold),
            qr,
            *footer,
            '</svg>',
        ]
        output = HERE / f"vasilisa-conference-{theme}.svg"
        output.write_text("\n".join(parts), encoding="utf-8")
        print(f"{output}: {output.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
