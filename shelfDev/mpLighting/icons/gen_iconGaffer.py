"""Run once in mayapy (or Maya) to generate iconGaffer.png for Send to Gaffer
(pipeDev/lightingDev/gafferSend.py): a cube sent along an arrow into a
little node graph. 256x256, rounded corners."""
import os
from PySide6 import QtGui, QtCore


def gen():
    scale = 4  # 64px design scaled up to the standard 256x256 shelf icon size
    size = 64 * scale
    img = QtGui.QImage(size, size, QtGui.QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(QtCore.Qt.GlobalColor.transparent)
    p = QtGui.QPainter(img)
    p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    s = lambda v: v * scale
    pt = lambda x, y: QtCore.QPointF(s(x), s(y))

    # dark rounded background (matches the other pipe icons)
    p.setPen(QtCore.Qt.PenStyle.NoPen)
    p.setBrush(QtGui.QColor(40, 38, 50))
    p.drawRoundedRect(0, 0, size, size, s(10), s(10))

    # the cube (what's sent), top left
    top = QtGui.QPolygonF([pt(8, 15), pt(17, 10), pt(26, 15), pt(17, 20)])
    left = QtGui.QPolygonF([pt(8, 15), pt(17, 20), pt(17, 30), pt(8, 25)])
    right = QtGui.QPolygonF([pt(17, 20), pt(26, 15), pt(26, 25), pt(17, 30)])
    for poly, colour in ((top, (120, 190, 255)), (left, (70, 130, 210)), (right, (45, 95, 170))):
        p.setBrush(QtGui.QColor(*colour))
        p.drawPolygon(poly)

    # the arrow across
    orange = QtGui.QColor(240, 150, 50)
    p.setPen(QtGui.QPen(orange, s(3.2), QtCore.Qt.PenStyle.SolidLine,
                        QtCore.Qt.PenCapStyle.RoundCap))
    p.drawLine(pt(14, 38), pt(30, 38))
    p.setPen(QtCore.Qt.PenStyle.NoPen)
    p.setBrush(orange)
    p.drawPolygon(QtGui.QPolygonF([pt(29, 32), pt(37, 38), pt(29, 44)]))

    # the node graph it lands in, right
    wire = QtGui.QPen(QtGui.QColor(176, 176, 190), s(1.6))
    nodes = [(48, 14), (48, 33), (40, 52), (56, 52)]
    p.setPen(wire)
    for a, b in ((0, 1), (1, 2), (1, 3)):
        p.drawLine(pt(*nodes[a]), pt(*nodes[b]))
    p.setPen(QtCore.Qt.PenStyle.NoPen)
    for i, (x, y) in enumerate(nodes):
        p.setBrush(QtGui.QColor(240, 150, 50) if i == 1 else QtGui.QColor(225, 225, 235))
        p.drawRoundedRect(QtCore.QRectF(s(x - 6), s(y - 4), s(12), s(8)), s(2), s(2))
    p.end()

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "iconGaffer.png")
    img.save(out)
    return out


if __name__ == "__main__":
    app = QtGui.QGuiApplication.instance() or QtGui.QGuiApplication([])
    print(gen())
