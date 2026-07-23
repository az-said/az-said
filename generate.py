"""
generate.py
Assemble the neofetch-style animated SVG(s) from config + live stats + portrait.

Usage:
  python3 generate.py                 # dark + light SVGs into out/
  python3 generate.py --style ascii   # override portrait style
  python3 generate.py --all-portraits # render one preview per portrait style
  python3 generate.py --static        # freeze animation (for PNG QA)
"""

from __future__ import annotations
import argparse
import datetime as dt
import os
from pathlib import Path
from zoneinfo import ZoneInfo

import portrait as P
import stats as S
from config import CONFIG

ROOT = Path(__file__).parent
OUT = ROOT / "out"
CHARW = 9.0
FONT = 15
LINEH = 22
VALUE_COL = 30

# cyberpunk neon palette (dark)
DARK = {
    "bg0": "#080512", "bg1": "#0d0820", "panel": "#0a0618",
    "border": "#ff2bd6", "border2": "#00eaff",
    "base": "#cfe9ff", "key": "#ff2bd6", "dot": "#43356b",
    "val": "#00eaff", "head": "#9a6cff", "prompt": "#5dff9f",
    "sep": "#33265a", "add": "#39ff8b", "del": "#ff5c7a", "dim": "#7c6ba8",
}
LIGHT = {
    "bg0": "#f5f2ff", "bg1": "#eee9ff", "panel": "#f7f4ff",
    "border": "#c81e9e", "border2": "#0090b8",
    "base": "#241a3a", "key": "#c81e9e", "dot": "#c9bce8",
    "val": "#0085a8", "head": "#6a3ec8", "prompt": "#0a9a52",
    "sep": "#cabfe6", "add": "#0f9d58", "del": "#d23b57", "dim": "#6a5c8e",
}


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ----------------------------------------------------------------------------
# dynamic fields
# ----------------------------------------------------------------------------

def _delta(since: str) -> str:
    start = dt.date.fromisoformat(since)
    today = dt.date.today()
    years = today.year - start.year
    months = today.month - start.month
    days = today.day - start.day
    if days < 0:
        months -= 1
        days += 30
    if months < 0:
        years -= 1
        months += 12
    return f"{years} years, {months} months, {days} days"


def uptime() -> str:
    if CONFIG.get("birth_date"):
        return _delta(CONFIG["birth_date"])
    return _delta(CONFIG["coding_since"])


def local_now() -> str:
    tz = ZoneInfo(CONFIG.get("timezone", "UTC"))
    return dt.datetime.now(tz).strftime("%H:%M %Z, %A")


# ----------------------------------------------------------------------------
# right-panel content model  -> list[ list[(text,color_key)] ]
# ----------------------------------------------------------------------------

def _row(key: str, val: str) -> list[tuple[str, str]]:
    dots = max(2, VALUE_COL - len(key) - 1)
    return [(f"{key} ", "key"), ("." * dots + " ", "dot"), (val, "val")]


def _header(word: str, width_chars: int = 46) -> list[tuple[str, str]]:
    fill = max(2, width_chars - len(word) - 1)
    return [(f"{word} ", "head"), ("-" * fill, "sep")]


def build_lines(st: dict) -> list[list[tuple[str, str]]]:
    user, host = CONFIG["user"], CONFIG["host"]
    lines: list[list[tuple[str, str]]] = []
    lines.append([(f"{user}@{host} ", "prompt"), ("-" * 34, "sep")])
    lines.append([(CONFIG.get("title_tagline", ""), "dim")])
    lines.append([("", "base")])

    lines.append(_row("Uptime", uptime()))
    lines.append(_row("Local", local_now()))
    for k, v in CONFIG["identity"]:
        lines.append(_row(k, v))
    lines.append([("", "base")])

    lines.append(_header("Languages"))
    for k, v in CONFIG["languages"]:
        lines.append(_row(k, v))
    lines.append([("", "base")])

    lines.append(_header("Hobbies"))
    for k, v in CONFIG["hobbies"]:
        lines.append(_row(k, v))
    lines.append([("", "base")])

    lines.append(_header("Contact"))
    for k, v in CONFIG["contact"]:
        lines.append(_row(k, v))
    lines.append([("", "base")])

    lines.append(_header("GitHub Stats"))
    lines.append(_row("Repos", f'{st["repos"]:,}  (Contributed {st["contributed"]:,})'))
    lines.append(_row("Commits", f'{st["commits"]:,}'))
    lines.append(_row("Stars", f'{st["stars"]:,}'))
    lines.append(_row("Followers", f'{st["followers"]:,}'))
    # lines of code with colored add/del
    loc = [
        ("Lines of Code ", "key"),
        ("." * max(2, VALUE_COL - 14) + " ", "dot"),
        (f'{st["loc_total"]:,} (', "val"),
        (f'{st["loc_add"]:,}++', "add"),
        (", ", "val"),
        (f'{st["loc_del"]:,}--', "del"),
        (")", "val"),
    ]
    lines.append(loc)
    return lines


