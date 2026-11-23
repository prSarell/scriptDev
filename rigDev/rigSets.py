"""
Rig Sets (mpRig shelf): checks the open rig for the sets a pipe Rigging
publish needs and offers to make the missing ones.

    cache_SET           the geometry that gets rendered (what a shot caches)
    character:  body_controls_SET  (required)
                face_controls_SET  (required for a MetaHuman, else optional)
    anything else (environment, prop, vehicle...):
                controls_SET       (required; no face set, no body_)

The asset type comes from the scene's folder (<film>\\maya\\assets\\<type>\\
...); outside the pipe you pick it. Suggestions: cache_SET = the visible
meshes in the rig's top group that aren't blendshape targets; controls =
its visible curve transforms named like controls (rig_rules.CONTROL_NAMES),
or an mGear / Advanced Skeleton controls set if there is one. Nothing is
made without the rigger saying so, and nothing existing is changed except
by Add Selected / Rename.

With the pipe installed (mpPipe), the set names come from its rig_rules.py
and Publish's own rig checks run too, so "ready" here means Publish
accepts it. Without it, the built-in names below are used (kept equal to
rig_rules by pipeDev/publishDev/test_rigSetsTool_mayapy.py).

    import rigSets; rigSets.show()
"""
import fnmatch
import os

import maya.cmds as cmds

try:
    import rig_rules as _rules
except ImportError:         # mpRig without the pipe
    _rules = None

CACHE_SET = "cache_SET"
CHARACTER_TYPES = ("character",)
CHARACTER_CONTROL_SETS = {"body": "body_controls_SET", "face": "face_controls_SET"}
OTHER_CONTROL_SETS = {"body": "controls_SET", "face": None}
CONTROL_NAMES = ["*_ctl", "*_CTL", "*_Ctl", "*_ctrl", "*_CTRL", "*_Ctrl",
                 "*Ctrl", "CTRL_*", "*_ctl[0-9]*", "*_CTL[0-9]*"]
KNOWN_SETS = [
    ("*_controllers_grp", "body", ""),
    ("FacialControls", "face", ""),
    ("ControlSet", "body", ""),
    ("FaceControlSet", "face", ""),
    ("AllSet", None, ""),
]
METAHUMAN_DNA_TYPE = "embeddedNodeRL4"
if _rules is not None:
    CACHE_SET = getattr(_rules, "CACHE_SET", CACHE_SET)
    CHARACTER_TYPES = getattr(_rules, "CHARACTER_TYPES", CHARACTER_TYPES)
    CHARACTER_CONTROL_SETS = getattr(_rules, "CHARACTER_CONTROL_SETS", CHARACTER_CONTROL_SETS)
    OTHER_CONTROL_SETS = getattr(_rules, "OTHER_CONTROL_SETS", OTHER_CONTROL_SETS)
    CONTROL_NAMES = getattr(_rules, "CONTROL_NAMES", CONTROL_NAMES)
    if getattr(_rules, "KNOWN_SETS", None) and len(_rules.KNOWN_SETS[0]) == 3:
        KNOWN_SETS = _rules.KNOWN_SETS
    METAHUMAN_DNA_TYPE = _rules.METAHUMAN.get("dna_node_type", METAHUMAN_DNA_TYPE)

CAMERAS = ("persp", "top", "front", "side")
CHARACTER = "character"
OTHER = "other"


# ---------------------------------------------------------------------------
# What the scene is
# ---------------------------------------------------------------------------

def scene_asset_type(path=None):
    """The asset type folder of a scene in <film>\\maya\\assets\\<type>\\...,
    lower case, else None."""
    path = path if path is not None else (cmds.file(query=True, sceneName=True) or "")
    parts = [p for p in os.path.normpath(path).replace("\\", "/").split("/") if p]
    for i in range(len(parts) - 2):
        if parts[i].lower() == "maya" and parts[i + 1].lower() == "assets":
            return parts[i + 2].lower()
    return None


