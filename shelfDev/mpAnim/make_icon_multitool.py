"""Run once inside Maya to generate iconMultiTool.png — a flat wrench
silhouette representing the multiTool animation-utilities menu.
Run with: mayapy make_icon_multitool.py  (requires PySide6)
"""
import os
from PySide6 import QtGui, QtCore

SIZE = 256
CORNER_R = 34


def _wrench_path():
    """Wrench silhouette built horizontally, centred on (0, 0)."""
    path = QtGui.QPainterPath()

    # handle
    handle = QtGui.QPainterPath()
    handle.addRoundedRect(QtCore.QRectF(-72, -14, 144, 28), 14, 14)
    path = path.united(handle)

    # closed (box) end — left
    ring_l = QtGui.QPainterPath()
    ring_l.addEllipse(QtCore.QPointF(-78, 0), 34, 34)
    hole_l = QtGui.QPainterPath()
    hole_l.addEllipse(QtCore.QPointF(-78, 0), 19, 19)
    path = path.united(ring_l.subtracted(hole_l))

    # open (spanner) end — right, with a wedge cut facing outward
    ring_r = QtGui.QPainterPath()
    ring_r.addEllipse(QtCore.QPointF(78, 0), 34, 34)
    hole_r = QtGui.QPainterPath()
    hole_r.addEllipse(QtCore.QPointF(78, 0), 19, 19)
    annulus_r = ring_r.subtracted(hole_r)
    wedge = QtGui.QPainterPath()
    wedge.addRect(QtCore.QRectF(78 + 14, -9, 40, 18))
    path = path.united(annulus_r.subtracted(wedge))

    return path


def gen():
    px = QtGui.QPixmap(SIZE, SIZE)
    px.fill(QtCore.Qt.GlobalColor.transparent)
    p = QtGui.QPainter(px)
    p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

    # white rounded background
    p.setBrush(QtGui.QColor(255, 255, 255, 255))
    p.setPen(QtCore.Qt.PenStyle.NoPen)
    p.drawRoundedRect(0, 0, SIZE, SIZE, CORNER_R, CORNER_R)

    # wrench, rotated 45 degrees, centred
    p.save()
    p.translate(SIZE / 2, SIZE / 2)
    p.rotate(-45)
    p.setBrush(QtGui.QColor(25, 25, 30, 255))
    p.setPen(QtCore.Qt.PenStyle.NoPen)
    p.drawPath(_wrench_path())
    p.restore()

    p.end()
    out = os.path.join(os.path.dirname(__file__), 'icons', 'iconMultiTool.png')
    px.save(out, 'PNG')
    print('Saved:', out)


gen()
