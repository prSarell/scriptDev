"""Run once inside Maya to generate iconMhBodyClean.png."""
import os
from PySide6 import QtGui, QtCore

def gen():
    size = 64
    px   = QtGui.QPixmap(size, size)
    px.fill(QtCore.Qt.GlobalColor.transparent)
    p = QtGui.QPainter(px)
    p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

    # Dark background
    p.setBrush(QtGui.QColor(45, 45, 55))
    p.setPen(QtCore.Qt.PenStyle.NoPen)
    p.drawRoundedRect(0, 0, size, size, 10, 10)

    # Body silhouette (simple torso shape)
    body_color = QtGui.QColor(160, 170, 190)
    p.setBrush(body_color)
    p.setPen(QtCore.Qt.PenStyle.NoPen)
    # Head
    p.drawEllipse(QtCore.QPointF(24, 13), 7, 7)
    # Torso
    torso = QtGui.QPainterPath()
    torso.moveTo(14, 24)
    torso.cubicTo(12, 28, 12, 36, 14, 42)
    torso.lineTo(34, 42)
    torso.cubicTo(36, 36, 36, 28, 34, 24)
    torso.closeSubpath()
    p.drawPath(torso)

    # LOD stack — three stacked rectangles on the right, two dimmed (deleted)
    rects = [(38, 10, 20, 7), (38, 20, 20, 7), (38, 30, 20, 7)]
    colors = [QtGui.QColor(80, 80, 90), QtGui.QColor(80, 80, 90),
              QtGui.QColor(100, 180, 120)]  # bottom one = kept (green)
    for (rx, ry, rw, rh), col in zip(rects, colors):
        p.setBrush(col)
        p.setPen(QtCore.Qt.PenStyle.NoPen)
        p.drawRoundedRect(rx, ry, rw, rh, 2, 2)

    # Strike through the top two (deleted LODs)
    strike_pen = QtGui.QPen(QtGui.QColor(200, 80, 80), 1.5)
    strike_pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
    p.setPen(strike_pen)
    for (rx, ry, rw, rh) in rects[:2]:
        cy = ry + rh / 2
        p.drawLine(QtCore.QPointF(rx + 1, cy), QtCore.QPointF(rx + rw - 1, cy))

    # Small broom/sweep icon at bottom — cleanup hint
    sweep_pen = QtGui.QPen(QtGui.QColor(200, 180, 100), 1.8)
    sweep_pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
    p.setPen(sweep_pen)
    p.drawLine(QtCore.QPointF(10, 52), QtCore.QPointF(54, 52))
    p.drawLine(QtCore.QPointF(18, 48), QtCore.QPointF(10, 56))
    p.drawLine(QtCore.QPointF(26, 48), QtCore.QPointF(18, 56))
    p.drawLine(QtCore.QPointF(34, 48), QtCore.QPointF(26, 56))
    p.drawLine(QtCore.QPointF(42, 48), QtCore.QPointF(34, 56))
    p.drawLine(QtCore.QPointF(50, 48), QtCore.QPointF(42, 56))

    p.end()
    out = os.path.join(os.path.dirname(__file__), 'iconMhBodyClean.png')
    px.save(out, 'PNG')
    print('Saved:', out)

gen()
