"""
Scout window: every render in a project, and what can be done to it
(see scout_api.py). Runs on its own, outside Maya, so it stays open while
Maya closes and opens:

    mayapy scout_ui.py              (the mpLighting shelf's Scout button does this)

Pick the project (a film folder on scratch); the table lists its renders
from renderSub's ledger, newest first, refreshed every few seconds. Batch
renders on this machine can be paused, resumed, killed and restarted (the
frames still missing); any render with finished frames loads in RV, and a
finished one publishes to the H drive and ShotGrid.
"""

import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6 import QtCore, QtGui, QtWidgets

import scout_api as api

rs = api.rs
TITLE = "Scout"
TICK_MS = 3000
FILTERS = (("active", "Running and waiting"), ("today", "Today"), ("week", "Last 7 days"),
           ("all", "Everything"))
COLUMNS = ("Status", "Shot", "Version", "Artist", "Department", "How", "Frames", "Started",
           "Machine", "Render ID")
HOW_LABELS = {rs.BATCH: "background", rs.SEQUENCE: "in Maya", rs.FLOW: "cloud"}
STATUS_COLOURS = {rs.RENDERING: "#5fa8ff", rs.QUEUED: "#b0b0b0", rs.PAUSED: "#f0b040",
                  rs.DONE: "#62c370", rs.FAILED: "#ff6b6b", rs.CANCELLED: "#c08080",
                  rs.INTERRUPTED: "#e08a50"}
BUTTONS = ((api.PAUSE, "Pause", "Suspend the render's Render.exe; Resume carries on where it stopped."),
           (api.RESUME, "Resume", "Carry on with a paused render."),
           (api.KILL, "Kill", "Stop the render (or take it out of the queue). The frames that "
                              "finished stay and can be published."),
           (api.RESTART, "Restart", "Render the frames still missing from a stopped render, "
                                    "into the same version."),
           (api.RV, "Load in RV", "Show the finished frames in RV."),
           (api.PUBLISH, "Publish...", "Publish to the H drive and ShotGrid, with notes."))


def _started(row):
    text = (row.get("info") or {}).get("started") or row.get("started") or ""
    return text[5:16].replace("T", " ")


def _age_days(row):
    import datetime
    text = (row.get("info") or {}).get("started") or row.get("started")
    try:
        return (datetime.datetime.now() - datetime.datetime.fromisoformat(text)).total_seconds() / 86400
    except (TypeError, ValueError):
        return 999


