"""
Build Tool — UI
Two tabs:
  Build Shot  — list the assets the open scene's shot needs (picker row:
                Film, Asset or Shot, Department, Type or Sequence, Asset
                or Shot, then - and +); one click pulls every ticked one
                from the H drive and references it into the open scene.
                Each asset's Keys dropdown puts a Layout/Animation
                publish's keys back on it (from the picker's shot).
                Building into an asset works the same way: referenced,
                like a shot (user, 2026-10-30: one Build button, no
                context). The mpModel shelf's Convert to Model makes a
                referenced model editable.
  My Scratch  — what's on the scratch drive, how safe it is to remove,
                and removal to the Recycle Bin.

Dev launch (Script Editor, Python tab):

    import sys, importlib
    for p in (r"C:\\Users\\scout\\Documents\\maya\\scriptDev\\pipeDev\\publishDev",
              r"C:\\Users\\scout\\Documents\\maya\\scriptDev\\pipeDev\\buildDev"):
        if p not in sys.path: sys.path.insert(0, p)
    import publishTool_api, pipeEnv, buildTool_api, pipePicker, buildTool_ui
    for m in (publishTool_api, pipeEnv, buildTool_api, pipePicker, buildTool_ui): importlib.reload(m)
    buildTool_ui.show()
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

import buildTool_api as api
import pipePicker as picker
pub = api.pub

# Two pickers, two jobs (user, 2026-10-28: "the difference between build and
# populate list mode"):
# - Add to list, above the list: Film | Asset or Shot | what's published |
#   Asset type | Asset, then - and +. The same departments as Build Into,
#   plus Environment, whatever department you're building as (user,
#   2026-10-30: "the 'add to list' department dropdown should be the same
#   as the ... dropdown in the Build into list"). Those with nothing Build
#   can add yet are greyed out (coming soon): FX and Lighting publish
#   nothing yet, and a shot's camera and caches come with the shot.
# - Build Into, under the list: Film | Asset or Shot | the artist's
#   department | Sequence or type | Shot or asset. Where the build goes
#   ("I want these things in this place"); it starts on the Maya project and
#   never changes it. The shot's own camera and caches come with the shot.
ASSET_SIDE = ("model", "rig", "creature", "lookDev")
TARGET_DEPARTMENTS = [(label, code, picker.ASSET if code in ASSET_SIDE else picker.SHOT,
                       bool(builds))
                      for label, code, builds in api.BUILD_FOR]
SOURCE_DEPARTMENTS = (
    [(label, code, side, code in ASSET_SIDE) for label, code, side, _ in TARGET_DEPARTMENTS
     if side == picker.ASSET] +
    [(api.DEPT_LABELS[pub.ENV_CODE], pub.ENV_CODE, picker.ASSET, True)] +
    [(label, code, side, False) for label, code, side, _ in TARGET_DEPARTMENTS
     if side == picker.SHOT])
# Published for a shot itself, not an asset: they only build into it.
SHOT_ITEMS = ("camera", "cache")

STATUS_TEXT = {
    api.SAFE: ("Safe to remove", "#7fbf7f"),
    api.CHANGED: ("Changed since last publish", "#e0a060"),
    api.UNPUBLISHED: ("Not backed up", "#e06060"),
}


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
            print("Build Tool: %s" % text)


def _table(headers):
    table = QtWidgets.QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
    table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
    table.verticalHeader().setVisible(False)
    table.horizontalHeader().setStretchLastSection(True)
    return table


def _heading(text):
    label = QtWidgets.QLabel("<b>%s</b>" % text)
    label.setContentsMargins(0, 6, 0, 0)
    return label


def _cell(text, colour=None):
    item = QtWidgets.QTableWidgetItem(text)
    if colour:
        item.setForeground(QtGui.QColor(colour))
    return item


def _check_cell(text, checked):
    """A row's first cell: its name with the tick that says it's built."""
    item = _cell(text)
    item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
                  | QtCore.Qt.ItemIsUserCheckable)
    item.setCheckState(QtCore.Qt.Checked if checked else QtCore.Qt.Unchecked)
    return item


# ---------------------------------------------------------------------------
# Build Shot tab
# ---------------------------------------------------------------------------

class BuildShotTab(QtWidgets.QWidget):
    """Pick assets from the H drive into a list for the shot, then Build
    Shot pulls + references (or updates) every ticked one in one click.
    The shot is the open scene's (user, 2026-10-22)."""

    def __init__(self, get_roots, parent=None):
        super(BuildShotTab, self).__init__(parent)
        self._get_roots = get_roots
        self._target_shot = None     # (film, seq, shot) being built into
        # Or (film, asset_type, asset) when building into an asset: built
        # the same way, referenced (user, 2026-10-30).
        self._target_asset = None
        self._published = []     # everything on the H drive for the shot's film
        self._other_films = {}   # film -> list_published, for the picker
        self._shot_keys = {}     # (film, seq, shot) -> api.list_shot_keys
        self._keys_src = None    # the shot the Keys dropdowns list (see _keys_source)
        self._rows = []          # the shot's list: published entries shown in the table
        self._removed = set()    # keys taken off this shot's list (kept until the shot changes)

        # Which shot: always the open scene's.
        self.target_lbl = QtWidgets.QLabel()
        self.target_lbl.setWordWrap(True)
        # Scene and Maya project in different shots/assets (2026-10-28).
        self.project_banner = picker.ProjectBanner(self._match_project)

        # Add to list (see SOURCE_DEPARTMENTS), then - and +.
        self.picker = picker.TargetPicker(SOURCE_DEPARTMENTS, self._items_for)
        self.picker.dept_combo.setToolTip("What's published: a model, a rig, an "
                                          "environment... Every department is listed, "
                                          "whatever you're building as. Greyed out: "
                                          "nothing to add yet.")
        self.picker.add_clicked.connect(self._add_asset)
        self.picker.remove_clicked.connect(self._remove_rows)

        # Build Into (see TARGET_DEPARTMENTS): starts on the Maya project, and
        # on the department the open scene is worked in.
        self._target_key = None      # (scene, project) the target was last set from
        self.target_picker = picker.TargetPicker(TARGET_DEPARTMENTS, self._target_items)
        self.target_picker.kind_combo.setToolTip("Building into a shot or an asset.")
        self.target_picker.dept_combo.setToolTip(
            "Your department: each department has its own list for a shot, and "
            "Animation brings in the shot's caches. FX and Lighting come later.")
        self.target_picker.group_combo.setToolTip("Sequence, or asset type")
        self.target_picker.name_combo.setToolTip("Shot, or asset")
        for button in (self.target_picker.add_btn, self.target_picker.remove_btn):
            button.hide()
        for combo in (self.target_picker.film_combo, self.target_picker.kind_combo,
                      self.target_picker.group_combo, self.target_picker.name_combo):
            combo.currentIndexChanged.connect(self._on_target_changed)
        self.target_picker.dept_combo.currentIndexChanged.connect(self._on_department_changed)

        # Which shot the Keys dropdowns list (user, 2026-10-23: keys can come
        # from another shot). This shot unless picked.
        self.keys_combo = QtWidgets.QComboBox()
        self.keys_combo.setToolTip("Which shot's Layout / Animation publishes the Keys "
                                   "column offers. Pick another shot to take its keys.")
        self.keys_combo.currentIndexChanged.connect(self._on_keys_source_changed)

        # The shot's asset list, filtered by department (user, 2026-10-21).
        self.filter_combo = QtWidgets.QComboBox()
        self.filter_combo.setToolTip("Show only one department's assets in the list. "
                                     "Build Shot still builds the whole list.")
        self.filter_combo.currentIndexChanged.connect(self._apply_filter)
        show = QtWidgets.QHBoxLayout()
        show.addWidget(QtWidgets.QLabel("Show:"))
        show.addWidget(self.filter_combo)
        show.addSpacing(16)
        self.keys_lbl = QtWidgets.QLabel("Keys from:")
        show.addWidget(self.keys_lbl)
        show.addWidget(self.keys_combo)
        show.addStretch(1)
        self.table = _table(["Asset", "Type", "Department", "Version", "Keys",
                             "In this shot", "Status"])
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.table.itemChanged.connect(self._on_item_changed)
        self.picker.remove_btn.setToolTip(
            "Take the highlighted assets off the list. Only the list changes: anything "
            "already in your scene stays there.")
        refresh_btn = QtWidgets.QPushButton("Refresh")
        refresh_btn.setToolTip("Look at the H drive again for new publishes. "
                               "Your list and version choices are kept.")
        refresh_btn.clicked.connect(self._on_refresh_clicked)
        repair_btn = QtWidgets.QPushButton("Repair")
        repair_btn.setToolTip("Find references in the open scene whose files are "
                              "missing, and pull those exact versions back from the H drive.")
        repair_btn.clicked.connect(self._repair)
        list_btns = QtWidgets.QHBoxLayout()
        list_btns.addWidget(refresh_btn)
        list_btns.addWidget(repair_btn)
        list_btns.addStretch(1)

        # One button, the same for a shot or an asset (user, 2026-10-30: "we
        # don't want a context sensitive build button").
        build_btn = self.build_btn = QtWidgets.QPushButton("Build")
        build_btn.setToolTip(
            "References every ticked asset into the open scene (pulled from the H drive "
            "into your scratch publish folder). New assets, and ones you pick another "
            "version for, start ticked; ones already in the scene start unticked.\n"
            "To work on a published model in an asset, Build it, then use Convert on "
            "the mpModel shelf.")
        build_btn.setMinimumHeight(36)
        build_btn.clicked.connect(self._build_shot)

        self.status = StatusLabel()
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.target_lbl)
        layout.addWidget(self.project_banner)
        layout.addWidget(_heading("Add to the list"))
        layout.addWidget(self.picker)
        layout.addLayout(show)
        layout.addWidget(self.table, 1)
        layout.addLayout(list_btns)
        layout.addWidget(_heading("Build into"))
        layout.addWidget(self.target_picker)
        layout.addWidget(build_btn)
        layout.addWidget(self.status)

    # -- filling ----------------------------------------------------------

    def refresh(self):
        """Start Build Into on the Maya project (and the open scene's
        department), refill both pickers' films and load the list. With the
        same scene and project as before, a Build Into picked by hand stays."""
        h_root = self._get_roots()[0]
        films = api.list_films(h_root) if h_root else []
        if self._scene_and_project() != self._target_key:
            self._default_target(films)
        else:
            self.target_picker.set_films(films, self.target_picker.film())
            self._read_target()
        target = self._target_shot or self._target_asset
        self.picker.set_films(films, target[0] if target else None)
        self._load_shot()
        self._show_mismatch()

    def check_target(self):
        """Another scene opened or another project set since the list was
        made: start again from the project. Otherwise the list (and its
        ticks, and a Build Into picked by hand) stays as it is."""
        if self._scene_and_project() != self._target_key:
            self.refresh()
        else:
            self._show_mismatch()

    @staticmethod
    def _scene_and_project():
        return (cmds.file(query=True, sceneName=True) or "",
                cmds.workspace(query=True, rootDirectory=True) or "")

    def _default_target(self, films):
        """Build Into starts on the Maya project's shot or asset (else the
        open scene's), on the department the scene is worked in (its
        working folder or file name, else Animation / Modeling)."""
        scene, project = self._scene_and_project()
        self._target_key = (scene, project)
        place = self._start_place = pub.pipe_place(project) or pub.pipe_place(scene)
        film = place["film"] if place else None
        if film and film not in films:
            films = films + [film]
        side = picker.SHOT if place and place["kind"] == "shot" else picker.ASSET
        code = api.department_of_scene(
            scene or os.path.join(place["folder"], "scenes", "untitled.ma")) if place else None
        if not code or dict((d[1], d[2]) for d in TARGET_DEPARTMENTS).get(code) != side:
            code = "anim" if side == picker.SHOT else "model"
        self.target_picker.set_films(films, film)
        self.target_picker.set_current(film=film, code=code,
                                       group=place["group"] if place else None,
                                       name=place["name"] if place else None)
        self._read_target()

    def _read_target(self):
        """_target_shot / _target_asset from Build Into."""
        p = self.target_picker
        picked = (p.film(), p.group(), p.name())
        ok = all(picked)
        self._target_shot = picked if ok and p.kind() == picker.SHOT else None
        self._target_asset = picked if ok and p.kind() == picker.ASSET else None

    def _on_target_changed(self, *args):
        """Build Into picked by hand: load that shot's (or asset's) list."""
        before = (self._target_shot, self._target_asset)
        self._read_target()
        if (self._target_shot, self._target_asset) != before:
            target = self._target_shot or self._target_asset
            if target and target[0] != self.picker.film():
                self.picker.set_films(api.list_films(self._get_roots()[0]), target[0])
            self._load_shot()
        self._show_mismatch()

    def department(self):
        return self.target_picker.department()

    def _on_department_changed(self, *args):
        """Another department: the list is that department's list for the
        shot (with the shot's caches if it builds them). Add to list stays
        as it is: it offers every department."""
        if self._target_shot and self._published:
            self._load_shot()

    def _target_place(self):
        target = self._target_shot or self._target_asset
        if not target:
            return None
        return {"film": target[0], "kind": "shot" if self._target_shot else "asset",
                "group": target[1], "name": target[2]}

    def target_mismatch(self):
        """{"project", "target"} places when Build Into isn't the Maya
        project's shot or asset, else None. Building there is refused (user,
        2026-10-28: "the pipe should refuse and make the user reset the
        project and save the file in the correct structure"). No pipe
        project set at all (a fresh Maya) never counts: Build sets it."""
        project = pub.pipe_place(cmds.workspace(query=True, rootDirectory=True) or "")
        target = self._target_place()
        if not (project and target) or all(project[k].lower() == target[k].lower()
                                           for k in ("film", "kind", "group", "name")):
            return None
        return {"project": project, "target": target}

    def _mismatch_text(self, mismatch):
        return ("Build into is <b>%s</b>, but your Maya project is <b>%s</b>, so Build "
                "won't run.<br>To build %s: set it as your project with the Project Tool "
                "and save your scene there. Or go back to the project's %s." % (
                    pub.place_label(mismatch["target"]), pub.place_label(mismatch["project"]),
                    pub.place_label(mismatch["target"]), mismatch["project"]["kind"]))

    def _show_mismatch(self):
        """The red banner: Build Into isn't the Maya project (Build refuses),
        else the scene isn't saved in the project (spec "Scene vs project":
        a warning)."""
        mismatch = self.target_mismatch()
        if mismatch:
            self.project_banner.match_btn.setText("Back to the project's %s"
                                                  % mismatch["project"]["kind"])
            self.project_banner.show_mismatch(self._mismatch_text(mismatch))
            return
        mismatch = api.pub.project_mismatch()
        self.project_banner.match_btn.setText("Set Project to the scene's")
        self.project_banner.show_mismatch(self._scene_text(mismatch) if mismatch else None)

    @staticmethod
    def _scene_text(mismatch):
        """Scene saved outside the project: Build won't run until they match."""
        return ("Your open scene is in <b>%s</b>, but your Maya project is <b>%s</b>, so "
                "Build won't run.<br>Set Project to the scene's, or open a scene in %s." % (
                    pub.place_label(mismatch["scene"]), pub.place_label(mismatch["project"]),
                    pub.place_label(mismatch["project"])))

    def _match_project(self):
        mismatch = self.target_mismatch()
        if mismatch:
            project = mismatch["project"]
            code = self.department()
            if dict((d[1], d[2]) for d in TARGET_DEPARTMENTS).get(code) != project["kind"]:
                code = "anim" if project["kind"] == "shot" else "model"
            self.target_picker.set_current(film=project["film"], code=code,
                                           group=project["group"], name=project["name"])
            self._on_target_changed()
            return
        mismatch = api.pub.project_mismatch()
        if mismatch:
            try:
                api.pub.set_maya_project(mismatch["scene"]["folder"])
            except api.pub.PublishError as e:
                self.status.show_message(str(e), ok=False)
                return
            self.status.show_message("Maya project set to %s, where the open scene is."
                                     % api.pub.place_label(mismatch["scene"]))
            self._target_key = self._scene_and_project()
        self._show_mismatch()

    def film(self):
        """The shot's or asset's film, else the picker's (for the My Scratch tab)."""
        target = self._target_shot or self._target_asset
        return target[0] if target else self.picker.film()

    def _asset_dir(self):
        scratch_root = self._get_roots()[1]
        if not (self._target_asset and scratch_root):
            return None
        return api.asset_folder(scratch_root, *self._target_asset)

    def _shot_dir(self):
        """The shot's (or asset's) folder on scratch: Build references into
        either the same way (user, 2026-10-30)."""
        scratch_root = self._get_roots()[1]
        if self._target_shot and scratch_root:
            return api.shot_folder(scratch_root, *self._target_shot)
        return self._asset_dir()

    def _h_target_dir(self):
        """The shot's or asset's folder on H: where its build lists live."""
        h_root = self._get_roots()[0]
        if not h_root:
            return None
        if self._target_shot:
            return api.shot_folder(h_root, *self._target_shot)
        if self._target_asset:
            return api.asset_folder(h_root, *self._target_asset)
        return None

    def _items_for(self, film, code, kind):
        """Add to list's last two dropdowns: the assets with a publish for
        that department (environments, for Environment)."""
        h_root = self._get_roots()[0]
        if not (h_root and os.path.isdir(h_root)):
            return []
        return [(p["asset_type"], p["asset"]) for p in self._published_in(film)
                if p["code"] == code and p.get("kind") not in SHOT_ITEMS]

    def _target_items(self, film, code, kind):
        """Build Into's last two dropdowns: the film's shots, or its assets
        (plus the place it started on, the project's or the scene's, if
        that isn't on the H drive yet: never silently another one)."""
        h_root = self._get_roots()[0]
        if not (h_root and os.path.isdir(h_root)):
            return []
        found = list(api.list_shots(h_root, film) if kind == picker.SHOT
                     else pub.list_h_assets(h_root, film))
        place = getattr(self, "_start_place", None)
        if (place and place["film"] == film and place["kind"] == kind
                and (place["group"], place["name"]) not in found):
            found.append((place["group"], place["name"]))
        return found

    def _published_in(self, film):
        target = self._target_shot or self._target_asset
        if target and film == target[0]:
            return self._published
        if film not in self._other_films:
            self._other_films[film] = api.list_published(self._get_roots()[0], film)
        return self._other_films[film]

    def _load_shot(self, *args):
        """Re-read the H drive and start the list with whatever is already
        in this shot."""
        h_root, scratch_root = self._get_roots()
        self._published, self._rows, self._removed = [], [], set()
        self._other_films, self._shot_keys, self._keys_src = {}, {}, None
        self._render_table()
        try:
            pub.check_roots(pub.resolve_root(h_root), pub.resolve_root(scratch_root))
        except pub.PublishError as e:
            self.target_lbl.setText("")
            self.status.show_message(str(e), ok=False)
            return
        for widget in (self.keys_lbl, self.keys_combo):     # keys come from shots
            widget.setVisible(not self._target_asset)
        if not (self._target_shot or self._target_asset):
            self.target_lbl.setText("")
            self.picker.refill()
            self.status.show_message(
                "Pick the shot (or asset) to build into under Build into, or set it as "
                "your Maya project with the Project tool.", ok=False)
            return
        film, group, name = self._target_shot or self._target_asset
        scene = cmds.file(query=True, sceneName=True)
        self.target_lbl.setText("Building into %s <b>%s</b> (%s), in %s" % (
            "shot" if self._target_shot else "asset", name, film,
            os.path.basename(scene) if scene else "a new scene"))
        self._published = api.list_published(h_root, film)
        if self._target_shot:
            # The shot's own camera, if one has been published (spec
            # "Cameras"), and its Final animation caches (one per item), for
            # the departments that build them.
            self._published += api.list_shot_cameras(h_root, film, group, name)
            self._published += api.list_shot_caches(h_root, film, group, name)
        self.picker.refill()
        if self._target_shot:
            self._fill_keys_shots()

        shot_dir = self._shot_dir()
        manifest = api.read_manifest(shot_dir) if shot_dir else {}
        # The list always starts with everything that belongs to this shot:
        # the department's list for the shot saved on the H drive (so it
        # comes back on any machine, user 2026-10-23), or for a shot without
        # one yet what's in its assets folder on scratch, plus anything
        # published for the shot itself, e.g. its camera, ready to build.
        saved = api.read_build_list(self._h_target_dir(), self.department())
        wanted = set(saved) if saved is not None else set(manifest)
        self._rows = []
        # Building into a blank scene (nothing referenced yet): always start
        # from the latest published versions, whatever the shot used before
        # (user, 2026-10-19). In a scene that already has the shot's assets,
        # each row starts at the version the shot has.
        blank = not api.scene_references()
        for p in self._published:
            if p.get("kind") == "cache":
                continue        # never from the shot's list: see _add_shot_caches
            if self._key(p) in wanted and self._key(p) not in manifest:
                self._rows.append(self._row(p, p["latest"]))    # e.g. a new scratch drive
            elif self._key(p) in wanted:
                # A version from before personal publishes isn't on the H
                # drive any more: start the choice at the latest instead.
                current = api.entry_version_id(manifest[self._key(p)])
                self._rows.append(self._row(p, current if current in p["versions"]
                                            and not blank else p["latest"]))
            elif p.get("kind") == "camera":
                self._rows.append(self._row(p, p["latest"]))
        self._add_shot_caches()
        self._render_table()
        self.status.show_message(
            "" if self._published else "Nothing has been published for %s yet." % film,
            ok=bool(self._published))

    def _add_shot_caches(self):
        """The shot's caches join the list when the department builds them
        (Animation compares with them "occasionally", user 2026-10-28), or
        when the open scene already has one; unticked unless the scene's is
        out of date. They're per scene, never on the shot's saved list, so a
        cache built once doesn't come back ticked in every new scene of the
        shot. Never taken off when the department changes."""
        builds = api.CACHE_CODE in api.builds_for(self.department())
        have = set(self._key(r) for r in self._rows) | self._removed
        for p in self._published:
            if p.get("kind") != "cache" or self._key(p) in have:
                continue
            row = self._row(p, p["latest"])
            if row.get("in_scene") is None:
                if not builds:
                    continue
                row["checked"] = False
            self._rows.append(row)

    def _fill_keys_shots(self):
        """Keys from: this shot first, then the film's other shots."""
        film, seq, shot = self._target_shot
        shots = [s for s in api.list_shots(self._get_roots()[0], film) if s != (seq, shot)]
        self.keys_combo.blockSignals(True)
        self.keys_combo.clear()
        self.keys_combo.addItem("%s (this shot)" % shot, (film, seq, shot))
        for s, sh in shots:
            self.keys_combo.addItem(sh, (film, s, sh))
        self.keys_combo.blockSignals(False)

    def _row(self, p, chosen):
        """A list row. 'in_scene' is what the open scene already has (see
        api.scene_version); such a row starts at that version and is only
        built if the student picks another one ('start' remembers it)."""
        shot_dir = self._shot_dir()
        in_scene = api.scene_version(shot_dir, p) if shot_dir else None
        if in_scene in p["versions"]:
            chosen = in_scene
        row = dict(p, chosen=chosen, start=chosen, in_scene=in_scene)
        # Keys: an asset already in the scene starts at the keys Build put
        # on it, or "keep" if Build didn't (keyed by hand: never wiped
        # unasked). A new one starts at this shot's latest keys.
        if p.get("kind") in SHOT_ITEMS or not self._target_shot:
            keys = None         # keys come from shots
        elif in_scene is not None:
            keys = api.keys_in_scene(p) or api.KEEP_KEYS
        else:
            mine = self._keys_for(row, self._target_shot)
            keys = api.sorted_keys(mine)[0] if mine else api.NO_KEYS
        row.update(keys_chosen=keys, keys_start=keys)
        row["checked"] = not self._left_as_is(row, shot_dir)
        return row

    # -- keys -------------------------------------------------------------

    def _keys_source(self):
        """The shot the Keys dropdowns list: the one picked in Keys from,
        else the shot being built into."""
        picked = self.keys_combo.currentData()
        if self._target_shot and picked and picked[0] == self._target_shot[0]:
            return tuple(picked)
        return self._target_shot

    def _keys_for(self, p, shot):
        """{keys id: info} published in shot for this row's asset."""
        if not shot or p.get("kind") in SHOT_ITEMS:
            return {}
        if shot not in self._shot_keys:
            h_root = self._get_roots()[0]
            self._shot_keys[shot] = (api.list_shot_keys(h_root, *shot)
                                     if h_root and os.path.isdir(h_root) else {})
        return self._shot_keys[shot].get(self._key(p), {})

    def _keys_info(self, p, kid):
        """info for a keys id, from whichever shot it was published in."""
        if kid in (None, api.KEEP_KEYS, api.NO_KEYS) or not self._target_shot:
            return None
        shot = api.parse_keys_id(kid)[0]
        seq = next((s for s, sh in api.list_shots(self._get_roots()[0], self._target_shot[0])
                    if sh == shot), None) if shot != self._target_shot[2] else self._target_shot[1]
        return self._keys_for(p, (self._target_shot[0], seq, shot)).get(kid) if seq else None

    def _on_keys_source_changed(self, *args):
        if self._rows and self._keys_source() != self._keys_src:
            self._render_table()

    def _on_keys_changed(self, p, kid):
        """Picking other keys ticks the row; picking back what the scene has
        unticks it again."""
        p["keys_chosen"] = kid
        self._on_version_changed(p, p.get("chosen", p["latest"]))

    def _keys_cell(self, row, p):
        """The Keys dropdown: the picker's shot's publishes for this asset,
        newest first, plus the current choice and what the scene has (kept
        when the picker moves on), Keep, and None."""
        self.table.removeCellWidget(row, 4)
        if p.get("keys_chosen") is None:
            self.table.setItem(row, 4, _cell("-"))
            return
        listed = self._keys_for(p, self._keys_src)
        kids = api.sorted_keys(listed)
        for kid in (p["keys_chosen"], p["keys_start"]):
            if kid not in kids and kid not in (api.KEEP_KEYS, api.NO_KEYS):
                kids.append(kid)
        if p.get("in_scene") is not None and api.KEEP_KEYS in (p["keys_chosen"],
                                                               p["keys_start"]):
            kids.append(api.KEEP_KEYS)
        if not kids:
            self.table.setItem(row, 4, _cell("-"))
            return
        kids.append(api.NO_KEYS)
        latest = api.sorted_keys(listed)[0] if listed else None
        combo = QtWidgets.QComboBox()
        for kid in kids:
            combo.addItem(api.keys_label(kid, this_shot=self._target_shot[2],
                                         latest=latest), kid)
        combo.setCurrentIndex(max(combo.findData(p["keys_chosen"]), 0))
        combo.setToolTip("Keys from a Layout or Animation publish, newest first. Build "
                         "replaces this asset's keys with them. Pick another shot in "
                         "Keys from (above the list) to list that shot's keys.")
        combo.currentIndexChanged.connect(
            lambda i, c=combo, r=p: self._on_keys_changed(r, c.currentData()))
        self.table.setCellWidget(row, 4, combo)

    def _left_as_is(self, p, shot_dir):
        """True if a row starts unticked: already in the scene and its
        version and keys not changed in the list. A rig whose file in the
        shot is missing or out of date starts ticked, since building is the fix."""
        if (p.get("in_scene") is None or p.get("chosen") != p.get("start")
                or p.get("keys_chosen") != p.get("keys_start")):
            return False
        entry = api.read_manifest(shot_dir).get(api.manifest_key(
            p["asset_type"], p["asset"], p["code"]))
        return api.link_state(shot_dir, entry) not in (api.MISSING, api.STALE)

    def _on_refresh_clicked(self):
        # A scene opened from another drive since the tool opened: follow it.
        window = self.window()
        moved = window.follow_open_scene() if hasattr(window, "follow_open_scene") else None
        if moved:
            self.refresh()
            self.status.show_message("Scratch drive set to %s, where the open scene is."
                                     % moved)
            return
        self._refresh_list()

    def _refresh_list(self):
        """Re-read the H drive without losing the list: rows added but not
        built yet stay, and version choices and ticks stay where they
        still exist."""
        kept = [(self._key(r), r.get("chosen"), r["checked"], r.get("keys_chosen"))
                for r in self._rows]
        picked = (self.picker.film(), self.picker.department(), self.picker.group(),
                  self.picker.name())
        removed = self._removed
        self._load_shot()
        if not self._published:
            return
        # Taken off the list stays off on a refresh (until the shot changes).
        self._removed = removed
        self._rows = [r for r in self._rows if self._key(r) not in removed]
        by_key = dict((self._key(p), p) for p in self._published)
        in_list = dict((self._key(r), r) for r in self._rows)
        for key, chosen, checked, keys in kept:
            if key not in by_key:
                continue
            row = in_list.get(key)
            if row is None:
                row = self._row(by_key[key], by_key[key]["latest"])
                self._rows.append(row)
            if chosen in row["versions"]:
                row["chosen"] = chosen
            if keys is not None and row.get("keys_chosen") is not None:
                row["keys_chosen"] = keys
            row["checked"] = checked
        self.picker.set_current(*picked)
        self._render_table()
        manifest = api.read_manifest(self._shot_dir()) if self._shot_dir() else {}
        newer = [r["asset"] for r in self._rows
                 if api.newer_available(r, manifest.get(self._key(r)))]
        self.status.show_message(
            "Refreshed. Newer versions available for: %s" % ", ".join(newer)
            if newer else "Refreshed. Everything in this %s is on its latest version."
            % ("shot" if self._target_shot else "asset"))

    @staticmethod
    def _key(p):
        return api.manifest_key(p["asset_type"], p["asset"], p["code"])

    def _render_table(self):
        shot_dir = self._shot_dir()
        manifest = api.read_manifest(shot_dir) if shot_dir else {}
        self._keys_src = self._keys_source()
        self.table.blockSignals(True)
        self.table.setRowCount(len(self._rows))
        for row, p in enumerate(self._rows):
            self.table.setItem(row, 0, _check_cell(p["asset"], p["checked"]))
            self.table.setItem(row, 1, _cell(p["asset_type"]))
            self.table.setItem(row, 2, _cell(api.DEPT_LABELS.get(p["code"], p["code"])))
            combo = QtWidgets.QComboBox()
            for vid in api.sorted_versions(p):      # newest first, everyone's
                combo.addItem(api.version_label(p, vid), vid)
            combo.setCurrentIndex(max(combo.findData(p.get("chosen", p["latest"])), 0))
            combo.currentIndexChanged.connect(
                lambda i, c=combo, r=p: self._on_version_changed(r, c.currentData()))
            self.table.setCellWidget(row, 3, combo)
            self._keys_cell(row, p)

            entry = manifest.get(self._key(p))
            if not entry:
                self.table.setItem(row, 5, _cell("-"))
                self.table.setItem(row, 6, _cell("Ready to build", "#9fc5ff"))
            else:
                current = api.entry_version_id(entry)
                text = (api.version_label(p, current, mark_latest=False)
                        if current in p["versions"] else "v%03d (old)" % entry["version"])
                if p.get("in_scene") is not None and p.get("keys_start") not in (
                        None, api.KEEP_KEYS):
                    text += ", keys %s" % api.keys_label(p["keys_start"],
                                                         this_shot=self._target_shot[2])
                self.table.setItem(row, 5, _cell(text))
                state = api.link_state(shot_dir, entry)    # rigs only (spec §4a)
                if p.get("in_scene") is None:
                    self.table.setItem(row, 6, _cell("Not in this scene: Build adds it",
                                                     "#9fc5ff"))
                elif state in (api.MISSING, api.STALE):
                    self.table.setItem(row, 6, _cell(
                        "Rig file %s in this shot: Build to fix"
                        % ("missing" if state == api.MISSING else "out of date"), "#e0a060"))
                elif api.newer_available(p, entry):
                    self.table.setItem(row, 6, _cell(
                        "%s available" % api.version_label(p, p["latest"], mark_latest=False),
                        "#e0a060"))
                else:
                    self.table.setItem(row, 6, _cell(
                        "Up to date" + (" (full copy, not linked)" if state == api.COPY else ""),
                        "#7fbf7f"))
        self.table.resizeColumnsToContents()
        self.table.blockSignals(False)
        self._fill_filter()

    def _on_item_changed(self, item):
        """A row's tick: only ticked rows are built."""
        if item.column() == 0 and item.row() < len(self._rows):
            self._rows[item.row()]["checked"] = item.checkState() == QtCore.Qt.Checked

    def _on_version_changed(self, p, vid):
        """Picking another version ticks the row; picking back the one the
        scene has unticks it again."""
        p["chosen"] = vid
        p["checked"] = not self._left_as_is(p, self._shot_dir())
        rows = [i for i, r in enumerate(self._rows) if r is p]
        if rows:
            item = self.table.item(rows[0], 0)
            self.table.blockSignals(True)
            item.setCheckState(QtCore.Qt.Checked if p["checked"] else QtCore.Qt.Unchecked)
            self.table.blockSignals(False)

    def _fill_filter(self):
        """The Show menu: All, plus each department in the list. Keeps the
        current choice while that department is still in the list."""
        current = self.filter_combo.currentData()
        codes = []
        for p in self._rows:
            if p["code"] not in codes:
                codes.append(p["code"])
        order = api.DEPT_CODES + [api.CAMERA_CODE, api.CACHE_CODE]
        codes.sort(key=lambda c: order.index(c) if c in order else len(order))
        self.filter_combo.blockSignals(True)
        self.filter_combo.clear()
        self.filter_combo.addItem("All departments", None)
        for code in codes:
            self.filter_combo.addItem(api.DEPT_LABELS.get(code, code), code)
        self.filter_combo.setCurrentIndex(max(self.filter_combo.findData(current), 0))
        self.filter_combo.blockSignals(False)
        self._apply_filter()

    def _apply_filter(self, *args):
        code = self.filter_combo.currentData()
        for row, p in enumerate(self._rows):
            self.table.setRowHidden(row, bool(code) and p["code"] != code)

    # -- list -------------------------------------------------------------

    def _add_asset(self):
        """+ : add the publish Add to list points at to the list, ticked."""
        film, code = self.picker.film(), self.picker.department()
        group, name = self.picker.group(), self.picker.name()
        target = self._target_shot or self._target_asset
        if not target:
            self.status.show_message("Pick the shot or asset to build into under Build "
                                     "into first.", ok=False)
            return
        if film != target[0]:
            self.status.show_message("This %s is in %s: pick from %s's assets."
                                     % ("shot" if self._target_shot else "asset",
                                        target[0], target[0]), ok=False)
            return
        if not code:
            self.status.show_message("%s doesn't build anything yet."
                                     % self.target_picker.dept_combo.currentText(), ok=False)
            return
        match = [p for p in self._published
                 if p.get("kind") not in SHOT_ITEMS
                 and (p["asset_type"], p["asset"], p["code"]) == (group, name, code)]
        if not match:
            self.status.show_message("Nothing has been published for %s %s yet."
                                     % (name or "this", api.DEPT_LABELS.get(code, code)),
                                     ok=False)
            return
        p = match[0]
        if any(self._key(r) == self._key(p) for r in self._rows):
            self.status.show_message("%s %s is already in the list."
                                     % (p["asset"], api.DEPT_LABELS.get(code, code)), ok=False)
            return
        self._removed.discard(self._key(p))
        self._rows.append(self._row(p, p["latest"]))
        if self.filter_combo.currentData() not in (None, code):
            self.filter_combo.setCurrentIndex(0)    # don't add it out of sight
        self._render_table()

    def _remove_rows(self):
        """Take the selected rows off the list (user, 2026-10-21: list only).
        The open scene and the shot's record aren't touched, so Build Shot
        simply leaves those assets alone."""
        rows = sorted(set(i.row() for i in self.table.selectedIndexes()
                          if not self.table.isRowHidden(i.row())), reverse=True)
        if not rows:
            self.status.show_message("Click the rows to remove first (on their name, "
                                     "not the Version menu).", ok=False)
            return
        gone = []
        for r in rows:
            self._removed.add(self._key(self._rows[r]))
            gone.insert(0, "%s %s" % (self._rows[r]["asset"], api.DEPT_LABELS.get(
                self._rows[r]["code"], self._rows[r]["code"])))
            del self._rows[r]
        self._render_table()
        failed = self._save_shot_list()
        self.status.show_message("Taken off this shot's list: %s\n(Anything already in your "
                                 "scene stays there.)%s" % (", ".join(gone), failed),
                                 ok=not failed)

    def _save_shot_list(self):
        """Save the list as the department's list for the shot on the H
        drive. Returns '' or a line saying why it couldn't be saved (never
        stops a build)."""
        folder = self._h_target_dir()
        if not folder:
            return ""
        # Caches are per scene, never the shot's (see _add_shot_caches).
        keys = [self._key(r) for r in self._rows if r.get("kind") != "cache"]
        try:
            api.write_build_list(folder, self.department(), keys)
        except Exception as e:
            return "\nThis %s's list couldn't be saved to the H drive: %s" % (
                "shot" if self._target_shot else "asset", e)
        return ""

    # -- actions ----------------------------------------------------------

    def _build_shot(self):
        # Build Into isn't the project: refused (user, 2026-10-28).
        mismatch = self.target_mismatch()
        if mismatch:
            self.status.show_message(
                "Nothing built: Build into (%s) isn't your Maya project (%s). Set the "
                "project with the Project Tool and save your scene there, or go back to "
                "the project's %s." % (pub.place_label(mismatch["target"]),
                                       pub.place_label(mismatch["project"]),
                                       mismatch["project"]["kind"]), ok=False)
            return
        # The scene saved outside the project: refused too (user, 2026-10-28:
        # "the students will need help to stay on pipe"; was a warning).
        mismatch = api.pub.project_mismatch()
        if mismatch:
            self.status.show_message(
                "Nothing built: the open scene is in %s, but your Maya project is %s. "
                "Set Project to the scene's (the button above), or open a scene in %s."
                % (pub.place_label(mismatch["scene"]), pub.place_label(mismatch["project"]),
                   pub.place_label(mismatch["project"])), ok=False)
            return
        shot_dir = self._shot_dir()
        if not shot_dir:
            self.status.show_message("Pick the shot or asset to build into under Build "
                                     "into first.", ok=False)
            return
        if not any(p["checked"] for p in self._rows):
            # Nothing to build (e.g. an asset re-added that's already in the
            # scene), but the list is still the shot's list from now on.
            failed = self._save_shot_list()
            self.status.show_message("Nothing ticked to build. This %s's list is saved."
                                     % ("shot" if self._target_shot else "asset")
                                     if not failed else failed.strip(), ok=not failed)
            return

        lines, warnings, replaced, changed_rigs = [], [], [], []
        try:
            # Build never moves a project that's set (user, 2026-10-28:
            # "don't change the project"); with none from the pipe yet (a
            # fresh Maya) it still sets the shot, so references resolve.
            if (not pub.pipe_place(cmds.workspace(query=True, rootDirectory=True) or "")
                    and api.ensure_maya_project(shot_dir)):
                lines.append("Maya project set to %s" % os.path.basename(shot_dir))
                self._target_key = self._scene_and_project()
        except Exception as e:
            warnings.append(str(e))
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        try:
            for p in self._rows:
                if not p["checked"]:
                    continue
                label = "%s %s" % (p["asset"], api.DEPT_LABELS.get(p["code"], p["code"]))
                try:
                    done, warning, old = api.build_asset(shot_dir, p,
                                                         p.get("chosen", p["latest"]),
                                                         self.department())
                except Exception as e:
                    warnings.append("%s: %s" % (label, e))
                    continue
                # Keys go on after the asset: when they were changed, or with
                # an asset new to the scene (then None means nothing to do).
                keys = p.get("keys_chosen")
                if keys not in (None, api.KEEP_KEYS) and (
                        keys != p.get("keys_start")
                        or (p.get("in_scene") is None and keys != api.NO_KEYS)):
                    try:
                        keys_done, keys_warning = api.build_keys(
                            shot_dir, p, keys, self._keys_info(p, keys))
                        done += keys_done
                        if keys_warning:
                            warnings.append("%s: %s" % (label, keys_warning))
                        p["keys_start"] = keys
                    except Exception as e:
                        warnings.append("%s: keys not put on: %s" % (label, e))
                p["in_scene"] = p["start"] = p.get("chosen", p["latest"])
                p["checked"] = False        # built: nothing left to do for it
                lines.append("%s: %s" % (label, ", ".join(done)))
                if warning:
                    warnings.append("%s: %s" % (label, warning))
                if old:
                    replaced.append(old)
                    if p["code"] in api.LINKED_CODES and self._target_shot:
                        changed_rigs.append(p)      # other shots follow (spec §4a)
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        self._render_table()
        failed = self._save_shot_list()
        if failed:
            warnings.append(failed.strip())
        text = "\n".join(lines)
        if warnings:
            text += "\n\n" + "\n".join(warnings)
        self.status.show_message(text, ok=not warnings)
        replaced += self._offer_other_shots(changed_rigs, shot_dir)
        self._offer_removal(replaced, shot_dir)

    def _offer_other_shots(self, changed_rigs, shot_dir):
        """After a rig update or rollback: every shot follows by default
        (spec §4a), so ask whether the student's other shots should switch
        too. Their scenes load it the next time they're opened. Returns the
        versions those shots no longer use."""
        replaced = []
        for p in changed_rigs:
            vid = p.get("chosen", p["latest"])
            others = api.other_shots_using(shot_dir, p, vid)
            if not others:
                continue
            label = "%s %s" % (p["asset"], api.DEPT_LABELS.get(p["code"], p["code"]))
            box = QtWidgets.QMessageBox(self)
            box.setIcon(QtWidgets.QMessageBox.Question)
            box.setWindowTitle("Other shots")
            box.setText("Switch %s to %s in your other shots too?\n\n%s\n\n"
                        "They load it the next time you open them. Choose 'Only this "
                        "shot' to leave them as they are (e.g. when rolling back one shot)."
                        % (label, api.version_label(p, vid, mark_latest=False),
                           "\n".join("  " + os.path.basename(o) for o in others)))
            every = box.addButton("Every shot", QtWidgets.QMessageBox.AcceptRole)
            box.addButton("Only this shot", QtWidgets.QMessageBox.RejectRole)
            box.setDefaultButton(every)
            box.exec()
            if box.clickedButton() != every:
                continue
            try:
                updated, old = api.update_shots(others, p, vid)
            except Exception as e:
                self.status.show_message(self.status._text + "\n\n%s: other shots not "
                                         "updated: %s" % (label, e), ok=False)
                continue
            replaced += old
            self.status.show_message(self.status._text + "\n\n%s also switched in: %s"
                                     % (label, ", ".join(updated)), ok=True)
        return replaced

    def _offer_removal(self, replaced, shot_dir):
        """After an update: versions no shot uses any more can go to the
        Recycle Bin, but only if the student says so (spec "Clearing old
        versions")."""
        unused = api.unused_versions(replaced, api.maya_dir_of_shot(shot_dir))
        if not unused:
            return
        names = "\n".join("  " + os.path.basename(p) for p in unused)
        answer = QtWidgets.QMessageBox.question(
            self, "Old versions",
            "No longer used by any of your shots:\n\n%s\n\nRemove them from your "
            "scratch drive? They go to the Recycle Bin, and can always be pulled "
            "again from the H drive." % names)
        if answer != QtWidgets.QMessageBox.Yes:
            return
        # Each version's textures go with it.
        unused = [f for path in unused for f in api.version_files(path)]
        if api.send_to_recycle_bin(unused):
            self.status.show_message(self.status._text + "\n\nRemoved %d old version(s)."
                                     % len(unused), ok=True)
        else:
            self.status.show_message(self.status._text + "\n\nCouldn't remove some old "
                                     "versions (open in another program?).", ok=False)

    def _repair(self):
        h_root, _ = self._get_roots()
        if not h_root or not os.path.isdir(h_root):
            self.status.show_message("Set the H drive first.", ok=False)
            return
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        try:
            fixed, not_fixed = api.repair_scene(h_root)
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        if not fixed and not not_fixed:
            self.status.show_message("Repair: nothing missing in this scene.")
            return
        self.status.show_message("Repair:\n" + "\n".join(fixed + not_fixed), ok=not not_fixed)


