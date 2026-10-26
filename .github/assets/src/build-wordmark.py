"""Build the ONEXUS wordmark as pure SVG paths (no <text>, no web fonts).

Text is shaped with HarfBuzz (so kerning is the font's own) and every glyph is
converted to an outline with fontTools. The output renders identically in any
<img>, on any machine, because there is no font left to fall back from.

Needs Inter 4.1 (SIL Open Font License, github.com/rsms/inter): set INTER_DIR
to its extras/ttf folder. Then: python build-wordmark.py .github/assets
Requires: pip install fonttools uharfbuzz
"""
import os
import sys
from pathlib import Path
import uharfbuzz as hb
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

HERE = Path(__file__).resolve().parent
FONTS = Path(os.environ.get("INTER_DIR", HERE / "inter" / "extras" / "ttf"))


def shape(font_file, text, size, tracking_em=0.0, features=None):
    """Return (svg path d, advance width in px) for text set at `size` px."""
    blob = hb.Blob.from_file_path(str(font_file))
    face = hb.Face(blob)
    font = hb.Font(face)
    upem = face.upem
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf, features or {"kern": True, "liga": True})
    tt = TTFont(str(font_file))
    gs = tt.getGlyphSet()
    order = tt.getGlyphOrder()
    scale = size / upem
    track = tracking_em * upem
    x = 0.0
    parts = []
    n = len(buf.glyph_infos)
    for i, (info, pos) in enumerate(zip(buf.glyph_infos, buf.glyph_positions)):
        name = order[info.codepoint]
        pen = SVGPathPen(gs)
        # flip y (font units are y-up), place at pen position
        tp = TransformPen(pen, (scale, 0, 0, -scale, (x + pos.x_offset) * scale, -pos.y_offset * scale))
        gs[name].draw(tp)
        d = pen.getCommands()
        if d:
            parts.append(d)
        x += pos.x_advance + (track if i < n - 1 else 0)
    return " ".join(parts), x * scale


def fmt(d):
    # trim float noise to keep the file small and diff-able
    import re
    return re.sub(r"-?\d+\.\d+", lambda m: f"{float(m.group()):.2f}".rstrip("0").rstrip("."), d)


THEMES = {
    "dark": {"accent": "#4ed5d5", "word": "#eceef2", "tag": "#9ba2ad"},
    "light": {"accent": "#0e8f92", "word": "#0b0c0f", "tag": "#59606b"},
}


WS, TS, TRK, LG, GAP, SW = 76, 21.5, 0.055, 37, 30, 1.9

def build(theme):
    c = THEMES[theme]
    W, H = 1000, 220
    word_d, word_w = shape(FONTS / "InterDisplay-SemiBold.ttf", "ONEXUS", WS, tracking_em=TRK)
    tag_d, tag_w = shape(FONTS / "Inter-Regular.ttf", "An operating system for agents", TS)
    # The mark: the in-app KERNEL_MARK geometry (24-unit grid), scaled.
    cap = WS * 0.727
    block_h = cap + LG + TS * 0.53
    m = (block_h + 12) / 24           # mark spans the whole text block
    gap = GAP
    block_w = 24 * m + gap + max(word_w, tag_w)
    x0 = (W - block_w) / 2
    my = (H - 24 * m) / 2
    wx = x0 + 24 * m + gap
    # cap height of Inter Display ~0.727em; set baseline so the word+tagline block centres on the mark
    base = H / 2 - block_h / 2 + cap
    tag_base = base + LG + TS * 0.53
    node_cx, node_cy = 17.83, 6.17
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="t">
  <title id="t">ONEXUS, an operating system for agents</title>
  <defs>
    <mask id="cut" maskUnits="userSpaceOnUse" x="0" y="0" width="24" height="24">
      <rect width="24" height="24" fill="#fff"/>
      <circle cx="{node_cx}" cy="{node_cy}" r="3.3" fill="#000"/>
    </mask>
  </defs>
  <g transform="translate({x0:.2f} {my:.2f}) scale({m:.4f})" fill="{c["accent"]}">
    <circle cx="12" cy="12" r="8.25" fill="none" stroke="{c["accent"]}" stroke-width="{SW}" mask="url(#cut)"/>
    <circle cx="12" cy="12" r="3"/>
    <circle cx="{node_cx}" cy="{node_cy}" r="1.9"/>
  </g>
  <path transform="translate({wx:.2f} {base:.2f})" fill="{c["word"]}" d="{fmt(word_d)}"/>
  <path transform="translate({wx + 3:.2f} {tag_base:.2f})" fill="{c["tag"]}" d="{fmt(tag_d)}"/>
</svg>
'''
    return svg


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else HERE)
    out.mkdir(parents=True, exist_ok=True)
    for theme in THEMES:
        (out / f"wordmark-{theme}.svg").write_text(build(theme))
    print("ok")
