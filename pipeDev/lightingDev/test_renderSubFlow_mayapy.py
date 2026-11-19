# renderSub on Flow Render (user, 2026-11-13: "lets get it running so I can
# test it"). mayapy can't sign in to Autodesk or reach the cloud, so Arnold's
# Flow Render export queue is stood in, and the "download" is files written
# where Flow Render writes them. This checks renderSub's side: what it
# submits, that it only waits for the frames in the version folder (2026-11-18:
# it no longer tracks the cloud job), and that frames arriving any other way
# (later, from a Job Monitor zip, in Flow Render's own folder) still finish
# the version. The real cloud is the user's hand test.
# Run: mayapy test_renderSubFlow_mayapy.py
import sys, os, shutil, tempfile, zipfile
HERE = os.path.dirname(os.path.abspath(__file__))
for sub in ("", "../publishDev", "../buildDev"):
    sys.path.insert(0, os.path.normpath(os.path.join(HERE, sub)))
import maya.standalone; maya.standalone.initialize()
import maya.cmds as cmds
import publishTool_api as pub
pub.who = lambda: "tester"
import renderSub_api as rs
import renderSub_flow as flow
ok = []
def check(label, cond): ok.append(bool(cond)); print("PASS" if cond else "FAIL", label)

# --- frames ------------------------------------------------------------------
check("a range every N frames goes as it is", flow.cloud_frames([1001, 1003, 1005]) == [1001, 1003, 1005])
check("Every Nth: the end frame renderSub adds is dropped (Flow renders start..end by N)",
      flow.cloud_frames(rs.frames_for("step", 1001, 1010, 4)) == [1001, 1005, 1009])
check("lighting check: five frames evenly spaced from the first",
      flow.cloud_frames(rs.check_frames(1001, 1118)) == [1001, 1030, 1059, 1088, 1117])
check("one frame is a range", flow.cloud_frames([1050]) == [1050] and flow.is_range([1050]))
check("a frame list isn't a range", not flow.is_range([1001, 1002, 1050]))

# --- a shot, and the stand-ins for Arnold's Flow Render -------------------------
scratch, h_root = tempfile.mkdtemp(prefix="rsf_scratch_"), tempfile.mkdtemp(prefix="rsf_h_")
shot_dir = os.path.join(scratch, "RST_TST", "maya", "sequences", "SEQ010", "SEQ010_010")
os.makedirs(os.path.join(shot_dir, "scenes", "lighting", "tester"))
cmds.file(new=True, force=True)
cmds.loadPlugin("mtoa", quiet=True)
cmds.playbackOptions(minTime=1001, maxTime=1005)
cam = cmds.camera()[0]
rs.ensure_arnold()
cmds.setAttr("defaultRenderGlobals.imageFilePrefix", "myShot", type="string")
scene = os.path.join(shot_dir, "scenes", "lighting", "tester", "light_001.ma")
cmds.file(rename=scene); cmds.file(save=True, type="mayaAscii")
ctx = rs.shot_of(scene, h_root)


class FakeJob(object):
    def __init__(self, n):
        self.job_id, self.args, self.failed, self.finished, self.progress = "local-%d" % n, {}, False, False, 0
        self.pending = False
    def setStartFrame(self, f): self.start = f
    def setEndFrame(self, f): self.end = self.endFrame = f
    def setFrameStep(self, f): self.step = f
    def appendJobArgs(self, a): self.args.update(a)
    def generateExportFiles(self):
        self.exported_prefix = cmds.getAttr("defaultRenderGlobals.imageFilePrefix")
        self.exported_size = (cmds.getAttr("defaultResolution.width"), cmds.getAttr("defaultResolution.height"))
        self.exported_stamp = cmds.getAttr("defaultArnoldDriver.customAttributes[%d]" % rs.ID_INDEX)
        return True
    def isFailed(self): return self.failed
    def isFinished(self): return self.finished
    def isPending(self): return self.pending
    def getProgress(self): return self.progress


class FakeQueue(object):
    jobs, started, cancelled = [], [], []
    @classmethod
    def instance(cls): return cls
    @classmethod
    def createNewJob(cls):
        cls.jobs.append(FakeJob(len(cls.jobs) + 1)); return cls.jobs[-1]
    @classmethod
    def startNextJob(cls): cls.started.append(cls.jobs[-1])
    @classmethod
    def removeJob(cls, job): cls.jobs.remove(job)
    @classmethod
    def getJobById(cls, job_id): return next((j for j in cls.jobs if j.job_id == job_id), None)
    @classmethod
    def cancelJob(cls, job): cls.cancelled.append(job)


class FakeSubmitModule(object):
    @staticmethod
    def incrementCurrentExportProcessCounter(): pass


