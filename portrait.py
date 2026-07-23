"""
portrait.py
Convert a photo into terminal-flavored portrait art, emitted as SVG fragments.

Renderers:
  - pixel   : colored, optionally dithered pixel grid (hero look)
  - ascii   : classic luminance ASCII
  - braille : ultra high detail 2x4 braille packing

Modes (color grading):
  - truecolor : real photo colors, maximum photographic detail
  - neon      : luminance mapped onto a cyberpunk ramp (keeps ALL detail as brightness)
  - duotone   : real color blended toward neon (a graded-photo look)

Detail is protected by a headshot crop, unsharp masking, and a dense grid.
"""

from __future__ import annotations
from PIL import Image, ImageOps, ImageFilter
import html


def _lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


# cyberpunk neon ramp: deep indigo shadow -> magenta -> violet -> cyan highlight
NEON_STOPS = [
    (0.00, (0x07, 0x04, 0x18)),
    (0.28, (0x5e, 0x0e, 0x8f)),
    (0.52, (0xd6, 0x24, 0xc0)),
    (0.72, (0x8a, 0x5c, 0xff)),
    (0.88, (0x2b, 0xb8, 0xff)),
    (1.00, (0x9c, 0xf7, 0xff)),
]


def neon_map(lum: float) -> tuple[int, int, int]:
    lum = max(0.0, min(1.0, lum))
    for i in range(len(NEON_STOPS) - 1):
        p0, c0 = NEON_STOPS[i]
        p1, c1 = NEON_STOPS[i + 1]
        if p0 <= lum <= p1:
            t = 0 if p1 == p0 else (lum - p0) / (p1 - p0)
            return _lerp(c0, c1, t)
    return NEON_STOPS[-1][1]


def _lum(rgb) -> float:
    return (0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]) / 255.0


def _hex(rgb) -> str:
    return "#%02x%02x%02x" % (rgb[0], rgb[1], rgb[2])


def _grade(rgb, mode):
    if mode == "truecolor":
        return rgb
    lum = _lum(rgb)
    if mode == "neon":
        return neon_map(lum)
    # duotone: keep real color but push toward the neon ramp
    return _lerp(rgb, neon_map(lum), 0.5)


# panel background the portrait fades into (matches generate.py DARK panel)
PANEL_BG = (0x0a, 0x06, 0x18)


def _oval_alpha(nx, ny, cx=0.5, cy=0.43, rx=0.53, ry=0.63):
    """Soft elliptical vignette: 1 at the face, fading to 0 past the head."""
    d = (((nx - cx) / rx) ** 2 + ((ny - cy) / ry) ** 2) ** 0.5
    lo, hi = 0.86, 1.14
    if d <= lo:
        return 1.0
    if d >= hi:
        return 0.0
    t = (d - lo) / (hi - lo)
    return 1.0 - (t * t * (3 - 2 * t))


# ----------------------------------------------------------------------------
# loading: headshot crop + detail boost
# ----------------------------------------------------------------------------

def load_square(path: str, aspect=(3, 4), long_side: int = 620) -> Image.Image:
    """Crop to a headshot aspect focused slightly above center, sharpen, boost contrast."""
    img = Image.open(path)
    img = ImageOps.exif_transpose(img).convert("RGB")
    tw = round(long_side * aspect[0] / aspect[1])
    img = ImageOps.fit(img, (tw, long_side), Image.LANCZOS, centering=(0.5, 0.40))
    img = ImageOps.autocontrast(img, cutoff=1)
    img = img.filter(ImageFilter.UnsharpMask(radius=2.2, percent=135, threshold=2))
    return img


def _placeholder(long_side: int = 620) -> Image.Image:
    tw = round(long_side * 3 / 4)
    img = Image.new("RGB", (tw, long_side), (10, 6, 24))
    px = img.load()
    cx, cy = tw * 0.5, long_side * 0.42
    for y in range(long_side):
        for x in range(tw):
            dx = (x - cx) / (tw * 0.5)
            dy = (y - cy) / (long_side * 0.5)
            if (dx * dx + (dy + 0.1) ** 2) < 0.5:
                px[x, y] = neon_map(0.4 + max(0.0, 0.5 - dx * dx) * 0.6)
    return img


def _rows(img, cols, cellw, cellh):
    return max(1, round(cols * (img.height / img.width) * (cellw / cellh)))


# ----------------------------------------------------------------------------
# renderers
# ----------------------------------------------------------------------------

