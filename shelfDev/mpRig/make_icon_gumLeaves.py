"""
make_icon_gumLeaves.py — generates iconGumLeaves.png
Run with: mayapy make_icon_gumLeaves.py  (requires Pillow)
"""
from PIL import Image, ImageDraw
import math
import os

SIZE     = 256
BG       = (45, 45, 50, 255)     # matches iconGumTree.png background
LEAF     = (95, 140, 70, 255)
LEAF_DK  = (70, 105, 52, 255)    # vein / shading
STEM     = (140, 100, 65, 255)   # matches iconGumTree.png trunk brown
CORNER_R = 40

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   'icons', 'iconGumLeaves.png')


def _leaf_outline(base_x, base_y, length, width, angle_deg):
    """Simple symmetric lanceolate leaf blade (pointed base + tip, wide
    belly at the middle), drawn pointing straight down (+Y) in local space
    then rotated so `angle_deg` (0 = straight down) sets its lean."""
    steps = 20
    left, right = [], []
    for i in range(steps + 1):
        t = i / steps
        belly = math.sin(t * math.pi)
        w = width * 0.5 * belly
        x = 0.0
        y = t * length
        left.append((x - w, y))
        right.append((x + w, y))
    pts = left + right[::-1]

    ang = math.radians(angle_deg)
    ca, sa = math.cos(ang), math.sin(ang)
    # local +Y (down) rotates toward angle_deg measured from straight down
    return [(base_x + x * ca + y * sa, base_y - x * sa + y * ca)
           for x, y in pts]


img = Image.new('RGBA', (SIZE, SIZE), BG)
draw = ImageDraw.Draw(img)

cx, cy = SIZE // 2, 62

# Short stem — everything hangs from this single attach point.
draw.line([(cx, cy - 26), (cx, cy)], fill=STEM, width=8)
draw.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=STEM)

# Three leaves fanned downward from the same point, each leaning a
# different amount off straight-down — echoes the tool's randomized,
# gravity-favouring droop.
leaves = [
    (cx, cy, 150, 46, -32),
    (cx, cy, 168, 50, 6),
    (cx, cy, 148, 44, 40),
]
for bx, by, length, width, angle in leaves:
    outline = _leaf_outline(bx, by, length, width, angle)
    draw.polygon(outline, fill=LEAF, outline=LEAF_DK)

for bx, by, length, width, angle in leaves:
    ang = math.radians(angle)
    tip = (bx + length * 0.94 * math.sin(ang),
           by + length * 0.94 * math.cos(ang))
    draw.line([(bx, by), tip], fill=LEAF_DK, width=3)

# Rounded corners
mask = Image.new('L', (SIZE, SIZE), 0)
ImageDraw.Draw(mask).rounded_rectangle(
    [0, 0, SIZE - 1, SIZE - 1], radius=CORNER_R, fill=255)
img.putalpha(mask)

img.save(OUT)
print(f'Saved: {OUT}')
