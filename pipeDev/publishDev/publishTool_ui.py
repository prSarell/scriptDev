"""
Publish Tool — UI
Same layout as the Build tool: the picker row (pipePicker: Film, Asset or Shot,
Department, Type or Sequence, Asset or Shot) adds to a
list with +, and one Publish click publishes every ticked row (spec §3i).
Each row is one publish: its own asset, department and objects (empty =
whole scene).

Needs shotgridConnect (ships with shotSub) for the ShotGrid step.

Dev launch (Script Editor, Python tab):

    import sys, importlib
    for p in (r"C:\\Users\\scout\\Documents\\maya\\scriptDev\\shelfDev\\mpAnim\\tools",
              r"C:\\Users\\scout\\Documents\\maya\\scriptDev\\pipeDev\\publishDev"):
        if p not in sys.path: sys.path.insert(0, p)
    import publishTool_api, publishTool_camera, pipePicker, publishTool_ui
    for m in (publishTool_api, publishTool_camera, pipePicker, publishTool_ui): importlib.reload(m)
    publishTool_ui.show()
"""

import sys
import os
import re
import subprocess

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
import publishTool_env as env
import pipeStudioLibrary as slib
import pipePicker as picker


# Departments that publish from an asset scene. Environment isn't one of
# them (user, 2026-10-26: it's a kind of asset, not a department): from an
# asset scene, an environment asset with an environment_SET publishes as an
# environment by itself; from a shot scene it's picked beside Layout.
LIVE_DEPARTMENTS = ("model", "rig", "creature", "lookDev")
# What a shot scene can publish: its camera (spec §3i "Cameras") and its
# animation (spec §4 "Shot (animation) publish v0").
SHOT_DEPARTMENTS = [(cam.CAM_LABEL, cam.CAM_CODE), (anim.ANIM_LABEL, anim.ANIM_CODE)]
DEPT_LABELS = dict((c, l) for l, c in api.DEPARTMENTS + SHOT_DEPARTMENTS)
# The picker's Department dropdown (user, 2026-10-22): the asset
# departments, then the stages a shot publishes for (Layout / Animation;
# Lighting and FX later), which set the approval needed and where things go.
# Environment sits after Layout: a shot's layout scene publishes its
# environment_SET to the environment asset picked in the last two dropdowns.
PICKER_DEPARTMENTS = (
    [(label, code, picker.ASSET, True) for label, code in api.DEPARTMENTS
     if code in LIVE_DEPARTMENTS] +
    [(label, code, picker.SHOT, live) for label, code, live in anim.PUBLISH_FOR])
PICKER_DEPARTMENTS.insert(len(LIVE_DEPARTMENTS) + 1,
                          (env.ENV_LABEL, env.ENV_CODE, picker.SHOT, True, picker.ASSET))
# ShotSub frames for an environment published from a shot scene.
ENV_SHOT_FRAMES = 2


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


class ReviewDialog(QtWidgets.QDialog):
    """Plays a publish's movie in RV as a reminder to watch it, and asks
    Publish or Cancel. Nothing waits on RV (user, 2026-10-22): both
    buttons work straight away, and closing RV brings this window back to
    the front. Modal, so the scene can't change in the meantime."""

    def __init__(self, movie, title, no_movie_reason="", parent=None):
        super(ReviewDialog, self).__init__(parent)
        self.setWindowTitle("Watch before publishing")
        self._title = title
        self._proc = None
        self.label = QtWidgets.QLabel()
        self.label.setWordWrap(True)
        self.label.setMinimumWidth(360)
        self.publish_btn = QtWidgets.QPushButton("Publish")
        self.publish_btn.setDefault(True)
        self.publish_btn.clicked.connect(self.accept)
        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons = QtWidgets.QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self.publish_btn)
        buttons.addWidget(cancel_btn)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.label)
        layout.addLayout(buttons)

        rv = api.find_rv()
        if movie and rv:
            try:
                self._proc = subprocess.Popen([rv, movie])
            except OSError as e:
                no_movie_reason = "RV wouldn't open: %s" % e
        if self._proc:
            self.label.setText("Playing %s in RV.\nPublish or cancel whenever you're ready."
                               % title)
            self._timer = QtCore.QTimer(self)
            self._timer.timeout.connect(self._poll)
            self._timer.start(300)
        else:
            if not movie:
                no_movie_reason = no_movie_reason or "No movie was made."
            elif not rv:
                no_movie_reason = "RV wasn't found on this machine."
            self.label.setText("Can't show the movie for %s: %s\nPublish anyway?"
                               % (title, no_movie_reason))
        self.publish_btn.setFocus()

    def _poll(self):
        """RV closed: bring the Publish / Cancel question to the front."""
        if self._proc.poll() is None:
            return
        self._timer.stop()
        self.label.setText("Publish %s?" % self._title)
        self.raise_()
        self.activateWindow()


