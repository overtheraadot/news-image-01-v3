#!/usr/bin/env python3
"""news-image-01 v3 — one image summing up the world news of Friday 13 November 2026.

A newspaper front page, drawn from scratch with pure Python standard
library only: a hand-rolled zlib PNG encoder and a 5x7 bitmap font rendered
with filled rectangles. No network, no clock, no files read, no unseeded
randomness — the only pseudo-randomness is a fixed-seed LCG, so repeated
runs are byte-identical.

Round-3 fix: the output location. The grader mounts the repo read-only,
mounts a writable /output, and sets no MAKEFUN_OUTPUT_DIR, so a default of
"./out" dies with PermissionError. output_dir() therefore prefers the env
var, then /output when it exists, then the current directory.

Writes entry.png, 1024x1024, well under 1 MiB.
"""

import math
import os
import struct
import zlib

W, H = 1024, 1024

# ---------------------------------------------------------------- palette
PAPER = (246, 241, 227)
WHITE = (255, 255, 255)
INK = (18, 18, 18)
NAVY = (16, 32, 64)
NIGHT = (11, 30, 58)
OCEAN = (29, 78, 137)
SKY = (120, 160, 210)
GOLD = (242, 195, 0)
RED = (198, 32, 32)
GREY = (120, 128, 138)
FRAME = (176, 168, 148)
SKIN = (232, 190, 160)
GREEN = (46, 125, 50)
STEEL = (125, 140, 155)
DARK = (70, 78, 88)

# ------------------------------------------------- fixed-seed randomness
class Rng:
    """Tiny LCG (Numerical Recipes constants); deterministic across runs."""

    def __init__(self, seed=20261113):
        self.s = seed

    def next(self):
        self.s = (1664525 * self.s + 1013904223) & 0xFFFFFFFF
        return self.s

    def below(self, n):
        return self.next() % n

    def frac(self):
        return self.next() / 4294967296.0


RNG = Rng()


# ------------------------------------------------------------------ canvas
class Canvas:
    def __init__(self, w=W, h=H):
        self.w, self.h = w, h
        self.buf = bytearray(w * h * 3)
        self.fill(0, 0, w, h, PAPER)

    def _span(self, y, x0, x1, rgb):
        """Fill one clipped horizontal run with a repeated RGB triple."""
        n = x1 - x0
        if n <= 0:
            return
        base = (y * self.w + x0) * 3
        self.buf[base:base + n * 3] = bytes(rgb) * n

    def fill(self, x, y, w, h, rgb):
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.w, x + w)
        y1 = min(self.h, y + h)
        for yy in range(y0, y1):
            self._span(yy, x0, x1, rgb)

    def dot(self, x, y, rgb):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.buf[i:i + 3] = bytes(rgb)

    def disc(self, cx, cy, r, rgb):
        for dy in range(-r, r + 1):
            dx = int((r * r - dy * dy) ** 0.5)
            self._span(cy + dy, max(0, cx - dx), min(self.w, cx + dx + 1), rgb)

    def ellipse(self, cx, cy, rx, ry, rgb):
        for dy in range(-ry, ry + 1):
            t = 1.0 - (dy * dy) / float(ry * ry)
            dx = int(rx * (t ** 0.5)) if t > 0 else 0
            self._span(cy + dy, max(0, cx - dx), min(self.w, cx + dx + 1), rgb)

    def segment(self, x0, y0, x1, y1, rgb):
        """Bresenham line."""
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            self.dot(x0, y0, rgb)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def thick(self, x0, y0, x1, y1, rgb, t=4):
        half = t // 2
        for ox in range(-half, half + 1):
            for oy in range(-half, half + 1):
                self.segment(x0 + ox, y0 + oy, x1 + ox, y1 + oy, rgb)

    def triangle(self, ax, ay, bx, by, cx, cy, rgb):
        def edge(xa, ya, xb, yb, x, y):
            return (x - xa) * (yb - ya) - (y - ya) * (xb - xa)

        d = edge(ax, ay, bx, by, cx, cy)
        if d == 0:
            return
        x0 = max(0, min(ax, bx, cx))
        x1 = min(self.w - 1, max(ax, bx, cx))
        y0 = max(0, min(ay, by, cy))
        y1 = min(self.h - 1, max(ay, by, cy))
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                w0 = edge(bx, by, cx, cy, x, y)
                w1 = edge(cx, cy, ax, ay, x, y)
                w2 = edge(ax, ay, bx, by, x, y)
                if (d > 0 and w0 >= 0 and w1 >= 0 and w2 >= 0) or \
                   (d < 0 and w0 <= 0 and w1 <= 0 and w2 <= 0):
                    self.dot(x, y, rgb)


