"""Run once in mayapy (or Maya) to generate iconRenderSub.png: a film frame
lit by a spotlight cone, with an upload-arrow badge, for renderSub
(pipeDev/lightingDev/renderSub_ui.py). 256x256, rounded corners."""
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

    # dark rounded background (matches the other pipe icons)
    p.setPen(QtCore.Qt.PenStyle.NoPen)
    p.setBrush(QtGui.QColor(40, 38, 50))
    p.drawRoundedRect(0, 0, size, size, s(10), s(10))

    # light cone from the top-left lamp onto the frame
    cone = QtGui.QPolygonF([QtCore.QPointF(s(12), s(10)), QtCore.QPointF(s(18), s(8)),
                            QtCore.QPointF(s(48), s(26)), QtCore.QPointF(s(18), s(44))])
    grad = QtGui.QLinearGradient(s(14), s(9), s(40), s(38))
    grad.setColorAt(0, QtGui.QColor(255, 220, 120, 200))
    grad.setColorAt(1, QtGui.QColor(255, 200, 90, 20))
    p.setBrush(grad)
    p.drawPolygon(cone)
    p.setBrush(QtGui.QColor(255, 210, 90))
    p.drawEllipse(QtCore.QPointF(s(14), s(9)), s(5), s(5))

    # film frame with sprocket holes
    frame = QtCore.QRectF(s(14), s(24), s(36), s(26))
    p.setBrush(QtGui.QColor(30, 30, 36))
    p.setPen(QtGui.QPen(QtGui.QColor(235, 235, 240), s(1.6)))
    p.drawRoundedRect(frame, s(2), s(2))
    p.setPen(QtCore.Qt.PenStyle.NoPen)
    p.setBrush(QtGui.QColor(235, 235, 240))
    for i in range(5):
        x = s(17 + i * 7)
        p.drawRect(QtCore.QRectF(x, s(26), s(3), s(2.5)))
        p.drawRect(QtCore.QRectF(x, s(45.5), s(3), s(2.5)))
    # the lit picture: a warm gradient
    pic = QtCore.QRectF(s(17), s(30), s(30), s(14))
    g2 = QtGui.QLinearGradient(pic.topLeft(), pic.bottomRight())
    g2.setColorAt(0, QtGui.QColor(255, 190, 90))
    g2.setColorAt(1, QtGui.QColor(200, 80, 60))
    p.setBrush(g2)
    p.drawRect(pic)

    # upload badge, bottom right (publish to H + ShotGrid)
    centre = QtCore.QPointF(s(51), s(51))
    p.setPen(QtGui.QPen(QtGui.QColor(40, 38, 50), s(2)))
    p.setBrush(QtGui.QColor(60, 150, 230))
    p.drawEllipse(centre, s(10), s(10))
    pen = QtGui.QPen(QtGui.QColor(255, 255, 255), s(2.6))
    pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(QtCore.Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.drawLine(QtCore.QPointF(s(51), s(56)), QtCore.QPointF(s(51), s(46)))
    p.drawPolyline(QtGui.QPolygonF([QtCore.QPointF(s(46.5), s(50)), QtCore.QPointF(s(51), s(45.5)),
                                    QtCore.QPointF(s(55.5), s(50))]))
    p.end()

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "iconRenderSub.png")
    img.save(out)
    return out


if __name__ == "__main__":
    app = QtGui.QGuiApplication.instance() or QtGui.QGuiApplication([])
    print(gen())
