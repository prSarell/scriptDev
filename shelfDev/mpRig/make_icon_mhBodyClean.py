"""
make_icon_mhBodyClean.py — generates iconMhBodyClean.png
Processes handClean.png (Desktop) into a shelf icon with rounded corners and MH badge.
Run with: mayapy make_icon_mhBodyClean.py  (requires Pillow + numpy)
"""
import os
import sys
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_mh_badge import add_mh_badge

SIZE     = 512
CORNER_R = 60
PAD      = 36

SRC = os.path.join(os.path.expanduser('~'), 'OneDrive', 'Desktop', 'handClean.png')
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icons', 'iconMhBodyClean.png')

# Load and flatten to white background
src = Image.open(SRC).convert('RGBA')
bg = Image.new('RGBA', src.size, (255, 255, 255, 255))
bg.alpha_composite(src)
gray = bg.convert('L')

# Auto-crop to dark content
arr = np.array(gray)
dark = arr < 200
rows = np.any(dark, axis=1)
cols = np.any(dark, axis=0)
r0, r1 = np.where(rows)[0][[0, -1]]
c0, c1 = np.where(cols)[0][[0, -1]]
margin = 8
gray = gray.crop((max(c0 - margin, 0), max(r0 - margin, 0),
                  min(c1 + margin, gray.width), min(r1 + margin, gray.height)))

# Scale to fit with padding, preserving aspect ratio
max_dim = SIZE - 2 * PAD
w, h = gray.size
scale = min(max_dim / w, max_dim / h)
gray = gray.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

# Centre on white RGBA canvas
canvas = Image.new('RGBA', (SIZE, SIZE), (255, 255, 255, 255))
ox = (SIZE - gray.width) // 2
oy = (SIZE - gray.height) // 2
canvas.paste(gray.convert('RGB'), (ox, oy))

# Rounded corners
mask = Image.new('L', (SIZE, SIZE), 0)
ImageDraw.Draw(mask).rounded_rectangle([0, 0, SIZE - 1, SIZE - 1], radius=CORNER_R, fill=255)
canvas.putalpha(mask)

# MH badge
canvas = add_mh_badge(canvas)

canvas.save(OUT)
print('Saved:', OUT)
