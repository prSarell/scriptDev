"""
make_icon_vpShader.py — generates iconVpShader.png
Human silhouette with orange dots at joint-critical positions.
Run with: python make_icon_vpShader.py  (requires Pillow)
"""
from PIL import Image, ImageDraw
import os

SIZE     = 512
CORNER_R = 60
CX       = SIZE // 2

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   'icons', 'iconVpShader.png')

canvas = Image.new('RGBA', (SIZE, SIZE), (255, 255, 255, 255))
draw   = ImageDraw.Draw(canvas)

BLACK  = (0, 0, 0, 255)
ORANGE = (255, 102, 0, 255)
WHITE  = (255, 255, 255, 255)

LINE = 18  # stroke width for silhouette

# ── Head ─────────────────────────────────────────────────────────────────────
HEAD_R = 52
HEAD_CY = 80
draw.ellipse(
    [CX - HEAD_R, HEAD_CY - HEAD_R, CX + HEAD_R, HEAD_CY + HEAD_R],
    outline=BLACK, width=LINE,
)

# ── Neck ─────────────────────────────────────────────────────────────────────
NECK_W = 24
draw.rectangle(
    [CX - NECK_W, HEAD_CY + HEAD_R - 4, CX + NECK_W, HEAD_CY + HEAD_R + 30],
    fill=BLACK,
)

# ── Torso ────────────────────────────────────────────────────────────────────
TORSO_TOP    = HEAD_CY + HEAD_R + 26
TORSO_BOTTOM = 300
TORSO_W      = 90
draw.rounded_rectangle(
    [CX - TORSO_W, TORSO_TOP, CX + TORSO_W, TORSO_BOTTOM],
    radius=20, outline=BLACK, width=LINE,
)

# ── Arms ─────────────────────────────────────────────────────────────────────
SHOULDER_Y = TORSO_TOP + 30
ELBOW_Y    = TORSO_TOP + 110
WRIST_Y    = TORSO_TOP + 195
ARM_W      = 14

for side in (-1, 1):
    sx = CX + side * (TORSO_W - 4)
    ex = CX + side * 148
    wx = CX + side * 170

    # Upper arm
    draw.line([sx, SHOULDER_Y, ex, ELBOW_Y], fill=BLACK, width=ARM_W)
    # Lower arm
    draw.line([ex, ELBOW_Y, wx, WRIST_Y], fill=BLACK, width=ARM_W)

# ── Legs ─────────────────────────────────────────────────────────────────────
HIP_Y   = TORSO_BOTTOM - 10
KNEE_Y  = 390
ANKLE_Y = 470
LEG_W   = 16
HIP_X_OFF   = 46
KNEE_X_OFF  = 60
ANKLE_X_OFF = 64

for side in (-1, 1):
    hx = CX + side * HIP_X_OFF
    kx = CX + side * KNEE_X_OFF
    ax = CX + side * ANKLE_X_OFF

    draw.line([hx, HIP_Y, kx, KNEE_Y],   fill=BLACK, width=LEG_W)
    draw.line([kx, KNEE_Y, ax, ANKLE_Y], fill=BLACK, width=LEG_W)

# ── Joint dots (orange — critical positions) ─────────────────────────────────
DOT_R    = 18
DOT_RING = 10   # white ring width to pop dot off silhouette

joint_positions = [
    # shoulders
    (CX - TORSO_W + 4, SHOULDER_Y),
    (CX + TORSO_W - 4, SHOULDER_Y),
    # elbows
    (CX - 148, ELBOW_Y),
    (CX + 148, ELBOW_Y),
    # wrists
    (CX - 170, WRIST_Y),
    (CX + 170, WRIST_Y),
    # hips
    (CX - HIP_X_OFF, HIP_Y),
    (CX + HIP_X_OFF, HIP_Y),
    # knees
    (CX - KNEE_X_OFF, KNEE_Y),
    (CX + KNEE_X_OFF, KNEE_Y),
    # ankles
    (CX - ANKLE_X_OFF, ANKLE_Y),
    (CX + ANKLE_X_OFF, ANKLE_Y),
]

for (x, y) in joint_positions:
    r_outer = DOT_R + DOT_RING // 2
    draw.ellipse(
        [x - r_outer, y - r_outer, x + r_outer, y + r_outer],
        fill=WHITE,
    )
    draw.ellipse(
        [x - DOT_R, y - DOT_R, x + DOT_R, y + DOT_R],
        fill=ORANGE,
    )

# ── Rounded corner mask ───────────────────────────────────────────────────────
mask = Image.new('L', (SIZE, SIZE), 0)
ImageDraw.Draw(mask).rounded_rectangle(
    [0, 0, SIZE - 1, SIZE - 1], radius=CORNER_R, fill=255
)
canvas.putalpha(mask)

from make_mh_badge import add_mh_badge
canvas = add_mh_badge(canvas)

canvas.save(OUT)
print('Saved: {}'.format(OUT))
