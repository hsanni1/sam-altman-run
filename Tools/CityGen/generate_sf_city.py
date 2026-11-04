"""Procedural 2D art generator for the San Francisco street corners in Sam Altman Run.

Draws side-view (side-scroller) parallax layers for three real California Street
intersections, using the reference photo looking east down California St from
Nob Hill toward the Bay Bridge:

  1. NobHill_CaliforniaPowell   - grand stone hotels, brick club, Victorians, cable car crossing
  2. Chinatown_CaliforniaGrant  - pagoda-roof corner buildings, Old St. Mary's brick church
  3. FiDi_CaliforniaKearny      - dark granite tower, white-grid tower, striped tower, stone bank

Every layer is a PNG at 1 px = 1 Unreal unit, bottom-anchored, 3840x1080 per corner.
Run:  python3 Tools/CityGen/generate_sf_city.py   (needs Pillow)
"""

import math
import os
import random

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "Art", "Source", "City")
PREVIEW = os.path.join(ROOT, "Art", "Preview")

W, H = 3840, 1080
SS = 2                     # supersampling factor for anti-aliasing
GROUND = 880               # sidewalk top / building base (px from top)
CURB = 950
STREET = 962
IX0, IX1 = 1700, 2300      # cross-street gap in the middle of each corner segment
VP = (2000, 720)           # vanishing point for the cross street
SKY_TOP = (74, 138, 206)
SKY_HORIZON = (204, 224, 238)

FONT_SANS = "/System/Library/Fonts/Helvetica.ttc"
FONT_CJK = "/System/Library/Fonts/Hiragino Sans GB.ttc"


# ---------------------------------------------------------------- helpers

def mix(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3)) + ((a[3],) if len(a) == 4 else ())


def dark(c, t):
    return mix(c, (18, 20, 30), t)


def light(c, t):
    return mix(c, (255, 252, 240), t)


def font(path, size):
    try:
        return ImageFont.truetype(path, int(size * SS))
    except OSError:
        return ImageFont.load_default()


class Canvas:
    """RGBA canvas drawn at SS x resolution; coordinates are in final pixels."""

    def __init__(self, w=W, h=H, bg=(0, 0, 0, 0)):
        self.w, self.h = w, h
        self.im = Image.new("RGBA", (w * SS, h * SS), bg)
        self.d = ImageDraw.Draw(self.im)

    def rect(self, x0, y0, x1, y1, fill):
        if x1 <= x0 or y1 <= y0:
            return
        self.d.rectangle([x0 * SS, y0 * SS, x1 * SS - 1, y1 * SS - 1], fill=fill)

    def poly(self, pts, fill):
        self.d.polygon([(x * SS, y * SS) for x, y in pts], fill=fill)

    def ellipse(self, x0, y0, x1, y1, fill):
        self.d.ellipse([x0 * SS, y0 * SS, x1 * SS, y1 * SS], fill=fill)

    def line(self, pts, fill, width=1):
        self.d.line([(x * SS, y * SS) for x, y in pts], fill=fill, width=max(1, int(width * SS)))

    def text(self, x, y, s, size, fill, path=FONT_SANS, anchor="mm"):
        self.d.text((x * SS, y * SS), s, font=font(path, size), fill=fill, anchor=anchor)

    def image(self):
        return self.im.resize((self.w, self.h), Image.LANCZOS)


def window(c, x, y, w, h, frame, glass, rng, arched=False, mullion=True):
    c.rect(x - 4, y - 4, x + w + 4, y + h + 4, frame)
    if arched:
        c.ellipse(x - 4, y - w / 2 - 4, x + w + 4, y + w / 2 + 4, frame)
        c.ellipse(x, y - w / 2, x + w, y + w / 2, light(glass, 0.25))
    c.rect(x, y, x + w, y + h, glass)
    c.rect(x, y, x + w, y + h * 0.38, light(glass, 0.22))        # sky reflection
    if rng.random() < 0.28:                                        # pulled blind
        c.rect(x, y, x + w, y + h * rng.uniform(0.2, 0.7), (228, 218, 196))
    if mullion:
        c.rect(x + w / 2 - 1.5, y, x + w / 2 + 1.5, y + h, frame)
        c.rect(x, y + h * 0.5 - 1.5, x + w, y + h * 0.5 + 1.5, frame)
    c.rect(x - 7, y + h + 4, x + w + 7, y + h + 10, dark(frame, 0.12))   # sill


def storefront(c, x0, x1, base, h, frame, glass, rng, awning=None):
    c.rect(x0, base - h, x1, base, dark(frame, 0.05))
    bays = max(1, int((x1 - x0) / 120))
    bw = (x1 - x0) / bays
    for i in range(bays):
        bx = x0 + i * bw
        if i == bays // 2:  # door
            c.rect(bx + bw * 0.3, base - h + 22, bx + bw * 0.7, base, dark(glass, 0.35))
            c.rect(bx + bw * 0.3 + 6, base - h + 30, bx + bw * 0.7 - 6, base - 4, glass)
            c.rect(bx + bw * 0.5 - 1, base - h + 30, bx + bw * 0.5 + 1, base - 4, dark(glass, 0.4))
        else:
            c.rect(bx + 10, base - h + 22, bx + bw - 10, base - 18, glass)
            c.rect(bx + 10, base - h + 22, bx + bw - 10, base - h + 46, light(glass, 0.25))
    if awning:
        stripes = int((x1 - x0) / 24)
        for i in range(stripes):
            col = awning if i % 2 == 0 else light(awning, 0.75)
            sx = x0 - 8 + i * (x1 - x0 + 16) / stripes
            c.poly([(sx, base - h - 6), (sx + (x1 - x0 + 16) / stripes, base - h - 6),
                    (sx + (x1 - x0 + 16) / stripes + 6, base - h + 34), (sx + 6, base - h + 34)], col)
        c.rect(x0 - 2, base - h + 34, x1 + 14, base - h + 42, dark(awning, 0.3))


def cornice(c, x0, x1, y, depth, color):
    c.rect(x0 - depth, y - 26, x1 + depth, y, color)
    c.rect(x0 - depth, y - 34, x1 + depth, y - 26, light(color, 0.2))
    c.rect(x0 - depth + 4, y, x1 + depth - 4, y + 8, dark(color, 0.35))
    for dx in range(int(x0 - depth + 10), int(x1 + depth - 10), 18):   # dentils
        c.rect(dx, y, dx + 8, y + 14, dark(color, 0.2))


def side_shade(c, x1, top, w, color):
    c.rect(x1 - w, top, x1, GROUND, dark(color, 0.22))


