"""Run once inside Maya (or mayapy) to generate iconEdgeToCurve.png."""
import os
from PySide6 import QtGui, QtCore


def gen():
    scale = 4  # 64px design scaled up to the standard 256x256 shelf icon size
    size = 64 * scale
    px = QtGui.QPixmap(size, size)
    px.fill(QtCore.Qt.GlobalColor.transparent)
    p = QtGui.QPainter(px)
    p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

    # ── dark rounded background ───────────────────────────────────────────────
    p.setBrush(QtGui.QColor(45, 45, 55))
    p.setPen(QtCore.Qt.PenStyle.NoPen)
    p.drawRoundedRect(0, 0, size, size, 10 * scale, 10 * scale)

    # ── faint mesh grid ───────────────────────────────────────────────────────
    grid_pen = QtGui.QPen(QtGui.QColor(95, 95, 110), 1.2 * scale)
    p.setPen(grid_pen)
    for i in range(1, 6):
        v = (8 + i * 8) * scale
        p.drawLine(QtCore.QPointF(v, 8 * scale), QtCore.QPointF(v, 56 * scale))
        p.drawLine(QtCore.QPointF(8 * scale, v), QtCore.QPointF(56 * scale, v))

    # ── selected edge path (bright) on grid vertices ──────────────────────────
    verts = [(24, 56), (24, 48), (32, 40), (32, 32), (40, 24), (40, 16), (40, 8)]
    verts = [QtCore.QPointF(x * scale, y * scale) for x, y in verts]
    edge_pen = QtGui.QPen(QtGui.QColor(120, 200, 255), 2.0 * scale)
    p.setPen(edge_pen)
    for a, b in zip(verts, verts[1:]):
        p.drawLine(a, b)

    # ── smooth curve through the path ─────────────────────────────────────────
    path = QtGui.QPainterPath(verts[0])
    for i in range(1, len(verts)):
        a, b = verts[i - 1], verts[i]
        mid = (a + b) / 2
        path.quadTo(a, mid) if i > 1 else path.lineTo(mid)
    path.lineTo(verts[-1])
    curve_pen = QtGui.QPen(QtGui.QColor(255, 160, 50), 3.0 * scale)
    curve_pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
    p.setPen(curve_pen)
    p.setBrush(QtCore.Qt.BrushStyle.NoBrush)
    p.drawPath(path)

    # ── snapped CV dots ───────────────────────────────────────────────────────
    p.setPen(QtGui.QPen(QtGui.QColor(45, 45, 55), 1.0 * scale))
    p.setBrush(QtGui.QColor(255, 230, 120))
    for v in verts:
        p.drawEllipse(v, 2.2 * scale, 2.2 * scale)

    p.end()
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'iconEdgeToCurve.png')
    px.save(out, 'PNG')
    print('Saved', out)


if __name__ == '__main__':
    import sys
    app = QtGui.QGuiApplication.instance() or QtGui.QGuiApplication(sys.argv)
    gen()
