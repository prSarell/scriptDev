"""
make_mh_badge.py — stamps a small black disc with white 'm' onto all
Metahuman-related shelf icons.

Run with: mayapy make_mh_badge.py  (requires Pillow)

Also imported as a helper by individual icon generators so the badge
is applied whenever an icon is regenerated.
"""
import os
from PIL import Image, ImageDraw, ImageFont

_ICONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icons')

MH_ICONS = [
    'iconMhBsBake.png',
    'iconMhRecycle.png',
    'iconMhDnaRepair.png',
    'iconVpShader.png',
    'iconMhBodyClean.png',
]

# Badge geometry — centred at (463, 463) inside the 60px rounded corner
_BX, _BY, _BR = 463, 463, 36


def _get_font(size=44):
    for path in (
        'C:/Windows/Fonts/arialbd.ttf',
        'C:/Windows/Fonts/arial.ttf',
        '/Library/Fonts/Arial Bold.ttf',
    ):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def add_mh_badge(img):
    """Return a copy of img with the 'm' badge stamped in the bottom-right."""
    out = img.convert('RGBA')
    draw = ImageDraw.Draw(out)
    draw.ellipse(
        [_BX - _BR, _BY - _BR, _BX + _BR, _BY + _BR],
        fill=(0, 0, 0, 255),
    )
    draw.text((_BX, _BY), 'm', font=_get_font(44),
              fill=(255, 255, 255, 255), anchor='mm')
    return out


if __name__ == '__main__':
    for name in MH_ICONS:
        path = os.path.join(_ICONS_DIR, name)
        if not os.path.exists(path):
            print('SKIP (not found): {}'.format(name))
            continue
        img = Image.open(path)
        badged = add_mh_badge(img)
        badged.save(path)
        print('Badged: {}'.format(name))
