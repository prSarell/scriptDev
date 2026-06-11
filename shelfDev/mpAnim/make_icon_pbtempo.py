"""
make_icon_pbtempo.py — generates iconPbTempo.png
Centres the bullet on a white square canvas with rounded corners.
Run with: mayapy make_icon_pbtempo.py  (requires Pillow + numpy)
"""
from PIL import Image, ImageDraw
import numpy as np
import os

SIZE     = 512
CORNER_R = 60
PAD      = 40

SRC = r"C:\Users\patsa\OneDrive\Pictures\Screenshots\bullet.png"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   'icons', 'iconPbTempo.png')

# ── Load, flatten to white background ────────────────────────────────────────
src = Image.open(SRC).convert('RGBA')
bg = Image.new('RGBA', src.size, (255, 255, 255, 255))
bg.paste(src, mask=src.split()[3])
gray = bg.convert('L')

# ── Auto-crop to dark content ────────────────────────────────────────────────
arr = np.array(gray)
dark = arr < 200
rows = np.any(dark, axis=1)
cols = np.any(dark, axis=0)
r0, r1 = np.where(rows)[0][[0, -1]]
c0, c1 = np.where(cols)[0][[0, -1]]
margin = 4
gray = gray.crop((max(c0 - margin, 0), max(r0 - margin, 0),
                  min(c1 + margin, gray.width), min(r1 + margin, gray.height)))

# ── Scale to fit, preserving aspect ratio ────────────────────────────────────
max_dim = SIZE - 2 * PAD
w, h = gray.size
scale = min(max_dim / w, max_dim / h)
gray = gray.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

# ── Binarize — remove gray background from source ────────────────────────────
arr2 = np.array(gray)
binary = np.where(arr2 < 150, 0, 255).astype(np.uint8)
gray = Image.fromarray(binary, 'L')

# ── Centre on white canvas ────────────────────────────────────────────────────
canvas = Image.new('RGBA', (SIZE, SIZE), (255, 255, 255, 255))
ox = (SIZE - gray.width) // 2
oy = (SIZE - gray.height) // 2
canvas.paste(gray.convert('RGBA'), (ox, oy))

# ── Rounded corners ───────────────────────────────────────────────────────────
corner_mask = Image.new('L', (SIZE, SIZE), 0)
ImageDraw.Draw(corner_mask).rounded_rectangle(
    [0, 0, SIZE - 1, SIZE - 1], radius=CORNER_R, fill=255
)
canvas.putalpha(corner_mask)

canvas.save(OUT)
print('Saved: {}'.format(OUT))
