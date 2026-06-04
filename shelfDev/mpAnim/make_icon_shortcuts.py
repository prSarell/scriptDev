"""
make_icon_shortcuts.py — generates iconShortCuts.png
Run with: mayapy make_icon_shortcuts.py
"""
from PIL import Image, ImageDraw
import os

SIZE    = 512
YELLOW  = (255, 185, 0)
BLACK   = (20, 20, 20)
OUT     = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'icons', 'iconShortCuts.png')

img  = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Yellow square background with slightly rounded corners
margin = 16
r      = 48
draw.rounded_rectangle([margin, margin, SIZE - margin, SIZE - margin],
                        radius=r, fill=YELLOW)

# Chevron — classic road-sign ">" shape as a 6-point polygon
# Points (clockwise): top-left, top-right, tip, bottom-right, bottom-left, inner-notch
S     = SIZE
mid_y = S / 2

p1 = (S * 0.10, S * 0.08)   # top-left outer
p2 = (S * 0.62, S * 0.08)   # top-right outer (pulled left so tip sticks out)
p3 = (S * 0.90, mid_y)       # tip — sharp rightmost point
p4 = (S * 0.62, S * 0.92)   # bottom-right outer
p5 = (S * 0.10, S * 0.92)   # bottom-left outer
p6 = (S * 0.36, mid_y)       # inner notch

draw.polygon([p1, p2, p3, p4, p5, p6], fill=BLACK)

img.save(OUT)
print(f'Saved: {OUT}')