def fake_exr(path, render_id):
    """Just an EXR header carrying a render ID (all exr_attribute reads)."""
    import struct
    os.makedirs(os.path.dirname(path), exist_ok=True)
    value, z = render_id.encode(), bytes(1)
    with open(path, "wb") as out:
        out.write(bytes([0x76, 0x2f, 0x31, 0x01]) + struct.pack("<I", 2))
        out.write(b"compression" + z + b"compression" + z + struct.pack("<I", 1) + z)
        out.write(rs.ID_ATTR.encode() + z + b"string" + z + struct.pack("<I", len(value)) + value)
        out.write(z)


def download(folder, info, frames, aovs=("beauty", "N_noice")):
    """Flow Render's auto-download: <folder>\\<aov>\\<prefix>.####.exr."""
    for aov in aovs:
        os.makedirs(os.path.join(folder, aov), exist_ok=True)
        for f in frames:
            with open(rs.frame_path(os.path.join(folder, aov), info["prefix"], f), "w") as out:
                out.write(aov)


monitor = []
cmds.flowRenderJobMonitor = lambda *a, **k: monitor.append(True)
flow._modules = lambda: (FakeQueue, FakeSubmitModule)
flow.available = lambda: (True, "")
flow.signed_in = lambda: True
flow.CHECK_EVERY, flow.SETTLE = 0, -1
rs.make_review_media = lambda info: None         # the frames here aren't real EXRs

# --- submit ------------------------------------------------------------------------
frames = flow.cloud_frames(rs.frames_for("step", 1001, 1005, 2))
info = rs.plan_render(ctx, scene, frames, cam, percent=50, how=rs.FLOW)
check("a cloud render is recorded as one (for its own estimates)",
      info["where"] == {"kind": rs.CLOUD, "machine": rs.CLOUD_MACHINE} and info["how"] == rs.FLOW)
job = flow.FlowJob.submit(info)
fj = FakeQueue.jobs[-1]
check("submitted to Arnold's queue: the frames as a range, the size, the camera",
      (fj.start, fj.end, fj.step) == (1001, 1005, 2) and (fj.width, fj.height) == tuple(info["size"])
      and fj.cameras == [cmds.listRelatives(cam, shapes=True, fullPath=True)[0].replace("|", "/")]
      and fj.args["originalScenePath"] == info["scene"] and FakeQueue.started == [fj])
check("Flow Render downloads the frames itself, into the version folder",
      fj.autoDownload is True and os.path.normpath(fj.autoDownloadLocation) == info["folder"]
      and os.path.isdir(info["folder"]))
check("the uploaded copy has renderSub's frame name and size",
      fj.exported_prefix == info["prefix"] and fj.exported_size == tuple(info["size"]))
check("... and the artist's own render settings are put back",
      cmds.getAttr("defaultRenderGlobals.imageFilePrefix") == "myShot"
      and not cmds.file(q=True, modified=True))
check("the uploaded copy carries the render ID for every frame's EXR header, then it's taken off",
      fj.exported_stamp == "STRING %s %s" % (rs.ID_ATTR, info["render_id"])
      and rs.ID_INDEX not in (cmds.getAttr("defaultArnoldDriver.customAttributes", multiIndices=True) or []))
check("Flow Render's upload queue names the job with the shot, version and render ID",
      fj.job_name == "%s %s (%s)" % (info["shot"], info["version"], info["render_id"]))
fj.pending = True
check("behind another upload in Flow Render's queue: says it's waiting (2026-11-19)",
      job.poll() is None and "waiting for the upload before it" in job.describe())
fj.pending = False
check("exporting: says so", job.poll() is None and "ready to upload" in job.describe())

fj.progress = 1005
flow.UPLOAD_WARN_MB = 1
usd = os.path.splitext(scene)[0] + "_defaultRenderLayer__%d__1.usd" % os.getpid()
with open(usd, "wb") as out:
    out.write(b"0" * 2000000)
check("uploading: no frames yet, the upload's size noted and a big one flagged",
      job.poll() is None and job.info["flow"]["upload_mb"] == 2
      and "uploading the scene (2 MB)" in job.describe() and "10 min" in job.describe())
check("an upload isn't 'in the cloud' yet: Maya closing now would lose it",
      not rs.in_cloud(rs.read_info(info["folder"])))
os.remove(usd)

fj.finished = True                               # Arnold lets it go: the cloud has it
job.poll()
saved = rs.read_info(info["folder"])
check("in the cloud once Arnold's queue lets it go, saved in render.json",
      saved["flow"]["state"] == flow.SENT and rs.in_cloud(saved)
      and "in the cloud, 0 of 3" in job.describe() and "Job Monitor" in job.describe())
check("a cloud render isn't marked interrupted (it carries on with Maya closed)",
      rs.settle(saved)["status"] == rs.RENDERING)
check("... and pruning leaves it alone", rs.prune(ctx, 0) == [] and os.path.isdir(info["folder"]))

download(info["folder"], info, [1001, 1003])
check("frames arriving: counted, still waiting for the rest", job.poll() is None and job.frames_done() == 2)

