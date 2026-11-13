"""
renderSub window: render the open shot in the background, review it, and
publish it to the H drive and ShotGrid. The work is in renderSub_api.py.

Shelf (mpLighting):
    import renderSub_ui; renderSub_ui.show()

The running render lives at module level (_JOB), so closing and reopening
the window picks it up again; the render itself never depends on the window.
"""

import os
import threading

import maya.cmds as cmds
import maya.utils

import publishTool_api as pub
import renderSub_api as api

WINDOW = "renderSubWindow"
KEEP_VAR = "renderSub_keepVersions"
OPEN_RV_VAR = "renderSub_openInRV"
HOW_VAR = "renderSub_how"          # sequence (default) or batch
DEFAULT_KEEP = 3
MODE_LABELS = (("shot", "Whole shot"),
               ("check", "Lighting check (start, end, middle + halfway each side)"),
               ("custom", "Custom range"), ("step", "Every Nth frame"), ("list", "Frame list"))
TICK_MS = 2000

_JOB = None         # the RenderJob running now, if any
_TIMER = None
_UI = None


def show():
    global _UI
    _UI = RenderSubUI()
    _UI.build()
    return _UI


class RenderSubUI(object):

    def __init__(self):
        self.w = {}
        self.ctx = None
        self.error = None

    # ------------------------------------------------------------------ layout
    def build(self):
        if cmds.window(WINDOW, exists=True):
            cmds.deleteUI(WINDOW)
        cmds.window(WINDOW, title="renderSub - Shot Render", widthHeight=(560, 860), sizeable=True)
        root = cmds.columnLayout(adj=True, parent=cmds.scrollLayout(childResizable=True))

        self._frame("Shot", root)
        for key, label in (("scene", "Scene"), ("shot", "Shot"), ("login", "Artist"),
                           ("next", "Next version"), ("local", "Renders to"), ("h", "Publishes to")):
            self.w[key] = self._field(label)
        cmds.button(label="Refresh", h=26, c=lambda *_: self.refresh())
        cmds.setParent(root)

        self._frame("Render", root)
        self._row("Camera")
        self.w["camera"] = cmds.optionMenu(changeCommand=lambda *_: self.update_counts())
        cmds.setParent("..")
        self._row("Frames")
        self.w["mode"] = cmds.optionMenu(changeCommand=lambda *_: self.update_modes())
        for _, label in MODE_LABELS:
            cmds.menuItem(label=label)
        cmds.setParent("..")
        cmds.rowLayout(numberOfColumns=6, columnWidth6=(100, 40, 70, 40, 70, 100))
        cmds.text(label="")
        cmds.text(label="Start")
        self.w["start"] = cmds.intField(width=64, changeCommand=lambda *_: self.update_counts())
        cmds.text(label="End")
        self.w["end"] = cmds.intField(width=64, changeCommand=lambda *_: self.update_counts())
        cmds.setParent("..")
        self._row("Every")
        self.w["step"] = cmds.intField(value=10, minValue=1, width=64,
                                       annotation="Render every Nth frame across the range "
                                                  "(the last frame is always included).",
                                       changeCommand=lambda *_: self.update_counts())
        cmds.setParent("..")
        self._row("Frame list")
        self.w["list"] = cmds.textField(placeholderText="e.g. 1001, 1050, 1100-1105",
                                        changeCommand=lambda *_: self.update_counts())
        cmds.setParent("..")
        self._row("Size")
        self.w["size"] = cmds.optionMenu(changeCommand=lambda *_: self.update_counts())
        for percent in api.RESOLUTIONS:
            cmds.menuItem(label="%d%%" % percent)
        cmds.setParent("..")
        self._row("Render on")
        self.w["where"] = cmds.optionMenu(
            annotation="Where the render runs. Time estimates come from earlier renders "
                       "of this shot in the same place.")
        cmds.menuItem(label="%s (%s)" % (api.WHERE_LABELS[api.LOCAL], api.where()["machine"]))
        cmds.menuItem(label="%s (coming soon)" % api.WHERE_LABELS[api.FARM], enable=False)
        cmds.setParent("..")
        self._row("Render")
        cmds.columnLayout(adj=True)
        self.w["how"] = cmds.radioCollection()
        saved_how = cmds.optionVar(q=HOW_VAR) if cmds.optionVar(exists=HOW_VAR) else api.SEQUENCE
        for how, tip in ((api.SEQUENCE, "Renders in this Maya, like Render > Render Sequence. "
                                        "Maya's own licence covers it (no watermark). Maya is busy "
                                        "until it's done; press Esc to stop."),
                         (api.BATCH, "Renders in the background with Render.exe, so you can keep "
                                     "working. Needs an Arnold batch licence, or the frames carry "
                                     "Arnold's watermark.")):
            cmds.radioButton(how, label=api.HOW_LABELS[how], annotation=tip,
                             select=(how == saved_how),
                             onCommand=lambda _, h=how: self._set_how(h))
        cmds.setParent("..")
        cmds.setParent("..")
        self.w["summary"] = cmds.text(label="", align="left", font="boldLabelFont")
        self.w["estimate"] = cmds.text(label="", align="left")
        cmds.separator(h=6, style="none")
        self.w["open_rv"] = cmds.checkBox(
            label="Open the frames in RV when the render finishes",
            value=cmds.optionVar(q=OPEN_RV_VAR) if cmds.optionVar(exists=OPEN_RV_VAR) else True,
            changeCommand=lambda v: cmds.optionVar(iv=(OPEN_RV_VAR, int(v))))
        self.w["render"] = cmds.button(label="Render", h=40, c=lambda *_: self.render())
        self.w["progress"] = cmds.progressBar(maxValue=1, height=14)
        self.w["status"] = cmds.text(label="", align="left")
        self.w["cancel"] = cmds.button(label="Cancel Render", h=26, enable=False,
                                       c=lambda *_: self.cancel())
        cmds.setParent(root)

        self._frame("Local Versions", root)
        self.w["versions"] = cmds.textScrollList(numberOfRows=7, allowMultiSelection=False)
        cmds.rowLayout(numberOfColumns=3, adjustableColumn=1)
        cmds.button(label="Play in RV", h=26, c=lambda *_: self.play())
        cmds.button(label="Open Folder", h=26, c=lambda *_: self.open_folder())
        cmds.button(label="Delete", h=26, c=lambda *_: self.delete())
        cmds.setParent("..")
        self._row("Keep newest")
        self.w["keep"] = cmds.intField(
            value=cmds.optionVar(q=KEEP_VAR) if cmds.optionVar(exists=KEEP_VAR) else DEFAULT_KEEP,
            minValue=0, width=64,
            annotation="Older local renders are deleted when you render again (0 = keep all). "
                       "Published ones are safe on the H drive.",
            changeCommand=lambda v: cmds.optionVar(iv=(KEEP_VAR, int(v))))
        cmds.setParent("..")
        cmds.setParent(root)

        self._frame("Publish", root)
        cmds.text(label="Notes (sent with this publish)", align="left")
        self.w["notes"] = cmds.scrollField(height=50, wordWrap=True)
        cmds.button(label="Publish Selected to H Drive + ShotGrid", h=34,
                    c=lambda *_: self.publish())
        cmds.setParent(root)

        cmds.showWindow(WINDOW)
        self.refresh()
        if _JOB and _JOB.poll() is None:
            self._set_running(True)
            _start_timer()

    def _frame(self, label, parent):
        cmds.frameLayout(label=label, collapsable=False, marginHeight=8, marginWidth=8, parent=parent)
        cmds.columnLayout(adj=True)

    def _row(self, label):
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=2, columnWidth2=(100, 380))
        cmds.text(label=label, align="left")

    def _field(self, label):
        self._row(label)
        field = cmds.textField(editable=False)
        cmds.setParent("..")
        return field

    # ------------------------------------------------------------------ state
    def refresh(self):
        scene = cmds.file(query=True, sceneName=True) or ""
        cmds.textField(self.w["scene"], e=True, text=os.path.basename(scene) or "<unsaved scene>")
        try:
            self.ctx, self.error = api.shot_of(scene, pub.get_root(pub.H_DRIVE)), None
        except api.PublishError as e:
            self.ctx, self.error = None, str(e)
        ctx = self.ctx or {}
        cmds.textField(self.w["shot"], e=True, text=ctx.get("shot", self.error or ""))
        cmds.textField(self.w["login"], e=True, text=ctx.get("login", ""))
        cmds.textField(self.w["next"], e=True,
                       text=os.path.basename(api.next_version(ctx)) if ctx else "")
        cmds.textField(self.w["local"], e=True, text=ctx.get("local", ""))
        cmds.textField(self.w["h"], e=True, text=ctx.get("h", ""))

        menu = self.w["camera"]
        current = cmds.optionMenu(menu, q=True, value=True) if cmds.optionMenu(
            menu, q=True, numberOfItems=True) else None
        for item in cmds.optionMenu(menu, q=True, itemListLong=True) or []:
            cmds.deleteUI(item)
        names = [c.split("|")[-1] for c in api.cameras()]
        for name in names or ["(no camera)"]:
            cmds.menuItem(label=name, parent=menu)
        if current in names:
            cmds.optionMenu(menu, e=True, value=current)

        start, end = api.shot_range()
        if not cmds.intField(self.w["start"], q=True, value=True):
            cmds.intField(self.w["start"], e=True, value=start)
            cmds.intField(self.w["end"], e=True, value=end)
        self.update_modes()
        self.refresh_versions()

    def mode(self):
        return MODE_LABELS[cmds.optionMenu(self.w["mode"], q=True, select=True) - 1][0]

    def update_modes(self):
        mode = self.mode()
        if mode in ("shot", "check"):
            start, end = api.shot_range()
            cmds.intField(self.w["start"], e=True, value=start)
            cmds.intField(self.w["end"], e=True, value=end)
        for key, on in (("start", mode in ("custom", "step")), ("end", mode in ("custom", "step")),
                        ("step", mode == "step"), ("list", mode == "list")):
            control = cmds.textField if key == "list" else cmds.intField
            control(self.w[key], e=True, enable=on)
        self.update_counts()

    def how(self):
        return cmds.radioCollection(self.w["how"], q=True, select=True) or api.SEQUENCE

    def _set_how(self, how):
        cmds.optionVar(sv=(HOW_VAR, how))
        self.update_counts()

    def percent(self):
        return api.RESOLUTIONS[cmds.optionMenu(self.w["size"], q=True, select=True) - 1]

    def frames(self):
        return api.frames_for(self.mode(),
                              cmds.intField(self.w["start"], q=True, value=True),
                              cmds.intField(self.w["end"], q=True, value=True),
                              cmds.intField(self.w["step"], q=True, value=True),
                              cmds.textField(self.w["list"], q=True, text=True))

    def update_counts(self):
        w, h = api.render_size(self.percent())
        estimate = ""
        try:
            frames = self.frames()
            text = "%d frame(s) at %d x %d" % (len(frames), w, h)
        except api.PublishError as e:
            frames, text = [], str(e)
        if frames and self.ctx:
            guess = api.predict(self.ctx["shot_project"], len(frames), (w, h), how=self.how())
            if guess:
                estimate = "About %s a frame on this computer, so about %s in all%s." % (
                    api.duration(guess["per_frame"]), api.duration(guess["total"]),
                    "" if guess["this_machine"] else " (from renders on other computers)")
            else:
                estimate = ("No time estimate yet: this shot hasn't been rendered here. "
                            "A quick test (every Nth frame at 25%) gives one.")
        cmds.text(self.w["summary"], e=True, label=text)
        cmds.text(self.w["estimate"], e=True, label=estimate)

    def camera(self):
        name = cmds.optionMenu(self.w["camera"], q=True, value=True)
        for c in api.cameras():
            if c.split("|")[-1] == name:
                return c
        return None

    def refresh_versions(self):
        cmds.textScrollList(self.w["versions"], e=True, removeAll=True)
        self._versions = api.local_versions(self.ctx) if self.ctx else []
        for v in self._versions:
            info = v["info"]
            label = "%s   %d frame(s)   %s" % (v["name"], len(info.get("frames", [])),
                                             info.get("status", "?"))
            if (info.get("timing") or {}).get("per_frame"):
                label += "   %s/frame" % api.duration(info["timing"]["per_frame"])
            if info.get("watermarked"):
                label += "   (watermarked)"
            if info.get("published"):
                label += "   [published]"
            cmds.textScrollList(self.w["versions"], e=True, append=label)

    def selected(self):
        index = cmds.textScrollList(self.w["versions"], q=True, selectIndexedItem=True)
        if not index:
            cmds.warning("renderSub: pick a version in the list first.")
            return None
        return self._versions[index[0] - 1]

    # ------------------------------------------------------------------ render
    def render(self):
        global _JOB
        if _JOB and _JOB.poll() is None:
            return _say("A render is already running. Wait for it, or cancel it.")
        self.refresh()
        if not self.ctx:
            return _say(self.error)
        camera = self.camera()
        if not camera:
            return _say("There's no camera to render through.")
        how = self.how()
        try:
            frames = self.frames()
            changed = api.ensure_arnold()
            if how == api.BATCH and (changed or cmds.file(query=True, modified=True)):
                # The background render reads the saved file, not this session.
                # (A sequence render renders the scene as it is open.)
                if cmds.confirmDialog(title="renderSub", message="Save the scene and render it?",
                                      button=["Save and Render", "Cancel"],
                                      defaultButton="Save and Render", cancelButton="Cancel",
                                      dismissString="Cancel") != "Save and Render":
                    return
                cmds.file(save=True)
            keep = cmds.intField(self.w["keep"], q=True, value=True)
            lost = api.prune(self.ctx, keep - 1) if keep > 0 else []
            if lost:
                cmds.warning("renderSub: deleted unpublished local render(s) %s (keeping the "
                             "newest %d)." % (", ".join(lost), keep))
            info = api.plan_render(self.ctx, cmds.file(query=True, sceneName=True),
                                   frames, camera, self.percent(), how=how)
            if how == api.SEQUENCE:
                return self._render_in_maya(info)
            _JOB = api.RenderJob(info)
        except (api.PublishError, OSError) as e:
            return _say(str(e))
        self._set_running(True)
        cmds.progressBar(self.w["progress"], e=True, maxValue=len(frames), progress=0)
        self.tick()
        _start_timer()
        self.refresh_versions()

    def _render_in_maya(self, info):
        """Sequence render: frame by frame in this Maya, with Maya's progress
        bar (Esc stops it between frames) and the window's own."""
        total = len(info["frames"])
        cmds.progressBar(self.w["progress"], e=True, maxValue=total, progress=0)
        cmds.progressWindow(title="renderSub", progress=0, maxValue=total, isInterruptable=True,
                            status="Rendering %s in Maya (Esc to stop)" % info["version"])

        def progress(done, total):
            status = "Rendering %s: %d of %d frame(s) done" % (info["version"], done, total)
            timing = api.timing(info)       # in Maya, each frame finishes before the next
            if timing and done < total:
                status += ", %s a frame, about %s left" % (
                    api.duration(timing["per_frame"]),
                    api.duration((total - done) * timing["per_frame"]))
            cmds.progressBar(self.w["progress"], e=True, progress=done)
            cmds.text(self.w["status"], e=True, label=status)
            cmds.progressWindow(e=True, progress=done, status=status + "  (Esc to stop)")
            cmds.refresh()
            return not cmds.progressWindow(q=True, isCancelled=True)

        try:
            info = api.render_in_maya(info, progress)
        except Exception as e:
            info = api.finish_render(info, 1)
            cmds.warning("renderSub: the render stopped: %s" % e)
        finally:
            cmds.progressWindow(endProgress=True)
        self.refresh()
        self._report(info)

    def _set_running(self, running):
        cmds.button(self.w["render"], e=True, enable=not running)
        cmds.button(self.w["cancel"], e=True, enable=running)

    def tick(self):
        """Every TICK_MS while a render runs: progress, then the finish."""
        global _JOB
        if not _JOB:
            return
        done, total = _JOB.frames_done(), len(_JOB.info["frames"])
        cmds.progressBar(self.w["progress"], e=True, maxValue=total, progress=done)
        if _JOB.poll() is None:
            status = "Rendering %s: %d of %d frame(s) done" % (_JOB.info["version"], done, total)
            timing = api.timing(_JOB.info, running=True)
            if timing:
                status += ", %s a frame, about %s left" % (
                    api.duration(timing["per_frame"]), api.duration(api.time_left(_JOB.info)))
            else:
                status += " (loading the scene, then the first frame)"
            cmds.text(self.w["status"], e=True, label=status)
            return
        _stop_timer()
        cmds.text(self.w["status"], e=True, label="Making the review movie...")
        cmds.refresh()
        info, _JOB = _JOB.finish(), None
        self._set_running(False)
        self.refresh()
        self._report(info)

    def _report(self, info):
        in_rv = info["status"] == "done" and cmds.checkBox(self.w["open_rv"], q=True, value=True)
        if in_rv:
            open_in_rv(info)
        if info["status"] == "done":
            cmds.text(self.w["status"], e=True, label="%s done" % info["version"])
            if info.get("movie_problem"):
                # No movie, no publish (api.publish refuses): just say why.
                return _say("%s rendered: %d frame(s), but there's no review movie, so it "
                            "can't be published:\n%s" % (info["version"], len(info["frames"]),
                                                        info["movie_problem"]))
            # Watch, then Publish or Cancel, as the Publish tool does.
            answer = ReviewDialog.ask(info, cmds.scrollField(self.w["notes"], q=True, text=True),
                                      in_rv)
            if answer is None:
                cmds.inViewMessage(amg="renderSub: <hl>%s</hl> kept on scratch, not published."
                                   % info["version"], pos="midCenter", fade=True)
                return
            cmds.scrollField(self.w["notes"], e=True, text=answer)
            self.publish_version(info["folder"], answer)
        elif info["status"] == "cancelled":
            cmds.text(self.w["status"], e=True, label="%s cancelled" % info["version"])
        else:
            cmds.text(self.w["status"], e=True, label="%s failed" % info["version"])
            where = ("Arnold's messages are in the Script Editor." if info.get("how") == api.SEQUENCE
                     else "End of the render log:\n%s" % api.log_tail(info))
            _say("%s didn't finish: %d frame(s) missing.\n\n%s"
                 % (info["version"], len(info["missing"]), where))

    def cancel(self):
        if _JOB and _JOB.poll() is None:
            _JOB.cancel()
        self.tick()

    # ------------------------------------------------------------------ versions
    def play(self):
        v = self.selected()
        if v:
            open_in_rv(dict(v["info"], folder=v["path"]))

    def open_folder(self):
        v = self.selected()
        path = v["path"] if v else (self.ctx or {}).get("local")
        if path and os.path.isdir(path):
            os.startfile(path)

    def delete(self):
        v = self.selected()
        if not v:
            return
        if _JOB and _JOB.poll() is None and _JOB.info["folder"] == v["path"]:
            return _say("That version is still rendering. Cancel it first.")
        extra = "" if v["info"].get("published") else "\nIt was never published."
        if cmds.confirmDialog(title="renderSub", message="Delete %s from scratch?%s" % (v["name"], extra),
                              button=["Delete", "Cancel"], cancelButton="Cancel",
                              dismissString="Cancel") == "Delete":
            api.delete_version(v["path"])
            self.refresh()

    # ------------------------------------------------------------------ publish
    def publish(self):
        """Publish Selected: the same watch-then-publish question as after a
        render, for a version kept earlier."""
        v = self.selected()
        if not (v and self.ctx):
            return
        info = dict(v["info"], folder=v["path"])
        answer = ReviewDialog.ask(info, cmds.scrollField(self.w["notes"], q=True, text=True),
                                  in_rv=False)
        if answer is not None:
            self.publish_version(v["path"], answer)

    def publish_version(self, folder, notes):
        if not self.ctx:
            return _say(self.error)
        name = os.path.basename(folder)
        cmds.waitCursor(state=True)
        try:
            result = api.publish(self.ctx, folder, notes)
        except Exception as e:
            return _say("The publish stopped:\n%s" % e)
        finally:
            cmds.waitCursor(state=False)
        self.refresh()
        lines = ["%s copied to the H drive:\n%s" % (name, result["dest"])]
        if result["sg_error"]:
            lines.append("The ShotGrid upload failed (publish again to retry it):\n"
                         + result["sg_error"])
        else:
            cmds.scrollField(self.w["notes"], e=True, text="")
            lines.append("ShotGrid Version made.")
        if (result["sg_version"] or {}).get("movie_problem"):
            lines.append("ShotGrid got no movie: " + result["sg_version"]["movie_problem"])
        _say("\n\n".join(lines + result["warnings"]))


