"""
renderSub window: render the open shot in the background, review it, and
publish it to the H drive and ShotGrid. The work is in renderSub_api.py.

Shelf (mpLighting):
    import renderSub_ui; renderSub_ui.show()

The renders running and queued live at module level (_QUEUE, any shot), so
closing and reopening the window, or opening another shot, picks them up
again; the renders never depend on the window. Batch renders stop when Maya
closes, and the next Maya says so at startup (user, 2026-11-19).
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

# Every mpLighting shelf click reloads this module (shelf_config
# RELOAD_ORDER), so the queue, its timer and the quit job carry over a
# reload. Starting them afresh forgot every render running or waiting:
# nothing finished them or started the next (2026-11-20, a night's queue).
_OLD_QUEUE = globals().get("_QUEUE")
_QUEUE = api.RenderQueue()     # every render running or waiting, any shot
if _OLD_QUEUE is not None:
    _QUEUE.jobs, _QUEUE.waiting = _OLD_QUEUE.jobs, _OLD_QUEUE.waiting
del _OLD_QUEUE
_TIMER = globals().get("_TIMER")
_UI = None
_QUIT_JOB = globals().get("_QUIT_JOB")


def _flow():
    """renderSub_flow (Flow Render, the cloud), or None if it won't load."""
    try:
        import renderSub_flow
        return renderSub_flow
    except Exception:
        return None


