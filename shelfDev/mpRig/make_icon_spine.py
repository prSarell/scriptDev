"""
make_icon_spine.py — generates iconSpine.png
Run with: mayapy make_icon_spine.py
"""
from PIL import Image, ImageDraw
import os

SIZE = 512
BG    = (28, 28, 28, 255)
BONE  = (225, 225, 225, 255)
OUT   = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     'icons', 'iconSpine.png')

img  = Image.new('RGBA', (SIZE, SIZE), BG)
draw = ImageDraw.Draw(img)

cx = SIZE // 2

# Vertebra geometry — posterior view
# Each vertebra: wide flat body + narrow spinous process nub at bottom centre
N         = 9    # vertebrae
body_w    = 200  # full width including lateral masses
body_h    = 28   # height of main horizontal bar
nub_w     = 38   # width of central spinous process nub
nub_h     = 16   # height of spinous process nub below body
disc_gap  = 10   # gap between vertebrae
body_r    = 10   # corner radius
nub_r     = 6

total_h = N * (body_h + nub_h) + (N - 1) * disc_gap
start_y = (SIZE - total_h) // 2

for i in range(N):
    y = start_y + i * (body_h + nub_h + disc_gap)

    # Main horizontal bar (laminae + lateral masses)
    draw.rounded_rectangle(
        [cx - body_w // 2, y,
         cx + body_w // 2, y + body_h],
        radius=body_r, fill=BONE
    )

    # Spinous process nub hanging below the centre of the bar
    draw.rounded_rectangle(
        [cx - nub_w // 2, y + body_h - nub_r,
         cx + nub_w // 2, y + body_h + nub_h],
        radius=nub_r, fill=BONE
    )

img.save(OUT)
print(f'Saved: {OUT}')
