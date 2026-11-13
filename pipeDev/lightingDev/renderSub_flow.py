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

How a job goes (the same steps as Arnold's own Flow Render window,
flow_render/ui/flowRenderSubmitUI.py, read 2026-11-13 in Arnold 7.5.2):
    submit      ExportQueueManager job: Maya saves a copy of the scene
                beside it, a background mayabatch exports it to USD and
                uploads it (Maya stays free). renderSub's frame names and
                size are set on the scene only while the copy is saved.
    track       the local job id -> the cloud job id (flowRenderQuery
                -fgeIdFromJobId; only this Maya knows it until it's saved
                to render.json), then -jobStatus every QUERY_EVERY s.
    download    when it succeeds, flowRenderSubmit -download into the
                version's flow_download\\ folder; the EXRs are moved up into
                the version folder under renderSub's own names
                (<shot>_<login>_render_v###.####.exr), so review, partial
                publish and Publish work as for a local render.
Once the cloud id is in render.json, closing Maya doesn't lose the job: the
renderSub window picks it up again and downloads it when it's done.

Flow Render renders start..end every N frames (its "frameSampling" is
motion-blur sub-frames, not a frame list), so cloud_frames() turns
renderSub's frame modes into a range.
"""

import os
import re
import time
import shutil

import maya.cmds as cmds

import renderSub_api as api

PublishError = api.PublishError

QUERY_EVERY = 15            # seconds between asking the cloud how a job is going
ID_WAIT = 300               # seconds to wait for the cloud id once the upload's done
DOWNLOAD_WAIT = 1800        # seconds to wait for every frame to download
INCOMING = "flow_download"  # where Flow Render downloads to, inside the version
OK_STATES = {"SUCCEEDED", "COMPLETED"}
BAD_STATES = {"FAILED", "CANCELED", "CANCELLED"}
EXPORT_MAYA_USD, EXPORT_ARNOLD_USD = "maya-usd", "arnold-usd"

_DOWNLOADED = set()         # cloud ids whose download Flow Render says has finished


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
# Download: Flow Render's files -> renderSub's names
# ---------------------------------------------------------------------------

_FRAME_NUMBER = re.compile(r"(\d+)\.exr$", re.IGNORECASE)


def collect(info):
    """Move downloaded EXRs from flow_download\\ (any subfolder, any name
    ending <frame>.exr) to <prefix>.####.exr in the version folder. With
    several files for one frame (AOVs), the beauty, else the shortest name.
    Returns the frames now in place."""
    incoming = os.path.join(info["folder"], INCOMING)
    wanted = set(info["frames"])
    found = {}
    for root, _, names in os.walk(incoming):
        for name in names:
            m = _FRAME_NUMBER.search(name)
            if not m or int(m.group(1)) not in wanted:
                continue
            frame = int(m.group(1))
            rank = (0 if "beauty" in name.lower() else 1, len(name))
            if frame not in found or rank < found[frame][0]:
                found[frame] = (rank, os.path.join(root, name))
    for frame, (_, path) in found.items():
        target = api.frame_path(info["folder"], info["prefix"], frame)
        if not os.path.isfile(target):
            try:
                shutil.move(path, target)
            except OSError:
                pass        # still being written; next time
    return [f for f in info["frames"] if os.path.isfile(api.frame_path(info["folder"], info["prefix"], f))]


def tidy(info):
    """Remove flow_download\\ once nothing is left in it but what renderSub
    didn't use (kept, and named, if anything else came down: the hand test
    shows what Flow Render sends)."""
    incoming = os.path.join(info["folder"], INCOMING)
    left = [os.path.relpath(os.path.join(r, n), incoming)
            for r, _, names in os.walk(incoming) for n in names]
    if not left:
        shutil.rmtree(incoming, ignore_errors=True)
    return left


def _downloaded(job_id):
    """Flow Render's download-finished callback."""
    _DOWNLOADED.add(str(job_id))


# ---------------------------------------------------------------------------
# A job: the same face as renderSub_api.RenderJob (poll / frames_done /
# cancel / finish), plus describe() for the window's status line.
# ---------------------------------------------------------------------------