def is_character(asset_type):
    return asset_type in (None, CHARACTER) or asset_type.lower() in CHARACTER_TYPES


def set_names(asset_type):
    """{"cache", "body", "face" (None for non-characters)}."""
    names = dict(CHARACTER_CONTROL_SETS if is_character(asset_type) else OTHER_CONTROL_SETS)
    names["cache"] = CACHE_SET
    return names


def _short(node):
    return node.split("|")[-1].split(":")[-1]


def top_group(selection=None):
    """The rig's top group (long name): the top of the selection, else the
    scene's one top-level group. None if that isn't one group."""
    selection = cmds.ls(selection=True, long=True) if selection is None else \
        cmds.ls(selection, long=True)
    if selection:
        tops = sorted(set("|" + n.split("|")[1] for n in selection if n.startswith("|")))
    else:
        tops = [t for t in cmds.ls(assemblies=True, long=True) or []
                if _short(t) not in CAMERAS
                and not cmds.listRelatives(t, shapes=True)
                and cmds.objectType(t, isAType="transform")]
    return tops[0] if len(tops) == 1 else None


def own_sets(name):
    """Object sets called name (any namespace), not from a reference."""
    return [s for s in cmds.ls(type="objectSet") or []
            if _short(s) == name and not cmds.referenceQuery(s, isNodeReferenced=True)]


def _descendants(top, node_type):
    return cmds.listRelatives(top, allDescendents=True, fullPath=True, type=node_type) or []


def _visible(transforms):
    visible = set(cmds.ls(transforms, visible=True, long=True) or [])
    return [t for t in transforms if t in visible]


def _not_nested(nodes):
    return [n for n in nodes if not any(n.startswith(o + "|") for o in nodes if o != n)]


def _members(object_set):
    """Everything in a set, following sets inside it (long names)."""
    found, todo, seen = [], [object_set], set()
    while todo:
        s = todo.pop()
        if s in seen:
            continue
        seen.add(s)
        for m in cmds.sets(s, query=True) or []:
            if cmds.nodeType(m) == "objectSet":
                todo.append(m)
            else:
                found += cmds.ls(m, long=True) or []
    return found


# ---------------------------------------------------------------------------
# Suggestions
# ---------------------------------------------------------------------------

def suggest_cache(top):
    """Visible meshes under top that aren't blendshape targets (transforms,
    none inside another)."""
    if not top:
        return []
    found = []
    for shape in _descendants(top, "mesh"):
        if cmds.getAttr(shape + ".intermediateObject"):
            continue
        if cmds.listConnections(shape + ".worldMesh", type="blendShape", source=False):
            continue                # a blendshape target, not render geo
        parent = cmds.listRelatives(shape, parent=True, fullPath=True)[0]
        if parent not in found:
            found.append(parent)
    return _not_nested(_visible(found))


def _known_sets(role):
    return [s for s in cmds.ls(type="objectSet") or []
            if not cmds.referenceQuery(s, isNodeReferenced=True)
            and any(r == role and fnmatch.fnmatchcase(_short(s), p) for p, r, _ in KNOWN_SETS)]


def suggest_controls(top, role="body", character=False):
    """What should go in the controls set: an mGear / Advanced Skeleton set
    of that role if there is one, else visible curve transforms under top
    named like controls (all visible curves if none are). A non-character's
    one controls set takes the face sets too. MetaHuman CTRL_ face
    controls go in the face set, never the body one."""
    roles = [role] if character else ["body", "face"]
    known = [s for r in roles for s in _known_sets(r)]
    if known:
        return known
    if not top or role == "face":
        return []
    curves = []
    for shape in _descendants(top, "nurbsCurve"):
        if cmds.getAttr(shape + ".intermediateObject"):
            continue
        parent = cmds.listRelatives(shape, parent=True, fullPath=True)[0]
        if parent not in curves:
            curves.append(parent)
    curves = _visible(curves)
    if character:
        curves = [c for c in curves if not _short(c).startswith("CTRL_")]
    named = [c for c in curves if any(fnmatch.fnmatchcase(_short(c), p) for p in CONTROL_NAMES)]
    return named or curves


