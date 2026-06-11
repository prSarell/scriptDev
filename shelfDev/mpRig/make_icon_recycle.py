"""
make_icon_recycle.py — generates iconMhRecycle.png
Run with: mayapy make_icon_recycle.py  (requires Pillow)
"""
from PIL import Image, ImageDraw
import numpy as np
import os

SIZE     = 512
PINK     = (230, 80, 155)
WHITE    = (255, 255, 255)
CORNER_R = 60
PAD      = 20

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   'icons', 'iconMhBsBake.png')
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   'icons', 'iconMhRecycle.png')

src = Image.open(SRC).convert('L')

# Auto-crop to dark pixels
arr_src = np.array(src)
dark = arr_src < 200
rows = np.any(dark, axis=1)
cols = np.any(dark, axis=0)
r0, r1 = np.where(rows)[0][[0, -1]]
c0, c1 = np.where(cols)[0][[0, -1]]
margin = 8
src = src.crop((max(c0 - margin, 0), max(r0 - margin, 0),
                min(c1 + margin, src.width), min(r1 + margin, src.height)))

# Scale to fit
max_dim = SIZE - 2 * PAD
w, h = src.size
scale = min(max_dim / w, max_dim / h)
src = src.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

# Centre on white canvas
canvas = Image.new('L', (SIZE, SIZE), 255)
ox = (SIZE - src.width) // 2
oy = (SIZE - src.height) // 2
canvas.paste(src, (ox, oy))

# dark pixels → white, light pixels → pink
arr = np.array(canvas, dtype=float) / 255.0
inv = 1.0 - arr  # dark=1.0, light=0.0

rgba = np.zeros((SIZE, SIZE, 4), dtype=np.uint8)
rgba[:, :, 0] = (PINK[0] + (WHITE[0] - PINK[0]) * inv).astype(np.uint8)
rgba[:, :, 1] = (PINK[1] + (WHITE[1] - PINK[1]) * inv).astype(np.uint8)
rgba[:, :, 2] = (PINK[2] + (WHITE[2] - PINK[2]) * inv).astype(np.uint8)
rgba[:, :, 3] = 255

result = Image.fromarray(rgba, 'RGBA')

# Rounded corners
corner_mask = Image.new('L', (SIZE, SIZE), 0)
ImageDraw.Draw(corner_mask).rounded_rectangle(
    [0, 0, SIZE - 1, SIZE - 1], radius=CORNER_R, fill=255
)
result.putalpha(corner_mask)

result.save(OUT)
print(f'Saved: {OUT}')
