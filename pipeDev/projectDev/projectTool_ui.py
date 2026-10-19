"""
Project Tool — UI
Pick one of your ShotGrid projects, see every asset and shot in it (yours
highlighted), and set any of them as the Maya project in one click. The
scratch folder structure is built from the H drive when it isn't there,
and the tool asks before bringing it up to date when the H drive changes.
Design: pipeDev/projectSwitcher_brief.md.

Dev launch (Script Editor, Python tab):

    import sys, importlib
    for p in (r"C:\\Users\\scout\\Documents\\maya\\scriptDev\\shelfDev\\mpAnim\\tools",
              r"C:\\Users\\scout\\Documents\\maya\\scriptDev\\pipeDev\\publishDev",
              r"C:\\Users\\scout\\Documents\\maya\\scriptDev\\pipeDev\\projectDev"):
        if p not in sys.path: sys.path.insert(0, p)
    import publishTool_api, projectTool_api, projectTool_ui
    for m in (publishTool_api, projectTool_api, projectTool_ui): importlib.reload(m)
    projectTool_ui.show()
"""

import os
import sys

import maya.cmds as cmds
from maya import OpenMayaUI as omui
from PySide6 import QtWidgets, QtCore, QtGui
import shiboken6

_DIR = os.path.dirname(__file__)
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

import publishTool_api as pub
import projectTool_api as api

MINE_COLOUR = "#7fbf7f"
DIM_COLOUR = "#888888"
ROLE_REL = QtCore.Qt.UserRole


def _maya_main_window():
    ptr = omui.MQtUtil.mainWindow()
    return shiboken6.wrapInstance(int(ptr), QtWidgets.QWidget)