class ScoutWindow(QtWidgets.QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle(TITLE)
        self.resize(1180, 640)
        self.settings = api.read_settings()
        self.rows = []
        self.workers = []           # publishes running: (process, result path, version)
        self._build()
        self.load_projects()
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(TICK_MS)

    # ------------------------------------------------------------------ layout
    def _build(self):
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)

        top = QtWidgets.QHBoxLayout()
        top.addWidget(QtWidgets.QLabel("Project"))
        self.project = QtWidgets.QComboBox()
        self.project.setMinimumWidth(260)
        self.project.currentIndexChanged.connect(lambda *_: self._project_changed())
        top.addWidget(self.project)
        add = QtWidgets.QPushButton("Add Project...")
        add.setToolTip("Add a film folder that isn't on this computer's own drives "
                       "(another scratch folder, a USB drive).")
        add.clicked.connect(self.add_project)
        top.addWidget(add)
        top.addSpacing(20)
        top.addWidget(QtWidgets.QLabel("Show"))
        self.filter = QtWidgets.QComboBox()
        for key, label in FILTERS:
            self.filter.addItem(label, key)
        self.filter.setCurrentIndex(max(0, [k for k, _ in FILTERS].index(
            self.settings.get("filter", "week"))))
        self.filter.currentIndexChanged.connect(lambda *_: self._filter_changed())
        top.addWidget(self.filter)
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Find: shot, artist, version or render ID")
        self.search.textChanged.connect(lambda *_: self.show_rows())
        top.addWidget(self.search, 1)
        layout.addLayout(top)

        self.table = QtWidgets.QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        # Several can be picked, to delete them together; the other buttons
        # act on one.
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self.show_selected)
        self.table.doubleClicked.connect(lambda *_: self.do(api.RV))
        layout.addWidget(self.table, 3)

        buttons = QtWidgets.QHBoxLayout()
        self.buttons = {}
        for action, label, tip in BUTTONS:
            b = QtWidgets.QPushButton(label)
            b.setToolTip(tip)
            b.clicked.connect(lambda _=False, a=action: self.do(a))
            buttons.addWidget(b)
            self.buttons[action] = b
        buttons.addStretch(1)
        for label, call in (("Open Folder", self.open_folder), ("Copy Render ID", self.copy_id),
                            ("Show Log", self.show_log)):
            b = QtWidgets.QPushButton(label)
            b.clicked.connect(call)
            buttons.addWidget(b)
            self.buttons[label] = b
        buttons.addSpacing(16)
        for label, call, tip in (
                ("Delete...", self.delete_selected,
                 "Delete the picked renders from scratch and take them off the list "
                 "(Delete key). Anything published stays on the H drive and ShotGrid."),
                ("Clear Deleted", self.clear_deleted,
                 "Take renders already deleted from scratch off the list.")):
            b = QtWidgets.QPushButton(label)
            b.setToolTip(tip)
            b.clicked.connect(call)
            buttons.addWidget(b)
            self.buttons[label] = b
        QtGui.QShortcut(QtGui.QKeySequence.Delete, self.table, self.delete_selected)
        layout.addLayout(buttons)

        self.details = QtWidgets.QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setMaximumBlockCount(400)
        layout.addWidget(self.details, 1)
        self.status = self.statusBar()

    # ------------------------------------------------------------------ projects
    def load_projects(self):
        extra = self.settings.get("projects", [])
        found = api.find_projects(extra)
        current = self.settings.get("project")
        self.project.blockSignals(True)
        self.project.clear()
        for path in found:
            self.project.addItem(os.path.basename(path), path)
            self.project.setItemData(self.project.count() - 1, path, QtCore.Qt.ToolTipRole)
        index = next((n for n, p in enumerate(found) if current and rs._same(p, current)), 0)
        self.project.setCurrentIndex(index)
        self.project.blockSignals(False)
        self.refresh()

    def add_project(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Pick a film folder (e.g. D:\\NWF_SHF)")
        if not path:
            return
        if not os.path.isdir(api.ledger_of(path)):
            return QtWidgets.QMessageBox.information(
                self, TITLE, "%s has no renders yet (no maya\\data\\renderSub\\renders folder). "
                "Pick the film folder itself, e.g. D:\\NWF_SHF." % path)
        projects = self.settings.setdefault("projects", [])
        if not any(rs._same(p, path) for p in projects):
            projects.append(os.path.normpath(path))
        self.settings["project"] = os.path.normpath(path)
        self._save_settings()
        self.load_projects()

    def _project_changed(self):
        self.settings["project"] = self.project.currentData()
        self._save_settings()
        self.refresh()

    def _filter_changed(self):
        self.settings["filter"] = self.filter.currentData()
        self._save_settings()
        self.show_rows()

    def _save_settings(self):
        try:
            api.write_settings(self.settings)
        except OSError:
            pass

    # ------------------------------------------------------------------ the table
    def tick(self):
        self.refresh()
        self._check_workers()

    def refresh(self):
        project = self.project.currentData()
        self.rows = api.project_renders(project) if project else []
        self._settle_stale()
        self.show_rows()
        states = api.services()
        if states:
            parts = []
            for s in states:
                q = api.read_queue(s["maya"])
                parts.append("Maya %s: %s, %d waiting" % (
                    s["maya"], "rendering" if q.get("running") else "idle", len(q.get("waiting", []))))
            self.status.showMessage("Render service running (%s)" % "; ".join(parts))
        else:
            self.status.showMessage("Render service not running: it starts when a render is sent "
                                    "to it (renderSub's background render, or Restart here).")

    def _settle_stale(self):
        """Renders nothing is running any more get their real status, off
        the window's thread (a finished one gets its movie made)."""
        busy = self.__dict__.setdefault("_settling", set())
        for row in self.rows:
            if api.stale(row) and row["folder"] not in busy:
                busy.add(row["folder"])
                row["status"], row["actions"] = "checking", []

                def run(r=row):
                    try:
                        api.settle_row(r)
                    except Exception:
                        pass
                    finally:
                        busy.discard(r["folder"])
                threading.Thread(target=run, daemon=True).start()
            elif row["folder"] in busy:
                row["status"], row["actions"] = "checking", []

    def _visible(self, row):
        key = self.filter.currentData()
        if key == "active" and row["status"] not in rs.ACTIVE:
            return False
        if key == "today" and _age_days(row) > 1:
            return False
        if key == "week" and _age_days(row) > 7:
            return False
        text = self.search.text().strip().lower()
        if text:
            hay = " ".join(str(row.get(k) or "") for k in ("shot", "login", "version", "render_id"))
            return text in hay.lower()
        return True

    def show_rows(self):
        keep_ids = set(r.get("render_id") for r in self.selected_rows())
        self.shown = [r for r in self.rows if self._visible(r)]
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.shown))
        for n, row in enumerate(self.shown):
            info = row.get("info") or {}
            values = (api.describe(row), row.get("shot"), row.get("version"), row.get("login"),
                      rs.department_label(row.get("department")) if row.get("department") else "",
                      HOW_LABELS.get(row.get("how"), row.get("how") or ""),
                      "%d / %d" % (row["frames_done"], row["total"]), _started(row),
                      (row.get("where") or {}).get("machine", ""), row.get("render_id"))
            for c, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(str(value or ""))
                if c == 0:
                    colour = STATUS_COLOURS.get(row["status"])
                    if colour:
                        item.setForeground(QtGui.QBrush(QtGui.QColor(colour)))
                    if info.get("watermarked"):
                        item.setToolTip("Rendered with Arnold's watermark (no batch licence)")
                self.table.setItem(n, c, item)
        selection = QtCore.QItemSelection()
        for n, row in enumerate(self.shown):
            if row.get("render_id") in keep_ids:
                selection.select(self.table.model().index(n, 0),
                                 self.table.model().index(n, len(COLUMNS) - 1))
        self.table.selectionModel().select(selection, QtCore.QItemSelectionModel.ClearAndSelect)
        self.table.blockSignals(False)
        self.table.resizeColumnsToContents()
        self.show_selected()

    def selected_rows(self):
        model = self.table.selectionModel()
        shown = getattr(self, "shown", [])
        picked = sorted(i.row() for i in model.selectedRows()) if model else []
        return [shown[n] for n in picked if n < len(shown)]

    def selected_row(self):
        """The picked render, when exactly one is picked."""
        rows = self.selected_rows()
        return rows[0] if len(rows) == 1 else None

    def show_selected(self):
        row = self.selected_row()
        allowed = row["actions"] if row else []
        for action, _, _ in BUTTONS:
            self.buttons[action].setEnabled(action in allowed)
        for label in ("Open Folder", "Copy Render ID", "Show Log"):
            self.buttons[label].setEnabled(bool(row))
        self.buttons["Delete..."].setEnabled(bool(self.selected_rows()))
        self.buttons["Clear Deleted"].setEnabled(
            any(not r["exists"] for r in getattr(self, "rows", [])))
        if not row:
            self.details.setPlainText("")
            return
        if row.get("render_id") == getattr(self, "_log_id", None):
            return                  # Show Log's text stays until another render is picked
        self._log_id = None
        lines = rs.describe_render(dict(row, frames_found=row["frames_done"]))
        if isinstance(lines, (list, tuple)):
            lines = "\n".join(lines)
        info = row.get("info") or {}
        if info.get("how") == rs.BATCH and not api.controllable(info):
            lines += "\nRendered on %s: control it from Scout on that machine." % (
                (info.get("where") or {}).get("machine"))
        elif info.get("how") in (rs.FLOW, rs.SEQUENCE):
            lines += "\n%s render: Scout shows it; it's run from renderSub." % HOW_LABELS[info["how"]]
        text = self.details.toPlainText()
        if text != lines:
            self.details.setPlainText(lines)

    # ------------------------------------------------------------------ actions
    def do(self, action):
        row = self.selected_row()
        if not row or action not in row["actions"]:
            return
        info = row["info"]
        if action == api.RV:
            return self._rv(info)
        if action == api.PUBLISH:
            return self._publish(info)
        if action == api.KILL:
            done = rs.frames_done(info, running=info.get("status") == rs.RENDERING)
            if QtWidgets.QMessageBox.question(
                    self, TITLE, "Kill %s %s?\n\n%d frame(s) have finished; they stay, and can "
                    "be published or restarted from." % (info["shot"], info["version"], done)) \
                    != QtWidgets.QMessageBox.Yes:
                return
        if action == api.RESTART:
            left = [f for f in info["frames"] if f not in rs.finished_frames(info)]
            if QtWidgets.QMessageBox.question(
                    self, TITLE, "Restart %s %s?\n\nRenders the %d frame(s) still missing (%s) "
                    "into the same version, in the background." % (
                        info["shot"], info["version"], len(left), rs.seq_string(left))) \
                    != QtWidgets.QMessageBox.Yes:
                return
        try:
            api.send(info.get("maya"), action, info["folder"])
        except api.ScoutError as e:
            return QtWidgets.QMessageBox.warning(self, TITLE, str(e))
        self.status.showMessage("Sent %s to the render service for %s." % (action, info["version"]), 4000)
        QtCore.QTimer.singleShot(1500, self.refresh)

    def _rv(self, info):
        self.status.showMessage("Loading %s in RV..." % info["version"], 6000)

        def run():
            problem = api.load_in_rv(info)
            if problem:
                QtCore.QMetaObject.invokeMethod(self, "_rv_problem", QtCore.Qt.QueuedConnection,
                                                QtCore.Q_ARG(str, problem))
        threading.Thread(target=run, daemon=True).start()

    @QtCore.Slot(str)
    def _rv_problem(self, problem):
        QtWidgets.QMessageBox.warning(self, TITLE, problem)

    def _publish(self, info):
        done = rs.finished_frames(info)
        part = "" if len(done) == len(info["frames"]) else \
            "\n(%s: the %d of %d frame(s) that finished)" % (info["status"], len(done), len(info["frames"]))
        notes, ok = QtWidgets.QInputDialog.getMultiLineText(
            self, TITLE, "Publish %s %s to the H drive and ShotGrid%s\n\nNotes:" % (
                info["shot"], info["version"], part))
        if not ok:
            return
        try:
            proc, result = api.start_worker(info.get("maya"), api.PUBLISH, info["folder"], notes)
        except api.ScoutError as e:
            return QtWidgets.QMessageBox.warning(self, TITLE, str(e))
        self.workers.append((proc, result, info["version"]))
        self.status.showMessage("Publishing %s (loading Maya in the background)..." % info["version"])

    def _check_workers(self):
        for work in list(self.workers):
            proc, result, version = work
            if proc.poll() is None:
                continue
            self.workers.remove(work)
            out = api.read_result(result) or {
                "ok": False, "message": "The publish of %s stopped without saying why "
                                        "(exit %s)." % (version, proc.returncode)}
            try:
                os.remove(result)
            except OSError:
                pass
            box = QtWidgets.QMessageBox.information if out.get("ok") else QtWidgets.QMessageBox.warning
            box(self, TITLE, out.get("message") or "")
            self.refresh()

    def open_folder(self):
        row = self.selected_row()
        if row and os.path.isdir(row.get("folder") or ""):
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(row["folder"]))

    def copy_id(self):
        row = self.selected_row()
        if row and row.get("render_id"):
            QtWidgets.QApplication.clipboard().setText(row["render_id"])
            self.status.showMessage("Copied %s" % row["render_id"], 3000)

    def delete_selected(self, ask=True):
        """Delete the picked renders from scratch and the list (user,
        2026-11-20: "remove or clear unwanted renders"). Running ones are
        left, with why."""
        rows = self.selected_rows()
        if not rows:
            return
        project = self.project.currentData()
        can = [r for r in rows if not api.why_not_delete(r)]
        refused = [api.why_not_delete(r) for r in rows if api.why_not_delete(r)]
        if not can:
            return QtWidgets.QMessageBox.warning(self, TITLE, "\n".join(refused))
        names = ["%s %s" % (r.get("shot"), r.get("version")) for r in can]
        lost = [r for r in can if r["exists"] and r["frames_done"] and not r.get("published")
                and not (r.get("info") or {}).get("published")]
        text = "Delete %d render(s) from scratch?\n\n%s" % (
            len(can), "\n".join(names[:12]) + ("\n...and %d more" % (len(names) - 12)
                                               if len(names) > 12 else ""))
        if lost:
            text += "\n\n%d of them were never published: their frames will be gone." % len(lost)
        text += "\n\nAnything published stays on the H drive and ShotGrid."
        if refused:
            text += "\n\nLeft alone:\n" + "\n".join(refused)
        if ask and QtWidgets.QMessageBox.question(self, TITLE, text) != QtWidgets.QMessageBox.Yes:
            return
        problems = []
        for r in can:
            try:
                api.delete_render(project, r)
            except api.ScoutError as e:
                problems.append(str(e))
        self.table.clearSelection()
        self.refresh()
        self.status.showMessage("Deleted %d render(s)." % (len(can) - len(problems)), 5000)
        if problems:
            QtWidgets.QMessageBox.warning(self, TITLE, "\n\n".join(problems))

    def clear_deleted(self, ask=True):
        """Take renders already gone from scratch off the list."""
        gone = [r for r in self.rows if not r["exists"]]
        if not gone:
            return
        if ask and QtWidgets.QMessageBox.question(
                self, TITLE, "Take %d render(s) already deleted from scratch off the list?"
                % len(gone)) != QtWidgets.QMessageBox.Yes:
            return
        project = self.project.currentData()
        for r in gone:
            api.forget(project, r)
        self.refresh()

    def show_log(self):
        row = self.selected_row()
        if not row or not row["exists"]:
            return
        tail = rs.log_tail(row["info"], lines=40)
        self._log_id = row.get("render_id")
        self.details.setPlainText(tail or "No render log (in-Maya and cloud renders don't write one).")


def main():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    app.setApplicationName(TITLE)
    window = ScoutWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
