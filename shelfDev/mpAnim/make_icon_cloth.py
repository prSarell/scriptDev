"""
Generates iconClothChain.png in the icons/ folder using only stdlib.
Run with: python make_icon_cloth.py  (or mayapy)
"""
import math
import os
import struct
import zlib


def _png(pixels, w, h):
    """Encode RGBA pixel list as a minimal PNG bytestring."""
    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    raw = b""
    for y in range(h):
        raw += b"\x00"
        for x in range(w):
            r, g, b, a = pixels[y * w + x]
            raw += struct.pack("BBBB", r, g, b, a)

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))  # 8-bit RGB
    # Use RGBA (color type 6)
    ihdr = chunk(b"IHDR", struct.pack(">II", w, h) + bytes([8, 6, 0, 0, 0]))
    idat = chunk(b"IDAT", zlib.compress(raw))
    iend = chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


def _blend(bg, fg):
    """Alpha-composite fg (r,g,b,a) over bg (r,g,b,a)."""
    a = fg[3] / 255.0
    return (
        int(fg[0] * a + bg[0] * (1 - a)),
        int(fg[1] * a + bg[1] * (1 - a)),
        int(fg[2] * a + bg[2] * (1 - a)),
        min(255, bg[3] + int(fg[3] * (1 - bg[3] / 255.0))),
    )


def _draw_circle(pixels, w, cx, cy, r, color, thickness=1.5):
    """Draw an antialiased circle outline."""
    for y in range(max(0, int(cy - r - 2)), min(w, int(cy + r + 2))):
        for x in range(max(0, int(cx - r - 2)), min(w, int(cx + r + 2))):
            dist = math.hypot(x - cx, y - cy)
            alpha = max(0.0, 1.0 - abs(dist - r) / (thickness * 0.75))
            if alpha > 0:
                c = (color[0], color[1], color[2], int(color[3] * alpha))
                pixels[y * w + x] = _blend(pixels[y * w + x], c)


def _draw_ellipse(pixels, w, cx, cy, rx, ry, angle_deg, color, thickness=3.0):
    """Draw a rotated ellipse outline by sampling points along it."""
    a = math.radians(angle_deg)
    steps = 120
    prev = None
    for i in range(steps + 1):
        t = 2 * math.pi * i / steps
        lx = rx * math.cos(t)
        ly = ry * math.sin(t)
        rx2 = lx * math.cos(a) - ly * math.sin(a) + cx
        ry2 = lx * math.sin(a) + ly * math.cos(a) + cy
        if prev:
            _draw_line(pixels, w, prev[0], prev[1], rx2, ry2, color, thickness)
        prev = (rx2, ry2)


def _draw_line(pixels, w, x0, y0, x1, y1, color, thickness=2.0):
    """Draw an antialiased line segment."""
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    if length == 0:
        return
    steps = max(1, int(length * 2))
    for i in range(steps + 1):
        t = i / steps
        px = x0 + dx * t
        py = y0 + dy * t
        for oy in range(int(py - thickness), int(py + thickness) + 2):
            for ox in range(int(px - thickness), int(px + thickness) + 2):
                if 0 <= ox < w and 0 <= oy < w:
                    d = math.hypot(ox - px, oy - py)
                    alpha = max(0.0, 1.0 - d / (thickness * 0.6))
                    if alpha > 0:
                        c = (color[0], color[1], color[2], int(color[3] * alpha))
                        pixels[oy * w + ox] = _blend(pixels[oy * w + ox], c)


def _draw_cubic(pixels, w, x0, y0, cx1, cy1, cx2, cy2, x1, y1, color, thickness=2.0):
    """Draw an antialiased cubic bezier."""
    steps = 80
    prev = (x0, y0)
    for i in range(1, steps + 1):
        t = i / steps
        mt = 1 - t
        x = mt**3*x0 + 3*mt**2*t*cx1 + 3*mt*t**2*cx2 + t**3*x1
        y = mt**3*y0 + 3*mt**2*t*cy1 + 3*mt*t**2*cy2 + t**3*y1
        _draw_line(pixels, w, prev[0], prev[1], x, y, color, thickness)
        prev = (x, y)


SIZE = 64
pixels = [(0, 0, 0, 0)] * (SIZE * SIZE)

# Background rounded rect (teal-blue)
BG = (40, 110, 140, 255)
r_corner = 10
for y in range(SIZE):
    for x in range(SIZE):
        dx = max(0, r_corner - x + 2, x - (SIZE - 3 - r_corner))
        dy = max(0, r_corner - y + 2, y - (SIZE - 3 - r_corner))
        dist = math.hypot(dx, dy)
        alpha = max(0.0, min(1.0, r_corner + 0.5 - dist))
        if alpha > 0:
            pixels[y * SIZE + x] = (BG[0], BG[1], BG[2], int(BG[3] * alpha))

# Three chain-link ellipses in a diagonal S arrangement
LINK = (220, 240, 255, 255)
links = [
    (20, 18, -30),
    (32, 33,   0),
    (44, 48,  30),
]
for cx, cy, angle in links:
    _draw_ellipse(pixels, SIZE, cx, cy, 10, 6, angle, LINK, thickness=3.0)

# Connector dots between links
DOT = (200, 230, 255, 200)
for cx, cy in [(27, 26), (37, 41)]:
    _draw_circle(pixels, SIZE, cx, cy, 2.0, DOT, thickness=2.0)

# Wavy cloth line at the bottom
WAVE = (160, 220, 255, 200)
_draw_cubic(pixels, SIZE, 10, 55, 18, 48, 26, 62, 34, 55, WAVE, thickness=2.0)
_draw_cubic(pixels, SIZE, 34, 55, 42, 48, 50, 62, 58, 55, WAVE, thickness=2.0)

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons", "iconClothChain.png")
with open(out, "wb") as f:
    f.write(_png(pixels, SIZE, SIZE))
print("Saved:", out)
