"""Run once inside Maya to generate iconHairBuilder.png."""
import os
from PySide6 import QtGui, QtCore

def gen():
    size = 64
    px   = QtGui.QPixmap(size, size)
    px.fill(QtCore.Qt.GlobalColor.transparent)
    p = QtGui.QPainter(px)
    p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

    bg = QtGui.QColor(45, 45, 55)
    p.setBrush(bg)
    p.setPen(QtCore.Qt.PenStyle.NoPen)
    p.drawRoundedRect(0, 0, size, size, 8, 8)

    # Three curved hair strands
    strand_colors = [QtGui.QColor(220, 180, 100),
                     QtGui.QColor(200, 155, 70),
                     QtGui.QColor(240, 200, 130)]
    offsets = [-10, 0, 10]
    pen = QtGui.QPen()
    pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)

    for col, ox in zip(strand_colors, offsets):
        pen.setColor(col)
        pen.setWidthF(3.0)
        p.setPen(pen)
        path = QtGui.QPainterPath()
        cx = size / 2 + ox
        path.moveTo(cx, 8)
        path.cubicTo(cx + 12, 20, cx - 12, 36, cx, 56)
        p.drawPath(path)

    # Small circle at root (follicle pin)
    p.setBrush(QtGui.QColor(100, 200, 180))
    p.setPen(QtCore.Qt.PenStyle.NoPen)
    p.drawEllipse(QtCore.QPointF(size / 2, 8), 4, 4)

    p.end()
    out = os.path.join(os.path.dirname(__file__), 'iconHairBuilder.png')
    px.save(out, 'PNG')
    print('Saved:', out)

gen()