def render_pixel(img, cols: int = 74, cell: int = 5, dither: bool = False,
                 mode: str = "duotone") -> tuple[str, int, int]:
    rows = _rows(img, cols, cell, cell)
    small = img.resize((cols, rows), Image.LANCZOS)
    if dither:
        small = small.quantize(colors=96, dither=Image.FLOYDSTEINBERG).convert("RGB")
    px = small.load()

    def cell_hex(x, y):
        a = _oval_alpha((x + 0.5) / cols, (y + 0.5) / rows)
        if a <= 0.02:
            return None
        return _hex(_lerp(PANEL_BG, _grade(px[x, y], mode), a))

    parts = []
    for y in range(rows):
        run_start = 0
        while run_start < cols:
            hx = cell_hex(run_start, y)
            x2 = run_start + 1
            while x2 < cols and cell_hex(x2, y) == hx:
                x2 += 1
            if hx is not None:
                gx = run_start * cell
                gw = (x2 - run_start) * cell
                parts.append(f'<rect x="{gx}" y="{y*cell}" width="{gw}" height="{cell}" fill="{hx}"/>')
            run_start = x2
    w, h = cols * cell, rows * cell
    inner = f'<g class="portrait pixel" filter="url(#pxGlow)">{"".join(parts)}</g>'
    return inner, w, h


ASCII_RAMP = " .`:-_,^=;><+!rc*/z?sLTv)J7(|Fi{C}fI31tlu[neoZ5Yxjya]2ESwqkP6h9d4VpOGbUAKXHm8RD#$Bg0MNWQ%&@"


def render_ascii(img, cols: int = 82, cw: int = 7, ch: int = 12,
                 mode: str = "neon") -> tuple[str, int, int]:
    rows = _rows(img, cols, cw, ch)
    small = img.resize((cols, rows), Image.LANCZOS)
    px = small.load()
    n = len(ASCII_RAMP) - 1
    lines = []
    for y in range(rows):
        spans = []
        for x in range(cols):
            a = _oval_alpha((x + 0.5) / cols, (y + 0.5) / rows)
            if a < 0.12:
                spans.append('<tspan> </tspan>')
                continue
            lum = _lum(px[x, y])
            glyph = ASCII_RAMP[round(lum * n)]
            col = _lerp(PANEL_BG, _grade(px[x, y], mode), a)
            spans.append(f'<tspan fill="{_hex(col)}">{html.escape(glyph)}</tspan>')
        lines.append(f'<text x="0" y="{(y+1)*ch}" xml:space="preserve" class="ascii-line">'
                     f'{"".join(spans)}</text>')
    w, h = cols * cw, rows * ch
    inner = f'<g class="portrait ascii" filter="url(#pxGlow)">{"".join(lines)}</g>'
    return inner, w, h


BRAILLE_BASE = 0x2800
_DOTS = [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2), (0, 3), (1, 3)]


def render_braille(img, cols: int = 56, cw: int = 8, ch: int = 13,
                   mode: str = "neon") -> tuple[str, int, int]:
    rows = _rows(img, cols, cw, ch)
    gw, gh = cols * 2, rows * 4
    small = ImageOps.autocontrast(img.resize((gw, gh), Image.LANCZOS), cutoff=2)
    px = small.load()
    vals = [_lum(px[x, y]) for y in range(gh) for x in range(gw)]
    thr = sum(vals) / len(vals) * 0.96
    lines = []
    for cy in range(rows):
        spans = []
        for cx in range(cols):
            mask, acc = 0, 0.0
            for bit, (dx, dy) in enumerate(_DOTS):
                lum = _lum(px[cx*2+dx, cy*4+dy])
                acc += lum
                if lum > thr:
                    mask |= (1 << bit)
            glyph = chr(BRAILLE_BASE + mask)
            col = _grade(px[cx*2, cy*4], mode)
            spans.append(f'<tspan fill="{_hex(col)}">{html.escape(glyph)}</tspan>')
        lines.append(f'<text x="0" y="{(cy+1)*ch}" xml:space="preserve" class="braille-line">'
                     f'{"".join(spans)}</text>')
    w, h = cols * cw, rows * ch
    inner = f'<g class="portrait braille" filter="url(#pxGlow)">{"".join(lines)}</g>'
    return inner, w, h


RENDERERS = {"pixel": render_pixel, "ascii": render_ascii, "braille": render_braille}
