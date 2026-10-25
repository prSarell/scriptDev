"""Run once inside Maya (or mayapy) to generate iconFreezeOcean.png."""
import math
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

    # ── dark rounded background ───────────────────────────────────────────────
    p.setBrush(QtGui.QColor(28, 40, 58))
    p.setPen(QtCore.Qt.PenStyle.NoPen)
    p.drawRoundedRect(0, 0, size, size, 10 * scale, 10 * scale)

    def wave_band(base_y, amp, wavelength, colour, x0, x1):
        path = QtGui.QPainterPath()
        path.moveTo(x0 * scale, 64 * scale)
        for i in range(x0, x1 + 1):
            y = base_y + amp * math.sin(i / wavelength * 2 * math.pi)
            path.lineTo(i * scale, y * scale)
        path.lineTo(x1 * scale, 64 * scale)
        path.closeSubpath()
        p.setBrush(colour)
        p.drawPath(path)

    # ── left half: live ocean (blue) ──────────────────────────────────────────
    wave_band(34, 5, 14, QtGui.QColor(40, 140, 210), 0, 32)
    # ── right half: same shape frozen into red terrain ────────────────────────
    wave_band(34, 5, 14, QtGui.QColor(170, 70, 35), 32, 64)

    # ── camera-frame brackets: "grab this frame" ──────────────────────────────
    pen = QtGui.QPen(QtGui.QColor(240, 240, 245), 2.5 * scale)
    pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.setBrush(QtCore.Qt.BrushStyle.NoBrush)
    for x, y, dx, dy in ((10, 10, 1, 1), (54, 10, -1, 1), (10, 54, 1, -1), (54, 54, -1, -1)):
        p.drawLine(QtCore.QPointF(x * scale, y * scale), QtCore.QPointF((x + 8 * dx) * scale, y * scale))
        p.drawLine(QtCore.QPointF(x * scale, y * scale), QtCore.QPointF(x * scale, (y + 8 * dy) * scale))

    p.end()
    out = os.path.join(os.path.dirname(__file__), 'iconFreezeOcean.png')
    img.save(out, 'PNG')
    print('Saved:', out)

gen()
