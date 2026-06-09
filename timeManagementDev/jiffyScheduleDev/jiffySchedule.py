# JiffySchedule — production schedule and asset tracker
# Part of the Jiffy suite for Maya artists

from PySide6 import QtWidgets, QtCore, QtGui
import os, json, time
import maya.cmds as cmds
from maya import OpenMayaUI as omui
from shiboken6 import wrapInstance

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DARK_BG    = "#1e1e1e"
PANEL_BG   = "#252525"
ITEM_BG    = "#2e2e2e"
ITEM_HOVER = "#363636"
BORDER     = "#444444"
TEXT       = "#ffffff"
SUBTEXT    = "#aaaaaa"

SHOT_STAGES  = ["Blocking", "Primary", "Final", "Rendered", "Omit"]
ASSET_STAGES = ["Blocking", "Primary", "Final", "Omit"]

STAGE_COLORS = {
    "Blocking": "#7a93ad",
    "Primary":  "#e0a030",
    "Final":    "#4caf50",
    "Rendered": "#9575cd",
    "Omit":     "#e05050",
}

THUMB_W, THUMB_H = 128, 72

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
# Viewport capture
# ---------------------------------------------------------------------------
def _capture_viewport(item_name):
    try:
        root = cmds.workspace(query=True, rootDirectory=True)
        thumb_dir = os.path.join(root, "jiffyShotData", "thumbnails")
        os.makedirs(thumb_dir, exist_ok=True)
        safe  = item_name.replace(" ", "_").replace("/", "_")
        fname = f"{safe}_{int(time.time())}.jpg"
        fpath = os.path.join(thumb_dir, fname).replace("\\", "/")
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
# Stage badge
# ---------------------------------------------------------------------------
class StageBadge(QtWidgets.QLabel):
    stage_changed = QtCore.Signal(str)

    def __init__(self, stage="Blocking", stages=None, parent=None):
        super().__init__(parent)
        self._stages = stages or SHOT_STAGES
        self.setFixedSize(90, 24)
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu)
        self.set_stage(stage)

    def set_stage(self, stage):
        if stage not in self._stages:
            stage = self._stages[0]
        color = STAGE_COLORS.get(stage, "#888")
        self.setText(stage)
        self.setStyleSheet(
            f"background:{color}; color:white; border-radius:4px;"
            f"font-weight:bold; font-size:11px; padding:2px 6px;"
        )

    def _context_menu(self, pos):
        menu = QtWidgets.QMenu(self)
        menu.setStyleSheet(_MENU_STYLE)
        actions = {menu.addAction(s): s for s in self._stages}
        chosen = menu.exec_(self.mapToGlobal(pos))
        if chosen in actions:
            self.set_stage(actions[chosen])
            self.stage_changed.emit(actions[chosen])


# ---------------------------------------------------------------------------
# Thumbnail label
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
# Item row
# ---------------------------------------------------------------------------
class ItemRowWidget(QtWidgets.QFrame):
    edit_requested   = QtCore.Signal(dict)
    delete_requested = QtCore.Signal(str)
    data_changed     = QtCore.Signal(dict)

    def __init__(self, item_data, item_label="Shot", stages=None, parent=None):
        super().__init__(parent)
        self.item_data  = item_data
        self.item_label = item_label
        self._stages    = stages or SHOT_STAGES
        self.setFixedHeight(90)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setStyleSheet(
            f"ItemRowWidget, QFrame{{background:{ITEM_BG};}}"
            f"ItemRowWidget:hover, QFrame:hover{{background:{ITEM_HOVER};}}"
        )
        self._build()
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu)

    def _build(self):
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(10, 8, 14, 8)
        row.setSpacing(14)

        self.thumb = ThumbnailLabel()
        self.thumb.set_image(self.item_data.get("thumbnail", ""))
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

        self.badge = StageBadge(stages=self._stages)
        self.badge.stage_changed.connect(self._on_stage_changed)
        row.addWidget(self.badge, alignment=QtCore.Qt.AlignVCenter)

        self._refresh_labels()

    def _refresh_labels(self):
        d = self.item_data
        self.name_lbl.setText(d.get("name", ""))
        fs, fe = d.get("frame_start", ""), d.get("frame_end", "")
        self.frames_lbl.setText(f"Frames: {fs} – {fe}" if fs or fe else "Frames: —")
        due = d.get("due_date", "")
        self.due_lbl.setText(f"Due: {due}" if due else "Due: —")
        artist = d.get("artist", "")
        self.artist_lbl.setText(f"Artist: {artist}" if artist else "Artist: —")
        self.badge.set_stage(d.get("stage", self._stages[0]))
        self.thumb.set_image(d.get("thumbnail", ""))

    def _do_capture(self):
        path = _capture_viewport(self.item_data.get("name", "item"))
        if path:
            self.item_data["thumbnail"] = path
            self.thumb.set_image(path)
            self.data_changed.emit(self.item_data)

    def _do_browse(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select Thumbnail", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff)"
        )
        if path:
            self.item_data["thumbnail"] = path
            self.thumb.set_image(path)
            self.data_changed.emit(self.item_data)

    def _on_stage_changed(self, stage):
        self.item_data["stage"] = stage
        self.data_changed.emit(self.item_data)

    def _context_menu(self, pos):
        menu = QtWidgets.QMenu(self)
        menu.setStyleSheet(_MENU_STYLE)
        edit_act   = menu.addAction(f"Edit {self.item_label}")
        delete_act = menu.addAction(f"Delete {self.item_label}")
        action = menu.exec_(self.mapToGlobal(pos))
        if action == edit_act:
            self.edit_requested.emit(self.item_data)
        elif action == delete_act:
            self.delete_requested.emit(self.item_data.get("name", ""))


