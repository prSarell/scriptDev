"""Run once inside Maya to generate iconNsStrip.png."""
import os
from PySide6 import QtGui, QtCore

def gen():
    size = 64
    px   = QtGui.QPixmap(size, size)
    px.fill(QtCore.Qt.GlobalColor.transparent)
    p = QtGui.QPainter(px)
    p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

    # Background
    p.setBrush(QtGui.QColor(45, 45, 55))
    p.setPen(QtCore.Qt.PenStyle.NoPen)
    p.drawRoundedRect(0, 0, size, size, 8, 8)

    font = QtGui.QFont('Courier New', 9, QtGui.QFont.Weight.Bold)
    p.setFont(font)

    # Dimmed "ns:" prefix
    p.setPen(QtGui.QColor(120, 80, 80))
    p.drawText(QtCore.QRect(5, 10, 30, 18), QtCore.Qt.AlignmentFlag.AlignLeft, 'ns:')

    # Strikethrough line over "ns:"
    pen = QtGui.QPen(QtGui.QColor(200, 80, 80), 1.5)
    p.setPen(pen)
    p.drawLine(4, 19, 32, 19)

    # Arrow
    arrow_pen = QtGui.QPen(QtGui.QColor(160, 160, 160), 1.5)
    arrow_pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
    p.setPen(arrow_pen)
    p.drawLine(8, 34, 56, 34)
    p.drawLine(48, 28, 56, 34)
    p.drawLine(48, 40, 56, 34)

    # Clean name below
    p.setPen(QtGui.QColor(140, 210, 140))
    font2 = QtGui.QFont('Courier New', 9, QtGui.QFont.Weight.Bold)
    p.setFont(font2)
    p.drawText(QtCore.QRect(5, 44, 54, 16), QtCore.Qt.AlignmentFlag.AlignLeft, 'name')

    p.end()
    out = os.path.join(os.path.dirname(__file__), 'iconNsStrip.png')
    px.save(out, 'PNG')
    print('Saved:', out)

gen()
