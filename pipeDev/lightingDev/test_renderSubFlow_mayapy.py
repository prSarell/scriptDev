# renderSub on Flow Render (user, 2026-11-13: "lets get it running so I can
# test it"). mayapy can't sign in to Autodesk or reach the cloud, so Arnold's
# Flow Render queue and its flowRenderQuery / flowRenderSubmit commands are
# stood in; this checks renderSub's side: what it submits, how it tracks the
# job (also after Maya restarts), and how the downloaded frames come back
# under renderSub's names. The real cloud is the user's hand test.
# Run: mayapy test_renderSubFlow_mayapy.py
import sys, os, shutil, tempfile
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
        self.job_id, self.args, self.failed = "local-%d" % n, {}, False
    def setStartFrame(self, f): self.start = f
    def setEndFrame(self, f): self.end = f
    def setFrameStep(self, f): self.step = f
    def appendJobArgs(self, a): self.args.update(a)
    def generateExportFiles(self):
        self.exported_prefix = cmds.getAttr("defaultRenderGlobals.imageFilePrefix")
        self.exported_size = (cmds.getAttr("defaultResolution.width"), cmds.getAttr("defaultResolution.height"))
        return True
    def isFailed(self): return self.failed


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


cloud = {"ids": {}, "status": {}, "downloads": []}

def fake_query(**kw):
    if "fgeIdFromJobId" in kw:
        return cloud["ids"].get(kw["fgeIdFromJobId"], "")
    if "jobStatus" in kw:
        return list(cloud["status"].get(kw["jobStatus"], ("QUEUED", "0")))
    return ""

def fake_submit(download=None, downloadLocation=None, downloadFinishedCallback=None):
    # What Flow Render's download might look like: its own names, in
    # subfolders, with an AOV beside the beauty.
    cloud["downloads"].append((download, downloadLocation, downloadFinishedCallback))
    sub = os.path.join(downloadLocation, "images", "camera1")
    os.makedirs(sub, exist_ok=True)
    for f in cloud["frames"]:
        for name in ("light_001.%04d.exr" % f, "light_001_AO.%04d.exr" % f):
            with open(os.path.join(sub, name), "w") as out:
                out.write("beauty" if "_AO" not in name else "ao")
    import maya.mel
    maya.mel.eval(downloadFinishedCallback)

cmds.flowRenderQuery, cmds.flowRenderSubmit = fake_query, fake_submit
cmds.flowRenderJobMonitor = lambda *a, **k: cloud.setdefault("monitor", True)
flow._modules = lambda: (FakeQueue, FakeSubmitModule)
flow.available = lambda: (True, "")
flow.signed_in = lambda: True
flow.QUERY_EVERY = 0
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
check("renderSub downloads it, not Flow Render's auto-download", fj.autoDownload is False)
check("the uploaded copy has renderSub's frame name and size",
      fj.exported_prefix == info["prefix"] and fj.exported_size == tuple(info["size"]))
check("... and the artist's own render settings are put back",
      cmds.getAttr("defaultRenderGlobals.imageFilePrefix") == "myShot"
      and not cmds.file(q=True, modified=True))
check("still uploading: no cloud id yet", job.poll() is None and "uploading" in job.describe())

cloud["ids"][fj.job_id] = "fge-123"
job.poll()
saved = rs.read_info(info["folder"])
check("the cloud id is saved in render.json once Flow Render gives it",
      saved["flow"]["fge"] == "fge-123" and rs.cloud_job_id(saved) == "fge-123")
check("a cloud render isn't marked interrupted (it carries on with Maya closed)",
      rs.settle(saved)["status"] == rs.RENDERING)
check("... and pruning leaves it alone", rs.prune(ctx, 0) == [] and os.path.isdir(info["folder"]))

cloud["status"]["fge-123"] = ("RUNNING", "66.7")
job.poll()
check("progress from the cloud's percent", job.frames_done() == 2 and "running, 66%" in job.describe())

# Maya closed and opened again: the window picks the job up from render.json.
job = flow.FlowJob(rs.read_info(info["folder"]))
cloud["frames"] = [1001, 1003, 1005]
cloud["status"]["fge-123"] = ("SUCCEEDED", "100")
check("picked up after a restart, it carries on to the end", job.poll() == 0)
download, location, callback = cloud["downloads"][-1]
check("downloaded into the version's flow_download folder",
      download == "fge-123" and os.path.normpath(location) == os.path.join(info["folder"], flow.INCOMING))
done = job.finish()
check("the frames come back under renderSub's names, the beauty not the AOV",
      done["status"] == rs.DONE and all(open(rs.frame_path(info["folder"], info["prefix"], f)).read() == "beauty"
                                        for f in (1001, 1003, 1005)))
check("files renderSub didn't use stay in flow_download, listed in render.json",
      os.path.isdir(os.path.join(info["folder"], flow.INCOMING))
      and len(rs.read_info(info["folder"])["flow"]["unused_downloads"]) == 3)
check("timed as a turnaround and kept apart from local renders",
      done["timing"]["done"] == 3 and rs.read_history(shot_dir)[-1]["where"]["kind"] == rs.CLOUD
      and rs.predict(shot_dir, 3, info["size"], kind=rs.CLOUD) is not None
      and rs.predict(shot_dir, 3, info["size"]) is None)

# --- when it goes wrong ---------------------------------------------------------------
bad = flow.FlowJob.submit(rs.plan_render(ctx, scene, [1001, 1002], cam, how=rs.FLOW))
cloud["ids"][FakeQueue.jobs[-1].job_id] = "fge-bad"
cloud["status"]["fge-bad"] = ("FAILED", "10")
bad.poll()
check("a failed cloud job fails the render, with why",
      bad.poll() == 1 and bad.finish()["status"] == rs.FAILED
      and "failed" in rs.read_info(bad.info["folder"])["flow"]["error"])

early = flow.FlowJob.submit(rs.plan_render(ctx, scene, [1001], cam, how=rs.FLOW))
check("cancel before the upload finishes: Arnold's queue cancels it",
      early.cancel() is None and FakeQueue.cancelled[-1].job_id == early.info["flow"]["local"]
      and early.finish()["status"] == rs.CANCELLED)

late = flow.FlowJob.submit(rs.plan_render(ctx, scene, [1001], cam, how=rs.FLOW))
cloud["ids"][FakeQueue.jobs[-1].job_id] = "fge-late"
late.poll()
note = late.cancel()
check("cancel once it's in the cloud: says to stop it in the Job Monitor, and opens it",
      note and "Job Monitor" in note and cloud.get("monitor"))

lost = flow.FlowJob.submit(rs.plan_render(ctx, scene, [1001], cam, how=rs.FLOW))
FakeQueue.jobs[-1].failed = True
check("the export or upload failing fails the render", lost.poll() == 1)

shutil.rmtree(scratch, ignore_errors=True); shutil.rmtree(h_root, ignore_errors=True)
print("\n%d/%d passed" % (sum(ok), len(ok)))
