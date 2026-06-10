"""
make_icon_follicle.py — generates iconFollicleRig.png
Run with: mayapy make_icon_follicle.py  (or any Python with Pillow)
"""
from PIL import Image, ImageDraw
import os

SIZE = 512
BG          = (28,  28,  28,  255)
SURF_FILL   = (38,  70,  82,  255)
SURF_EDGE   = (70,  130, 155, 255)
FOL_COLOR   = (75,  205, 225, 255)
JNT_COLOR   = (225, 175, 70,  255)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   'icons', 'iconFollicleRig.png')

img  = Image.new('RGBA', (SIZE, SIZE), BG)
draw = ImageDraw.Draw(img)

# Surface panel
sx0, sy0, sx1, sy1 = 68, 160, 444, 420
draw.rounded_rectangle([sx0, sy0, sx1, sy1], radius=22,
                        fill=SURF_FILL, outline=SURF_EDGE, width=6)

# Grid of follicles — 3 cols x 3 rows
COLS, ROWS = 3, 3
margin_x, margin_y = 68, 60
step_x = (sx1 - sx0 - 2 * margin_x) // (COLS - 1)
step_y = (sy1 - sy0 - 2 * margin_y) // (ROWS - 1)
FOL_R  = 18
JNT_LEN = 52
JNT_R   = 10
JNT_W   = 7

# Which follicles get a visible joint stub (skip corners to keep it clean)
show_joint = {(0,1), (1,0), (1,1), (1,2), (2,1)}

for r in range(ROWS):
    for c in range(COLS):
        fx = sx0 + margin_x + c * step_x
        fy = sy0 + margin_y + r * step_y

        if (r, c) in show_joint:
            tip_y = fy - FOL_R - JNT_LEN
            draw.line([(fx, fy - FOL_R), (fx, tip_y)], fill=JNT_COLOR, width=JNT_W)
            draw.ellipse([fx - JNT_R, tip_y - JNT_R,
                          fx + JNT_R, tip_y + JNT_R], fill=JNT_COLOR)

        draw.ellipse([fx - FOL_R, fy - FOL_R,
                      fx + FOL_R, fy + FOL_R], fill=FOL_COLOR)

img.save(OUT)
print(f'Saved: {OUT}')
