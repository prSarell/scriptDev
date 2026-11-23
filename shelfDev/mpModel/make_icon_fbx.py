"""
make_icon_fbx.py: generates icons/iconModelFbxExport.png (256x256, rounded
corners), in the style of the other mpModel icons: the shelf's orange, a
white cube with an arrow out to the right (export), and the label FBX.
Run with: mayapy make_icon_fbx.py
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6 import QtCore, QtGui, QtWidgets

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

SIZE = 256
COLOUR = QtGui.QColor("#d9822b")
WHITE = QtGui.QColor("white")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons", "iconModelFbxExport.png")

image = QtGui.QImage(SIZE, SIZE, QtGui.QImage.Format_ARGB32)
image.fill(QtCore.Qt.transparent)
p = QtGui.QPainter(image)
p.setRenderHint(QtGui.QPainter.Antialiasing)
p.setPen(QtCore.Qt.NoPen)
p.setBrush(COLOUR)
p.drawRoundedRect(0, 0, SIZE, SIZE, 30, 30)

# An isometric cube, outlined (as in iconModelConvert).
pen = QtGui.QPen(WHITE, 9, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin)
p.setPen(pen)
p.setBrush(QtCore.Qt.NoBrush)
cx, top, w, h = 90, 34, 58, 34
P = QtCore.QPointF
front = [P(cx, top + 2 * h), P(cx - w, top + h), P(cx - w, top + h + 74),
         P(cx, top + 2 * h + 74), P(cx + w, top + h + 74), P(cx + w, top + h)]
p.drawPolygon(QtGui.QPolygonF([P(cx, top), P(cx + w, top + h), P(cx, top + 2 * h),
                               P(cx - w, top + h)]))
p.drawPolyline(QtGui.QPolygonF(front))
p.drawLine(P(cx, top + 2 * h), P(cx, top + 2 * h + 74))

# An arrow out to the right.
p.drawLine(P(166, 106), P(218, 106))
p.setPen(QtCore.Qt.NoPen)
p.setBrush(WHITE)
p.drawPolygon(QtGui.QPolygonF([P(236, 106), P(208, 88), P(208, 124)]))

# Offscreen Qt has no system fonts: load Arial Bold from Windows.
family = QtGui.QFontDatabase.applicationFontFamilies(QtGui.QFontDatabase.addApplicationFont(
    os.path.join(os.environ.get("WINDIR", "C:/Windows"), "Fonts", "arialbd.ttf")))
font = QtGui.QFont(family[0] if family else "Arial", 1, QtGui.QFont.Bold)
font.setPixelSize(44)
p.setFont(font)
p.setPen(WHITE)
p.drawText(QtCore.QRectF(0, 190, SIZE, 52), QtCore.Qt.AlignCenter, "FBX")
p.end()

os.makedirs(os.path.dirname(OUT), exist_ok=True)
image.save(OUT)
print("Saved: %s" % OUT)
