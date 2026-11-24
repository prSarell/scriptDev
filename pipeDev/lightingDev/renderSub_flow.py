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
data/pathmap.json". 2026-11-24 (SEQ010_120 v004) the same 403 lost the
shot's USD landscape (Build's model stage): Flow Render logged it "already
uploaded", sent the job with 21 of its 22 files, and the frames came back
without the landscape. So:

    parts       a long range goes as several Flow Render jobs (plan_parts),
                each one's scene USD about PART_MB, sized from the shot's
                last cloud render (mb_per_frame). Arnold's queue uploads
                them one after another; the first carries the shared files
                (USD stages, textures) and the cloud keeps them, so the
                later parts skip them (Flow Render checks before uploading).
    the log     once a part is sent, its upload in FlowRenderMaya.log (from
                its scene USD's name to "Submitting job") is read for files
                that never got up (upload_problems). A part that lost one
                has its frames dropped as they arrive (they're missing that
                file), so the version can't finish or publish with them,
                and the artist is told which file and frames, to render
                them again.

Flow Render renders start..end every N frames (its "frameSampling" is
motion-blur sub-frames, not a frame list), so cloud_frames() turns
renderSub's frame modes into a range.
"""

import os
import re
import glob
import json
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
PART_MB = 150               # a part's scene USD: leaves room in the 10 min for the shared files
MB_PER_FRAME = 3.5          # with nothing to go on (SEQ010_120 2026-11-24: 353 MB, 101 frames)
FLOW_LOG = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Autodesk", "Logs", "FlowRenderMaya.log")
LOG_WAIT = 120              # s after a part is sent to find its upload in the log
_PUT = re.compile(r"sending http put request with file (.+?)(?: in \d+ parts?\b.*)?$")
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


def _count(rng):
    start, end, step = rng
    return (end - start) // max(1, step) + 1


# ---------------------------------------------------------------------------
# Parts: a long range as several jobs, each inside the upload limit
# ---------------------------------------------------------------------------

def plan_parts(frames, mb_frame):
    """renderSub's frames (a range) cut into as few even parts as keep each
    part's scene USD about PART_MB."""
    per = max(1, int(PART_MB / max(mb_frame, 0.01)))
    n = len(frames)
    size = -(-n // -(-n // per))            # even parts, none over per
    return [frames[i:i + size] for i in range(0, n, size)]


def mb_per_frame(info):
    """MB of scene USD per frame, from this shot's newest cloud render in
    the ledger (other renders of a shot export much the same scene), else
    MB_PER_FRAME."""
    try:
        found = glob.glob(os.path.join(api.ledger_dir(info), "*-%s-*.json" % info["shot"]))
    except Exception:
        found = []
    for path in sorted(found, key=os.path.getmtime, reverse=True):
        try:
            with open(path) as f:
                entry = json.load(f)
        except (IOError, OSError, ValueError):
            continue
        flow = entry.get("flow") or {}
        if entry.get("render_id") == info.get("render_id"):
            continue
        if flow.get("mb_per_frame"):
            return flow["mb_per_frame"]
        if flow.get("upload_mb") and flow.get("range"):     # before parts: one job
            return flow["upload_mb"] / float(_count(flow["range"]))
    return MB_PER_FRAME


def upload_problems(pos, marker, path=None):
    """Files a job's upload never got up, from FlowRenderMaya.log: its
    upload runs from the first line naming its scene USD (marker) to
    "Submitting job". A file counts when its last try ended "Failed to
    upload asset" (Flow Render then logs it "already uploaded" and sends
    the job anyway: 2026-11-24). Returns the paths, or None while the
    upload isn't all in the log yet."""
    try:
        with open(path or FLOW_LOG, "rb") as f:
            f.seek(0, 2)
            f.seek(pos if pos <= f.tell() else 0)
            data = f.read()
    except (IOError, OSError):
        return None
    started, failed, current = marker is None, {}, None
    for raw in data.splitlines():
        line = raw.decode("utf-8", "replace").rstrip()
        if not started:
            started = marker in line
            continue
        put = _PUT.search(line)
        if put:
            current = put.group(1).strip()
            failed[current] = False
        elif "Failed to upload asset" in line and current:
            failed[current] = True
        elif "Submitting job" in line:
            return sorted(p for p, bad in failed.items() if bad)
    return None


def lost_frames(info):
    return set((info.get("flow") or {}).get("lost_frames") or [])


def wanted_frames(info):
    """The frames still to come back whole: a part that lost a file on the
    way up renders without it, so its frames don't count."""
    lost = lost_frames(info)
    return [f for f in info["frames"] if f not in lost]


def _drop_lost(info):
    """A lost part's frames, wherever they are in the version (every AOV),
    go: they rendered without a file the scene needs."""
    for f in lost_frames(info):
        for path in api._frame_files(info, f):
            try:
                if os.path.isfile(path):
                    os.remove(path)
            except OSError:
                pass


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
    _drop_lost(info)
    if info.get("render_id") and len(api.frame_files(info)) < len(wanted_frames(info)):
        _by_id(info)
        _drop_lost(info)
    return api.frame_files(info)


def search_folders(info):
    """Where a cloud render's frames may land when Flow Render ignores the
    download folder: the shot's project (images\\, its own download folder)
    and the artist's Downloads."""
    project = info.get("project") or ""
    found = [os.path.join(project, "images"), os.path.join(project, FLOW_DEFAULT_FOLDER),
             os.path.join(os.path.expanduser("~"), "Downloads")]
    return [f for f in found if f and os.path.isdir(f)]


def _by_id(info):
    """Frames carrying this render's ID in their EXR header, found anywhere
    in search_folders, move into the version (an AOV's subfolder kept). A
    frame of any other render has another ID, so it's never taken."""
    folder = os.path.normcase(os.path.normpath(info["folder"]))
    for path in api.frames_with_id(info["render_id"], search_folders(info)):
        if os.path.normcase(os.path.normpath(path)).startswith(folder + os.sep):
            continue                        # already in the version
        parent_dir = os.path.dirname(path)
        parent = os.path.basename(parent_dir)
        # An AOV layout (<somewhere>\beauty\, <somewhere>\N_noice\...) keeps
        # its subfolder; a flat download goes in the version itself.
        in_aovs = parent == api.BEAUTY or os.path.isdir(
            os.path.join(os.path.dirname(parent_dir), api.BEAUTY))
        sub = parent if in_aovs else ""
        target = os.path.join(info["folder"], sub, os.path.basename(path))
        if os.path.exists(target):
            continue
        try:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.move(path, target)
        except OSError:
            pass


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
    return len(collect(info)) == len(wanted_frames(info)) and _settled(info)


def catch_up(info):
    """A cloud render renderSub isn't watching (Maya was closed, Cancel
    stopped the wait, the frames came from the Job Monitor): once every
    frame is in the folder, finish it so it can be reviewed and published.
    One that lost a file on the way up finishes failed, its lost part's
    frames dropped whenever they turn up. Returns the info, updated or not."""
    if (info.get("how") != api.FLOW or info.get("published") or info.get("status") == api.DONE
            or info.get("status") not in api.STOPPED + (api.RENDERING,)):
        return info
    if lost_frames(info) and info.get("status") in api.STOPPED:
        collect(info)
        return info
    if all_down(info):
        return api.finish_render(info, 1 if lost_frames(info) else 0)
    return info


# ---------------------------------------------------------------------------
# A job: the same face as renderSub_api.RenderJob (poll / frames_done /
# cancel / finish), plus describe() for the window's status line. One
# version can be several Flow Render jobs (info["flow"]["parts"]).
# ---------------------------------------------------------------------------

def _parts(info):
    """The version's Flow Render jobs; a render sent before parts (one job,
    its fields on info["flow"] itself) becomes one part."""
    flow = info["flow"]
    if "parts" not in flow:
        flow["parts"] = [{"local": flow.get("local"), "range": flow.get("range"),
                          "frames": len(info["frames"]), "state": flow.get("state"),
                          "upload_mb": flow.get("upload_mb"), "log": "before parts"}]
    return flow["parts"]


def _frames_text(part):
    start, end, step = part["range"]
    return "%d-%d" % (start, end) + (" every %d" % step if step > 1 else "")


class FlowJob(object):

    def __init__(self, info):
        self.info = info
        self.cancelled = False
        self._result = None
        self._next_check = 0.0
        self._next_log = 0.0
        self._warned_size = False
        _parts(info)

    # ------------------------------------------------------------- submit
    @classmethod
    def submit(cls, info):
        """Start the cloud render of a planned version (api.plan_render with
        how=FLOW), in parts when it's long (plan_parts). Returns the
        FlowJob, or raises PublishError."""
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
        os.makedirs(info["folder"], exist_ok=True)
        rate = mb_per_frame(info)
        slices = plan_parts(frames, rate)
        layer = cmds.editRenderLayerGlobals(query=True, currentRenderLayer=True)
        mode = (EXPORT_MAYA_USD if cmds.pluginInfo("mayaUsdPlugin", query=True, registered=True)
                else EXPORT_ARNOLD_USD)
        stem = os.path.splitext(os.path.basename(info["scene"]))[0]
        try:
            log_pos = os.path.getsize(FLOW_LOG)
        except OSError:
            log_pos = 0

        manager = EQM.instance()
        made, parts = [], []
        # The scene copies Flow Render uploads are saved now: give them
        # renderSub's frame names, size and camera while they're saved.
        settings = api._SequenceSettings(info)
        settings.values["defaultRenderGlobals.imageFilePrefix"] = info["prefix"]
        with settings:
            for n, part_frames in enumerate(slices, 1):
                start, end, step = _range(part_frames)
                sfr.incrementCurrentExportProcessCounter()
                job = manager.createNewJob()
                made.append(job)
                name = "%s %s" % (info["shot"], info["version"])
                if len(slices) > 1:
                    name += " part %d of %d" % (n, len(slices))
                if info.get("render_id"):       # shown in Flow Render's upload queue
                    name += " (%s)" % info["render_id"]
                job.job_name = name
                job.renderLayer = layer
                job.exportMode = mode
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
                if not job.generateExportFiles():
                    for j in made:
                        manager.removeJob(j)
                    raise PublishError("Flow Render couldn't save a copy of the scene to upload. "
                                       "See the Script Editor.")
                number = getattr(job, "job_number", None)
                parts.append({"local": str(job.job_id), "name": name, "state": UPLOADING,
                              "range": [start, end, step], "frames": len(part_frames),
                              # the USD Arnold exports, named <scene>_<layer>__<pid>__<n>.usd
                              "usd": ("%s_%s__%d__%d.usd" % (stem, layer, os.getpid(), number)
                                      if number is not None else None)})
        manager.startNextJob()
        info["flow"] = {"state": UPLOADING, "export_mode": mode, "range": list(_range(frames)),
                        "mb_per_frame_guess": round(rate, 2), "log_pos": log_pos, "parts": parts}
        api.write_info(info["folder"], info)
        return cls(info)

    # ------------------------------------------------------------- state
    def _save(self):
        api.write_info(self.info["folder"], self.info)

    def _local_job(self, part):
        try:
            EQM, _ = _modules()
            return EQM.instance().getJobById(part.get("local"))
        except Exception:
            return None

    def _unsent(self):
        return [p for p in _parts(self.info) if p.get("state") != SENT]

    def _cancel_uploads(self):
        """Arnold's queue drops the parts not yet sent. Returns how many."""
        n = 0
        for part in self._unsent():
            job = self._local_job(part)
            if job is not None:
                EQM, _ = _modules()
                EQM.instance().cancelJob(job)
                n += 1
        return n

    def _fail(self, why):
        self.info["flow"]["error"] = why
        self._save()
        self._result = 1

    def poll(self):
        """None while the job runs; then 0 (every frame is in the folder) or
        1 (failed, or a part lost a file on the way up)."""
        if self._result is None:
            try:
                self._step()
            except Exception as e:
                self._fail("renderSub lost track of the Flow Render job: %s" % e)
        return self._result

    def _step(self):
        flow = self.info["flow"]
        if flow.get("state") == UPLOADING:
            for part in self._unsent():
                job = self._local_job(part)
                if job is not None and job.isFailed():
                    self._cancel_uploads()
                    return self._fail("Flow Render couldn't export or upload the scene%s. Arnold's "
                                      "log is named in the Script Editor."
                                      % (" (%s)" % part["name"] if len(_parts(self.info)) > 1 else ""))
                if job is None or job.isFinished():
                    # Arnold lets the job go once the cloud has it.
                    part.update(state=SENT, sent=api._now(), sent_ts=time.time())
                    self._save()
                    continue
                if not job.isPending():
                    self._note_upload_size(part)
                break
            if not self._unsent():
                flow.update(state=SENT, sent=api._now())
                self._save()
        now = time.time()
        if now >= self._next_log:
            self._next_log = now + CHECK_EVERY
            self._check_log()
        if flow.get("state") == UPLOADING or now < self._next_check:
            return
        self._next_check = now + CHECK_EVERY
        if all_down(self.info):
            self._result = 1 if lost_frames(self.info) else 0

    # ------------------------------------------------------------- the log
    def _check_log(self):
        """Read each sent part's upload in FlowRenderMaya.log, in order, for
        files that never got up (upload_problems)."""
        flow = self.info["flow"]
        for part in _parts(self.info):
            if part.get("log"):
                continue
            if part.get("state") != SENT:
                return
            if not os.path.isfile(FLOW_LOG):
                part["log"] = "no log"
                self._save()
                continue
            problems = upload_problems(flow.get("log_pos", 0), part.get("usd"))
            if problems is None:
                if time.time() - part.get("sent_ts", 0) < LOG_WAIT:
                    return                  # the log may not be written yet
                part["log"] = "not in the log"
            elif problems:
                part.update(log="lost", lost=[os.path.basename(p) for p in problems])
                self._lose(part)
            else:
                part["log"] = "ok"
            self._save()

    def _lose(self, part):
        flow = self.info["flow"]
        start, end, step = part["range"]
        lost = set(flow.get("lost_frames") or []) | set(range(start, end + 1, step))
        flow["lost_frames"] = sorted(lost & set(self.info["frames"]))
        files = ", ".join(part["lost"])
        why = ("Flow Render lost %s on the way up (its upload link ran out), so frames %s "
               "render without it. renderSub drops those frames as they come back. Cancel "
               "'%s' in %s to save your cloud hours, then render frames %s again."
               % (files, _frames_text(part), part["name"], JOB_MONITOR, _frames_text(part)))
        flow["error"] = (flow["error"] + "\n\n" + why) if flow.get("error") else why
        cmds.warning("renderSub: " + why)
        collect(self.info)

    # ------------------------------------------------------------- upload size
    def _usd(self, part):
        """The USD Arnold exported for a part's upload (beside the scene;
        deleted once it's uploaded)."""
        folder = os.path.dirname(self.info["scene"])
        if part.get("usd"):
            path = os.path.join(folder, part["usd"])
            return path if os.path.isfile(path) else None
        base = os.path.splitext(self.info["scene"])[0]
        found = glob.glob("%s_*__%d__*.usd" % (glob.escape(base), os.getpid()))
        return max(found, key=os.path.getmtime) if found else None

    def _note_upload_size(self, part):
        usd = self._usd(part)
        try:
            mb = os.path.getsize(usd) / 1e6 if usd else 0
        except OSError:
            return
        if mb <= (part.get("upload_mb") or 0):
            return
        part["upload_mb"] = round(mb)
        flow = self.info["flow"]
        sized = [p for p in _parts(self.info) if p.get("upload_mb")]
        flow["upload_mb"] = sum(p["upload_mb"] for p in sized)
        flow["mb_per_frame"] = round(max(p["upload_mb"] / float(p["frames"]) for p in sized), 2)
        self._save()
        if mb > UPLOAD_WARN_MB and not self._warned_size:
            self._warned_size = True
            cmds.warning("renderSub: the scene for Flow Render is %d MB. On a slow connection "
                         "an upload over ~%d MB can run past Flow Render's 10 min upload limit, "
                         "and Flow Render then drops files from the job. Fewer frames make a "
                         "smaller upload." % (mb, UPLOAD_WARN_MB))

    # ------------------------------------------------------------- the window's view
    def frames_done(self):
        return len(api.frame_files(self.info))

    def describe(self):
        flow, version = self.info["flow"], self.info["version"]
        parts = _parts(self.info)
        lost = " Frames %s lost a file on the way up: see the Script Editor." % ", ".join(
            _frames_text(p) for p in parts if p.get("lost")) if lost_frames(self.info) else ""
        if flow.get("state") == UPLOADING:
            part = self._unsent()[0]
            job = self._local_job(part)
            which = (" part %d of %d (frames %s)" % (parts.index(part) + 1, len(parts),
                                                     _frames_text(part)) if len(parts) > 1 else "")
            exporting = job is not None and (job.getProgress() or 0) < getattr(job, "endFrame", 0)
            if job is not None and job.isPending():
                # Flow Render uploads one job at a time.
                text = "waiting for the upload before it"
            elif exporting:
                text = "getting the scene ready to upload (frame %d)" % job.getProgress()
            else:
                mb = part.get("upload_mb")
                text = "uploading the scene%s" % (" (%d MB)" % mb if mb else "")
                if mb and mb > UPLOAD_WARN_MB:
                    text += ", big: it may not make Flow Render's 10 min limit"
            return "Flow Render %s%s: %s. Keep Maya open.%s" % (version, which, text, lost)
        return ("Flow Render %s: in the cloud, %d of %d frame(s) downloaded. Keep Maya open; "
                "the render's progress is in %s.%s" % (version, self.frames_done(),
                                                      len(wanted_frames(self.info)), JOB_MONITOR, lost))

    def cancel(self):
        """Stop it. Parts not yet sent are cancelled in Arnold's queue;
        once a part is in the cloud renderSub just stops waiting, and the
        cloud job can only be stopped in Flow Render's Job Monitor (opened
        here). Returns a note for the artist, or None."""
        self.cancelled = True
        self._result = 1
        self._cancel_uploads()
        if not any(p.get("state") == SENT for p in _parts(self.info)):
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