# ---------------------------------------------------------------- building styles
# Each style draws one facade whose base sits on GROUND, spanning x .. x + w.

def stone_hotel(c, rng, x, w, floors=9):
    body = rng.choice([(232, 219, 190), (226, 212, 182), (238, 228, 205)])
    frame, glass = light(body, 0.35), (92, 118, 140)
    story = 96
    top = GROUND - floors * story - 40
    c.rect(x, top, x + w, GROUND, body)
    # rusticated base
    c.rect(x, GROUND - story * 1.4, x + w, GROUND, dark(body, 0.08))
    for gy in range(int(GROUND - story * 1.4), GROUND, 22):
        c.rect(x, gy, x + w, gy + 3, dark(body, 0.22))
    ex = x + w / 2
    c.rect(ex - 60, GROUND - 150, ex + 60, GROUND, dark(body, 0.3))
    c.ellipse(ex - 60, GROUND - 210, ex + 60, GROUND - 90, dark(body, 0.3))
    c.rect(ex - 48, GROUND - 140, ex + 48, GROUND, (58, 52, 46))
    c.rect(ex - 90, GROUND - 168, ex + 90, GROUND - 150, (34, 70, 54))          # canopy
    c.rect(ex - 86, GROUND - 150, ex - 80, GROUND, (40, 40, 40))
    c.rect(ex + 80, GROUND - 150, ex + 86, GROUND, (40, 40, 40))
    cols = max(2, int(w / 110))
    cw = w / cols
    for f in range(2, floors + 1):
        fy = GROUND - f * story + 20
        for i in range(cols):
            wx = x + i * cw + cw / 2 - 23
            if f <= 1 or abs(wx + 23 - ex) < 70 and f == 2:
                continue
            window(c, wx, fy, 46, 60, frame, glass, rng, arched=(f == floors))
    c.rect(x - 6, GROUND - story * 1.4 - 12, x + w + 6, GROUND - story * 1.4, light(body, 0.2))
    c.rect(x - 4, GROUND - (floors - 1) * story - 10, x + w + 4, GROUND - (floors - 1) * story, light(body, 0.2))
    cornice(c, x, x + w, top + 30, 18, light(body, 0.1))
    for fx in (x + 40, x + w - 40):                                               # flagpoles
        c.rect(fx - 2, top - 120, fx + 2, top, (70, 70, 70))
        c.rect(fx + 2, top - 118, fx + 62, top - 80, rng.choice([(40, 70, 150), (180, 60, 50), (230, 190, 70)]))
    side_shade(c, x + w, top, 12, body)


def victorian(c, rng, x, w=260):
    body = rng.choice([(196, 222, 214), (240, 206, 170), (214, 196, 228), (245, 232, 170), (230, 170, 160)])
    trim, glass = (250, 248, 240), (74, 96, 118)
    story, floors = 104, 3
    top = GROUND - floors * story - 46
    c.rect(x, top, x + w, GROUND, body)
    for yy in range(int(top), GROUND, 9):                                         # clapboard siding
        c.rect(x, yy, x + w, yy + 2, dark(body, 0.08))
    # bay window over left 55%
    bw = w * 0.55
    bx0, bx1 = x + 10, x + 10 + bw
    c.rect(bx0 - 6, GROUND - floors * story, bx1 + 6, GROUND - story + 6, trim)
    c.rect(bx0, GROUND - floors * story + 4, bx0 + 20, GROUND - story, dark(body, 0.18))
    c.rect(bx1 - 20, GROUND - floors * story + 4, bx1, GROUND - story, light(body, 0.15))
    c.rect(bx0 + 20, GROUND - floors * story + 4, bx1 - 20, GROUND - story, body)
    for f in (2, 3):
        fy = GROUND - f * story + 18
        window(c, bx0 + 30, fy, bw - 60, 66, trim, glass, rng)
        window(c, bx0 + 4, fy + 4, 12, 58, trim, dark(glass, 0.2), rng, mullion=False)
        window(c, bx1 - 16, fy + 4, 12, 58, trim, light(glass, 0.15), rng, mullion=False)
    # garage under bay
    c.rect(bx0 + 10, GROUND - 92, bx1 - 10, GROUND, trim)
    c.rect(bx0 + 16, GROUND - 86, bx1 - 16, GROUND, (120, 112, 100))
    for gy in range(GROUND - 80, GROUND, 16):
        c.rect(bx0 + 16, gy, bx1 - 16, gy + 2, (100, 92, 82))
    # entry + stoop on the right
    dx0 = bx1 + 26
    dx1 = x + w - 18
    c.rect(dx0, GROUND - story - 64, dx1, GROUND - story + 10, trim)
    c.rect(dx0 + 8, GROUND - story - 56, dx1 - 8, GROUND - story + 10, (96, 50, 44))
    for s in range(6):
        c.rect(dx0 - 10 - s * 6, GROUND - story + 10 + s * 16, dx1 + 4, GROUND - story + 26 + s * 16, light(trim, 0) if s % 2 else (226, 222, 214))
    for f in (2, 3):
        window(c, dx0 + 6, GROUND - f * story + 18, dx1 - dx0 - 12, 66, trim, glass, rng)
    # ornate cornice with brackets and pediment
    cornice(c, x, x + w, top + 40, 10, trim)
    for bxx in range(int(x + 8), int(x + w - 8), 34):
        c.rect(bxx, top + 40, bxx + 10, top + 64, trim)
    c.poly([(bx0 - 6, top + 6), ((bx0 + bx1) / 2, top - 40), (bx1 + 6, top + 6)], trim)
    c.poly([(bx0 + 14, top + 2), ((bx0 + bx1) / 2, top - 26), (bx1 - 14, top + 2)], body)
    side_shade(c, x + w, top, 8, body)


