"""
make_icon_dsfr.py — generates iconDsfr.png
Face oval with surface joints (dots) — represents Double Skin Face Rig.
Run with: mayapy make_icon_dsfr.py  (requires Pillow)
"""
from PIL import Image, ImageDraw
import os

SIZE     = 512
CORNER_R = 60
CX, CY   = SIZE // 2, SIZE // 2

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   'icons', 'iconDsfr.png')

canvas = Image.new('RGBA', (SIZE, SIZE), (255, 255, 255, 255))
draw   = ImageDraw.Draw(canvas)

# ── Face oval ─────────────────────────────────────────────────────────────────
FACE_W, FACE_H = 360, 440
face_box = [
    CX - FACE_W // 2, CY - FACE_H // 2,
    CX + FACE_W // 2, CY + FACE_H // 2,
]
LINE = 22
draw.ellipse(face_box, outline=(0, 0, 0, 255), width=LINE)

# ── Surface joint dots (representing joints pinned to face surface) ────────────
import math

DOT_R   = 20
DOT_FILL   = (0, 0, 0, 255)
DOT_STROKE = 14

# 8 joint positions — mirrored pairs on the face oval plus lip corners
joint_angles_with_r = [
    # (angle_deg, radial_fraction)  angle 0=right, 90=bottom
    (  45, 0.80),   # cheek R
    ( 135, 0.80),   # cheek L
    ( -45, 0.80),   # brow R
    (-135, 0.80),   # brow L
    (  90, 0.95),   # chin
    ( -90, 0.80),   # forehead
    (  20, 0.95),   # lip corner R
    ( 160, 0.95),   # lip corner L
]

RX = FACE_W / 2
RY = FACE_H / 2

for angle_deg, rfrac in joint_angles_with_r:
    a = math.radians(angle_deg)
    x = CX + rfrac * RX * math.cos(a)
    y = CY + rfrac * RY * math.sin(a)
    # white filled circle with black border
    draw.ellipse(
        [x - DOT_R - DOT_STROKE // 2, y - DOT_R - DOT_STROKE // 2,
         x + DOT_R + DOT_STROKE // 2, y + DOT_R + DOT_STROKE // 2],
        outline=(0, 0, 0, 255), fill=(255, 255, 255, 255), width=8,
    )

# ── Rounded corner mask ───────────────────────────────────────────────────────
mask = Image.new('L', (SIZE, SIZE), 0)
ImageDraw.Draw(mask).rounded_rectangle(
    [0, 0, SIZE - 1, SIZE - 1], radius=CORNER_R, fill=255
)
canvas.putalpha(mask)

canvas.save(OUT)
print('Saved: {}'.format(OUT))
