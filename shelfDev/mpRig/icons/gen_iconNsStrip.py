"""Run once inside Maya to generate iconNsStrip.png."""
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

    # ── ID card (landscape, centered) ────────────────────────────────────────
    card_x, card_y, card_w, card_h = 5, 14, 54, 36
    p.setBrush(QtGui.QColor(62, 62, 75))
    p.setPen(QtGui.QPen(QtGui.QColor(190, 190, 200), 2.0))
    p.drawRoundedRect(card_x, card_y, card_w, card_h, 6, 6)

    silhouette = QtGui.QColor(210, 210, 220)

    # ── person silhouette (left portion of card) ──────────────────────────────
    # head
    p.setBrush(silhouette)
    p.setPen(QtCore.Qt.PenStyle.NoPen)
    head_cx, head_cy, head_r = 18.5, 25.0, 5.0
    p.drawEllipse(QtCore.QPointF(head_cx, head_cy), head_r, head_r)

    # shoulders — ellipse clipped to card bottom edge
    p.save()
    clip = QtGui.QPainterPath()
    clip.addRoundedRect(card_x, card_y, card_w, card_h, 6, 6)
    p.setClipPath(clip)
    p.drawEllipse(QtCore.QPointF(head_cx, 41.0), 8.5, 6.5)
    p.restore()

    # ── name lines (right portion of card) ───────────────────────────────────
    line_pen = QtGui.QPen(QtGui.QColor(190, 190, 200), 3.5)
    line_pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
    p.setPen(line_pen)
    lx = 30
    for y, x_end in ((24, 55), (31, 55), (38, 47)):
        p.drawLine(QtCore.QPointF(lx, y), QtCore.QPointF(x_end, y))

    p.end()
    out = os.path.join(os.path.dirname(__file__), 'iconNsStrip.png')
    px.save(out, 'PNG')
    print('Saved:', out)

gen()
