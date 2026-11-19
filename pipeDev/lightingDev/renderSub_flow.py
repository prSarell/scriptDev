"""
renderSub on Flow Render: Autodesk's Arnold cloud rendering (tech preview
since Arnold 7.5.1; 40 h free per Autodesk account a month). The user,
2026-11-13: "this might be a great option for students to handle test render
submissions during animation without locking them out of machines"; "lets
get it running so I can test it. If it turns out to be to difficult to
manage we will ditch it."

Everything Flow Render is in this file, so an Arnold update that changes it
only breaks this file (renderSub's "Render on" menu then greys the option
out), and ditching it is deleting this file and that menu item.

renderSub only SENDS the render to the cloud and then watches the version
folder for the frames (user, 2026-11-18: "Maybe all renderSub needs to do is
send the render to the the cloud"). Hand tests 2026-11-18 showed the cloud
renders work, but renderSub can't follow a job there: flowRenderQuery
-fgeIdFromJobId doesn't map Arnold's export-queue job to the cloud job, so
renderSub never got an id to ask about or download, and marked good renders
failed. Flow Render's own auto-download already brings the frames down,
named as renderSub names them, so:

    submit      ExportQueueManager job (the same steps as Arnold's Flow
                Render window, flow_render/ui/flowRenderSubmitUI.py): Maya
                saves a copy of the scene, a background mayabatch exports it
                to USD, then Maya uploads it (Maya stays free). renderSub's
                frame names and size are set on the scene only while the copy
                is saved. Auto-download is on, into the version folder:
                Flow Render writes <version>\\<aov>\\<prefix>.####.exr, the
                layout frames_folder() reads (beauty\\ plus the AOVs).
    uploading   until Arnold's queue lets the job go: it does that when the
                cloud has taken the job (_finalizeBatchExport, after the
                submission-finished callback).
    in the cloud  renderSub waits for every frame to be in the folder. It
                can't see the cloud job, so a job that fails there just
                sends no frames: the status line points at Flow Render's Job
                Monitor, and Cancel stops waiting. Frames that arrive later
                (Maya was closed, or the artist downloaded the zip from the
                Job Monitor into the version folder) are picked up by
                catch_up() whenever the window lists the versions.

Upload limit (hand test 2026-11-18, FlowRenderMaya.log): Flow Render's
upload links last 10 minutes. A 354 MB USD (101 animated frames) took 12 min
at ~0.5 MB/s, the last file's link had run out (403), Flow Render skipped it
without noticing, and every frame failed "Missing path mapping file
data/pathmap.json". renderSub warns when the export is bigger than
UPLOAD_WARN_MB; fewer frames make a smaller USD.

Flow Render renders start..end every N frames (its "frameSampling" is
motion-blur sub-frames, not a frame list), so cloud_frames() turns
renderSub's frame modes into a range.
"""

import os
import glob
import time
import shutil
import zipfile

import maya.cmds as cmds

import renderSub_api as api

PublishError = api.PublishError

UPLOADING, SENT = "uploading", "in the cloud"
CHECK_EVERY = 10            # seconds between looks at the version folder
SETTLE = 15                 # a frame untouched this long has finished downloading
UPLOAD_WARN_MB = 250        # ~10 min of upload at 0.5 MB/s (see the module notes)
FLOW_DEFAULT_FOLDER = "flow_render_images"   # Flow Render's own download folder, in the project
EXPORT_MAYA_USD, EXPORT_ARNOLD_USD = "maya-usd", "arnold-usd"
JOB_MONITOR = "Arnold > Flow Render > Job Monitor"


# ---------------------------------------------------------------------------
# Is it here?
# ---------------------------------------------------------------------------

def _modules():
    from flow_render.core.exportQueueManager import ExportQueueManager
    from flow_render.cmds import submitFlowRender as sfr
    return ExportQueueManager, sfr


def available():
    """(True, "") when this Maya can use Flow Render, else (False, why)."""
    if cmds.about(batch=True):
        return False, "Flow Render needs Maya with its window open."
    try:
        if not cmds.pluginInfo("flowRender", query=True, loaded=True):
            cmds.loadPlugin("flowRender", quiet=True)
        _modules()
    except Exception:
        return False, ("This Maya's Arnold has no Flow Render: it needs Arnold for Maya "
                       "5.6.1 or newer (Arnold 7.5.1+).")
    import maya.OpenMaya as om
    if not hasattr(om, "MCloudWebService"):
        return False, "This Maya can't sign in to an Autodesk account."
    return True, ""