def brick_club(c, rng, x, w, floors=5):
    brick, stone, glass = (152, 74, 58), (236, 228, 210), (70, 88, 104)
    story = 100
    top = GROUND - floors * story - 50
    c.rect(x, top, x + w, GROUND, brick)
    for yy in range(int(top), GROUND, 8):
        c.rect(x, yy, x + w, yy + 1, dark(brick, 0.15))
    c.rect(x, GROUND - story, x + w, GROUND, stone)
    for gy in range(GROUND - story, GROUND, 20):
        c.rect(x, gy, x + w, gy + 2, dark(stone, 0.15))
    cols = max(2, int(w / 100))
    cw = w / cols
    for f in range(2, floors + 1):
        for i in range(cols):
            wx = x + i * cw + cw / 2 - 22
            fy = GROUND - f * story + 22
            c.rect(wx - 10, fy - 16, wx + 54, fy - 4, stone)                     # lintel
            window(c, wx, fy, 44, 62, stone, glass, rng)
    ex = x + w / 2
    c.ellipse(ex - 46, GROUND - 130, ex + 46, GROUND - 40, dark(stone, 0.2))
    c.rect(ex - 46, GROUND - 86, ex + 46, GROUND, dark(stone, 0.2))
    c.ellipse(ex - 36, GROUND - 120, ex + 36, GROUND - 50, (60, 44, 36))
    c.rect(ex - 36, GROUND - 86, ex + 36, GROUND, (60, 44, 36))
    for i in range(cols):
        c.rect(x + i * cw + cw / 2 - 40, GROUND - story - 10, x + i * cw + cw / 2 + 40, GROUND - story, stone)
    c.rect(x - 8, top, x + w + 8, top + 30, stone)                                 # balustrade
    for bx in range(int(x), int(x + w), 16):
        c.rect(bx + 4, top - 30, bx + 10, top, stone)
    c.rect(x - 8, top - 38, x + w + 8, top - 28, stone)
    side_shade(c, x + w, top, 10, brick)


def deco_apartment(c, rng, x, w, floors=8):
    body = rng.choice([(222, 196, 168), (236, 222, 200), (206, 188, 170), (230, 206, 196)])
    frame, glass = light(body, 0.3), (84, 104, 124)
    story = 92
    top = GROUND - floors * story - 30
    c.rect(x, top, x + w, GROUND, body)
    for px in range(int(x), int(x + w), int(w / 4)):                               # pilasters
        c.rect(px, top, px + 14, GROUND, light(body, 0.14))
    storefront(c, x, x + w, GROUND, 110, dark(body, 0.4), (76, 92, 102), rng)
    cols = max(2, int(w / 90))
    cw = w / cols
    for f in range(2, floors + 1):
        for i in range(cols):
            window(c, x + i * cw + cw / 2 - 20, GROUND - f * story + 18, 40, 56, frame, glass, rng)
    # fire escape
    fx = x + cw * (cols - 1) + 6
    for f in range(2, floors + 1):
        fy = GROUND - (f - 1) * story - 4
        c.rect(fx - 6, fy - 4, fx + cw - 6, fy, (34, 34, 38))
        for rx in range(int(fx - 6), int(fx + cw - 6), 8):
            c.rect(rx, fy - 30, rx + 2, fy, (34, 34, 38))
        c.rect(fx - 6, fy - 32, fx + cw - 6, fy - 28, (34, 34, 38))
        c.line([(fx + 4, fy), (fx + cw - 18, fy - story + 4)], (34, 34, 38), 3)
    # stepped deco parapet
    mid = x + w / 2
    c.rect(x, top - 16, x + w, top, light(body, 0.1))
    c.rect(mid - w * 0.25, top - 46, mid + w * 0.25, top, light(body, 0.1))
    c.rect(mid - w * 0.1, top - 76, mid + w * 0.1, top, light(body, 0.18))
    side_shade(c, x + w, top, 10, body)


def pagoda_roof(c, cx, y, w, roof, ridge):
    """Stacked roof with upturned eaves; y is the eave line."""
    c.poly([(cx - w / 2 - 30, y - 6), (cx - w / 2 - 14, y + 10), (cx + w / 2 + 14, y + 10),
            (cx + w / 2 + 30, y - 6), (cx + w / 2 - 20, y - 46), (cx - w / 2 + 20, y - 46)], roof)
    c.poly([(cx - w / 2 - 30, y - 6), (cx - w / 2 - 40, y - 22), (cx - w / 2 - 14, y + 2)], roof)
    c.poly([(cx + w / 2 + 30, y - 6), (cx + w / 2 + 40, y - 22), (cx + w / 2 + 14, y + 2)], roof)
    for tx in range(int(cx - w / 2 - 10), int(cx + w / 2 + 10), 10):               # tile lines
        c.rect(tx, y - 40, tx + 2, y + 6, dark(roof, 0.2))
    c.rect(cx - w / 2 + 16, y - 52, cx + w / 2 - 16, y - 44, ridge)
    c.rect(cx - w / 2 - 14, y + 8, cx + w / 2 + 14, y + 14, ridge)


def lantern(c, x, y, r=16, color=(214, 40, 36)):
    c.rect(x - 1, y - r - 14, x + 1, y - r + 2, (40, 30, 30))
    c.ellipse(x - r, y - r, x + r, y + r, color)
    c.ellipse(x - r * 0.55, y - r, x + r * 0.55, y + r, light(color, 0.15))
    c.rect(x - r * 0.5, y - r - 3, x + r * 0.5, y - r + 3, (230, 180, 60))
    c.rect(x - r * 0.5, y + r - 3, x + r * 0.5, y + r + 3, (230, 180, 60))
    c.rect(x - 2, y + r + 3, x + 2, y + r + 14, (230, 180, 60))


def pagoda_building(c, rng, x, w, tower_left=False):
    body, red, green, gold = (238, 230, 214), (196, 48, 38), (46, 118, 84), (232, 186, 70)
    glass = (70, 90, 100)
    story, floors = 100, 4
    top = GROUND - floors * story - 20
    c.rect(x, top, x + w, GROUND, body)
    storefront(c, x, x + w, GROUND, 116, red, (70, 86, 90), rng, awning=(180, 36, 30))
    cols = max(2, int(w / 100))
    cw = w / cols
    for f in range(2, floors + 1):
        fy = GROUND - f * story + 20
        for i in range(cols):
            window(c, x + i * cw + cw / 2 - 24, fy, 48, 58, red, glass, rng)
        c.rect(x + 6, fy + 66, x + w - 6, fy + 72, green)                         # balcony rail
        for rx in range(int(x + 8), int(x + w - 8), 12):
            c.rect(rx, fy + 72, rx + 4, fy + 92, green)
        c.rect(x + 6, fy + 92, x + w - 6, fy + 98, green)
    for px in (x, x + w - 14):
        c.rect(px, top, px + 14, GROUND - 116, red)
    # corner pagoda tower
    tw = 170
    tcx = x + tw / 2 + 10 if tower_left else x + w - tw / 2 - 10
    c.rect(x, top - 6, x + w, top + 12, red)
    pagoda_roof(c, (x + x + w) / 2, top, w - 30, green, gold)
    t1 = top - 50
    c.rect(tcx - tw / 2, t1 - 110, tcx + tw / 2, t1, body)
    for i in range(3):
        window(c, tcx - tw / 2 + 18 + i * 50, t1 - 90, 30, 56, red, glass, rng, arched=True)
    pagoda_roof(c, tcx, t1 - 110, tw, red, gold)
    t2 = t1 - 160
    c.rect(tcx - tw / 2 + 30, t2 - 90, tcx + tw / 2 - 30, t2, body)
    window(c, tcx - 18, t2 - 74, 36, 50, red, glass, rng, arched=True)
    pagoda_roof(c, tcx, t2 - 90, tw - 60, red, gold)
    c.rect(tcx - 4, t2 - 190, tcx + 4, t2 - 140, gold)                             # finial
    c.ellipse(tcx - 10, t2 - 206, tcx + 10, t2 - 186, gold)
    # vertical shop sign
    sx = x + (w * 0.25 if not tower_left else w * 0.7)
    c.rect(sx - 26, GROUND - 330, sx + 26, GROUND - 130, red)
    c.rect(sx - 20, GROUND - 324, sx + 20, GROUND - 136, dark(red, 0.1))
    for k, ch in enumerate(rng.choice(["金山茶", "飯店麵", "金門號"])):
        c.text(sx, GROUND - 292 + k * 60, ch, 40, gold, path=FONT_CJK)
    for f in range(2, floors + 1):
        lantern(c, x + 40, GROUND - f * story + 80)
        lantern(c, x + w - 40, GROUND - f * story + 80)
    side_shade(c, x + w, top, 10, body)