class ProjectToolUI(QtWidgets.QDialog):

    def __init__(self, parent=None):
        super(ProjectToolUI, self).__init__(parent or _maya_main_window())
        self.setWindowTitle("Project Tool")
        self.setObjectName("projectToolUI")
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.Window)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.resize(560, 640)
        self._user, self._projects, self._films, self._mine = None, [], {}, set()
        self._diff = None

        self.who_lbl = QtWidgets.QLabel()
        self.project_combo = QtWidgets.QComboBox()
        self.project_combo.currentIndexChanged.connect(self._fill_film)
        refresh_btn = QtWidgets.QPushButton("Refresh")
        refresh_btn.setToolTip("Look at ShotGrid and the H drive again.")
        refresh_btn.clicked.connect(self.refresh)
        top = QtWidgets.QHBoxLayout()
        top.addWidget(QtWidgets.QLabel("Project:"))
        top.addWidget(self.project_combo, 1)
        top.addWidget(refresh_btn)

        # Shown when the H drive's folders have changed since scratch was made.
        self.update_lbl = QtWidgets.QLabel()
        self.update_lbl.setWordWrap(True)
        self.update_btn = QtWidgets.QPushButton("Update Scratch")
        self.update_btn.setToolTip("Add the new folders to your scratch drive. "
                                   "Nothing on scratch is removed or overwritten.")
        self.update_btn.clicked.connect(self._update_structure)
        self.update_box = QtWidgets.QFrame()
        self.update_box.setFrameShape(QtWidgets.QFrame.StyledPanel)
        box = QtWidgets.QHBoxLayout(self.update_box)
        box.addWidget(self.update_lbl, 1)
        box.addWidget(self.update_btn)
        self.update_box.hide()

        self.filter_edit = QtWidgets.QLineEdit()
        self.filter_edit.setPlaceholderText("Filter, e.g. EAP_010 or backpack")
        self.filter_edit.textChanged.connect(self._apply_filter)
        self.mine_chk = QtWidgets.QCheckBox("Only mine")
        self.mine_chk.setToolTip("Only the assets and shots you're assigned to in ShotGrid.")
        self.mine_chk.toggled.connect(self._apply_filter)
        filters = QtWidgets.QHBoxLayout()
        filters.addWidget(self.filter_edit, 1)
        filters.addWidget(self.mine_chk)

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels(["Asset / Shot", "On scratch", ""])
        self.tree.setRootIsDecorated(True)
        self.tree.itemDoubleClicked.connect(lambda *_: self._set_project())
        self.tree.itemSelectionChanged.connect(self._on_selection)

        self.set_btn = QtWidgets.QPushButton("Set Project")
        self.set_btn.setToolTip("Make it the Maya project. If it isn't on your scratch "
                                "drive yet, its folders are made first.")
        self.set_btn.clicked.connect(self._set_project)
        self.set_btn.setEnabled(False)

        self.status = QtWidgets.QLabel()
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.who_lbl)
        layout.addLayout(top)
        layout.addWidget(self.update_box)
        layout.addLayout(filters)
        layout.addWidget(self.tree, 1)
        layout.addWidget(self.set_btn)
        layout.addWidget(self.status)
        self.refresh()

    # -- helpers ----------------------------------------------------------

    def _roots(self):
        return (pub.resolve_root(pub.get_root(pub.H_DRIVE)),
                pub.resolve_root(pub.get_root(pub.SCRATCH)))

    def _message(self, text, ok=True):
        colour = "#7fbf7f" if ok else "#e0a060"
        self.status.setText('<span style="color:%s">%s</span>' % (colour, text.replace("\n", "<br>")))
        if text:
            print("Project Tool: %s" % text)

    def _film(self):
        return self.project_combo.currentData()

    # -- filling ----------------------------------------------------------

    def refresh(self):
        """Who you are and your projects from ShotGrid; films from the H drive."""
        h_root, scratch_root = self._roots()
        self.project_combo.blockSignals(True)
        self.project_combo.clear()
        self.tree.clear()
        try:
            pub.check_roots(h_root, scratch_root)
        except pub.PublishError as e:
            self.who_lbl.setText("")
            self.project_combo.blockSignals(False)
            self._message(str(e) + "\nSet them in the Publish or Build tool first.", ok=False)
            return
        try:
            self._user = api.shotgrid_user()
            if self._user:
                self._projects = api.user_projects(self._user)
        except Exception as e:
            self.project_combo.blockSignals(False)
            self._message("Couldn't reach ShotGrid: %s" % e, ok=False)
            return
        if not self._user:
            self.who_lbl.setText("")
            self.project_combo.blockSignals(False)
            self._message("ShotGrid doesn't know RMIT ID '%s'.\nAsk your teacher to add you "
                          "(and your RMIT ID) to ShotGrid." % api.rmit_id(), ok=False)
            return
        self.who_lbl.setText("You: %s (%s)" % (self._user["name"], api.rmit_id()))
        self._films = api.films_by_project(h_root)
        model = QtGui.QStandardItemModel(self.project_combo)
        for project in self._projects:
            film = self._films.get(project["id"])
            item = QtGui.QStandardItem(project["name"] if film else
                                       "%s  (not on the H drive yet)" % project["name"])
            item.setData(film, QtCore.Qt.UserRole)
            item.setData(project["id"], QtCore.Qt.UserRole + 1)
            item.setEnabled(bool(film))
            model.appendRow(item)
        self.project_combo.setModel(model)
        # Start on the project the open scene is in, else the first usable one.
        current = api.current_project()
        index = -1
        for i, project in enumerate(self._projects):
            film = self._films.get(project["id"])
            if film and (index < 0 or os.path.join(scratch_root, film).lower()
                         in current.lower()):
                index = i
        self.project_combo.setCurrentIndex(max(index, 0))
        self.project_combo.blockSignals(False)
        if not self._projects:
            self._message("You're not on any ShotGrid projects yet. Ask your teacher.", ok=False)
            return
        self._fill_film()

    def _fill_film(self, *args):
        h_root, scratch_root = self._roots()
        film = self._film()
        self.tree.clear()
        self.update_box.hide()
        if not film:
            return
        project_id = self.project_combo.currentData(QtCore.Qt.UserRole + 1)
        try:
            self._mine = api.assigned(self._user, project_id)
        except Exception:
            self._mine = set()
        current = api.current_project().lower()
        groups = {}
        for project in api.film_projects(h_root, film):
            top_label = "Assets" if project["kind"] == "asset" else "Shots"
            top = groups.get(top_label)
            if top is None:
                top = groups[top_label] = QtWidgets.QTreeWidgetItem([top_label])
                self.tree.addTopLevelItem(top)
            key = (top_label, project["group"])
            group = groups.get(key)
            if group is None:
                group = groups[key] = QtWidgets.QTreeWidgetItem([project["group"]])
                top.addChild(group)
            path = api.scratch_project(scratch_root, project["rel"])
            on_scratch = os.path.isfile(os.path.join(path, api.WORKSPACE))
            mine = api.is_assigned(project, self._mine)
            notes = []
            if mine:
                notes.append("yours")
            if os.path.normpath(path).lower() == current:
                notes.append("current project")
            item = QtWidgets.QTreeWidgetItem([project["name"], "yes" if on_scratch else "",
                                              ", ".join(notes)])
            item.setData(0, ROLE_REL, project["rel"])
            item.setData(0, ROLE_REL + 1, mine)
            if mine:
                font = item.font(0)
                font.setBold(True)
                item.setFont(0, font)
                item.setForeground(0, QtGui.QColor(MINE_COLOUR))
            if not on_scratch:
                item.setForeground(1, QtGui.QColor(DIM_COLOUR))
            group.addChild(item)
        for top in (groups.get("Assets"), groups.get("Shots")):
            if top:
                top.setExpanded(True)
        self.tree.resizeColumnToContents(0)
        self._check_structure()
        self._apply_filter()
        self._message("" if self.tree.topLevelItemCount() else
                      "%s has no assets or shots on the H drive yet." % film)

    def _check_structure(self):
        """If the film is on scratch and the H drive has changed since, say
        what's new and offer to update. Nothing changed = nothing shown."""
        h_root, scratch_root = self._roots()
        film = self._film()
        self._diff = api.structure_diff(h_root, scratch_root, film)
        if not self._diff["on_scratch"]:
            self.update_box.hide()
            return
        lines = []
        if self._diff["missing"] or self._diff["workspaces"]:
            what = api.describe_diff(self._diff) or "new folders"
            lines.append("The H drive's folders have changed: %s." % what)
        if self._diff["gone"]:
            lines.append("On your scratch but not on the H drive any more (kept, in case "
                         "they hold your work): %s" % ", ".join(r[-1] for r in self._diff["gone"]))
        self.update_lbl.setText("\n".join(lines))
        self.update_btn.setVisible(bool(self._diff["missing"] or self._diff["workspaces"]))
        self.update_box.setVisible(bool(lines))

    def _apply_filter(self, *args):
        text = self.filter_edit.text().strip().lower()
        only_mine = self.mine_chk.isChecked()
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            top_shown = False
            for g in range(top.childCount()):
                group = top.child(g)
                group_shown = False
                for c in range(group.childCount()):
                    item = group.child(c)
                    show = ((not text or text in item.text(0).lower()
                             or text in group.text(0).lower())
                            and (not only_mine or item.data(0, ROLE_REL + 1)))
                    item.setHidden(not show)
                    group_shown = group_shown or show
                group.setHidden(not group_shown)
                top_shown = top_shown or group_shown
            top.setHidden(not top_shown)

    def _on_selection(self):
        items = self.tree.selectedItems()
        self.set_btn.setEnabled(bool(items and items[0].data(0, ROLE_REL)))

    # -- actions ----------------------------------------------------------

    def _progress(self, title):
        dialog = QtWidgets.QProgressDialog(title, "", 0, 100, self)
        dialog.setCancelButton(None)        # folders only: nothing to cancel half way
        dialog.setWindowModality(QtCore.Qt.WindowModal)
        dialog.setMinimumDuration(500)

        def step(done, total):
            dialog.setMaximum(total)
            dialog.setValue(done)
            QtWidgets.QApplication.processEvents()
        return dialog, step

    def _update_structure(self):
        h_root, scratch_root = self._roots()
        film = self._film()
        dialog, step = self._progress("Updating %s on your scratch drive..." % film)
        try:
            folders, workspaces = api.update_structure(h_root, scratch_root, film,
                                                       diff=self._diff, progress=step)
        finally:
            dialog.close()
        self._fill_film()
        self._message("Scratch updated: %d new folder(s), %d new project(s)." % (folders, workspaces))

    def _set_project(self):
        items = self.tree.selectedItems()
        rel = items[0].data(0, ROLE_REL) if items else None
        if not rel:
            return
        if cmds.file(query=True, modified=True):
            answer = QtWidgets.QMessageBox.question(
                self, "Unsaved changes",
                "Your scene has unsaved changes. Set the project anyway?\n"
                "(The open scene stays open; only the Maya project changes.)")
            if answer != QtWidgets.QMessageBox.Yes:
                return
        h_root, scratch_root = self._roots()
        dialog, step = self._progress("Building %s on your scratch drive..." % rel[0])
        try:
            path, done = api.set_project(h_root, scratch_root, list(rel), progress=step)
        except pub.PublishError as e:
            self._message(str(e), ok=False)
            return
        finally:
            dialog.close()
        self._fill_film()
        self._message("%s: %s.\n%s" % (rel[-1], "; ".join(done), path))


_instance = None


def show():
    global _instance
    if _instance is not None:
        try:
            _instance.close()
        except RuntimeError:
            pass
    _instance = ProjectToolUI()
    _instance.show()
    return _instance
