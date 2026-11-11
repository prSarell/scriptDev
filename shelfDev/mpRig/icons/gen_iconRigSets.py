"""Run once in mayapy (or Maya) to generate iconRigSets.png: three
overlapping set rings (cache, controls, face) with a tick badge, for the
Rig Sets tool (rigDev/rigSets.py). 256x256, rounded corners."""
import os
from PySide6 import QtGui, QtCore


def gen():
    scale = 4  # 64px design scaled up to the standard 256x256 shelf icon size
    size = 64 * scale
    img = QtGui.QImage(size, size, QtGui.QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(QtCore.Qt.GlobalColor.transparent)
    p = QtGui.QPainter(img)
    p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

    # ── dark rounded background (matches the other mpRig icons) ──────────────
    p.setBrush(QtGui.QColor(45, 45, 55))
    p.setPen(QtCore.Qt.PenStyle.NoPen)
    p.drawRoundedRect(0, 0, size, size, 10 * scale, 10 * scale)

    # ── three set rings: cache (blue), controls (orange), face (green) ───────
    rings = [((24, 24), QtGui.QColor(120, 200, 255)),
             ((40, 24), QtGui.QColor(255, 160, 50)),
             ((32, 38), QtGui.QColor(140, 220, 120))]
    r = 13 * scale
    for (x, y), colour in rings:
        fill = QtGui.QColor(colour)
        fill.setAlpha(70)
        p.setBrush(fill)
        p.setPen(QtGui.QPen(colour, 2.4 * scale))
        p.drawEllipse(QtCore.QPointF(x * scale, y * scale), r, r)

    # ── tick badge, bottom right ─────────────────────────────────────────────
    centre = QtCore.QPointF(50 * scale, 50 * scale)
    p.setPen(QtGui.QPen(QtGui.QColor(45, 45, 55), 2.0 * scale))
    p.setBrush(QtGui.QColor(60, 190, 110))
    p.drawEllipse(centre, 10 * scale, 10 * scale)
    tick = QtGui.QPen(QtGui.QColor(255, 255, 255), 3.0 * scale)
    tick.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
    tick.setJoinStyle(QtCore.Qt.PenJoinStyle.RoundJoin)
    p.setPen(tick)
    p.setBrush(QtCore.Qt.BrushStyle.NoBrush)
    path = QtGui.QPainterPath(QtCore.QPointF(45 * scale, 50.5 * scale))
    path.lineTo(QtCore.QPointF(48.5 * scale, 54 * scale))
    path.lineTo(QtCore.QPointF(55.5 * scale, 46 * scale))
    p.drawPath(path)

    p.end()
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'iconRigSets.png')
    img.save(out, 'PNG')
    print('Saved', out)


if __name__ == '__main__':
    gen()