def signed_in():
    import maya.OpenMaya as om
    try:
        return bool(om.MCloudWebService.isLoggedIn())
    except Exception:
        return False


def sign_in():
    """Maya's own Autodesk sign-in (Flow Render uses that account: there's
    no separate Arnold account)."""
    import maya.OpenMaya as om
    om.MCloudWebService.login()


def quota_text():
    """Flow Render's own summary of the free hours left, or ""."""
    try:
        return cmds.flowRenderQuery(quotaOverviewText=True) or ""
    except Exception:
        return ""


def open_job_monitor():
    try:
        cmds.flowRenderJobMonitor()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Frames
# ---------------------------------------------------------------------------

def _even(frames):
    return len(frames) < 3 or len({b - a for a, b in zip(frames, frames[1:])}) == 1


def cloud_frames(frames):
    """The frames Flow Render will render for renderSub's frames: the same
    ones when they're a range every N frames; an Every Nth render without
    the end frame renderSub adds; otherwise (the lighting check) the same
    number of frames evenly spaced from the first, which can land a frame
    short of the end."""
    frames = sorted(set(frames))
    if _even(frames):
        return frames
    if _even(frames[:-1]):
        return frames[:-1]
    n = len(frames)
    step = max(1, (frames[-1] - frames[0]) // (n - 1))
    return list(range(frames[0], frames[0] + step * (n - 1) + 1, step))


def is_range(frames):
    """True when Flow Render can render exactly these frames."""
    return _even(sorted(set(frames)))


def _range(frames):
    step = frames[1] - frames[0] if len(frames) > 1 else 1
    return frames[0], frames[-1], step


# ---------------------------------------------------------------------------
# The frames coming back
# ---------------------------------------------------------------------------

def _move_into(src, dst, keep=lambda name: True):
    """Move the files under src (keeping their subfolders) into dst, those
    keep() wants; a file still being written stays for next time. Empty
    folders left behind are removed."""
    for root, _, names in os.walk(src, topdown=False):
        rel = os.path.relpath(root, src)
        for name in names:
            if not keep(name):
                continue
            target_dir = os.path.normpath(os.path.join(dst, rel))
            target = os.path.join(target_dir, name)
            if os.path.exists(target):
                continue
            try:
                os.makedirs(target_dir, exist_ok=True)
                shutil.move(os.path.join(root, name), target)
            except OSError:
                pass
        if os.path.normcase(root) != os.path.normcase(src):
            try:
                os.rmdir(root)
            except OSError:
                pass


def _ours(info):
    return lambda name: name.startswith(info["prefix"] + ".")


def _unzip(info):
    """A zip the artist saved from the Job Monitor into the version folder:
    its frames go in place and the zip goes (or Publish would copy it to H).
    A zip still downloading isn't a whole zip yet, so it waits."""
    folder = info["folder"]
    for path in glob.glob(os.path.join(folder, "*.zip")):
        if not zipfile.is_zipfile(path):
            continue
        try:
            with zipfile.ZipFile(path) as z:
                names = [n for n in z.namelist() if not n.endswith("/")]
                if not any(os.path.basename(n).startswith(info["prefix"] + ".") for n in names):
                    continue        # not this version's frames: leave it be
                for n in names:
                    if os.path.isabs(n) or ".." in n.replace("\\", "/").split("/"):
                        continue
                    z.extract(n, folder)
            os.remove(path)
        except (OSError, zipfile.BadZipFile):
            pass


def _lift(info):
    """Frames that came down one folder too deep (a zip's own top folder,
    say: <version>\\<something>\\beauty\\...) move up to <version>\\beauty\\..."""
    folder = info["folder"]
    for root, dirs, _ in os.walk(folder):
        depth = os.path.relpath(root, folder).count(os.sep) + (root != folder)
        if depth > 3:
            dirs[:] = []
            continue
        if root != folder and api.BEAUTY in dirs:
            _move_into(root, folder, _ours(info))
            dirs[:] = []


def collect(info):
    """Bring this version's downloaded frames into its folder from wherever
    they landed (a Job Monitor zip, too deep, or Flow Render's own
    <project>\\flow_render_images\\ when it ignored the download folder:
    hand test 2026-11-18). Returns the beauty frames now in place."""
    _unzip(info)
    _lift(info)
    default = os.path.join(info.get("project") or "", FLOW_DEFAULT_FOLDER)
    if info.get("project") and os.path.isdir(default):
        _move_into(default, info["folder"], _ours(info))
        try:
            os.rmdir(default)               # only when nothing else is in it
        except OSError:
            pass
    return api.frame_files(info)


def _settled(info):
    """True when no file in the version folder has changed for SETTLE s."""
    newest = 0
    for root, _, names in os.walk(info["folder"]):
        for n in names:
            try:
                newest = max(newest, os.path.getmtime(os.path.join(root, n)))
            except OSError:
                return False
    return time.time() - newest > SETTLE


def all_down(info):
    return len(collect(info)) == len(info["frames"]) and _settled(info)


def catch_up(info):
    """A cloud render renderSub isn't watching (Maya was closed, Cancel
    stopped the wait, the frames came from the Job Monitor): once every
    frame is in the folder, finish it so it can be reviewed and published.
    Returns the info, updated or not."""
    if (info.get("how") != api.FLOW or info.get("published") or info.get("status") == api.DONE
            or info.get("status") not in api.STOPPED + (api.RENDERING,)):
        return info
    if all_down(info):
        return api.finish_render(info, 0)
    return info


# ---------------------------------------------------------------------------
# A job: the same face as renderSub_api.RenderJob (poll / frames_done /
# cancel / finish), plus describe() for the window's status line.
# ---------------------------------------------------------------------------

class FlowJob(object):

    def __init__(self, info):
        self.info = info
        self.cancelled = False
        self._result = None
        self._next_check = 0.0
        self._warned_size = False

    # ------------------------------------------------------------- submit
    @classmethod
    def submit(cls, info):
        """Start the cloud render of a planned version (api.plan_render with
        how=FLOW). Returns the FlowJob, or raises PublishError."""
        ok, why = available()
        if not ok:
            raise PublishError(why)
        if not signed_in():
            sign_in()
            if not signed_in():
                raise PublishError("Sign in to your Autodesk account (Maya's Help > Sign In, "
                                   "top right of Maya), then render again. Flow Render uses "
                                   "the same account as Maya.")
        frames = info["frames"]
        if not is_range(frames):
            raise PublishError("Flow Render renders a range every N frames, not a frame list.")
        EQM, sfr = _modules()
        cam_shapes = cmds.listRelatives(info["camera"], shapes=True, fullPath=True, type="camera") or []
        if not cam_shapes:
            raise PublishError("The camera '%s' has no camera shape." % info["camera"])
        start, end, step = _range(frames)
        os.makedirs(info["folder"], exist_ok=True)

        sfr.incrementCurrentExportProcessCounter()
        manager = EQM.instance()
        job = manager.createNewJob()
        job.renderLayer = cmds.editRenderLayerGlobals(query=True, currentRenderLayer=True)
        job.exportMode = (EXPORT_MAYA_USD if cmds.pluginInfo("mayaUsdPlugin", query=True, registered=True)
                          else EXPORT_ARNOLD_USD)
        job.testResolution = "100%"
        job.skipFileCheck = True        # renderSub saved the scene first
        job.autoDownload = True         # Flow Render brings the frames down...
        job.autoDownloadLocation = info["folder"].replace("\\", "/")   # ...into the version
        job.setStartFrame(start)
        job.setEndFrame(end)
        job.setFrameStep(step)
        job.cameras = [cam_shapes[0].replace("|", "/")]
        job.width, job.height = info["size"]
        job.frameSampling = ""
        job.appendJobArgs({"originalScenePath": info["scene"]})

        # The scene copy Flow Render uploads is saved now: give it
        # renderSub's frame names, size and camera while it's saved.
        settings = api._SequenceSettings(info)
        settings.values["defaultRenderGlobals.imageFilePrefix"] = info["prefix"]
        with settings:
            exported = job.generateExportFiles()
        if not exported:
            manager.removeJob(job)
            raise PublishError("Flow Render couldn't save a copy of the scene to upload. "
                               "See the Script Editor.")
        manager.startNextJob()
        info["flow"] = {"local": str(job.job_id), "state": UPLOADING,
                        "export_mode": job.exportMode, "range": [start, end, step]}
        api.write_info(info["folder"], info)
        return cls(info)

    # ------------------------------------------------------------- state
    def _save(self):
        api.write_info(self.info["folder"], self.info)

    def _local_job(self):
        try:
            EQM, _ = _modules()
            return EQM.instance().getJobById(self.info["flow"].get("local"))
        except Exception:
            return None

    def _fail(self, why):
        self.info["flow"]["error"] = why
        self._save()
        self._result = 1

    def poll(self):
        """None while the job runs; then 0 (every frame is in the folder) or 1."""
        if self._result is None:
            try:
                self._step()
            except Exception as e:
                self._fail("renderSub lost track of the Flow Render job: %s" % e)
        return self._result

    def _step(self):
        flow = self.info["flow"]
        if flow.get("state") == UPLOADING:
            job = self._local_job()
            if job is not None and job.isFailed():
                return self._fail("Flow Render couldn't export or upload the scene. Arnold's log "
                                  "is named in the Script Editor.")
            self._note_upload_size()
            if job is None or job.isFinished():
                # Arnold lets the job go once the cloud has it.
                flow.update(state=SENT, sent=api._now())
                self._save()
            return
        now = time.time()
        if now < self._next_check:
            return
        self._next_check = now + CHECK_EVERY
        if all_down(self.info):
            self._result = 0

    def _usd(self):
        """The USD Arnold exported for upload (beside the scene, named
        <scene>_<layer>__<pid>__<n>.usd; deleted once it's uploaded)."""
        base = os.path.splitext(self.info["scene"])[0]
        found = glob.glob("%s_*__%d__*.usd" % (glob.escape(base), os.getpid()))
        return max(found, key=os.path.getmtime) if found else None

    def _note_upload_size(self):
        usd = self._usd()
        try:
            mb = os.path.getsize(usd) / 1e6 if usd else 0
        except OSError:
            return
        if mb <= self.info["flow"].get("upload_mb", 0):
            return
        self.info["flow"]["upload_mb"] = round(mb)
        self._save()
        if mb > UPLOAD_WARN_MB and not self._warned_size:
            self._warned_size = True
            cmds.warning("renderSub: the scene for Flow Render is %d MB. On a slow connection "
                         "an upload over ~%d MB can run past Flow Render's 10 min upload limit, "
                         "and the job then fails in the cloud ('Missing path mapping file'). "
                         "Fewer frames make a smaller upload." % (mb, UPLOAD_WARN_MB))

    # ------------------------------------------------------------- the window's view
    def frames_done(self):
        return len(api.frame_files(self.info))

    def describe(self):
        flow, version = self.info["flow"], self.info["version"]
        if flow.get("state") == UPLOADING:
            job = self._local_job()
            exporting = job is not None and (job.getProgress() or 0) < getattr(job, "endFrame", 0)
            if job is not None and job.isPending():
                # Flow Render uploads one job at a time.
                text = "waiting for the upload before it"
            elif exporting:
                text = "getting the scene ready to upload (frame %d)" % job.getProgress()
            else:
                mb = flow.get("upload_mb")
                text = "uploading the scene%s" % (" (%d MB)" % mb if mb else "")
                if mb and mb > UPLOAD_WARN_MB:
                    text += ", big: it may not make Flow Render's 10 min limit"
            return "Flow Render %s: %s. Keep Maya open." % (version, text)
        return ("Flow Render %s: in the cloud, %d of %d frame(s) downloaded. Keep Maya open; "
                "the render's progress is in %s." % (version, self.frames_done(),
                                                    len(self.info["frames"]), JOB_MONITOR))

    def cancel(self):
        """Stop it. Before the upload finishes, Arnold's queue cancels it;
        after, renderSub stops waiting and the cloud job can only be
        stopped in Flow Render's Job Monitor (opened here). Returns a note
        for the artist, or None."""
        self.cancelled = True
        self._result = 1
        if self.info["flow"].get("state") == UPLOADING:
            job = self._local_job()
            if job is not None:
                EQM, _ = _modules()
                EQM.instance().cancelJob(job)
                return None
        open_job_monitor()
        return ("renderSub has stopped waiting for %s, but it may still be rendering in the "
                "cloud (and using your hours): cancel it in the Job Monitor, now open.\n\n"
                "If you let it finish instead, its frames still come back to the version "
                "folder, and renderSub finishes the version when they're all there."
                % self.info["version"])

    def finish(self):
        collect(self.info)
        return api.finish_render(self.info, self._result, cancelled=self.cancelled)
