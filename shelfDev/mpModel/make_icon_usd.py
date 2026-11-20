"""
make_icon_usd.py: generates icons/iconModelUsdHierarchy.png and
icons/iconModelUsdNames.png (256x256, rounded corners) in the mpModel style
(make_icon_convert.py): a flat colour, a white drawing and a label.
Hierarchy: a little tree, geo above render and proxy. Names: a name tag.
Run with: mayapy make_icon_usd.py
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6 import QtCore, QtGui, QtWidgets

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

SIZE = 256
COLOUR = QtGui.QColor("#d9822b")
WHITE = QtGui.QColor("white")
ICONS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")
P = QtCore.QPointF


def _font(pixels):
    # Offscreen Qt has no system fonts: load Arial Bold from Windows.
    family = QtGui.QFontDatabase.applicationFontFamilies(QtGui.QFontDatabase.addApplicationFont(
        os.path.join(os.environ.get("WINDIR", "C:/Windows"), "Fonts", "arialbd.ttf")))
    font = QtGui.QFont(family[0] if family else "Arial", 1, QtGui.QFont.Bold)
    font.setPixelSize(pixels)
    return font


def _start():
    image = QtGui.QImage(SIZE, SIZE, QtGui.QImage.Format_ARGB32)
    image.fill(QtCore.Qt.transparent)
    p = QtGui.QPainter(image)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    p.setPen(QtCore.Qt.NoPen)
    p.setBrush(COLOUR)
    p.drawRoundedRect(0, 0, SIZE, SIZE, 30, 30)
    return image, p


def _finish(image, p, label, name, pixels=40):
    p.setFont(_font(pixels))
    p.setPen(WHITE)
    p.drawText(QtCore.QRectF(0, 192, SIZE, 52), QtCore.Qt.AlignCenter, label)
    p.end()
    os.makedirs(ICONS, exist_ok=True)
    out = os.path.join(ICONS, name)
    image.save(out)
    print("Saved: %s" % out)


# --- USD Hierarchy: geo, with render and proxy below it ----------------------
image, p = _start()
pen = QtGui.QPen(WHITE, 8, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin)
p.setPen(pen)
p.setBrush(QtCore.Qt.NoBrush)
p.drawLine(P(78, 66), P(78, 150))           # the trunk
p.drawLine(P(78, 108), P(124, 108))         # to render
p.drawLine(P(78, 150), P(124, 150))         # to proxy
p.setPen(QtCore.Qt.NoPen)
p.setBrush(WHITE)
p.drawRoundedRect(QtCore.QRectF(44, 28, 120, 40), 9, 9)        # geo
p.drawRoundedRect(QtCore.QRectF(124, 90, 92, 36), 8, 8)        # render
p.setBrush(QtCore.Qt.NoBrush)
p.setPen(QtGui.QPen(WHITE, 6))
p.drawRoundedRect(QtCore.QRectF(127, 135, 86, 30), 7, 7)       # proxy: outline only
p.setPen(COLOUR)
p.setFont(_font(24))
p.drawText(QtCore.QRectF(44, 28, 120, 40), QtCore.Qt.AlignCenter, "geo")
_finish(image, p, "USD TREE", "iconModelUsdHierarchy.png")

# --- USD Names: a name tag --------------------------------------------------
image, p = _start()
p.setPen(QtCore.Qt.NoPen)
p.setBrush(WHITE)
tag = QtGui.QPainterPath()
tag.moveTo(42, 60)
tag.lineTo(178, 60)
tag.lineTo(222, 112)
tag.lineTo(178, 164)
tag.lineTo(42, 164)
tag.closeSubpath()
p.drawPath(tag)
p.setBrush(COLOUR)
p.drawEllipse(P(190, 112), 9, 9)            # the tag's hole
p.setPen(COLOUR)
p.setFont(_font(30))
p.drawText(QtCore.QRectF(46, 72, 132, 40), QtCore.Qt.AlignCenter, "seat")
p.setFont(_font(26))
p.drawText(QtCore.QRectF(46, 112, 132, 40), QtCore.Qt.AlignCenter, "_GEO")
_finish(image, p, "USD NAMES", "iconModelUsdNames.png", pixels=38)
