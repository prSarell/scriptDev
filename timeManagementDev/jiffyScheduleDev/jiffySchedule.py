# JiffySchedule — Shot list and production schedule tool
# Part of the Jiffy suite for Maya artists

from PySide6 import QtWidgets, QtCore, QtGui
import os
import json
import time
import maya.cmds as cmds
from maya import OpenMayaUI as omui
from shiboken6 import wrapInstance

# ---------------------------------------------------------------------------
# Colour palette — matches JiffyPomo dark scheme
# ---------------------------------------------------------------------------
DARK_BG    = "#1e1e1e"
PANEL_BG   = "#252525"
ITEM_BG    = "#2e2e2e"
ITEM_HOVER = "#363636"
BORDER     = "#444444"
TEXT       = "#ffffff"
SUBTEXT    = "#aaaaaa"

STAGE_COLORS = {
    "Blocking": "#7a93ad",
    "Primary":  "#e0a030",
    "Final":    "#4caf50",
    "Omit":     "#e05050",
}
STAGES = list(STAGE_COLORS.keys())

THUMB_W, THUMB_H = 128, 72   # 16:9

_LIST_STYLE = (
    f"QListWidget{{background:{PANEL_BG};border:none;color:white;outline:none;}}"
    f"QListWidget::item{{padding:8px 12px;border-bottom:1px solid {BORDER};}}"
    f"QListWidget::item:selected{{background:#3a3a3a;color:white;}}"
    f"QListWidget::item:hover{{background:#303030;}}"
)
_MENU_STYLE = (
    f"QMenu{{background:{PANEL_BG};color:white;border:1px solid {BORDER};}}"
    f"QMenu::item:selected{{background:#444;}}"
)


# ---------------------------------------------------------------------------
# Viewport capture helper
# ---------------------------------------------------------------------------
def _capture_viewport(shot_name):
    try:
        root = cmds.workspace(query=True, rootDirectory=True)
        thumb_dir = os.path.join(root, "jiffyShotData", "thumbnails")
        os.makedirs(thumb_dir, exist_ok=True)
        safe   = shot_name.replace(" ", "_").replace("/", "_")
        fname  = f"{safe}_{int(time.time())}.jpg"
        fpath  = os.path.join(thumb_dir, fname).replace("\\", "/")
        cmds.playblast(
            frame=int(cmds.currentTime(q=True)),
            format="image",
            completeFilename=fpath,
            widthHeight=[THUMB_W * 2, THUMB_H * 2],
            percent=100,
            viewer=False,
            showOrnaments=False,
            forceOverwrite=True,
            compression="jpg",
            quality=85,
        )
        if os.path.exists(fpath):
            return fpath
    except Exception as e:
        QtWidgets.QMessageBox.warning(None, "Capture Error", str(e))
    return ""


# ---------------------------------------------------------------------------
# Stage badge — right-click to change stage in-place
# ---------------------------------------------------------------------------
class StageBadge(QtWidgets.QLabel):
    stage_changed = QtCore.Signal(str)

    def __init__(self, stage="Blocking", parent=None):
        super().__init__(parent)
        self.setFixedSize(90, 24)
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu)
        self.set_stage(stage)

    def set_stage(self, stage):
        color = STAGE_COLORS.get(stage, "#888")
        self.setText(stage)
        self.setStyleSheet(
            f"background:{color}; color:white; border-radius:4px;"
            f"font-weight:bold; font-size:11px; padding:2px 6px;"
        )

    def _context_menu(self, pos):
        menu = QtWidgets.QMenu(self)
        menu.setStyleSheet(_MENU_STYLE)
        actions = {menu.addAction(s): s for s in STAGES}
        chosen = menu.exec_(self.mapToGlobal(pos))
        if chosen in actions:
            self.set_stage(actions[chosen])
            self.stage_changed.emit(actions[chosen])