def chinatown_shop(c, rng, x, w):
    body = rng.choice([(244, 226, 160), (180, 214, 190), (236, 176, 150), (226, 220, 210)])
    rail = rng.choice([(46, 118, 84), (196, 48, 38), (230, 180, 60)])
    glass = (72, 92, 108)
    story, floors = 98, 3
    top = GROUND - floors * story - 28
    c.rect(x, top, x + w, GROUND, body)
    storefront(c, x, x + w, GROUND, 112, dark(body, 0.45), (70, 90, 96), rng,
               awning=rng.choice([(200, 40, 34), (40, 110, 80), (220, 160, 40)]))
    cols = max(2, int(w / 96))
    cw = w / cols
    for f in range(2, floors + 1):
        fy = GROUND - f * story + 18
        c.rect(x + 10, fy - 8, x + w - 10, fy + 76, dark(body, 0.25))           # recessed loggia
        for i in range(cols):
            window(c, x + i * cw + cw / 2 - 22, fy, 44, 58, light(body, 0.3), glass, rng)
        c.rect(x + 4, fy + 58, x + w - 4, fy + 64, rail)
        for rx in range(int(x + 6), int(x + w - 6), 10):
            c.rect(rx, fy + 64, rx + 4, fy + 84, rail)
        c.rect(x + 4, fy + 82, x + w - 4, fy + 88, rail)
    c.rect(x - 6, top, x + w + 6, top + 22, rail)
    c.poly([(x - 6, top), (x + w / 2, top - 34), (x + w + 6, top)], dark(rail, 0.1))
    # hanging blade sign
    sx = x + w - 34
    c.rect(sx - 2, GROUND - 230, sx + 40, GROUND - 224, (40, 40, 40))
    c.rect(sx + 4, GROUND - 224, sx + 40, GROUND - 140, (200, 40, 34))
    c.text(sx + 22, GROUND - 200, rng.choice(["茶", "麵", "餅"]), 26, (240, 200, 80), path=FONT_CJK)
    c.text(sx + 22, GROUND - 162, rng.choice(["館", "店", "家"]), 26, (240, 200, 80), path=FONT_CJK)
    side_shade(c, x + w, top, 8, body)


def church(c, rng, x, w=420):
    """Old St. Mary's-style red brick church with a square clock tower."""
    brick, stone, glass = (146, 62, 48), (226, 214, 190), (70, 76, 110)
    nave_top = GROUND - 330
    c.rect(x, nave_top, x + w, GROUND, brick)
    for yy in range(int(nave_top), GROUND, 8):
        c.rect(x, yy, x + w, yy + 1, dark(brick, 0.15))
    c.poly([(x - 10, nave_top), (x + w / 2, nave_top - 120), (x + w + 10, nave_top)], dark(brick, 0.05))
    c.poly([(x + 14, nave_top), (x + w / 2, nave_top - 104), (x + w - 14, nave_top)], brick)
    tw = 150
    tx = x + w / 2 - tw / 2
    ttop = GROUND - 700
    c.rect(tx, ttop, tx + tw, GROUND, dark(brick, 0.04))
    for yy in range(int(ttop), GROUND, 8):
        c.rect(tx, yy, tx + tw, yy + 1, dark(brick, 0.18))
    for sx in (tx, tx + tw - 14):
        c.rect(sx, ttop, sx + 14, GROUND, light(brick, 0.08))
    # clock
    cx, cy = tx + tw / 2, ttop + 120
    c.ellipse(cx - 46, cy - 46, cx + 46, cy + 46, stone)
    c.ellipse(cx - 38, cy - 38, cx + 38, cy + 38, (246, 242, 230))
    for k in range(12):
        a = k * math.pi / 6
        c.rect(cx + math.cos(a) * 32 - 2, cy + math.sin(a) * 32 - 2, cx + math.cos(a) * 32 + 2, cy + math.sin(a) * 32 + 2, (30, 30, 30))
    c.line([(cx, cy), (cx, cy - 28)], (30, 30, 30), 4)
    c.line([(cx, cy), (cx + 20, cy + 6)], (30, 30, 30), 4)
    # crenellations
    for k in range(5):
        c.rect(tx - 8 + k * 36, ttop - 30, tx + 14 + k * 36, ttop, stone)
    c.rect(tx - 8, ttop - 6, tx + tw + 8, ttop + 10, stone)

    def gothic(gx, gy, gw, gh):
        c.poly([(gx - 6, gy + gh), (gx - 6, gy), (gx + gw / 2, gy - gw * 0.8), (gx + gw + 6, gy), (gx + gw + 6, gy + gh)], stone)
        c.poly([(gx, gy + gh), (gx, gy), (gx + gw / 2, gy - gw * 0.7), (gx + gw, gy), (gx + gw, gy + gh)], glass)
        c.rect(gx + gw / 2 - 2, gy - gw * 0.6, gx + gw / 2 + 2, gy + gh, stone)

    gothic(tx + tw / 2 - 30, ttop + 260, 60, 150)
    for gx in (x + 30, x + 90, x + w - 140, x + w - 80):
        gothic(gx, GROUND - 270, 46, 130)
    # door
    c.poly([(cx - 50, GROUND), (cx - 50, GROUND - 110), (cx, GROUND - 170), (cx + 50, GROUND - 110), (cx + 50, GROUND)], stone)
    c.poly([(cx - 38, GROUND), (cx - 38, GROUND - 104), (cx, GROUND - 154), (cx + 38, GROUND - 104), (cx + 38, GROUND)], (80, 46, 34))
    c.rect(cx - 2, GROUND - 150, cx + 2, GROUND, (50, 30, 22))
    side_shade(c, x + w, nave_top, 10, brick)


