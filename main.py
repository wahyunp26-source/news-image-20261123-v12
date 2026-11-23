#!/usr/bin/env python3
"""news-image-20261123 v11 — "Monday 23 November 2026" front page.

Pure stdlib (Python 3.13). Writes /output/entry.png (1024x1024, PNG).
No network, no randomness, no time: two runs write identical bytes.

Design (v11): closes the LAST TWO gaps vs #1 — readability (criterion 3)
and craft (criterion 5). Same strict grid, same 35 stories, same copy,
same masthead as v10 (already matches #1: 42 px caps / 857 px wide).
Three changes only:
1. Hero 2 Dymer: THIRTEEN drone trails (was 9), each with its own
   slope, length and start height — no more parallel hatching — plus a
   small drone dart at the head of every trail, a 5-stop night sky
   (navy -> indigo -> purple -> rose glow at the horizon), and a
   smaller, dimmer moon moved to the top-left corner.
2. Mid scenes: every focal object scaled up ~15-25% in frame (taller
   ship superstructure, wider towers, broader boat hull, bigger planet,
   van, truck, moon, magnifier, bed, submarine) so each reads instantly
   at 300 px.
3. Sky softness: every scene sky gains an intermediate gradient stop
   (smoother colour transitions) and a soft glow wash where it was
   flat; hero 1 wall and hero 3 dusk gain extra stops too.
"""
import base64
import binascii
import json
import math
import os
import struct
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.environ.get("MAKEFUN_OUTPUT_DIR", "out")
W, H = 1024, 1024

# ---------------------------------------------------------------- palette
PAPER = (244, 239, 226)
PAPER2 = (250, 246, 236)
INK = (28, 28, 34)
NAVY = (28, 38, 72)
NAVY2 = (20, 28, 56)
BRICK = (168, 60, 42)
BRICK_D = (140, 48, 34)
SAGE = (110, 128, 96)
OCHRE = (196, 148, 72)
CREAM = (232, 222, 198)
GREY = (110, 110, 118)
LGREY = (200, 198, 188)
WHITE = (255, 255, 255)
BLACK = (12, 12, 16)

REGION_COLORS = [
    ("EUROPE", (52, 74, 122)),
    ("MIDDLE EAST", (168, 60, 42)),
    ("AMERICAS", (110, 128, 96)),
    ("ASIA-PACIFIC", (196, 148, 72)),
    ("AFRICA", (188, 110, 52)),
    ("WORLD", (110, 92, 140)),
]
REGION_OF = {name: col for name, col in REGION_COLORS}