class FlowJob(object):

    def __init__(self, info):
        self.info = info
        self.cancelled = False
        self._result = None
        self._next_query = 0.0
        self._download_asked = info.get("flow", {}).get("download_asked")
        self._lost_since = None

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

        sfr.incrementCurrentExportProcessCounter()
        manager = EQM.instance()
        job = manager.createNewJob()
        job.renderLayer = cmds.editRenderLayerGlobals(query=True, currentRenderLayer=True)
        job.exportMode = (EXPORT_MAYA_USD if cmds.pluginInfo("mayaUsdPlugin", query=True, registered=True)
                          else EXPORT_ARNOLD_USD)
        job.testResolution = "100%"
        job.skipFileCheck = True        # renderSub saved the scene first
        job.autoDownload = False        # renderSub downloads it, into the version folder
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
        info["flow"] = {"local": str(job.job_id), "fge": "", "state": "Uploading",
                        "percent": 0, "export_mode": job.exportMode,
                        "range": [start, end, step]}
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
        """None while the job runs; then 0 (frames came back) or 1."""
        if self._result is None:
            try:
                self._step()
            except Exception as e:
                self._fail("Flow Render stopped answering: %s" % e)
        return self._result

    def _step(self):
        flow = self.info["flow"]
        now = time.time()
        if not flow.get("fge"):
            return self._find_cloud_id(flow, now)
        if not self._download_asked:
            if now < self._next_query:
                return
            self._next_query = now + QUERY_EVERY
            self._check_status(flow)
        if self._download_asked and self._result is None:
            got = collect(self.info)
            if set(self.info["frames"]) <= set(got) or flow["fge"] in _DOWNLOADED:
                collect(self.info)
                left = tidy(self.info)
                if left:
                    flow["unused_downloads"] = left[:20]
                self._save()
                self._result = 0
            elif now - flow.get("download_started", now) > DOWNLOAD_WAIT:
                self._fail("The download didn't finish in %d min." % (DOWNLOAD_WAIT // 60))

    def _find_cloud_id(self, flow, now):
        job = self._local_job()
        if job is not None and job.isFailed():
            return self._fail("Flow Render couldn't export or upload the scene. Arnold's log "
                              "is named in the Script Editor.")
        try:
            out = cmds.flowRenderQuery(fgeIdFromJobId=flow["local"])
        except Exception:
            out = None
        fge = str(out[0] if isinstance(out, (list, tuple)) and out else out or "")
        if fge:
            flow.update(fge=fge, state="Queued")
            self._save()
            return
        if job is None:
            # Uploaded (the job's gone from the queue) but no cloud id yet.
            self._lost_since = self._lost_since or now
            if now - self._lost_since > ID_WAIT:
                self._fail("The upload finished but Flow Render never gave the job an id. "
                           "Check Arnold > Flow Render > Job Monitor.")

    def _check_status(self, flow):
        result = cmds.flowRenderQuery(jobStatus=flow["fge"]) or []
        if isinstance(result, str):
            result = [result]
        state = str(result[0]).upper() if result else ""
        try:
            percent = float(result[1]) if len(result) > 1 else flow.get("percent", 0)
        except ValueError:
            percent = flow.get("percent", 0)
        if state and (state != flow.get("state") or percent != flow.get("percent")):
            flow.update(state=state, percent=percent)
            self._save()
        if state in OK_STATES:
            self._download(flow)
        elif state in BAD_STATES:
            self._fail("Flow Render says the job %s." % state.lower())

    def _download(self, flow):
        incoming = os.path.join(self.info["folder"], INCOMING)
        os.makedirs(incoming, exist_ok=True)
        callback = 'python("import renderSub_flow; renderSub_flow._downloaded(\\"%s\\")")' % flow["fge"]
        cmds.flowRenderSubmit(download=flow["fge"], downloadLocation=incoming.replace("\\", "/"),
                              downloadFinishedCallback=callback)
        self._download_asked = True
        flow.update(download_asked=True, download_started=time.time(), state="Downloading")
        self._save()

    # ------------------------------------------------------------- the window's view
    def frames_done(self):
        if self._download_asked:
            return len(api.frame_files(self.info))
        percent = self.info["flow"].get("percent") or 0
        return int(len(self.info["frames"]) * min(100.0, percent) / 100.0)

    def describe(self):
        flow = self.info["flow"]
        state = flow.get("state", "")
        if not flow.get("fge"):
            text = "uploading the scene (Maya stays free; don't close it until it's queued)"
        elif self._download_asked:
            text = "downloading: %d of %d frame(s)" % (len(api.frame_files(self.info)),
                                                       len(self.info["frames"]))
        else:
            text = "%s, %d%%" % (state.lower() or "queued", int(flow.get("percent") or 0))
        return "Flow Render %s: %s" % (self.info["version"], text)

    def cancel(self):
        """Stop it. Before the upload finishes, Arnold's queue cancels it;
        after, the cloud job can only be stopped in Flow Render's Job
        Monitor (opened here). Returns a note for the artist, or None."""
        self.cancelled = True
        self._result = 1
        flow = self.info["flow"]
        if not flow.get("fge"):
            job = self._local_job()
            if job is not None:
                EQM, _ = _modules()
                EQM.instance().cancelJob(job)
            return None
        try:
            cmds.flowRenderJobMonitor()
        except Exception:
            pass
        return ("renderSub has stopped waiting for %s, but the job may still be rendering in "
                "the cloud (and using your hours). Cancel it in Flow Render's Job Monitor, "
                "now open." % self.info["version"])

    def finish(self):
        if self.info["flow"].get("download_asked"):
            collect(self.info)
        return api.finish_render(self.info, self._result, cancelled=self.cancelled)