def _flow_available():
    flow = _flow()
    if not flow:
        return False, "renderSub's Flow Render part (renderSub_flow.py) isn't installed."
    try:
        return flow.available()
    except Exception as e:
        return False, "Flow Render didn't load: %s" % e


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
        self._row("Department")
        self.w["department"] = cmds.optionMenu(
            annotation="The department this render comes from. It starts as the scene's "
                       "scenes\\<department>\\ folder; it goes in the render's notes and on "
                       "the ShotGrid Version.")
        for label, _ in api.DEPARTMENTS:
            cmds.menuItem(label=label)
        cmds.setParent("..")
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
                       "of this shot in the same place.",
            changeCommand=lambda *_: self._set_where())
        cmds.menuItem(label="%s (%s)" % (api.WHERE_LABELS[api.LOCAL], api.where()["machine"]))
        flow_ok, flow_why = _flow_available()
        cmds.menuItem(label=api.WHERE_LABELS[api.CLOUD] + ("" if flow_ok else " (not in this Maya)"),
                      enable=flow_ok,
                      annotation=("Autodesk's cloud rendering (tech preview, free hours each "
                                  "month on your Autodesk account). Maya stays free while it "
                                  "uploads and renders; the frames come back here."
                                  if flow_ok else flow_why))
        cmds.menuItem(label="%s (coming soon)" % api.WHERE_LABELS[api.FARM], enable=False)
        self._where_kinds = [api.LOCAL, api.CLOUD, api.FARM]
        cmds.setParent("..")
        self._row("Render")
        self.w["how_column"] = cmds.columnLayout(adj=True)
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
        self.w["render"] = cmds.button(
            label="Render", h=40, c=lambda *_: self.render(),
            annotation="Saves the scene as its next version, copies it into the render's "
                       "folder and renders the copy. Another render can be started while "
                       "this one runs, from any shot: batch renders wait their turn.")
        self.w["status"] = cmds.text(label="", align="left")
        cmds.setParent(root)

        self._frame("Render Queue (every shot)", root)
        self.w["queue"] = cmds.textScrollList(
            numberOfRows=4, allowMultiSelection=False,
            annotation="Renders running or waiting in this Maya. Batch renders run one at a "
                       "time and stop if Maya closes; cloud renders carry on in the cloud "
                       "once they've uploaded.")
        self.w["progress"] = cmds.progressBar(maxValue=1, height=14)
        self.w["cancel"] = cmds.button(label="Cancel Selected", h=26, enable=False,
                                       c=lambda *_: self.cancel())
        cmds.setParent(root)

        self._frame("Local Versions", root)
        self.w["versions"] = cmds.textScrollList(numberOfRows=7, allowMultiSelection=False)
        cmds.rowLayout(numberOfColumns=3, adjustableColumn=1)
        cmds.button(label="Play in RV", h=26, c=lambda *_: self.play())
        cmds.button(label="Open Folder", h=26, c=lambda *_: self.open_folder())
        cmds.button(label="Delete", h=26, c=lambda *_: self.delete())
        cmds.setParent("..")
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=1)
        cmds.button(label="Copy Render ID", h=26, c=lambda *_: self.copy_id(),
                    annotation="Every render has its own ID (in render.json, on the ShotGrid "
                               "Version and in each frame's EXR header). Copy the selected one's.")
        cmds.button(label="Find Render...", h=26, c=lambda *_: self.find_render(),
                    annotation="Find any render by its ID: on this computer, or published "
                               "on the H drive.")
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
        self._reviewing = False
        self._to_review = []
        self.refresh()
        self._pick_up_cloud_renders()
        self.show_queue()
        if _QUEUE.busy():
            _start_timer()

    def _pick_up_cloud_renders(self):
        """Cloud renders sent before Maya was closed carry on in the cloud:
        watch them again (any shot) so their frames come back to their
        versions and they finish here."""
        flow = _flow()
        if not flow:
            return
        folders = list(api.read_jobs()["cloud"])
        if self.ctx:
            folders += [v["path"] for v in api.local_versions(self.ctx)]
        watched = _QUEUE.folders()
        for folder in folders:
            info = api.read_info(folder)
            if api.in_cloud(info) and not any(api._same(folder, w) for w in watched):
                _QUEUE.add(flow.FlowJob(dict(info, folder=folder)))
                watched.append(folder)
        _remember_cloud()

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
        if scene != getattr(self, "_department_scene", None):
            # A new scene starts from its folder's department; a refresh of
            # the same scene keeps the artist's choice.
            self._department_scene = scene
            cmds.optionMenu(self.w["department"], e=True,
                            value=api.department_label(api.department_of(scene)))

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

    def where(self):
        return self._where_kinds[cmds.optionMenu(self.w["where"], q=True, select=True) - 1]

    def _set_where(self):
        # In Maya / in the background only matter on this computer.
        cmds.columnLayout(self.w["how_column"], e=True, enable=self.where() == api.LOCAL)
        self._quota = None
        self.update_counts()

    def how(self):
        if self.where() == api.CLOUD:
            return api.FLOW
        return cmds.radioCollection(self.w["how"], q=True, select=True) or api.SEQUENCE

    def _set_how(self, how):
        cmds.optionVar(sv=(HOW_VAR, how))
        self.update_counts()

    def percent(self):
        return api.RESOLUTIONS[cmds.optionMenu(self.w["size"], q=True, select=True) - 1]

    def frames(self):
        frames = api.frames_for(self.mode(),
                                cmds.intField(self.w["start"], q=True, value=True),
                                cmds.intField(self.w["end"], q=True, value=True),
                                cmds.intField(self.w["step"], q=True, value=True),
                                cmds.textField(self.w["list"], q=True, text=True))
        if self.where() == api.CLOUD:
            flow = _flow()
            if self.mode() == "list" and not flow.is_range(frames):
                raise api.PublishError("Flow Render renders a range every N frames, not a "
                                       "frame list: use Every Nth frame or Custom range.")
            frames = flow.cloud_frames(frames)
        return frames

    def update_counts(self):
        w, h = api.render_size(self.percent())
        estimate = ""
        cloud = self.where() == api.CLOUD
        try:
            frames = self.frames()
            text = "%d frame(s) at %d x %d" % (len(frames), w, h)
            if cloud:
                text += " on Flow Render: %s" % api.seq_string(frames)
        except api.PublishError as e:
            frames, text = [], str(e)
        if cloud:
            if getattr(self, "_quota", None) is None:
                self._quota = _flow().quota_text() if _flow() else ""
            guess = api.predict(self.ctx["shot_project"], len(frames), (w, h), kind=api.CLOUD) \
                if frames and self.ctx else None
            estimate = ("About %s from submit to frames back, from earlier cloud renders of this "
                        "shot. " % api.duration(guess["total"]) if guess else
                        "No estimate yet for the cloud. ")
            estimate += self._quota or "Hours left: shown once you're signed in to Autodesk."
        elif frames and self.ctx:
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

    def department(self):
        index = cmds.optionMenu(self.w["department"], q=True, select=True)
        return api.DEPARTMENTS[index - 1][1]

    def camera(self):
        name = cmds.optionMenu(self.w["camera"], q=True, value=True)
        for c in api.cameras():
            if c.split("|")[-1] == name:
                return c
        return None

    def refresh_versions(self):
        cmds.textScrollList(self.w["versions"], e=True, removeAll=True)
        self._versions = api.local_versions(self.ctx) if self.ctx else []
        running = _QUEUE.folders()
        for v in self._versions:
            # A render nothing is running any more (Maya crashed, the power
            # went) shows as interrupted, ready to publish what finished.
            info = v["info"] = api.settle(dict(v["info"], folder=v["path"]), running) \
                if v["info"].get("status") in api.ACTIVE else v["info"]
            watched = any(api._same(r, v["path"]) for r in running)
            if info.get("how") == api.FLOW and not watched and _flow():
                # Cloud frames that came back while renderSub wasn't watching
                # (Maya closed, Cancel, or downloaded from the Job Monitor).
                info = v["info"] = _flow().catch_up(dict(info, folder=v["path"]))
            total = len(info.get("frames", []))
            if info.get("status") in api.STOPPED and "frames" in info:
                count = "%d of %d frame(s)" % (len(api.finished_frames(dict(info, folder=v["path"]))), total)
            else:
                count = "%d frame(s)" % total
            status = info.get("status", "?")
            if status == api.QUEUED and _QUEUE.place(v["path"]):
                status = "queued (%s)" % _ordinal(_QUEUE.place(v["path"]))
            label = "%s   %s   %s" % (v["name"], count, status)
            if info.get("department"):
                label += "   %s" % api.department_label(info["department"])
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
        """Render the open shot: save the scene as its next version, copy it
        into a new version folder, then render the copy here, in the
        background (queued behind a batch render already running) or in the
        cloud. Other renders, from any shot, can be running."""
        self.refresh()
        if not self.ctx:
            return _say(self.error)
        camera = self.camera()
        if not camera:
            return _say("There's no camera to render through.")
        how = self.how()
        if how == api.SEQUENCE and _QUEUE.batch_running():
            return _say("A batch render is using this computer. Render in the background "
                        "instead (it waits its turn), or wait for it.")
        try:
            frames = self.frames()
            changed = api.ensure_arnold()
            next_name = os.path.basename(api.version_up_path(cmds.file(query=True, sceneName=True)))
            if changed or cmds.file(query=True, modified=True):
                if cmds.confirmDialog(
                        title="renderSub",
                        message="Save the scene as %s and render it?" % next_name,
                        button=["Save and Render", "Cancel"], defaultButton="Save and Render",
                        cancelButton="Cancel", dismissString="Cancel") != "Save and Render":
                    return
            # Every render has its own version of the working file (user,
            # 2026-11-19); the artist carries on in it.
            scene = api.save_version_up()
            self.refresh()
            keep = cmds.intField(self.w["keep"], q=True, value=True)
            lost = api.prune(self.ctx, keep - 1, _QUEUE.folders()) if keep > 0 else []
            if lost:
                cmds.warning("renderSub: deleted unpublished local render(s) %s (keeping the "
                             "newest %d)." % (", ".join(lost), keep))
            info = api.plan_render(self.ctx, scene, frames, camera, self.percent(), how=how,
                                   department=self.department())
            api.copy_scene(info)
            if how == api.SEQUENCE:
                return self._render_in_maya(info)
            if how == api.FLOW:
                try:
                    _QUEUE.add(_flow().FlowJob.submit(info))
                except Exception as e:
                    api.finish_render(info, 1)
                    self.refresh_versions()
                    raise api.PublishError("Flow Render didn't take the job:\n%s" % e)
                _remember_cloud()
            else:
                _QUEUE.add_batch(info)
        except (api.PublishError, OSError, RuntimeError) as e:
            return _say(str(e))
        _watch_quit()
        print("renderSub: %s %s is render %s" % (info["shot"], info["version"], info["render_id"]))
        cmds.inViewMessage(amg="renderSub: saved as <hl>%s</hl>; %s %s." % (
            os.path.basename(scene), info["version"],
            "queued" if info["status"] == api.QUEUED else "started"),
            pos="topCenter", fade=True)
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
        self.report(info)

    # ------------------------------------------------------------------ queue
    def show_queue(self):
        """The Render Queue list: every render running or waiting, any shot."""
        selected = self._queue_selected()
        self._queue_rows = [j.info for j in _QUEUE.jobs] + list(_QUEUE.waiting)
        cmds.textScrollList(self.w["queue"], e=True, removeAll=True)
        for info in self._queue_rows:
            cmds.textScrollList(self.w["queue"], e=True,
                                append="%s  %s   %s" % (info["shot"], info["version"],
                                                        describe(info)))
        for n, info in enumerate(self._queue_rows, 1):
            if selected and api._same(info["folder"], selected):
                cmds.textScrollList(self.w["queue"], e=True, selectIndexedItem=n)
        cmds.button(self.w["cancel"], e=True, enable=bool(self._queue_rows))
        batch = next((j for j in _QUEUE.jobs if j.info.get("how") == api.BATCH), None)
        if batch:
            cmds.progressBar(self.w["progress"], e=True, maxValue=len(batch.info["frames"]),
                             progress=batch.frames_done())
        else:
            cmds.progressBar(self.w["progress"], e=True, maxValue=1, progress=0)

    def _queue_selected(self):
        index = cmds.textScrollList(self.w["queue"], q=True, selectIndexedItem=True)
        rows = getattr(self, "_queue_rows", [])
        return rows[index[0] - 1]["folder"] if index and index[0] <= len(rows) else None

    def tick(self):
        """Every TICK_MS while anything is in the queue: the list, and the
        status line for the running batch render (else the newest job)."""
        self.show_queue()
        job = next((j for j in _QUEUE.jobs if j.info.get("how") == api.BATCH), None) or \
            (_QUEUE.jobs[-1] if _QUEUE.jobs else None)
        if job:
            cmds.text(self.w["status"], e=True, label="%s %s: %s" % (
                job.info["shot"], job.info["version"], describe(job.info, job)))
        elif _QUEUE.waiting:
            cmds.text(self.w["status"], e=True, label="%d render(s) waiting" % len(_QUEUE.waiting))

    def report(self, info):
        """A render finished: the Watch before publishing window (or why it
        failed). One at a time: another that finishes meanwhile waits."""
        self._to_review.append(info)
        if self._reviewing:
            return
        self._reviewing = True
        try:
            while self._to_review:
                self._report(self._to_review.pop(0))
        finally:
            self._reviewing = False

    def _report(self, info):
        in_rv = info["status"] == api.DONE and cmds.checkBox(self.w["open_rv"], q=True, value=True)
        if in_rv:
            open_in_rv(info)
        if info["status"] == api.DONE:
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
        else:
            done = len(api.finished_frames(info))
            label = "%s %s: %d of %d frame(s) finished" % (info["version"], info["status"],
                                                           done, len(info["frames"]))
            if done:
                label += " (Publish Selected publishes them)"
            cmds.text(self.w["status"], e=True, label=label)
            if info["status"] == api.FAILED:
                if info.get("how") == api.FLOW:
                    where = (info.get("flow") or {}).get("error") or "See the Script Editor."
                elif info.get("how") == api.SEQUENCE:
                    where = "Arnold's messages are in the Script Editor."
                else:
                    where = "End of the render log:\n%s" % api.log_tail(info)
                _say("%s didn't finish: %d frame(s) missing.%s\n\n%s"
                     % (info["version"], len(info["missing"]),
                        " The %d that finished can still be published: pick it in Local "
                        "Versions, then Publish Selected." % done if done else "", where))

    def cancel(self):
        """Cancel the render picked in the Render Queue."""
        folder = self._queue_selected()
        if not folder:
            if len(getattr(self, "_queue_rows", [])) != 1:
                return _say("Pick the render to cancel in the Render Queue list.")
            folder = self._queue_rows[0]["folder"]
        note = _QUEUE.cancel(folder)
        _on_tick()
        if note:
            _say(note)

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

    def copy_id(self):
        v = self.selected()
        if not v:
            return
        rid = v["info"].get("render_id")
        if not rid:
            return _say("%s has no render ID." % v["name"])
        from PySide6 import QtWidgets
        QtWidgets.QApplication.clipboard().setText(rid)
        print("renderSub: %s is render %s (copied)" % (v["name"], rid))
        cmds.inViewMessage(amg="Copied render ID <hl>%s</hl>" % rid, pos="midCenter", fade=True)

    def find_render(self):
        """Where is the render with this ID, and how does it stand?"""
        if cmds.promptDialog(title="Find Render", message="Render ID (or the start of one):",
                             button=["Find", "Cancel"], defaultButton="Find",
                             cancelButton="Cancel", dismissString="Cancel") != "Find":
            return
        rid = cmds.promptDialog(query=True, text=True).strip()
        if not rid:
            return
        entry = api.find_render(rid)
        if not entry:
            h_root = pub.get_root(pub.H_DRIVE)
            entry = api.find_published(rid, h_root) if h_root else None
        if not entry:
            return _say("No render with ID %s on this computer's scratch drive or published "
                        "on the H drive (an ID that matches more than one render needs more "
                        "of it)." % rid)
        _say(api.describe_render(entry))
        v = self.selected()
        if not v:
            return
        if any(api._same(f, v["path"]) for f in _QUEUE.folders()):
            return _say("That version is in the Render Queue. Cancel it first.")
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
        # The version's own shot, not the open scene's (api.version_ctx):
        # the open scene can be another shot, or unsaved.
        name = os.path.basename(folder)
        cmds.waitCursor(state=True)
        try:
            result = api.publish(self.ctx, folder, notes, running=_QUEUE.folders())
        except Exception as e:
            return _say("The publish stopped:\n%s" % e)
        finally:
            cmds.waitCursor(state=False)
        self.refresh()
        lines = ["%s copied to the H drive:\n%s" % (name, result["dest"])]
        if result.get("partial"):
            lines.append("Only the frames that finished were published; the ShotGrid note says so.")
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
        frames = api.finished_frames(info)
        if api.partial(info):
            what = ("%d of %d frame(s) finished (%s) before the render was %s. Only those "
                    "publish." % (len(frames), len(info["frames"]), api.seq_string(frames),
                                  info["status"]))
        else:
            what = "%d frame(s) %s." % (len(frames), "are opening in RV" if in_rv else "rendered")
        text = ("%s: %s\n\nPublish to the H drive and ShotGrid, or cancel to keep it "
                "on your scratch drive only (it stays in Local Versions)." % (info["version"], what))
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
        _TIMER.timeout.connect(_tick)
    _TIMER.start(TICK_MS)


