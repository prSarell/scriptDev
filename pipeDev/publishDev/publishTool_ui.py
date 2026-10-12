"""
Publish Tool — UI
Same layout as the Build tool: pick an Asset + Department, add it to a
list, and one Publish click publishes every row (spec §3i). Each row is
one publish: its own asset, department and objects (empty = whole scene).

Needs shotgridConnect (ships with shotSub) for the ShotGrid step.

Dev launch (Script Editor, Python tab):

    import sys, importlib
    for p in (r"C:\\Users\\scout\\Documents\\maya\\scriptDev\\shelfDev\\mpAnim\\tools",
              r"C:\\Users\\scout\\Documents\\maya\\scriptDev\\pipeDev\\publishDev"):
        if p not in sys.path: sys.path.insert(0, p)
    import publishTool_api, publishTool_camera, publishTool_ui
    for m in (publishTool_api, publishTool_camera, publishTool_ui): importlib.reload(m)
    publishTool_ui.show()
"""

import sys
import os

import maya.cmds as cmds
from maya import OpenMayaUI as omui
from PySide6 import QtWidgets, QtCore, QtGui
import shiboken6

_DIR = os.path.dirname(__file__)
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

import publishTool_api as api
import publishTool_camera as cam


# Departments that can publish an asset scene today. The rest (shot work:
# Previs, Anim, FX, Render) show as "coming soon" until shot publishing exists.
LIVE_DEPARTMENTS = ("model", "rig", "creature", "lookDev")
# What a shot scene can publish today: its camera (spec §3i "Cameras").
SHOT_DEPARTMENTS = [(cam.CAM_LABEL, cam.CAM_CODE)]
DEPT_LABELS = dict((c, l) for l, c in api.DEPARTMENTS + SHOT_DEPARTMENTS)


def _maya_main_window():
    ptr = omui.MQtUtil.mainWindow()
    return shiboken6.wrapInstance(int(ptr), QtWidgets.QWidget)


class StatusLabel(QtWidgets.QLabel):
    """Selectable message line, with right-click Copy; also prints to the
    Script Editor so messages can always be copied."""

    def __init__(self, parent=None):
        super(StatusLabel, self).__init__(parent)
        self.setWordWrap(True)
        self.setTextInteractionFlags(
            QtCore.Qt.TextSelectableByMouse | QtCore.Qt.TextSelectableByKeyboard)
        self.setContextMenuPolicy(QtCore.Qt.ActionsContextMenu)
        action = QtGui.QAction("Copy message", self)
        action.triggered.connect(
            lambda: QtWidgets.QApplication.clipboard().setText(self._text))
        self.addAction(action)
        self._text = ""

    def show_message(self, text, ok=True):
        self._text = text
        colour = "#7fbf7f" if ok else "#e0a060"
        self.setText('<span style="color:%s">%s</span>' % (colour, text.replace("\n", "<br>")))
        if text:
            print("Publish Tool: %s" % text)