def bank_classic(c, rng, x, w):
    stone, glass = (230, 222, 204), (60, 70, 76)
    top = GROUND - 440
    c.rect(x, top, x + w, GROUND, stone)
    c.rect(x - 10, GROUND - 26, x + w + 10, GROUND, dark(stone, 0.12))         # plinth steps
    c.rect(x - 20, GROUND - 12, x + w + 20, GROUND, dark(stone, 0.18))
    n = 6
    gap = (w - 60) / (n - 1)
    for i in range(n - 1):                                                       # tall windows between columns
        wx = x + 30 + i * gap + 30
        c.rect(wx, GROUND - 320, wx + gap - 60, GROUND - 40, dark(stone, 0.25))
        c.rect(wx + 6, GROUND - 312, wx + gap - 66, GROUND - 46, glass)
        c.rect(wx + 6, GROUND - 312, wx + gap - 66, GROUND - 260, light(glass, 0.2))
    for i in range(n):
        cx = x + 30 + i * gap
        c.rect(cx - 18, GROUND - 350, cx + 18, GROUND - 26, light(stone, 0.2))
        for fl in range(-12, 13, 8):
            c.rect(cx + fl, GROUND - 350, cx + fl + 2, GROUND - 26, dark(stone, 0.1))
        c.rect(cx - 26, GROUND - 364, cx + 26, GROUND - 350, light(stone, 0.1))  # capital
        c.rect(cx - 24, GROUND - 40, cx + 24, GROUND - 26, light(stone, 0.1))
    c.rect(x - 14, GROUND - 400, x + w + 14, GROUND - 364, light(stone, 0.12))  # entablature
    c.text(x + w / 2, GROUND - 382, "BANK OF THE GOLDEN GATE", min(22, w / 17), dark(stone, 0.45))
    cornice(c, x, x + w, top + 30, 20, light(stone, 0.08))
    c.rect(x + w / 2 - 50, GROUND - 200, x + w / 2 + 50, GROUND - 26, (120, 88, 48))   # bronze doors
    c.rect(x + w / 2 - 1, GROUND - 200, x + w / 2 + 1, GROUND - 26, (80, 56, 30))
    side_shade(c, x + w, top, 12, stone)


def tower_dark(c, rng, x, w):
    """555 California-style dark carnelian granite tower with sawtooth bay ribs."""
    granite, glass = (88, 52, 48), (40, 44, 56)
    top = -10
    c.rect(x, top, x + w, GROUND, granite)
    rib = 34
    for i, rx in enumerate(range(int(x), int(x + w), rib)):
        c.rect(rx + 4, top, rx + rib - 10, GROUND - 160, glass)
        c.rect(rx + rib - 10, top, rx + rib - 4, GROUND - 160, light(granite, 0.18))  # sunlit rib edge
        c.rect(rx, top, rx + 4, GROUND - 160, dark(granite, 0.25))
    for fy in range(int(GROUND - 160), int(top), -40):
        c.rect(x, fy - 4, x + w, fy, dark(granite, 0.15))
    # recessed lobby
    c.rect(x, GROUND - 160, x + w, GROUND, dark(granite, 0.45))
    c.rect(x + 30, GROUND - 140, x + w - 30, GROUND, (54, 64, 72))
    for px in range(int(x + 40), int(x + w - 30), 90):
        c.rect(px, GROUND - 160, px + 24, GROUND, granite)
    c.rect(x, 0, x + 18, GROUND - 160, light(granite, 0.12))
    side_shade(c, x + w, top, 18, granite)


def tower_grid(c, rng, x, w):
    """White punched-window grid tower (left side of the reference photo)."""
    body, glass = (238, 234, 222), (98, 116, 130)
    c.rect(x, -10, x + w, GROUND, body)
    cols = int(w / 46)
    cw = w / cols
    for fy in range(GROUND - 150, -60, -44):
        for i in range(cols):
            wx = x + i * cw + 8
            c.rect(wx, fy, wx + cw - 16, fy + 28, glass)
            c.rect(wx, fy, wx + cw - 16, fy + 5, dark(body, 0.45))               # deep reveal shadow
            c.rect(wx, fy, wx + 4, fy + 28, dark(body, 0.35))
            if rng.random() < 0.2:
                c.rect(wx + 4, fy + 5, wx + cw - 16, fy + 16, (232, 226, 210))
    storefront(c, x, x + w, GROUND, 140, dark(body, 0.5), (62, 76, 88), rng)
    side_shade(c, x + w, -10, 14, body)


def tower_striped(c, rng, x, w):
    """Cream piers with green-glass bands and a dark central slot (right side of photo)."""
    cream, glassg, slot = (226, 214, 180), (110, 150, 120), (66, 70, 76)
    c.rect(x, -10, x + w, GROUND, cream)
    sx0, sx1 = x + w * 0.47, x + w * 0.53
    for fy in range(GROUND - 170, -60, -54):
        c.rect(x + 10, fy, x + w - 10, fy + 30, glassg)
        c.rect(x + 10, fy, x + w - 10, fy + 8, light(glassg, 0.3))
        for mx in range(int(x + 10), int(x + w - 10), 26):
            c.rect(mx, fy, mx + 3, fy + 30, dark(glassg, 0.3))
        c.rect(x + 10, fy + 30, x + w - 10, fy + 34, dark(cream, 0.15))
    c.rect(sx0, -10, sx1, GROUND - 170, slot)
    for fy in range(GROUND - 170, -60, -54):
        c.rect(sx0 + 4, fy + 6, sx1 - 4, fy + 26, (90, 100, 110))
    storefront(c, x, x + w, GROUND, 150, (60, 62, 66), (70, 86, 96), rng)
    side_shade(c, x + w, -10, 14, cream)