def _cell(text, colour=None):
    item = QtWidgets.QTableWidgetItem(text)
    if colour:
        item.setForeground(QtGui.QColor(colour))
    return item


def _check_cell(text, checked):
    """A row's first cell: its name with the tick that says it's published."""
    item = _cell(text)
    item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
                  | QtCore.Qt.ItemIsUserCheckable)
    item.setCheckState(QtCore.Qt.Checked if checked else QtCore.Qt.Unchecked)
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

        # What to add to the list (user, 2026-10-22): Film | Asset or Shot |
        # Department | Type or Sequence | Asset or Shot, then - and +.
        self.picker = picker.TargetPicker(PICKER_DEPARTMENTS, self._items_for)
        self.picker.dept_combo.setToolTip(
            "Layout: publishes the camera and what's selected; never caches.\n"
            "Animation: the same, plus caches once a publish is approved for Final.\n"
            "Ask for approval in the notes (e.g. \"please approve for lighting\").\n"
            "Environment: this scene's environment_SET (landscape, buildings, sky).")
        self.picker.add_clicked.connect(self._add_row)
        self.picker.remove_clicked.connect(self._remove_rows)

        # The publish list. Only ticked rows are published.
        self.table = QtWidgets.QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Asset / Shot", "Type", "Department", "Objects", "Publishes as"])
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemChanged.connect(self._on_item_changed)
        self.objects_btn = QtWidgets.QPushButton("Set Objects from Selection")
        self.objects_btn.setToolTip("Publish only the objects selected in Maya (and "
                                    "their children) for the selected row(s).")
        self.objects_btn.clicked.connect(self._set_objects)
        self.whole_btn = QtWidgets.QPushButton("Whole Scene")
        self.whole_btn.setToolTip("Publish the whole scene file for the selected row(s).")
        self.whole_btn.clicked.connect(self._clear_objects)
        list_btns = QtWidgets.QHBoxLayout()
        list_btns.addWidget(self.objects_btn)
        list_btns.addWidget(self.whole_btn)
        list_btns.addStretch(1)

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
        layout.addWidget(self.picker)
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
            # New scene or H drive: refill the picker, starting on what the
            # open scene is. The student can still pick anything.
            self._picker_key = key
            films = api.list_films(h_root) if h_root else []
            if ctx and ctx["film"] not in films:
                films.append(ctx["film"])
            self.picker.set_films(films, ctx["film"] if ctx else None)
            if ctx and ctx["kind"] == "shot":
                self.picker.set_current(code=anim.ANIM_CODE, group=ctx["seq"],
                                        name=ctx["shot"])
            elif ctx:
                # Start on the department the file name says (scout_rig_v002
                # -> Rigging), so a rig isn't published as a model by default.
                words = re.split(r"[_.]", os.path.basename(scene).lower())
                code = next((c for c in LIVE_DEPARTMENTS if c.lower() in words),
                            LIVE_DEPARTMENTS[0])
                self.picker.set_current(code=code, group=ctx["asset_type"], name=ctx["asset"])
            self._set_frame_defaults(ctx)
            self._set_shot_mode(bool(ctx) and ctx["kind"] == "shot")
        else:
            # Same scene: re-read the H drive, keeping what's picked, so an
            # asset or shot made while the window was open shows up (user,
            # 2026-10-26: fieldA was made on H and couldn't be picked).
            self.picker.refill()
        self._render_table()

    def _items_for(self, film, code, kind):
        """The picker's last two dropdowns: the film's shots, or its assets
        (environment assets only, for Environment)."""
        h_root = self._roots()[0]
        if not (h_root and os.path.isdir(h_root)):
            return []
        if kind == picker.SHOT:
            shots = api.list_shots(h_root, film)
            _, ctx = self._scene_context()
            if (ctx and ctx["kind"] == "shot" and ctx["film"] == film
                    and (ctx["seq"], ctx["shot"]) not in shots):
                shots.append((ctx["seq"], ctx["shot"]))
            return shots
        assets = api.list_h_assets(h_root, film)
        if code == env.ENV_CODE:
            assets = [a for a in assets if a[0] == env.ENV_TYPE]
        return assets

    def _set_shot_mode(self, shot):
        """Set Objects / Whole Scene are for asset rows only."""
        for widget in (self.objects_btn, self.whole_btn):
            widget.setVisible(not shot)
        self.picker.add_btn.setToolTip(
            "Add what's selected in Maya (cameras, characters, props...): the tool works "
            "out what each one is. For the Environment, environment_SET decides what goes."
            if shot else
            "Add this asset with what's selected in Maya. With nothing selected, the "
            "whole scene is published.")

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

    def _plan(self, row):
        scene = cmds.file(query=True, sceneName=True)
        if row["code"] == cam.CAM_CODE:
            return cam.plan_camera(scene, *self._roots(), camera=row["objects"][0])
        if row["code"] == anim.ANIM_CODE:
            return anim.plan_anim(scene, *self._roots(), items=anim.classify(row["objects"]),
                                  publish_for=row["publish_for"])
        if row["code"] == env.ENV_CODE:
            env.check_environment()
            return env.plan_environment(scene, *self._roots(),
                                        target=(row["asset_type"], row["asset"]))
        return api.plan_publish(scene, *self._roots(), code=row["code"],
                                target=(row["asset_type"], row["asset"]))

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
        self.table.blockSignals(True)
        self.table.setRowCount(len(self._rows))
        problems = []
        try:
            api.check_script_nodes()    # also checked again on Publish
        except api.PublishError as e:
            problems.append(str(e))
        for r, row in enumerate(self._rows):
            stage = row.get("publish_for")
            type_label = row.get("type_label", row["asset_type"])
            objects = ", ".join(row["objects"]) if row["objects"] else "(whole scene)"
            if row["code"] == env.ENV_CODE:
                objects = "(what's in %s)" % env.ENVIRONMENT_SET
            item = None
            if row["code"] == anim.ANIM_CODE:
                try:
                    item = anim.classify(row["objects"])[0]
                    type_label = ("made in the shot" if item["kind"] == "shot" else
                                  "%s v%03d" % (item["kind"], item["stamp"].get("version") or 0))
                    objects = "%s (%s)" % (objects, "keyed" if item["animated"] else "no keys")
                except api.PublishError:
                    pass        # shown as "can't publish" in the last column
            self.table.setItem(r, 0, _check_cell(row["asset"], row["checked"]))
            self.table.setItem(r, 1, _cell(type_label))
            dept = DEPT_LABELS[row["code"]]
            if row["code"] == anim.ANIM_CODE:
                dept = anim.PUBLISH_FOR_LABELS[stage]
            elif row["code"] == cam.CAM_CODE:
                dept = "%s (%s)" % (dept, anim.PUBLISH_FOR_LABELS[stage])
            self.table.setItem(r, 2, _cell(dept))
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
                         if stage == anim.ANIM_CODE else []))
                self.table.setItem(r, 4, _cell(text))
                self.table.item(r, 4).setToolTip(dest)
            except api.PublishError as e:
                self.table.setItem(r, 4, _cell("can't publish", "#e0a060"))
                if row["checked"]:      # an unticked row doesn't hold up the rest
                    problems.append(str(e))
        self.table.resizeColumnsToContents()
        self.table.blockSignals(False)
        ticked = any(row["checked"] for row in self._rows)

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
        self.publish_btn.setEnabled(ticked and not problems and bool(ctx))

    def _on_item_changed(self, item):
        """A row's tick: only ticked rows are published."""
        if item.column() != 0 or item.row() >= len(self._rows):
            return
        self._rows[item.row()]["checked"] = item.checkState() == QtCore.Qt.Checked
        # Re-render after this signal: the item can't be replaced inside it.
        QtCore.QTimer.singleShot(0, self._render_table)

    # -- list -------------------------------------------------------------

    def _selected_rows(self):
        return sorted(set(i.row() for i in self.table.selectedIndexes()))

    def _add_selected_in_shot(self, shot, publish_for):
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
                row.update(publish_for=publish_for, checked=True)
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

    def _add_environment(self, asset):
        """Shot scene: a row publishing environment_SET to the picked
        environment asset (spec §4c)."""
        if any(r["code"] == env.ENV_CODE for r in self._rows):
            self.status.show_message("The environment is already in the list.", ok=False)
            return
        try:
            env.check_environment()
        except api.PublishError as e:
            self.status.show_message(str(e), ok=False)
            return
        self._rows.append({"asset_type": env.ENV_TYPE, "asset": asset, "code": env.ENV_CODE,
                           "objects": [], "uuids": [], "type_label": env.ENV_TYPE,
                           "checked": True})
        self._render_table()
        self.status.show_message("Added the environment, to %s." % asset)

    def _save_into_asset(self):
        """The scene isn't in an asset's or a shot's scenes folder (never
        saved, or saved outside the pipe). If an asset is picked, offer to
        make it on scratch the way the Project Tool's Set Project does and
        save the scene there as its working file, so it can be published
        (user, 2026-10-26: fieldA was on H but not on scratch, so there was
        nowhere to save it and publish from). True once it's saved there."""
        film, code = self.picker.film(), self.picker.department()
        group, name = self.picker.group(), self.picker.name()
        if (self.picker.kind() == picker.SHOT and code != env.ENV_CODE) or not (film and name):
            self.status.show_message("Save your scene in an asset's or a shot's scenes "
                                     "folder first, or pick the asset to publish to.", ok=False)
            return False
        import projectTool_api as proj
        try:
            h_root, scratch_root = (api.resolve_root(r) for r in self._roots())
            api.check_roots(h_root, scratch_root)
            login = api.who()
        except api.PublishError as e:
            self.status.show_message(str(e), ok=False)
            return False
        rel = (film, "maya", "assets", group, name)
        project = proj.scratch_project(scratch_root, rel)
        folder = os.path.join(project, "scenes", login)
        current = cmds.file(query=True, sceneName=True)
        ext = os.path.splitext(current)[1].lower() if current else ".ma"
        ext = ext if ext in api.SCENE_EXTS else ".ma"
        number = 1
        while os.path.exists(os.path.join(folder, "%s_%03d%s" % (name, number, ext))):
            number += 1
        dest = os.path.normpath(os.path.join(folder, "%s_%03d%s" % (name, number, ext)))
        text = ("This scene isn't saved in a pipeline project, so it can't be published yet."
                "\n\nSave it as %s's working scene?\n  %s" % (name, dest))
        if not os.path.isfile(os.path.join(project, proj.WORKSPACE)):
            text += ("\n\n%s isn't on your scratch drive yet: it'll be made first, as the "
                     "Project Tool's Set Project would." % name)
        if current:
            text += "\n\nThe file you have open now is left as it is."
        box = QtWidgets.QMessageBox(self)
        box.setIcon(QtWidgets.QMessageBox.Question)
        box.setWindowTitle("Save into %s" % name)
        box.setText(text)
        save = box.addButton("Save Here", QtWidgets.QMessageBox.AcceptRole)
        box.addButton(QtWidgets.QMessageBox.Cancel)
        box.setDefaultButton(save)
        box.exec()
        if box.clickedButton() != save:
            self.status.show_message("Not added: save your scene in an asset's or a shot's "
                                     "scenes folder first.", ok=False)
            return False
        try:
            proj.set_project(h_root, scratch_root, rel, login)
            cmds.file(rename=dest)
            cmds.file(save=True, type="mayaAscii" if ext == ".ma" else "mayaBinary")
        except Exception as e:
            self.status.show_message("Couldn't save into %s: %s" % (name, e), ok=False)
            return False
        # The window follows the newly saved scene; keep what was picked.
        self.refresh()
        self.picker.set_current(film=film, code=code, group=group, name=name)
        return True

    def _add_row(self):
        """+ : add what the picker says. A shot department adds what's
        selected in the shot; an asset department adds that asset with
        the selection as its objects (nothing selected = whole scene)."""
        scene, ctx = self._scene_context()
        if not ctx:
            if not self._save_into_asset():
                return
            scene, ctx = self._scene_context()
        code, label = self.picker.department(), self.picker.dept_combo.currentText()
        group, name = self.picker.group(), self.picker.name()
        in_shot = ctx["kind"] == "shot"
        shot_dept = self.picker.kind() == picker.SHOT and code != env.ENV_CODE
        if in_shot and not shot_dept and code != env.ENV_CODE:
            self.status.show_message(
                "%s is published from an asset's scene. A shot scene publishes Layout, "
                "Animation or its Environment." % label, ok=False)
            return
        if not name:
            self.status.show_message("There's nothing to pick for %s in %s yet."
                                     % (label, self.picker.film()), ok=False)
            return
        if shot_dept:
            if not in_shot or (ctx["film"], ctx["seq"], ctx["shot"]) != (
                    self.picker.film(), group, name):
                self.status.show_message(
                    "%s for %s is published from that shot's own scene: open one of its "
                    "scenes first." % (label, name), ok=False)
                return
            return self._add_selected_in_shot(ctx["shot"], code)
        if self.picker.film() != ctx["film"]:
            self.status.show_message("This scene is in %s, so it publishes to %s's assets."
                                     % (ctx["film"], ctx["film"]), ok=False)
            return
        if in_shot:
            return self._add_environment(name)
        if (code == api.MODEL_CODE and group == env.ENV_TYPE
                and self._looks_like_environment()):
            # An environment asset with an environment_SET is an environment
            # publish (user, 2026-10-26; 2026-10-23 a shed environment went
            # out as Modeling twice and left its image planes behind). No
            # environment_SET: a plain Modeling publish.
            code, label = env.ENV_CODE, env.ENV_LABEL
        if any((r["asset_type"], r["asset"], r["code"]) == (group, name, code)
               for r in self._rows):
            self.status.show_message("%s %s is already in the list." % (name, label), ok=False)
            return
        # Whatever is selected in Maya becomes this row's objects; nothing
        # selected = the whole scene. environment_SET decides an environment.
        selection = [] if code == env.ENV_CODE else cmds.ls(selection=True) or []
        problem = self._check_objects(code, selection)
        if problem:
            self.status.show_message(problem, ok=False)
            return
        self._rows.append({"asset_type": group, "asset": name,
                           "code": code, "objects": list(selection),
                           "uuids": cmds.ls(selection, uuid=True) if selection else [],
                           "checked": True})
        self._render_table()
        self.status.show_message(
            "Added %s %s: %s" % (name, label,
                                 ", ".join(selection) if selection else "whole scene"))

    @staticmethod
    def _looks_like_environment():
        """True if the open scene has an environment_SET (spec §4c)."""
        return any(cmds.nodeType(n) == "objectSet"
                   for n in cmds.ls(env.ENVIRONMENT_SET) or [])

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
        if code == env.ENV_CODE:
            # environment_SET decides what goes, not the selection.
            try:
                env.check_environment()
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
            box = QtWidgets.QMessageBox(self)
            box.setIcon(QtWidgets.QMessageBox.Question)
            box.setWindowTitle("Unsaved changes")
            box.setText("Your scene has unsaved changes.\n"
                        "Save it now and publish the saved version?")
            save = box.addButton("Save and Publish", QtWidgets.QMessageBox.AcceptRole)
            box.addButton(QtWidgets.QMessageBox.Cancel)
            box.setDefaultButton(save)
            box.exec()
            if box.clickedButton() != save:
                # Never a silent no-op (user, 2026-10-26).
                self.status.show_message("Not published: the scene has unsaved changes. "
                                         "Save it, or press Publish and pick Save and Publish.",
                                         ok=False)
                return
            cmds.file(save=True)
        try:
            self._publish_saved()
        finally:
            # The publish puts the working scene back as it was, but the
            # playblast (isolate select, panel camera) can leave Maya
            # thinking it changed, so after a cancelled publish the next
            # Publish asked to save again (user, 2026-10-26). It was saved
            # just above, so it's still the saved scene.
            cmds.file(modified=False)

    def _publish_saved(self):
        """Publish the ticked rows from the saved scene."""

        scene = cmds.file(query=True, sceneName=True)
        self._sync_objects()    # anything renamed since the last refresh
        frame_count = None if self.timeline_chk.isChecked() else self.frames_spin.value()
        notes = self.notes_edit.toPlainText().strip()
        lines, ok, published, cancelled = [], True, False, False
        _, ctx = self._scene_context()
        in_shot = bool(ctx) and ctx["kind"] == "shot"
        # Only the ticked rows. All the Animation items for one stage go out
        # as ONE publish (one shared version number, spec item 1), so they
        # become a single job here.
        rows = [r for r in self._rows if r["checked"]]
        anim_rows = [r for r in rows if r["code"] == anim.ANIM_CODE]
        jobs = [r for r in rows if r["code"] != anim.ANIM_CODE]
        for _, stage, _ in anim.PUBLISH_FOR:
            items = [r for r in anim_rows if r["publish_for"] == stage]
            if items:
                jobs.append({"asset_type": "shot", "asset": ", ".join(r["asset"] for r in items),
                             "code": anim.ANIM_CODE, "publish_for": stage,
                             "objects": [r["objects"][0] for r in items]})
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        try:
            for row in jobs:
                label = "%s %s" % (row["asset"], row["code"])
                # Anything published under a shot (cameras, characters' anim,
                # ...) always uses the whole timeline (spec "Shot publishes").
                frames = None if row["asset_type"] == "shot" else frame_count
                if row["code"] == env.ENV_CODE and in_shot:
                    # The shot's timeline is locked on, but an environment
                    # is a still: 2 frames, like any asset by default.
                    frames = ENV_SHOT_FRAMES
                if row["code"] == anim.ANIM_CODE:
                    label = "%s %s" % (row["asset"],
                                       anim.PUBLISH_FOR_LABELS[row["publish_for"]])
                review = self._review(label)
                try:
                    if row["code"] == cam.CAM_CODE:
                        plan = cam.publish_camera(scene, *self._roots(),
                                                  camera=row["objects"][0],
                                                  frame_count=frames, notes=notes,
                                                  publish_for=row["publish_for"],
                                                  review=review)
                    elif row["code"] == anim.ANIM_CODE:
                        plan = anim.publish_anim(scene, *self._roots(),
                                                 objects=row["objects"], notes=notes,
                                                 publish_for=row["publish_for"],
                                                 review=review)
                        label += {
                            anim.FINAL: " (Final approved: caches made)",
                            anim.ANIMATION: " (no caches yet: they're made once a publish "
                                            "is approved for Final)",
                        }.get(plan["stage"], "")
                    else:
                        plan = api.publish(scene, *self._roots(), code=row["code"],
                                           frame_count=frames, notes=notes,
                                           objects=row["objects"],
                                           target=(row["asset_type"], row["asset"]),
                                           review=review)
                except api.PublishCancelled:
                    lines.append("%s: cancelled after watching the movie, nothing published."
                                 % label)
                    cancelled = True
                    continue
                except Exception as e:
                    lines.append("%s: FAILED — nothing published:\n  %s" % (label, e))
                    ok = False
                    continue
                published = True
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
            if published:
                line = self._back_up_studio_library(scene)
                if line:
                    lines.append(line)
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        if ok and not cancelled:
            # Kept after a failure or cancel so the student doesn't have to
            # retype them.
            self.notes_edit.clear()
        self._render_table()
        self.status.show_message("\n".join(lines), ok=ok)

    def _review(self, label):
        """The publish's review step: watch the movie in RV, then Publish or
        Cancel (api.review_before_publish)."""
        def review(movie, plan):
            reason = "" if movie else (getattr(api._shotgrid(), "last_encode_problem", None)
                                       or "RV's rvio wasn't found on this machine.")
            QtWidgets.QApplication.restoreOverrideCursor()
            try:
                dialog = ReviewDialog(movie, "%s v%03d" % (label, plan["version"]), reason, self)
                return dialog.exec() == QtWidgets.QDialog.Accepted
            finally:
                QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        return review

    def _back_up_studio_library(self, scene):
        """Every publish, iterative or final, backs up the film's Studio
        Library folders to the H drive (spec §4b). A problem here never
        undoes the publish; it's reported as a line."""
        try:
            h_root, scratch_root = (api.resolve_root(r) for r in self._roots())
            _, rel = api.find_film_folder(scene)
            return slib.describe(slib.back_up(scratch_root, h_root, rel[0]),
                                 "backed up to the H drive")
        except Exception as e:
            return "Studio Library not backed up: %s" % e

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
