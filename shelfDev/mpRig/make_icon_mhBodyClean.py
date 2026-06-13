"""
make_icon_mhBodyClean.py — generates iconMhBodyClean.png
White background, black hand-with-soap-foam line art, rounded corners, MH badge.
Run with: mayapy make_icon_mhBodyClean.py  (requires Pillow)
"""
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw
from make_mh_badge import add_mh_badge

SIZE     = 512
CORNER_R = 60
LW       = 10
LW_THIN  = 8
LC       = (0, 0, 0, 255)
OUT      = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        'icons', 'iconMhBodyClean.png')

img  = Image.new('RGBA', (SIZE, SIZE), (255, 255, 255, 255))
draw = ImageDraw.Draw(img)


def qbez_pts(p0, pc, p1, n=40):
    pts = []
    for i in range(n + 1):
        t = i / n
        pts.append((
            (1-t)**2*p0[0] + 2*(1-t)*t*pc[0] + t**2*p1[0],
            (1-t)**2*p0[1] + 2*(1-t)*t*pc[1] + t**2*p1[1],
        ))
    return pts


def dline(p0, p1, w=LW):
    draw.line([p0, p1], fill=LC, width=w)


def dbez(p0, pc, p1, w=LW, n=40):
    pts = qbez_pts(p0, pc, p1, n)
    for i in range(len(pts) - 1):
        draw.line([(round(pts[i][0]),   round(pts[i][1])),
                   (round(pts[i+1][0]), round(pts[i+1][1]))], fill=LC, width=w)


def dcircle(cx, cy, r, w=LW):
    draw.arc([round(cx-r), round(cy-r), round(cx+r), round(cy+r)],
             0, 360, fill=LC, width=w)


# ── Floating bubbles ──────────────────────────────────────────────────────────
dcircle(104,  88, 28, LW_THIN)
dcircle(400,  72, 24, LW_THIN)
dcircle( 64, 168, 20,       7)

# ── Foam cluster ──────────────────────────────────────────────────────────────
for cx, cy, r in [
    (224, 264, 60),
    (296, 240, 56),
    (176, 208, 44),
    (336, 208, 44),
    (256, 176, 48),
    (208, 152, 36),
    (304, 152, 36),
]:
    dcircle(cx, cy, r, LW)

# ── Hand ──────────────────────────────────────────────────────────────────────

# Wrist left side
dline((48, 480), (64, 416))

# Thumb
dbez((64, 416), (32, 376), (72, 344))    # left side
dbez((72, 344), (96, 320), (136, 344))   # tip
dline((136, 344), (160, 384))            # right side

# Web between thumb and index
dbez((160, 384), (224, 352), (272, 352))

# Index finger
dline((272, 352), (288, 304))
dbez((288, 304), (304, 272), (336, 288))
dline((336, 288), (336, 344))

# Valley between index and middle
dline((336, 344), (352, 376))

# Middle finger (longest)
dline((352, 376), (368, 320))
dbez((368, 320), (384, 280), (416, 304))
dline((416, 304), (416, 368))

# Valley between middle and ring
dline((416, 368), (424, 400))

# Ring finger
dline((424, 400), (432, 352))
dbez((432, 352), (448, 320), (464, 352))
dline((464, 352), (448, 408))

# Valley between ring and pinky
dline((448, 408), (448, 432))

# Pinky (shortest)
dline((448, 432), (456, 400))
dbez((456, 400), (472, 376), (464, 408))
dline((464, 408), (448, 448))

# Right palm edge
dbez((448, 448), (432, 480), (384, 496))

# Palm bottom arc (closes to wrist)
dbez((384, 496), (224, 508), (48, 480))

# ── Rounded corners ───────────────────────────────────────────────────────────
mask = Image.new('L', (SIZE, SIZE), 0)
ImageDraw.Draw(mask).rounded_rectangle([0, 0, SIZE-1, SIZE-1], radius=CORNER_R, fill=255)
img.putalpha(mask)

# ── MH badge ─────────────────────────────────────────────────────────────────
img = add_mh_badge(img)

img.save(OUT)
print('Saved:', OUT)