def midrise_office(c, rng, x, w, floors=11):
    body = rng.choice([(150, 140, 128), (176, 168, 156), (122, 112, 104)])
    glass = (70, 84, 98)
    story = 70
    top = GROUND - floors * story - 120
    c.rect(x, top, x + w, GROUND, body)
    for f in range(floors):
        fy = GROUND - 150 - f * story
        c.rect(x + 12, fy - 40, x + w - 12, fy, glass)
        c.rect(x + 12, fy - 40, x + w - 12, fy - 30, light(glass, 0.2))
        for mx in range(int(x + 12), int(x + w - 12), 40):
            c.rect(mx, fy - 40, mx + 4, fy, dark(body, 0.2))
    storefront(c, x, x + w, GROUND, 120, dark(body, 0.4), (64, 78, 90), rng)
    c.rect(x - 6, top, x + w + 6, top + 20, light(body, 0.1))
    c.rect(x + w * 0.2, top - 60, x + w * 0.5, top, dark(body, 0.15))          # mechanical penthouse
    side_shade(c, x + w, top, 12, body)


# ---------------------------------------------------------------- cross street (perspective gap)

def project(x0, y0, x1):
    """Project a point on the near facade plane at x0 toward VP, returning y at x1."""
    k = (x1 - VP[0]) / (x0 - VP[0])
    return VP[1] + (y0 - VP[1]) * k


def cross_street_walls(c, rng, left_color, right_color, left_h, right_h):
    far_l, far_r = 1860, 2140
    for (x0, x1, col, h) in ((IX0, far_l, left_color, left_h), (IX1, far_r, right_color, right_h)):
        shade = dark(col, 0.32)
        top0 = GROUND - h
        c.poly([(x0, top0), (x1, project(x0, top0, x1)), (x1, project(x0, GROUND, x1)), (x0, GROUND)], shade)
        story = 96
        for f in range(1, int(h / story)):
            ya, yb = GROUND - f * story - 20, GROUND - f * story - 74
            for seg in range(4):
                xa = x0 + (x1 - x0) * (seg * 0.25 + 0.04)
                xb = x0 + (x1 - x0) * (seg * 0.25 + 0.18)
                c.poly([(xa, project(x0, ya, xa)), (xb, project(x0, ya, xb)),
                        (xb, project(x0, yb, xb)), (xa, project(x0, yb, xa))], dark(shade, 0.35))
    # distant buildings down the cross street
    x = far_l
    while x < far_r:
        bw = rng.randint(50, 90)
        bh = rng.randint(90, 260)
        col = mix(rng.choice([(200, 190, 170), (170, 160, 150), (220, 214, 200)]), SKY_HORIZON, 0.35)
        base = project(IX0, GROUND, far_l)
        c.rect(x, base - bh, min(x + bw, far_r), base, col)
        for wy in range(int(base - bh + 10), int(base - 10), 22):
            for wx in range(int(x + 6), int(min(x + bw, far_r) - 10), 16):
                c.rect(wx, wy, wx + 8, wy + 10, dark(col, 0.2))
        x += bw


# ---------------------------------------------------------------- street & props

def street_layer(rng, cross_rails=False):
    c = Canvas()
    concrete = (196, 192, 184)
    c.rect(0, GROUND, W, CURB, concrete)
    c.rect(0, GROUND, W, GROUND + 6, light(concrete, 0.25))
    for jx in range(0, W, 120):
        c.rect(jx, GROUND, jx + 2, CURB, dark(concrete, 0.15))
    c.rect(0, CURB, W, STREET, (164, 160, 152))
    c.rect(0, STREET - 3, W, STREET, (120, 116, 110))
    c.rect(0, STREET, W, H, (88, 88, 92))                      # asphalt
    for _ in range(900):
        px, py = rng.randint(0, W), rng.randint(STREET, H)
        c.rect(px, py, px + 3, py + 2, (98, 98, 102))
    c.rect(0, 994, W, H, (150, 70, 64))                         # red transit lane (as in the photo)
    for ry in (1004, 1028, 1050, 1074):
        c.rect(0, ry, W, ry + 5, (182, 178, 172))
        c.rect(0, ry + 5, W, ry + 7, (92, 60, 56))
    for sy in (1015, 1061):                                     # cable slot
        c.rect(0, sy, W, sy + 3, (40, 36, 36))
    c.text(900, 1040, "ONLY", 30, (238, 232, 222), path=FONT_SANS)
    c.text(3000, 1040, "ONLY", 30, (238, 232, 222), path=FONT_SANS)
    # cross street gap: asphalt receding to VP, curb ramps, crosswalk
    far_l, far_r = 1860, 2140
    gy = project(IX0, GROUND, far_l)
    c.rect(IX0, GROUND, IX1, STREET, (92, 92, 96))
    c.poly([(IX0, GROUND), (IX1, GROUND), (far_r, gy), (far_l, gy)], (92, 92, 96))
    c.poly([(IX0 - 40, GROUND), (IX0, GROUND), (far_l, gy), (far_l - 14, gy)], concrete)
    c.poly([(IX1, GROUND), (IX1 + 40, GROUND), (far_r + 14, gy), (far_r, gy)], concrete)
    c.poly([(1996, GROUND), (2004, GROUND), (2002, gy), (1998, gy)], (232, 196, 80))   # center line
    if cross_rails:
        for off in (-120, -80, 80, 120):
            c.line([(2000 + off * 1.2, STREET), (2000 + off * 0.35, gy)], (182, 178, 172), 4)
            c.rect(2000 + off * 1.2 - 2, STREET, 2000 + off * 1.2 + 3, H, (182, 178, 172))
    for bx in range(IX0 + 20, IX1 - 20, 44):                    # crosswalk bars
        c.rect(bx, STREET + 4, bx + 26, 990, (240, 238, 232))
    c.rect(IX0 - 4, CURB, IX0 + 60, STREET, (226, 196, 80))      # tactile ramps
    c.rect(IX1 - 60, CURB, IX1 + 4, STREET, (226, 196, 80))
    return c


def tree(c, rng, x, scale=1.0):
    trunk = (92, 70, 52)
    c.rect(x - 8 * scale, GROUND + 30 - 230 * scale, x + 8 * scale, GROUND + 30, trunk)
    c.line([(x, GROUND - 120 * scale), (x - 50 * scale, GROUND - 210 * scale)], trunk, 8 * scale)
    c.line([(x, GROUND - 140 * scale), (x + 46 * scale, GROUND - 230 * scale)], trunk, 8 * scale)
    c.rect(x - 34 * scale, GROUND + 26, x + 34 * scale, GROUND + 34, (110, 90, 70))   # tree well
    greens = [(66, 118, 52), (86, 140, 60), (112, 164, 74), (150, 190, 90)]
    for i, g in enumerate(greens):
        for _ in range(9):
            r = rng.uniform(40, 70) * scale * (1 - i * 0.12)
            cx = x + rng.uniform(-110, 110) * scale
            cy = GROUND - 280 * scale + rng.uniform(-70, 60) * scale - i * 12 * scale
            c.ellipse(cx - r, cy - r, cx + r, cy + r, g)