# ---------------------------------------------------------------------------
# Thumbnail — left-click captures viewport, right-click offers recapture/browse
# ---------------------------------------------------------------------------
class ThumbnailLabel(QtWidgets.QLabel):
    capture_requested = QtCore.Signal()
    browse_requested  = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(THUMB_W, THUMB_H)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu)
        self._set_placeholder()

    def _set_placeholder(self):
        self.clear()
        self.setText("Click to Capture")
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setStyleSheet(
            f"background:#333; border:1px solid {BORDER}; color:{SUBTEXT}; font-size:10px;"
        )

    def set_image(self, path):
        if path and os.path.exists(path):
            pix = QtGui.QPixmap(path).scaled(
                THUMB_W, THUMB_H,
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation,
            )
            self.setPixmap(pix)
            self.setAlignment(QtCore.Qt.AlignCenter)
            self.setStyleSheet(f"background:#333; border:1px solid {BORDER};")
        else:
            self._set_placeholder()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.capture_requested.emit()
        super().mousePressEvent(event)

    def _context_menu(self, pos):
        menu = QtWidgets.QMenu(self)
        menu.setStyleSheet(_MENU_STYLE)
        cap_act    = menu.addAction("Recapture from Viewport")
        browse_act = menu.addAction("Browse for Image…")
        action = menu.exec_(self.mapToGlobal(pos))
        if action == cap_act:
            self.capture_requested.emit()
        elif action == browse_act:
            self.browse_requested.emit()


# ---------------------------------------------------------------------------
# Shot row
# ---------------------------------------------------------------------------
class ShotRowWidget(QtWidgets.QFrame):
    edit_requested   = QtCore.Signal(dict)
    delete_requested = QtCore.Signal(str)
    data_changed     = QtCore.Signal(dict)

    def __init__(self, shot_data, parent=None):
        super().__init__(parent)
        self.shot_data = shot_data
        self.setFixedHeight(90)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setStyleSheet(
            f"ShotRowWidget, QFrame{{background:{ITEM_BG};}}"
            f"ShotRowWidget:hover, QFrame:hover{{background:{ITEM_HOVER};}}"
        )
        self._build()
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu)

    def _build(self):
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(10, 8, 14, 8)
        row.setSpacing(14)

        self.thumb = ThumbnailLabel()
        self.thumb.set_image(self.shot_data.get("thumbnail", ""))
        self.thumb.capture_requested.connect(self._do_capture)
        self.thumb.browse_requested.connect(self._do_browse)
        row.addWidget(self.thumb)

        col = QtWidgets.QVBoxLayout()
        col.setSpacing(3)
        self.name_lbl   = QtWidgets.QLabel()
        self.name_lbl.setStyleSheet("font-weight:bold; font-size:13px; color:white;")
        self.frames_lbl = QtWidgets.QLabel()
        self.frames_lbl.setStyleSheet(f"font-size:11px; color:{SUBTEXT};")
        self.due_lbl    = QtWidgets.QLabel()
        self.due_lbl.setStyleSheet(f"font-size:11px; color:{SUBTEXT};")
        self.artist_lbl = QtWidgets.QLabel()
        self.artist_lbl.setStyleSheet(f"font-size:11px; color:{SUBTEXT};")
        for lbl in (self.name_lbl, self.frames_lbl, self.due_lbl, self.artist_lbl):
            col.addWidget(lbl)
        row.addLayout(col, stretch=1)

        self.badge = StageBadge()
        self.badge.stage_changed.connect(self._on_stage_changed)
        row.addWidget(self.badge, alignment=QtCore.Qt.AlignVCenter)

        self._refresh_labels()

    def _refresh_labels(self):
        d = self.shot_data
        self.name_lbl.setText(d.get("name", ""))
        fs, fe = d.get("frame_start", ""), d.get("frame_end", "")
        self.frames_lbl.setText(f"Frames: {fs} – {fe}" if fs or fe else "Frames: —")
        due = d.get("due_date", "")
        self.due_lbl.setText(f"Due: {due}" if due else "Due: —")
        artist = d.get("artist", "")
        self.artist_lbl.setText(f"Artist: {artist}" if artist else "Artist: —")
        self.badge.set_stage(d.get("stage", "Blocking"))
        self.thumb.set_image(d.get("thumbnail", ""))

    def refresh(self, shot_data):
        self.shot_data = shot_data
        self._refresh_labels()

    def _do_capture(self):
        path = _capture_viewport(self.shot_data.get("name", "shot"))
        if path:
            self.shot_data["thumbnail"] = path
            self.thumb.set_image(path)
            self.data_changed.emit(self.shot_data)

    def _do_browse(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select Thumbnail", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff)"
        )
        if path:
            self.shot_data["thumbnail"] = path
            self.thumb.set_image(path)
            self.data_changed.emit(self.shot_data)

    def _on_stage_changed(self, stage):
        self.shot_data["stage"] = stage
        self.data_changed.emit(self.shot_data)

    def _context_menu(self, pos):
        menu = QtWidgets.QMenu(self)
        menu.setStyleSheet(_MENU_STYLE)
        edit_act   = menu.addAction("Edit Shot")
        delete_act = menu.addAction("Delete Shot")
        action = menu.exec_(self.mapToGlobal(pos))
        if action == edit_act:
            self.edit_requested.emit(self.shot_data)
        elif action == delete_act:
            self.delete_requested.emit(self.shot_data.get("name", ""))