def _say(message):
    cmds.confirmDialog(title="renderSub", message=message or "", button=["OK"])


def _maya_window():
    from maya import OpenMayaUI
    from PySide6 import QtWidgets
    from shiboken6 import wrapInstance
    pointer = OpenMayaUI.MQtUtil.mainWindow()
    return wrapInstance(int(pointer), QtWidgets.QWidget) if pointer else None


class ReviewDialog(object):
    """Watch before publishing (user, 2026-11-13: "a popup that asks the
    student to publish or cancel ... after RV loads. So they can get their
    eyes on the frames before sending it to ShotGrid. We have that feature
    as part of the publish tool"). Same shape as the Publish tool's
    ReviewDialog: both buttons work straight away, nothing waits on RV.
    Cancel keeps the render on scratch (Local Versions) to publish or delete
    later; a watermarked render says so here, so it's one question."""

    @staticmethod
    def ask(info, notes="", in_rv=True):
        """Returns the notes to publish with, or None for Cancel."""
        from PySide6 import QtWidgets
        dialog = QtWidgets.QDialog(_maya_window())
        dialog.setWindowTitle("Watch before publishing")
        dialog.setObjectName("renderSubReview")
        text = ("%s: %d frame(s) %s.\n\nPublish to the H drive and ShotGrid, or cancel to keep it "
                "on your scratch drive only (it stays in Local Versions)." % (
                    info["version"], len(info["frames"]),
                    "are opening in RV" if in_rv else "rendered"))
        if info.get("watermarked"):
            text += "\n\nThese frames carry Arnold's watermark. " + api.NO_LICENCE_HELP
        label = QtWidgets.QLabel(text)
        label.setWordWrap(True)
        label.setMinimumWidth(420)
        notes_box = QtWidgets.QPlainTextEdit(notes or "")
        notes_box.setPlaceholderText('Notes for ShotGrid, e.g. "first light pass, rim too hot"')
        notes_box.setFixedHeight(70)
        play = QtWidgets.QPushButton("Play in RV")
        play.clicked.connect(lambda: open_in_rv(info))
        publish = QtWidgets.QPushButton("Publish")
        publish.setDefault(True)
        publish.clicked.connect(dialog.accept)
        cancel = QtWidgets.QPushButton("Cancel")
        cancel.clicked.connect(dialog.reject)
        buttons = QtWidgets.QHBoxLayout()
        buttons.addWidget(play)
        buttons.addStretch(1)
        buttons.addWidget(publish)
        buttons.addWidget(cancel)
        layout = QtWidgets.QVBoxLayout(dialog)
        layout.addWidget(label)
        layout.addWidget(QtWidgets.QLabel("Notes (sent with this publish)"))
        layout.addWidget(notes_box)
        layout.addLayout(buttons)
        publish.setFocus()
        accepted = dialog.exec() == QtWidgets.QDialog.Accepted
        return notes_box.toPlainText() if accepted else None


