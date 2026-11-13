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
DEFAULT_KEEP = 3
MODE_LABELS = (("shot", "Whole shot"), ("custom", "Custom range"),
               ("step", "Every Nth frame"), ("list", "Frame list"))
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
        if mode == "shot":
            start, end = api.shot_range()
            cmds.intField(self.w["start"], e=True, value=start)
            cmds.intField(self.w["end"], e=True, value=end)
        for key, on in (("start", mode in ("custom", "step")), ("end", mode in ("custom", "step")),
                        ("step", mode == "step"), ("list", mode == "list")):
            control = cmds.textField if key == "list" else cmds.intField
            control(self.w[key], e=True, enable=on)
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
            guess = api.predict(self.ctx["shot_project"], len(frames), (w, h))
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
        try:
            frames = self.frames()
            changed = api.ensure_arnold()
            if changed or cmds.file(query=True, modified=True):
                # The background render reads the saved file, not this session.
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
                                   frames, camera, self.percent())
            _JOB = api.RenderJob(info)
        except (api.PublishError, OSError) as e:
            return _say(str(e))
        self._set_running(True)
        cmds.progressBar(self.w["progress"], e=True, maxValue=len(frames), progress=0)
        self.tick()
        _start_timer()
        self.refresh_versions()

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
        if info["status"] == "done" and cmds.checkBox(self.w["open_rv"], q=True, value=True):
            open_in_rv(info)
        if info["status"] == "done":
            text = "%s rendered: %d frame(s)." % (info["version"], len(info["frames"]))
            if info.get("watermarked"):
                text += "\n\n" + api.NO_LICENCE_HELP
            if info.get("movie_problem"):
                text += "\n\nNo review movie: " + info["movie_problem"]
            cmds.text(self.w["status"], e=True, label="%s done" % info["version"])
            if info.get("watermarked") or info.get("movie_problem"):
                _say(text)
            else:
                cmds.inViewMessage(amg="renderSub: <hl>%s</hl> rendered." % info["version"],
                                   pos="midCenter", fade=True)
        elif info["status"] == "cancelled":
            cmds.text(self.w["status"], e=True, label="%s cancelled" % info["version"])
        else:
            cmds.text(self.w["status"], e=True, label="%s failed" % info["version"])
            _say("%s didn't finish: %d frame(s) missing.\n\nEnd of the render log:\n%s"
                 % (info["version"], len(info["missing"]), api.log_tail(info)))

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
        v = self.selected()
        if not (v and self.ctx):
            return
        if v["info"].get("watermarked") and cmds.confirmDialog(
                title="renderSub", message="%s has Arnold's watermark.\n\n%s\n\nPublish it anyway?"
                % (v["name"], api.NO_LICENCE_HELP), button=["Publish", "Cancel"],
                cancelButton="Cancel", dismissString="Cancel") != "Publish":
            return
        cmds.waitCursor(state=True)
        try:
            result = api.publish(self.ctx, v["path"],
                                 cmds.scrollField(self.w["notes"], q=True, text=True))
        except Exception as e:
            return _say("The publish stopped:\n%s" % e)
        finally:
            cmds.waitCursor(state=False)
        self.refresh()
        lines = ["%s copied to the H drive:\n%s" % (v["name"], result["dest"])]
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