# Maya closed and opened again: the window picks the job up from render.json.
job = flow.FlowJob(rs.read_info(info["folder"]))
download(info["folder"], info, [1005])
check("picked up after a restart, done once every frame is in the folder", job.poll() == 0)
done = job.finish()
check("finished: the beauty frames in beauty\\, AOVs beside them",
      done["status"] == rs.DONE and done["missing"] == []
      and all(open(rs.beauty_path(done, f)).read() == "beauty" for f in frames)
      and os.path.isfile(rs.frame_path(os.path.join(info["folder"], "N_noice"), info["prefix"], 1003)))
check("timed as a turnaround and kept apart from local renders",
      done["timing"]["done"] == 3 and rs.read_history(shot_dir)[-1]["where"]["kind"] == rs.CLOUD
      and rs.predict(shot_dir, 3, info["size"], kind=rs.CLOUD) is not None
      and rs.predict(shot_dir, 3, info["size"]) is None)


def sent(frames):
    j = flow.FlowJob.submit(rs.plan_render(ctx, scene, frames, cam, how=rs.FLOW))
    FakeQueue.removeJob(FakeQueue.jobs[-1])      # uploaded: gone from Arnold's queue
    j.poll()
    return j

# --- frames that come back another way ---------------------------------------------
late = sent([1001, 1002])
note = late.cancel()
check("cancel once it's in the cloud: stops waiting, says to stop it in the Job Monitor, opens it",
      note and "Job Monitor" in note and monitor and late.finish()["status"] == rs.CANCELLED)
default = os.path.join(shot_dir, flow.FLOW_DEFAULT_FOLDER)
download(default, late.info, [1001, 1002])
download(default, {"prefix": "someone_else"}, [1001], aovs=("beauty",))
caught = flow.catch_up(rs.read_info(late.info["folder"]))
check("its frames arriving later, in Flow Render's own folder: moved in and the version finished",
      caught["status"] == rs.DONE and len(rs.frame_files(caught)) == 2
      and os.path.isfile(rs.frame_path(os.path.join(default, "beauty"), "someone_else", 1001)))

zipped = sent([1001, 1002])
zipped.cancel()
zipped.finish()
src = os.path.join(scratch, "zipsrc")
download(os.path.join(src, "job_frames"), zipped.info, [1001, 1002])
zip_path = os.path.join(zipped.info["folder"], "NFW_defaultRenderLayer_cameraShape1.zip")
with zipfile.ZipFile(zip_path, "w") as z:
    for root, _, names in os.walk(src):
        for n in names:
            z.write(os.path.join(root, n), os.path.relpath(os.path.join(root, n), src))
caught = flow.catch_up(rs.read_info(zipped.info["folder"]))
check("a zip saved from the Job Monitor into the version folder: unzipped into place, zip gone",
      caught["status"] == rs.DONE and len(rs.frame_files(caught)) == 2 and not os.path.exists(zip_path)
      and os.path.isdir(os.path.join(zipped.info["folder"], "beauty")))

# frames somewhere else entirely (2026-11-19, SEQ010_170 v005): found by the ID in
# their EXR headers, moved in with their AOV folders; another render's left alone
lost_id = sent([1001, 1002])
lost_id.cancel(); lost_id.finish()
where_ = os.path.join(shot_dir, "images", "someDownload", "job_1234")
for aov in ("beauty", "N_noice"):
    for f in (1001, 1002):
        fake_exr(rs.frame_path(os.path.join(where_, aov), lost_id.info["prefix"], f), lost_id.info["render_id"])
other = rs.frame_path(os.path.join(where_, "beauty"), "SEQ010_010_tester_render_v099", 1001)
fake_exr(other, "R20260101-000000-SEQ010_010-0000")
caught = flow.catch_up(rs.read_info(lost_id.info["folder"]))
check("frames that landed anywhere in the shot are found by render ID and finish the version",
      caught["status"] == rs.DONE and len(rs.frame_files(caught)) == 2
      and os.path.isfile(rs.frame_path(os.path.join(lost_id.info["folder"], "N_noice"), lost_id.info["prefix"], 1002))
      and os.path.isfile(other))

half = sent([1001, 1002])
half.cancel(); half.finish()
download(half.info["folder"], half.info, [1001])
check("only some frames back: it stays stopped (a partial publish is still there)",
      flow.catch_up(rs.read_info(half.info["folder"]))["status"] == rs.CANCELLED)

# --- when it goes wrong ---------------------------------------------------------------
early = flow.FlowJob.submit(rs.plan_render(ctx, scene, [1001], cam, how=rs.FLOW))
check("cancel before the upload finishes: Arnold's queue cancels it",
      early.cancel() is None and FakeQueue.cancelled[-1].job_id == early.info["flow"]["local"]
      and early.finish()["status"] == rs.CANCELLED)

lost = flow.FlowJob.submit(rs.plan_render(ctx, scene, [1001], cam, how=rs.FLOW))
FakeQueue.jobs[-1].failed = True
check("the export or upload failing fails the render", lost.poll() == 1)

shutil.rmtree(scratch, ignore_errors=True); shutil.rmtree(h_root, ignore_errors=True)
print("\n%d/%d passed" % (sum(ok), len(ok)))