# ---------------------------------------------------------------------------
# Item dialog
# ---------------------------------------------------------------------------
class ItemDialog(QtWidgets.QDialog):
    def __init__(self, item_data=None, item_label="Shot", stages=None, parent=None):
        super().__init__(parent)
        self._stages    = stages or SHOT_STAGES
        self.item_label = item_label
        self.setWindowTitle(f"Add {item_label}" if item_data is None else f"Edit {item_label}")
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
        self._data = item_data.copy() if item_data else {}
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
        self.stage_combo      = QtWidgets.QComboBox()
        for s in self._stages:
            self.stage_combo.addItem(s)
        self.stage_combo.setCurrentText(self._data.get("stage", self._stages[0]))
        layout.addRow(f"{self.item_label} Name:", self.name_edit)
        layout.addRow("Frame Start:",             self.frame_start_edit)
        layout.addRow("Frame End:",               self.frame_end_edit)
        layout.addRow("Due Date:",                self.due_edit)
        layout.addRow("Artist:",                  self.artist_edit)
        layout.addRow("Stage:",                   self.stage_combo)
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
# Item list panel — scrollable rows, right pane of the tool
# ---------------------------------------------------------------------------
class ItemListPanel(QtWidgets.QWidget):
    data_changed = QtCore.Signal()

    def __init__(self, item_label="Shot", stages=None, parent=None):
        super().__init__(parent)
        self.item_label = item_label
        self._stages    = stages or SHOT_STAGES
        self.items      = []
        self._build()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QtWidgets.QWidget()
        header.setFixedHeight(38)
        header.setStyleSheet(f"background:{PANEL_BG}; border-bottom:1px solid {BORDER};")
        hl = QtWidgets.QHBoxLayout(header)
        hl.setContentsMargins(12, 0, 12, 0)
        self.header_lbl = QtWidgets.QLabel(f"All {self.item_label}s")
        self.header_lbl.setStyleSheet("font-weight:bold; font-size:13px; color:white;")
        hl.addWidget(self.header_lbl)
        hl.addStretch()
        self.add_btn = QtWidgets.QPushButton(f"+ Add {self.item_label}")
        self.add_btn.setEnabled(False)
        self.add_btn.setStyleSheet(
            "QPushButton{background:#2e5a2e;color:white;border:none;padding:4px 14px;border-radius:3px;}"
            "QPushButton:hover{background:#3a7a3a;}"
            "QPushButton:disabled{background:#333;color:#666;}"
        )
        self.add_btn.clicked.connect(self._add_item)
        hl.addWidget(self.add_btn)
        layout.addWidget(header)

        col_bar = QtWidgets.QWidget()
        col_bar.setFixedHeight(24)
        col_bar.setStyleSheet(f"background:{PANEL_BG}; border-bottom:1px solid {BORDER};")
        cl = QtWidgets.QHBoxLayout(col_bar)
        cl.setContentsMargins(10, 0, 14, 0)
        cl.setSpacing(14)
        for text, w in [("Thumbnail", THUMB_W), (f"{self.item_label} Details", 0), ("Stage", 90)]:
            lbl = QtWidgets.QLabel(text)
            lbl.setStyleSheet(f"font-size:10px; color:{SUBTEXT};")
            if w:
                lbl.setFixedWidth(w)
                cl.addWidget(lbl)
            else:
                cl.addWidget(lbl, stretch=1)
        layout.addWidget(col_bar)

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

    def set_content(self, label, items, writable=False):
        self.header_lbl.setText(label)
        self.items = list(items)
        self.add_btn.setEnabled(writable)
        self._rebuild()

    def _rebuild(self):
        while self.vbox.count() > 1:
            item = self.vbox.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for item in self.items:
            self._append_row(item)

    def _append_row(self, item_data):
        row = ItemRowWidget(item_data, item_label=self.item_label, stages=self._stages)
        row.edit_requested.connect(self._edit_item)
        row.delete_requested.connect(self._delete_item)
        row.data_changed.connect(self._on_row_changed)
        self.vbox.insertWidget(self.vbox.count() - 1, row)

    def _add_item(self):
        defaults = {
            "frame_start": str(int(cmds.playbackOptions(q=True, minTime=True))),
            "frame_end":   str(int(cmds.playbackOptions(q=True, maxTime=True))),
        }
        if self.item_label == "Shot":
            scene_path = cmds.file(query=True, sceneName=True)
            defaults["name"] = os.path.splitext(os.path.basename(scene_path))[0] if scene_path else ""

        dlg = ItemDialog(item_data=defaults, item_label=self.item_label, stages=self._stages, parent=self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            data = dlg.get_data()
            if data["name"]:
                self.items.append(data)
                self._append_row(data)
                self.data_changed.emit()

    def _edit_item(self, item_data):
        idx = next((i for i, s in enumerate(self.items) if s.get("name") == item_data.get("name")), None)
        if idx is None:
            return
        dlg = ItemDialog(item_data=item_data, item_label=self.item_label, stages=self._stages, parent=self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            self.items[idx] = dlg.get_data()
            self._rebuild()
            self.data_changed.emit()

    def _delete_item(self, name):
        reply = QtWidgets.QMessageBox.question(
            self, f"Delete {self.item_label}", f"Delete '{name}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )
        if reply == QtWidgets.QMessageBox.Yes:
            self.items = [s for s in self.items if s.get("name") != name]
            self._rebuild()
            self.data_changed.emit()

    def _on_row_changed(self, item_data):
        idx = next((i for i, s in enumerate(self.items) if s.get("name") == item_data.get("name")), None)
        if idx is not None:
            self.items[idx] = item_data
        self.data_changed.emit()


# ---------------------------------------------------------------------------
# Schedule page — data management + ItemListPanel
# Groups are driven externally via select_group(); NavPanel owns the list UI.
# ---------------------------------------------------------------------------
class SchedulePage(QtWidgets.QWidget):
    data_changed = QtCore.Signal()

    def __init__(self, item_label="Shot", stages=None, parent=None):
        super().__init__(parent)
        self.item_label       = item_label
        self._stages          = stages or SHOT_STAGES
        self._data            = {}   # {project: {group: [items]}}
        self._current_project = ""
        self._active_group    = ""

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.item_panel = ItemListPanel(item_label=item_label, stages=self._stages)
        self.item_panel.data_changed.connect(self._on_items_changed)
        layout.addWidget(self.item_panel)

    # --- called by JiffySchedule ---

    def set_project(self, project):
        self._flush()
        self._current_project = project
        self._active_group    = ""
        self._refresh_view()

    def select_group(self, group):
        self._flush()
        self._active_group = group
        if group:
            self._data.setdefault(self._current_project, {}).setdefault(group, [])
        self._refresh_view()

    def project_added(self, name):
        self._data.setdefault(name, {})

    def project_removed(self, name):
        self._data.pop(name, None)

    def get_groups_for_project(self, project):
        return list(self._data.get(project, {}).keys())

    # --- data ---

    def _flush(self):
        if self._current_project and self._active_group:
            self._data.setdefault(self._current_project, {})[self._active_group] = list(self.item_panel.items)

    def _refresh_view(self):
        proj  = self._current_project
        group = self._active_group
        if not proj:
            items = [i for p in self._data.values() for g in p.values() for i in g]
            self.item_panel.set_content(f"All {self.item_label}s", items, writable=False)
        elif not group:
            items = [i for g in self._data.get(proj, {}).values() for i in g]
            self.item_panel.set_content(f"{proj}  —  All {self.item_label}s", items, writable=False)
        else:
            items = self._data.get(proj, {}).get(group, [])
            self.item_panel.set_content(group, items, writable=True)

    def _on_items_changed(self):
        self._flush()
        self.data_changed.emit()

    def get_data(self):
        self._flush()
        return dict(self._data)

    def load_data(self, data):
        if any(isinstance(v, list) for v in data.values()):
            data = {}
        self._data = data
        self._refresh_view()


# ---------------------------------------------------------------------------
# NavPanel — Projects (top) + Groups (bottom) stacked in one left panel.
# The groups section label and content change when the active tab switches.
# ---------------------------------------------------------------------------
class NavPanel(QtWidgets.QWidget):
    project_changed = QtCore.Signal(str)   # "" = All Projects
    project_added   = QtCore.Signal(str)
    project_removed = QtCore.Signal(str)
    group_changed   = QtCore.Signal(str)   # "" = All Groups
    group_added     = QtCore.Signal(str)
    group_removed   = QtCore.Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._group_label = "Scene"
        self.setFixedWidth(170)
        self.setStyleSheet(f"background:{PANEL_BG};")
        self._build()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- Projects section ---
        layout.addWidget(self._make_section_header("PROJECTS", self._add_project, store_lbl=False))
        self.project_list = self._make_list()
        self.project_list.addItem("All Projects")
        self.project_list.setCurrentRow(0)
        self.project_list.currentTextChanged.connect(
            lambda t: self.project_changed.emit("" if t == "All Projects" else (t or ""))
        )
        self.project_list.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.project_list.customContextMenuRequested.connect(
            lambda pos: self._list_ctx(self.project_list, pos, "Project")
        )
        layout.addWidget(self.project_list)

        # --- Groups section ---
        self._group_section_hdr = self._make_section_header("SCENES", self._add_group, store_lbl=True)
        layout.addWidget(self._group_section_hdr)
        self.group_list = self._make_list()
        self.group_list.addItem("All Scenes")
        self.group_list.setCurrentRow(0)
        self.group_list.currentTextChanged.connect(self._on_group_text_changed)
        self.group_list.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.group_list.customContextMenuRequested.connect(
            lambda pos: self._list_ctx(self.group_list, pos, self._group_label)
        )
        layout.addWidget(self.group_list)

    def _make_section_header(self, title, add_cb, store_lbl=False):
        h = QtWidgets.QWidget()
        h.setFixedHeight(32)
        h.setStyleSheet(
            f"background:{PANEL_BG}; border-top:1px solid {BORDER}; border-bottom:1px solid {BORDER};"
        )
        hl = QtWidgets.QHBoxLayout(h)
        hl.setContentsMargins(12, 0, 8, 0)
        lbl = QtWidgets.QLabel(title)
        lbl.setStyleSheet(f"font-size:10px; font-weight:bold; color:{SUBTEXT}; letter-spacing:1px;")
        hl.addWidget(lbl)
        hl.addStretch()
        btn = QtWidgets.QPushButton("+")
        btn.setFixedSize(22, 22)
        btn.setStyleSheet(
            "QPushButton{background:#2e5a2e;color:white;border:none;border-radius:3px;font-size:14px;}"
            "QPushButton:hover{background:#3a7a3a;}"
            "QPushButton:disabled{background:#333;color:#555;}"
        )
        btn.clicked.connect(add_cb)
        hl.addWidget(btn)
        if store_lbl:
            self._group_header_lbl = lbl
            self._group_add_btn    = btn
            btn.setEnabled(False)
        return h

    def _make_list(self):
        lw = QtWidgets.QListWidget()
        lw.setStyleSheet(_LIST_STYLE)
        return lw

    def _on_group_text_changed(self, t):
        all_text = f"All {self._group_label}s"
        self.group_changed.emit("" if t == all_text else (t or ""))

    # --- public API ---

    def set_groups(self, groups, group_label="Scene", enabled=True):
        self._group_label = group_label
        self._group_header_lbl.setText(f"{group_label.upper()}S")
        self._group_add_btn.setEnabled(enabled)

        all_text = f"All {group_label}s"
        self.group_list.blockSignals(True)
        self.group_list.clear()
        self.group_list.addItem(all_text)
        for g in groups:
            self.group_list.addItem(g)
        self.group_list.setCurrentRow(0)
        self.group_list.blockSignals(False)

    def get_groups(self):
        all_text = f"All {self._group_label}s"
        return [
            self.group_list.item(i).text()
            for i in range(self.group_list.count())
            if self.group_list.item(i).text() != all_text
        ]

    def set_projects(self, projects):
        self.project_list.blockSignals(True)
        self.project_list.clear()
        self.project_list.addItem("All Projects")
        for p in projects:
            self.project_list.addItem(p)
        self.project_list.setCurrentRow(0)
        self.project_list.blockSignals(False)

    def get_projects(self):
        return [
            self.project_list.item(i).text()
            for i in range(self.project_list.count())
            if self.project_list.item(i).text() != "All Projects"
        ]

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
        self.project_added.emit(name)
        self.project_list.setCurrentRow(self.project_list.count() - 1)

    def _add_group(self):
        name, ok = QtWidgets.QInputDialog.getText(
            self, f"Add {self._group_label}", f"{self._group_label} name:"
        )
        name = name.strip()
        if not (ok and name):
            return
        existing = [self.group_list.item(i).text() for i in range(self.group_list.count())]
        if name in existing:
            QtWidgets.QMessageBox.warning(self, f"Add {self._group_label}", f"'{name}' already exists.")
            return
        self.group_list.addItem(name)
        self.group_added.emit(name)
        self.group_list.setCurrentRow(self.group_list.count() - 1)

    def _list_ctx(self, list_widget, pos, label):
        item = list_widget.itemAt(pos)
        all_text = "All Projects" if label == "Project" else f"All {self._group_label}s"
        if not item or item.text() == all_text:
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
                name = item.text()
                list_widget.blockSignals(True)
                list_widget.takeItem(list_widget.row(item))
                list_widget.setCurrentRow(0)
                list_widget.blockSignals(False)
                if label == "Project":
                    self.project_removed.emit(name)
                    self.project_changed.emit("")
                else:
                    self.group_removed.emit(name)
                    self.group_changed.emit("")


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------
class JiffySchedule(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setWindowTitle("JiffySchedule")
        self.resize(1080, 720)
        self.setStyleSheet(f"QWidget{{background:{DARK_BG};color:white;}}")
        self._active_project = ""
        self._build()
        self._make_dockable()
        self.load_data()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Title bar — "JiffySchedule"  Shots  Assets  (all on one line)
        title_bar = QtWidgets.QWidget()
        title_bar.setFixedHeight(42)
        title_bar.setStyleSheet(f"background:#1a1a1a; border-bottom:1px solid {BORDER};")
        tl = QtWidgets.QHBoxLayout(title_bar)
        tl.setContentsMargins(16, 0, 0, 0)
        tl.setSpacing(0)

        name_lbl = QtWidgets.QLabel("JiffySchedule")
        name_lbl.setStyleSheet("font-size:17px; font-weight:bold; color:white;")
        tl.addWidget(name_lbl)
        tl.addSpacing(24)

        self.tab_bar = QtWidgets.QTabBar()
        self.tab_bar.addTab("Shots")
        self.tab_bar.addTab("Assets")
        self.tab_bar.setStyleSheet(
            "QTabBar{background:transparent;}"
            f"QTabBar::tab{{background:transparent;color:{SUBTEXT};padding:0 20px;"
            f"height:42px;border:none;border-bottom:2px solid transparent;font-size:13px;}}"
            "QTabBar::tab:selected{color:white;border-bottom:2px solid #4caf50;}"
            "QTabBar::tab:hover{color:white;}"
        )
        self.tab_bar.currentChanged.connect(self._on_tab_changed)
        tl.addWidget(self.tab_bar)
        tl.addStretch()
        layout.addWidget(title_bar)

        # Body — NavPanel (left) + stacked pages (right)
        body = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        body.setHandleWidth(1)
        body.setStyleSheet(f"QSplitter::handle{{background:{BORDER};}}")

        self.nav = NavPanel()
        self.nav.project_changed.connect(self._on_project_changed)
        self.nav.project_added.connect(self._on_project_added)
        self.nav.project_removed.connect(self._on_project_removed)
        self.nav.group_changed.connect(self._on_group_changed)
        self.nav.group_added.connect(self._on_group_added)
        self.nav.group_removed.connect(self._on_group_removed)

        self.shots_page  = SchedulePage(item_label="Shot",  stages=SHOT_STAGES)
        self.assets_page = SchedulePage(item_label="Asset", stages=ASSET_STAGES)
        self.shots_page.data_changed.connect(self.save_data)
        self.assets_page.data_changed.connect(self.save_data)

        self.stack = QtWidgets.QStackedWidget()
        self.stack.addWidget(self.shots_page)
        self.stack.addWidget(self.assets_page)

        body.addWidget(self.nav)
        body.addWidget(self.stack)
        body.setStretchFactor(0, 0)
        body.setStretchFactor(1, 1)
        layout.addWidget(body)

    def _active_page(self):
        return self.shots_page if self.tab_bar.currentIndex() == 0 else self.assets_page

    def _group_label_for_tab(self, index):
        return "Scene" if index == 0 else "Asset"

    def _on_tab_changed(self, index):
        self.stack.setCurrentIndex(index)
        page  = self._active_page()
        label = self._group_label_for_tab(index)
        groups  = page.get_groups_for_project(self._active_project)
        enabled = bool(self._active_project)
        self.nav.set_groups(groups, group_label=label, enabled=enabled)
        page.select_group("")

    def _on_project_changed(self, project):
        self._active_project = project
        self.shots_page.set_project(project)
        self.assets_page.set_project(project)
        label   = self._group_label_for_tab(self.tab_bar.currentIndex())
        groups  = self._active_page().get_groups_for_project(project)
        enabled = bool(project)
        self.nav.set_groups(groups, group_label=label, enabled=enabled)

    def _on_project_added(self, name):
        self.shots_page.project_added(name)
        self.assets_page.project_added(name)
        self.save_data()

    def _on_project_removed(self, name):
        self.shots_page.project_removed(name)
        self.assets_page.project_removed(name)
        self.save_data()

    def _on_group_changed(self, group):
        self._active_page().select_group(group)

    def _on_group_added(self, name):
        self._active_page().project_added(self._active_project)  # ensure slot exists
        self._active_page().select_group(name)
        self.save_data()

    def _on_group_removed(self, name):
        page = self._active_page()
        page._data.get(self._active_project, {}).pop(name, None)
        page.select_group("")
        self.save_data()

    def save_data(self):
        path = self._save_path()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            payload = {
                "projects": self.nav.get_projects(),
                "shots":    self.shots_page.get_data(),
                "assets":   self.assets_page.get_data(),
            }
            with open(path + ".tmp", "w") as f:
                json.dump(payload, f, indent=4)
            os.replace(path + ".tmp", path)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Save Error", str(e))

    def load_data(self):
        path = self._save_path()
        if not os.path.exists(path):
            return
        try:
            with open(path, "r") as f:
                saved = json.load(f)

            # Migrate: old format had "data"/"projects" inside "shots"
            if "shots" in saved and isinstance(saved["shots"], dict) and "data" in saved["shots"]:
                saved = {
                    "projects": saved["shots"].get("projects", []),
                    "shots":    saved["shots"].get("data", {}),
                    "assets":   saved.get("assets", {}).get("data", {})
                        if isinstance(saved.get("assets"), dict) else {},
                }
            elif "data" in saved and "shots" not in saved:
                saved = {
                    "projects": saved.get("projects", []),
                    "shots":    saved.get("data", {}),
                    "assets":   {},
                }

            projects = saved.get("projects", [])
            self.nav.set_projects(projects)
            for p in projects:
                self.shots_page.project_added(p)
                self.assets_page.project_added(p)
            self.shots_page.load_data(saved.get("shots", {}))
            self.assets_page.load_data(saved.get("assets", {}))
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Load Error", str(e))

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
