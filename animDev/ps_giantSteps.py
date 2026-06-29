# -*- coding: utf-8 -*-
"""
ps_giantSteps.py — Giant Steps: Non-destructive stepped-key workflow

Usage:
    import importlib
    import ps_giantSteps as gs
    importlib.reload(gs)
    gs.show()
"""

from __future__ import annotations

import maya.cmds as cmds
import maya.mel as mel
from maya import OpenMayaUI as omui
from PySide6 import QtWidgets, QtCore, QtGui
from shiboken6 import wrapInstance


# ═════════════════════════════════════════════════════════════════════════════
# Constants
# ═════════════════════════════════════════════════════════════════════════════

WINDOW_NAME = "psGiantStepsWin"

# Dark theme
_BG       = "#1e1e1e"
_BG_PANEL = "#252525"
_BG_INPUT = "#2e2e2e"
_BORDER   = "#444444"
_FG       = "#ffffff"
_FG_DIM   = "#aaaaaa"

# Timeline colours
_MARKED     = "#4caf50"
_MARKED_HVR = "#66bb6a"
_UNMARKED   = "#3a3a3a"
_HOVER      = "#4a4a4a"
_CURRENT    = "#e0a030"

# Buttons
_GREEN_BTN_BG  = "#2e5a2e"
_GREEN_BTN_HVR = "#3a7a3a"
_ACCENT        = "#4D90D4"
_ACCENT_HVR    = "#3a6fa8"

STYLESHEET = f"""
QDialog {{
    background-color: {_BG};
    color: {_FG};
    font-size: 12px;
}}
QLabel {{
    color: {_FG};
    background: transparent;
}}
QLineEdit {{
    background: {_BG_INPUT};
    border: 1px solid {_BORDER};
    border-radius: 2px;
    padding: 5px 8px;
    color: {_FG};
}}
QLineEdit:focus {{
    border-color: {_ACCENT};
}}
QSpinBox {{
    background: {_BG_INPUT};
    border: 1px solid {_BORDER};
    border-radius: 2px;
    padding: 3px 6px;
    color: {_FG};
}}
QPushButton {{
    background: {_BG_INPUT};
    border: 1px solid {_BORDER};
    border-radius: 2px;
    padding: 5px 12px;
    color: {_FG};
}}
QPushButton:hover {{
    background: {_HOVER};
}}
#headerTitle {{
    font-size: 14px;
    font-weight: bold;
    color: rgba(255,255,255,200);
    padding: 6px 0px;
}}
#infoLabel {{
    color: {_FG_DIM};
    font-size: 11px;
}}
#statusLabel {{
    color: {_FG_DIM};
    font-size: 11px;
    padding: 4px 0px;
}}
#bakeBtn {{
    background: {_GREEN_BTN_BG};
    color: white;
    font-weight: bold;
    font-size: 13px;
    border: none;
    border-radius: 3px;
    padding: 8px 16px;
    min-height: 32px;
}}
#bakeBtn:hover {{
    background: {_GREEN_BTN_HVR};
}}
#bakeBtn:disabled {{
    background: #333;
    color: #555;
}}
#previewBtn {{
    background: {_ACCENT};
    color: white;
    font-weight: bold;
    border: none;
    border-radius: 2px;
    padding: 5px 16px;
}}
#previewBtn:hover {{
    background: {_ACCENT_HVR};
}}
#refreshBtn {{
    font-size: 11px;
    padding: 3px 10px;
}}
#quickBtn {{
    font-size: 11px;
    padding: 3px 8px;
}}
"""


# ═════════════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════════════

def _maya_main_window():
    ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(ptr), QtWidgets.QWidget)


def _get_timeslider_range():
    tc = mel.eval("$tmpVar=$gPlayBackSlider")
    rng = cmds.timeControl(tc, q=True, rangeArray=True)
    if (rng[1] - rng[0]) <= 1:
        start = int(cmds.playbackOptions(q=True, min=True))
        end = int(cmds.playbackOptions(q=True, max=True))
    else:
        start = int(rng[0])
        end = int(rng[1] - 1)
    return start, end


def _get_selected_controls():
    sel = cmds.ls(sl=True, long=False) or []
    controls = []
    for s in sel:
        if cmds.objectType(s, isAType="transform"):
            controls.append(s)
    return controls


def _auto_layer_name():
    existing = set(cmds.ls(type="animLayer") or [])
    for i in range(1, 1000):
        name = "giantSteps_{:03d}".format(i)
        if name not in existing:
            return name
    return "giantSteps"


# ═════════════════════════════════════════════════════════════════════════════
# Timeline Widget
# ═════════════════════════════════════════════════════════════════════════════