# ------------------------------------------------------------- 5x7 font
# Each glyph is 7 rows of 5 bits. Only the characters the page uses.
FONT = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01110", "10001", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    "J": ("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "11011", "10001"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00110", "01000", "10000", "11111"),
    "3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    "6": ("01110", "10000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00001", "01110"),
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    ".": ("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
    "-": ("00000", "00000", "00000", "01110", "00000", "00000", "00000"),
    ":": ("00000", "01100", "01100", "00000", "01100", "01100", "00000"),
    "!": ("00100", "00100", "00100", "00100", "00100", "00000", "00100"),
    ",": ("00000", "00000", "00000", "00000", "01100", "00100", "01000"),
    "'": ("00100", "00100", "01000", "00000", "00000", "00000", "00000"),
    "•": ("00000", "00100", "01110", "01110", "01110", "00100", "00000"),
}


def text_w(s, scale):
    return len(s) * 6 * scale - scale


def draw_text(cv, s, x, y, scale, rgb, center=False):
    """Draw s at scale; unknown glyphs are skipped but still advance."""
    if center:
        x -= text_w(s, scale) // 2
    cx = x
    for ch in s:
        g = FONT.get(ch)
        if g is not None:
            for row in range(7):
                bits = g[row]
                for ci in range(5):
                    if bits[ci] == "1":
                        cv.fill(cx + ci * scale, y + row * scale,
                                scale, scale, rgb)
        cx += 6 * scale


# ------------------------------------------------------------------- flags
def flag_pole(cv, x, y, h=56):
    cv.fill(x - 3, y - 6, 2, h + 6, (90, 80, 60))
    cv.disc(x - 2, y - 8, 3, GOLD)


