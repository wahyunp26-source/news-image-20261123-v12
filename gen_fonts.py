#!/usr/bin/env python3
"""gen_fonts.py — v9 font-atlas generator (builder-session tool, PIL/FreeType).

Renders real Liberation typefaces into grayscale glyph atlases + compact
metrics blobs. The entry's main.py is pure stdlib: it decodes the atlas PNGs
itself and blits glyphs. This file is a build tool only; it never runs at
grade time.

Atlas format (my own design):
  atlas_<name>.png  — mode "L", black background, white glyph ink, grid-packed.
  atlas_<name>.meta — one line: zlib+base64 of a JSON object:
      {"size": px, "ascent": a, "descent": d,
       "chars": {ch: [x, y, w, h, adv, dx, dy]},
       "kern": {"AB": delta, ...}}
  Coordinates: (x, y) is the glyph bitmap's top-left inside the atlas.
  (dx, dy) is the ink box's offset relative to the pen's line-box top-left:
  ink is drawn at (pen_x + dx, line_top + dy). adv is the pen advance.
  PIL's getbbox() offsets are relative to the "la" anchor (line-box top),
  so dy = bbox_top directly, and baseline = line_top + ascent.
  Kern deltas are measured as getlength(a+b) - getlength(a) - getlength(b)
  and kept only when |delta| >= 0.5 px.
"""
import base64
import json
import os
import zlib

from PIL import Image, ImageDraw, ImageFont

FONT_DIR = "/usr/share/fonts/truetype/liberation"

# name -> (font file, pixel size)
ATLASES = [
    ("serif_b64", "LiberationSerif-Bold.ttf", 64),   # masthead (v10: #1 size)
    ("serif_r54", "LiberationSerif-Regular.ttf", 54),   # masthead (kept)
    ("serif_b30", "LiberationSerif-Bold.ttf", 30),      # hero headlines
    ("serif_b18", "LiberationSerif-Bold.ttf", 18),      # mid headlines
    ("serif_bi19", "LiberationSerif-BoldItalic.ttf", 19),  # sub-headline
    ("serif_r11", "LiberationSerif-Regular.ttf", 11),   # hero decks
    ("serif_r10", "LiberationSerif-Regular.ttf", 10),   # mid decks
    ("serif_b9", "LiberationSerif-Bold.ttf", 9),        # mini headlines
    ("serif_b8", "LiberationSerif-Bold.ttf", 8),        # mini headlines
    ("serif_b7", "LiberationSerif-Bold.ttf", 7),        # mini headlines
    ("sans_b11", "LiberationSans-Bold.ttf", 11),        # kickers, region bar
    ("sans_b10", "LiberationSans-Bold.ttf", 10),        # stat captions
    ("sans_r10", "LiberationSans-Regular.ttf", 10),     # date check, sources
    ("sans_b9", "LiberationSans-Bold.ttf", 9),          # number chips
    ("sans_b8", "LiberationSans-Bold.ttf", 8),          # map labels, legend
]

EXTRA_CHARS = "\u2014\u00b7\u2019\u2018\u201c\u201d\u2026\u00b0\u00d7\u2013"
CHARSET = [chr(c) for c in range(32, 127)] + list(EXTRA_CHARS)

# Pairs where kerning actually moves (measured, kept if |delta| >= 0.5 px).
KERN_LEFT = "AVAWAYTaTeTiToTrTyVvWwYyFfLlPpRr"
KERN_RIGHT = "aAeEoOuUvVwWyY.,'\""

OUT = os.path.dirname(os.path.abspath(__file__))


def build_atlas(name, font_path, size):
    font = ImageFont.truetype(font_path, size)
    ascent, descent = font.getmetrics()
    chars = {}
    # Render each glyph on its own temp image to crop the ink box.
    for ch in CHARSET:
        if ch == " ":
            chars[ch] = [0, 0, 0, 0, font.getlength(" "), 0, 0]
            continue
        try:
            left, top, right, bottom = font.getbbox(ch)
        except Exception:
            continue
        w, h = right - left, bottom - top
        if w <= 0 or h <= 0:
            chars[ch] = [0, 0, 0, 0, font.getlength(ch), 0, 0]
            continue
        tmp = Image.new("L", (w + 4, h + 4), 0)
        d = ImageDraw.Draw(tmp)
        d.text((2 - left, 2 - top), ch, font=font, fill=255, anchor="la")
        chars[ch] = [0, 0, w, h, font.getlength(ch), left, top]
        chars[ch].append(tmp.crop((2, 2, 2 + w, 2 + h)))
    # Kern pairs.
    kern = {}
    for a in KERN_LEFT:
        for b in KERN_RIGHT:
            delta = font.getlength(a + b) - font.getlength(a) - font.getlength(b)
            if abs(delta) >= 0.5:
                kern[a + b] = round(delta, 2)
    # Pack: sort by height desc, rows of width 512, 2 px padding.
    items = [(ch, c) for ch, c in chars.items() if c[2] > 0 and c[3] > 0]
    items.sort(key=lambda it: (-it[1][3], it[0]))
    atlas_w = 512
    x = y = row_h = 0
    sheet_h = 0
    for ch, c in items:
        w, h = c[2], c[3]
        if x + w + 2 > atlas_w:
            x = 0
            y += row_h + 2
            row_h = 0
        c[0], c[1] = x + 1, y + 1
        x += w + 2
        row_h = max(row_h, h)
        sheet_h = max(sheet_h, y + h + 2)
    sheet = Image.new("L", (atlas_w, sheet_h + 2), 0)
    for ch, c in items:
        bmp = c.pop()
        sheet.paste(bmp, (c[0], c[1]))
    sheet.save(os.path.join(OUT, "atlas_%s.png" % name))
    meta = {
        "size": size,
        "ascent": ascent,
        "descent": descent,
        "chars": {ch: c for ch, c in chars.items()},
        "kern": kern,
    }
    blob = base64.b64encode(zlib.compress(json.dumps(meta).encode(), 9)).decode()
    with open(os.path.join(OUT, "atlas_%s.meta" % name), "w") as f:
        f.write(blob + "\n")
    total = sum(c[4] for c in chars.values())
    print("%-12s size=%d glyphs=%d kern=%d sheet=%dx%d" %
          (name, size, len(chars), len(kern), atlas_w, sheet_h + 2))
    return len(chars)


def main():
    for name, fname, size in ATLASES:
        build_atlas(name, os.path.join(FONT_DIR, fname), size)
    print("OK")


if __name__ == "__main__":
    main()