class TimelineWidget(QtWidgets.QWidget):

    markers_changed = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._start = 1
        self._end = 24
        self._marked: set[int] = set()
        self._hover_frame: int | None = None
        self._current_frame: int | None = None
        self.setMouseTracking(True)
        self.setMinimumHeight(44)
        self.setFixedHeight(50)

    def set_range(self, start: int, end: int):
        self._start = start
        self._end = end
        self._marked.clear()
        self._hover_frame = None
        self.markers_changed.emit()
        self.update()

    def set_marked_frames(self, frames: set[int]):
        self._marked = set(frames)
        self.markers_changed.emit()
        self.update()

    def get_marked_frames(self) -> list[int]:
        return sorted(self._marked)

    def set_current_frame(self, frame: int):
        self._current_frame = frame
        self.update()

    def _num_frames(self) -> int:
        return max(1, self._end - self._start + 1)

    def _cell_width(self) -> float:
        pad = 4
        return (self.width() - pad * 2) / self._num_frames()

    def _frame_at_x(self, x: int):
        pad = 4
        idx = int((x - pad) / self._cell_width())
        frame = self._start + idx
        if frame < self._start or frame > self._end:
            return None
        return frame

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        pad = 4
        num = self._num_frames()
        cw = self._cell_width()
        h = self.height()
        cell_h = h - 8
        y_off = 4

        show_labels = cw >= 18
        label_every = 1
        if cw < 18:
            show_labels = cw >= 10
            label_every = 2
        if cw < 10:
            show_labels = False

        font = p.font()
        font.setPixelSize(max(8, min(10, int(cw * 0.6))))
        p.setFont(font)

        for i in range(num):
            frame = self._start + i
            x = pad + i * cw
            rect = QtCore.QRectF(x + 0.5, y_off, cw - 1, cell_h)

            if frame in self._marked:
                if frame == self._hover_frame:
                    p.setBrush(QtGui.QColor(_MARKED_HVR))
                else:
                    p.setBrush(QtGui.QColor(_MARKED))
                p.setPen(QtCore.Qt.PenStyle.NoPen)
                p.drawRoundedRect(rect, 2, 2)
                p.setPen(QtGui.QColor("#ffffff"))
            else:
                if frame == self._hover_frame:
                    p.setBrush(QtGui.QColor(_HOVER))
                else:
                    p.setBrush(QtGui.QColor(_UNMARKED))
                p.setPen(QtCore.Qt.PenStyle.NoPen)
                p.drawRoundedRect(rect, 2, 2)
                p.setPen(QtGui.QColor(_FG_DIM))

            if show_labels and (i % label_every == 0):
                p.drawText(rect, QtCore.Qt.AlignmentFlag.AlignCenter, str(frame))

            if self._current_frame == frame:
                pen = QtGui.QPen(QtGui.QColor(_CURRENT), 2)
                p.setPen(pen)
                p.setBrush(QtCore.Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), 2, 2)

        p.end()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            frame = self._frame_at_x(int(event.position().x()))
            if frame is not None:
                if frame in self._marked:
                    self._marked.discard(frame)
                else:
                    self._marked.add(frame)
                self.markers_changed.emit()
                self.update()

    def mouseMoveEvent(self, event):
        frame = self._frame_at_x(int(event.position().x()))
        if frame != self._hover_frame:
            self._hover_frame = frame
            self.update()

    def leaveEvent(self, event):
        self._hover_frame = None
        self.update()


# ═════════════════════════════════════════════════════════════════════════════
# Main Dialog
# ═════════════════════════════════════════════════════════════════════════════

