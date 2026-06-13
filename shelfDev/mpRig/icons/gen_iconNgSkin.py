"""Run once inside Maya to generate iconNgSkin.png."""
import os
from PySide6 import QtGui, QtCore

def gen():
    size = 64
    px   = QtGui.QPixmap(size, size)
    px.fill(QtCore.Qt.GlobalColor.transparent)
    p = QtGui.QPainter(px)
    p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

    # ── dark rounded background ───────────────────────────────────────────────
    p.setBrush(QtGui.QColor(45, 45, 55))
    p.setPen(QtCore.Qt.PenStyle.NoPen)
    p.drawRoundedRect(0, 0, size, size, 10, 10)

    # ── diamond mesh (vertices + edges) ──────────────────────────────────────
    cx, cy = 32, 30
    top   = QtCore.QPointF(cx,      cy - 18)
    right = QtCore.QPointF(cx + 18, cy)
    btm   = QtCore.QPointF(cx,      cy + 18)
    left  = QtCore.QPointF(cx - 18, cy)

    edge_pen = QtGui.QPen(QtGui.QColor(170, 170, 185), 1.5)
    p.setPen(edge_pen)
    for a, b in [(top, right), (right, btm), (btm, left), (left, top),
                 (top, btm), (left, right)]:
        p.drawLine(a, b)

    # ── weight-coloured vertex dots ───────────────────────────────────────────
    p.setPen(QtCore.Qt.PenStyle.NoPen)
    for pt, col in [
        (top,   QtGui.QColor(220,  55,  55)),   # red   (full influence)
        (right, QtGui.QColor(220, 155,  40)),   # orange
        (btm,   QtGui.QColor( 55, 155, 220)),   # blue  (low influence)
        (left,  QtGui.QColor( 70, 200, 175)),   # teal
    ]:
        p.setBrush(col)
        p.drawEllipse(pt, 5.5, 5.5)

    p.end()
    out = os.path.join(os.path.dirname(__file__), 'iconNgSkin.png')
    px.save(out, 'PNG')
    print('Saved:', out)

gen()
