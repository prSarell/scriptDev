"""
make_icon_dna_repair.py — generates iconMhDnaRepair.png
White skull on blue background with a red medical cross overlay.
Run with: python make_icon_dna_repair.py  (requires Pillow + numpy)
"""
from PIL import Image, ImageDraw
import numpy as np
import os

SIZE      = 512
BG        = (30, 80, 165)    # medical blue
WHITE     = (255, 255, 255)
RED       = (220, 35, 35)
CORNER_R  = 60
PAD       = 20

# Cross geometry
CROSS_W   = 72    # arm thickness
CROSS_LEN = 290   # total arm length (centred)

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   'icons', 'iconMhBsBake.png')
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   'icons', 'iconMhDnaRepair.png')

# ── Load and crop skull ──────────────────────────────────────────────────────
src = Image.open(SRC).convert('L')

arr_src = np.array(src)
dark = arr_src < 200
rows = np.any(dark, axis=1)
cols = np.any(dark, axis=0)
r0, r1 = np.where(rows)[0][[0, -1]]
c0, c1 = np.where(cols)[0][[0, -1]]
margin = 8
src = src.crop((max(c0 - margin, 0), max(r0 - margin, 0),
                min(c1 + margin, src.width), min(r1 + margin, src.height)))

# ── Scale to fit ─────────────────────────────────────────────────────────────
max_dim = SIZE - 2 * PAD
w, h = src.size
scale = min(max_dim / w, max_dim / h)
src = src.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

# ── Centre on white canvas, then invert to white skull on blue ───────────────
canvas = Image.new('L', (SIZE, SIZE), 255)
ox = (SIZE - src.width) // 2
oy = (SIZE - src.height) // 2
canvas.paste(src, (ox, oy))

arr = np.array(canvas, dtype=float) / 255.0
inv = 1.0 - arr  # skull outline = 1.0, bg = 0.0

rgba = np.zeros((SIZE, SIZE, 4), dtype=np.uint8)
rgba[:, :, 0] = (BG[0] + (WHITE[0] - BG[0]) * inv).astype(np.uint8)
rgba[:, :, 1] = (BG[1] + (WHITE[1] - BG[1]) * inv).astype(np.uint8)
rgba[:, :, 2] = (BG[2] + (WHITE[2] - BG[2]) * inv).astype(np.uint8)
rgba[:, :, 3] = 255

result = Image.fromarray(rgba, 'RGBA')

# ── Draw red cross ────────────────────────────────────────────────────────────
draw = ImageDraw.Draw(result)
cx = cy = SIZE // 2
half_l = CROSS_LEN // 2
half_w = CROSS_W  // 2

# Horizontal bar
draw.rectangle([cx - half_l, cy - half_w, cx + half_l, cy + half_w], fill=RED + (255,))
# Vertical bar
draw.rectangle([cx - half_w, cy - half_l, cx + half_w, cy + half_l], fill=RED + (255,))

# ── Rounded corners ───────────────────────────────────────────────────────────
corner_mask = Image.new('L', (SIZE, SIZE), 0)
ImageDraw.Draw(corner_mask).rounded_rectangle(
    [0, 0, SIZE - 1, SIZE - 1], radius=CORNER_R, fill=255
)
result.putalpha(corner_mask)

result.save(OUT)
print('Saved: {}'.format(OUT))