def _cell(text, colour=None):
    item = QtWidgets.QTableWidgetItem(text)
    if colour:
        item.setForeground(QtGui.QColor(colour))
    return item


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class PublishToolUI(QtWidgets.QDialog):

    def __init__(self, parent=None):
        super(PublishToolUI, self).__init__(parent or _maya_main_window())
        self.setWindowTitle("Publish Tool")
        self.setObjectName("publishToolUI")
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.Window)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.resize(780, 520)
        self._rows = []     # [{asset_type, asset, code, objects}]
        self._picker_key = None

        # Drive locations: settings, so the tool works on any drive setup
        # (home test rig, RMIT). Either the drive or its film folder is fine.
        roots = QtWidgets.QFormLayout()
        self.root_edits = {}
        for key, label, hint in (
                (api.H_DRIVE, "H drive:", "where publishes go, e.g. H:\\  or  F:\\"),
                (api.SCRATCH, "Scratch drive:", "where you work, e.g. D:\\")):
            edit = QtWidgets.QLineEdit(api.get_root(key))
            edit.setPlaceholderText(hint)
            edit.editingFinished.connect(lambda k=key: self._on_root_edited(k))
            browse_btn = QtWidgets.QPushButton("Browse...")
            browse_btn.clicked.connect(lambda checked=False, k=key: self._browse_root(k))
            row = QtWidgets.QHBoxLayout()
            row.addWidget(edit, 1)
            row.addWidget(browse_btn)
            roots.addRow(label, row)
            self.root_edits[key] = edit

        # The scene being published from.
        self.scene_lbl = QtWidgets.QLabel()
        self.scene_lbl.setWordWrap(True)
        self.scene_lbl.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        scene_row = QtWidgets.QHBoxLayout()
        scene_row.addWidget(QtWidgets.QLabel("Scene:"))
        scene_row.addWidget(self.scene_lbl, 1)

        # Which asset + department to add to the list.
        self.asset_combo = QtWidgets.QComboBox()
        self.asset_combo.setMinimumWidth(200)
        self.dept_combo = QtWidgets.QComboBox()
        self.asset_combo.currentIndexChanged.connect(self._fill_departments)
        add_btn = QtWidgets.QPushButton("Add to List")
        add_btn.setToolTip("Add this asset to the publish list. Whatever is "
                           "selected in Maya is what gets published; with "
                           "nothing selected, the whole scene is. For a shot's "
                           "Camera, select the camera.")
        add_btn.clicked.connect(self._add_row)
        pick = QtWidgets.QHBoxLayout()
        pick.addWidget(QtWidgets.QLabel("Asset:"))
        pick.addWidget(self.asset_combo, 1)
        pick.addWidget(QtWidgets.QLabel("Department:"))
        pick.addWidget(self.dept_combo)
        pick.addWidget(add_btn)

        # The publish list.
        self.table = QtWidgets.QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Asset / Shot", "Type", "Department", "Objects", "Publishes as"])
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        objects_btn = QtWidgets.QPushButton("Set Objects from Selection")
        objects_btn.setToolTip("Publish only the objects selected in Maya (and "
                               "their children) for the selected row(s).")
        objects_btn.clicked.connect(self._set_objects)
        whole_btn = QtWidgets.QPushButton("Whole Scene")
        whole_btn.setToolTip("Publish the whole scene file for the selected row(s).")
        whole_btn.clicked.connect(self._clear_objects)
        remove_btn = QtWidgets.QPushButton("Remove from List")
        remove_btn.clicked.connect(self._remove_rows)
        list_btns = QtWidgets.QHBoxLayout()
        list_btns.addWidget(objects_btn)
        list_btns.addWidget(whole_btn)
        list_btns.addStretch(1)
        list_btns.addWidget(remove_btn)

        # shotSub of each publish: 2 frames by default, more if wanted.
        self.frames_spin = QtWidgets.QSpinBox()
        self.frames_spin.setRange(1, 10000)
        self.frames_spin.setValue(2)
        self.frames_spin.setToolTip("How many frames to playblast for ShotGrid, "
                                    "from the start of the playback range.")
        self.timeline_chk = QtWidgets.QCheckBox("Timeline")
        self.timeline_chk.setToolTip("Playblast the whole playback range instead.")
        self.timeline_chk.toggled.connect(lambda on: self.frames_spin.setEnabled(not on))
        frames_row = QtWidgets.QHBoxLayout()
        frames_row.addWidget(QtWidgets.QLabel("ShotSub frames:"))
        frames_row.addWidget(self.frames_spin)
        frames_row.addWidget(self.timeline_chk)
        frames_row.addStretch(1)

        # Notes go to ShotGrid as a Note on the Version, like shotSub's.
        self.notes_edit = QtWidgets.QPlainTextEdit()
        self.notes_edit.setPlaceholderText(
            'e.g. "UVs done, ready for lookDev" -- posted to ShotGrid with '
            "every row in this publish.")
        self.notes_edit.setFixedHeight(60)

        self.publish_btn = QtWidgets.QPushButton("Publish")
        self.publish_btn.setMinimumHeight(36)
        self.publish_btn.setToolTip(
            "For every row: playblast for ShotGrid, save the publish to the H "
            "drive, and send the shotSub to ShotGrid.")
        self.publish_btn.clicked.connect(self._publish)

        self.status = StatusLabel()

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(roots)
        layout.addLayout(scene_row)
        layout.addLayout(pick)
        layout.addWidget(self.table, 1)
        layout.addLayout(list_btns)
        layout.addLayout(frames_row)
        layout.addWidget(QtWidgets.QLabel("Notes (sent to ShotGrid with this publish):"))
        layout.addWidget(self.notes_edit)
        layout.addWidget(self.publish_btn)
        layout.addWidget(self.status)

        self.refresh()

    # -- settings ---------------------------------------------------------

    def _root(self, key):
        return api.resolve_root(self.root_edits[key].text().strip())

    def _roots(self):
        return self._root(api.H_DRIVE), self._root(api.SCRATCH)

    def _on_root_edited(self, key):
        if self._root(key):
            api.set_root(key, self._root(key))
        self.refresh()

    def _browse_root(self, key):
        name = "H drive" if key == api.H_DRIVE else "scratch drive"
        path = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Choose the %s (the drive, or its film folder)" % name, self._root(key))
        if path:
            self.root_edits[key].setText(os.path.normpath(path))
            self._on_root_edited(key)

    # -- filling ----------------------------------------------------------

    def _scene_context(self):
        """The open scene and what it is: an asset scene or a shot scene."""
        scene = cmds.file(query=True, sceneName=True) or ""
        if not scene:
            return scene, None
        for context in (api.asset_context, cam.shot_context):
            try:
                ctx = context(scene)
            except api.PublishError:
                continue
            ctx.setdefault("kind", "asset")
            return scene, ctx
        return scene, None

    def refresh(self):
        scene, ctx = self._scene_context()
        self.scene_lbl.setText(scene or "(unsaved scene)")
        h_root = self._roots()[0]
        key = (scene, h_root)
        if key != self._picker_key:
            # New scene or H drive: refill the picker, defaulting to the
            # asset whose folder the scene is in.
            self._picker_key = key
            self.asset_combo.blockSignals(True)
            self.asset_combo.clear()
            if ctx and ctx["kind"] == "shot":
                # A shot scene publishes for its own shot only.
                self.asset_combo.addItem("%s  (shot)" % ctx["shot"],
                                         "shot/%s" % ctx["shot"])
            elif ctx and h_root and os.path.isdir(h_root):
                for asset_type, asset in api.list_h_assets(h_root, ctx["film"]):
                    self.asset_combo.addItem("%s  (%s)" % (asset, asset_type),
                                             "%s/%s" % (asset_type, asset))
                index = self.asset_combo.findData(
                    "%s/%s" % (ctx["asset_type"], ctx["asset"]))
                self.asset_combo.setCurrentIndex(max(index, 0))
            self.asset_combo.blockSignals(False)
            self._fill_departments()
        self._render_table()

    def _fill_departments(self, *args):
        """Asset departments for an asset, Camera for a shot."""
        data = self.asset_combo.currentData() or ""
        current = self.dept_combo.currentData()
        model = QtGui.QStandardItemModel(self.dept_combo)
        if data.startswith("shot/"):
            departments, live = SHOT_DEPARTMENTS, [c for _, c in SHOT_DEPARTMENTS]
        else:
            departments, live = api.DEPARTMENTS, LIVE_DEPARTMENTS
        for label, code in departments:
            item = QtGui.QStandardItem(label if code in live else "%s (coming soon)" % label)
            item.setData(code, QtCore.Qt.UserRole)
            item.setEnabled(code in live)
            model.appendRow(item)
        self.dept_combo.setModel(model)
        index = self.dept_combo.findData(current)
        self.dept_combo.setCurrentIndex(max(index, 0))

    def _plan(self, row):
        scene = cmds.file(query=True, sceneName=True)
        if row["code"] == cam.CAM_CODE:
            return cam.plan_camera(scene, *self._roots(), camera=row["objects"][0])
        return api.plan_publish(scene, *self._roots(), code=row["code"],
                                target=(row["asset_type"], row["asset"]))

    def _render_table(self):
        scene, ctx = self._scene_context()
        self.table.setRowCount(len(self._rows))
        problems = []
        for r, row in enumerate(self._rows):
            self.table.setItem(r, 0, _cell(row["asset"]))
            self.table.setItem(r, 1, _cell(row["asset_type"]))
            self.table.setItem(r, 2, _cell(DEPT_LABELS[row["code"]]))
            objects = ", ".join(row["objects"]) if row["objects"] else "(whole scene)"
            self.table.setItem(r, 3, _cell(objects, None if row["objects"] else "#999999"))
            try:
                plan = self._plan(row)
                dest, text = plan["dest"], os.path.basename(plan["dest"])
                if row["code"] == cam.CAM_CODE:
                    text += "  + keys"
                    dest += "\n" + plan["keys_dest"]
                self.table.setItem(r, 4, _cell(text))
                self.table.item(r, 4).setToolTip(dest)
            except api.PublishError as e:
                self.table.setItem(r, 4, _cell("can't publish", "#e0a060"))
                problems.append(str(e))
        self.table.resizeColumnsToContents()

        if not scene:
            self.status.show_message("Save your scene on the scratch drive first.", ok=False)
        elif not ctx:
            self.status.show_message(
                "This scene isn't in an asset's or a shot's scenes folder.\n"
                "Expected <film>\\maya\\assets\\<type>\\<asset>\\scenes\\ or "
                "<film>\\maya\\sequences\\<sequence>\\<shot>\\scenes\\", ok=False)
        elif problems:
            self.status.show_message(problems[0], ok=False)
        elif not self._rows:
            self.status.show_message("")
        self.publish_btn.setEnabled(bool(self._rows) and not problems and bool(ctx))

    # -- list -------------------------------------------------------------

    def _selected_rows(self):
        return sorted(set(i.row() for i in self.table.selectedIndexes()))

    def _add_row(self):
        data, code = self.asset_combo.currentData(), self.dept_combo.currentData()
        if not data or code not in LIVE_DEPARTMENTS + (cam.CAM_CODE,):
            return
        asset_type, asset = data.split("/")
        if any((r["asset_type"], r["asset"], r["code"]) == (asset_type, asset, code)
               for r in self._rows):
            self.status.show_message("%s %s is already in the list."
                                     % (asset, self.dept_combo.currentText()), ok=False)
            return
        # Whatever is selected in Maya becomes this row's objects; nothing
        # selected = the whole scene.
        selection = cmds.ls(selection=True) or []
        problem = self._check_objects(code, selection)
        if problem:
            self.status.show_message(problem, ok=False)
            return
        self._rows.append({"asset_type": asset_type, "asset": asset,
                           "code": code, "objects": list(selection)})
        self._render_table()
        self.status.show_message(
            "Added %s %s: %s" % (asset, self.dept_combo.currentText(),
                                 ", ".join(selection) if selection else "whole scene"))

    @staticmethod
    def _check_objects(code, objects):
        """Cameras only go to their shot (spec "Cameras"): a Camera row
        takes exactly one camera, an asset row never takes one."""
        if code == cam.CAM_CODE:
            try:
                cam.check_camera(objects)
            except api.PublishError as e:
                return str(e)
            return None
        cameras = cam.contains_camera(objects)
        if cameras:
            return ("Cameras are published to their shot, not to an asset: %s\n"
                    "Open the shot scene and use a Camera row." % ", ".join(cameras))
        return None

    def _set_objects(self):
        selection = cmds.ls(selection=True) or []
        rows = self._selected_rows()
        if not rows or not selection:
            self.status.show_message("Select row(s) in the list and object(s) in Maya first.",
                                     ok=False)
            return
        for r in rows:
            problem = self._check_objects(self._rows[r]["code"], selection)
            if problem:
                self.status.show_message(problem, ok=False)
                return
        for r in rows:
            self._rows[r]["objects"] = list(selection)
        self._render_table()

    def _clear_objects(self):
        for r in self._selected_rows():
            if self._rows[r]["code"] == cam.CAM_CODE:
                self.status.show_message("A Camera row always publishes just its camera.",
                                         ok=False)
                continue
            self._rows[r]["objects"] = []
        self._render_table()

    def _remove_rows(self):
        for r in reversed(self._selected_rows()):
            del self._rows[r]
        self._render_table()

    # -- publish ----------------------------------------------------------

    def _publish(self):
        if cmds.file(query=True, modified=True):
            answer = QtWidgets.QMessageBox.question(
                self, "Unsaved changes",
                "Your scene has unsaved changes.\n"
                "Save it now and publish the saved version?")
            if answer != QtWidgets.QMessageBox.Yes:
                return
            cmds.file(save=True)

        scene = cmds.file(query=True, sceneName=True)
        frame_count = None if self.timeline_chk.isChecked() else self.frames_spin.value()
        notes = self.notes_edit.toPlainText().strip()
        lines, ok = [], True
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        try:
            for row in self._rows:
                label = "%s %s" % (row["asset"], row["code"])
                try:
                    if row["code"] == cam.CAM_CODE:
                        plan = cam.publish_camera(scene, *self._roots(),
                                                  camera=row["objects"][0],
                                                  frame_count=frame_count, notes=notes)
                    else:
                        plan = api.publish(scene, *self._roots(), code=row["code"],
                                           frame_count=frame_count, notes=notes,
                                           objects=row["objects"],
                                           target=(row["asset_type"], row["asset"]))
                except Exception as e:
                    lines.append("%s: FAILED — nothing published:\n  %s" % (label, e))
                    ok = False
                    continue
                if plan["sg_error"]:
                    lines.append("%s: v%03d saved to the H drive, but the ShotGrid "
                                 "upload failed:\n  %s" % (label, plan["version"], plan["sg_error"]))
                    ok = False
                else:
                    entity = plan.get("sg_asset") or plan.get("sg_shot")
                    lines.append("%s: published v%03d to the H drive and ShotGrid (%s)"
                                 % (label, plan["version"], entity["code"]))
                for warning in plan.get("warnings") or []:
                    lines.append("  " + warning)
                if plan["movie_warning"]:
                    lines.append("  " + plan["movie_warning"])
                    ok = False
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        if ok:
            # Kept after a failure so the student doesn't have to retype them.
            self.notes_edit.clear()
        self._render_table()
        self.status.show_message("\n".join(lines), ok=ok)

    def changeEvent(self, event):
        # Re-check the open scene whenever the window is brought forward.
        if event.type() == QtCore.QEvent.ActivationChange and self.isActiveWindow():
            self.refresh()
        super(PublishToolUI, self).changeEvent(event)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

_instance = None


def show():
    global _instance
    if _instance is not None:
        try:
            _instance.close()
        except RuntimeError:
            pass
    _instance = PublishToolUI()
    _instance.show()
    return _instance