# ---------------------------------------------------------------------------
# Add / Edit dialog
# ---------------------------------------------------------------------------
class ShotDialog(QtWidgets.QDialog):
    def __init__(self, shot_data=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Shot" if shot_data is None else "Edit Shot")
        self.setMinimumWidth(340)
        self.setStyleSheet(
            f"QDialog{{background:{DARK_BG};color:white;}}"
            f"QLabel{{color:white;}}"
            f"QLineEdit{{background:{ITEM_BG};color:white;border:1px solid {BORDER};padding:4px;}}"
            f"QComboBox{{background:{ITEM_BG};color:white;border:1px solid {BORDER};padding:4px;}}"
            f"QComboBox QAbstractItemView{{background:{ITEM_BG};color:white;selection-background-color:#444;}}"
            f"QPushButton{{background:#444;color:white;border:1px solid {BORDER};padding:4px 12px;}}"
            f"QPushButton:hover{{background:#555;}}"
        )
        self._data = shot_data.copy() if shot_data else {}
        self._build()

    def _build(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)
        self.name_edit        = QtWidgets.QLineEdit(self._data.get("name", ""))
        self.frame_start_edit = QtWidgets.QLineEdit(str(self._data.get("frame_start", "")))
        self.frame_end_edit   = QtWidgets.QLineEdit(str(self._data.get("frame_end", "")))
        self.due_edit         = QtWidgets.QLineEdit(self._data.get("due_date", ""))
        self.artist_edit      = QtWidgets.QLineEdit(self._data.get("artist", ""))
        self.stage_combo = QtWidgets.QComboBox()
        for s in STAGES:
            self.stage_combo.addItem(s)
        self.stage_combo.setCurrentText(self._data.get("stage", "Blocking"))
        layout.addRow("Shot Name:",   self.name_edit)
        layout.addRow("Frame Start:", self.frame_start_edit)
        layout.addRow("Frame End:",   self.frame_end_edit)
        layout.addRow("Due Date:",    self.due_edit)
        layout.addRow("Artist:",      self.artist_edit)
        layout.addRow("Stage:",       self.stage_combo)
        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def get_data(self):
        return {
            "name":        self.name_edit.text().strip(),
            "frame_start": self.frame_start_edit.text().strip(),
            "frame_end":   self.frame_end_edit.text().strip(),
            "due_date":    self.due_edit.text().strip(),
            "artist":      self.artist_edit.text().strip(),
            "stage":       self.stage_combo.currentText(),
            "thumbnail":   self._data.get("thumbnail", ""),
        }


# ---------------------------------------------------------------------------
# Right panel — scrollable shot rows
# ---------------------------------------------------------------------------
class ShotListPanel(QtWidgets.QWidget):
    data_changed = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.shots     = []
        self._readonly = True
        self._build()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QtWidgets.QWidget()
        header.setFixedHeight(38)
        header.setStyleSheet(f"background:{PANEL_BG}; border-bottom:1px solid {BORDER};")
        hl = QtWidgets.QHBoxLayout(header)
        hl.setContentsMargins(12, 0, 12, 0)
        self.header_lbl = QtWidgets.QLabel("All Shots")
        self.header_lbl.setStyleSheet("font-weight:bold; font-size:13px; color:white;")
        hl.addWidget(self.header_lbl)
        hl.addStretch()
        self.add_btn = QtWidgets.QPushButton("+ Add Shot")
        self.add_btn.setStyleSheet(
            "QPushButton{background:#2e5a2e;color:white;border:none;padding:4px 14px;border-radius:3px;}"
            "QPushButton:hover{background:#3a7a3a;}"
            "QPushButton:disabled{background:#333;color:#666;}"
        )
        self.add_btn.clicked.connect(self._add_shot)
        hl.addWidget(self.add_btn)
        layout.addWidget(header)

        # Column labels
        col_bar = QtWidgets.QWidget()
        col_bar.setFixedHeight(24)
        col_bar.setStyleSheet(f"background:{PANEL_BG}; border-bottom:1px solid {BORDER};")
        cl = QtWidgets.QHBoxLayout(col_bar)
        cl.setContentsMargins(10, 0, 14, 0)
        cl.setSpacing(14)
        for text, w in [("Thumbnail", THUMB_W), ("Shot Details", 0), ("Stage", 90)]:
            lbl = QtWidgets.QLabel(text)
            lbl.setStyleSheet(f"font-size:10px; color:{SUBTEXT};")
            if w:
                lbl.setFixedWidth(w)
                cl.addWidget(lbl)
            else:
                cl.addWidget(lbl, stretch=1)
        layout.addWidget(col_bar)

        # Scroll area
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea{{border:none; background:{DARK_BG};}}")
        self.container = QtWidgets.QWidget()
        self.container.setStyleSheet(f"background:{DARK_BG};")
        self.vbox = QtWidgets.QVBoxLayout(self.container)
        self.vbox.setContentsMargins(0, 0, 0, 0)
        self.vbox.setSpacing(1)
        self.vbox.addStretch()
        scroll.setWidget(self.container)
        layout.addWidget(scroll)

    def set_scene(self, label, shots, readonly=False):
        self.header_lbl.setText(label)
        self.shots     = list(shots)
        self._readonly = readonly
        self.add_btn.setEnabled(not readonly)
        self._rebuild()

    def _rebuild(self):
        while self.vbox.count() > 1:
            item = self.vbox.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for shot in self.shots:
            self._append_row(shot)

    def _append_row(self, shot_data):
        row = ShotRowWidget(shot_data)
        row.edit_requested.connect(self._edit_shot)
        row.delete_requested.connect(self._delete_shot)
        row.data_changed.connect(self._on_row_data_changed)
        self.vbox.insertWidget(self.vbox.count() - 1, row)

    def _add_shot(self):
        scene_path = cmds.file(query=True, sceneName=True)
        scene_name = os.path.splitext(os.path.basename(scene_path))[0] if scene_path else ""
        defaults = {
            "name":        scene_name,
            "frame_start": str(int(cmds.playbackOptions(q=True, minTime=True))),
            "frame_end":   str(int(cmds.playbackOptions(q=True, maxTime=True))),
        }
        dlg = ShotDialog(shot_data=defaults, parent=self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            data = dlg.get_data()
            if data["name"]:
                self.shots.append(data)
                self._append_row(data)
                self.data_changed.emit()

    def _edit_shot(self, shot_data):
        idx = next(
            (i for i, s in enumerate(self.shots) if s.get("name") == shot_data.get("name")),
            None
        )
        if idx is None:
            return
        dlg = ShotDialog(shot_data=shot_data, parent=self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            self.shots[idx] = dlg.get_data()
            self._rebuild()
            self.data_changed.emit()

    def _delete_shot(self, name):
        reply = QtWidgets.QMessageBox.question(
            self, "Delete Shot", f"Delete '{name}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )
        if reply == QtWidgets.QMessageBox.Yes:
            self.shots = [s for s in self.shots if s.get("name") != name]
            self._rebuild()
            self.data_changed.emit()

    def _on_row_data_changed(self, shot_data):
        idx = next(
            (i for i, s in enumerate(self.shots) if s.get("name") == shot_data.get("name")),
            None
        )
        if idx is not None:
            self.shots[idx] = shot_data
        self.data_changed.emit()


# ---------------------------------------------------------------------------
# Left panel — Projects (top) + Scenes (bottom)
# ---------------------------------------------------------------------------
class NavigationPanel(QtWidgets.QWidget):
    project_changed = QtCore.Signal(str)   # "" = All Projects
    scene_changed   = QtCore.Signal(str)   # "" = All Scenes

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(190)
        self.setStyleSheet(f"background:{PANEL_BG};")
        self._build()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Projects section
        layout.addWidget(self._section_header("Projects", self._add_project))
        self.project_list = self._make_list()
        self.project_list.addItem("All Projects")
        self.project_list.setCurrentRow(0)
        self.project_list.currentTextChanged.connect(self._on_project_changed)
        self.project_list.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.project_list.customContextMenuRequested.connect(
            lambda pos: self._list_context_menu(self.project_list, pos, "Project")
        )
        layout.addWidget(self.project_list)

        # Scenes section
        layout.addWidget(self._section_header("Scenes", self._add_scene))
        self.scene_list = self._make_list()
        self.scene_list.addItem("All Scenes")
        self.scene_list.setCurrentRow(0)
        self.scene_list.currentTextChanged.connect(self._on_scene_changed)
        self.scene_list.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.scene_list.customContextMenuRequested.connect(
            lambda pos: self._list_context_menu(self.scene_list, pos, "Scene")
        )
        layout.addWidget(self.scene_list)

    def _section_header(self, title, add_callback):
        h = QtWidgets.QWidget()
        h.setFixedHeight(32)
        h.setStyleSheet(
            f"background:{PANEL_BG}; border-top:1px solid {BORDER}; border-bottom:1px solid {BORDER};"
        )
        hl = QtWidgets.QHBoxLayout(h)
        hl.setContentsMargins(12, 0, 8, 0)
        lbl = QtWidgets.QLabel(title.upper())
        lbl.setStyleSheet(f"font-size:10px; font-weight:bold; color:{SUBTEXT}; letter-spacing:1px;")
        hl.addWidget(lbl)
        hl.addStretch()
        btn = QtWidgets.QPushButton("+")
        btn.setFixedSize(22, 22)
        btn.setStyleSheet(
            "QPushButton{background:#2e5a2e;color:white;border:none;border-radius:3px;font-size:14px;}"
            "QPushButton:hover{background:#3a7a3a;}"
        )
        btn.clicked.connect(add_callback)
        hl.addWidget(btn)
        return h

    def _make_list(self):
        lw = QtWidgets.QListWidget()
        lw.setStyleSheet(_LIST_STYLE)
        return lw

    def _on_project_changed(self, text):
        self.project_changed.emit("" if text == "All Projects" else text)

    def _on_scene_changed(self, text):
        self.scene_changed.emit("" if text == "All Scenes" else text)

    def _add_project(self):
        name, ok = QtWidgets.QInputDialog.getText(self, "Add Project", "Project name:")
        name = name.strip()
        if not (ok and name):
            return
        existing = [self.project_list.item(i).text() for i in range(self.project_list.count())]
        if name in existing:
            QtWidgets.QMessageBox.warning(self, "Add Project", f"'{name}' already exists.")
            return
        self.project_list.addItem(name)
        self.project_list.setCurrentRow(self.project_list.count() - 1)

    def _add_scene(self):
        current = self.project_list.currentItem()
        if not current or current.text() == "All Projects":
            QtWidgets.QMessageBox.warning(self, "Add Scene", "Select a project first.")
            return
        name, ok = QtWidgets.QInputDialog.getText(self, "Add Scene", "Scene name:")
        name = name.strip()
        if not (ok and name):
            return
        existing = [self.scene_list.item(i).text() for i in range(self.scene_list.count())]
        if name in existing:
            QtWidgets.QMessageBox.warning(self, "Add Scene", f"'{name}' already exists.")
            return
        self.scene_list.addItem(name)
        self.scene_list.setCurrentRow(self.scene_list.count() - 1)

    def _list_context_menu(self, list_widget, pos, label):
        item = list_widget.itemAt(pos)
        if not item or item.text() in ("All Projects", "All Scenes"):
            return
        menu = QtWidgets.QMenu(self)
        menu.setStyleSheet(_MENU_STYLE)
        remove_act = menu.addAction(f"Remove {label}")
        action = menu.exec_(list_widget.mapToGlobal(pos))
        if action == remove_act:
            reply = QtWidgets.QMessageBox.question(
                self, f"Remove {label}",
                f"Remove '{item.text()}' and all its contents?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            )
            if reply == QtWidgets.QMessageBox.Yes:
                list_widget.blockSignals(True)
                list_widget.takeItem(list_widget.row(item))
                list_widget.setCurrentRow(0)
                list_widget.blockSignals(False)
                if label == "Project":
                    self.project_changed.emit("")
                else:
                    self.scene_changed.emit("")

    # --- public API ---

    def set_projects(self, projects):
        self.project_list.blockSignals(True)
        while self.project_list.count() > 1:
            self.project_list.takeItem(1)
        for p in projects:
            self.project_list.addItem(p)
        self.project_list.blockSignals(False)

    def set_scenes(self, scenes):
        self.scene_list.blockSignals(True)
        while self.scene_list.count() > 1:
            self.scene_list.takeItem(1)
        for s in scenes:
            self.scene_list.addItem(s)
        self.scene_list.setCurrentRow(0)
        self.scene_list.blockSignals(False)

    def get_projects(self):
        return [
            self.project_list.item(i).text()
            for i in range(self.project_list.count())
            if self.project_list.item(i).text() != "All Projects"
        ]

    def get_scenes(self):
        return [
            self.scene_list.item(i).text()
            for i in range(self.scene_list.count())
            if self.scene_list.item(i).text() != "All Scenes"
        ]


# ---------------------------------------------------------------------------
# Main window
# Data model: _data[project][scene] = [shot_dict, ...]
# ---------------------------------------------------------------------------
class JiffySchedule(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setWindowTitle("JiffySchedule")
        self.resize(960, 720)
        self.setStyleSheet(f"QWidget{{background:{DARK_BG};color:white;}}")

        self._data           = {}
        self._active_project = ""
        self._active_scene   = ""

        self._build()
        self._make_dockable()
        self.load_data()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title_bar = QtWidgets.QWidget()
        title_bar.setFixedHeight(42)
        title_bar.setStyleSheet(f"background:#1a1a1a; border-bottom:1px solid {BORDER};")
        tl = QtWidgets.QHBoxLayout(title_bar)
        tl.setContentsMargins(16, 0, 16, 0)
        lbl = QtWidgets.QLabel("JiffySchedule")
        lbl.setStyleSheet("font-size:17px; font-weight:bold; color:white;")
        tl.addWidget(lbl)
        layout.addWidget(title_bar)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet(f"QSplitter::handle{{background:{BORDER};}}")

        self.nav_panel  = NavigationPanel(self)
        self.shot_panel = ShotListPanel(self)

        splitter.addWidget(self.nav_panel)
        splitter.addWidget(self.shot_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        self.nav_panel.project_changed.connect(self._on_project_changed)
        self.nav_panel.scene_changed.connect(self._on_scene_changed)
        self.shot_panel.data_changed.connect(self._on_data_changed)

        layout.addWidget(splitter)

    # --- navigation ---

    def _flush(self):
        if self._active_project and self._active_scene:
            self._data \
                .setdefault(self._active_project, {}) \
                [self._active_scene] = list(self.shot_panel.shots)

    def _on_project_changed(self, project):
        self._flush()
        self._active_project = project
        self._active_scene   = ""

        if not project:
            all_shots = [s for p in self._data.values() for sc in p.values() for s in sc]
            self.shot_panel.set_scene("All Shots", all_shots, readonly=True)
            self.nav_panel.set_scenes([])
        else:
            scenes = list(self._data.get(project, {}).keys())
            self.nav_panel.set_scenes(scenes)
            all_shots = [s for sc in self._data.get(project, {}).values() for s in sc]
            label = f"{project}  —  All Scenes"
            self.shot_panel.set_scene(label, all_shots, readonly=True)

    def _on_scene_changed(self, scene):
        self._flush()
        self._active_scene = scene

        if not scene:
            if self._active_project:
                all_shots = [s for sc in self._data.get(self._active_project, {}).values() for s in sc]
                self.shot_panel.set_scene(f"{self._active_project}  —  All Scenes", all_shots, readonly=True)
            else:
                all_shots = [s for p in self._data.values() for sc in p.values() for s in sc]
                self.shot_panel.set_scene("All Shots", all_shots, readonly=True)
        else:
            shots = self._data.get(self._active_project, {}).get(scene, [])
            self.shot_panel.set_scene(scene, shots, readonly=False)

    def _on_data_changed(self):
        self._flush()
        self.save_data()

    # --- persistence ---

    def save_data(self):
        projects = self.nav_panel.get_projects()
        scenes   = self.nav_panel.get_scenes()

        for k in list(self._data.keys()):
            if k not in projects:
                del self._data[k]
        for p in projects:
            self._data.setdefault(p, {})
            if p == self._active_project:
                for k in list(self._data[p].keys()):
                    if k not in scenes:
                        del self._data[p][k]
                for s in scenes:
                    self._data[p].setdefault(s, [])

        path = self._save_path()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            payload = {
                "projects": projects,
                "project_scenes": {p: list(self._data.get(p, {}).keys()) for p in projects},
                "data": self._data,
            }
            with open(path + ".tmp", "w") as f:
                json.dump(payload, f, indent=4)
            os.replace(path + ".tmp", path)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Save Error", str(e))

    def load_data(self):
        path = self._save_path()
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    saved = json.load(f)
                data = saved.get("data", {})
                # Discard old flat format {scene: [shots]} — new format is {project: {scene: [shots]}}
                if any(isinstance(v, list) for v in data.values()):
                    data = {}
                self._data = data
                self.nav_panel.set_projects(saved.get("projects", []))
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Load Error", str(e))
        all_shots = [s for p in self._data.values() for sc in p.values() for s in sc]
        self.shot_panel.set_scene("All Shots", all_shots, readonly=True)

    def _save_path(self):
        root = cmds.workspace(query=True, rootDirectory=True)
        return os.path.join(root, "jiffyShotData", "jiffyschedule.json")

    def _make_dockable(self):
        ptr = omui.MQtUtil.mainWindow()
        if ptr:
            maya_win = wrapInstance(int(ptr), QtWidgets.QMainWindow)
            self.setParent(maya_win)
            self.setWindowFlags(QtCore.Qt.Window)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def run_jiffyschedule():
    global _jiffyschedule_window
    try:
        if _jiffyschedule_window and not _jiffyschedule_window.isHidden():
            _jiffyschedule_window.close()
    except (NameError, RuntimeError):
        pass
    _jiffyschedule_window = JiffySchedule()
    _jiffyschedule_window.show()
    _jiffyschedule_window.raise_()
    return _jiffyschedule_window


if __name__ == "__main__":
    run_jiffyschedule()
