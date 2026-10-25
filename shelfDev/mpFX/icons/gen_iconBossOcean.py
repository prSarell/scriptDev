"""Run once inside Maya (or mayapy) to generate iconBossOcean.png."""
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

    # ── sky-to-deep-water rounded background ──────────────────────────────────
    grad = QtGui.QLinearGradient(0, 0, 0, size)
    grad.setColorAt(0.0, QtGui.QColor(28, 52, 82))
    grad.setColorAt(1.0, QtGui.QColor(8, 22, 40))
    p.setBrush(grad)
    p.setPen(QtCore.Qt.PenStyle.NoPen)
    p.drawRoundedRect(0, 0, size, size, 10 * scale, 10 * scale)

    # ── three wave bands, back to front ───────────────────────────────────────
    bands = (
        (24, 3.0, 9.0, 0.0, QtGui.QColor(40, 110, 170)),
        (34, 4.0, 11.0, 1.3, QtGui.QColor(30, 140, 200)),
        (45, 5.0, 14.0, 2.4, QtGui.QColor(70, 190, 230)),
    )
    for base_y, amp, wavelength, phase, colour in bands:
        path = QtGui.QPainterPath()
        path.moveTo(0, size)
        for i in range(0, 65):
            y = base_y + amp * math.sin(i / wavelength * 2 * math.pi + phase)
            path.lineTo(i * scale, y * scale)
        path.lineTo(size, size)
        path.closeSubpath()
        p.setBrush(colour)
        p.drawPath(path)

    # ── white crest line on the front wave ────────────────────────────────────
    base_y, amp, wavelength, phase, _ = bands[-1]
    crest = QtGui.QPainterPath()
    crest.moveTo(0, (base_y + amp * math.sin(phase)) * scale)
    for i in range(1, 65):
        y = base_y + amp * math.sin(i / wavelength * 2 * math.pi + phase)
        crest.lineTo(i * scale, y * scale)
    pen = QtGui.QPen(QtGui.QColor(235, 248, 255), 1.6 * scale)
    pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.setBrush(QtCore.Qt.BrushStyle.NoBrush)
    p.drawPath(crest)

    # clip everything to the rounded corners
    p.setCompositionMode(QtGui.QPainter.CompositionMode.CompositionMode_DestinationIn)
    p.setPen(QtCore.Qt.PenStyle.NoPen)
    p.setBrush(QtGui.QColor(0, 0, 0, 255))
    mask = QtGui.QPainterPath()
    mask.addRoundedRect(0, 0, size, size, 10 * scale, 10 * scale)
    p.drawPath(mask)

    p.end()
    out = os.path.join(os.path.dirname(__file__), 'iconBossOcean.png')
    img.save(out, 'PNG')
    print('Saved:', out)

gen()