def street_lamp(c, x, facing=1):
    pole = (70, 74, 78)
    c.rect(x - 7, GROUND + 26, x + 7, GROUND + 34, dark(pole, 0.2))
    c.rect(x - 5, GROUND - 400, x + 5, GROUND + 30, pole)
    pts = [(x + facing * k * 2, GROUND - 400 - math.sin(k / 40 * math.pi / 2) * 40) for k in range(0, 41)]
    c.line(pts, pole, 7)
    hx = x + facing * 80
    c.poly([(hx - 26, GROUND - 444), (hx + 26, GROUND - 444), (hx + 18, GROUND - 430), (hx - 18, GROUND - 430)], pole)
    c.rect(hx - 16, GROUND - 430, hx + 16, GROUND - 426, (246, 236, 200))


def street_sign(c, x, cross_name, main_name="CALIFORNIA ST"):
    c.rect(x - 4, GROUND - 300, x + 4, GROUND + 30, (60, 64, 68))
    c.rect(x - 90, GROUND - 330, x + 90, GROUND - 300, (24, 104, 64))
    c.text(x, GROUND - 315, main_name, 17, (250, 250, 250))
    c.rect(x - 70, GROUND - 368, x + 70, GROUND - 338, (24, 104, 64))
    c.text(x, GROUND - 353, cross_name, 17, (250, 250, 250))
    c.rect(x - 36, GROUND - 270, x + 36, GROUND - 220, (250, 250, 250))       # cable car stop plate
    c.rect(x - 32, GROUND - 266, x + 32, GROUND - 224, (150, 60, 50))
    c.text(x, GROUND - 245, "CABLE CAR", 11, (250, 250, 250))


def lantern_string(c, x0, x1, y, sag=40):
    pts = [(x0 + (x1 - x0) * t / 30, y + math.sin(t / 30 * math.pi) * sag) for t in range(31)]
    c.line(pts, (40, 30, 30), 2)
    for t in range(2, 30, 3):
        px, py = pts[t]
        lantern(c, px, py + 18, 13)


# ---------------------------------------------------------------- shared background layers

def sky_layer():
    im = Image.new("RGBA", (1920, H))
    d = ImageDraw.Draw(im)
    for y in range(H):
        t = min(1.0, y / 760)
        d.line([(0, y), (1920, y)], fill=mix(SKY_TOP, SKY_HORIZON, t ** 1.4) + (255,))
    return im


