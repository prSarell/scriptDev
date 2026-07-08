"""
make_icon_metahuman_badge.py — stamps the MetaHuman badge onto iconMetahuman.png.

iconMetahuman.png has a black background, so it needs the inverted
white-dot / black-"m" badge variant per the studio icon standard.
There's no source art to regenerate the icon from scratch, so this
script badges the existing 256x256 PNG in place.

Run with: mayapy make_icon_metahuman_badge.py  (requires Pillow)
"""
import os
import sys
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'mpRig'))
from make_mh_badge import add_mh_badge

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icons', 'iconMetahuman.png')

img = Image.open(OUT)
badged = add_mh_badge(img, invert=True)
badged.save(OUT)
print('Badged:', OUT)