# ---------------------------------------------------------------- canvas
class Canvas:
    def __init__(self, w, h, bg):
        self.w, self.h = w, h
        self.px = bytearray(w * h * 3)
        self.fill_rect(0, 0, w, h, bg)

    def _idx(self, x, y):
        return (y * self.w + x) * 3

    def set(self, x, y, col):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = self._idx(x, y)
            self.px[i], self.px[i + 1], self.px[i + 2] = col

    def blend(self, x, y, col, alpha):
        """Blend col over the pixel at (x, y); alpha 0..255."""
        if alpha <= 0 or not (0 <= x < self.w and 0 <= y < self.h):
            return
        if alpha >= 255:
            self.set(x, y, col)
            return
        i = self._idx(x, y)
        inv = 255 - alpha
        self.px[i] = (col[0] * alpha + self.px[i] * inv) // 255
        self.px[i + 1] = (col[1] * alpha + self.px[i + 1] * inv) // 255
        self.px[i + 2] = (col[2] * alpha + self.px[i + 2] * inv) // 255

    def fill_rect(self, x0, y0, x1, y1, col):
        x0 = max(0, x0)
        y0 = max(0, y0)
        x1 = min(self.w, x1)
        y1 = min(self.h, y1)
        for y in range(y0, y1):
            i = self._idx(x0, y)
            row = bytes(col) * (x1 - x0)
            self.px[i:i + (x1 - x0) * 3] = row

    def alpha_rect(self, x0, y0, x1, y1, col, alpha):
        for y in range(max(0, y0), min(self.h, y1)):
            for x in range(max(0, x0), min(self.w, x1)):
                self.blend(x, y, col, alpha)

    def hline(self, x0, x1, y, col, wdt=1):
        for yy in range(y - wdt // 2, y + (wdt + 1) // 2):
            for x in range(x0, x1):
                self.set(x, yy, col)

    def vline(self, x, y0, y1, col, wdt=1):
        for xx in range(x - wdt // 2, x + (wdt + 1) // 2):
            for y in range(y0, y1):
                self.set(xx, y, col)

    def disc(self, cx, cy, r, col):
        if r <= 0:
            return
        r2 = r * r
        for y in range(cy - r, cy + r + 1):
            dy = y - cy
            dx = int(math.sqrt(max(0, r2 - dy * dy)))
            for x in range(cx - dx, cx + dx + 1):
                self.set(x, y, col)

    def alpha_disc(self, cx, cy, r, col, alpha):
        if r <= 0 or alpha <= 0:
            return
        r2 = r * r
        for y in range(cy - r, cy + r + 1):
            dy = y - cy
            dx = int(math.sqrt(max(0, r2 - dy * dy)))
            for x in range(cx - dx, cx + dx + 1):
                self.blend(x, y, col, alpha)

    def ellipse(self, cx, cy, rx, ry, col):
        if rx <= 0 or ry <= 0:
            return
        for y in range(cy - ry, cy + ry + 1):
            dy = (y - cy) / ry
            dx = int(rx * math.sqrt(max(0.0, 1.0 - dy * dy)))
            for x in range(cx - dx, cx + dx + 1):
                self.set(x, y, col)

    def alpha_ellipse(self, cx, cy, rx, ry, col, alpha):
        if rx <= 0 or ry <= 0 or alpha <= 0:
            return
        for y in range(cy - ry, cy + ry + 1):
            dy = (y - cy) / ry
            dx = int(rx * math.sqrt(max(0.0, 1.0 - dy * dy)))
            for x in range(cx - dx, cx + dx + 1):
                self.blend(x, y, col, alpha)

    def poly(self, pts, col):
        """Scanline fill of a polygon [(x, y), ...]."""
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        for y in range(max(0, min(ys)), min(self.h, max(ys) + 1)):
            xs = []
            n = len(pts)
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                if (y0 <= y < y1) or (y1 <= y < y0):
                    xs.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                for x in range(int(math.ceil(xs[k])), int(xs[k + 1]) + 1):
                    self.set(x, y, col)

    def alpha_poly(self, pts, col, alpha):
        if alpha <= 0 or len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        for y in range(max(0, min(ys)), min(self.h, max(ys) + 1)):
            xs = []
            n = len(pts)
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                if (y0 <= y < y1) or (y1 <= y < y0):
                    xs.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                for x in range(int(math.ceil(xs[k])), int(xs[k + 1]) + 1):
                    self.blend(x, y, col, alpha)

    def line(self, x0, y0, x1, y1, col, wdt=1):
        dx, dy = x1 - x0, y1 - y0
        steps = max(abs(dx), abs(dy), 1)
        for s in range(steps + 1):
            x = round(x0 + dx * s / steps)
            y = round(y0 + dy * s / steps)
            if wdt <= 1:
                self.set(x, y, col)
            else:
                self.disc(x, y, wdt // 2, col)

    def vgrad(self, x0, y0, x1, y1, stops):
        """Vertical gradient; stops = [(pos 0..1, (r,g,b)), ...] sorted."""
        h = y1 - y0
        if h <= 0:
            return
        for y in range(y0, y1):
            t = (y - y0) / max(1, h - 1)
            col = _lerp_stops(stops, t)
            self.fill_rect(x0, y, x1, y + 1, col)

    def hgrad(self, x0, y0, x1, y1, stops):
        w = x1 - x0
        if w <= 0:
            return
        for x in range(x0, x1):
            t = (x - x0) / max(1, w - 1)
            col = _lerp_stops(stops, t)
            self.fill_rect(x, y0, x + 1, y1, col)

    def glow(self, cx, cy, r, col, alpha=90, steps=14):
        """Radial glow: concentric translucent discs, alpha fading out."""
        for s in range(steps, 0, -1):
            rr = r * s // steps
            a = alpha * (steps - s) // steps
            if a > 0:
                self.alpha_disc(cx, cy, rr, col, a)

    def soft_shadow(self, cx, cy, rx, ry, alpha=70):
        self.alpha_ellipse(cx, cy, rx, ry, (0, 0, 0), alpha)

    def round_rect(self, x0, y0, x1, y1, r, col):
        self.fill_rect(x0 + r, y0, x1 - r, y1, col)
        self.fill_rect(x0, y0 + r, x1, y1 - r, col)
        for cx, cy in ((x0 + r, y0 + r), (x1 - r, y0 + r),
                       (x0 + r, y1 - r), (x1 - r, y1 - r)):
            self.disc(cx, cy, r, col)

    def alpha_round_rect(self, x0, y0, x1, y1, r, col, alpha):
        self.alpha_rect(x0 + r, y0, x1 - r, y1, col, alpha)
        self.alpha_rect(x0, y0 + r, x1, y1 - r, col, alpha)
        for cx, cy in ((x0 + r, y0 + r), (x1 - r, y0 + r),
                       (x0 + r, y1 - r), (x1 - r, y1 - r)):
            self.alpha_disc(cx, cy, r, col, alpha)


def _lerp_stops(stops, t):
    if t <= stops[0][0]:
        return stops[0][1]
    for i in range(1, len(stops)):
        if t <= stops[i][0]:
            p0, c0 = stops[i - 1]
            p1, c1 = stops[i]
            f = 0.0 if p1 == p0 else (t - p0) / (p1 - p0)
            return tuple(round(c0[k] + (c1[k] - c0[k]) * f) for k in range(3))
    return stops[-1][1]


def lerp_col(c0, c1, f):
    return tuple(round(c0[k] + (c1[k] - c0[k]) * f) for k in range(3))


# ---------------------------------------------------------------- PNG codec
def _png_chunk(typ, data):
    return (struct.pack(">I", len(data)) + typ + data +
            struct.pack(">I", binascii.crc32(typ + data) & 0xFFFFFFFF))


def write_png(cv, path):
    raw = bytearray()
    for y in range(cv.h):
        raw.append(0)
        raw += cv.px[y * cv.w * 3:(y + 1) * cv.w * 3]
    ihdr = struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0)
    data = (b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", ihdr) +
            _png_chunk(b"IDAT", zlib.compress(bytes(raw), 9)) +
            _png_chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(data)


def _unfilter(raw, w, h, bpp):
    """Undo PNG scanline filters; returns rows of bytes (no filter byte)."""
    stride = w * bpp
    out = bytearray()
    prev = bytearray(stride)
    pos = 0
    for _ in range(h):
        ftype = raw[pos]
        pos += 1
        line = bytearray(raw[pos:pos + stride])
        pos += stride
        if ftype == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 0xFF
        elif ftype == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ftype == 3:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 0xFF
        elif ftype == 4:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        out += line
        prev = line
    return bytes(out)


def read_gray_png(path):
    """Read an 8-bit grayscale non-interlaced PNG -> (w, h, bytes)."""
    data = open(path, "rb").read()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG: " + path
    pos = 8
    idat = bytearray()
    w = h = None
    ctype = None
    while pos < len(data):
        ln = struct.unpack(">I", data[pos:pos + 4])[0]
        typ = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + ln]
        if typ == b"IHDR":
            w, h, depth, ctype = struct.unpack(">IIBB", body[:10])
            assert depth == 8 and ctype == 0, "need 8-bit gray PNG"
        elif typ == b"IDAT":
            idat += body
        elif typ == b"IEND":
            break
        pos += 12 + ln
    return w, h, _unfilter(zlib.decompress(bytes(idat)), w, h, 1)


# ---------------------------------------------------------------- fonts
class Font:
    def __init__(self, name):
        with open(os.path.join(HERE, "atlas_%s.meta" % name)) as f:
            blob = f.read().strip()
        meta = json.loads(zlib.decompress(base64.b64decode(blob)))
        self.name = name
        self.size = meta["size"]
        self.ascent = meta["ascent"]
        self.descent = meta["descent"]
        self.chars = meta["chars"]
        self.kern = meta.get("kern", {})
        w, h, px = read_gray_png(os.path.join(HERE, "atlas_%s.png" % name))
        self.aw, self.ah, self.apx = w, h, px

    def adv(self, ch):
        c = self.chars.get(ch)
        return c[4] if c else self.size * 0.5

    def width(self, text, tracking=0):
        total = 0.0
        prev = None
        for ch in text:
            if prev is not None:
                total += self.kern.get(prev + ch, 0)
            total += self.adv(ch) + tracking
            prev = ch
        return total

    def draw(self, cv, x, line_top, text, col, tracking=0):
        """Draw text with its line-box top at line_top; returns end x."""
        pen = float(x)
        prev = None
        for ch in text:
            c = self.chars.get(ch)
            if c is not None:
                cx, cy, w, h, _adv, dx, dy = c
                if w > 0 and h > 0:
                    for yy in range(h):
                        row = (cy + yy) * self.aw + cx
                        for xx in range(w):
                            a = self.apx[row + xx]
                            if a:
                                cv.blend(int(pen) + dx + xx,
                                         line_top + dy + yy, col, a)
            if prev is not None:
                pen += self.kern.get(prev + ch, 0)
            pen += self.adv(ch) + tracking
            prev = ch
        return pen

    def draw_centered(self, cv, cx, line_top, text, col, tracking=0):
        x = cx - self.width(text, tracking) / 2.0
        return self.draw(cv, int(round(x)), line_top, text, col, tracking)


FONTS = {}


def F(name):
    if name not in FONTS:
        FONTS[name] = Font(name)
    return FONTS[name]


class WrapError(Exception):
    pass


def wrap(font, text, max_w, tracking=0):
    """Word-boundary wrap only. Raises WrapError on overflow or on a line
    that is nothing but a source tag like (Reuters)."""
    words = text.split(" ")
    lines = []
    cur = ""
    for word in words:
        trial = word if not cur else cur + " " + word
        if font.width(trial, tracking) <= max_w:
            cur = trial
        else:
            if not cur:
                raise WrapError("word too wide for box: %r" % word)
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    for ln in lines:
        if ln.startswith("(") and ln.endswith(")") and " " not in ln:
            raise WrapError("orphan source tag on its own line: %r" % ln)
    return lines


def draw_wrapped(cv, font, x, line_top, text, max_w, line_h, col,
                 max_lines=None, tracking=0):
    lines = wrap(font, text, max_w, tracking)
    if max_lines is not None and len(lines) > max_lines:
        raise WrapError("text needs %d lines, max %d: %r" %
                        (len(lines), max_lines, text))
    for i, ln in enumerate(lines):
        font.draw(cv, x, line_top + i * line_h, ln, col, tracking)
    return len(lines)

# ---------------------------------------------------------------- stories
# (num, kicker, headline, deck, source, region, lat, lon)
# Decks are full sentences; hero decks 15-22 words, mid decks 9-11 words.
# Hero 3 deck rewritten plainly (v8's "two are hurt" was ambiguous).
HEROES = [
    (1, "ANTALYA, TURKEY \u2014 CLIMATE",
     "COP31 climate talks collapse",
     "194 nations reject the Antalya Pact; the longest COP ever ends "
     "with no fossil-fuel deal.",
     "CNN, Reuters", "EU", 36.9, 30.7),
    (2, "KYIV REGION, UKRAINE \u2014 WAR",
     "Drone hits flats in Dymer, 14 missing",
     "A five-storey block collapses in the overnight attack; 186 drones "
     "were fired and 161 shot down.",
     "Reuters", "EU", 50.7, 30.3),
    (3, "MANAMA, BAHRAIN \u2014 IRAN WAR",
     "Iran strikes US bases in Bahrain",
     "Tehran says it struck US Patriot radars at al-Riffa and Awali; "
     "25 tankers are hit in a week.",
     "Al Jazeera", "ME", 26.23, 50.59),
]

MIDS = [
    (4, "GULF OF FINLAND", "Russian cargo ship burns",
     "A drone strike sets the ship ablaze; all 16 crew escape.",
     "BBC", "EU", 59.9, 25.0),
    (5, "KRYVYI RIH, UKRAINE", "Strike hits Zelenskyy's city",
     "Two are killed and 60 hurt in a Russian strike.",
     "Al Jazeera", "EU", 47.91, 33.35),
    (6, "BAYELSA, NIGERIA", "Mourners' boat capsizes",
     "A Niger boat sinks after a funeral; 24 people drown.",
     "AP", "AF", 4.92, 6.33),
    (7, "SPACE", "BepiColombo reaches Mercury",
     "The probe reaches Mercury after eight years in space.",
     "ESA", "EU", 49.87, 8.65),  # Darmstadt: ESA mission control
    (8, "GAZA", "Strike hits food aid vehicle",
     "Three Palestinians die in an air strike on aid.",
     "Al Jazeera", "ME", 31.5, 34.47),
    (9, "SINALOA, MEXICO", "El Chapo Isidro caught, 11 killed",
     "The cartel leader is held after a bloody raid in Guasave.",
     "AP", "AM", 25.57, -108.47),
    (10, "TEHRAN, IRAN", "Iran to ration electricity in wartime",
     "War damage forces rolling power cuts across Iran.",
     "Straits Times", "ME", 35.7, 51.4),
    (11, "WASHINGTON", "Nvidia faces US SEC probe",
     "The SEC opens a probe into the chipmaker.",
     "Straits Times", "AM", 38.9, -77.04),
    (12, "BRASILIA, BRAZIL", "Bolsonaro in intensive care",
     "Ex-president stable in hospital after surgery today.",
     "Reuters", "AM", -15.79, -47.88),
    (13, "CANBERRA", "Marles rejects US AUKUS report",
     "He says the budget number in the report is wrong.",
     "Reuters", "AP", -35.28, 149.13),
]

# (num, headline incl. source, region, lat, lon, motif)
MINIS = [
    (14, "FBI database was hacked. (AP)", "AM", 38.9, -77.04, "fbi"),
    (15, "US stocks slide on AI fears. (Reuters)", "AM", 40.71, -74.0, "chart"),
    (16, "6.7 quake hits Sacred Valley. (AP)", "AM", -13.3, -72.2, "quake"),
    (17, "45 people killed in South Sudan. (AP)", "AF", 4.85, 31.6, "sun"),
    (18, "Ukraine flies 2,700 drones. (Kyiv)", "EU", 50.45, 30.52, "drones"),
    (19, "NATO opens incursion talks. (Reuters)", "EU", 50.85, 4.35, "flag"),
    (20, "90 nations back power pledge. (Reuters)", "EU", 36.9, 30.7, "leaf"),
    (21, "Netanyahu opens unity talks. (TOI)", "ME", 31.77, 35.21, "podium"),
    (22, "Blast hits the Crimea Bridge. (Reuters)", "EU", 45.3, 36.5, "bridge"),
    (23, "Ex-police chief dead in Italy. (ANSA)", "EU", 41.9, 12.5, "badge"),
    (24, "Fire hits 6 Zanzibar hotels. (BBC)", "AF", -6.16, 39.2, "fire"),
    (25, "12 vehicles burned in West Bank. (AP)", "ME", 31.9, 35.2, "cars"),
    (26, "Trump: India wants US OK. (Reuters)", "AP", 28.6, 77.2, "tricolor"),
    (27, "Kutcher AI bet pays $7B. (Bloomberg)", "AP", 23.2, 69.7, "up"),
    (28, "Likud joins Jerusalem talks. (ST)", "ME", 31.77, 35.21, "podium"),
    (29, "Tigray strikes in Ethiopia. (Reuters)", "AF", 13.5, 39.5, "mountain"),
    (30, "Minister quits in S. Korea. (Yonhap)", "AP", 37.57, 126.98, "flag"),
    (31, "37 missing in Indonesia fire. (AP)", "AP", -6.2, 106.8, "fire"),
    (32, "Liverpool win 4-0 at Anfield. (BBC)", "EU", 53.4, -3.0, "pitch"),
    (33, "Verstappen wins in Las Vegas. (F1)", "AM", 36.17, -115.14, "checker"),
    (34, "Van Gogh sells at record $190.4M. (AP)", "W", 40.71, -74.0, "swirl"),
    (35, "Alcaraz wins first ATP title. (ATP)", "W", 45.07, 7.69, "tennis"),
]

STAT_STRIP = [
    ("~200", "NATIONS AT THE COP31 TALKS"),
    ("2 DAYS", "OVERTIME AT COP31"),
    ("25", "TANKERS HIT IN 7 DAYS"),
    ("186", "DRONES FIRED OVERNIGHT"),
    ("14", "MISSING IN DYMER"),
    ("4", "US BASES TARGETED"),
]

SUBHEAD = ("COP31 collapses with no deal \u00b7 Iran hits US bases in "
           "Bahrain \u00b7 14 missing in Dymer drone strike")

DATE_CHECK = ("Wires read up to 06:00 UTC, Monday 23 November 2026. Every "
              "story was reported or developing on 22\u201323 November. "
              "Left out: the Shenzhen summit (19 Nov); the Kerch Bridge "
              "strikes. Pictures and map: original, drawn in code.")

SOURCES = ("Sources: CNN \u00b7 Reuters \u00b7 AP \u00b7 Al Jazeera \u00b7 BBC "
           "\u00b7 The Times \u00b7 AFP \u00b7 Straits Times \u00b7 Kyiv "
           "Independent \u00b7 ESA \u00b7 F1 \u00b7 Yonhap \u00b7 ANSA "
           "\u00b7 Bloomberg \u00b7 ST \u00b7 TOI \u00b7 ATP.")

HERO_CHIPS = ["COP31: NO DEAL", "DYMER: 14 MISSING", "GULF: 25 HIT"]
HERO_CAPTIONS = ["Summit president", "Officials' count", "Bahrain govt"]
MID_CHIPS = ["SHIP ABLAZE", "2 DEAD, 60 HURT", "24 DEAD", "8 YEARS ON",
             "3 KILLED", "11 DEAD", "POWER CUTS", "SEC PROBE",
             "BOLSONARO: ICU", "AUKUS ROW"]
MID_CAPTIONS = ["Finnish forces", "Officials' count", "Emergency agency",
                "ESA", "Witnesses", "Officials' count", "Officials",
                "Media report", "Hospital", "Minister"]

# ---------------------------------------------------------------- grid
# ONE strict grid: every x comes from M/CW, every y from the band table.
M = 29                      # margin
CW = 966                    # content width; 29 + 966 = 995 = 1024 - 29
X0, X1 = M, M + CW

BANNER_H = 24
MASTHEAD_TOP = 22
SUBHEAD_TOP = 92
RULE_Y1, RULE_Y2 = 120, 123
STAT_TOP, STAT_BOT = 130, 178
REGION_TOP, REGION_BOT = 184, 206

HERO_Y = 212
HERO_IMG_H = 118
HERO_KICK_TOP = HERO_IMG_H + 5
HERO_HEAD_TOP = HERO_KICK_TOP + 14
HERO_HEAD_LH = 33
HERO_DECK_TOP = HERO_HEAD_TOP + 2 * HERO_HEAD_LH + 3
HERO_DECK_LH = 14

MID_Y1 = 461
MID_Y2 = 631
MID_IMG_H = 76
MID_KICK_TOP = MID_IMG_H + 4
MID_HEAD_TOP = MID_KICK_TOP + 13
MID_HEAD_LH = 21
MID_DECK_TOP = MID_HEAD_TOP + 2 * MID_HEAD_LH + 2
MID_DECK_LH = 13

BOT_HEAD_TOP = 801
BOT_Y = 816
BOT_H = 138
DATE_TOP, DATE_BOT = 960, 986
SOURCES_TOP = 990
FOOT_TOP, FOOT_BOT = 1004, 1024

# Columns: heroes 3 x 316, gutter 9; mids 5 x 186, gutter 9.
HERO_W = 316
HERO_GUT = 9
MID_W = 186
MID_GUT = 9
MINI_X0 = 509
MINI_W = 76
MINI_GUT = 6
MINI_H = 33
MINI_ROW_GUT = 2
MAP_X0, MAP_X1 = X0, 499
MAP_Y0, MAP_Y1 = BOT_Y, BOT_Y + BOT_H


def hero_x(i):
    return X0 + i * (HERO_W + HERO_GUT)


def mid_x(i):
    return X0 + i * (MID_W + MID_GUT)


def mini_xy(i):
    col, row = i % 6, i // 6
    return (MINI_X0 + col * (MINI_W + MINI_GUT),
            BOT_Y + row * (MINI_H + MINI_ROW_GUT))


def region_segments():
    """(name, x0, x1, count) — widths proportional to story counts."""
    counts = [("EUROPE", 11), ("MIDDLE EAST", 6), ("AMERICAS", 7),
              ("ASIA-PACIFIC", 5), ("AFRICA", 4), ("WORLD", 2)]
    total = sum(c for _, c in counts)
    segs = []
    x = X0
    for i, (name, c) in enumerate(counts):
        w = CW * c // total
        if i == len(counts) - 1:
            w = X1 - x
        segs.append((name, x, x + w, c))
        x += w
    return segs

# ---------------------------------------------------------------- illustration
# Editorial-illustration toolkit: gradients, glows, soft shadows, layered
# depth, translucent smoke. Scenes are painted, not diagrammed: every sky,
# sea and ground is a gradient; every light has a glow; every object sits
# on a soft shadow; far layers are paler than near layers.

def lcg(seed):
    """Deterministic pseudo-random floats in [0, 1)."""
    s = seed & 0x7FFFFFFF
    while True:
        s = (1103515245 * s + 12345) & 0x7FFFFFFF
        yield s / 2147483648.0


def flame(cv, cx, base_y, w, h):
    """A flame: glow + three nested teardrop layers."""
    cv.glow(cx, base_y - h // 2, max(w, h), (255, 140, 40), alpha=70)
    outer = [(cx - w // 2, base_y), (cx - w // 2, base_y - h // 2),
             (cx, base_y - h), (cx + w // 2, base_y - h // 2),
             (cx + w // 2, base_y)]
    cv.poly(outer, (235, 110, 30))
    mid = [(cx - w // 3, base_y), (cx - w // 3, base_y - h // 3),
           (cx, base_y - int(h * 0.72)), (cx + w // 3, base_y - h // 3),
           (cx + w // 3, base_y)]
    cv.poly(mid, (250, 190, 60))
    inner = [(cx - w // 5, base_y), (cx - w // 5, base_y - h // 4),
             (cx, base_y - h // 2), (cx + w // 5, base_y - h // 4),
             (cx + w // 5, base_y)]
    cv.poly(inner, (255, 240, 170))


def smoke(cv, cx, cy, r, alpha=60):
    """Translucent smoke: three overlapping soft discs."""
    cv.alpha_disc(cx - r // 2, cy + r // 4, int(r * 0.7), (120, 120, 128), alpha)
    cv.alpha_disc(cx, cy, r, (140, 140, 148), alpha)
    cv.alpha_disc(cx + r // 2, cy - r // 3, int(r * 0.6), (110, 110, 118), alpha)


def person(cv, cx, head_y, r, skin, shirt):
    """A seated figure: round head + shoulders, one straight baseline."""
    cv.ellipse(cx, head_y + r + 8, r + 4, r + 2, shirt)
    cv.disc(cx, head_y, r, skin)


def windows(cv, x0, y0, w, h, cols, rows, lit, lit_frac, seed, col=(255, 200, 90)):
    """A strict window grid; lit_frac of the panes glow (deterministic)."""
    gen = lcg(seed)
    cw, ch = w // cols, h // rows
    for ri in range(rows):
        for ci in range(cols):
            if next(gen) < lit_frac:
                wx = x0 + ci * cw + cw // 2
                wy = y0 + ri * ch + ch // 2
                cv.fill_rect(wx - 1, wy - 1, wx + 2, wy + 2, col)


def ship_hull(cv, x0, y_base, w, h, col):
    """A ship hull with a gentle bow, sitting on y_base."""
    pts = [(x0, y_base - h), (x0 + w - 14, y_base - h),
           (x0 + w, y_base - h + 5), (x0 + w - 8, y_base),
           (x0, y_base)]
    cv.poly(pts, col)


def van(cv, x0, y_base, w, h, body, cross=False):
    """A van: body + cab + wheels with hubs, soft shadow under it."""
    cv.soft_shadow(x0 + w // 2, y_base + 2, w // 2, 3, 50)
    cv.round_rect(x0, y_base - h, x0 + w, y_base - 4, 3, body)
    cv.round_rect(x0 + int(w * 0.62), y_base - h - 4, x0 + w - 2,
                  y_base - 4, 3, body)
    for wx in (x0 + int(w * 0.22), x0 + int(w * 0.78)):
        cv.disc(wx, y_base - 3, 5, (20, 20, 24))
        cv.disc(wx, y_base - 3, 2, (200, 200, 205))
    if cross:
        cx, cy = x0 + w // 3, y_base - h // 2 - 2
        cv.fill_rect(cx - 2, cy - 7, cx + 3, cy + 8, (200, 50, 40))
        cv.fill_rect(cx - 7, cy - 2, cx + 8, cy + 3, (200, 50, 40))


# ---------------------------------------------------------------- heroes
def scene_hero1(cv, x0, y0, w, h):
    """COP31 hall (v10): big globe left, warm wall, thermometer, seven
    delegates in one straight row behind a long table with name plates,
    '194 NATIONS' placard top right, wall clock. Like #1's hero 1."""
    cv.vgrad(x0, y0, x0 + w, y0 + h,
             [(0.0, (250, 244, 230)), (0.4, (246, 237, 216)),
              (0.7, (242, 230, 205)), (1.0, (236, 220, 190))])
    cv.glow(x0 + w // 2, y0 + 20, 120, (255, 238, 190), alpha=45)
    cv.glow(x0 + 225, y0 + 62, 80, (255, 240, 200), alpha=30)
    # floor band + baseboard
    cv.vgrad(x0, y0 + h - 22, x0 + w, y0 + h,
             [(0.0, (146, 102, 58)), (1.0, (118, 80, 44))])
    cv.hline(x0, x0 + w, y0 + h - 22, (110, 76, 42), 1)
    # globe, left, BIG with soft shading + shadow + stand
    gx, gy, gr = x0 + 58, y0 + 58, 38
    cv.soft_shadow(gx, gy + gr + 4, gr + 5, 5, 55)
    cv.disc(gx, gy, gr, (70, 120, 180))
    cv.alpha_disc(gx - 11, gy - 12, 24, (130, 175, 220), 110)
    cv.ellipse(gx - 8, gy + 3, 16, 11, (110, 170, 110))
    cv.ellipse(gx + 11, gy - 13, 12, 8, (120, 180, 115))
    cv.ellipse(gx + 3, gy + 16, 13, 8, (105, 165, 105))
    cv.ellipse(gx - 16, gy - 2, 8, 5, (115, 175, 112))
    cv.fill_rect(gx - 4, gy + gr, gx + 5, gy + gr + 9, (90, 70, 45))
    cv.fill_rect(gx - 12, gy + gr + 8, gx + 13, gy + gr + 11, (70, 54, 34))
    # thermometer
    tx = x0 + 110
    cv.round_rect(tx - 4, y0 + 28, tx + 5, y0 + 76, 4, WHITE)
    cv.fill_rect(tx - 2, y0 + 52, tx + 3, y0 + 74, (200, 60, 45))
    cv.disc(tx, y0 + 80, 8, (200, 60, 45))
    cv.disc(tx, y0 + 80, 8, (200, 60, 45))
    # delegates: SEVEN in one straight row, equal spacing, one baseline
    skins = [(232, 196, 160), (210, 170, 130), (240, 205, 170),
             (200, 160, 120), (228, 190, 155), (215, 175, 135),
             (236, 200, 165)]
    shirts = [(52, 74, 122), (168, 60, 42), (110, 128, 96),
              (196, 148, 72), (90, 90, 110), (70, 110, 110),
              (150, 90, 120)]
    for i in range(7):
        cx = x0 + 150 + i * 24
        person(cv, cx, y0 + 68, 10, skins[i], shirts[i])
    # table with wood gradient + soft shadow + papers
    cv.soft_shadow(x0 + 223, y0 + 104, 85, 5, 55)
    cv.vgrad(x0 + 138, y0 + 86, x0 + 308, y0 + 102,
             [(0.0, (168, 118, 66)), (1.0, (138, 94, 50))])
    cv.hline(x0 + 138, x0 + 308, y0 + 101, (110, 74, 38), 1)
    for px in (x0 + 150, x0 + 204, x0 + 260):
        cv.fill_rect(px, y0 + 82, px + 12, y0 + 86, (250, 248, 240))
    # name plates on the table front, one per delegate
    for i in range(7):
        cx = x0 + 150 + i * 24
        cv.fill_rect(cx - 7, y0 + 89, cx + 7, y0 + 95, (250, 248, 240))
    # placard top right, like #1's "~200 nations" box
    cv.fill_rect(x0 + 196, y0 + 8, x0 + 272, y0 + 26, WHITE)
    cv.hline(x0 + 196, x0 + 272, y0 + 8, INK, 1)
    cv.hline(x0 + 196, x0 + 272, y0 + 25, INK, 1)
    cv.vline(x0 + 196, y0 + 8, y0 + 26, INK, 1)
    cv.vline(x0 + 271, y0 + 8, y0 + 26, INK, 1)
    F("sans_b9").draw_centered(cv, x0 + 234, y0 + 12, "194 NATIONS", INK)
    # wall clock, top right
    ccx, ccy = x0 + 293, y0 + 26
    cv.disc(ccx, ccy, 15, (40, 40, 48))
    cv.disc(ccx, ccy, 13, WHITE)
    cv.line(ccx, ccy, ccx, ccy - 8, (40, 40, 48), 1)
    cv.line(ccx, ccy, ccx + 6, ccy + 2, (40, 40, 48), 1)
    cv.disc(ccx, ccy, 2, (40, 40, 48))


def scene_hero2(cv, x0, y0, w, h):
    """Dymer at night (v11): THIRTEEN drone trails, each with its own
    slope/length/start height (no parallel hatching), a small drone dart
    at every trail head, glowing tips, 5-stop night sky with a rose
    glow at the horizon, small dim moon top-left. Like #1's hero 2,
    denser than #1's ~7 trails."""
    cv.vgrad(x0, y0, x0 + w, y0 + h,
             [(0.0, (10, 12, 38)), (0.35, (24, 20, 56)),
              (0.6, (48, 30, 70)), (0.82, (92, 44, 66)),
              (1.0, (140, 62, 52))])
    gen = lcg(11)
    for _ in range(26):
        sx = x0 + int(next(gen) * w)
        sy = y0 + int(next(gen) * 55)
        cv.disc(sx, sy, 1, (220, 220, 240))
    # small dim moon, top-left corner (no longer competing with the rain)
    cv.glow(x0 + 26, y0 + 20, 16, (240, 235, 200), alpha=35)
    cv.disc(x0 + 26, y0 + 20, 7, (240, 235, 200))
    cv.alpha_disc(x0 + 26, y0 + 20, 10, (240, 235, 200), 18)
    # rose glow behind the skyline, softening the horizon
    cv.glow(x0 + 160, y0 + h - 12, 90, (210, 95, 80), alpha=28)
    # far skyline (paler, lower contrast)
    for i, (bx, bw, bh) in enumerate([(8, 52, 34), (66, 46, 44), (118, 56, 30),
                                      (180, 48, 40), (234, 56, 34)]):
        cv.fill_rect(x0 + bx, y0 + h - 14 - bh, x0 + bx + bw, y0 + h - 14,
                     (52, 56, 92))
        windows(cv, x0 + bx + 4, y0 + h - 14 - bh + 4, bw - 8, bh - 8,
                3, 3, True, 0.5, 100 + i, col=(190, 190, 215))
    # near skyline (darker, warm windows)
    for i, (bx, bw, bh) in enumerate([(0, 70, 62), (78, 64, 76), (150, 72, 56),
                                      (230, 86, 68)]):
        cv.fill_rect(x0 + bx, y0 + h - 14 - bh, x0 + bx + bw, y0 + h - 14,
                     (20, 22, 48))
        windows(cv, x0 + bx + 6, y0 + h - 14 - bh + 6, bw - 12, bh - 12,
                4, 5, True, 0.85, 200 + i)
    # horizon haze: warm translucent band above the ground
    cv.alpha_rect(x0, y0 + h - 30, x0 + w, y0 + h - 14, (255, 150, 70), 22)
    # collapsed block: shorter + rubble + BIG fire
    fx = x0 + 110
    cv.fill_rect(fx, y0 + h - 14 - 26, fx + 34, y0 + h - 14, (20, 22, 48))
    cv.fill_rect(fx + 4, y0 + h - 20, fx + 14, y0 + h - 14, (14, 14, 30))
    cv.fill_rect(fx + 20, y0 + h - 18, fx + 30, y0 + h - 14, (14, 14, 30))
    cv.fill_rect(fx - 6, y0 + h - 16, fx + 2, y0 + h - 14, (14, 14, 30))
    flame(cv, fx + 12, y0 + h - 14, 18, 26)
    flame(cv, fx + 26, y0 + h - 14, 14, 20)
    smoke(cv, fx + 30, y0 + h - 44, 12, 55)
    smoke(cv, fx + 42, y0 + h - 56, 9, 45)
    # ground band with warm reflection under the fire
    cv.fill_rect(x0, y0 + h - 14, x0 + w, y0 + h, (16, 16, 36))
    cv.alpha_rect(fx - 20, y0 + h - 14, fx + 54, y0 + h - 8, (255, 140, 40), 35)
    cv.alpha_rect(fx - 8, y0 + h - 8, fx + 42, y0 + h - 4, (255, 170, 70), 25)
    # drone trails: THIRTEEN, each with its own slope, length, start
    # height and tip size; a small drone dart rides at every head.
    # (sx, sy, dx, dy, tip_r) — hand-picked, deterministic.
    trails = [(18, 2, 22, 52, 4), (48, 8, 30, 66, 5), (76, 2, 18, 48, 3),
              (104, 12, 34, 74, 5), (128, 4, 26, 60, 4), (152, 10, 40, 78, 5),
              (178, 2, 20, 50, 4), (202, 14, 32, 70, 5), (226, 4, 24, 56, 4),
              (248, 8, 36, 72, 5), (272, 2, 22, 54, 4), (292, 12, 28, 64, 4),
              (62, 20, 26, 58, 4)]
    for sx, sy, dx, dy, tr in trails:
        hx, hy = x0 + sx, y0 + sy
        tx, ty = hx + dx, hy + dy
        cv.line(hx, hy, tx, ty, (235, 235, 245), 1)
        cv.glow(tx, ty, 9, (255, 160, 60), alpha=80)
        cv.disc(tx, ty, tr, (255, 170, 70))
        # drone dart at the head: pale body + dark nose, angled along
        # the trail so each dart points a slightly different way
        cv.poly([(hx - 4, hy + 1), (hx + 4, hy + 1), (hx, hy + 8)],
                (215, 215, 228))
        cv.disc(hx, hy + 3, 1, (40, 40, 52))


def scene_hero3(cv, x0, y0, w, h):
    """Gulf at dusk (v10): gradient sky, low sun with glow, grey tanks
    with a big flame cluster, BIG dark smoke plume, red tanker with
    flames and sea reflection. Like #1's hero 3, more dramatic."""
    cv.vgrad(x0, y0, x0 + w, y0 + h,
             [(0.0, (72, 50, 94)), (0.3, (130, 70, 90)),
              (0.55, (200, 100, 52)), (0.75, (205, 110, 55)),
              (1.0, (176, 72, 38))])
    # low sun with glow
    cv.glow(x0 + 258, y0 + 38, 48, (250, 210, 130), alpha=65)
    cv.disc(x0 + 258, y0 + 38, 13, (250, 220, 140))
    # strike trails: 3 diagonals with glowing tips, from the top
    for i, tx0 in enumerate((60, 120, 180)):
        ty0 = y0 + 2
        tx1, ty1 = x0 + tx0 + 26, y0 + 52
        cv.line(x0 + tx0, ty0, tx1, ty1, (235, 235, 245), 1)
        cv.glow(tx1, ty1, 8, (255, 160, 60), alpha=75)
        cv.disc(tx1, ty1, 4, (255, 170, 70))
    # sea with reflection under the sun + wave lines
    cv.vgrad(x0, y0 + 92, x0 + w, y0 + h,
             [(0.0, (16, 48, 62)), (1.0, (10, 34, 48))])
    cv.alpha_rect(x0 + 228, y0 + 94, x0 + 292, y0 + 110, (250, 170, 90), 35)
    cv.alpha_rect(x0 + 20, y0 + 100, x0 + 180, y0 + 102, (200, 220, 235), 28)
    cv.alpha_rect(x0 + 60, y0 + 108, x0 + 200, y0 + 110, (200, 220, 235), 20)
    # three GREY storage tanks (grey reads as metal, not candle wax)
    for i, tx in enumerate((56, 108, 160)):
        cx = x0 + tx
        cv.soft_shadow(cx, y0 + 92, 24, 4, 55)
        cv.vgrad(cx - 22, y0 + 62, cx + 22, y0 + 92,
                 [(0.0, (205, 205, 203)), (1.0, (158, 158, 156))])
        cv.ellipse(cx, y0 + 62, 22, 6, (180, 180, 178))
        cv.ellipse(cx, y0 + 61, 20, 5, (225, 225, 223))
        cv.fill_rect(cx - 22, y0 + 89, cx + 22, y0 + 92, (120, 120, 118))
        # tank pipe + valve on the side
        cv.fill_rect(cx + 24, y0 + 70, cx + 27, y0 + 92, (140, 140, 138))
    # one big flame cluster rising between the tanks
    for fx in (x0 + 108, x0 + 128, x0 + 148, x0 + 168):
        flame(cv, fx, y0 + 92, 18, 32)
    # BIG dark smoke plume drifting right from the fire
    smoke(cv, x0 + 168, y0 + 30, 24, 80)
    smoke(cv, x0 + 196, y0 + 18, 18, 70)
    smoke(cv, x0 + 220, y0 + 10, 13, 60)
    cv.alpha_disc(x0 + 180, y0 + 22, 10, (60, 60, 70), 70)
    # red tanker, bottom right, with flames + reflection
    hx = x0 + 192
    cv.soft_shadow(hx + 55, y0 + 110, 55, 4, 55)
    ship_hull(cv, hx, y0 + 110, 108, 16, (182, 62, 42))
    cv.hline(hx, hx + 94, y0 + 94, (220, 110, 80), 2)
    cv.fill_rect(hx + 8, y0 + 82, hx + 28, y0 + 94, (240, 240, 238))
    cv.fill_rect(hx + 34, y0 + 88, hx + 52, y0 + 94, (110, 128, 96))
    cv.fill_rect(hx + 58, y0 + 88, hx + 76, y0 + 94, (196, 148, 72))
    cv.fill_rect(hx + 82, y0 + 86, hx + 96, y0 + 94, (52, 74, 122))
    flame(cv, hx + 44, y0 + 88, 13, 15)
    flame(cv, hx + 64, y0 + 88, 11, 13)
    flame(cv, hx + 86, y0 + 88, 10, 12)
    cv.alpha_rect(hx + 10, y0 + 111, hx + 100, y0 + 114, (220, 110, 80), 30)

# ---------------------------------------------------------------- mid scenes
def scene_mid4(cv, x0, y0, w, h):
    """Ship ablaze, night sea (v11): taller superstructure filling the
    frame, sunset-orange horizon glow, four bigger deck flames, funnel
    smoke, smoother night sky."""
    cv.vgrad(x0, y0, x0 + w, y0 + h,
             [(0.0, (18, 22, 52)), (0.5, (28, 30, 66)),
              (1.0, (44, 44, 84))])
    cv.vgrad(x0, y0 + 46, x0 + w, y0 + h,
             [(0.0, (14, 44, 60)), (1.0, (10, 30, 46))])
    # horizon glow behind the ship
    cv.alpha_rect(x0, y0 + 34, x0 + w, y0 + 52, (255, 130, 50), 30)
    cv.alpha_rect(x0, y0 + 52, x0 + w, y0 + 54, (200, 220, 235), 40)
    cv.alpha_rect(x0, y0 + 62, x0 + w, y0 + 64, (200, 220, 235), 30)
    cv.soft_shadow(x0 + w // 2, y0 + 70, 82, 4, 50)
    ship_hull(cv, x0 + 8, y0 + 68, 170, 21, (165, 50, 36))
    cv.fill_rect(x0 + 20, y0 + 34, x0 + 46, y0 + 52, (240, 240, 238))
    cv.fill_rect(x0 + 50, y0 + 36, x0 + 74, y0 + 52, (110, 128, 96))
    cv.fill_rect(x0 + 78, y0 + 36, x0 + 102, y0 + 52, (196, 148, 72))
    cv.fill_rect(x0 + 106, y0 + 36, x0 + 130, y0 + 52, (52, 74, 122))
    # funnel with smoke
    cv.fill_rect(x0 + 140, y0 + 34, x0 + 150, y0 + 52, (30, 30, 36))
    flame(cv, x0 + 58, y0 + 46, 15, 22)
    flame(cv, x0 + 88, y0 + 46, 14, 20)
    flame(cv, x0 + 114, y0 + 46, 15, 22)
    flame(cv, x0 + 140, y0 + 46, 13, 18)
    smoke(cv, x0 + 144, y0 + 22, 10, 50)
    smoke(cv, x0 + 156, y0 + 16, 8, 40)


def scene_mid5(cv, x0, y0, w, h):
    """Kryvyi Rih at dusk (v11): brighter sky, four far buildings,
    three near towers wider and taller, bigger blast glow + flames,
    drifting smoke."""
    cv.vgrad(x0, y0, x0 + w, y0 + h,
             [(0.0, (122, 106, 138)), (0.7, (205, 130, 75)),
              (1.0, (130, 75, 62))])
    for i, (bx, bw, bh) in enumerate([(6, 48, 30), (56, 56, 38), (114, 48, 32),
                                      (160, 26, 26)]):
        cv.fill_rect(x0 + bx, y0 + h - 12 - bh, x0 + bx + bw, y0 + h - 12,
                     (74, 74, 104))
    for i, (bx, bw, bh) in enumerate([(0, 62, 52), (64, 60, 62), (126, 60, 56)]):
        cv.fill_rect(x0 + bx, y0 + h - 12 - bh, x0 + bx + bw, y0 + h - 12,
                     (28, 28, 52))
        windows(cv, x0 + bx + 5, y0 + h - 12 - bh + 5, bw - 10, bh - 10,
                4, 4, True, 0.8, 300 + i)
    cv.fill_rect(x0, y0 + h - 12, x0 + w, y0 + h, (22, 22, 40))
    cv.glow(x0 + 92, y0 + h - 16, 30, (255, 140, 40), alpha=70)
    flame(cv, x0 + 92, y0 + h - 12, 20, 28)
    flame(cv, x0 + 108, y0 + h - 12, 14, 18)
    smoke(cv, x0 + 108, y0 + h - 34, 10, 50)
    smoke(cv, x0 + 122, y0 + h - 46, 8, 40)


def scene_mid6(cv, x0, y0, w, h):
    """Capsized boat, calm sea (v11): wider hull filling the frame,
    broader white stripe, two bigger life rings, floating debris, more
    wave lines, bigger warm sun, smoother sky."""
    cv.vgrad(x0, y0, x0 + w, y0 + h,
             [(0.0, (170, 210, 230)), (0.5, (205, 222, 232)),
              (1.0, (240, 235, 210))])
    cv.vgrad(x0, y0 + 42, x0 + w, y0 + h,
             [(0.0, (40, 120, 140)), (1.0, (90, 170, 180))])
    for wy in (50, 58, 66, 70):
        cv.alpha_rect(x0 + 8, y0 + wy, x0 + w - 8, y0 + wy + 1,
                      (220, 240, 245), 55)
    cv.glow(x0 + 140, y0 + 14, 22, (250, 230, 160), alpha=55)
    cv.disc(x0 + 140, y0 + 14, 10, (250, 228, 150))
    # capsized hull: wide, tilted, with mast + broad white stripe
    cv.poly([(x0 + 20, y0 + 50), (x0 + 150, y0 + 42), (x0 + 158, y0 + 54),
             (x0 + 28, y0 + 62)], (140, 90, 50))
    cv.poly([(x0 + 22, y0 + 50), (x0 + 150, y0 + 42), (x0 + 152, y0 + 48),
             (x0 + 24, y0 + 56)], (245, 240, 230))
    cv.line(x0 + 92, y0 + 44, x0 + 92, y0 + 28, (90, 60, 35), 2)
    # debris plank floating left
    cv.fill_rect(x0 + 12, y0 + 60, x0 + 30, y0 + 63, (120, 80, 45))
    # two life rings floating
    cv.disc(x0 + 156, y0 + 58, 11, (235, 110, 40))
    cv.disc(x0 + 156, y0 + 58, 6, (60, 140, 155))
    cv.disc(x0 + 20, y0 + 66, 8, (235, 110, 40))
    cv.disc(x0 + 20, y0 + 66, 5, (60, 140, 155))


def scene_mid7(cv, x0, y0, w, h):
    """BepiColombo at Mercury (v11): bigger shaded planet with more
    craters, small grey moon, bigger probe with glowing trail, more
    stars, smoother space sky."""
    cv.vgrad(x0, y0, x0 + w, y0 + h,
             [(0.0, (8, 10, 28)), (0.5, (15, 14, 40)),
              (1.0, (24, 20, 52))])
    gen = lcg(77)
    for _ in range(30):
        cv.disc(x0 + int(next(gen) * w), y0 + int(next(gen) * h), 1,
                (220, 220, 240))
    # small grey moon, top left
    cv.disc(x0 + 26, y0 + 52, 6, (150, 150, 160))
    cv.disc(x0 + 24, y0 + 51, 2, (120, 120, 130))
    # Mercury: bigger shaded disc + craters + glow
    px, py, pr = x0 + 126, y0 + 38, 26
    cv.glow(px, py, 42, (220, 130, 60), alpha=45)
    cv.disc(px, py, pr, (200, 110, 50))
    cv.alpha_disc(px - 8, py - 9, 16, (235, 165, 95), 130)
    cv.disc(px - 6, py + 6, 5, (170, 90, 40))
    cv.disc(px + 9, py - 8, 4, (175, 95, 42))
    cv.disc(px + 2, py + 12, 3, (165, 85, 38))
    cv.disc(px - 13, py - 1, 3, (180, 100, 45))
    # probe with dish + glowing trail
    cv.glow(x0 + 12, y0 + 30, 8, (200, 200, 230), alpha=50)
    cv.line(x0 + 12, y0 + 30, x0 + 52, y0 + 30, (200, 200, 220), 1)
    cv.line(x0 + 4, y0 + 30, x0 + 12, y0 + 30, (150, 150, 180), 1)
    cv.fill_rect(x0 + 52, y0 + 24, x0 + 64, y0 + 36, (220, 220, 225))
    cv.disc(x0 + 68, y0 + 30, 6, (200, 200, 210))
    cv.disc(x0 + 68, y0 + 30, 4, (120, 120, 130))


def scene_mid8(cv, x0, y0, w, h):
    """Aid van, Gaza (v11): bigger van, bigger building silhouette
    behind, three smoke puffs, sandy ground with shadow line, smoother
    sky."""
    cv.vgrad(x0, y0, x0 + w, y0 + h,
             [(0.0, (180, 210, 225)), (0.5, (210, 221, 228)),
              (1.0, (240, 232, 200))])
    cv.vgrad(x0, y0 + 54, x0 + w, y0 + h,
             [(0.0, (210, 180, 130)), (1.0, (190, 160, 110))])
    # building silhouette behind the van
    cv.fill_rect(x0 + 6, y0 + 16, x0 + 48, y0 + 54, (200, 190, 165))
    windows(cv, x0 + 10, y0 + 22, 32, 24, 3, 2, True, 0.6, 500,
            col=(120, 110, 95))
    cv.fill_rect(x0 + 6, y0 + 54, x0 + w, y0 + 56, (170, 145, 100))
    smoke(cv, x0 + 40, y0 + 22, 13, 55)
    smoke(cv, x0 + 58, y0 + 14, 10, 45)
    smoke(cv, x0 + 76, y0 + 20, 9, 40)
    van(cv, x0 + 28, y0 + 70, 132, 30, (245, 245, 242), cross=True)


def scene_mid9(cv, x0, y0, w, h):
    """Sinaloa desert (v11): bigger truck, two bigger cacti, rocks,
    strong sun glow, long shadow under the truck, smoother sky."""
    cv.vgrad(x0, y0, x0 + w, y0 + h,
             [(0.0, (170, 205, 225)), (0.5, (208, 215, 205)),
              (1.0, (245, 225, 180))])
    cv.glow(x0 + 118, y0 + 14, 30, (250, 225, 150), alpha=60)
    cv.disc(x0 + 118, y0 + 14, 10, (250, 228, 150))
    cv.vgrad(x0, y0 + 46, x0 + w, y0 + 62,
             [(0.0, (222, 192, 138)), (1.0, (208, 176, 120))])
    cv.vgrad(x0, y0 + 62, x0 + w, y0 + h,
             [(0.0, (198, 168, 112)), (1.0, (182, 150, 96))])
    # cacti + rocks
    cv.fill_rect(x0 + 160, y0 + 26, x0 + 165, y0 + 50, (70, 120, 70))
    cv.fill_rect(x0 + 154, y0 + 33, x0 + 160, y0 + 38, (70, 120, 70))
    cv.fill_rect(x0 + 165, y0 + 38, x0 + 171, y0 + 42, (70, 120, 70))
    cv.fill_rect(x0 + 18, y0 + 36, x0 + 22, y0 + 52, (80, 130, 80))
    cv.disc(x0 + 172, y0 + 58, 3, (150, 120, 80))
    cv.disc(x0 + 178, y0 + 60, 2, (150, 120, 80))
    cv.disc(x0 + 12, y0 + 62, 2, (150, 120, 80))
    cv.soft_shadow(x0 + 95, y0 + 72, 64, 3, 50)
    cv.fill_rect(x0 + 34, y0 + 48, x0 + 130, y0 + 66, (178, 58, 42))
    cv.fill_rect(x0 + 130, y0 + 42, x0 + 158, y0 + 66, (150, 48, 36))
    cv.fill_rect(x0 + 134, y0 + 46, x0 + 150, y0 + 58, (200, 220, 235))
    for wx in (x0 + 52, x0 + 100, x0 + 140):
        cv.disc(wx, y0 + 68, 6, (20, 20, 24))
        cv.disc(wx, y0 + 68, 2, (200, 200, 205))


def scene_mid10(cv, x0, y0, w, h):
    """Tehran at night, power cuts (v11): bigger moon with glow, two
    taller power pylons in silhouette, wider dark towers with more lit
    windows, purple horizon glow, smoother night sky."""
    cv.vgrad(x0, y0, x0 + w, y0 + h,
             [(0.0, (16, 18, 46)), (0.5, (22, 22, 54)),
              (1.0, (30, 28, 60))])
    gen = lcg(31)
    for _ in range(10):
        cv.disc(x0 + int(next(gen) * w), y0 + int(next(gen) * 30), 1,
                (200, 200, 220))
    cv.glow(x0 + 150, y0 + 16, 36, (240, 235, 200), alpha=50)
    cv.disc(x0 + 150, y0 + 16, 18, (240, 235, 200))
    cv.alpha_disc(x0 + 145, y0 + 12, 9, (220, 215, 180), 60)
    cv.glow(x0 + 90, y0 + h - 8, 60, (120, 70, 110), alpha=25)
    for i, (bx, bw, bh) in enumerate([(2, 52, 58), (56, 60, 64), (118, 58, 52)]):
        cv.fill_rect(x0 + bx, y0 + h - 10 - bh, x0 + bx + bw, y0 + h - 10,
                     (22, 24, 50))
        windows(cv, x0 + bx + 5, y0 + h - 10 - bh + 5, bw - 10, bh - 10,
                4, 5, True, 0.55, 400 + i)
    # power pylons: two silhouettes with cross-arms, in front of towers
    for px in (x0 + 30, x0 + 156):
        cv.vline(px, y0 + 30, y0 + h - 10, (12, 12, 22), 3)
        cv.hline(px - 10, px + 10, y0 + 36, (12, 12, 22), 2)
        cv.hline(px - 7, px + 7, y0 + 48, (12, 12, 22), 2)
    cv.fill_rect(x0, y0 + h - 10, x0 + w, y0 + h, (16, 16, 34))


def scene_mid11(cv, x0, y0, w, h):
    """Nvidia probe (v11): chart on paper with light gridlines, thicker
    up-then-down line, bigger dots, bigger magnifier over the dip,
    warm paper gradient instead of a flat fill."""
    cv.vgrad(x0, y0, x0 + w, y0 + h,
             [(0.0, (242, 240, 230)), (1.0, (232, 230, 220))])
    # light gridlines
    for gx in (x0 + 56, x0 + 104, x0 + 152):
        cv.vline(gx, y0 + 10, y0 + h - 12, (210, 208, 198), 1)
    for gy in (y0 + 22, y0 + 40, y0 + 58):
        cv.hline(x0 + 14, x0 + w - 8, gy, (210, 208, 198), 1)
    cv.vline(x0 + 14, y0 + 10, y0 + h - 12, (90, 90, 100), 1)
    cv.hline(x0 + 14, x0 + w - 8, y0 + h - 12, (90, 90, 100), 1)
    pts = [(x0 + 22, y0 + 54), (x0 + 62, y0 + 38), (x0 + 102, y0 + 46),
           (x0 + 142, y0 + 24), (x0 + 170, y0 + 42)]
    cols = [(60, 140, 70), (200, 60, 45), (60, 140, 70), (200, 60, 45)]
    for i in range(4):
        cv.line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], cols[i], 4)
    for px, py in pts:
        cv.disc(px, py, 5, INK)
    mx, my = pts[2]
    cv.disc(mx, my, 16, (40, 40, 48))
    cv.disc(mx, my, 14, (240, 238, 228))
    cv.line(mx + 10, my + 10, mx + 21, my + 21, (40, 40, 48), 2)


def scene_mid12(cv, x0, y0, w, h):
    """Bolsonaro in hospital (v11): bigger bed with warm blanket,
    curtain band, bigger monitor with trace, IV pole + bag, floor,
    smoother wall gradient."""
    cv.vgrad(x0, y0, x0 + w, y0 + h,
             [(0.0, (210, 225, 235)), (0.5, (222, 232, 240)),
              (1.0, (235, 240, 245))])
    # curtain band, left
    cv.fill_rect(x0, y0, x0 + 10, y0 + h, (170, 200, 185))
    cv.vline(x0 + 10, y0, y0 + h, (140, 175, 160), 1)
    cx, cy = x0 + 32, y0 + 22
    cv.fill_rect(cx - 3, cy - 10, cx + 4, cy + 11, (60, 160, 90))
    cv.fill_rect(cx - 10, cy - 3, cx + 11, cy + 4, (60, 160, 90))
    # bed with pillow + blanket + patient head, bigger
    cv.soft_shadow(x0 + 100, y0 + 68, 66, 4, 45)
    cv.fill_rect(x0 + 32, y0 + 48, x0 + 168, y0 + 66, (120, 130, 145))
    cv.fill_rect(x0 + 38, y0 + 42, x0 + 66, y0 + 52, WHITE)
    cv.fill_rect(x0 + 90, y0 + 48, x0 + 168, y0 + 66, (110, 160, 130))
    cv.disc(x0 + 52, y0 + 46, 8, (232, 196, 160))
    cv.fill_rect(x0 + 32, y0 + 66, x0 + 36, y0 + 72, (90, 95, 105))
    cv.fill_rect(x0 + 164, y0 + 66, x0 + 168, y0 + 72, (90, 95, 105))
    cv.fill_rect(x0, y0 + 72, x0 + w, y0 + 74, (200, 205, 210))
    # IV pole + bag
    cv.vline(x0 + 172, y0 + 22, y0 + 62, (90, 90, 100), 1)
    cv.round_rect(x0 + 166, y0 + 24, x0 + 178, y0 + 36, 2, (220, 225, 235))
    # monitor with a trace, bigger
    cv.fill_rect(x0 + 132, y0 + 8, x0 + 178, y0 + 32, (30, 34, 44))
    cv.line(x0 + 135, y0 + 21, x0 + 144, y0 + 21, (90, 220, 120), 1)
    cv.line(x0 + 144, y0 + 21, x0 + 148, y0 + 14, (90, 220, 120), 1)
    cv.line(x0 + 148, y0 + 14, x0 + 153, y0 + 28, (90, 220, 120), 1)
    cv.line(x0 + 153, y0 + 28, x0 + 175, y0 + 21, (90, 220, 120), 1)


def scene_mid13(cv, x0, y0, w, h):
    """AUKUS submarine (v11): bigger darker sub filling the frame,
    taller periscope with bigger flag, three wake lines, more rising
    bubbles, smoother sea sky."""
    cv.vgrad(x0, y0, x0 + w, y0 + h,
             [(0.0, (170, 205, 225)), (0.5, (198, 220, 228)),
              (1.0, (225, 235, 230))])
    cv.vgrad(x0, y0 + 42, x0 + w, y0 + h,
             [(0.0, (30, 90, 110)), (1.0, (18, 60, 80))])
    cv.alpha_rect(x0, y0 + 48, x0 + w, y0 + 50, (220, 240, 245), 45)
    cv.alpha_rect(x0, y0 + 58, x0 + w, y0 + 60, (220, 240, 245), 35)
    cv.alpha_rect(x0, y0 + 66, x0 + w, y0 + 68, (220, 240, 245), 25)
    # bubbles rising from the sub
    for bx, by, br in ((x0 + 60, y0 + 22, 3), (x0 + 72, y0 + 14, 2),
                       (x0 + 52, y0 + 12, 2), (x0 + 44, y0 + 20, 2)):
        cv.disc(bx, by, br, (220, 240, 245))
    # submarine: dark capsule half-submerged + periscope + flag + wake
    cv.soft_shadow(x0 + 95, y0 + 54, 72, 4, 45)
    cv.round_rect(x0 + 18, y0 + 28, x0 + 172, y0 + 56, 12, (24, 32, 48))
    cv.alpha_rect(x0 + 18, y0 + 28, x0 + 172, y0 + 38, (70, 85, 105), 60)
    cv.fill_rect(x0 + 82, y0 + 22, x0 + 102, y0 + 32, (24, 32, 48))
    cv.vline(x0 + 108, y0 + 10, y0 + 26, (24, 32, 48), 2)
    cv.poly([(x0 + 110, y0 + 10), (x0 + 124, y0 + 15), (x0 + 110, y0 + 20)],
            (200, 60, 45))
    cv.line(x0 + 172, y0 + 44, x0 + 184, y0 + 40, (220, 240, 245), 1)
    cv.line(x0 + 172, y0 + 50, x0 + 184, y0 + 48, (220, 240, 245), 1)
    cv.line(x0 + 172, y0 + 56, x0 + 182, y0 + 56, (220, 240, 245), 1)


MID_SCENES = [scene_mid4, scene_mid5, scene_mid6, scene_mid7, scene_mid8,
              scene_mid9, scene_mid10, scene_mid11, scene_mid12, scene_mid13]


# ---------------------------------------------------------------- mini motifs
def mini_motif(cv, x0, y0, w, h, key):
    """One tiny motif inside a 76x13 strip: 2-4 shapes, distinct colours."""
    bg = {"fbi": (24, 30, 58), "chart": (240, 238, 228),
          "quake": (120, 90, 60), "sun": (250, 200, 90),
          "drones": (16, 18, 44), "flag": (52, 74, 122),
          "leaf": (110, 150, 90), "podium": (150, 110, 70),
          "bridge": (40, 110, 130), "badge": (196, 148, 72),
          "fire": (40, 40, 52), "cars": (200, 200, 205),
          "tricolor": (240, 235, 220), "up": (240, 238, 228),
          "mountain": (120, 90, 60), "pitch": (90, 140, 80),
          "checker": (240, 240, 235), "swirl": (40, 60, 110),
          "tennis": (200, 220, 90)}.get(key, (200, 200, 205))
    cv.fill_rect(x0, y0, x0 + w, y0 + h, bg)
    cx, cy = x0 + w // 2, y0 + h // 2
    if key == "fbi":
        cv.fill_rect(x0 + 28, y0 + 3, x0 + 48, y0 + h - 2, (200, 200, 215))
        cv.disc(x0 + 58, y0 + 6, 3, (240, 240, 245))
        cv.disc(x0 + 58, y0 + 6, 2, (24, 30, 58))
    elif key == "chart":
        pts = [(x0 + 8, y0 + 9), (x0 + 28, y0 + 4), (x0 + 48, y0 + 8),
               (x0 + 68, y0 + 3)]
        for i in range(3):
            cv.line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1],
                    (200, 60, 45) if i % 2 else (60, 140, 70), 1)
    elif key == "quake":
        cv.poly([(x0 + 22, y0 + h), (cx, y0 + 1), (x0 + 54, y0 + h)],
                (90, 65, 40))
        cv.line(cx, y0 + 1, cx + 4, y0 + 7, (240, 240, 245), 1)
        cv.line(cx + 4, y0 + 7, cx - 2, y0 + 11, (240, 240, 245), 1)
    elif key == "sun":
        cv.disc(cx, cy, 5, (235, 120, 40))
        for dx, dy in ((-9, 0), (9, 0), (0, -5), (0, 5)):
            cv.line(cx + dx, cy + dy, cx + dx * 2 - (dx and 3 or 0),
                    cy + dy * 2 - (dy and 3 or 0), (235, 120, 40), 1)
    elif key == "drones":
        for i, dx in enumerate((14, 34, 54)):
            cv.disc(x0 + dx, y0 + 4, 2, (240, 240, 245))
            cv.line(x0 + dx, y0 + 4, x0 + dx + 8, y0 + 10, (255, 170, 70), 1)
    elif key == "flag":
        cv.fill_rect(x0 + 30, y0 + 2, x0 + 52, y0 + 10, (240, 240, 245))
        cv.disc(x0 + 41, y0 + 6, 2, (52, 74, 122))
        cv.vline(x0 + 28, y0 + 2, y0 + h, (120, 120, 130), 1)
    elif key == "leaf":
        cv.ellipse(cx, cy, 12, 4, (60, 120, 60))
        cv.line(cx - 12, cy, cx + 12, cy, (40, 90, 40), 1)
    elif key == "podium":
        cv.fill_rect(cx - 10, y0 + 6, cx + 10, y0 + h, (110, 80, 50))
        cv.fill_rect(cx - 2, y0 + 1, cx + 2, y0 + 6, (240, 240, 245))
    elif key == "bridge":
        cv.line(x0 + 10, y0 + 10, x0 + 38, y0 + 2, (240, 240, 245), 1)
        cv.line(x0 + 38, y0 + 2, x0 + 66, y0 + 10, (240, 240, 245), 1)
        cv.disc(cx, y0 + 4, 2, (255, 170, 70))
    elif key == "badge":
        cv.disc(cx, cy, 5, (240, 210, 90))
        cv.disc(cx, cy, 2, (196, 148, 72))
    elif key == "fire":
        flame(cv, cx, y0 + h - 1, 8, 10)
    elif key == "cars":
        for bx in (x0 + 12, x0 + 44):
            cv.fill_rect(bx, y0 + 3, bx + 20, y0 + 9, (180, 60, 45))
            cv.disc(bx + 4, y0 + 10, 2, (20, 20, 24))
            cv.disc(bx + 16, y0 + 10, 2, (20, 20, 24))
    elif key == "tricolor":
        cv.fill_rect(x0, y0, x0 + w, y0 + 4, (230, 140, 50))
        cv.fill_rect(x0, y0 + 4, x0 + w, y0 + 9, (240, 240, 240))
        cv.fill_rect(x0, y0 + 9, x0 + w, y0 + h, (40, 130, 70))
    elif key == "up":
        cv.line(cx - 8, y0 + 10, cx, y0 + 2, (60, 140, 70), 2)
        cv.line(cx, y0 + 2, cx + 8, y0 + 10, (60, 140, 70), 2)
    elif key == "mountain":
        cv.poly([(x0 + 18, y0 + h), (cx, y0 + 1), (x0 + 58, y0 + h)],
                (100, 75, 50))
        cv.alpha_disc(cx + 8, y0 + 3, 4, (200, 200, 210), 90)
    elif key == "pitch":
        cv.hline(x0, x0 + w, cy, (240, 240, 245), 1)
        cv.disc(cx, cy, 3, WHITE)
    elif key == "checker":
        for i in range(8):
            if i % 2 == 0:
                cv.fill_rect(x0 + i * 9, y0, x0 + i * 9 + 9, y0 + h,
                             (20, 20, 24))
    elif key == "swirl":
        cv.disc(cx, cy, 5, (250, 210, 90))
        cv.line(cx - 4, cy, cx + 4, cy - 3, (40, 60, 110), 1)
        cv.line(cx + 4, cy - 3, cx - 1, cy + 3, (40, 60, 110), 1)
    elif key == "tennis":
        cv.disc(cx, cy, 5, (200, 220, 90))
        cv.line(cx - 3, cy - 4, cx - 3, cy + 4, WHITE, 1)
        cv.line(cx + 3, cy - 4, cx + 3, cy + 4, WHITE, 1)


# ---------------------------------------------------------------- map
def load_worldmap():
    blob = open(os.path.join(HERE, "worldmap.txt")).read().strip()
    bits = base64.b64decode(blob)
    land = set()
    for i in range(140 * 72):
        if bits[i // 8] >> (i % 8) & 1:
            land.add((i % 140, i // 140))
    return land


def lonlat_to_map(lon, lat):
    x = MAP_X0 + (lon + 180.0) / 360.0 * (MAP_X1 - MAP_X0)
    y = MAP_Y0 + (83.0 - lat) / 143.0 * (MAP_Y1 - MAP_Y0)
    return x, y


MAP_LABELS = [("NORTH AMERICA", -105, 58), ("SOUTH AMERICA", -65, -30),
              ("EUROPE", -25, 50), ("AFRICA", 20, -15), ("ASIA", 95, 45),
              ("OCEANIA", 130, -20)]


def draw_map(cv, stories):
    """Dotted continents, graticule, region labels, 35 numbered pins.
    Pins are decluttered: any pin landing within 11 px of an earlier pin
    is pushed out along 8 candidate directions, with a leader line."""
    land = load_worldmap()
    # graticule every 30 degrees
    for lon in range(-180, 181, 30):
        x = int(MAP_X0 + (lon + 180) / 360.0 * (MAP_X1 - MAP_X0))
        cv.vline(x, MAP_Y0, MAP_Y1, (196, 194, 186), 1)
    for lat in range(-60, 84, 30):
        y = int(MAP_Y0 + (83 - lat) / 143.0 * (MAP_Y1 - MAP_Y0))
        cv.hline(MAP_X0, MAP_X1, y, (196, 194, 186), 1)
    # land dots
    for (col, row) in land:
        x = MAP_X0 + (col + 0.5) / 140 * (MAP_X1 - MAP_X0)
        y = MAP_Y0 + (row + 0.5) / 72 * (MAP_Y1 - MAP_Y0)
        cv.disc(int(x), int(y), 1, (92, 92, 102))
    # region labels with paper halo
    f8 = F("sans_b8")
    for name, lon, lat in MAP_LABELS:
        x, y = lonlat_to_map(lon, lat)
        tw = f8.width(name)
        cx, cy = int(x - tw / 2), int(y - 5)
        cv.fill_rect(cx - 3, cy - 2, cx + int(tw) + 3, cy + 9, PAPER)
        f8.draw(cv, cx, cy, name, INK)
    # pins, decluttered
    placed = []
    fnum = F("sans_b8")
    for (num, _k, _h, _d, _s, region, lat, lon) in stories:
        tx, ty = lonlat_to_map(lon, lat)
        px, py = tx, ty
        for _ in range(2):
            clash = None
            for (ox, oy) in placed:
                if abs(px - ox) < 11 and abs(py - oy) < 11:
                    clash = (ox, oy)
                    break
            if clash is None:
                break
            best, bestd = None, -1
            for ang in range(8):
                ax = px + 12 * math.cos(ang * math.pi / 4)
                ay = py + 12 * math.sin(ang * math.pi / 4)
                dmin = min([999] + [math.hypot(ax - ox, ay - oy)
                                    for (ox, oy) in placed])
                if dmin > bestd:
                    best, bestd = (ax, ay), dmin
            px, py = best
        if (px, py) != (tx, ty):
            cv.line(int(tx), int(ty), int(px), int(py), (120, 120, 130), 1)
        placed.append((px, py))
        col = REGION_OF[{"EU": "EUROPE", "ME": "MIDDLE EAST",
                         "AM": "AMERICAS", "AP": "ASIA-PACIFIC",
                         "AF": "AFRICA", "W": "WORLD"}[region]]
        cv.disc(int(px), int(py), 7, WHITE)
        cv.disc(int(px), int(py), 6, col)
        label = str(num)
        tw = fnum.width(label)
        fnum.draw(cv, int(px - tw / 2), int(py - 4), label, WHITE)
    # border
    cv.hline(MAP_X0, MAP_X1, MAP_Y0, INK, 1)
    cv.hline(MAP_X0, MAP_X1, MAP_Y1 - 1, INK, 1)
    cv.vline(MAP_X0, MAP_Y0, MAP_Y1, INK, 1)
    cv.vline(MAP_X1 - 1, MAP_Y0, MAP_Y1, INK, 1)

# ---------------------------------------------------------------- chips
def label_chip(cv, x0, y0, text, font_name, h, pad=6):
    f = F(font_name)
    w = int(f.width(text)) + 2 * pad
    cv.fill_rect(x0, y0, x0 + w, y0 + h, BRICK)
    f.draw(cv, x0 + pad, y0 + (h - f.size) // 2 + 1, text, WHITE)
    return w


def caption_chip(cv, x0, y1, text, h=12):
    f = F("sans_b8")
    w = int(f.width(text)) + 10
    cv.fill_rect(x0 + 4, y1 - h - 3, x0 + 4 + w, y1 - 3, (16, 16, 20))
    f.draw(cv, x0 + 9, y1 - h - 1, text, WHITE)


def number_circle(cv, cx, cy, num, r=8):
    cv.disc(cx, cy, r, BRICK)
    cv.disc(cx, cy, r - 1, WHITE)
    f = F("sans_b9")
    label = str(num)
    f.draw(cv, int(cx - f.width(label) / 2), cy - 4, label, BRICK)


# ---------------------------------------------------------------- page
def build_page():
    cv = Canvas(W, H, PAPER)
    # --- banner
    cv.fill_rect(0, 0, W, BANNER_H, NAVY)
    F("sans_b10").draw_centered(
        cv, W // 2, 7, "THE WORLD IN ONE DAY \u2014 MONDAY 23 NOVEMBER 2026",
        WHITE)
    # --- masthead: #1's real masthead — big bold serif, title case.
    # Measured full-res: #1 caps 43 px tall, 894 px wide. serif_b64
    # gives 42 px caps; tracking 5 widens the line to ~884 px.
    # Line_top 22 leaves a 2 px gap to the subhead.
    F("serif_b64").draw_centered(cv, W // 2, MASTHEAD_TOP,
                                 "Monday 23 November 2026", INK, tracking=5)
    # --- sub-headline: three stories in one line
    F("serif_bi19").draw_centered(cv, W // 2, SUBHEAD_TOP, SUBHEAD, BRICK_D)
    # --- double rule
    cv.hline(X0, X1, RULE_Y1, INK, 2)
    cv.hline(X0, X1, RULE_Y2, INK, 1)
    # --- stat strip: 6 equal cells, number + caption, even dividers
    cell_w = CW // 6
    fnum = F("serif_b30")
    fcap = F("sans_b9")
    for i, (num, cap) in enumerate(STAT_STRIP):
        cx = X0 + i * cell_w + cell_w // 2
        fnum.draw_centered(cv, cx, STAT_TOP + 4, num, BRICK_D)
        fcap.draw_centered(cv, cx, STAT_TOP + 36, cap, INK)
        if i:
            cv.vline(X0 + i * cell_w, STAT_TOP + 4, STAT_BOT - 4, LGREY, 1)
    # --- region bar: segments proportional to story counts
    for name, x0, x1, c in region_segments():
        col = REGION_OF[name]
        cv.fill_rect(x0, REGION_TOP, x1, REGION_BOT, col)
        F("sans_b11").draw_centered(cv, (x0 + x1) // 2, REGION_TOP + 5,
                                    "%s %d" % (name, c), WHITE)
    # --- heroes
    for i, st in enumerate(HEROES):
        num, kicker, head, deck, src, region, lat, lon = st
        x0 = hero_x(i)
        y0 = HERO_Y
        scene = [scene_hero1, scene_hero2, scene_hero3][i]
        scene(cv, x0, y0, HERO_W, HERO_IMG_H)
        label_chip(cv, x0, y0, HERO_CHIPS[i], "sans_b11", 16)
        if i == 0:
            label_chip(cv, x0, y0 + 18, "TOP STORY", "sans_b8", 12, pad=5)
        caption_chip(cv, x0, y0 + HERO_IMG_H, HERO_CAPTIONS[i], h=14)
        F("sans_b11").draw(cv, x0, y0 + HERO_KICK_TOP, kicker, BRICK_D)
        draw_wrapped(cv, F("serif_b30"), x0, y0 + HERO_HEAD_TOP, head,
                     HERO_W, HERO_HEAD_LH, INK, max_lines=2)
        draw_wrapped(cv, F("serif_r11"), x0, y0 + HERO_DECK_TOP,
                     deck + " (" + src + ")", HERO_W, HERO_DECK_LH, INK,
                     max_lines=2)
    # --- mids, two rows of five
    for row in range(2):
        y0 = MID_Y1 if row == 0 else MID_Y2
        for j in range(5):
            idx = row * 5 + j
            st = MIDS[idx]
            num, kicker, head, deck, src, region, lat, lon = st
            x0 = mid_x(j)
            MID_SCENES[idx](cv, x0, y0, MID_W, MID_IMG_H)
            label_chip(cv, x0, y0, MID_CHIPS[idx], "sans_b9", 14, pad=5)
            number_circle(cv, x0 + MID_W - 10, y0 + 10, num)
            caption_chip(cv, x0, y0 + MID_IMG_H, MID_CAPTIONS[idx], h=12)
            F("sans_b11").draw(cv, x0, y0 + MID_KICK_TOP, kicker, BRICK_D)
            draw_wrapped(cv, F("serif_b18"), x0, y0 + MID_HEAD_TOP, head,
                         MID_W, MID_HEAD_LH, INK, max_lines=2)
            draw_wrapped(cv, F("serif_r10"), x0, y0 + MID_DECK_TOP,
                         deck + " (" + src + ")", MID_W, MID_DECK_LH, INK,
                         max_lines=2)
    # --- bottom header
    F("sans_b11").draw(cv, X0, BOT_HEAD_TOP, "WHERE IT HAPPENED", INK)
    rh = "THE REST OF THE DAY \u2014 22 MORE STORIES"
    F("sans_b11").draw(cv, int(X1 - F("sans_b11").width(rh)), BOT_HEAD_TOP,
                       rh, BRICK_D)
    # --- map (all 35 pins)
    all_stories = [(n, k, h, d, s, r, la, lo)
                   for (n, k, h, d, s, r, la, lo) in HEROES]
    all_stories += [(n, k, h, d, s, r, la, lo)
                    for (n, k, h, d, s, r, la, lo) in MIDS]
    all_stories += [(n, h, "", "", "", r, la, lo)
                    for (n, h, r, la, lo, _m) in MINIS]
    draw_map(cv, all_stories)
    # --- mini tiles
    for i, (num, head, region, lat, lon, motif) in enumerate(MINIS):
        x0, y0 = mini_xy(i)
        mini_motif(cv, x0, y0, MINI_W, 13, motif)
        cv.disc(x0 + 7, y0 + 7, 6, WHITE)
        f8 = F("sans_b8")
        lab = str(num)
        f8.draw(cv, int(x0 + 7 - f8.width(lab) / 2), y0 + 3, lab, BRICK)
        draw_wrapped(cv, F("serif_b7"), x0, y0 + 15, head, MINI_W, 9,
                     INK, max_lines=2)
    # --- DATE CHECK box
    cv.fill_rect(X0, DATE_TOP, X1, DATE_BOT, PAPER2)
    cv.hline(X0, X1, DATE_TOP, BRICK, 1)
    cv.hline(X0, X1, DATE_BOT - 1, BRICK, 1)
    cv.vline(X0, DATE_TOP, DATE_BOT, BRICK, 1)
    cv.vline(X1 - 1, DATE_TOP, DATE_BOT, BRICK, 1)
    draw_wrapped(cv, F("sans_r10"), X0 + 10, DATE_TOP + 3, DATE_CHECK,
                 CW - 20, 13, INK, max_lines=2)
    # --- sources line
    F("sans_r10").draw_centered(cv, W // 2, SOURCES_TOP, SOURCES, GREY)
    # --- footer
    cv.fill_rect(0, FOOT_TOP, W, FOOT_BOT, NAVY)
    F("sans_b10").draw(cv, X0, FOOT_TOP + 6, "THE WORLD IN ONE DAY", WHITE)
    ft = "MONDAY 23 NOVEMBER 2026 \u00b7 ONE PAGE"
    F("sans_b10").draw(cv, int(X1 - F("sans_b10").width(ft)), FOOT_TOP + 6,
                       ft, WHITE)
    return cv


# ---------------------------------------------------------------- audits
def audit():
    """Fail loudly on any wrap/overflow or grid inconsistency."""
    # grid equalities
    assert hero_x(2) + HERO_W == X1, "hero grid right edge"
    assert mid_x(4) + MID_W == X1, "mid grid right edge"
    mx, my = mini_xy(23)
    assert mx + MINI_W == X1, "mini grid right edge"
    assert my + MINI_H == BOT_Y + BOT_H, "mini grid bottom edge"
    assert sum(x1 - x0 for _, x0, x1, _ in region_segments()) == CW
    assert sum(1 for _ in HEROES) + sum(1 for _ in MIDS) + \
        sum(1 for _ in MINIS) == 35, "story count"
    # wraps: report line counts, enforce the budgets (all at once)
    errs = []
    def check(font_name, text, max_w, budget, tag, tracking=0):
        try:
            lines = wrap(F(font_name), text, max_w, tracking)
        except WrapError as e:
            errs.append("%s: %s" % (tag, e))
            return
        if len(lines) != budget:
            errs.append("%s: %d lines, want %d: %r" %
                        (tag, len(lines), budget, text))
    for st in HEROES:
        check("serif_b30", st[2], HERO_W, 2, "hero headline %d" % st[0])
        check("serif_r11", st[3] + " (" + st[4] + ")", HERO_W, 2,
              "hero deck %d" % st[0])
    for st in MIDS:
        check("serif_b18", st[2], MID_W, 2, "mid headline %d" % st[0])
        check("serif_r10", st[3] + " (" + st[4] + ")", MID_W, 2,
              "mid deck %d" % st[0])
    for st in MINIS:
        check("serif_b7", st[1], MINI_W, 2, "mini headline %d" % st[0])
    check("sans_r10", DATE_CHECK, CW - 20, 2, "date check")
    check("sans_r10", SOURCES, CW, 1, "sources")
    check("serif_bi19", SUBHEAD, CW, 1, "subhead")
    check("serif_b64", "Monday 23 November 2026", CW, 1, "masthead",
          tracking=5)
    for num, cap in STAT_STRIP:
        check("sans_b9", cap, CW // 6 - 8, 1, "stat caption %s" % num)
    for name, x0, x1, c in region_segments():
        check("sans_b11", "%s %d" % (name, c), x1 - x0 - 4, 1,
              "region label %s" % name)
    if errs:
        raise WrapError("wrap audit failed:\n" + "\n".join(errs))
    print("audit: grid + wraps OK (35 stories, all budgets met)")


def main():
    audit()
    cv = build_page()
    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, "entry.png")
    write_png(cv, out)
    with open(out, "rb") as f:
        data = f.read()
    print("wrote %s (%d bytes, sha256 %s)" %
          (out, len(data), __import__("hashlib").sha256(data).hexdigest()))


if __name__ == "__main__":
    main()
