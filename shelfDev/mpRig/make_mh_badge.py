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

# Badge geometry as fractions of canvas size — originally tuned as
# (463, 463, 36) on a 512px canvas; expressed as ratios so the badge
# scales correctly on any icon size (e.g. the 256px mpAnim icons).
_BX_R, _BY_R, _BR_R = 463 / 512, 463 / 512, 36 / 512
_FONT_R = 44 / 512


def _get_font(size):
    for path in (
        'C:/Windows/Fonts/arialbd.ttf',
        'C:/Windows/Fonts/arial.ttf',
        '/Library/Fonts/Arial Bold.ttf',
    ):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def add_mh_badge(img, invert=False):
    """Return a copy of img with the 'm' badge stamped in the bottom-right.

    invert=True gives a white dot / black "m" — use this on icons with a
    black background, per the studio icon standard.
    """
    out = img.convert('RGBA')
    size = out.width
    bx, by, br = _BX_R * size, _BY_R * size, _BR_R * size
    dot_color = (255, 255, 255, 255) if invert else (0, 0, 0, 255)
    text_color = (0, 0, 0, 255) if invert else (255, 255, 255, 255)

    draw = ImageDraw.Draw(out)
    draw.ellipse([bx - br, by - br, bx + br, by + br], fill=dot_color)
    draw.text((bx, by), 'm', font=_get_font(round(_FONT_R * size)),
              fill=text_color, anchor='mm')
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
