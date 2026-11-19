"""Run once in mayapy (or Maya) to generate iconBackdropCard.png: a dashed
image-plane outline behind a solid sky card (gradient, sun, clouds) facing
a small camera, for Backdrop Card (pipeDev/lightingDev/backdropCard.py).
256x256, rounded corners, same background as the other mpLighting icons."""
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

    # the free image plane: a dashed outline, offset behind the card
    pen = QtGui.QPen(QtGui.QColor(170, 170, 185), s(1.3))
    pen.setDashPattern([2.5, 2])
    p.setPen(pen)
    p.setBrush(QtCore.Qt.BrushStyle.NoBrush)
    p.drawPolygon(QtGui.QPolygonF([pt(18, 8), pt(57, 12), pt(57, 40), pt(18, 38)]))

    # the card: sky gradient on a slightly turned quad
    card = QtGui.QPolygonF([pt(10, 15), pt(49, 19), pt(49, 48), pt(10, 46)])
    grad = QtGui.QLinearGradient(pt(30, 15), pt(30, 48))
    grad.setColorAt(0, QtGui.QColor(70, 130, 220))
    grad.setColorAt(0.7, QtGui.QColor(150, 195, 240))
    grad.setColorAt(1, QtGui.QColor(250, 205, 150))
    p.setPen(QtCore.Qt.PenStyle.NoPen)
    p.setBrush(grad)
    p.drawPolygon(card)
    p.save()
    clip = QtGui.QPainterPath(); clip.addPolygon(card); p.setClipPath(clip)
    p.setBrush(QtGui.QColor(255, 225, 120))                      # sun
    p.drawEllipse(pt(38, 34), s(4.5), s(4.5))
    p.setBrush(QtGui.QColor(255, 255, 255, 230))                 # clouds
    for cx, cy, r in ((17, 26, 3.2), (21, 24.5, 4), (25.5, 26.5, 3), (33, 22, 2.4), (36.5, 21, 3)):
        p.drawEllipse(pt(cx, cy), s(r), s(r * 0.75))
    p.restore()
    p.setPen(QtGui.QPen(QtGui.QColor(235, 235, 240), s(1.4)))
    p.setBrush(QtCore.Qt.BrushStyle.NoBrush)
    p.drawPolygon(card)

    # a small camera looking at the card (it renders now)
    p.setPen(QtCore.Qt.PenStyle.NoPen)
    p.setBrush(QtGui.QColor(235, 235, 240))
    p.drawRoundedRect(QtCore.QRectF(s(36), s(50), s(14), s(9)), s(1.5), s(1.5))
    p.drawPolygon(QtGui.QPolygonF([pt(50, 52.5), pt(56, 49.5), pt(56, 59.5), pt(50, 56.5)]))
    p.setBrush(QtGui.QColor(230, 70, 60))                        # record light
    p.drawEllipse(pt(39.5, 53), s(1.3), s(1.3))
    p.end()

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "iconBackdropCard.png")
    img.save(out)
    return out


if __name__ == "__main__":
    app = QtGui.QGuiApplication.instance() or QtGui.QGuiApplication([])
    print(gen())
