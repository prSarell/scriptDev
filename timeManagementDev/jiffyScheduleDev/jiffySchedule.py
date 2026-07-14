# JiffySchedule — production schedule and asset tracker
# Part of the Jiffy suite for Maya artists

# ---------------------------------------------------------------------------
# MULTI-USER NOTE (2026-06-14)
# For a small team (e.g. 3 people), shared access can be achieved by pointing
# all users' Maya projects to the same shared folder (OneDrive, network drive,
# etc.) — they will all read/write the same jiffyschedule.json automatically.
# No team size or member list needs to be defined.
#
# Risk: last-save-wins if two people save simultaneously.
# Options considered:
#   1. Convention — agree to coordinate via chat before editing (zero code, fine for small teams)
#   2. Lock file — write jiffyschedule.lock with name + timestamp on open/save;
#                  warn others that someone is currently editing
#   3. Timestamp log — append who saved and when; collisions are visible after the fact
#
# A Reload button would also help — lets users pull latest from disk without
# closing the tool. Decide on collision strategy before implementing.
# ---------------------------------------------------------------------------

from PySide6 import QtWidgets, QtCore, QtGui
import os, json, time
from datetime import date as _date, datetime as _datetime, timedelta as _timedelta
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

_DATA_DIR_PREF = "jiffyScheduleDataDir"

SHOT_STAGES  = ["Previs", "Blocking", "Primary", "Final", "Rendered", "Omit"]
ASSET_STAGES = ["WIP", "Testing", "Production Ready", "Omit"]

STAGE_COLORS = {
    "Previs":           "#607d8b",
    "Blocking":         "#7a93ad",
    "Primary":          "#e0a030",
    "Final":            "#4caf50",
    "Rendered":         "#9575cd",
    "Omit":             "#e05050",
    "WIP":              "#7a93ad",
    "Testing":          "#e0a030",
    "Production Ready": "#4caf50",
}

THUMB_W, THUMB_H = 128, 72
_ITEM_MIME = "application/x-jiffy-item"

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
# Date helpers  (DD-MM-YYYY throughout the tool)
# ---------------------------------------------------------------------------
def _parse_dmy(s):
    """Parse a date string → date, accepts DD-MM-YYYY, DD/MM/YYYY, or YYYY-MM-DD."""
    if not s or not s.strip():
        return None
    s = s.strip()
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return _datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None

def _today_dmy():
    return _date.today().strftime("%d-%m-%Y")

def _proximity_badge(due_str):
    """Return (text, color_hex) countdown badge for a DD-MM-YYYY due date."""
    d = _parse_dmy(due_str)
    if d is None:
        return "—", SUBTEXT
    days = (d - _date.today()).days
    if days < 0:   return "OVERDUE",      "#e05050"
    if days == 0:  return "TODAY",        "#e05050"
    if days <= 7:  return f"{days}d  ⚠",  "#e0a030"
    if days <= 30: return f"{days}d",     "#c8a000"
    return f"{days}d",                    "#4a7a4a"