def line_chars(segs) -> int:
    return sum(len(t) for t, _ in segs)


# ----------------------------------------------------------------------------
# SVG assembly
# ----------------------------------------------------------------------------

def render_svg(theme: dict, portrait_inner: str, pw: int, ph: int,
               lines, static: bool) -> str:
    left_x, top_y = 28, 60
    panel_x = left_x + pw + 60
    max_chars = max(line_chars(l) for l in lines)
    panel_w = int(max_chars * CHARW) + 30
    width = panel_x + panel_w + 30
    panel_h = len(lines) * LINEH + 30
    height = max(top_y + ph + 40, top_y + panel_h + 30)

    # portrait vertical centering
    py = top_y + max(0, (panel_h - ph) // 2)

    defs = f'''
  <defs>
    <linearGradient id="frame" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{theme['border']}"/>
      <stop offset="1" stop-color="{theme['border2']}"/>
    </linearGradient>
    <filter id="pxGlow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="1.1" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <filter id="txtGlow" x="-10%" y="-10%" width="120%" height="120%">
      <feGaussianBlur stdDeviation="0.5" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <pattern id="scan" width="1" height="3" patternUnits="userSpaceOnUse">
      <rect width="1" height="3" fill="transparent"/>
      <rect width="1" height="1" fill="#ffffff" opacity="0.035"/>
    </pattern>
    <clipPath id="scanIn"><rect x="{left_x}" y="{py}" width="{pw}" height="{0 if not static else ph}">
      {'' if static else f'<animate attributeName="height" from="0" to="{ph}" begin="0.2s" dur="1.6s" fill="freeze"/>'}
    </rect></clipPath>
  </defs>'''

    css = f'''
  <style>
    text {{ font-family: ui-monospace,'SF Mono','JetBrains Mono',Menlo,Consolas,monospace;
            font-size:{FONT}px; dominant-baseline:middle; }}
    .cursor {{ animation: blink 1s steps(1) infinite; }}
    @keyframes blink {{ 50% {{ opacity:0; }} }}
    .title {{ font-size:20px; font-weight:700; letter-spacing:1px; }}
    @keyframes glowpulse {{ 0%,100% {{ opacity:0.85 }} 50% {{ opacity:1 }} }}
    .frame {{ animation: glowpulse 4s ease-in-out infinite; }}
  </style>'''

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" fill="none">',
        defs, css,
        f'<rect width="{width}" height="{height}" rx="16" fill="{theme["bg0"]}"/>',
        f'<rect x="6" y="6" width="{width-12}" height="{height-12}" rx="12" '
        f'fill="{theme["panel"]}" stroke="url(#frame)" stroke-width="2" class="frame"/>',
        f'<rect width="{width}" height="{height}" rx="16" fill="url(#scan)"/>',
        # window dots
        f'<circle cx="26" cy="26" r="6" fill="{theme["del"]}"/>'
        f'<circle cx="46" cy="26" r="6" fill="#ffcf4a"/>'
        f'<circle cx="66" cy="26" r="6" fill="{theme["add"]}"/>',
        f'<text x="{width/2}" y="27" text-anchor="middle" fill="{theme["dim"]}" '
        f'font-size="12">{esc(CONFIG["user"])}@{esc(CONFIG["host"])} : neofetch</text>',
        # portrait with scan-in wipe
        f'<g clip-path="url(#scanIn)"><g transform="translate({left_x},{py})">{portrait_inner}</g></g>',
    ]

    # right panel typed lines
    start = 0.3
    for i, segs in enumerate(lines):
        ly = top_y + 18 + i * LINEH
        nchars = max(1, line_chars(segs))
        lw = int(nchars * CHARW) + 8
        dur = max(0.25, nchars * 0.02)
        # build tspans
        tspans = []
        for text, ck in segs:
            if text == "":
                continue
            tspans.append(f'<tspan fill="{theme[ck]}">{esc(text)}</tspan>')
        text_el = (f'<text x="{panel_x}" y="{ly}" xml:space="preserve" '
                   f'filter="url(#txtGlow)">{"".join(tspans)}</text>')
        if static:
            parts.append(text_el)
        else:
            cid = f"typ{i}"
            parts.append(
                f'<clipPath id="{cid}"><rect x="{panel_x}" y="{ly-LINEH/2}" '
                f'width="0" height="{LINEH}">'
                f'<animate attributeName="width" from="0" to="{lw}" '
                f'begin="{start:.2f}s" dur="{dur:.2f}s" fill="freeze"/></rect></clipPath>'
            )
            parts.append(f'<g clip-path="url(#{cid})">{text_el}</g>')
            start += dur * 0.85

    # blinking prompt cursor at the bottom
    cy = top_y + 18 + len(lines) * LINEH
    cur_begin = start + 0.1
    cur_attrs = '' if static else f'opacity="0"'
    cur_anim = '' if static else (
        f'<animate attributeName="opacity" from="0" to="1" begin="{cur_begin:.2f}s" '
        f'dur="0.01s" fill="freeze"/>')
    parts.append(
        f'<text x="{panel_x}" y="{cy}" fill="{theme["prompt"]}" {cur_attrs}>'
        f'{cur_anim}{esc(CONFIG["user"])}@{esc(CONFIG["host"])}:~$ '
        f'<tspan class="cursor" fill="{theme["val"]}">&#9608;</tspan></text>'
    )
    parts.append("</svg>")
    return "\n".join(parts)


