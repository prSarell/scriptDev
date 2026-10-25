"""Run once inside Maya (or mayapy) to generate iconSnowLand.png."""
import os
from PySide6 import QtGui, QtCore

def gen():
    scale = 4  # 64px design scaled up to the standard 256x256 shelf icon size
    size = 64 * scale
    # QImage rather than QPixmap so this also runs headless in mayapy
    img = QtGui.QImage(size, size, QtGui.QImage.Format.Format_ARGB32)
    img.fill(QtCore.Qt.GlobalColor.transparent)
    p = QtGui.QPainter(img)
    p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

    # ── sky rounded background ────────────────────────────────────────────────
    grad = QtGui.QLinearGradient(0, 0, 0, size)
    grad.setColorAt(0.0, QtGui.QColor(70, 120, 180))
    grad.setColorAt(1.0, QtGui.QColor(170, 200, 230))
    p.setBrush(grad)
    p.setPen(QtCore.Qt.PenStyle.NoPen)
    p.drawRoundedRect(0, 0, size, size, 10 * scale, 10 * scale)

    def poly(points, colour):
        p.setBrush(colour)
        p.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(x * scale, y * scale) for x, y in points]))

    # ── red rock mountains (steep slopes) ─────────────────────────────────────
    poly(((0, 64), (0, 44), (14, 30), (24, 40), (38, 18), (52, 34), (64, 26), (64, 64)),
         QtGui.QColor(150, 40, 25))
    # shaded right faces
    poly(((38, 18), (52, 34), (46, 64), (40, 64)), QtGui.QColor(110, 28, 18))
    poly(((14, 30), (24, 40), (18, 64), (14, 64)), QtGui.QColor(110, 28, 18))

    # ── snow on the flat-ish tops ─────────────────────────────────────────────
    snow = QtGui.QColor(245, 248, 252)
    poly(((32, 25), (38, 18), (44, 25), (41, 27), (38, 24), (35, 27)), snow)
    poly(((10, 34), (14, 30), (18, 34), (16, 35), (14, 33), (12, 35)), snow)
    poly(((59, 29), (64, 26), (64, 31), (61, 30)), snow)

    # ── flat valley floor catches snow ────────────────────────────────────────
    poly(((0, 64), (0, 54), (20, 50), (40, 53), (64, 49), (64, 64)), snow)

    p.end()
    out = os.path.join(os.path.dirname(__file__), 'iconSnowLand.png')
    img.save(out, 'PNG')
    print('Saved:', out)

gen()
