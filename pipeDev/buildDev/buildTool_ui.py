"""
Build Tool — UI
Two tabs:
  Build Shot  — list the assets a shot needs; one click pulls them from
                the H drive and references them into the open scene.
  My Scratch  — what's on the scratch drive, how safe it is to remove,
                and removal to the Recycle Bin.

Dev launch (Script Editor, Python tab):

    import sys, importlib
    for p in (r"C:\\Users\\scout\\Documents\\maya\\scriptDev\\pipeDev\\publishDev",
              r"C:\\Users\\scout\\Documents\\maya\\scriptDev\\pipeDev\\buildDev"):
        if p not in sys.path: sys.path.insert(0, p)
    import publishTool_api, pipeEnv, buildTool_api, buildTool_ui
    for m in (publishTool_api, pipeEnv, buildTool_api, buildTool_ui): importlib.reload(m)
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
pub = api.pub

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


def _cell(text, colour=None):
    item = QtWidgets.QTableWidgetItem(text)
    if colour:
        item.setForeground(QtGui.QColor(colour))
    return item


# ---------------------------------------------------------------------------
# Build Shot tab
# ---------------------------------------------------------------------------

class BuildShotTab(QtWidgets.QWidget):
    """Pick assets from the H drive into a list for the shot, then Build
    Shot pulls + references (or updates) all of them in one click."""

    def __init__(self, get_roots, parent=None):
        super(BuildShotTab, self).__init__(parent)
        self._get_roots = get_roots
        self._published = []     # everything on the H drive
        self._rows = []          # the shot's list: published entries shown in the table
        self._removed = set()    # keys taken off this shot's list (kept until the shot changes)

        # Which shot.
        self.film_combo = QtWidgets.QComboBox()
        self.film_combo.currentIndexChanged.connect(self._fill_shots)
        self.shot_combo = QtWidgets.QComboBox()
        self.shot_combo.setMinimumWidth(180)
        self.shot_combo.currentIndexChanged.connect(self._load_shot)
        project_btn = QtWidgets.QPushButton("Set Maya Project")
        project_btn.setToolTip("Make this shot the current Maya project. "
                               "Build Shot also does this for you.")
        project_btn.clicked.connect(self._set_project)
        top = QtWidgets.QHBoxLayout()
        top.addWidget(QtWidgets.QLabel("Film:"))
        top.addWidget(self.film_combo)
        top.addWidget(QtWidgets.QLabel("Shot:"))
        top.addWidget(self.shot_combo, 1)
        top.addWidget(project_btn)

        # Which asset to add from the H drive.
        self.asset_combo = QtWidgets.QComboBox()
        self.asset_combo.setMinimumWidth(200)
        self.asset_combo.currentIndexChanged.connect(self._fill_departments)
        self.dept_combo = QtWidgets.QComboBox()
        add_btn = QtWidgets.QPushButton("Add to Shot")
        add_btn.clicked.connect(self._add_asset)
        pick = QtWidgets.QHBoxLayout()
        pick.addWidget(QtWidgets.QLabel("Add asset:"))
        pick.addWidget(self.asset_combo, 1)
        pick.addWidget(QtWidgets.QLabel("as"))
        pick.addWidget(self.dept_combo)
        pick.addWidget(add_btn)

        # The shot's asset list, filtered by department (user, 2026-10-21).
        self.filter_combo = QtWidgets.QComboBox()
        self.filter_combo.setToolTip("Show only one department's assets in the list. "
                                     "Build Shot still builds the whole list.")
        self.filter_combo.currentIndexChanged.connect(self._apply_filter)
        show = QtWidgets.QHBoxLayout()
        show.addWidget(QtWidgets.QLabel("Show:"))
        show.addWidget(self.filter_combo)
        show.addStretch(1)
        self.table = _table(["Asset", "Type", "Department", "Version",
                             "In this shot", "Status"])
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        remove_btn = QtWidgets.QPushButton("Remove from List")
        remove_btn.setToolTip("Take the selected assets off the list. Only the list "
                              "changes: anything already in your scene stays there.")
        remove_btn.clicked.connect(self._remove_rows)
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
        list_btns.addWidget(remove_btn)

        build_btn = QtWidgets.QPushButton("Build Shot")
        build_btn.setMinimumHeight(36)
        build_btn.setToolTip(
            "Adds every asset in the list that isn't in the open scene yet "
            "(pulled from the H drive into your scratch publish folder). Assets "
            "already in the scene are left as they are, unless you pick another "
            "version for them in the list.")
        build_btn.clicked.connect(self._build_shot)

        self.status = StatusLabel()
        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(top)
        layout.addLayout(pick)
        layout.addLayout(show)
        layout.addWidget(self.table, 1)
        layout.addLayout(list_btns)
        layout.addWidget(build_btn)
        layout.addWidget(self.status)

    # -- filling ----------------------------------------------------------

    def refresh(self):
        h_root, scratch_root = self._get_roots()
        current = self.film_combo.currentText()
        self.film_combo.blockSignals(True)
        self.film_combo.clear()
        films = api.list_films(h_root) if h_root else []
        self.film_combo.addItems(films)
        if current in films:
            self.film_combo.setCurrentText(current)
        self.film_combo.blockSignals(False)
        self._fill_shots()

    def _fill_shots(self, *args):
        h_root, scratch_root = self._get_roots()
        film = self.film_combo.currentText()
        current = self.shot_combo.currentData()
        scene_shot = api.shot_of_scene(cmds.file(query=True, sceneName=True) or "",
                                       scratch_root) if scratch_root else None
        self.shot_combo.blockSignals(True)
        self.shot_combo.clear()
        if film and scratch_root and os.path.isdir(scratch_root):
            for seq, shot in api.list_shots(scratch_root, film):
                self.shot_combo.addItem(shot, "%s/%s" % (seq, shot))
        # Prefer the shot already picked, else the shot the open scene is in.
        for wanted in (current, "%s/%s" % scene_shot[1:] if scene_shot else None):
            index = self.shot_combo.findData(wanted) if wanted else -1
            if index >= 0:
                self.shot_combo.setCurrentIndex(index)
                break
        self.shot_combo.blockSignals(False)
        self._load_shot()

    def _shot_dir(self):
        h_root, scratch_root = self._get_roots()
        data = self.shot_combo.currentData()
        film = self.film_combo.currentText()
        if not (data and film and scratch_root):
            return None
        seq, shot = data.split("/")
        return api.shot_folder(scratch_root, film, seq, shot)

    def _load_shot(self, *args):
        """Re-read the H drive, fill the asset picker, and start the list
        with whatever is already in this shot."""
        h_root, scratch_root = self._get_roots()
        film = self.film_combo.currentText()
        self._published, self._rows, self._removed = [], [], set()
        self.asset_combo.clear()
        self._render_table()
        try:
            pub.check_roots(pub.resolve_root(h_root), pub.resolve_root(scratch_root))
        except pub.PublishError as e:
            self.status.show_message(str(e), ok=False)
            return
        if not film:
            self.status.show_message("No film folders found on the H drive.", ok=False)
            return
        self._published = api.list_published(h_root, film)
        shot = self.shot_combo.currentData()
        if shot:
            # The shot's own camera, if one has been published (spec "Cameras").
            self._published += api.list_shot_cameras(h_root, film, *shot.split("/"))

        seen = []
        for p in self._published:
            if (p["asset_type"], p["asset"]) not in seen:
                seen.append((p["asset_type"], p["asset"]))
                self.asset_combo.addItem("%s  (%s)" % (p["asset"], p["asset_type"]),
                                         "%s/%s" % (p["asset_type"], p["asset"]))
        self._fill_departments()

        shot_dir = self._shot_dir()
        manifest = api.read_manifest(shot_dir) if shot_dir else {}
        # The list always starts with everything that belongs to this shot:
        # what's already in its assets folder (at the version it has), plus
        # anything published for the shot itself, e.g. its camera, ready to build.
        self._rows = []
        # Building into a blank scene (nothing referenced yet): always start
        # from the latest published versions, whatever the shot used before
        # (user, 2026-10-19). In a scene that already has the shot's assets,
        # each row starts at the version the shot has.
        blank = not api.scene_references()
        for p in self._published:
            if self._key(p) in manifest:
                # A version from before personal publishes isn't on the H
                # drive any more: start the choice at the latest instead.
                current = api.entry_version_id(manifest[self._key(p)])
                self._rows.append(self._row(p, current if current in p["versions"]
                                            and not blank else p["latest"]))
            elif p.get("kind") == "camera":
                self._rows.append(self._row(p, p["latest"]))
        self._render_table()
        self.status.show_message(
            "" if self._published else "Nothing has been published for %s yet." % film,
            ok=bool(self._published))

    def _row(self, p, chosen):
        """A list row. 'in_scene' is what the open scene already has (see
        api.scene_version); such a row starts at that version and is only
        built if the student picks another one ('start' remembers it)."""
        shot_dir = self._shot_dir()
        in_scene = api.scene_version(shot_dir, p) if shot_dir else None
        if in_scene in p["versions"]:
            chosen = in_scene
        return dict(p, chosen=chosen, start=chosen, in_scene=in_scene)

    @staticmethod
    def _left_as_is(p, shot_dir):
        """True if Build Shot should skip this row: already in the scene and
        its version not changed in the list. A rig whose file in the shot is
        missing or out of date is still built, since that's the fix."""
        if p.get("in_scene") is None or p.get("chosen") != p.get("start"):
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
        built yet stay, and version choices stay where they still exist."""
        kept = [(self._key(r), r.get("chosen")) for r in self._rows]
        picked = (self.asset_combo.currentData(), self.dept_combo.currentData())
        removed = self._removed
        self._load_shot()
        if not self._published:
            return
        # Taken off the list stays off on a refresh (until the shot changes).
        self._removed = removed
        self._rows = [r for r in self._rows if self._key(r) not in removed]
        by_key = dict((self._key(p), p) for p in self._published)
        in_list = dict((self._key(r), r) for r in self._rows)
        for key, chosen in kept:
            if key not in by_key:
                continue
            row = in_list.get(key)
            if row is None:
                row = self._row(by_key[key], by_key[key]["latest"])
                self._rows.append(row)
            if chosen in row["versions"]:
                row["chosen"] = chosen
        index = self.asset_combo.findData(picked[0]) if picked[0] else -1
        if index >= 0:
            self.asset_combo.setCurrentIndex(index)
            dept = self.dept_combo.findData(picked[1])
            if dept >= 0:
                self.dept_combo.setCurrentIndex(dept)
        self._render_table()
        manifest = api.read_manifest(self._shot_dir()) if self._shot_dir() else {}
        newer = [r["asset"] for r in self._rows
                 if api.newer_available(r, manifest.get(self._key(r)))]
        self.status.show_message(
            "Refreshed. Newer versions available for: %s" % ", ".join(newer)
            if newer else "Refreshed. Everything in this shot is on its latest version.")

    def _fill_departments(self, *args):
        self.dept_combo.clear()
        data = self.asset_combo.currentData()
        for p in self._published:
            if "%s/%s" % (p["asset_type"], p["asset"]) == data:
                self.dept_combo.addItem(api.DEPT_LABELS.get(p["code"], p["code"]), p["code"])

    @staticmethod
    def _key(p):
        return api.manifest_key(p["asset_type"], p["asset"], p["code"])

    def _render_table(self):
        shot_dir = self._shot_dir()
        manifest = api.read_manifest(shot_dir) if shot_dir else {}
        self.table.setRowCount(len(self._rows))
        for row, p in enumerate(self._rows):
            self.table.setItem(row, 0, _cell(p["asset"]))
            self.table.setItem(row, 1, _cell(p["asset_type"]))
            self.table.setItem(row, 2, _cell(api.DEPT_LABELS.get(p["code"], p["code"])))
            combo = QtWidgets.QComboBox()
            for vid in api.sorted_versions(p):      # newest first, everyone's
                combo.addItem(api.version_label(p, vid), vid)
            combo.setCurrentIndex(max(combo.findData(p.get("chosen", p["latest"])), 0))
            combo.currentIndexChanged.connect(
                lambda i, c=combo, r=p: r.__setitem__("chosen", c.currentData()))
            self.table.setCellWidget(row, 3, combo)

            entry = manifest.get(self._key(p))
            if not entry:
                self.table.setItem(row, 4, _cell("-"))
                self.table.setItem(row, 5, _cell("Ready to build", "#9fc5ff"))
            else:
                current = api.entry_version_id(entry)
                self.table.setItem(row, 4, _cell(
                    api.version_label(p, current, mark_latest=False)
                    if current in p["versions"] else "v%03d (old)" % entry["version"]))
                state = api.link_state(shot_dir, entry)    # rigs only (spec §4a)
                if p.get("in_scene") is None:
                    self.table.setItem(row, 5, _cell("Not in this scene: Build adds it",
                                                     "#9fc5ff"))
                elif state in (api.MISSING, api.STALE):
                    self.table.setItem(row, 5, _cell(
                        "Rig file %s in this shot: Build to fix"
                        % ("missing" if state == api.MISSING else "out of date"), "#e0a060"))
                elif api.newer_available(p, entry):
                    self.table.setItem(row, 5, _cell(
                        "%s available" % api.version_label(p, p["latest"], mark_latest=False),
                        "#e0a060"))
                else:
                    self.table.setItem(row, 5, _cell(
                        "Up to date" + (" (full copy, not linked)" if state == api.COPY else ""),
                        "#7fbf7f"))
        self.table.resizeColumnsToContents()
        self._fill_filter()

    def _fill_filter(self):
        """The Show menu: All, plus each department in the list. Keeps the
        current choice while that department is still in the list."""
        current = self.filter_combo.currentData()
        codes = []
        for p in self._rows:
            if p["code"] not in codes:
                codes.append(p["code"])
        order = api.DEPT_CODES + [api.CAMERA_CODE]
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
        data, code = self.asset_combo.currentData(), self.dept_combo.currentData()
        match = [p for p in self._published
                 if "%s/%s" % (p["asset_type"], p["asset"]) == data and p["code"] == code]
        if not match:
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
        self.status.show_message("Taken off the list: %s\n(Anything already in your scene "
                                 "stays there.)" % ", ".join(gone))

    # -- actions ----------------------------------------------------------

    def _set_project(self):
        shot_dir = self._shot_dir()
        if not shot_dir:
            return
        try:
            api.set_maya_project(shot_dir)
        except Exception as e:
            self.status.show_message(str(e), ok=False)
            return
        self.status.show_message("Maya project set to %s" % shot_dir)

    def _build_shot(self):
        shot_dir = self._shot_dir()
        if not shot_dir or not self._rows:
            self.status.show_message("Pick a shot and add assets to the list first.", ok=False)
            return
        scene_shot = api.shot_of_scene(cmds.file(query=True, sceneName=True) or "",
                                       self._get_roots()[1])
        if scene_shot and "%s/%s" % scene_shot[1:] != self.shot_combo.currentData():
            answer = QtWidgets.QMessageBox.question(
                self, "Different shot",
                "The open scene belongs to shot %s, but you're building %s.\n"
                "Reference these assets into the open scene anyway?"
                % (scene_shot[2], self.shot_combo.currentText()))
            if answer != QtWidgets.QMessageBox.Yes:
                return

        lines, warnings, replaced, changed_rigs = [], [], [], []
        try:
            if api.ensure_maya_project(shot_dir):
                lines.append("Maya project set to %s" % os.path.basename(shot_dir))
        except Exception as e:
            warnings.append(str(e))
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        try:
            for p in self._rows:
                label = "%s %s" % (p["asset"], api.DEPT_LABELS.get(p["code"], p["code"]))
                if self._left_as_is(p, shot_dir):
                    lines.append("%s: already in the scene, left as is" % label)
                    continue
                try:
                    done, warning, old = api.build_asset(shot_dir, p,
                                                         p.get("chosen", p["latest"]))
                except Exception as e:
                    warnings.append("%s: %s" % (label, e))
                    continue
                p["in_scene"] = p["start"] = p.get("chosen", p["latest"])
                lines.append("%s: %s" % (label, ", ".join(done)))
                if warning:
                    warnings.append("%s: %s" % (label, warning))
                if old:
                    replaced.append(old)
                    if p["code"] in api.LINKED_CODES:
                        changed_rigs.append(p)
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        self._render_table()
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
        self.scratch_tab = ScratchTab(self._roots, self.build_tab.film_combo.currentText)
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