def open_in_rv(info):
    """Show a version's EXR frames (the review movie if the frames are
    gone) in renderSub's RV window. A new RV takes a few seconds to start,
    so it's done off Maya's main thread; a failure comes back as a warning
    in the Script Editor and the status line."""
    media = api.rv_media(info)
    if not media and os.path.isfile(api.movie_path(info)):
        media = [api.movie_path(info)]
    if not media:
        return _say("%s has no frames or movie to play." % info.get("version", "This version"))

    def run():
        problem = api.push_to_rv(media)
        if problem:
            maya.utils.executeDeferred(cmds.warning, "renderSub: " + problem)
    threading.Thread(target=run, daemon=True).start()


def _start_timer():
    global _TIMER
    from PySide6 import QtCore
    if _TIMER is None:
        _TIMER = QtCore.QTimer()
        _TIMER.timeout.connect(_on_tick)
    _TIMER.start(TICK_MS)


def _stop_timer():
    if _TIMER:
        _TIMER.stop()


def _on_tick():
    global _JOB
    if _UI and cmds.window(WINDOW, exists=True):
        _UI.tick()
    elif _JOB and _JOB.poll() is not None:
        # Window closed during the render: finish it anyway.
        _stop_timer()
        _JOB, job = None, _JOB
        job.finish()
