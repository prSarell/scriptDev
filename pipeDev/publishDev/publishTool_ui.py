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
import re

import maya.cmds as cmds
from maya import OpenMayaUI as omui
from PySide6 import QtWidgets, QtCore, QtGui
import shiboken6

_DIR = os.path.dirname(__file__)
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

import publishTool_api as api
import publishTool_camera as cam
import publishTool_anim as anim


# Departments that can publish an asset scene today. The rest (shot work:
# Previs, Anim, FX, Render) show as "coming soon" until shot publishing exists.
LIVE_DEPARTMENTS = ("model", "rig", "creature", "lookDev")
# What a shot scene can publish: its camera (spec §3i "Cameras") and its
# animation (spec §4 "Shot (animation) publish v0").
SHOT_DEPARTMENTS = [(cam.CAM_LABEL, cam.CAM_CODE), (anim.ANIM_LABEL, anim.ANIM_CODE)]
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
        self._rows = []     # [{asset_type, asset, code, objects, uuids}]
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
        self.add_btn = QtWidgets.QPushButton("Add to List")
        self.add_btn.clicked.connect(self._add_row)
        self.asset_lbl = QtWidgets.QLabel("Asset:")
        self.dept_lbl = QtWidgets.QLabel("Department:")
        # In a shot scene there's nothing to pick: Publish works out what
        # each selected thing is (spec §4 item 6a).
        self.shot_hint = QtWidgets.QLabel(
            "Select everything you want to publish in Maya (cameras, characters, "
            "props...) and click Add Selected. The tool works out what each one is.")
        self.shot_hint.setWordWrap(True)
        # Which stage a shot publish is for (Layout / Animation; Lighting and
        # FX later). It sets the approval needed and where things go.
        self.publish_for_lbl = QtWidgets.QLabel("Publish for:")
        self.publish_for_combo = QtWidgets.QComboBox()
        model = QtGui.QStandardItemModel(self.publish_for_combo)
        for label, code, live in anim.PUBLISH_FOR:
            item = QtGui.QStandardItem(label if live else "%s (coming soon)" % label)
            item.setData(code, QtCore.Qt.UserRole)
            item.setEnabled(live)
            model.appendRow(item)
        self.publish_for_combo.setModel(model)
        self.publish_for_combo.setCurrentIndex(
            self.publish_for_combo.findData(anim.ANIM_CODE))
        self.publish_for_combo.setToolTip(
            "Layout: publishes the camera and what's selected; never caches.\n"
            "Animation: the same, plus caches once a publish is approved for Final.\n"
            "Ask for approval in the notes (e.g. \"please approve for lighting\").")
        self.publish_for_combo.currentIndexChanged.connect(lambda *_: self._render_table())
        pick = QtWidgets.QHBoxLayout()
        pick.addWidget(self.asset_lbl)
        pick.addWidget(self.asset_combo, 1)
        pick.addWidget(self.dept_lbl)
        pick.addWidget(self.dept_combo)
        pick.addWidget(self.publish_for_lbl)
        pick.addWidget(self.publish_for_combo)
        pick.addWidget(self.shot_hint, 1)
        pick.addWidget(self.add_btn)

        # The publish list.
        self.table = QtWidgets.QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Asset / Shot", "Type", "Department", "Objects", "Publishes as"])
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.objects_btn = QtWidgets.QPushButton("Set Objects from Selection")
        self.objects_btn.setToolTip("Publish only the objects selected in Maya (and "
                                    "their children) for the selected row(s).")
        self.objects_btn.clicked.connect(self._set_objects)
        self.whole_btn = QtWidgets.QPushButton("Whole Scene")
        self.whole_btn.setToolTip("Publish the whole scene file for the selected row(s).")
        self.whole_btn.clicked.connect(self._clear_objects)
        remove_btn = QtWidgets.QPushButton("Remove from List")
        remove_btn.clicked.connect(self._remove_rows)
        list_btns = QtWidgets.QHBoxLayout()
        list_btns.addWidget(self.objects_btn)
        list_btns.addWidget(self.whole_btn)
        list_btns.addStretch(1)
        list_btns.addWidget(remove_btn)

        # shotSub of each publish: 2 frames by default, more if wanted.
        self.frames_spin = QtWidgets.QSpinBox()
        self.frames_spin.setRange(1, 10000)
        self.frames_spin.setValue(2)
        self.frames_spin.setToolTip("How many frames to playblast for ShotGrid, "
                                    "from the start of the playback range.\n"
                                    "Asset publishes only: shot publishes (e.g. "
                                    "Camera) always use the whole timeline.")
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
        # The scratch drive follows the open scene (spec "Scratch drive
        # follows the work"); the saved setting is only the fallback.
        moved = api.follow_open_scene(*self._roots())
        if moved:
            self.root_edits[api.SCRATCH].setText(moved)
            self.status.show_message("Scratch drive set to %s, where the open scene is." % moved)
        scene, ctx = self._scene_context()
        try:
            login = api.who()
        except api.PublishError:
            login = "?"
        # Publishes are personal: say whose folder and name they'll go under.
        self.scene_lbl.setText("%s\nPublishing as: %s" % (scene or "(unsaved scene)", login))
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
            # Start on the department the file name says (scout_rig_v002 ->
            # Rigging), so a rig isn't published as a model by default.
            words = re.split(r"[_.]", os.path.basename(scene).lower())
            for code in LIVE_DEPARTMENTS:
                if code.lower() in words and self.dept_combo.findData(code) >= 0:
                    self.dept_combo.setCurrentIndex(self.dept_combo.findData(code))
                    break
            self._set_frame_defaults(ctx)
            self._set_shot_mode(bool(ctx) and ctx["kind"] == "shot")
        self._render_table()

    def _set_shot_mode(self, shot):
        """Shot scene: no Asset/Department pickers, one Add Selected button.
        Asset scene: pick the asset and department as before."""
        for widget in (self.asset_lbl, self.asset_combo, self.dept_lbl, self.dept_combo,
                       self.objects_btn, self.whole_btn):
            widget.setVisible(not shot)
        for widget in (self.shot_hint, self.publish_for_lbl, self.publish_for_combo):
            widget.setVisible(shot)
        self.add_btn.setText("Add Selected" if shot else "Add to List")
        self.add_btn.setToolTip(
            "Add everything selected in Maya. Cameras publish as the shot camera; "
            "published assets and things made in the shot publish their animation."
            if shot else
            "Add this asset to the publish list. Whatever is selected in Maya is what "
            "gets published; with nothing selected, the whole scene is.")

    def _set_frame_defaults(self, ctx):
        """ShotSub frames for a newly opened scene: a shot scene uses the
        whole timeline (and always does, spec "Shot publishes"), an asset
        scene starts at 2 frames."""
        shot = bool(ctx) and ctx["kind"] == "shot"
        self.timeline_chk.setChecked(shot)
        self.timeline_chk.setEnabled(not shot)
        self.timeline_chk.setToolTip(
            "Shot publishes always playblast the whole timeline." if shot
            else "Playblast the whole playback range instead.")
        if not shot:
            self.frames_spin.setValue(2)

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
        if row["code"] == anim.ANIM_CODE:
            return anim.plan_anim(scene, *self._roots(), items=anim.classify(row["objects"]),
                                  publish_for=self._publish_for())
        return api.plan_publish(scene, *self._roots(), code=row["code"],
                                target=(row["asset_type"], row["asset"]))

    def _publish_for(self):
        """The shot publish's stage: anim.LAYOUT_CODE or anim.ANIM_CODE."""
        return self.publish_for_combo.currentData() or anim.ANIM_CODE

    def _sync_objects(self):
        """Rows remember their objects by UUID, so renaming or reparenting
        one in Maya after adding it doesn't break the row: pick up the
        current names. An object that's been deleted keeps its old name,
        and Publish reports it as no longer in the scene."""
        for row in self._rows:
            uuids = row.get("uuids") or []
            if len(uuids) != len(row["objects"]):
                continue    # no UUIDs recorded: keep the names as they are
            row["objects"] = [(cmds.ls(uuid) or [old])[0]
                              for uuid, old in zip(uuids, row["objects"])]

    def _render_table(self):
        self._sync_objects()
        scene, ctx = self._scene_context()
        self.table.setRowCount(len(self._rows))
        problems = []
        try:
            api.check_script_nodes()    # also checked again on Publish
        except api.PublishError as e:
            problems.append(str(e))
        for r, row in enumerate(self._rows):
            type_label = row.get("type_label", row["asset_type"])
            objects = ", ".join(row["objects"]) if row["objects"] else "(whole scene)"
            item = None
            if row["code"] == anim.ANIM_CODE:
                try:
                    item = anim.classify(row["objects"])[0]
                    type_label = ("made in the shot" if item["kind"] == "shot" else
                                  "%s v%03d" % (item["kind"], item["stamp"].get("version") or 0))
                    objects = "%s (%s)" % (objects, "keyed" if item["animated"] else "no keys")
                except api.PublishError:
                    pass        # shown as "can't publish" in the last column
            self.table.setItem(r, 0, _cell(row["asset"]))
            self.table.setItem(r, 1, _cell(type_label))
            self.table.setItem(r, 2, _cell(
                anim.PUBLISH_FOR_LABELS[self._publish_for()] if row["code"] == anim.ANIM_CODE
                else DEPT_LABELS[row["code"]]))
            self.table.setItem(r, 3, _cell(objects, None if row["objects"] else "#999999"))
            try:
                plan = self._plan(row)
                dest, text = plan["dest"], os.path.basename(plan["dest"])
                if row["code"] == cam.CAM_CODE:
                    text += "  + keys"
                    dest += "\n" + plan["keys_dest"]
                elif row["code"] == anim.ANIM_CODE:
                    files = plan["item_files"][item["name"]]
                    text = (os.path.basename(files["keys"]) + "  + map" if item["animated"]
                            else "in the full shot file only (no keys)")
                    dest = "\n".join(
                        ["Full shot file: " + plan["dest"]] +
                        ([files["keys"], files["map"]] if item["animated"] else []) +
                        (["If the shot's Final is approved, also: " + files["cache"]]
                         if self._publish_for() == anim.ANIM_CODE else []))
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

    def _add_selected_in_shot(self, shot):
        """Shot scene: every selected thing becomes a row, sorted by what it
        is. Cameras -> a Camera row each; published assets (pipe stamp) and
        things made in the shot -> an Animation item each. Things that can't
        be published are reported; the rest are still added."""
        selection = cmds.ls(selection=True, long=True) or []
        if not selection:
            self.status.show_message("Select what you want to publish in Maya first.", ok=False)
            return
        have = set(u for r in self._rows for u in r.get("uuids") or [])
        added, problems = [], []
        for node in selection:
            camera = cam.camera_transform(node) or cam.camera_in_group(node)
            try:
                if camera:
                    cam.check_camera([camera])
                    uuid = cmds.ls(camera, uuid=True)[0]
                    row = {"asset_type": "shot", "asset": shot, "code": cam.CAM_CODE,
                           "objects": [cmds.ls(camera)[0]], "uuids": [uuid],
                           "type_label": "camera"}
                else:
                    item = anim.classify([node])[0]
                    uuid = cmds.ls(item["root"], uuid=True)[0]
                    row = {"asset_type": "shot", "asset": item["name"], "code": anim.ANIM_CODE,
                           "objects": [cmds.ls(item["root"])[0]], "uuids": [uuid]}
            except api.PublishError as e:
                problems.append(str(e))
                continue
            if uuid in have:
                continue        # already in the list (or a child of something that is)
            have.add(uuid)
            self._rows.append(row)
            added.append(row["asset"])
        self._render_table()
        lines = (["Added: %s" % ", ".join(added)] if added else
                 ["Nothing new to add." if not problems else ""])
        self.status.show_message("\n".join([l for l in lines if l] + problems),
                                 ok=not problems)

    def _add_row(self):
        scene, ctx = self._scene_context()
        if ctx and ctx["kind"] == "shot":
            return self._add_selected_in_shot(ctx["shot"])
        data, code = self.asset_combo.currentData(), self.dept_combo.currentData()
        if not data or code not in LIVE_DEPARTMENTS + (cam.CAM_CODE, anim.ANIM_CODE):
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
                           "code": code, "objects": list(selection),
                           "uuids": cmds.ls(selection, uuid=True) if selection else []})
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
        if code == anim.ANIM_CODE:
            # Publish works out what each thing is (spec item 6a).
            try:
                anim.classify(objects)
            except api.PublishError as e:
                return str(e)
            return None
        cameras = cam.contains_camera(objects)
        if cameras:
            return ("Cameras are published to their shot, not to an asset: %s\n"
                    "Open the shot scene and use a Camera row." % ", ".join(cameras))
        if code == api.MODEL_CODE:
            try:
                api.check_not_a_rig(objects)
            except api.PublishError as e:
                return str(e)
        if code == api.RIG_CODE:
            # Rigs must carry a hand-made cache_SET (spec "cache_SET") and
            # control sets (spec "Rig sets: controls and render geo").
            try:
                import publishTool_textures as tex
                api.check_cache_set(objects)
                api.check_control_sets(objects)
                tex.collect(objects)        # missing textures
            except api.PublishError as e:
                return str(e)
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
            self._rows[r]["uuids"] = cmds.ls(selection, uuid=True)
        self._render_table()

    def _clear_objects(self):
        for r in self._selected_rows():
            if self._rows[r]["code"] == cam.CAM_CODE:
                self.status.show_message("A Camera row always publishes just its camera.",
                                         ok=False)
                continue
            if self._rows[r]["code"] == anim.ANIM_CODE:
                self.status.show_message("An Animation row publishes what you select: select "
                                         "it in Maya and use Set Objects from Selection.", ok=False)
                continue
            self._rows[r]["objects"] = []
            self._rows[r]["uuids"] = []
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
        self._sync_objects()    # anything renamed since the last refresh
        frame_count = None if self.timeline_chk.isChecked() else self.frames_spin.value()
        notes = self.notes_edit.toPlainText().strip()
        lines, ok = [], True
        # All the Animation items in a shot go out as ONE publish (one shared
        # version number, spec item 1), so they become a single job here.
        anim_rows = [r for r in self._rows if r["code"] == anim.ANIM_CODE]
        jobs = [r for r in self._rows if r["code"] != anim.ANIM_CODE]
        if anim_rows:
            jobs.append({"asset_type": "shot", "asset": ", ".join(r["asset"] for r in anim_rows),
                         "code": anim.ANIM_CODE,
                         "objects": [r["objects"][0] for r in anim_rows]})
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        try:
            for row in jobs:
                label = "%s %s" % (row["asset"], row["code"])
                # Anything published under a shot (cameras, characters' anim,
                # ...) always uses the whole timeline (spec "Shot publishes").
                frames = None if row["asset_type"] == "shot" else frame_count
                try:
                    if row["code"] == cam.CAM_CODE:
                        plan = cam.publish_camera(scene, *self._roots(),
                                                  camera=row["objects"][0],
                                                  frame_count=frames, notes=notes,
                                                  publish_for=self._publish_for())
                    elif row["code"] == anim.ANIM_CODE:
                        plan = anim.publish_anim(scene, *self._roots(),
                                                 objects=row["objects"], notes=notes,
                                                 publish_for=self._publish_for())
                        label = "%s %s" % (row["asset"],
                                           anim.PUBLISH_FOR_LABELS[self._publish_for()])
                        label += {
                            anim.FINAL: " (Final approved: caches made)",
                            anim.ANIMATION: " (no caches yet: they're made once a publish "
                                            "is approved for Final)",
                        }.get(plan["stage"], "")
                    else:
                        plan = api.publish(scene, *self._roots(), code=row["code"],
                                           frame_count=frames, notes=notes,
                                           objects=row["objects"],
                                           target=(row["asset_type"], row["asset"]))
                except Exception as e:
                    lines.append("%s: FAILED — nothing published:\n  %s" % (label, e))
                    ok = False
                    continue
                version = "v%03d (%s)" % (plan["version"], plan["login"])
                if plan["sg_error"]:
                    lines.append("%s: %s saved to the H drive, but the ShotGrid "
                                 "upload failed:\n  %s" % (label, version, plan["sg_error"]))
                    ok = False
                else:
                    entity = plan.get("sg_asset") or plan.get("sg_shot")
                    lines.append("%s: published %s to the H drive and ShotGrid (%s)"
                                 % (label, version, entity["code"]))
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
