"""Run once in mayapy (or Maya) to generate iconScout.png: a list of renders
with progress bars and a pause badge, for Scout, the render manager
(pipeDev/scoutDev/scout_ui.py). 256x256, rounded corners."""
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

    # four render rows: a status dot, then a progress bar
    rows = ((0.55, QtGui.QColor(95, 168, 255)),     # rendering
            (1.0, QtGui.QColor(98, 195, 112)),      # done
            (0.35, QtGui.QColor(240, 176, 64)),     # paused
            (0.0, QtGui.QColor(176, 176, 176)))     # waiting
    for i, (fill, colour) in enumerate(rows):
        y = s(11 + i * 10.5)
        p.setBrush(colour)
        p.drawEllipse(QtCore.QPointF(s(11), y + s(3)), s(3), s(3))
        track = QtCore.QRectF(s(18), y, s(36), s(6))
        p.setBrush(QtGui.QColor(70, 68, 84))
        p.drawRoundedRect(track, s(3), s(3))
        if fill:
            p.setBrush(colour)
            p.drawRoundedRect(QtCore.QRectF(track.x(), y, track.width() * fill, s(6)), s(3), s(3))

    # pause badge, bottom right
    centre = QtCore.QPointF(s(50), s(51))
    p.setPen(QtGui.QPen(QtGui.QColor(40, 38, 50), s(2)))
    p.setBrush(QtGui.QColor(240, 176, 64))
    p.drawEllipse(centre, s(10), s(10))
    p.setPen(QtCore.Qt.PenStyle.NoPen)
    p.setBrush(QtGui.QColor(40, 38, 50))
    p.drawRoundedRect(QtCore.QRectF(s(45.5), s(45.5), s(3.2), s(11)), s(1), s(1))
    p.drawRoundedRect(QtCore.QRectF(s(51.3), s(45.5), s(3.2), s(11)), s(1), s(1))
    p.end()

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "iconScout.png")
    img.save(out)
    return out


if __name__ == "__main__":
    app = QtGui.QGuiApplication.instance() or QtGui.QGuiApplication([])
    print(gen())