def _tick():
    """The timer's slot. It looks _on_tick up each time, so after a reload
    the kept timer runs the new code."""
    _on_tick()


def _stop_timer():
    if _TIMER:
        _TIMER.stop()


def _on_tick():
    """Move the queue on. Finished renders get the Watch before publishing
    window when renderSub's window is open; with it closed they wait in
    their shot's Local Versions."""
    try:
        finished = _QUEUE.step()
    except Exception as e:      # never leave the timer dead with renders queued
        cmds.warning("renderSub: the render queue hit a problem: %s" % e)
        finished = []
    if any(info.get("how") == api.FLOW for info in finished):
        _remember_cloud()
    window = _UI and cmds.window(WINDOW, exists=True)
    if window:
        _UI.tick()
    if finished and window:
        _UI.refresh()
        for info in finished:
            _UI.report(info)
    for info in finished if not window else []:
        cmds.inViewMessage(amg="renderSub: <hl>%s %s</hl> %s. Open renderSub to review it."
                           % (info["shot"], info["version"], info["status"]),
                           pos="topCenter", fade=True)
    if not _QUEUE.busy():
        _stop_timer()


def describe(info, job=None):
    """What a render in the queue is doing, in a few words."""
    job = job or _QUEUE.job(info["folder"])
    total = len(info["frames"])
    if info.get("status") == api.QUEUED:
        return "batch: waiting (%s in line)" % _ordinal(_QUEUE.place(info["folder"]) or 1)
    if info.get("how") == api.FLOW:
        if api.in_cloud(info):
            return "cloud: in the cloud, %d of %d frame(s) downloaded" % (
                len(api.frame_files(info)), total)
        text = job.describe() if job else "uploading"
        return "cloud: " + (text.split(": ", 1)[-1] if text.startswith("Flow Render") else text)
    done = job.frames_done() if job else 0
    if job is None or job.poll() is not None:
        return "batch: finishing"
    text = "batch: rendering, %d of %d frame(s) done" % (done, total)
    if api.timing(info, running=True):
        text += ", about %s left" % api.duration(api.time_left(info))
    else:
        text += " (loading the scene)"
    return text