class GiantStepsDialog(QtWidgets.QDialog):

    _instance = None

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName(WINDOW_NAME)
        self.setWindowTitle("Giant Steps")
        self.setWindowFlags(
            QtCore.Qt.WindowType.Window
            | QtCore.Qt.WindowType.WindowMinimizeButtonHint
            | QtCore.Qt.WindowType.WindowCloseButtonHint
        )
        self.setMinimumWidth(500)
        self.resize(600, 340)
        self.setStyleSheet(STYLESHEET)

        self._controls: list[str] = []
        self._start = 1
        self._end = 24
        self._preview_playing = False
        self._preview_index = 0
        self._script_jobs: list[int] = []

        self._preview_timer = QtCore.QTimer(self)
        self._preview_timer.timeout.connect(self._preview_step)

        self._build_ui()
        self._refresh_selection()

        try:
            job_id = cmds.scriptJob(
                event=["timeChanged", self._on_time_changed],
                parent=WINDOW_NAME,
                protected=True,
            )
            self._script_jobs.append(job_id)
        except Exception:
            pass

    # ── Build UI ─────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 8)
        root.setSpacing(8)

        # Header
        title = QtWidgets.QLabel("Giant Steps")
        title.setObjectName("headerTitle")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)

        # Info row
        info_row = QtWidgets.QHBoxLayout()
        info_row.setSpacing(12)
        self._info_label = QtWidgets.QLabel("No controls selected")
        self._info_label.setObjectName("infoLabel")
        info_row.addWidget(self._info_label, 1)
        refresh_btn = QtWidgets.QPushButton("Refresh")
        refresh_btn.setObjectName("refreshBtn")
        refresh_btn.clicked.connect(self._refresh_selection)
        info_row.addWidget(refresh_btn)
        root.addLayout(info_row)

        # Timeline
        self._timeline = TimelineWidget()
        self._timeline.markers_changed.connect(self._on_markers_changed)
        root.addWidget(self._timeline)

        # Quick-mark row
        qm_row = QtWidgets.QHBoxLayout()
        qm_row.setSpacing(4)
        qm_label = QtWidgets.QLabel("Mark:")
        qm_label.setObjectName("infoLabel")
        qm_row.addWidget(qm_label)
        for n in (2, 3, 4):
            btn = QtWidgets.QPushButton("Every {}s".format(n))
            btn.setObjectName("quickBtn")
            btn.clicked.connect(lambda checked=False, step=n: self._mark_every_n(step))
            qm_row.addWidget(btn)
        clear_btn = QtWidgets.QPushButton("Clear All")
        clear_btn.setObjectName("quickBtn")
        clear_btn.clicked.connect(self._clear_markers)
        qm_row.addWidget(clear_btn)
        qm_row.addStretch()
        root.addLayout(qm_row)

        # Preview row
        prev_row = QtWidgets.QHBoxLayout()
        prev_row.setSpacing(8)
        self._preview_btn = QtWidgets.QPushButton("Preview")
        self._preview_btn.setObjectName("previewBtn")
        self._preview_btn.clicked.connect(self._toggle_preview)
        prev_row.addWidget(self._preview_btn)
        prev_row.addWidget(QtWidgets.QLabel("Speed:"))
        self._fps_spin = QtWidgets.QSpinBox()
        self._fps_spin.setRange(1, 24)
        self._fps_spin.setValue(8)
        self._fps_spin.setSuffix(" fps")
        prev_row.addWidget(self._fps_spin)
        prev_row.addStretch()
        root.addLayout(prev_row)

        # Separator
        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        sep.setStyleSheet("color: {};".format(_BORDER))
        root.addWidget(sep)

        # Bake section
        bake_row = QtWidgets.QHBoxLayout()
        bake_row.setSpacing(8)
        bake_row.addWidget(QtWidgets.QLabel("Layer:"))
        self._layer_edit = QtWidgets.QLineEdit(_auto_layer_name())
        bake_row.addWidget(self._layer_edit, 1)
        root.addLayout(bake_row)

        self._bake_btn = QtWidgets.QPushButton("Bake Stepped Keys")
        self._bake_btn.setObjectName("bakeBtn")
        self._bake_btn.clicked.connect(self._bake)
        root.addWidget(self._bake_btn)

        # Status
        self._status = QtWidgets.QLabel("Select controls and set a timeline range, then mark step frames.")
        self._status.setObjectName("statusLabel")
        root.addWidget(self._status)

    # ── Selection / Range ────────────────────────────────────────────────

    def _refresh_selection(self):
        self._controls = _get_selected_controls()
        self._start, self._end = _get_timeslider_range()
        self._timeline.set_range(self._start, self._end)
        self._layer_edit.setText(_auto_layer_name())

        if self._controls:
            self._info_label.setText(
                "{} controls  |  Frames {} – {} ({})".format(
                    len(self._controls), self._start, self._end,
                    self._end - self._start + 1
                )
            )
        else:
            self._info_label.setText("No controls selected  |  Frames {} – {}".format(
                self._start, self._end
            ))

        self._update_button_states()

    def _on_markers_changed(self):
        n = len(self._timeline.get_marked_frames())
        self._set_status("{} step frames marked".format(n) if n else "Click the timeline to mark step frames")
        self._update_button_states()

    def _update_button_states(self):
        has_marks = len(self._timeline.get_marked_frames()) > 0
        has_ctrls = len(self._controls) > 0
        self._bake_btn.setEnabled(has_marks and has_ctrls)
        self._preview_btn.setEnabled(has_marks)

    def _on_time_changed(self):
        if not self._preview_playing:
            try:
                frame = int(cmds.currentTime(q=True))
                self._timeline.set_current_frame(frame)
            except Exception:
                pass

    # ── Quick mark ───────────────────────────────────────────────────────

    def _mark_every_n(self, n: int):
        frames = set()
        for f in range(self._start, self._end + 1, n):
            frames.add(f)
        if self._end not in frames:
            frames.add(self._end)
        self._timeline.set_marked_frames(frames)

    def _clear_markers(self):
        self._timeline.set_marked_frames(set())

    # ── Preview ──────────────────────────────────────────────────────────

    def _toggle_preview(self):
        if self._preview_playing:
            self._stop_preview()
        else:
            self._start_preview()

    def _start_preview(self):
        frames = self._timeline.get_marked_frames()
        if not frames:
            self._set_status("No frames marked")
            return

        cmds.play(state=False)
        self._preview_playing = True
        self._preview_index = 0
        self._preview_btn.setText("Stop")

        interval = max(16, int(1000.0 / self._fps_spin.value()))
        self._preview_timer.start(interval)

        cmds.undoInfo(stateWithoutFlush=False)
        cmds.currentTime(frames[0], edit=True)
        self._timeline.set_current_frame(frames[0])

    def _preview_step(self):
        frames = self._timeline.get_marked_frames()
        if not frames:
            self._stop_preview()
            return

        self._preview_index = (self._preview_index + 1) % len(frames)
        frame = frames[self._preview_index]
        cmds.currentTime(frame, edit=True)
        self._timeline.set_current_frame(frame)

    def _stop_preview(self):
        self._preview_timer.stop()
        self._preview_playing = False
        self._preview_btn.setText("Preview")
        cmds.undoInfo(stateWithoutFlush=True)

    # ── Bake ─────────────────────────────────────────────────────────────

    def _bake(self):
        if not self._controls:
            cmds.inViewMessage(
                amg="<hl>No controls selected</hl> — select animation controls first.",
                pos="midCenter", fade=True,
            )
            return

        frames = self._timeline.get_marked_frames()
        if not frames:
            self._set_status("No frames marked")
            return

        layer_name = self._layer_edit.text().strip()
        if not layer_name:
            layer_name = _auto_layer_name()
            self._layer_edit.setText(layer_name)

        if cmds.objExists(layer_name):
            layer_name = _auto_layer_name()
            self._layer_edit.setText(layer_name)

        self._set_status("Baking...")
        QtWidgets.QApplication.processEvents()

        cmds.undoInfo(openChunk=True, chunkName="GiantSteps_Bake")
        try:
            cmds.animLayer(layer_name, override=True)
            cmds.select(self._controls)
            cmds.animLayer(layer_name, edit=True, addSelectedObjects=True)

            for frame in frames:
                for ctrl in self._controls:
                    attrs = cmds.listAttr(ctrl, keyable=True) or []
                    for attr in attrs:
                        full = "{}.{}".format(ctrl, attr)
                        try:
                            val = cmds.getAttr(full, time=frame)
                            if isinstance(val, list):
                                val = val[0]
                            if isinstance(val, (tuple, list)):
                                continue
                            cmds.setKeyframe(
                                ctrl, attribute=attr,
                                time=frame, value=float(val),
                                animLayer=layer_name,
                            )
                        except Exception:
                            pass

            layer_curves = cmds.animLayer(layer_name, q=True, animCurves=True) or []
            for curve in layer_curves:
                try:
                    cmds.keyTangent(curve, ott="step")
                except Exception:
                    pass

            cmds.select(self._controls)

            self._set_status(
                "Baked {} frames on '{}' ({} controls)".format(
                    len(frames), layer_name, len(self._controls)
                )
            )
            cmds.inViewMessage(
                amg="<hl>Giant Steps</hl> — layer '{}' created".format(layer_name),
                pos="midCenter", fade=True,
            )
            self._layer_edit.setText(_auto_layer_name())

        except Exception as e:
            self._set_status("Bake failed: {}".format(e))
            cmds.warning("Giant Steps bake failed: {}".format(e))
        finally:
            cmds.undoInfo(closeChunk=True)

    # ── Status ───────────────────────────────────────────────────────────

    def _set_status(self, msg: str):
        self._status.setText(msg)

    # ── Cleanup ──────────────────────────────────────────────────────────

    def closeEvent(self, event):
        if self._preview_playing:
            self._stop_preview()
        for job in self._script_jobs:
            try:
                cmds.scriptJob(kill=job, force=True)
            except Exception:
                pass
        self._script_jobs.clear()
        super().closeEvent(event)


# ═════════════════════════════════════════════════════════════════════════════
# Entry point
# ═════════════════════════════════════════════════════════════════════════════

def show():
    if GiantStepsDialog._instance is not None:
        try:
            GiantStepsDialog._instance.close()
            GiantStepsDialog._instance.deleteLater()
        except Exception:
            pass
    GiantStepsDialog._instance = GiantStepsDialog(parent=_maya_main_window())
    GiantStepsDialog._instance.show()