def _prod_week(target, w1_start, hol_start=None, hol_end=None):
    """
    Production week number for *target* (date), counting from w1_start (date).
    Holiday period [hol_start, hol_end] is excluded from the week count.
    Returns None if w1_start is None or target < w1_start.
    """
    if w1_start is None or target < w1_start:
        return None
    days = (target - w1_start).days
    if hol_start and hol_end and hol_start <= hol_end:
        ov_s = max(w1_start, hol_start)
        ov_e = min(target,   hol_end)
        if ov_e >= ov_s:
            days -= (ov_e - ov_s).days + 1
    return max(1, days // 7 + 1) if days >= 0 else None


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

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            menu = QtWidgets.QMenu(self)
            menu.setStyleSheet(_MENU_STYLE)
            actions = {menu.addAction(s): s for s in self._stages}
            chosen = menu.exec_(self.mapToGlobal(event.pos()))
            if chosen in actions:
                self.set_stage(actions[chosen])
                self.stage_changed.emit(actions[chosen])
        super().mousePressEvent(event)


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
        self._drag_start = None
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
        row.setContentsMargins(4, 8, 14, 8)
        row.setSpacing(14)

        self._handle = QtWidgets.QLabel("⠿")
        self._handle.setFixedWidth(16)
        self._handle.setAlignment(QtCore.Qt.AlignCenter)
        self._handle.setStyleSheet(f"color:{SUBTEXT}; font-size:16px;")
        self._handle.setCursor(QtCore.Qt.SizeVerCursor)
        self._handle.installEventFilter(self)
        row.addWidget(self._handle)

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

    def eventFilter(self, obj, event):
        if obj is self._handle:
            t = event.type()
            if t == QtCore.QEvent.MouseButtonPress and event.button() == QtCore.Qt.LeftButton:
                self._drag_start = QtCore.QPoint(event.pos())
                return True
            if t == QtCore.QEvent.MouseMove and self._drag_start is not None:
                if (event.pos() - self._drag_start).manhattanLength() >= QtWidgets.QApplication.startDragDistance():
                    self._start_drag(self._handle.mapTo(self, event.pos()))
                    self._drag_start = None
                return True
            if t == QtCore.QEvent.MouseButtonRelease:
                self._drag_start = None
        return super().eventFilter(obj, event)

    def _start_drag(self, hotspot):
        drag = QtGui.QDrag(self)
        mime = QtCore.QMimeData()
        mime.setData(_ITEM_MIME, QtCore.QByteArray(self.item_data.get("name", "").encode()))
        drag.setMimeData(mime)
        drag.setPixmap(self.grab())
        drag.setHotSpot(hotspot)
        drag.exec_(QtCore.Qt.MoveAction)

    def _refresh_labels(self):
        d = self.item_data
        self.name_lbl.setText(d.get("name", ""))
        fs, fe = d.get("frame_start", ""), d.get("frame_end", "")
        self.frames_lbl.setText(f"Frames: {fs} – {fe}" if fs or fe else "")
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
        self._is_new    = item_data is None
        self.setWindowTitle(f"Add {item_label}" if self._is_new else f"Edit {item_label}")
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
        default_due = self._data.get("due_date", _today_dmy())
        self.due_edit    = QtWidgets.QLineEdit(default_due)
        self.due_edit.setPlaceholderText("DD-MM-YYYY")
        self.artist_edit = QtWidgets.QLineEdit(self._data.get("artist", ""))
        self.stage_combo = QtWidgets.QComboBox()
        for s in self._stages:
            self.stage_combo.addItem(s)
        self.stage_combo.setCurrentText(self._data.get("stage", self._stages[0]))
        layout.addRow(f"{self.item_label} Name:", self.name_edit)
        if self.item_label != "Asset":
            layout.addRow("Frame Start:", self.frame_start_edit)
            layout.addRow("Frame End:",   self.frame_end_edit)
        layout.addRow("Due Date:",  self.due_edit)
        layout.addRow("Artist:",    self.artist_edit)
        layout.addRow("Stage:",     self.stage_combo)
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
# Drop container — used by ItemListPanel for drag-to-reorder
# ---------------------------------------------------------------------------
class _InsertLine(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        self.setFixedHeight(2)
        self.hide()

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.fillRect(self.rect(), QtGui.QColor("#4caf50"))
        p.end()


class _DropContainer(QtWidgets.QWidget):
    drop_performed = QtCore.Signal(str, int)  # (item_name, target_index)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._line = _InsertLine(self)

    def _gap_at(self, y):
        """Return (line_y, insert_index) for the gap nearest to y."""
        layout = self.layout()
        if layout is None:
            return 0, 0
        count = layout.count() - 1  # last item is stretch
        for i in range(count):
            w = layout.itemAt(i).widget()
            if w and y < w.y() + w.height() // 2:
                return w.y(), i
        last = layout.itemAt(count - 1).widget() if count > 0 else None
        end_y = (last.y() + last.height()) if last else y
        return end_y, count

    def _show_line(self, y):
        self._line.setGeometry(0, max(0, y - 1), self.width(), 2)
        self._line.show()
        self._line.raise_()

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(_ITEM_MIME):
            line_y, _ = self._gap_at(event.pos().y())
            self._show_line(line_y)
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat(_ITEM_MIME):
            line_y, _ = self._gap_at(event.pos().y())
            self._show_line(line_y)
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self._line.hide()

    def dropEvent(self, event):
        if event.mimeData().hasFormat(_ITEM_MIME):
            name = bytes(event.mimeData().data(_ITEM_MIME)).decode()
            _, target_idx = self._gap_at(event.pos().y())
            self._line.hide()
            self.drop_performed.emit(name, target_idx)
            event.acceptProposedAction()


# ---------------------------------------------------------------------------
# Item list panel
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
        self.container = _DropContainer()
        self.container.setStyleSheet(f"background:{DARK_BG};")
        self.container.drop_performed.connect(self._on_drop)
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
        defaults = {}
        if self.item_label == "Shot":
            defaults["frame_start"] = str(int(cmds.playbackOptions(q=True, minTime=True)))
            defaults["frame_end"]   = str(int(cmds.playbackOptions(q=True, maxTime=True)))
            scene_path = cmds.file(query=True, sceneName=True)
            defaults["name"] = os.path.splitext(os.path.basename(scene_path))[0] if scene_path else ""

        dlg = ItemDialog(item_data=defaults if defaults else None,
                         item_label=self.item_label, stages=self._stages, parent=self)
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

    def _on_drop(self, name, target_idx):
        src_idx = next((i for i, s in enumerate(self.items) if s.get("name") == name), None)
        if src_idx is None or src_idx == target_idx:
            return
        item = self.items.pop(src_idx)
        if target_idx > src_idx:
            target_idx -= 1
        self.items.insert(target_idx, item)
        self._rebuild()
        self.data_changed.emit()


# ---------------------------------------------------------------------------
# Schedule page — data management + ItemListPanel
# ---------------------------------------------------------------------------
class SchedulePage(QtWidgets.QWidget):
    data_changed = QtCore.Signal()

    def __init__(self, item_label="Shot", stages=None, parent=None):
        super().__init__(parent)
        self.item_label       = item_label
        self._stages          = stages or SHOT_STAGES
        self._data            = {}
        self._current_project = ""
        self._active_group    = ""

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.item_panel = ItemListPanel(item_label=item_label, stages=self._stages)
        self.item_panel.data_changed.connect(self._on_items_changed)
        layout.addWidget(self.item_panel)

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
        if self._current_project == name:
            self._current_project = ""
            self._active_group = ""
        self._data.pop(name, None)

    def get_groups_for_project(self, project):
        return list(self._data.get(project, {}).keys())

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
# Pie chart — donut style, % complete in centre
# ---------------------------------------------------------------------------
class PieChartWidget(QtWidgets.QWidget):
    def __init__(self, title="", complete_stages=None, parent=None):
        super().__init__(parent)
        self.title           = title
        self.complete_stages = complete_stages or []
        self._counts         = {}
        self.setFixedSize(200, 220)

    def set_data(self, counts):
        self._counts = {k: v for k, v in counts.items() if v > 0}
        self.update()

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        side = 172
        cx, cy = self.width() / 2, side / 2 + 4
        cr = QtCore.QRectF(cx - side / 2, cy - side / 2, side, side)
        total = sum(self._counts.values())
        if total == 0:
            p.setPen(QtGui.QColor(BORDER))
            p.setBrush(QtGui.QColor("#333"))
            p.drawEllipse(cr)
            p.setPen(QtGui.QColor(SUBTEXT))
            p.drawText(cr, QtCore.Qt.AlignCenter, "No data")
        else:
            start = 90 * 16
            for stage, count in self._counts.items():
                span = max(1, int(round(count / total * 360 * 16)))
                p.setBrush(QtGui.QColor(STAGE_COLORS.get(stage, "#888")))
                p.setPen(QtCore.Qt.NoPen)
                p.drawPie(cr, start, -span)
                start -= span
            hole = side * 0.44
            hr = QtCore.QRectF(cx - hole / 2, cy - hole / 2, hole, hole)
            p.setBrush(QtGui.QColor(DARK_BG))
            p.setPen(QtCore.Qt.NoPen)
            p.drawEllipse(hr)
            complete = sum(v for k, v in self._counts.items() if k in self.complete_stages)
            pct = int(complete / total * 100)
            f = QtGui.QFont()
            f.setBold(True)
            f.setPixelSize(22)
            p.setFont(f)
            p.setPen(QtGui.QColor(TEXT))
            p.drawText(hr, QtCore.Qt.AlignCenter, f"{pct}%")
        if self.title:
            tr = QtCore.QRectF(0, side + 10, self.width(), 20)
            f2 = QtGui.QFont()
            f2.setPixelSize(11)
            p.setFont(f2)
            p.setPen(QtGui.QColor(SUBTEXT))
            p.drawText(tr, QtCore.Qt.AlignCenter, self.title)
        p.end()


# ---------------------------------------------------------------------------
# Milestone dialog — DD-MM-YYYY, today default, optional extension note
# ---------------------------------------------------------------------------
class MilestoneDialog(QtWidgets.QDialog):
    def __init__(self, data=None, prod_settings=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Milestone" if data is None else "Edit Milestone")
        self.setMinimumWidth(340)
        self.setStyleSheet(
            f"QDialog{{background:{DARK_BG};color:white;}}"
            f"QLabel{{color:white;}}"
            f"QLineEdit{{background:{ITEM_BG};color:white;border:1px solid {BORDER};padding:4px;}}"
            f"QPushButton{{background:#444;color:white;border:1px solid {BORDER};padding:4px 12px;}}"
            f"QPushButton:hover{{background:#555;}}"
        )
        self._data = data.copy() if data else {}
        self._is_new = data is None
        self._prod_settings = prod_settings or {}
        self._build()

    def _build(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)
        self.name_edit = QtWidgets.QLineEdit(self._data.get("name", ""))
        default_date = self._data.get("due_date", "")
        self.date_edit = QtWidgets.QLineEdit(default_date)
        self.date_edit.setPlaceholderText("DD-MM-YYYY or W8")
        layout.addRow("Milestone:", self.name_edit)
        layout.addRow("Due Date:",  self.date_edit)
        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def get_data(self):
        raw = self.date_edit.text().strip()
        if raw and _parse_dmy(raw) is None:
            raw = self._week_input_to_date(raw)
        return {
            "name":     self.name_edit.text().strip(),
            "due_date": raw,
        }

    def _week_input_to_date(self, s):
        """Convert 'W8' or '8' to DD-MM-YYYY using production settings. Returns s unchanged if it can't."""
        w1 = _parse_dmy(self._prod_settings.get("week1_start", ""))
        if w1 is None:
            return s
        token = s.strip().upper().lstrip("W")
        try:
            wk = int(token)
        except ValueError:
            return s
        return (w1 + _timedelta(days=7 * (wk - 1))).strftime("%d-%m-%Y")


# ---------------------------------------------------------------------------
# Production schedule settings dialog (opened by clicking the week number)
# ---------------------------------------------------------------------------
class _ProductionSettingsDialog(QtWidgets.QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Production Schedule Settings")
        self.setMinimumWidth(360)
        self.setStyleSheet(
            f"QDialog{{background:{DARK_BG};color:white;}}"
            f"QLabel{{color:white;}}"
            f"QLineEdit{{background:{ITEM_BG};color:white;border:1px solid {BORDER};"
            f"padding:5px;font-size:12px;border-radius:3px;}}"
            f"QSpinBox{{background:{ITEM_BG};color:white;border:1px solid {BORDER};"
            f"padding:5px;font-size:12px;border-radius:3px;}}"
            f"QPushButton{{background:#444;color:white;border:1px solid {BORDER};padding:5px 14px;}}"
            f"QPushButton:hover{{background:#555;}}"
        )
        self._settings = settings
        self._build()

    def _build(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setLabelAlignment(QtCore.Qt.AlignRight)

        self.week1_edit = QtWidgets.QLineEdit(self._settings.get("week1_start", "") or _today_dmy())
        self.week1_edit.setPlaceholderText("DD-MM-YYYY  or  YYYY-MM-DD")

        self.total_weeks_edit = QtWidgets.QLineEdit(str(self._settings.get("total_weeks", 12)))
        self.total_weeks_edit.setValidator(QtGui.QIntValidator(1, 52))

        self.hol_start_edit = QtWidgets.QLineEdit(self._settings.get("holiday_start", ""))
        self.hol_start_edit.setPlaceholderText("DD-MM-YYYY  or  YYYY-MM-DD  (optional)")
        self.hol_end_edit   = QtWidgets.QLineEdit(self._settings.get("holiday_end", ""))
        self.hol_end_edit.setPlaceholderText("DD-MM-YYYY  or  YYYY-MM-DD  (optional)")

        layout.addRow("Week 1 Start:",  self.week1_edit)
        layout.addRow("Total Weeks:",   self.total_weeks_edit)

        sep_lbl = QtWidgets.QLabel("Mid-term break")
        sep_lbl.setStyleSheet(
            f"font-size:10px; font-weight:bold; color:{SUBTEXT}; letter-spacing:1px; padding-top:6px;"
        )
        layout.addRow("", sep_lbl)
        layout.addRow("Break Start:",   self.hol_start_edit)
        layout.addRow("Break End:",     self.hol_end_edit)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def get_data(self):
        return {
            "week1_start":   self.week1_edit.text().strip(),
            "total_weeks":   int(self.total_weeks_edit.text() or "12"),
            "holiday_start": self.hol_start_edit.text().strip(),
            "holiday_end":   self.hol_end_edit.text().strip(),
        }


# ---------------------------------------------------------------------------
# Week timeline bar — drawn with paintEvent
# ---------------------------------------------------------------------------
class _WeekTimelineWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._settings = {}
        self._milestones = []
        self.setMinimumHeight(100)

    def set_settings(self, settings, milestones=None):
        self._settings = settings
        self._milestones = milestones or []
        self.update()

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)

        s    = self._settings
        w1   = _parse_dmy(s.get("week1_start", ""))
        tw   = s.get("total_weeks", 12)
        hs   = _parse_dmy(s.get("holiday_start", ""))
        he   = _parse_dmy(s.get("holiday_end", ""))
        curr = _prod_week(_date.today(), w1, hs, he)

        if w1 is None:
            f = QtGui.QFont()
            f.setPixelSize(11)
            p.setFont(f)
            p.setPen(QtGui.QColor(SUBTEXT))
            p.drawText(
                self.rect(), QtCore.Qt.AlignCenter,
                "Click the week number  ▶  to set up your production schedule"
            )
            p.end()
            return

        # Determine break position (0-based index: insert break BEFORE slot break_slot)
        has_break  = hs is not None and he is not None
        break_slot = None
        if has_break:
            days_to_hol = max(0, (hs - w1).days)
            break_slot  = min(days_to_hol // 7, tw)  # insert break before week (break_slot+1)

        # Build draw list: each entry is ('week', week_num) or ('break',)
        draw_list = []
        for wk in range(1, tw + 1):
            if has_break and break_slot == wk - 1 and wk > 1:
                draw_list.append(("break",))
            draw_list.append(("week", wk))
        # if break is before week 1 (start of semester) still insert at front
        if has_break and break_slot == 0:
            draw_list.insert(0, ("break",))

        n_slots    = len(draw_list)
        ms_strip_h = 18
        margin_x   = 14
        margin_y   = 6
        label_h    = 24
        usable_w   = self.width() - 2 * margin_x
        avail_h    = self.height() - ms_strip_h - 2 * margin_y - label_h
        box_h      = min(avail_h, 28)
        box_y      = ms_strip_h + margin_y + (avail_h - box_h) / 2
        slot_w     = usable_w / n_slots if n_slots else usable_w

        for idx, item in enumerate(draw_list):
            sx = margin_x + idx * slot_w
            bw = max(1.0, slot_w - 3)

            if item[0] == "break":
                p.setBrush(QtGui.QColor("#2a2a2a"))
                p.setPen(QtCore.Qt.NoPen)
                p.drawRoundedRect(QtCore.QRectF(sx + 1.5, box_y, bw, box_h), 3, 3)
                f = QtGui.QFont()
                f.setPixelSize(8)
                p.setFont(f)
                p.setPen(QtGui.QColor(SUBTEXT))
                p.drawText(
                    QtCore.QRectF(sx, box_y, slot_w, box_h),
                    QtCore.Qt.AlignCenter, "BRK"
                )
                p.drawText(
                    QtCore.QRectF(sx, box_y + box_h + 2, slot_w, label_h),
                    QtCore.Qt.AlignCenter, "break"
                )
            else:
                wk      = item[1]
                is_curr = curr is not None and wk == curr
                bg  = QtGui.QColor("#484848") if is_curr else QtGui.QColor("#303030")
                fg  = QtGui.QColor("white")

                p.setBrush(bg)
                p.setPen(QtCore.Qt.NoPen)
                p.drawRoundedRect(QtCore.QRectF(sx + 1.5, box_y, bw, box_h), 3, 3)

                if is_curr:
                    p.setBrush(QtCore.Qt.NoBrush)
                    p.setPen(QtGui.QPen(QtGui.QColor("white"), 1.5))
                    p.drawRoundedRect(QtCore.QRectF(sx + 1.5, box_y, bw, box_h), 3, 3)

                f = QtGui.QFont()
                f.setPixelSize(11)
                f.setBold(is_curr)
                p.setFont(f)
                p.setPen(fg)
                p.drawText(
                    QtCore.QRectF(sx, box_y, slot_w, box_h),
                    QtCore.Qt.AlignCenter, str(wk)
                )
                f2 = QtGui.QFont()
                f2.setPixelSize(8)
                p.setFont(f2)
                p.setPen(QtGui.QColor("white") if is_curr else QtGui.QColor(SUBTEXT))
                p.drawText(
                    QtCore.QRectF(sx, box_y + box_h + 2, slot_w, 11),
                    QtCore.Qt.AlignCenter, f"W{wk}"
                )
                wk_start = w1 + _timedelta(days=7 * (wk - 1))
                f3 = QtGui.QFont()
                f3.setPixelSize(7)
                p.setFont(f3)
                p.setPen(QtGui.QColor(SUBTEXT))
                p.drawText(
                    QtCore.QRectF(sx, box_y + box_h + 13, slot_w, 11),
                    QtCore.Qt.AlignCenter,
                    f"{wk_start.day} {wk_start.strftime('%b')}",
                )

        # Draw milestone markers in the strip above the week blocks
        MS_COLOR = "#e0c030"
        for ms in self._milestones:
            due_d = _parse_dmy(ms.get("due_date", ""))
            if due_d is None:
                continue
            wk = _prod_week(due_d, w1, hs, he)
            if wk is None:
                continue
            for slot_idx, item in enumerate(draw_list):
                if item[0] == "week" and item[1] == wk:
                    sx      = margin_x + slot_idx * slot_w
                    mid_x   = sx + slot_w / 2
                    tip_y   = ms_strip_h - 2
                    tri = QtGui.QPolygonF([
                        QtCore.QPointF(mid_x,     tip_y),
                        QtCore.QPointF(mid_x - 4, tip_y - 7),
                        QtCore.QPointF(mid_x + 4, tip_y - 7),
                    ])
                    p.setBrush(QtGui.QColor(MS_COLOR))
                    p.setPen(QtCore.Qt.NoPen)
                    p.drawPolygon(tri)
                    name = ms.get("name", "")
                    if len(name) > 9:
                        name = name[:8] + "…"
                    f_ms = QtGui.QFont()
                    f_ms.setPixelSize(7)
                    p.setFont(f_ms)
                    p.setPen(QtGui.QColor(MS_COLOR))
                    p.drawText(
                        QtCore.QRectF(sx, 1, slot_w, tip_y - 9),
                        QtCore.Qt.AlignCenter, name,
                    )
                    break

        p.end()


# ---------------------------------------------------------------------------
# Clickable big week-count display (right 1/3 of production panel)
# ---------------------------------------------------------------------------
class _WeekCountWidget(QtWidgets.QWidget):
    clicked = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hovered = False
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self._build()

    def _build(self):
        vl = QtWidgets.QVBoxLayout(self)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(0)
        vl.setAlignment(QtCore.Qt.AlignCenter)

        inner = QtWidgets.QWidget()
        inner.setObjectName("weekInner")
        il = QtWidgets.QVBoxLayout(inner)
        il.setContentsMargins(16, 16, 16, 12)
        il.setSpacing(0)
        il.setAlignment(QtCore.Qt.AlignCenter)

        self._top_lbl  = QtWidgets.QLabel("")
        self._top_lbl.setAlignment(QtCore.Qt.AlignCenter)
        self._top_lbl.setStyleSheet(
            f"font-size:10px; font-weight:bold; color:{SUBTEXT}; letter-spacing:2px;"
        )
        self._num_lbl  = QtWidgets.QLabel("—")
        self._num_lbl.setAlignment(QtCore.Qt.AlignCenter)
        self._num_lbl.setStyleSheet("font-size:68px; font-weight:bold; color:#444;")
        self._of_lbl   = QtWidgets.QLabel("")
        self._of_lbl.setAlignment(QtCore.Qt.AlignCenter)
        self._of_lbl.setStyleSheet(
            f"font-size:11px; color:{SUBTEXT}; letter-spacing:1px;"
        )
        self._hint_lbl = QtWidgets.QLabel("click to configure")
        self._hint_lbl.setAlignment(QtCore.Qt.AlignCenter)
        self._hint_lbl.setStyleSheet(f"font-size:9px; color:{SUBTEXT}; padding-top:6px;")

        il.addStretch()
        il.addWidget(self._top_lbl)
        il.addWidget(self._num_lbl)
        il.addWidget(self._of_lbl)
        il.addWidget(self._hint_lbl)
        il.addStretch()
        vl.addWidget(inner, stretch=1)

    def update_settings(self, settings):
        w1   = _parse_dmy(settings.get("week1_start", ""))
        tw   = settings.get("total_weeks", 12)
        hs   = _parse_dmy(settings.get("holiday_start", ""))
        he   = _parse_dmy(settings.get("holiday_end", ""))
        curr = _prod_week(_date.today(), w1, hs, he)

        if curr is None:
            self._top_lbl.setText("")
            self._num_lbl.setText("—")
            self._num_lbl.setStyleSheet("font-size:68px; font-weight:bold; color:#444;")
            self._of_lbl.setText("")
            self._hint_lbl.setText("click to configure")
        else:
            remaining = max(0, tw - curr)
            if curr > tw:
                color = "#e05050"
            elif remaining <= 2:
                color = "#e0a030"
            else:
                color = "#4caf50"
            self._top_lbl.setText("WEEK")
            self._num_lbl.setText(str(curr))
            self._num_lbl.setStyleSheet(
                f"font-size:68px; font-weight:bold; color:{color};"
            )
            self._of_lbl.setText(f"OF {tw}")
            self._hint_lbl.setText("click to edit")

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        color = ITEM_HOVER if self._hovered else ITEM_BG
        p.fillRect(self.rect(), QtGui.QColor(color))
        p.end()

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


# ---------------------------------------------------------------------------
# Compact milestone row for the NavPanel (170 px wide)
# ---------------------------------------------------------------------------
class _NavMilestoneRow(QtWidgets.QFrame):
    delete_requested = QtCore.Signal(int)
    edit_requested   = QtCore.Signal(int)

    def __init__(self, index, data, parent=None):
        super().__init__(parent)
        self._index = index
        self.setFixedHeight(40)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setStyleSheet(
            f"_NavMilestoneRow, QFrame{{background:{PANEL_BG};}}"
            f"_NavMilestoneRow:hover, QFrame:hover{{background:{ITEM_HOVER};}}"
        )
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(10, 0, 10, 0)
        row.setSpacing(6)

        name_lbl = QtWidgets.QLabel(data.get("name", ""))
        name_lbl.setStyleSheet("font-size:11px; color:white;")
        row.addWidget(name_lbl, stretch=1)

        due = data.get("due_date", "")
        if due:
            badge_text, badge_color = _proximity_badge(due)
            badge = QtWidgets.QLabel(badge_text)
            badge.setFixedHeight(18)
            badge.setMinimumWidth(36)
            badge.setAlignment(QtCore.Qt.AlignCenter)
            badge.setStyleSheet(
                f"background:{badge_color}; color:white; border-radius:3px;"
                f"font-size:9px; font-weight:bold; padding:0 4px;"
            )
            row.addWidget(badge)

        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._ctx)

    def _ctx(self, pos):
        menu = QtWidgets.QMenu(self)
        menu.setStyleSheet(_MENU_STYLE)
        edit_act = menu.addAction("Edit Milestone")
        del_act  = menu.addAction("Delete Milestone")
        act = menu.exec_(self.mapToGlobal(pos))
        if act == edit_act:
            self.edit_requested.emit(self._index)
        elif act == del_act:
            self.delete_requested.emit(self._index)


# ---------------------------------------------------------------------------
# Full milestone row for the Progress page content area
# ---------------------------------------------------------------------------
class _ProgressMilestoneRow(QtWidgets.QFrame):
    delete_requested = QtCore.Signal(int)
    edit_requested   = QtCore.Signal(int)

    def __init__(self, index, data, prod_settings, parent=None):
        super().__init__(parent)
        self._index  = index
        self.setMinimumHeight(44)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setStyleSheet(
            f"_ProgressMilestoneRow, QFrame{{background:{ITEM_BG}; border-bottom:1px solid {BORDER};}}"
            f"_ProgressMilestoneRow:hover, QFrame:hover{{background:{ITEM_HOVER};}}"
        )

        vl = QtWidgets.QVBoxLayout(self)
        vl.setContentsMargins(14, 6, 14, 6)
        vl.setSpacing(2)

        # Main info row
        main = QtWidgets.QHBoxLayout()
        main.setSpacing(12)

        # Production week badge
        due     = data.get("due_date", "")
        due_d   = _parse_dmy(due)
        w1_d    = _parse_dmy(prod_settings.get("week1_start", ""))
        hs_d    = _parse_dmy(prod_settings.get("holiday_start", ""))
        he_d    = _parse_dmy(prod_settings.get("holiday_end", ""))
        wk_num  = _prod_week(due_d, w1_d, hs_d, he_d) if (due_d and w1_d) else None

        if wk_num is not None:
            wk_badge = QtWidgets.QLabel(f"Wk {wk_num}")
            wk_badge.setFixedSize(38, 20)
            wk_badge.setAlignment(QtCore.Qt.AlignCenter)
            wk_badge.setStyleSheet(
                f"background:#3a4a5a; color:#a0c4e0; border-radius:3px;"
                f"font-size:10px; font-weight:bold;"
            )
            main.addWidget(wk_badge)

        # Name
        name_lbl = QtWidgets.QLabel(data.get("name", ""))
        name_lbl.setStyleSheet("font-size:13px; color:white; font-weight:bold;")
        main.addWidget(name_lbl, stretch=1)

        # Due date text
        if due:
            due_lbl = QtWidgets.QLabel(f"Due: {due}")
            due_lbl.setStyleSheet(f"font-size:11px; color:{SUBTEXT};")
            main.addWidget(due_lbl)

            badge_text, badge_color = _proximity_badge(due)
            badge = QtWidgets.QLabel(badge_text)
            badge.setFixedSize(80, 22)
            badge.setAlignment(QtCore.Qt.AlignCenter)
            badge.setStyleSheet(
                f"background:{badge_color}; color:white; border-radius:4px;"
                f"font-weight:bold; font-size:11px;"
            )
            main.addWidget(badge)

        vl.addLayout(main)

        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._ctx)

    def _ctx(self, pos):
        menu = QtWidgets.QMenu(self)
        menu.setStyleSheet(_MENU_STYLE)
        edit_act = menu.addAction("Edit Milestone")
        del_act  = menu.addAction("Delete Milestone")
        act = menu.exec_(self.mapToGlobal(pos))
        if act == edit_act:
            self.edit_requested.emit(self._index)
        elif act == del_act:
            self.delete_requested.emit(self._index)


# ---------------------------------------------------------------------------
# Progress page — stats strip + charts + production schedule + milestones
# ---------------------------------------------------------------------------
class ProgressPage(QtWidgets.QWidget):
    data_changed   = QtCore.Signal()
    save_requested = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._milestones      = {}   # {project: [{name, due_date, extension}]}
        self._production      = {}   # {project: {week1_start, total_weeks, holiday_start, holiday_end}}
        self._current_project = ""
        self._shots_data      = {}
        self._assets_data     = {}
        self._build()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._hdr_lbl = QtWidgets.QLabel("Select a project to view progress")
        self._hdr_lbl.setFixedHeight(38)
        self._hdr_lbl.setStyleSheet(
            f"font-weight:bold; font-size:13px; color:white; background:{PANEL_BG};"
            f"border-bottom:1px solid {BORDER}; padding-left:14px;"
        )
        layout.addWidget(self._hdr_lbl)

        self._scroll = QtWidgets.QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet(f"QScrollArea{{border:none; background:{DARK_BG};}}")
        self._content_widget = QtWidgets.QWidget()
        self._content_widget.setStyleSheet(f"background:{DARK_BG};")
        self._content_layout = QtWidgets.QVBoxLayout(self._content_widget)
        self._content_layout.setContentsMargins(20, 20, 20, 20)
        self._content_layout.setSpacing(16)
        self._content_layout.addStretch()
        self._scroll.setWidget(self._content_widget)
        layout.addWidget(self._scroll)

    # ── public API ──────────────────────────────────────────────────────────

    def set_project(self, project, shots_data, assets_data):
        self._current_project = project
        self._shots_data      = shots_data
        self._assets_data     = assets_data
        self._refresh()

    def refresh_data(self, shots_data, assets_data):
        self._shots_data  = shots_data
        self._assets_data = assets_data
        if self._current_project:
            self._refresh()

    def project_added(self, name):
        self._milestones.setdefault(name, [])
        self._production.setdefault(name, {"week1_start": "", "total_weeks": 12,
                                           "holiday_start": "", "holiday_end": ""})

    def project_removed(self, name):
        self._milestones.pop(name, None)
        self._production.pop(name, None)

    def add_milestone(self):
        prod = self._production.get(self._current_project, {})
        dlg = MilestoneDialog(prod_settings=prod, parent=self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            data = dlg.get_data()
            if data["name"]:
                self._milestones.setdefault(self._current_project, []).append(data)
                self.data_changed.emit()

    def delete_milestone(self, idx):
        proj = self._current_project
        ms = self._milestones.get(proj, [])
        if 0 <= idx < len(ms):
            del ms[idx]
            self.data_changed.emit()

    def get_milestones_for_project(self, project):
        return list(self._milestones.get(project, []))

    def get_milestones(self):
        return dict(self._milestones)

    def load_milestones(self, data):
        self._milestones = {k: v for k, v in data.items() if isinstance(v, list)}

    def get_production(self):
        return dict(self._production)

    def load_production(self, data):
        self._production = {k: v for k, v in data.items() if isinstance(v, dict)}

    # ── internal ────────────────────────────────────────────────────────────

    def _refresh(self):
        while self._content_layout.count() > 1:
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()

        proj = self._current_project
        if not proj:
            self._hdr_lbl.setText("Select a project to view progress")
            return

        self._hdr_lbl.setText(f"{proj}  —  Progress")
        shots_counts  = self._stage_counts(self._shots_data.get(proj, {}),  SHOT_STAGES)
        assets_counts = self._stage_counts(self._assets_data.get(proj, {}), ASSET_STAGES)
        prod_settings = self._production.get(proj, {})

        widgets = [
            self._build_date_panel(),
            self._build_summary_strip(shots_counts, assets_counts),
            self._build_charts_panel(shots_counts, assets_counts),
            self._build_combined_panel(proj, prod_settings),
        ]
        for i, w in enumerate(widgets):
            self._content_layout.insertWidget(i, w)

    @staticmethod
    def _stage_counts(project_groups, all_stages):
        counts = {}
        for items in project_groups.values():
            for item in items:
                s = item.get("stage", all_stages[0])
                counts[s] = counts.get(s, 0) + 1
        return {s: counts.get(s, 0) for s in all_stages if counts.get(s, 0) > 0}

    @staticmethod
    def _build_date_panel():
        today = _date.today()
        panel = QtWidgets.QWidget()
        panel.setStyleSheet(f"background:{PANEL_BG}; border-radius:6px;")
        row = QtWidgets.QHBoxLayout(panel)
        row.setContentsMargins(28, 18, 28, 18)
        row.setSpacing(0)
        day_lbl = QtWidgets.QLabel(today.strftime("%A"))
        day_lbl.setStyleSheet("font-size:34px; font-weight:bold; color:white; background:transparent;")
        sep_lbl = QtWidgets.QLabel("  —  ")
        sep_lbl.setStyleSheet(f"font-size:34px; color:{SUBTEXT}; background:transparent;")
        date_lbl = QtWidgets.QLabel(today.strftime("%d %B %Y"))
        date_lbl.setStyleSheet(f"font-size:34px; color:{SUBTEXT}; background:transparent;")
        row.addWidget(day_lbl)
        row.addWidget(sep_lbl)
        row.addWidget(date_lbl)
        row.addStretch()
        return panel

    @staticmethod
    def _build_summary_strip(shots_counts, assets_counts):
        total_shots  = sum(shots_counts.values())
        rendered     = shots_counts.get("Rendered", 0)
        total_assets = sum(assets_counts.values())
        prod_ready   = assets_counts.get("Production Ready", 0)

        strip = QtWidgets.QWidget()
        strip.setStyleSheet(f"background:{PANEL_BG}; border-radius:6px;")
        row = QtWidgets.QHBoxLayout(strip)
        row.setContentsMargins(20, 14, 20, 14)
        row.setSpacing(0)

        cards = [
            ("TOTAL SHOTS",      str(total_shots),  TEXT),
            ("RENDERED",         str(rendered),     "#9575cd"),
            ("TOTAL ASSETS",     str(total_assets), TEXT),
            ("PRODUCTION READY", str(prod_ready),   "#4caf50"),
        ]
        for i, (label, value, val_color) in enumerate(cards):
            if i > 0:
                sep = QtWidgets.QFrame()
                sep.setFrameShape(QtWidgets.QFrame.VLine)
                sep.setFixedHeight(44)
                sep.setStyleSheet(f"color:{BORDER};")
                row.addWidget(sep)
                row.addSpacing(20)
            card = QtWidgets.QWidget()
            card.setStyleSheet("background:transparent;")
            cvl = QtWidgets.QVBoxLayout(card)
            cvl.setContentsMargins(0, 0, 0, 0)
            cvl.setSpacing(2)
            val_lbl = QtWidgets.QLabel(value)
            val_lbl.setStyleSheet(f"font-size:28px; font-weight:bold; color:{val_color};")
            val_lbl.setAlignment(QtCore.Qt.AlignCenter)
            lbl = QtWidgets.QLabel(label)
            lbl.setStyleSheet(f"font-size:10px; color:{SUBTEXT}; letter-spacing:1px;")
            lbl.setAlignment(QtCore.Qt.AlignCenter)
            cvl.addWidget(val_lbl)
            cvl.addWidget(lbl)
            row.addWidget(card, stretch=1)
        return strip

    def _build_charts_panel(self, shots_counts, assets_counts):
        panel = QtWidgets.QWidget()
        panel.setStyleSheet(f"background:{PANEL_BG}; border-radius:6px;")
        row = QtWidgets.QHBoxLayout(panel)
        row.setContentsMargins(28, 20, 28, 20)
        row.setSpacing(32)

        shots_pie = PieChartWidget(title="Shots", complete_stages=["Final", "Rendered"])
        shots_pie.set_data(shots_counts)
        row.addWidget(shots_pie, alignment=QtCore.Qt.AlignTop)
        row.addLayout(self._stats_col(shots_counts, SHOT_STAGES))

        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.VLine)
        sep.setStyleSheet(f"color:{BORDER};")
        row.addWidget(sep)

        assets_pie = PieChartWidget(title="Assets", complete_stages=["Production Ready"])
        assets_pie.set_data(assets_counts)
        row.addWidget(assets_pie, alignment=QtCore.Qt.AlignTop)
        row.addLayout(self._stats_col(assets_counts, ASSET_STAGES))
        row.addStretch()
        return panel

    @staticmethod
    def _stats_col(counts, all_stages):
        col = QtWidgets.QVBoxLayout()
        col.setSpacing(7)
        total = sum(counts.values())
        col.addSpacing(8)
        for stage in all_stages:
            count = counts.get(stage, 0)
            pct   = int(count / total * 100) if total else 0
            color = STAGE_COLORS.get(stage, "#888")
            rw = QtWidgets.QWidget()
            rl = QtWidgets.QHBoxLayout(rw)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.setSpacing(8)
            dot = QtWidgets.QLabel("●")
            dot.setFixedWidth(14)
            dot.setStyleSheet(f"color:{color}; font-size:13px;")
            rl.addWidget(dot)
            name_lbl = QtWidgets.QLabel(stage)
            name_lbl.setFixedWidth(130)
            name_lbl.setStyleSheet(f"font-size:11px; color:{'white' if count else SUBTEXT};")
            rl.addWidget(name_lbl)
            cnt_lbl = QtWidgets.QLabel(f"{count}  ({pct}%)")
            cnt_lbl.setStyleSheet(f"font-size:11px; color:{SUBTEXT};")
            rl.addWidget(cnt_lbl)
            rl.addStretch()
            col.addWidget(rw)
        col.addStretch()
        return col

    def _sorted_milestones_with_idx(self, proj):
        """Return [(original_index, data), ...] sorted ascending by due date; undated at end."""
        ms = self._milestones.get(proj, [])
        indexed = list(enumerate(ms))
        return sorted(
            indexed,
            key=lambda x: _parse_dmy(x[1].get("due_date", "")) or _date.max
        )

    def _build_combined_panel(self, proj, prod_settings):
        """Milestones list (left 2/3, sorted by date) + big week counter (right 1/3)."""
        panel = QtWidgets.QWidget()
        panel.setStyleSheet(f"background:{PANEL_BG}; border-radius:6px;")
        panel.setMinimumHeight(220)
        vl = QtWidgets.QVBoxLayout(panel)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(0)

        # ── Header ──
        hdr_w = QtWidgets.QWidget()
        hdr_w.setFixedHeight(38)
        hdr_w.setStyleSheet(f"border-bottom:1px solid {BORDER};")
        hl = QtWidgets.QHBoxLayout(hdr_w)
        hl.setContentsMargins(14, 0, 14, 0)
        hdr_lbl = QtWidgets.QLabel("MILESTONES")
        hdr_lbl.setStyleSheet(
            f"font-size:10px; font-weight:bold; color:{SUBTEXT}; letter-spacing:1px;"
        )
        hl.addWidget(hdr_lbl)
        vl.addWidget(hdr_w)

        # ── Week timeline ──
        timeline = _WeekTimelineWidget()
        timeline.set_settings(prod_settings, milestones=self._milestones.get(proj, []))
        timeline.setFixedHeight(100)
        timeline.setStyleSheet(f"background:{PANEL_BG}; border-bottom:1px solid {BORDER};")
        vl.addWidget(timeline)

        # ── Body: milestone list (2/3) | separator | week count (1/3) ──
        body = QtWidgets.QWidget()
        body.setStyleSheet("background:transparent;")
        body_row = QtWidgets.QHBoxLayout(body)
        body_row.setContentsMargins(0, 0, 0, 0)
        body_row.setSpacing(0)

        # Left 2/3 — sorted milestone rows in a scroll area
        ms_widget = QtWidgets.QWidget()
        ms_widget.setStyleSheet(f"background:{DARK_BG};")
        ms_vl = QtWidgets.QVBoxLayout(ms_widget)
        ms_vl.setContentsMargins(0, 0, 0, 0)
        ms_vl.setSpacing(1)

        sorted_ms = self._sorted_milestones_with_idx(proj)
        if sorted_ms:
            for orig_idx, ms_data in sorted_ms:
                row = _ProgressMilestoneRow(orig_idx, ms_data, prod_settings)
                row.edit_requested.connect(lambda idx, p=proj: self._edit_milestone(p, idx))
                row.delete_requested.connect(self._delete_ms_and_refresh)
                ms_vl.addWidget(row)
        else:
            empty = QtWidgets.QLabel("No milestones yet — use  + Add  above")
            empty.setStyleSheet(f"color:{SUBTEXT}; font-size:11px; padding:18px 14px;")
            ms_vl.addWidget(empty)
        ms_vl.addStretch()

        ms_scroll = QtWidgets.QScrollArea()
        ms_scroll.setWidgetResizable(True)
        ms_scroll.setStyleSheet(f"QScrollArea{{border:none; background:{DARK_BG};}}")
        ms_scroll.setWidget(ms_widget)
        body_row.addWidget(ms_scroll, stretch=2)

        # Vertical separator
        vsep = QtWidgets.QFrame()
        vsep.setFrameShape(QtWidgets.QFrame.VLine)
        vsep.setStyleSheet(f"color:{BORDER};")
        body_row.addWidget(vsep)

        # Right 1/3 — big clickable week number
        self._week_count_widget = _WeekCountWidget()
        self._week_count_widget.update_settings(prod_settings)
        self._week_count_widget.clicked.connect(
            lambda: self._open_prod_settings_dialog(proj)
        )
        body_row.addWidget(self._week_count_widget, stretch=1)

        vl.addWidget(body, stretch=1)
        return panel

    def _open_prod_settings_dialog(self, proj):
        dlg = _ProductionSettingsDialog(self._production.get(proj, {}), parent=self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            self._production[proj] = dlg.get_data()
            self._refresh()
            self.save_requested.emit()

    def _edit_milestone(self, proj, idx):
        ms = self._milestones.get(proj, [])
        if 0 <= idx < len(ms):
            prod = self._production.get(proj, {})
            dlg = MilestoneDialog(data=ms[idx], prod_settings=prod, parent=self)
            if dlg.exec_() == QtWidgets.QDialog.Accepted:
                ms[idx] = dlg.get_data()
                self._refresh()
                self.data_changed.emit()

    def _delete_ms_and_refresh(self, idx):
        self.delete_milestone(idx)
        self._refresh()


# ---------------------------------------------------------------------------
# Artists tab — global artist roster (name + role)
# ---------------------------------------------------------------------------
class _ArtistDialog(QtWidgets.QDialog):
    def __init__(self, data=None, parent=None):
        super().__init__(parent)
        self._is_new = data is None
        self.setWindowTitle("Add Artist" if self._is_new else "Edit Artist")
        self.setMinimumWidth(300)
        self.setStyleSheet(
            f"QDialog{{background:{DARK_BG};color:white;}}"
            f"QLabel{{color:white;}}"
            f"QLineEdit{{background:{ITEM_BG};color:white;border:1px solid {BORDER};padding:4px;}}"
            f"QPushButton{{background:#444;color:white;border:1px solid {BORDER};padding:4px 12px;}}"
            f"QPushButton:hover{{background:#555;}}"
        )
        self._data = data.copy() if data else {}
        self._build()

    def _build(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)
        self.name_edit = QtWidgets.QLineEdit(self._data.get("name", ""))
        self.role_edit = QtWidgets.QLineEdit(self._data.get("role", ""))
        self.role_edit.setPlaceholderText("e.g. Animator, Rigger, VFX…")
        layout.addRow("Name:", self.name_edit)
        layout.addRow("Role:", self.role_edit)
        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def get_data(self):
        return {
            "name": self.name_edit.text().strip(),
            "role": self.role_edit.text().strip(),
        }


class _ArtistRow(QtWidgets.QFrame):
    edit_requested   = QtCore.Signal(int)
    delete_requested = QtCore.Signal(int)

    def __init__(self, index, data, parent=None):
        super().__init__(parent)
        self._index = index
        self.setFixedHeight(56)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setStyleSheet(
            f"_ArtistRow, QFrame{{background:{ITEM_BG}; border-bottom:1px solid {BORDER};}}"
            f"_ArtistRow:hover, QFrame:hover{{background:{ITEM_HOVER};}}"
        )
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(14, 8, 14, 8)
        row.setSpacing(10)
        left = QtWidgets.QVBoxLayout()
        left.setSpacing(2)
        name_lbl = QtWidgets.QLabel(data.get("name", ""))
        name_lbl.setStyleSheet("font-weight:bold; font-size:13px; color:white;")
        role_lbl = QtWidgets.QLabel(data.get("role", ""))
        role_lbl.setStyleSheet(f"font-size:11px; color:{SUBTEXT};")
        left.addWidget(name_lbl)
        left.addWidget(role_lbl)
        row.addLayout(left, stretch=1)
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._ctx)

    def _ctx(self, pos):
        menu = QtWidgets.QMenu(self)
        menu.setStyleSheet(_MENU_STYLE)
        edit_act = menu.addAction("Edit Artist")
        del_act  = menu.addAction("Delete Artist")
        act = menu.exec_(self.mapToGlobal(pos))
        if act == edit_act:
            self.edit_requested.emit(self._index)
        elif act == del_act:
            self.delete_requested.emit(self._index)


class ArtistsPage(QtWidgets.QWidget):
    data_changed = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._artists = []
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
        lbl = QtWidgets.QLabel("Artists")
        lbl.setStyleSheet("font-weight:bold; font-size:13px; color:white;")
        hl.addWidget(lbl)
        hl.addStretch()
        add_btn = QtWidgets.QPushButton("+ Add Artist")
        add_btn.setStyleSheet(
            "QPushButton{background:#2e5a2e;color:white;border:none;padding:4px 14px;border-radius:3px;}"
            "QPushButton:hover{background:#3a7a3a;}"
        )
        add_btn.clicked.connect(self._add_artist)
        hl.addWidget(add_btn)
        layout.addWidget(header)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea{{border:none; background:{DARK_BG};}}")
        self._container = QtWidgets.QWidget()
        self._container.setStyleSheet(f"background:{DARK_BG};")
        self._vbox = QtWidgets.QVBoxLayout(self._container)
        self._vbox.setContentsMargins(0, 0, 0, 0)
        self._vbox.setSpacing(1)
        self._vbox.addStretch()
        scroll.setWidget(self._container)
        layout.addWidget(scroll)

    def _rebuild(self):
        while self._vbox.count() > 1:
            item = self._vbox.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for i, artist in enumerate(self._artists):
            row = _ArtistRow(i, artist)
            row.edit_requested.connect(self._edit_artist)
            row.delete_requested.connect(self._delete_artist)
            self._vbox.insertWidget(self._vbox.count() - 1, row)

    def _add_artist(self):
        dlg = _ArtistDialog(parent=self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            data = dlg.get_data()
            if data["name"]:
                self._artists.append(data)
                self._rebuild()
                self.data_changed.emit()

    def _edit_artist(self, idx):
        if 0 <= idx < len(self._artists):
            dlg = _ArtistDialog(data=self._artists[idx], parent=self)
            if dlg.exec_() == QtWidgets.QDialog.Accepted:
                self._artists[idx] = dlg.get_data()
                self._rebuild()
                self.data_changed.emit()

    def _delete_artist(self, idx):
        if 0 <= idx < len(self._artists):
            name = self._artists[idx].get("name", "")
            reply = QtWidgets.QMessageBox.question(
                self, "Delete Artist", f"Remove '{name}'?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            )
            if reply == QtWidgets.QMessageBox.Yes:
                del self._artists[idx]
                self._rebuild()
                self.data_changed.emit()

    def get_data(self):
        return list(self._artists)

    def load_data(self, data):
        self._artists = list(data) if isinstance(data, list) else []
        self._rebuild()


# ---------------------------------------------------------------------------
# NavPanel — Projects (top) + Groups or Milestones (bottom)
# ---------------------------------------------------------------------------
class NavPanel(QtWidgets.QWidget):
    project_changed            = QtCore.Signal(str)
    project_added              = QtCore.Signal(str)
    project_removed            = QtCore.Signal(str)
    group_changed              = QtCore.Signal(str)
    group_added                = QtCore.Signal(str)
    group_removed              = QtCore.Signal(str)
    milestone_add_requested    = QtCore.Signal()
    milestone_delete_requested = QtCore.Signal(int)
    milestone_edit_requested   = QtCore.Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._group_label = "Scene"
        self.setMinimumWidth(140)
        self.setStyleSheet(f"background:{PANEL_BG};")
        self._build()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._make_section_widget(
            "PROJECTS", self._add_project, self._remove_project
        ))
        self.project_list = self._make_list()
        self.project_list.currentTextChanged.connect(
            lambda t: self.project_changed.emit(t or "")
        )
        self.project_list.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.project_list.customContextMenuRequested.connect(
            lambda pos: self._list_ctx(self.project_list, pos, "Project")
        )
        layout.addWidget(self.project_list)

        self._bottom_stack = QtWidgets.QStackedWidget()

        # ── Stack 0: Groups ──
        groups_page = QtWidgets.QWidget()
        groups_page.setStyleSheet(f"background:{PANEL_BG};")
        gvl = QtWidgets.QVBoxLayout(groups_page)
        gvl.setContentsMargins(0, 0, 0, 0)
        gvl.setSpacing(0)
        gvl.addWidget(self._make_section_widget(
            "SCENES", self._add_group, self._remove_group,
            store_add_btn_as="_group_add_btn",
            store_remove_btn_as="_group_remove_btn",
            store_label_as="_group_header_lbl",
        ))
        self.group_list = self._make_list()
        self.group_list.currentTextChanged.connect(self._on_group_text_changed)
        self.group_list.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.group_list.customContextMenuRequested.connect(
            lambda pos: self._list_ctx(self.group_list, pos, self._group_label)
        )
        gvl.addWidget(self.group_list)
        self._bottom_stack.addWidget(groups_page)

        # ── Stack 1: Milestones ──
        ms_page = QtWidgets.QWidget()
        ms_page.setStyleSheet(f"background:{PANEL_BG};")
        mvl = QtWidgets.QVBoxLayout(ms_page)
        mvl.setContentsMargins(0, 0, 0, 0)
        mvl.setSpacing(0)
        mvl.addWidget(self._make_section_widget(
            "MILESTONES", lambda: self.milestone_add_requested.emit(),
            self._remove_milestone,
        ))
        ms_scroll = QtWidgets.QScrollArea()
        ms_scroll.setWidgetResizable(True)
        ms_scroll.setStyleSheet(f"QScrollArea{{border:none; background:{PANEL_BG};}}")
        self._ms_container = QtWidgets.QWidget()
        self._ms_container.setStyleSheet(f"background:{PANEL_BG};")
        self._ms_vbox = QtWidgets.QVBoxLayout(self._ms_container)
        self._ms_vbox.setContentsMargins(0, 0, 0, 0)
        self._ms_vbox.setSpacing(1)
        self._ms_vbox.addStretch()
        ms_scroll.setWidget(self._ms_container)
        mvl.addWidget(ms_scroll)
        self._bottom_stack.addWidget(ms_page)

        layout.addWidget(self._bottom_stack)

    def _make_section_widget(self, title, add_cb, remove_cb=None,
                              store_add_btn_as=None, store_remove_btn_as=None,
                              store_label_as=None):
        _GREEN_BTN = (
            "QPushButton{background:#2e5a2e;color:white;border:none;border-radius:3px;"
            "font-size:16px;font-weight:bold;}"
            "QPushButton:hover{background:#3a7a3a;}"
            "QPushButton:disabled{background:#333;color:#555;}"
        )
        h = QtWidgets.QWidget()
        h.setFixedHeight(32)
        h.setStyleSheet(
            f"background:{PANEL_BG};"
            f"border-top:1px solid {BORDER}; border-bottom:1px solid {BORDER};"
        )
        hl = QtWidgets.QHBoxLayout(h)
        hl.setContentsMargins(12, 0, 8, 0)
        hl.setSpacing(4)
        lbl = QtWidgets.QLabel(title)
        lbl.setStyleSheet(
            f"font-size:10px; font-weight:bold; color:{SUBTEXT}; letter-spacing:1px;"
        )
        hl.addWidget(lbl)
        hl.addStretch()
        add_btn = QtWidgets.QPushButton("+")
        add_btn.setFixedSize(24, 24)
        add_btn.setStyleSheet(_GREEN_BTN)
        add_btn.clicked.connect(add_cb)
        hl.addWidget(add_btn)
        if store_add_btn_as:
            setattr(self, store_add_btn_as, add_btn)
            add_btn.setEnabled(False)
        rem_btn = QtWidgets.QPushButton("−")
        rem_btn.setFixedSize(24, 24)
        rem_btn.setStyleSheet(_GREEN_BTN)
        if remove_cb:
            rem_btn.clicked.connect(remove_cb)
        hl.addWidget(rem_btn)
        if store_remove_btn_as:
            setattr(self, store_remove_btn_as, rem_btn)
            rem_btn.setEnabled(False)
        if store_label_as:
            setattr(self, store_label_as, lbl)
        return h

    def _make_list(self):
        lw = QtWidgets.QListWidget()
        lw.setStyleSheet(_LIST_STYLE)
        return lw

    def _on_group_text_changed(self, t):
        self.group_changed.emit(t or "")

    def show_bottom_section(self, visible):
        self._bottom_stack.setVisible(visible)

    def show_milestones(self, milestones):
        self._bottom_stack.setCurrentIndex(1)
        self._bottom_stack.setVisible(True)
        while self._ms_vbox.count() > 1:
            item = self._ms_vbox.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for i, ms in enumerate(milestones):
            row = _NavMilestoneRow(i, ms)
            row.edit_requested.connect(self.milestone_edit_requested)
            row.delete_requested.connect(self.milestone_delete_requested)
            self._ms_vbox.insertWidget(self._ms_vbox.count() - 1, row)

    def set_groups(self, groups, group_label="Scene", enabled=True):
        self._group_label = group_label
        self._group_header_lbl.setText(f"{group_label.upper()}S")
        self._group_add_btn.setEnabled(enabled)
        self._group_remove_btn.setEnabled(enabled)
        self.group_list.blockSignals(True)
        self.group_list.clear()
        for g in groups:
            self.group_list.addItem(g)
        self.group_list.setCurrentRow(0)
        self.group_list.blockSignals(False)
        self._bottom_stack.setCurrentIndex(0)
        self._bottom_stack.setVisible(True)
        self.group_changed.emit(groups[0] if groups else "")

    def get_groups(self):
        return [
            self.group_list.item(i).text()
            for i in range(self.group_list.count())
        ]

    def set_projects(self, projects):
        self.project_list.blockSignals(True)
        self.project_list.clear()
        for p in projects:
            self.project_list.addItem(p)
        self.project_list.setCurrentRow(0)
        self.project_list.blockSignals(False)

    def get_projects(self):
        return [
            self.project_list.item(i).text()
            for i in range(self.project_list.count())
        ]

    def _add_project(self):
        name, ok = QtWidgets.QInputDialog.getText(self, "Add Project", "Project name:")
        name = name.strip()
        if not (ok and name): return
        existing = [self.project_list.item(i).text() for i in range(self.project_list.count())]
        if name in existing:
            QtWidgets.QMessageBox.warning(self, "Add Project", f"'{name}' already exists.")
            return
        self.project_list.addItem(name)
        self.project_added.emit(name)
        self.project_list.setCurrentRow(self.project_list.count() - 1)

    def _remove_project(self):
        item = self.project_list.currentItem()
        if not item:
            return
        name = item.text()
        reply = QtWidgets.QMessageBox.question(
            self, "Remove Project",
            f"Remove '{name}' and all its contents?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )
        if reply == QtWidgets.QMessageBox.Yes:
            self.project_list.blockSignals(True)
            self.project_list.takeItem(self.project_list.row(item))
            self.project_list.setCurrentRow(0)
            self.project_list.blockSignals(False)
            self.project_removed.emit(name)
            next_item = self.project_list.currentItem()
            self.project_changed.emit(next_item.text() if next_item else "")

    def _remove_group(self):
        item = self.group_list.currentItem()
        if not item:
            return
        name = item.text()
        reply = QtWidgets.QMessageBox.question(
            self, f"Remove {self._group_label}",
            f"Remove '{name}' and all its contents?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )
        if reply == QtWidgets.QMessageBox.Yes:
            self.group_list.blockSignals(True)
            self.group_list.takeItem(self.group_list.row(item))
            self.group_list.setCurrentRow(0)
            self.group_list.blockSignals(False)
            self.group_removed.emit(name)
            next_group = self.group_list.currentItem()
            self.group_changed.emit(next_group.text() if next_group else "")

    def _remove_milestone(self):
        ms_count = self._ms_vbox.count() - 1
        if ms_count <= 0:
            return
        last_idx = ms_count - 1
        self.milestone_delete_requested.emit(last_idx)

    def _add_group(self):
        name, ok = QtWidgets.QInputDialog.getText(
            self, f"Add {self._group_label}", f"{self._group_label} name:"
        )
        name = name.strip()
        if not (ok and name): return
        existing = [self.group_list.item(i).text() for i in range(self.group_list.count())]
        if name in existing:
            QtWidgets.QMessageBox.warning(self, f"Add {self._group_label}", f"'{name}' already exists.")
            return
        self.group_list.addItem(name)
        self.group_added.emit(name)
        self.group_list.setCurrentRow(self.group_list.count() - 1)

    def _list_ctx(self, list_widget, pos, label):
        item = list_widget.itemAt(pos)
        if not item:
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
                    next_item = list_widget.currentItem()
                    self.project_changed.emit(next_item.text() if next_item else "")
                else:
                    self.group_removed.emit(name)
                    next_item = list_widget.currentItem()
                    self.group_changed.emit(next_item.text() if next_item else "")


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------
class JiffySchedule(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setWindowTitle("JiffySchedule")
        self.resize(1200, 900)
        self.setStyleSheet(f"QWidget{{background:{DARK_BG};color:white;}}")
        self._active_project = ""
        self._workspace_job = None
        self._data_dir = cmds.optionVar(q=_DATA_DIR_PREF) if cmds.optionVar(exists=_DATA_DIR_PREF) else ""
        self._build()
        self._make_dockable()
        if self._data_dir:
            self.load_data()
        else:
            QtCore.QTimer.singleShot(300, self._prompt_data_dir)
        self._workspace_job = cmds.scriptJob(
            event=['workspaceChanged', self._update_project_banner])

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title_bar = QtWidgets.QWidget()
        title_bar.setFixedHeight(42)
        title_bar.setStyleSheet(f"background:#1a1a1a; border-bottom:1px solid {BORDER};")
        tl = QtWidgets.QHBoxLayout(title_bar)
        tl.setContentsMargins(16, 0, 8, 0)
        tl.setSpacing(0)
        name_lbl = QtWidgets.QLabel("JiffySchedule")
        name_lbl.setStyleSheet("font-size:17px; font-weight:bold; color:white;")
        tl.addWidget(name_lbl)
        tl.addSpacing(24)
        self.tab_bar = QtWidgets.QTabBar()
        self.tab_bar.addTab("Shots")
        self.tab_bar.addTab("Assets")
        self.tab_bar.addTab("Progress")
        self.tab_bar.addTab("Artists")
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
        folder_btn = QtWidgets.QPushButton("📁")
        folder_btn.setFixedSize(30, 30)
        folder_btn.setToolTip("Change data folder")
        folder_btn.setStyleSheet(
            "QPushButton{background:transparent;color:#666;border:none;font-size:14px;}"
            "QPushButton:hover{color:white;}"
        )
        folder_btn.clicked.connect(self._choose_data_dir)
        tl.addWidget(folder_btn)
        layout.addWidget(title_bar)

        workspace = cmds.workspace(query=True, rootDirectory=True).rstrip("/\\")
        project_name = os.path.basename(workspace)
        if not project_name or project_name == "default":
            banner_text = "Project:  No project set"
            banner_color = "#e05050"
        else:
            banner_text = f"Project:  {project_name}"
            banner_color = "#4caf50"
        self._project_banner = QtWidgets.QLabel(banner_text)
        self._project_banner.setFixedHeight(36)
        self._project_banner.setStyleSheet(
            f"background:#1a1a1a; color:{banner_color}; font-size:15px; font-weight:bold;"
            f"padding-left:16px; border-bottom:1px solid {BORDER};"
        )
        layout.addWidget(self._project_banner)

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
        self.nav.milestone_add_requested.connect(self._on_milestone_add)
        self.nav.milestone_delete_requested.connect(self._on_milestone_delete)
        self.nav.milestone_edit_requested.connect(self._on_milestone_edit)

        self.shots_page    = SchedulePage(item_label="Shot",  stages=SHOT_STAGES)
        self.assets_page   = SchedulePage(item_label="Asset", stages=ASSET_STAGES)
        self.progress_page = ProgressPage()
        self.artists_page  = ArtistsPage()

        self.shots_page.data_changed.connect(self._on_shots_changed)
        self.assets_page.data_changed.connect(self._on_assets_changed)
        self.progress_page.data_changed.connect(self._on_milestone_data_changed)
        self.progress_page.save_requested.connect(self.save_data)
        self.artists_page.data_changed.connect(self.save_data)

        self.stack = QtWidgets.QStackedWidget()
        self.stack.addWidget(self.shots_page)
        self.stack.addWidget(self.assets_page)
        self.stack.addWidget(self.progress_page)
        self.stack.addWidget(self.artists_page)

        body.addWidget(self.nav)
        body.addWidget(self.stack)
        body.setSizes([220, 980])
        body.setStretchFactor(0, 0)
        body.setStretchFactor(1, 1)
        layout.addWidget(body)

    def _active_page(self):
        idx = self.tab_bar.currentIndex()
        if idx == 0: return self.shots_page
        if idx == 1: return self.assets_page
        return None

    def _group_label_for_tab(self, index):
        return "Scene" if index == 0 else "Asset"

    def _on_tab_changed(self, index):
        self.stack.setCurrentIndex(index)
        if index == 2:
            self._enter_progress_tab()
        elif index == 3:
            self.nav.show_bottom_section(False)
        else:
            page    = self._active_page()
            label   = self._group_label_for_tab(index)
            groups  = page.get_groups_for_project(self._active_project)
            self.nav.set_groups(groups, group_label=label, enabled=bool(self._active_project))

    def _enter_progress_tab(self):
        proj = self._active_project
        self.progress_page.set_project(
            proj, self.shots_page.get_data(), self.assets_page.get_data()
        )
        if proj:
            self.nav.show_milestones(self.progress_page.get_milestones_for_project(proj))
        else:
            self.nav.show_bottom_section(False)

    def _refresh_nav_milestones(self):
        if self.tab_bar.currentIndex() == 2 and self._active_project:
            self.nav.show_milestones(
                self.progress_page.get_milestones_for_project(self._active_project)
            )

    def _on_project_changed(self, project):
        self._active_project = project
        self.shots_page.set_project(project)
        self.assets_page.set_project(project)
        idx = self.tab_bar.currentIndex()
        if idx == 2:
            self.progress_page.set_project(
                project, self.shots_page.get_data(), self.assets_page.get_data()
            )
            if project:
                self.nav.show_milestones(self.progress_page.get_milestones_for_project(project))
            else:
                self.nav.show_bottom_section(False)
        elif idx == 3:
            pass  # artists tab — global, unaffected by project selection
        else:
            label  = self._group_label_for_tab(idx)
            groups = self._active_page().get_groups_for_project(project)
            self.nav.set_groups(groups, group_label=label, enabled=bool(project))

    def _on_project_added(self, name):
        self.shots_page.project_added(name)
        self.assets_page.project_added(name)
        self.progress_page.project_added(name)
        self.save_data()

    def _on_project_removed(self, name):
        self.shots_page.project_removed(name)
        self.assets_page.project_removed(name)
        self.progress_page.project_removed(name)
        self.save_data()

    def _on_group_changed(self, group):
        page = self._active_page()
        if page: page.select_group(group)

    def _on_group_added(self, name):
        page = self._active_page()
        if page:
            page.project_added(self._active_project)
            page.select_group(name)
        self.save_data()

    def _on_group_removed(self, name):
        page = self._active_page()
        if page:
            page._data.get(self._active_project, {}).pop(name, None)
            page.select_group("")
        self.save_data()

    def _on_shots_changed(self):
        self.progress_page.refresh_data(self.shots_page.get_data(), self.assets_page.get_data())
        self.save_data()

    def _on_assets_changed(self):
        self.progress_page.refresh_data(self.shots_page.get_data(), self.assets_page.get_data())
        self.save_data()

    def _on_milestone_add(self):
        self.progress_page.add_milestone()

    def _on_milestone_delete(self, idx):
        self.progress_page.delete_milestone(idx)
        if self.tab_bar.currentIndex() == 2:
            self.progress_page._refresh()

    def _on_milestone_edit(self, idx):
        self.progress_page._edit_milestone(self.progress_page._current_project, idx)

    def _on_milestone_data_changed(self):
        self._refresh_nav_milestones()
        self.progress_page._refresh()
        self.save_data()

    def save_data(self):
        path = self._save_path()
        if not path:
            return
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            g = self.geometry()
            payload = {
                "projects":   self.nav.get_projects(),
                "shots":      self.shots_page.get_data(),
                "assets":     self.assets_page.get_data(),
                "milestones": self.progress_page.get_milestones(),
                "production": self.progress_page.get_production(),
                "artists":    self.artists_page.get_data(),
                "window":     {"x": g.x(), "y": g.y(), "w": g.width(), "h": g.height()},
            }
            with open(path + ".tmp", "w") as f:
                json.dump(payload, f, indent=4)
            os.replace(path + ".tmp", path)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Save Error", str(e))

    def load_data(self):
        path = self._save_path()
        if not path or not os.path.exists(path):
            return
        try:
            with open(path, "r") as f:
                saved = json.load(f)

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
                self.progress_page.project_added(p)
            self.shots_page.load_data(saved.get("shots", {}))
            self.assets_page.load_data(saved.get("assets", {}))
            self.progress_page.load_milestones(saved.get("milestones", {}))
            self.progress_page.load_production(saved.get("production", {}))
            self.artists_page.load_data(saved.get("artists", []))
            win = saved.get("window", {})
            if win:
                self.setGeometry(
                    win.get("x", 100), win.get("y", 100),
                    win.get("w", 1200), win.get("h", 900)
                )
            if projects:
                self._on_project_changed(projects[0])
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Load Error", str(e))

    def _update_project_banner(self):
        workspace = cmds.workspace(query=True, rootDirectory=True).rstrip("/\\")
        project_name = os.path.basename(workspace)
        if not project_name or project_name == "default":
            self._project_banner.setText("Project:  No project set")
            self._project_banner.setStyleSheet(
                f"background:#1a1a1a; color:#e05050; font-size:15px; font-weight:bold;"
                f"padding-left:16px; border-bottom:1px solid {BORDER};"
            )
        else:
            self._project_banner.setText(f"Project:  {project_name}")
            self._project_banner.setStyleSheet(
                f"background:#1a1a1a; color:#4caf50; font-size:15px; font-weight:bold;"
                f"padding-left:16px; border-bottom:1px solid {BORDER};"
            )

    def _save_path(self):
        if not self._data_dir:
            return None
        os.makedirs(self._data_dir, exist_ok=True)
        return os.path.join(self._data_dir, "jiffyschedule.json")

    def _prompt_data_dir(self):
        QtWidgets.QMessageBox.information(
            self, "JiffySchedule — Choose data folder",
            "Please choose a folder where JiffySchedule will store your project data.\n"
            "This only needs to be done once.",
        )
        self._choose_data_dir()

    def _choose_data_dir(self):
        start = self._data_dir or os.path.expanduser("~")
        d = QtWidgets.QFileDialog.getExistingDirectory(
            self, "JiffySchedule — Choose data folder", start,
        )
        if d:
            self._data_dir = d
            cmds.optionVar(sv=(_DATA_DIR_PREF, d))
            self.load_data()

    def closeEvent(self, event):
        global _jiffyschedule_window
        _jiffyschedule_window = None
        if self._workspace_job is not None:
            try:
                cmds.scriptJob(kill=self._workspace_job, force=True)
            except Exception:
                pass
            self._workspace_job = None
        super().closeEvent(event)

    def _make_dockable(self):
        ptr = omui.MQtUtil.mainWindow()
        if ptr:
            maya_win = wrapInstance(int(ptr), QtWidgets.QMainWindow)
            self.setParent(maya_win)
            self.setWindowFlags(QtCore.Qt.Window)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
_jiffyschedule_window = None

def run_jiffyschedule():
    global _jiffyschedule_window
    if _jiffyschedule_window is not None:
        try:
            _jiffyschedule_window.raise_()
            _jiffyschedule_window.activateWindow()
            return _jiffyschedule_window
        except RuntimeError:
            _jiffyschedule_window = None
    _jiffyschedule_window = JiffySchedule()
    _jiffyschedule_window.show()
    _jiffyschedule_window.raise_()
    return _jiffyschedule_window


if __name__ == "__main__":
    run_jiffyschedule()
