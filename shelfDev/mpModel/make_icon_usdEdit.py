"""
make_icon_usdEdit.py: generates icons/iconModelUsdEdit.png (256x256, rounded
corners), in the style of the other mpModel USD icons: the shelf's orange,
three stacked layers (shot over asset over publish) with a move arrow on
the top one, and the label USD EDIT.
Run with: mayapy make_icon_usdEdit.py
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6 import QtCore, QtGui, QtWidgets

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

SIZE = 256
COLOUR = QtGui.QColor("#d9822b")
WHITE = QtGui.QColor("white")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons", "iconModelUsdEdit.png")
P = QtCore.QPointF

image = QtGui.QImage(SIZE, SIZE, QtGui.QImage.Format_ARGB32)
image.fill(QtCore.Qt.transparent)
p = QtGui.QPainter(image)
p.setRenderHint(QtGui.QPainter.Antialiasing)
p.setPen(QtCore.Qt.NoPen)
p.setBrush(COLOUR)
p.drawRoundedRect(0, 0, SIZE, SIZE, 30, 30)


def layer(cx, cy, filled):
    """A flat diamond: one USD layer seen from above."""
    shape = QtGui.QPolygonF([P(cx, cy - 26), P(cx + 62, cy), P(cx, cy + 26), P(cx - 62, cy)])
    p.setPen(QtGui.QPen(WHITE, 8, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
    p.setBrush(WHITE if filled else COLOUR)
    p.drawPolygon(shape)


layer(96, 142, False)      # publish
layer(96, 112, False)      # asset
layer(96, 82, True)        # shot: the one being edited

# A move arrow beside the top layer.
pen = QtGui.QPen(WHITE, 9, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin)
p.setPen(pen)
p.drawLine(P(176, 82), P(222, 82))
p.drawLine(P(199, 59), P(199, 105))
p.setPen(QtCore.Qt.NoPen)
p.setBrush(WHITE)
for tip in ((P(236, 82), P(220, 72), P(220, 92)), (P(199, 45), P(189, 61), P(209, 61)),
            (P(199, 119), P(189, 103), P(209, 103))):
    p.drawPolygon(QtGui.QPolygonF(list(tip)))

family = QtGui.QFontDatabase.applicationFontFamilies(QtGui.QFontDatabase.addApplicationFont(
    os.path.join(os.environ.get("WINDIR", "C:/Windows"), "Fonts", "arialbd.ttf")))
font = QtGui.QFont(family[0] if family else "Arial", 1, QtGui.QFont.Bold)
font.setPixelSize(38)
p.setFont(font)
p.setPen(WHITE)
p.drawText(QtCore.QRectF(0, 192, SIZE, 52), QtCore.Qt.AlignCenter, "USD EDIT")
p.end()

os.makedirs(os.path.dirname(OUT), exist_ok=True)
image.save(OUT)
print("Saved: %s" % OUT)