# ----------------------------------------------------------------------------
# driver
# ----------------------------------------------------------------------------

def make_portrait(style: str, mode: str | None = None):
    photo = ROOT / CONFIG["photo"]
    img = P.load_square(str(photo)) if photo.exists() else P._placeholder()
    mode = mode or CONFIG.get("portrait_mode", "duotone")
    if style == "pixel":
        return P.render_pixel(img, mode=mode)
    if style == "ascii":
        return P.render_ascii(img, mode=mode)
    if style == "braille":
        return P.render_braille(img, mode=mode)
    raise ValueError(style)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--style", default=CONFIG["portrait_style"])
    ap.add_argument("--mode", default=None)
    ap.add_argument("--name", default=None, help="output basename for a variant")
    ap.add_argument("--all-portraits", action="store_true")
    ap.add_argument("--compare", action="store_true")
    ap.add_argument("--static", action="store_true")
    args = ap.parse_args()

    if args.compare:
        OUT.mkdir(exist_ok=True)
        st = S.collect()
        lines = build_lines(st)
        combos = [("pixel", "truecolor"), ("pixel", "neon"), ("pixel", "duotone"),
                  ("braille", "neon"), ("ascii", "neon")]
        for style, mode in combos:
            inner, pw, ph = make_portrait(style, mode)
            svg = render_svg(DARK, inner, pw, ph, lines, static=True)
            fn = OUT / f"cmp_{style}_{mode}.svg"
            fn.write_text(svg)
            print(f"[compare] {fn.relative_to(ROOT)}  ({pw}x{ph})")
        return

    OUT.mkdir(exist_ok=True)
    st = S.collect()
    if st.get("is_placeholder"):
        print("[stats] using placeholder values (set GH_USERNAME + GH_TOKEN for live)")
    lines = build_lines(st)

    styles = ["pixel", "ascii", "braille"] if args.all_portraits else [args.style]
    for style in styles:
        inner, pw, ph = make_portrait(style)
        for name, theme in (("dark", DARK), ("light", LIGHT)):
            svg = render_svg(theme, inner, pw, ph, lines, args.static)
            if args.all_portraits:
                fn = OUT / f"preview_{style}_{name}.svg"
            elif args.name:
                fn = OUT / f"{args.name}_{name}.svg"
            else:
                fn = OUT / f"{name}_mode.svg"
            fn.write_text(svg)
            print(f"[write] {fn.relative_to(ROOT)}  ({pw}x{ph} portrait, {len(svg)//1024}kb)")


if __name__ == "__main__":
    main()
