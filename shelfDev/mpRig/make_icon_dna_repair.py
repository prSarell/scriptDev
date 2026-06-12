"""
make_icon_dna_repair.py — generates iconMhDnaRepair.png
Same skull as iconMhBsBake.png but with X marks replacing the eye circles.
Black and white, no colour changes.
Run with: mayapy make_icon_dna_repair.py  (requires Pillow + numpy)
"""
from collections import deque
from PIL import Image, ImageDraw
import numpy as np
import os

SIZE     = 512
CORNER_R = 60
PAD      = 20
X_WIDTH  = 26   # stroke weight of the X lines

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   'icons', 'iconMhBsBake.png')
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   'icons', 'iconMhDnaRepair.png')


def bfs_label(mask):
    """Return (labels_array, n_labels) — pure-numpy BFS connected components."""
    H, W = mask.shape
    labeled = np.zeros((H, W), dtype=np.int32)
    n = 0
    ys, xs = np.where(mask)
    for start_y, start_x in zip(ys.tolist(), xs.tolist()):
        if labeled[start_y, start_x]:
            continue
        n += 1
        q = deque()
        q.append((start_y, start_x))
        labeled[start_y, start_x] = n
        while q:
            y, x = q.popleft()
            for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                ny, nx = y + dy, x + dx
                if 0 <= ny < H and 0 <= nx < W and mask[ny, nx] and not labeled[ny, nx]:
                    labeled[ny, nx] = n
                    q.append((ny, nx))
    return labeled, n


# ── Load source (RGBA → L) ────────────────────────────────────────────────────
src = Image.open(SRC).convert('RGBA')

# Build a grayscale from the alpha-composited version (white bg)
bg = Image.new('RGBA', src.size, (255, 255, 255, 255))
bg.paste(src, mask=src.split()[3])
gray = bg.convert('L')

# ── Auto-crop to content ──────────────────────────────────────────────────────
arr_src = np.array(gray)
dark = arr_src < 128
rows = np.any(dark, axis=1)
cols = np.any(dark, axis=0)
r0, r1 = np.where(rows)[0][[0, -1]]
c0, c1 = np.where(cols)[0][[0, -1]]
margin = 8
gray = gray.crop((max(c0 - margin, 0), max(r0 - margin, 0),
                  min(c1 + margin, gray.width), min(r1 + margin, gray.height)))

# ── Scale to fit SIZE ─────────────────────────────────────────────────────────
max_dim = SIZE - 2 * PAD
w, h = gray.size
scale = min(max_dim / w, max_dim / h)
gray = gray.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

# ── Centre on white canvas ────────────────────────────────────────────────────
canvas = Image.new('L', (SIZE, SIZE), 255)
ox = (SIZE - gray.width) // 2
oy = (SIZE - gray.height) // 2
canvas.paste(gray, (ox, oy))

# ── Find eye circles via BFS connected components ────────────────────────────
arr = np.array(canvas)
dark_mask = arr < 128

labeled, n_labels = bfs_label(dark_mask)

# Score each component: favour medium-sized blobs in upper half, not at border
eye_candidates = []
for lbl in range(1, n_labels + 1):
    ys_c, xs_c = np.where(labeled == lbl)
    size = len(ys_c)
    if size < 400 or size > 30000:
        continue
    cy = float(np.mean(ys_c))
    cx = float(np.mean(xs_c))
    if cy > SIZE * 0.72:          # below 72% = teeth/jaw, skip
        continue
    if ys_c.min() <= 2 or xs_c.min() <= 2:  # touches border = skull outline
        continue
    r_approx = float(np.sqrt(size / np.pi))
    eye_candidates.append((cx, cy, r_approx, size))

# Take the two largest in-range blobs and sort left → right
eye_candidates.sort(key=lambda e: -e[3])
eyes = sorted(eye_candidates[:2], key=lambda e: e[0])

if len(eyes) != 2:
    raise RuntimeError(
        'Expected 2 eye blobs, found {}. Candidates: {}'.format(
            len(eyes), eye_candidates
        )
    )

# ── Erase eye circles, draw X marks ─────────────────────────────────────────
result = canvas.convert('RGBA')
draw = ImageDraw.Draw(result)

for cx, cy, r, _ in eyes:
    # Erase with white ellipse (slightly oversized)
    er = int(r * 1.25)
    draw.ellipse([cx - er, cy - er, cx + er, cy + er], fill=(255, 255, 255, 255))

    # Draw X — arm length matches original circle radius
    arm = int(r * 0.88)
    draw.line([(cx - arm, cy - arm), (cx + arm, cy + arm)],
              fill=(0, 0, 0, 255), width=X_WIDTH)
    draw.line([(cx + arm, cy - arm), (cx - arm, cy + arm)],
              fill=(0, 0, 0, 255), width=X_WIDTH)

# ── Rounded corners ───────────────────────────────────────────────────────────
corner_mask = Image.new('L', (SIZE, SIZE), 0)
ImageDraw.Draw(corner_mask).rounded_rectangle(
    [0, 0, SIZE - 1, SIZE - 1], radius=CORNER_R, fill=255
)
result.putalpha(corner_mask)

from make_mh_badge import add_mh_badge
result = add_mh_badge(result)

result.save(OUT)
print('Eyes at: {}'.format([(round(cx), round(cy)) for cx, cy, *_ in eyes]))
print('Saved: {}'.format(OUT))
