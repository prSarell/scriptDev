"""
make_icon_convert.py: generates icons/iconModelConvert.png (256x256,
rounded corners), in the style of the mpPipe / mpLayout icons: a flat colour,
a white cube with a turn-back arrow (publish -> plain model), and a label.
Run with: mayapy make_icon_convert.py
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6 import QtCore, QtGui, QtWidgets

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

SIZE = 256
COLOUR = QtGui.QColor("#d9822b")
WHITE = QtGui.QColor("white")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons", "iconModelConvert.png")

image = QtGui.QImage(SIZE, SIZE, QtGui.QImage.Format_ARGB32)
image.fill(QtCore.Qt.transparent)
p = QtGui.QPainter(image)
p.setRenderHint(QtGui.QPainter.Antialiasing)
p.setPen(QtCore.Qt.NoPen)
p.setBrush(COLOUR)
p.drawRoundedRect(0, 0, SIZE, SIZE, 30, 30)

# An isometric cube, outlined.
pen = QtGui.QPen(WHITE, 9, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin)
p.setPen(pen)
p.setBrush(QtCore.Qt.NoBrush)
cx, top, w, h = 96, 34, 58, 34
P = QtCore.QPointF
front = [P(cx, top + 2 * h), P(cx - w, top + h), P(cx - w, top + h + 74),
         P(cx, top + 2 * h + 74), P(cx + w, top + h + 74), P(cx + w, top + h)]
p.drawPolygon(QtGui.QPolygonF([P(cx, top), P(cx + w, top + h), P(cx, top + 2 * h),
                               P(cx - w, top + h)]))
p.drawPolyline(QtGui.QPolygonF(front))
p.drawLine(P(cx, top + 2 * h), P(cx, top + 2 * h + 74))

# A turn-back arrow beside it.
arc = QtCore.QRectF(170, 70, 64, 64)
p.drawArc(arc, 210 * 16, 260 * 16)
p.setPen(QtCore.Qt.NoPen)
p.setBrush(WHITE)
tip = QtGui.QPolygonF([P(160, 122), P(186, 112), P(180, 140)])
p.drawPolygon(tip)

# Offscreen Qt has no system fonts: load Arial Bold from Windows.
family = QtGui.QFontDatabase.applicationFontFamilies(QtGui.QFontDatabase.addApplicationFont(
    os.path.join(os.environ.get("WINDIR", "C:/Windows"), "Fonts", "arialbd.ttf")))
font = QtGui.QFont(family[0] if family else "Arial", 1, QtGui.QFont.Bold)
font.setPixelSize(40)
p.setFont(font)
p.setPen(WHITE)
p.drawText(QtCore.QRectF(0, 190, SIZE, 52), QtCore.Qt.AlignCenter, "CONVERT")
p.end()

os.makedirs(os.path.dirname(OUT), exist_ok=True)
image.save(OUT)
print("Saved: %s" % OUT)
