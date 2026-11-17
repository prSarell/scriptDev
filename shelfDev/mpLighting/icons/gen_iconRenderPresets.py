"""Run once in mayapy (or Maya) to generate iconRenderPresets.png: a spot
light over a stack of preset cards, with settings sliders on the top card,
for Render Presets (pipeDev/lightingDev/renderPresets_ui.py). 256x256,
rounded corners, same background as iconRenderSub."""
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

    # light cone from the lamp down onto the cards
    cone = QtGui.QPolygonF([pt(28, 13), pt(36, 13), pt(54, 40), pt(10, 40)])
    grad = QtGui.QLinearGradient(pt(32, 12), pt(32, 40))
    grad.setColorAt(0, QtGui.QColor(255, 220, 120, 190))
    grad.setColorAt(1, QtGui.QColor(255, 200, 90, 15))
    p.setBrush(grad)
    p.drawPolygon(cone)
    # the lamp: a spot light head
    p.setBrush(QtGui.QColor(235, 235, 240))
    p.drawPolygon(QtGui.QPolygonF([pt(25, 5), pt(39, 5), pt(37, 13), pt(27, 13)]))
    p.setBrush(QtGui.QColor(255, 210, 90))
    p.drawRoundedRect(QtCore.QRectF(s(27), s(11.5), s(10), s(3)), s(1.2), s(1.2))

    # stack of preset cards
    for i, shade in enumerate((90, 130)):
        off = (2 - i) * 3.5
        p.setBrush(QtGui.QColor(shade, shade, shade + 15))
        p.drawRoundedRect(QtCore.QRectF(s(12 + off), s(30 - off), s(40), s(26)), s(3), s(3))
    top = QtCore.QRectF(s(12), s(37), s(40), s(22))
    p.setBrush(QtGui.QColor(235, 235, 240))
    p.drawRoundedRect(top, s(3), s(3))

    # settings sliders on the top card
    for row, (knob, colour) in enumerate(((0.65, (60, 150, 230)), (0.3, (255, 170, 60)),
                                          (0.8, (90, 190, 120)))):
        y = 42.5 + row * 6
        pen = QtGui.QPen(QtGui.QColor(150, 150, 160), s(1.4))
        pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawLine(pt(17, y), pt(47, y))
        p.setPen(QtCore.Qt.PenStyle.NoPen)
        p.setBrush(QtGui.QColor(*colour))
        p.drawEllipse(pt(17 + 30 * knob, y), s(2.3), s(2.3))
    p.end()

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "iconRenderPresets.png")
    img.save(out)
    return out


if __name__ == "__main__":
    app = QtGui.QGuiApplication.instance() or QtGui.QGuiApplication([])
    print(gen())