def has_metahuman():
    try:
        return bool(cmds.ls(type=METAHUMAN_DNA_TYPE))
    except RuntimeError:
        return False


# ---------------------------------------------------------------------------
# Checking
# ---------------------------------------------------------------------------

def check(asset_type, top=None):
    """One row per set the rig needs:
    {key, name, required, set (node or None), count, ok, status,
     suggestion: [nodes], wrong: node with the other kind's name or None}."""
    names = set_names(asset_type)
    character = is_character(asset_type)
    other = OTHER_CONTROL_SETS if character else CHARACTER_CONTROL_SETS
    metahuman = character and has_metahuman()
    rows = []
    for key in ("cache", "body", "face"):
        name = names.get(key)
        if not name:
            continue
        required = key != "face" or metahuman
        found = own_sets(name)
        row = {"key": key, "name": name, "required": required, "set": None, "count": 0,
               "ok": False, "status": "", "suggestion": [], "wrong": None}
        if key == "cache":
            row["suggestion"] = suggest_cache(top)
        else:
            row["suggestion"] = suggest_controls(top, key, character)
        if len(found) > 1:
            row["status"] = "more than one (%s): keep just one" % ", ".join(found)
        elif found:
            row["set"] = found[0]
            members = _members(found[0])
            row["count"] = len(members)
            outside = [m for m in members if top and not
                       (m == top or m.startswith(top + "|"))]
            if key == "cache":
                geo_types = ("mesh", "nurbsSurface", "subdiv")
                geo = [m for m in members if cmds.nodeType(m) in geo_types
                       or (cmds.objectType(m, isAType="transform")
                           and cmds.listRelatives(m, allDescendents=True, type=geo_types))]
                transforms = [m for m in members if cmds.objectType(m, isAType="transform")]
                if not members:
                    row["status"] = "empty"
                elif not geo:
                    row["status"] = "no geometry in it"
                elif len(_not_nested(transforms)) != len(transforms):
                    row["status"] = "holds a group and things inside it: keep one or the other"
                elif outside:
                    row["status"] = "%d thing(s) outside the rig's top group" % len(outside)
                else:
                    row["ok"], row["status"] = True, "%d item(s)" % len(members)
            else:
                ctrls = [m for m in members if cmds.objectType(m, isAType="transform")]
                if not ctrls and key == "face" and metahuman:
                    row["ok"] = True
                    row["status"] = "empty: fine, Publish adds the MetaHuman face controls"
                elif not ctrls:
                    row["status"] = "empty" if key != "face" else \
                        "empty: add the face controls, or delete it if there's no face"
                elif outside:
                    row["status"] = "%d control(s) outside the rig's top group" % len(outside)
                else:
                    row["ok"], row["status"] = True, "%d control(s)" % len(ctrls)
        else:
            if key == "body":
                wrong = own_sets(other["body"])     # e.g. body_controls_SET on a prop
                row["wrong"] = wrong[0] if len(wrong) == 1 else None
            if row["wrong"]:
                row["status"] = "missing: the controls are in %s, rename it" % _short(row["wrong"])
            elif required:
                row["status"] = "missing"
            else:
                row["ok"], row["status"] = True, "not needed (optional)"
        rows.append(row)
    return rows


def wrong_kind_sets(asset_type):
    """Sets named for the other kind of rig that would be left over, e.g. a
    face_controls_SET on a prop."""
    if is_character(asset_type):
        return own_sets(OTHER_CONTROL_SETS["body"])
    return [s for n in CHARACTER_CONTROL_SETS.values() if n for s in own_sets(n)]


def publish_check(asset_type, top):
    """Publish's own verdict on the rig (pipe installed): None = ready,
    else its message. Raises ImportError without the pipe."""
    import publishTool_api as api
    try:
        api.check_script_nodes()
        api.check_rig_selection([top] if top else [])
        api.check_cache_set([top])
        api.check_control_sets([top], asset_type)
    except api.PublishError as e:
        return str(e)
    return None