def bay_bridge_layer():
    c = Canvas()
    horizon = 700
    haze = SKY_HORIZON
    water = mix((70, 118, 150), haze, 0.3)
    c.rect(0, horizon, W, H, water + (255,))
    for y in range(horizon + 6, H, 14):
        for x in range(0, W, 140):
            c.rect(x + (y * 7) % 90, y, x + (y * 7) % 90 + 50, y + 2, light(water, 0.25) + (255,))
    hills = mix((120, 138, 150), haze, 0.45) + (255,)
    pts = [(0, horizon)]
    for x in range(0, W + 1, 40):                                  # tileable: period divides W
        pts.append((x, horizon - 34 - 18 * math.sin(x / W * 6 * math.pi) - 10 * math.sin(x / W * 22 * math.pi)))
    pts.append((W, horizon))
    c.poly(pts, hills)
    steel = mix((160, 166, 172), haze, 0.35) + (255,)
    deck = 648
    span = 1280
    tops = [(x, 380) for x in (-span // 2, span // 2, span + span // 2, 2 * span + span // 2, 3 * span + span // 2)]
    for (tx, ty) in tops:
        for lx in (tx - 22, tx + 14):
            c.rect(lx, ty, lx + 8, deck + 30, steel)
        for by in range(ty + 20, deck, 54):
            c.line([(tx - 18, by), (tx + 18, by + 50)], steel, 4)
            c.line([(tx + 18, by), (tx - 18, by + 50)], steel, 4)
        c.rect(tx - 26, ty - 6, tx + 26, ty + 6, steel)
    for (ax, ay), (bx, by) in zip(tops, tops[1:]):
        pts = []
        for k in range(61):
            t = k / 60
            pts.append((ax + (bx - ax) * t, ay + 6 + (deck - 22 - ay) * (1 - (2 * t - 1) ** 2)))
        c.line(pts, steel, 3)
        for k in range(2, 60, 2):
            px, py = pts[k]
            c.line([(px, py), (px, deck)], steel, 1)
    c.rect(0, deck, W, deck + 12, steel)
    c.rect(0, deck + 12, W, deck + 22, dark(steel, 0.15))
    for x in range(0, W, 24):
        c.line([(x, deck + 12), (x + 12, deck + 22)], dark(steel, 0.25), 2)
    for (tx, ty) in tops:
        c.rect(tx - 30, deck + 22, tx + 30, horizon + 4, dark(steel, 0.1))   # piers
    return c.image()


def skyline_far(seed, landmarks):
    rng = random.Random(seed)
    c = Canvas()
    base = mix((128, 150, 178), SKY_HORIZON, 0.35)
    x = -40
    while x < W:
        bw = rng.randint(90, 220)
        bh = rng.randint(260, 640)
        col = mix(base, SKY_HORIZON, rng.uniform(0, 0.3))
        c.rect(x, GROUND - bh, x + bw, GROUND, col)
        for wy in range(GROUND - bh + 14, GROUND, 26):
            c.rect(x + 8, wy, x + bw - 8, wy + 3, light(col, 0.1))
        x += bw + rng.randint(-20, 30)
    for kind, lx in landmarks:
        col = mix(base, (90, 110, 140), 0.25)
        if kind == "pyramid":         # Transamerica-style spire
            c.poly([(lx - 70, GROUND), (lx - 8, 90), (lx + 8, 90), (lx + 70, GROUND)], light(col, 0.15))
            c.rect(lx - 3, 20, lx + 3, 92, light(col, 0.15))
        elif kind == "obelisk":       # rounded-top supertall
            c.rect(lx - 80, 60, lx + 80, GROUND, col)
            c.ellipse(lx - 80, 0, lx + 80, 120, col)
            for wy in range(80, GROUND, 18):
                c.rect(lx - 72, wy, lx + 72, wy + 2, light(col, 0.12))
        elif kind == "twin_spires":   # Grace Cathedral-style towers
            for ox in (-60, 60):
                c.rect(lx + ox - 30, 300, lx + ox + 30, GROUND, col)
                c.poly([(lx + ox - 34, 300), (lx + ox, 220), (lx + ox + 34, 300)], col)
            c.rect(lx - 60, 420, lx + 60, GROUND, col)
            c.ellipse(lx - 40, 470, lx + 40, 550, light(col, 0.2))
        elif kind == "hotel_tower":   # Mark Hopkins-style
            c.rect(lx - 90, 260, lx + 90, GROUND, col)
            c.rect(lx - 40, 200, lx + 40, 260, col)
            c.rect(lx - 2, 120, lx + 2, 200, col)
            c.rect(lx + 2, 122, lx + 40, 146, light(col, 0.2))
    return c.image()


# ---------------------------------------------------------------- corners

def corner_nob_hill():
    rng = random.Random(1849)
    b = Canvas()
    cross_street_walls(b, rng, (232, 219, 190), (152, 74, 58), 820, 550)
    x = 0
    for fn, w, kw in [(victorian, 250, {}), (victorian, 240, {}), (deco_apartment, 380, {"floors": 7}),
                      (victorian, 250, {}), (stone_hotel, 580, {"floors": 8})]:
        fn(b, rng, x, w, **kw)
        x += w
    assert x == IX0, x
    x = IX1
    for fn, w, kw in [(brick_club, 420, {"floors": 5}), (stone_hotel, 640, {"floors": 9}),
                      (victorian, 240, {}), (deco_apartment, 240, {"floors": 6})]:
        fn(b, rng, x, w, **kw)
        x += w
    assert x == W, x
    p = Canvas()
    for tx in (300, 760, 1240, 2800, 3300, 3700):
        tree(p, rng, tx, rng.uniform(0.85, 1.1))
    for lx in (520, 1480, 2560, 3500):
        street_lamp(p, lx, 1 if lx < 2000 else -1)
    street_sign(p, IX0 - 30, "POWELL ST")
    street_sign(p, IX1 + 30, "POWELL ST")
    return b, p, street_layer(rng, cross_rails=True), skyline_far(11, [("twin_spires", 700), ("hotel_tower", 2600)])


def corner_chinatown():
    rng = random.Random(1853)
    b = Canvas()
    cross_street_walls(b, rng, (238, 230, 214), (238, 230, 214), 500, 500)
    x = 0
    for fn, w, kw in [(chinatown_shop, 280, {}), (chinatown_shop, 260, {}), (church, 440, {}),
                      (chinatown_shop, 300, {}), (pagoda_building, 420, {})]:
        fn(b, rng, x, w, **kw)
        x += w
    assert x == IX0, x
    x = IX1
    for fn, w, kw in [(pagoda_building, 440, {"tower_left": True}), (chinatown_shop, 280, {}),
                      (deco_apartment, 320, {"floors": 6}), (chinatown_shop, 260, {}),
                      (chinatown_shop, 240, {})]:
        fn(b, rng, x, w, **kw)
        x += w
    assert x == W, x
    p = Canvas()
    lantern_string(p, 0, 980, 560)
    lantern_string(p, 1280, IX0, 560)
    lantern_string(p, IX1, 3100, 560)
    lantern_string(p, 3100, W, 560)
    for lx in (700, 2900):
        street_lamp(p, lx, 1 if lx < 2000 else -1)
    for tx in (1100, 3500):
        tree(p, rng, tx, 0.8)
    street_sign(p, IX0 - 30, "GRANT AVE")
    street_sign(p, IX1 + 30, "GRANT AVE")
    return b, p, street_layer(rng), skyline_far(22, [("pyramid", 1000), ("obelisk", 3000)])


def corner_fidi():
    rng = random.Random(1969)
    b = Canvas()
    cross_street_walls(b, rng, (88, 52, 48), (238, 234, 222), 1000, 1000)
    x = 0
    for fn, w, kw in [(tower_grid, 520, {}), (midrise_office, 300, {}), (bank_classic, 380, {}),
                      (tower_dark, 500, {})]:
        fn(b, rng, x, w, **kw)
        x += w
    assert x == IX0, x
    x = IX1
    for fn, w, kw in [(tower_striped, 540, {}), (midrise_office, 300, {"floors": 9}),
                      (tower_grid, 400, {}), (bank_classic, 300, {})]:
        fn(b, rng, x, w, **kw)
        x += w
    assert x == W, x
    p = Canvas()
    for tx in (200, 1050, 2650, 3420):
        tree(p, rng, tx, rng.uniform(0.9, 1.15))
    for lx in (640, 1560, 2420, 3200):
        street_lamp(p, lx, 1 if lx < 2000 else -1)
    street_sign(p, IX0 - 30, "KEARNY ST")
    street_sign(p, IX1 + 30, "KEARNY ST")
    return b, p, street_layer(rng), skyline_far(33, [("pyramid", 2050), ("obelisk", 600)])


CORNERS = {
    "NobHill_CaliforniaPowell": corner_nob_hill,
    "Chinatown_CaliforniaGrant": corner_chinatown,
    "FiDi_CaliforniaKearny": corner_fidi,
}


def main():
    shared = os.path.join(OUT, "Shared")
    os.makedirs(shared, exist_ok=True)
    os.makedirs(PREVIEW, exist_ok=True)
    sky = sky_layer()
    bridge = bay_bridge_layer()
    sky.save(os.path.join(shared, "T_SF_Sky.png"))
    bridge.save(os.path.join(shared, "T_SF_BayBridge.png"))
    strip = []
    for name, fn in CORNERS.items():
        buildings, props, street, far = fn()
        layers = {"Skyline": far, "Buildings": buildings.image(), "Street": street.image(), "Props": props.image()}
        d = os.path.join(OUT, name)
        os.makedirs(d, exist_ok=True)
        for lname, im in layers.items():
            im.save(os.path.join(d, f"T_{name}_{lname}.png"))
        comp = sky.resize((W, H))
        for im in (bridge, layers["Skyline"], layers["Buildings"], layers["Street"], layers["Props"]):
            comp = Image.alpha_composite(comp, im)
        comp.convert("RGB").save(os.path.join(PREVIEW, f"{name}.png"))
        strip.append(comp)
        print("wrote", name)
    full = Image.new("RGB", (W * len(strip), H))
    for i, im in enumerate(strip):
        full.paste(im.convert("RGB"), (i * W, 0))
    full.resize((full.width // 4, H // 4), Image.LANCZOS).save(os.path.join(PREVIEW, "SF_CaliforniaStreet_Strip.png"))


if __name__ == "__main__":
    main()