def flag_ukraine(cv, x, y, w=84, h=56):
    cv.fill(x, y, w, h // 2, (0, 87, 183))
    cv.fill(x, y + h // 2, w, h - h // 2, (255, 215, 0))


def flag_eu(cv, x, y, w=84, h=56):
    cv.fill(x, y, w, h, (0, 51, 153))
    for i in range(12):
        a = 2 * math.pi * i / 12.0 - math.pi / 2
        sx = x + w // 2 + int(19 * math.cos(a))
        sy = y + h // 2 + int(13 * math.sin(a))
        cv.disc(sx, sy, 2, GOLD)


def flag_usa(cv, x, y, w=84, h=56):
    for i in range(13):
        stripe = (179, 25, 66) if i % 2 == 0 else WHITE
        cv.fill(x, y + i * h // 13, w, h // 13 + 1, stripe)
    cv.fill(x, y, int(w * 0.4), int(h * 7 / 13), (10, 49, 97))
    for r in range(4):
        for c in range(5):
            cv.disc(x + 4 + c * 6, y + 4 + r * 6, 1, WHITE)


# ------------------------------------------------------------------ globe
def draw_globe(cv, cx, cy, r):
    cv.disc(cx, cy, r, SKY)                 # rim light
    cv.disc(cx, cy, r - 3, NIGHT)           # night side
    # continents, a touch lighter than the night sea
    cv.ellipse(cx - 48, cy - 42, 42, 26, OCEAN)
    cv.ellipse(cx + 52, cy - 30, 34, 22, OCEAN)
    cv.ellipse(cx - 20, cy + 48, 48, 22, OCEAN)
    cv.ellipse(cx + 58, cy + 42, 26, 18, OCEAN)
    cv.ellipse(cx - 70, cy + 8, 18, 30, OCEAN)
    # city lights: fixed-seed points, evenly spread over the disc
    for _ in range(120):
        a = RNG.below(360)
        d = int((r - 12) * (RNG.frac() ** 0.5))
        x = cx + int(d * math.cos(math.radians(a)))
        y = cy + int(d * math.sin(math.radians(a)))
        if (x - cx) ** 2 + (y - cy) ** 2 < (r - 8) ** 2:
            cv.fill(x, y, 2, 2, GOLD)


def draw_dove(cv):
    """White dove with an olive branch, flying above the globe."""
    cv.triangle(462, 168, 500, 158, 470, 190, WHITE)   # tail feathers
    cv.ellipse(512, 176, 54, 26, WHITE)               # body
    cv.disc(558, 156, 15, WHITE)                       # head
    cv.triangle(571, 152, 588, 158, 571, 163, (230, 120, 40))  # beak
    cv.disc(562, 152, 2, INK)                          # eye
    cv.ellipse(500, 170, 30, 12, (216, 222, 230))      # folded wing
    cv.thick(586, 160, 624, 178, GREEN, 3)             # olive branch
    cv.ellipse(600, 166, 9, 4, GREEN)
    cv.ellipse(612, 172, 9, 4, GREEN)
    cv.ellipse(622, 178, 9, 4, GREEN)
    cv.disc(606, 176, 3, (60, 90, 40))
    cv.disc(618, 182, 3, (60, 90, 40))


def sparkle(cv, x, y, r, rgb):
    """Four-point star used for glints."""
    cv.triangle(x, y - r, x + r // 3, y - r // 3, x - r // 3, y - r // 3, rgb)
    cv.triangle(x, y + r, x + r // 3, y + r // 3, x - r // 3, y + r // 3, rgb)
    cv.triangle(x - r, y, x - r // 3, y + r // 3, x - r // 3, y - r // 3, rgb)
    cv.triangle(x + r, y, x + r // 3, y + r // 3, x + r // 3, y - r // 3, rgb)


# --------------------------------------------------------------- vignettes
def cell(cv, x, y, w=320, h=208):
    cv.fill(x, y, w, h, WHITE)
    cv.fill(x, y, w, 2, FRAME)
    cv.fill(x, y + h - 2, w, 2, FRAME)
    cv.fill(x, y, 2, h, FRAME)
    cv.fill(x + w - 2, y, 2, h, FRAME)


def cell_label(cv, x, y, s):
    draw_text(cv, s, x + 160, y + 184, 2, INK, center=True)


def v_nvidia(cv, ox, oy):
    """Empty witness chair, computer chip, red downward arrow."""
    wood = (120, 72, 32)
    cv.fill(ox + 50, oy + 30, 12, 80, wood)        # chair back
    cv.fill(ox + 50, oy + 100, 90, 12, wood)       # chair seat
    cv.fill(ox + 52, oy + 112, 10, 50, wood)       # back leg
    cv.fill(ox + 128, oy + 112, 10, 50, wood)      # front leg
    cv.fill(ox + 155, oy + 45, 72, 72, (30, 30, 40))   # chip
    cv.fill(ox + 167, oy + 57, 48, 48, (70, 80, 110))
    cv.fill(ox + 177, oy + 67, 28, 28, (150, 170, 200))
    for i in range(4):                             # chip pins
        cv.fill(ox + 163 + i * 16, oy + 37, 8, 8, GREY)
        cv.fill(ox + 163 + i * 16, oy + 117, 8, 8, GREY)
        cv.fill(ox + 147, oy + 53 + i * 16, 8, 8, GREY)
        cv.fill(ox + 227, oy + 53 + i * 16, 8, 8, GREY)
    cv.fill(ox + 258, oy + 30, 16, 70, RED)        # arrow shaft
    cv.triangle(ox + 238, oy + 100, ox + 294, oy + 100,
                ox + 266, oy + 150, RED)           # arrow head


def v_microsoft(cv, ox, oy):
    """Dark envelope (Mail / Teams) with a gold warning triangle."""
    cv.fill(ox + 55, oy + 55, 190, 100, (28, 38, 66))
    edge = (96, 116, 165)
    cv.segment(ox + 55, oy + 55, ox + 150, oy + 105, edge)
    cv.segment(ox + 245, oy + 55, ox + 150, oy + 105, edge)
    cv.segment(ox + 55, oy + 155, ox + 150, oy + 105, edge)
    cv.segment(ox + 245, oy + 155, ox + 150, oy + 105, edge)
    cv.triangle(ox + 225, oy + 10, ox + 268, oy + 10,
                ox + 246, oy + 54, GOLD)           # warning triangle
    cv.fill(ox + 243, oy + 20, 6, 16, INK)
    cv.fill(ox + 243, oy + 40, 6, 6, INK)
    draw_text(cv, "MAIL", ox + 78, oy + 162, 1, GREY)
    draw_text(cv, "TEAMS", ox + 205, oy + 162, 1, GREY)


def v_hospital(cv, ox, oy):
    """Hospital building with a red cross, lit candle beside it."""
    cv.fill(ox + 45, oy + 50, 150, 115, WHITE)
    cv.fill(ox + 45, oy + 50, 150, 3, GREY)
    cv.fill(ox + 45, oy + 50, 3, 115, GREY)
    cv.fill(ox + 192, oy + 50, 3, 115, GREY)
    cv.fill(ox + 45, oy + 162, 150, 3, GREY)
    for wx in (ox + 60, ox + 155):
        for wy in (oy + 70, oy + 100):
            cv.fill(wx, wy, 22, 16, (90, 140, 190))
    cv.fill(ox + 112, oy + 62, 12, 36, RED)        # cross
    cv.fill(ox + 100, oy + 72, 36, 12, RED)
    cv.fill(ox + 106, oy + 132, 28, 33, (60, 60, 70))  # door
    cv.fill(ox + 238, oy + 100, 18, 65, WHITE)     # candle
    cv.fill(ox + 238, oy + 100, 18, 2, GREY)
    cv.fill(ox + 238, oy + 100, 2, 65, GREY)
    cv.fill(ox + 254, oy + 100, 2, 65, GREY)
    cv.segment(ox + 247, oy + 100, ox + 247, oy + 92, INK)  # wick
    cv.ellipse(ox + 247, oy + 82, 8, 13, (240, 140, 0))    # flame
    cv.ellipse(ox + 247, oy + 85, 4, 7, GOLD)


def v_gemini(cv, ox, oy):
    """Smart glasses with a gold '4' badge and glints."""
    lens = (150, 190, 230)
    cv.ellipse(ox + 110, oy + 95, 45, 38, lens)    # left lens
    cv.ellipse(ox + 110, oy + 95, 36, 30, WHITE)
    cv.ellipse(ox + 210, oy + 95, 45, 38, lens)    # right lens
    cv.ellipse(ox + 210, oy + 95, 36, 30, WHITE)
    cv.thick(ox + 155, oy + 95, ox + 165, oy + 95, DARK, 5)  # bridge
    cv.thick(ox + 65, oy + 95, ox + 45, oy + 70, DARK, 5)    # temples
    cv.thick(ox + 255, oy + 95, ox + 275, oy + 70, DARK, 5)
    sparkle(cv, ox + 62, oy + 42, 12, GOLD)
    sparkle(cv, ox + 262, oy + 38, 10, GOLD)
    sparkle(cv, ox + 160, oy + 150, 9, GOLD)
    cv.disc(ox + 272, oy + 148, 24, GOLD)          # '4' badge
    cv.disc(ox + 272, oy + 148, 20, (200, 160, 0))
    draw_text(cv, "4", ox + 272, oy + 137, 3, WHITE, center=True)


def v_england(cv, ox, oy):
    """Goal net, ball in the net, striker mid-kick."""
    net = (200, 205, 210)
    for gx in range(70, 261, 20):                  # net mesh
        cv.segment(ox + gx, oy + 40, ox + gx, oy + 150, net)
    for gy in range(40, 151, 18):
        cv.segment(ox + 70, oy + gy, ox + 260, oy + gy, net)
    cv.fill(ox + 66, oy + 36, 6, 118, WHITE)       # posts + crossbar
    cv.fill(ox + 258, oy + 36, 6, 118, WHITE)
    cv.fill(ox + 66, oy + 36, 198, 6, WHITE)
    cv.disc(ox + 200, oy + 108, 20, (200, 205, 210))  # ball rim
    cv.disc(ox + 200, oy + 108, 18, WHITE)            # ball
    cv.disc(ox + 200, oy + 108, 5, INK)
    for dx, dy in ((-14, -12), (14, -12), (-14, 12), (14, 12)):
        cv.disc(ox + 200 + dx, oy + 108 + dy, 3, INK)
    cv.disc(ox + 42, oy + 88, 10, SKIN)            # striker head
    cv.fill(ox + 34, oy + 98, 16, 30, WHITE)       # shirt
    cv.fill(ox + 36, oy + 128, 12, 14, NAVY)       # shorts
    cv.thick(ox + 40, oy + 142, ox + 30, oy + 168, INK, 5)   # standing leg
    cv.thick(ox + 46, oy + 142, ox + 78, oy + 128, INK, 5)   # kicking leg
    cv.thick(ox + 36, oy + 104, ox + 22, oy + 88, SKIN, 5)   # arms
    cv.thick(ox + 48, oy + 104, ox + 62, oy + 88, SKIN, 5)


def v_hormuz(cv, ox, oy):
    """LNG tanker, a spiked mine, and a blast star above the Strait."""
    cv.fill(ox + 10, oy + 130, 300, 40, STEEL)     # sea
    cv.fill(ox + 55, oy + 95, 210, 30, DARK)       # hull
    cv.triangle(ox + 265, oy + 95, ox + 300, oy + 95,
                ox + 265, oy + 125, DARK)          # bow
    cv.fill(ox + 80, oy + 70, 40, 25, RED)         # deck containers
    cv.fill(ox + 125, oy + 70, 40, 25, GOLD)
    cv.fill(ox + 170, oy + 70, 40, 25, OCEAN)
    cv.fill(ox + 220, oy + 60, 35, 35, WHITE)      # bridge tower
    cv.fill(ox + 226, oy + 68, 23, 10, (90, 140, 190))
    cv.fill(ox + 258, oy + 68, 14, 27, DARK)       # funnel
    cv.disc(ox + 265, oy + 52, 8, (165, 170, 175))  # smoke
    cv.disc(ox + 274, oy + 38, 10, (175, 180, 185))
    cv.disc(ox + 264, oy + 22, 8, (185, 190, 195))
    sparkle(cv, ox + 150, oy + 38, 16, GOLD)       # blast star
    sparkle(cv, ox + 150, oy + 38, 8, RED)
    mx, my = ox + 42, oy + 62                      # mine
    for k in range(8):
        a = math.pi * k / 4.0
        cv.segment(mx, my,
                   mx + int(20 * math.cos(a)), my + int(20 * math.sin(a)),
                   INK)
    cv.disc(mx, my, 12, INK)
    cv.disc(mx, my, 8, DARK)
    cv.segment(ox + 30, oy + 142, ox + 90, oy + 142, WHITE)  # wave lines
    cv.segment(ox + 130, oy + 154, ox + 200, oy + 154, WHITE)
    cv.segment(ox + 220, oy + 142, ox + 290, oy + 142, WHITE)


# -------------------------------------------------------------------- page
def draw_page():
    cv = Canvas()
    # outer frame
    cv.fill(10, 10, 1004, 3, INK)
    cv.fill(10, 1011, 1004, 3, INK)
    cv.fill(10, 10, 3, 1004, INK)
    cv.fill(1011, 10, 3, 1004, INK)

    # masthead
    draw_text(cv, "FRIDAY 13 NOVEMBER 2026", 512, 26, 5, INK, center=True)
    draw_text(cv, "THE WORLD TODAY", 512, 72, 3, INK, center=True)
    cv.fill(40, 106, 944, 4, INK)
    cv.fill(40, 114, 944, 2, INK)

    # lead story: globe, dove, flags, banner, deck line
    draw_globe(cv, 512, 292, 118)
    draw_dove(cv)
    flag_pole(cv, 140, 210)
    flag_ukraine(cv, 140, 210)
    flag_pole(cv, 140, 280)
    flag_eu(cv, 140, 280)
    flag_pole(cv, 800, 245)
    flag_usa(cv, 800, 245)
    cv.fill(112, 424, 800, 46, NAVY)
    draw_text(cv, "EUROPE JOINS UKRAINE TALKS", 512, 436, 3, WHITE,
              center=True)
    draw_text(cv, "PUTIN MEETS WITKOFF AND KUSHNER IN MOSCOW",
              512, 478, 2, INK, center=True)

    # six vignettes, 2 rows x 3 columns
    grid = [
        (16, 508, v_nvidia, "NVIDIA CEO RESIGNS"),
        (352, 508, v_microsoft, "MAIL AND TEAMS OUTAGE"),
        (688, 508, v_hospital, "HOSPITAL STRIKE KILLS SIX"),
        (16, 724, v_gemini, "GEMINI 4, SMART GLASSES"),
        (352, 724, v_england, "ENGLAND BEAT CROATIA"),
        (688, 724, v_hormuz, "MINE HITS LNG TANKER"),
    ]
    for x, y, fn, lab in grid:
        cell(cv, x, y)
        fn(cv, x, y)
        cell_label(cv, x, y, lab)

    # footer ticker: Storm Charles + the planned prisoner exchange
    cv.fill(16, 940, 992, 56, NAVY)
    draw_text(cv, "STORM CHARLES BATTERS PORTUGAL  •  "
                 "LARGEST PRISONER SWAP PLANNED",
              512, 958, 2, WHITE, center=True)
    return cv


# --------------------------------------------------------------------- png
def encode_png(cv):
    raw = b"".join(
        b"\x00" + bytes(cv.buf[y * W * 3:(y + 1) * W * 3])
        for y in range(H)
    )

    def chunk(tag, data):
        out = struct.pack(">I", len(data)) + tag + data
        return out + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))


def output_dir():
    """Where entry.png goes.

    The grader runs as uid 65534 on a read-only filesystem with a
    writable /output mounted and sets no MAKEFUN_OUTPUT_DIR, so the
    /output fallback is what saves the run there. Locally, an explicit
    env var wins; with neither, fall back to the current directory.
    """
    env_dir = os.environ.get("MAKEFUN_OUTPUT_DIR")
    if env_dir:
        return env_dir
    if os.path.isdir("/output"):
        return "/output"
    return "."


def main():
    out_dir = output_dir()
    os.makedirs(out_dir, exist_ok=True)
    data = encode_png(draw_page())
    path = os.path.join(out_dir, "entry.png")
    with open(path, "wb") as f:
        f.write(data)
    print(f"wrote {path} ({len(data)} bytes)")


if __name__ == "__main__":
    main()
