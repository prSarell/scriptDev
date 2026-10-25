"""Run once inside Maya (or mayapy) to generate iconCloudVolume.png."""
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

    # ── sunset sky rounded background ─────────────────────────────────────────
    grad = QtGui.QLinearGradient(0, 0, 0, size)
    grad.setColorAt(0.0, QtGui.QColor(40, 70, 120))
    grad.setColorAt(0.65, QtGui.QColor(200, 120, 90))
    grad.setColorAt(1.0, QtGui.QColor(240, 170, 100))
    p.setBrush(grad)
    p.setPen(QtCore.Qt.PenStyle.NoPen)
    p.drawRoundedRect(0, 0, size, size, 10 * scale, 10 * scale)

    # ── cloud: overlapping puffs, soft shadow then lit body ───────────────────
    puffs = ((20, 38, 11), (32, 30, 14), (45, 36, 11), (27, 41, 9), (40, 42, 9))
    cloud = QtGui.QPainterPath()
    cloud.setFillRule(QtCore.Qt.FillRule.WindingFill)  # merge overlapping puffs
    for cx, cy, r in puffs:
        cloud.addEllipse(QtCore.QPointF(cx * scale, cy * scale), r * scale, r * scale)
    cloud = cloud.simplified()

    p.setBrush(QtGui.QColor(120, 110, 140, 150))
    p.drawPath(cloud.translated(0, 3 * scale))

    body = QtGui.QLinearGradient(0, 16 * scale, 0, 51 * scale)
    body.setColorAt(0.0, QtGui.QColor(255, 255, 255))
    body.setColorAt(1.0, QtGui.QColor(225, 215, 230))
    p.setBrush(body)
    p.drawPath(cloud)

    p.end()
    out = os.path.join(os.path.dirname(__file__), 'iconCloudVolume.png')
    img.save(out, 'PNG')
    print('Saved:', out)

gen()