# ---------------------------------------------------------------------------
# Making
# ---------------------------------------------------------------------------

def make_set(name, members):
    """A new set called exactly name holding members. Raises RuntimeError if
    something else already has that name."""
    if cmds.objExists(name):
        raise RuntimeError("Something in the scene is already called %s." % name)
    made = cmds.sets(empty=True, name=name)
    if made != name:
        cmds.delete(made)
        raise RuntimeError("Maya wouldn't name the set %s." % name)
    if members:
        cmds.sets(members, add=made)
    return made


def add_to_set(object_set, members):
    if members:
        cmds.sets(members, add=object_set)


def rename_set(node, name):
    if cmds.objExists(name):
        raise RuntimeError("Something in the scene is already called %s." % name)
    return cmds.rename(node, name)


def build_missing(rows):
    """Make every required set that's missing (and not just misnamed) from
    its suggestion. Returns [(name, count)]."""
    made = []
    cmds.undoInfo(openChunk=True, chunkName="rigSets_build")
    try:
        for row in rows:
            if row["set"] or row["wrong"] or not row["required"] or row["status"].startswith("more"):
                continue
            make_set(row["name"], row["suggestion"])
            made.append((row["name"], len(row["suggestion"])))
    finally:
        cmds.undoInfo(closeChunk=True)
    return made


# ---------------------------------------------------------------------------
# Window
# ---------------------------------------------------------------------------

WINDOW_NAME = "mpRigSetsTool"
TYPE_CHOICES = [("Character (body + face controls)", CHARACTER),
                ("Environment, prop, vehicle... (one controls set)", OTHER)]


def _maya_main_window():
    from maya import OpenMayaUI as omui
    from PySide6 import QtWidgets
    from shiboken6 import wrapInstance
    ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(ptr), QtWidgets.QWidget) if ptr else None


def show():
    from PySide6 import QtWidgets
    for w in QtWidgets.QApplication.topLevelWidgets():
        if w.objectName() == WINDOW_NAME:
            w.close()
            w.deleteLater()
    win = _window_class()(_maya_main_window())
    win.show()
    return win