# ---------------------------------------------------------------------------
# My Scratch tab
# ---------------------------------------------------------------------------

class ScratchTab(QtWidgets.QWidget):

    def __init__(self, get_roots, get_film, parent=None):
        super(ScratchTab, self).__init__(parent)
        self._get_roots = get_roots
        self._get_film = get_film
        self._items = []

        intro = QtWidgets.QLabel(
            "Everything on your scratch drive that holds files. Removing sends "
            "the files to the Recycle Bin; folders are kept.")
        intro.setWordWrap(True)
        self.table = _table(["Item", "Kind", "Size", "Latest publish", "Status"])
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.total_lbl = QtWidgets.QLabel()

        refresh_btn = QtWidgets.QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        remove_btn = QtWidgets.QPushButton("Remove from Scratch...")
        remove_btn.clicked.connect(self._remove_selected)
        buttons = QtWidgets.QHBoxLayout()
        buttons.addWidget(refresh_btn)
        buttons.addStretch(1)
        buttons.addWidget(remove_btn)

        self.status = StatusLabel()
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.total_lbl)
        layout.addLayout(buttons)
        layout.addWidget(self.status)

    def refresh(self):
        h_root, scratch_root = self._get_roots()
        film = self._get_film()
        self.table.setRowCount(0)
        self._items = []
        if not (film and scratch_root and os.path.isdir(scratch_root)):
            self.total_lbl.setText("")
            return
        self._items = api.scratch_items(scratch_root, h_root, film)
        self.table.setRowCount(len(self._items))
        for row, item in enumerate(self._items):
            text, colour = STATUS_TEXT[item["status"]]
            self.table.setItem(row, 0, _cell(item["label"]))
            self.table.setItem(row, 1, _cell(item["kind"]))
            self.table.setItem(row, 2, _cell(api.format_size(item["size"])))
            self.table.setItem(row, 3, _cell(item["latest"]))
            self.table.setItem(row, 4, _cell(text, colour))
        self.table.resizeColumnsToContents()
        total = sum(i["size"] for i in self._items)
        self.total_lbl.setText("%d item(s), %s on scratch for %s."
                               % (len(self._items), api.format_size(total), film))

    def _remove_selected(self):
        rows = sorted(set(i.row() for i in self.table.selectedIndexes()))
        if not rows:
            self.status.show_message("Pick an item to remove first.", ok=False)
            return
        item = self._items[rows[0]]
        try:
            api.removal_check(item["folder"], *self._get_roots())
        except api.BuildError as e:
            self.status.show_message(str(e), ok=False)
            return

        name = os.path.basename(item["folder"])
        summary = ("%d file(s), %s, from:\n%s\n\nThey go to the Recycle Bin, and the "
                   "folders are kept." % (len(item["files"]), api.format_size(item["size"]),
                                          item["folder"]))
        if item["status"] == api.SAFE:
            answer = QtWidgets.QMessageBox.question(
                self, "Remove from Scratch",
                "Remove '%s' from your scratch drive?\n\n%s\n\nEverything here is "
                "published or can be pulled again." % (name, summary))
            if answer != QtWidgets.QMessageBox.Yes:
                return
        else:
            # Risky: show exactly what isn't backed up, and make them type the name.
            shown = "\n".join(os.path.relpath(f, item["folder"]) for f in item["risky"][:12])
            if len(item["risky"]) > 12:
                shown += "\n... and %d more" % (len(item["risky"]) - 12)
            reason = ("These files changed after the last publish"
                      if item["status"] == api.CHANGED else
                      "These files aren't published or backed up anywhere")
            typed, ok = QtWidgets.QInputDialog.getText(
                self, "Remove from Scratch — not backed up",
                "WARNING: %s:\n\n%s\n\nRemoving '%s' moves %s\n\n"
                "Type %s to confirm:" % (reason, shown, name, summary, name))
            if not ok:
                return
            if typed.strip() != name:
                self.status.show_message("Name didn't match — nothing was removed.", ok=False)
                return

        if not self._close_scene_if_inside(item["folder"]):
            return
        if api.send_to_recycle_bin(item["files"]):
            self.status.show_message("Moved %d file(s) for '%s' to the Recycle Bin."
                                     % (len(item["files"]), name))
        else:
            self.status.show_message("Some files couldn't be moved to the Recycle Bin "
                                     "(open in another program?). Check %s." % item["folder"],
                                     ok=False)
        self.refresh()

    def _close_scene_if_inside(self, folder):
        scene = cmds.file(query=True, sceneName=True) or ""
        inside = os.path.normcase(os.path.normpath(scene)).startswith(
            os.path.normcase(os.path.normpath(folder)) + os.sep)
        if not inside:
            return True
        if cmds.file(query=True, modified=True):
            answer = QtWidgets.QMessageBox.question(
                self, "Open scene",
                "The open scene is in this folder and has unsaved changes.\n"
                "Close it WITHOUT saving and continue?")
            if answer != QtWidgets.QMessageBox.Yes:
                return False
        cmds.file(new=True, force=True)
        return True


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class BuildToolUI(QtWidgets.QDialog):

    def __init__(self, parent=None):
        super(BuildToolUI, self).__init__(parent or _maya_main_window())
        self.setWindowTitle("Build Tool")
        self.setObjectName("buildToolUI")
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.Window)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.resize(760, 480)

        # Same drive settings as the Publish tool.
        roots = QtWidgets.QFormLayout()
        self.root_edits = {}
        for key, label, hint in (
                (pub.H_DRIVE, "H drive:", "where publishes are, e.g. H:\\  or  F:\\"),
                (pub.SCRATCH, "Scratch drive:", "where you work, e.g. D:\\")):
            edit = QtWidgets.QLineEdit(pub.get_root(key))
            edit.setPlaceholderText(hint)
            edit.editingFinished.connect(lambda k=key: self._on_root_edited(k))
            browse_btn = QtWidgets.QPushButton("Browse...")
            browse_btn.clicked.connect(lambda checked=False, k=key: self._browse_root(k))
            row = QtWidgets.QHBoxLayout()
            row.addWidget(edit, 1)
            row.addWidget(browse_btn)
            roots.addRow(label, row)
            self.root_edits[key] = edit

        self.build_tab = BuildShotTab(self._roots)
        self.scratch_tab = ScratchTab(self._roots, self.build_tab.film)
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.addTab(self.build_tab, "Build Shot")
        self.tabs.addTab(self.scratch_tab, "My Scratch")
        self.tabs.currentChanged.connect(self._on_tab_changed)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(roots)
        layout.addWidget(self.tabs, 1)
        self.refresh()

    def _root(self, key):
        return pub.resolve_root(self.root_edits[key].text().strip())

    def _roots(self):
        return self._root(pub.H_DRIVE), self._root(pub.SCRATCH)

    def _on_root_edited(self, key):
        if self._root(key):
            pub.set_root(key, self._root(key))
        self.refresh()

    def _browse_root(self, key):
        name = "H drive" if key == pub.H_DRIVE else "scratch drive"
        path = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Choose the %s (the drive, or its film folder)" % name, self._root(key))
        if path:
            self.root_edits[key].setText(os.path.normpath(path))
            self._on_root_edited(key)

    def refresh(self):
        moved = self.follow_open_scene()
        self.build_tab.refresh()
        if self.tabs.currentWidget() is self.scratch_tab:
            self.scratch_tab.refresh()
        if moved:
            self.build_tab.status.show_message(
                "Scratch drive set to %s, where the open scene is." % moved)

    def follow_open_scene(self):
        """The scratch drive follows the open scene (spec "Scratch drive
        follows the work"); the saved setting is only the fallback.
        Returns the new scratch drive if it changed, else None."""
        moved = pub.follow_open_scene(*self._roots())
        if moved:
            self.root_edits[pub.SCRATCH].setText(moved)
        return moved

    def _on_tab_changed(self, index):
        # Scanning scratch walks every file, so only do it when the tab is shown.
        if self.tabs.widget(index) is self.scratch_tab:
            self.scratch_tab.refresh()
        else:
            self.build_tab._load_shot()

    def changeEvent(self, event):
        # Builds go into the open scene: if another one was opened while
        # the window was in the background, follow it.
        if event.type() == QtCore.QEvent.ActivationChange and self.isActiveWindow():
            self.build_tab.check_target()
        super(BuildToolUI, self).changeEvent(event)


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
    _instance = BuildToolUI()
    _instance.show()
    return _instance