def _ordinal(n):
    return "%d%s" % (n, {1: "st", 2: "nd", 3: "rd"}.get(n if n < 20 else n % 10, "th"))


def _remember_cloud():
    """Note the cloud renders still to come back, so the next Maya watches
    them again whatever shot it opens (renderSub_api.read_jobs)."""
    keep = [f for f in api.read_jobs()["cloud"]
            if api.in_cloud(api.read_info(f)) and not any(api._same(f, c) for c in _QUEUE.cloud_folders())]
    api.write_jobs(cloud=keep + _QUEUE.cloud_folders())


def _watch_quit():
    """Once a render starts: when Maya closes, stop the batch renders
    (user, 2026-11-19: cloud renders carry on, batch renders don't) and
    leave a warning for the next Maya's Script Editor."""
    global _QUIT_JOB
    if _QUIT_JOB is None or not cmds.scriptJob(exists=_QUIT_JOB):
        _QUIT_JOB = cmds.scriptJob(event=["quitApplication", _on_quit], protected=True)


def _on_quit():
    try:
        _remember_cloud()
        lines = _QUEUE.stop_for_quit()
        if lines:
            api.write_jobs(stopped=api.read_jobs()["stopped"] + lines)
            for line in lines:
                print("renderSub: " + line)
    except Exception as e:      # never stop Maya closing
        print("renderSub: couldn't stop the renders cleanly: %s" % e)