def _window_class():
    import html
    from PySide6 import QtWidgets, QtCore, QtGui

    class RigSetsWindow(QtWidgets.QDialog):
        def __init__(self, parent=None):
            super(RigSetsWindow, self).__init__(parent)
            self.setObjectName(WINDOW_NAME)
            self.setWindowTitle("Rig Sets")
            self.setWindowFlags(self.windowFlags() | QtCore.Qt.Tool)
            self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
            self.resize(720, 420)
            self.rows, self.top = [], None

            lay = QtWidgets.QVBoxLayout(self)
            form = QtWidgets.QFormLayout()
            self.type_label = QtWidgets.QLabel()
            self.type_combo = QtWidgets.QComboBox()
            for label, value in TYPE_CHOICES:
                self.type_combo.addItem(label, value)
            self.type_combo.currentIndexChanged.connect(self.refresh)
            type_row = QtWidgets.QHBoxLayout()
            type_row.addWidget(self.type_label)
            type_row.addWidget(self.type_combo, 1)
            form.addRow("Asset type:", type_row)
            top_row = QtWidgets.QHBoxLayout()
            self.top_label = QtWidgets.QLabel()
            use_sel = QtWidgets.QPushButton("Use Selected")
            use_sel.setToolTip("Use the top group of what's selected as the rig")
            use_sel.clicked.connect(self._use_selected)
            top_row.addWidget(self.top_label, 1)
            top_row.addWidget(use_sel)
            form.addRow("Rig top group:", top_row)
            lay.addLayout(form)

            self.table = QtWidgets.QTableWidget(0, 4)
            self.table.setHorizontalHeaderLabels(["Set", "Status", "Suggested", ""])
            self.table.verticalHeader().setVisible(False)
            self.table.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
            self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            head = self.table.horizontalHeader()
            head.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
            head.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
            head.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
            head.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
            lay.addWidget(self.table, 1)

            self.verdict = QtWidgets.QLabel()
            self.verdict.setWordWrap(True)
            self.verdict.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            scroll = QtWidgets.QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(self.verdict)
            scroll.setMaximumHeight(130)
            lay.addWidget(scroll)

            buttons = QtWidgets.QHBoxLayout()
            self.build_btn = QtWidgets.QPushButton("Build Missing Sets")
            self.build_btn.setToolTip("Make each missing set from its suggestion (asks first)")
            self.build_btn.clicked.connect(self._build)
            again = QtWidgets.QPushButton("Check Again")
            again.clicked.connect(self.refresh)
            close = QtWidgets.QPushButton("Close")
            close.clicked.connect(self.close)
            buttons.addWidget(self.build_btn)
            buttons.addStretch(1)
            buttons.addWidget(again)
            buttons.addWidget(close)
            lay.addLayout(buttons)

            self._init_type()
            self.top = top_group([])
            self.refresh()

        # -- state --------------------------------------------------------

        def _init_type(self):
            folder = scene_asset_type()
            self.folder_type = folder
            self.type_combo.blockSignals(True)
            if folder:
                self.type_label.setText("%s  (from the scene's folder)" % folder)
                self.type_combo.setCurrentIndex(0 if is_character(folder) else 1)
                self.type_combo.setVisible(False)
            else:
                self.type_label.setText("")
                self.type_label.setVisible(False)
            self.type_combo.blockSignals(False)

        def asset_type(self):
            if self.folder_type:
                return self.folder_type
            return self.type_combo.currentData()

        def _use_selected(self):
            top = top_group()
            if not top:
                self._message("Select something inside one rig group (or the group itself).")
                return
            self.top = top
            self.refresh()

        def _message(self, text, title="Rig Sets"):
            QtWidgets.QMessageBox.information(self, title, text)

        # -- table --------------------------------------------------------

        def refresh(self, *_):
            if self.top and not cmds.objExists(self.top):
                self.top = None
            if not self.top:
                self.top = top_group([])
            self.top_label.setText(self.top.lstrip("|") if self.top else
                                   "<b>none found</b>: select the rig's top group and "
                                   "click Use Selected")
            self.rows = check(self.asset_type(), self.top)
            self.table.setRowCount(len(self.rows))
            for r, row in enumerate(self.rows):
                name = QtWidgets.QTableWidgetItem(row["name"] + ("" if row["required"] else "  (optional)"))
                status = QtWidgets.QTableWidgetItem(("OK: " if row["ok"] else "") + row["status"])
                status.setForeground(QtGui.QBrush(
                    QtGui.QColor(46, 139, 87) if row["ok"] else QtGui.QColor(192, 57, 43)))
                status.setToolTip(row["status"])
                sugg = QtWidgets.QTableWidgetItem(self._suggestion_text(row))
                sugg.setToolTip("\n".join(_short(n) for n in row["suggestion"][:40]))
                self.table.setItem(r, 0, name)
                self.table.setItem(r, 1, status)
                self.table.setItem(r, 2, sugg)
                self.table.setCellWidget(r, 3, self._row_buttons(row))
            self.table.resizeRowsToContents()
            self.build_btn.setEnabled(any(
                not row["set"] and not row["wrong"] and row["required"]
                and not row["status"].startswith("more") for row in self.rows))
            self._update_verdict()

        @staticmethod
        def _suggestion_text(row):
            s = row["suggestion"]
            if not s:
                return "-"
            if len(s) == 1:
                return _short(s[0])
            return "%d (%s, ...)" % (len(s), _short(s[0]))

        def _row_buttons(self, row):
            w = QtWidgets.QWidget()
            h = QtWidgets.QHBoxLayout(w)
            h.setContentsMargins(2, 0, 2, 0)
            sel = QtWidgets.QPushButton("Select Suggested")
            sel.setEnabled(bool(row["suggestion"]))
            sel.setToolTip("Select the suggestion so you can check or change it, "
                           "then Make / Add from Selection")
            sel.clicked.connect(lambda _=False, r=row: self._select(r["suggestion"]))
            h.addWidget(sel)
            if row["set"]:
                pick = QtWidgets.QPushButton("Select Set")
                pick.clicked.connect(lambda _=False, r=row: cmds.select(r["set"], replace=True, noExpand=True))
                add = QtWidgets.QPushButton("Add Selected")
                add.clicked.connect(lambda _=False, r=row: self._add(r))
                h.addWidget(pick)
                h.addWidget(add)
            elif row["wrong"]:
                ren = QtWidgets.QPushButton("Rename to %s" % row["name"])
                ren.clicked.connect(lambda _=False, r=row: self._rename(r))
                h.addWidget(ren)
            else:
                make = QtWidgets.QPushButton("Make from Selection")
                make.setToolTip("Make %s holding what's selected in Maya" % row["name"])
                make.clicked.connect(lambda _=False, r=row: self._make(r))
                h.addWidget(make)
            return w

        def _update_verdict(self):
            asset_type = self.asset_type()
            problems = [r for r in self.rows if not r["ok"]]
            leftover = wrong_kind_sets(asset_type)
            lines = []
            try:
                verdict = publish_check(asset_type, self.top) if self.top else \
                    "No rig top group."
                if verdict is None:
                    lines.append("<b style='color:#2e8b57'>Publish check: ready to publish "
                                 "as Rigging.</b>")
                else:
                    lines.append("<b style='color:#c0392b'>Publish check:</b> " +
                                 html.escape(verdict).replace("\n", "<br>"))
            except ImportError:
                if problems or not self.top:
                    lines.append("<b style='color:#c0392b'>Not ready:</b> fix the rows in red.")
                else:
                    lines.append("<b style='color:#2e8b57'>Sets look right.</b> (The pipe "
                                 "isn't installed, so Publish's own check didn't run.)")
            if leftover and not is_character(asset_type):
                lines.append(html.escape("Left over: %s (a non-character rig only needs %s)."
                             % (", ".join(leftover), set_names(asset_type)["body"])))
            self.verdict.setText("<br><br>".join(lines))

        # -- actions ------------------------------------------------------

        @staticmethod
        def _select(nodes):
            cmds.select(nodes, replace=True, noExpand=True)

        def _make(self, row):
            selection = cmds.ls(selection=True, long=True) or []
            if not selection:
                self._message("Select what goes in %s first (Select Suggested is a good "
                              "start)." % row["name"])
                return
            try:
                make_set(row["name"], selection)
            except RuntimeError as e:
                self._message(str(e))
            self.refresh()

        def _add(self, row):
            selection = cmds.ls(selection=True, long=True) or []
            if not selection:
                self._message("Select what to add to %s first." % row["name"])
                return
            add_to_set(row["set"], selection)
            self.refresh()

        def _rename(self, row):
            try:
                rename_set(row["wrong"], row["name"])
            except RuntimeError as e:
                self._message(str(e))
            self.refresh()

        def _build(self):
            todo = [r for r in self.rows if not r["set"] and not r["wrong"] and r["required"]
                    and not r["status"].startswith("more")]
            if not todo:
                return
            lines = []
            for r in todo:
                if r["suggestion"]:
                    lines.append("%s  <-  %s" % (r["name"], self._suggestion_text(r)))
                else:
                    lines.append("%s  <-  nothing found: made empty, fill it yourself" % r["name"])
            answer = QtWidgets.QMessageBox.question(
                self, "Build Missing Sets",
                "Make these sets?\n\n  " + "\n  ".join(lines) +
                "\n\nCheck them afterwards (Select Set) and add or remove anything the "
                "suggestion got wrong. Ctrl+Z undoes this.")
            if answer != QtWidgets.QMessageBox.Yes:
                return
            try:
                build_missing(self.rows)
            except RuntimeError as e:
                self._message(str(e))
            self.refresh()

    return RigSetsWindow
