# Scout (user, 2026-11-20): the render service owns the batch queue; pause,
# resume, kill and restart; the window lists a project's renders. Builds a
# throwaway film folder, drives the service with stand-in renders (a Python
# process writing frames), then hands one real Render.exe render to a real
# service process, as renderSub does.
# Run: mayapy test_scout_mayapy.py
import sys, os, time, json, shutil, tempfile, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
PATHS = [os.path.normpath(os.path.join(HERE, sub)) for sub in
         ("", "../lightingDev", "../publishDev", "../buildDev")]
sys.path[:0] = PATHS
# The services and windows this test starts find the same modules, and keep
# their state in a throwaway Scout home, never the machine's.
os.environ["PYTHONPATH"] = os.pathsep.join(PATHS + [os.environ.get("PYTHONPATH", "")])
os.environ["SCOUT_HOME"] = tempfile.mkdtemp(prefix="scout_home_")
os.environ["QT_QPA_PLATFORM"] = "offscreen"
import maya.standalone; maya.standalone.initialize()
import maya.cmds as cmds
import publishTool_api as pub
pub.who = lambda: "tester"
import renderSub_api as rs
import scout_api as api
import scout_service
ok = []
def check(label, cond): ok.append(bool(cond)); print("PASS" if cond else "FAIL", label)
def wait_for(cond, timeout=20.0, step=None):
    end = time.time() + timeout
    while time.time() < end:
        if step:
            step()
        if cond():
            return True
        time.sleep(0.1)
    return cond()

# --- pause, resume and kill a process and the one it started -----------------
ticks = os.path.join(os.environ["SCOUT_HOME"], "ticks.txt")
child_py = os.path.join(os.environ["SCOUT_HOME"], "child.py")
parent_py = os.path.join(os.environ["SCOUT_HOME"], "parent.py")
with open(child_py, "w") as f:
    f.write("import sys, time\nwhile True:\n"
            "    open(sys.argv[1], 'a').write('x'); time.sleep(0.05)\n")
with open(parent_py, "w") as f:
    f.write("import sys, subprocess\n"
            "subprocess.Popen([sys.executable, sys.argv[1], sys.argv[2]]).wait()\n")
parent = subprocess.Popen([sys.executable, parent_py, child_py, ticks])
check("process tree: the child is found", wait_for(lambda: len(api.process_tree(parent.pid)) == 2, 10))
wait_for(lambda: os.path.isfile(ticks), 10)
api.pause_process(parent.pid)
time.sleep(0.3); before = os.path.getsize(ticks); time.sleep(0.8)
check("pause: the child stops working too", os.path.getsize(ticks) == before)
api.resume_process(parent.pid)
check("resume: it carries on", wait_for(lambda: os.path.getsize(ticks) > before, 5))
child = api.process_tree(parent.pid)[1]
api.pause_process(parent.pid)
api.kill_process(parent.pid)
check("kill (even paused): the whole tree stops",
      wait_for(lambda: not api.alive(parent.pid) and not api.alive(child), 10))

# --- a shot on a temp scratch drive --------------------------------------------
scratch, h_root = tempfile.mkdtemp(prefix="scout_scratch_"), tempfile.mkdtemp(prefix="scout_h_")
shot_dir = os.path.join(scratch, "SCT_TST", "maya", "sequences", "SEQ010", "SEQ010_010")
work = os.path.join(shot_dir, "scenes", "lighting", "tester")
os.makedirs(work)
cmds.file(new=True, force=True)
cmds.loadPlugin("mtoa", quiet=True)
cmds.playbackOptions(minTime=1001, maxTime=1003)
cmds.polyCube()
cmds.directionalLight(rotation=(-45, 30, 0))
cam = cmds.camera()[0]
cmds.xform(cam, translation=(4, 3, 6))
cmds.viewPlace(cam, lookAt=(0, 0, 0))
cmds.setAttr("defaultResolution.width", 160)
cmds.setAttr("defaultResolution.height", 90)
rs.ensure_arnold()
scene = os.path.join(work, "light_001.ma")
cmds.file(rename=scene); cmds.file(save=True, type="mayaAscii")
ctx = rs.shot_of(scene, h_root)
film = os.path.join(scratch, "SCT_TST")

# --- the service, with stand-in renders ----------------------------------------
WRITER = ("import sys, time\n"
          "folder, prefix, frames, delay = sys.argv[1], sys.argv[2], sys.argv[3].split(','), float(sys.argv[4])\n"
          "for f in frames:\n"
          "    time.sleep(delay)\n"
          "    open('%s/%s.%04d.exr' % (folder, prefix, int(f)), 'wb').write(b'x' * 1000)\n"
          "open(folder + '/render.log', 'a').write('Scene x.ma completed.\\n')\n")   # as Render.exe's


class FakeJob(object):
    """Like renderSub's RenderJob, but a Python process writes the frames."""
    delay = 0.4
    def __init__(self, info):
        self.info, self.cancelled = info, False
        frames = info.get("render_frames") or info["frames"]
        self.process = subprocess.Popen([sys.executable, "-c", WRITER, info["folder"], info["prefix"],
                                         ",".join(str(f) for f in frames), str(FakeJob.delay)])
        info["pid"] = self.process.pid
        rs.write_info(info["folder"], info)
    def poll(self): return self.process.poll()
    def cancel(self):
        self.cancelled = True
        api.kill_process(self.process.pid)
        self.process.wait()
    def finish(self): return rs.finish_render(self.info, self.process.returncode, self.cancelled)


svc = scout_service.Service("test", job_class=FakeJob, idle_exit=3600)
step = svc.step
status = lambda i: rs.read_info(i["folder"])["status"]
done = lambda i: len(rs.frame_files(dict(rs.read_info(i["folder"]), folder=i["folder"])))
a = rs.plan_render(ctx, scene, list(range(1001, 1007)), cam)
b = rs.plan_render(ctx, scene, [1001, 1002], cam)
api.send("test", api.SUBMIT, a["folder"], start=False)
api.send("test", api.SUBMIT, b["folder"], start=False)
step()
check("submit: the first renders, the second waits in the service's queue",
      status(a) == rs.RENDERING and status(b) == rs.QUEUED
      and rs.read_info(b["folder"])["pid"] == os.getpid()
      and api.read_queue("test")["waiting"] == [b["folder"]])
# (renderSub leaving a render queued in a live process alone is tested in
# test_renderSub_mayapy; here the service shares this process's pid.)
check("the window offers Pause and Kill for the running one, Kill for the waiting one",
      api.actions(dict(rs.read_info(a["folder"]), folder=a["folder"])) == [api.PAUSE, api.KILL]
      and api.actions(dict(rs.read_info(b["folder"]), folder=b["folder"])) == [api.KILL])
wait_for(lambda: done(a) >= 1, 10, step)
api.send("test", api.PAUSE, a["folder"], start=False); step()
paused_at = done(a); time.sleep(1.2); step()
check("pause: status paused and no more frames while paused",
      status(a) == rs.PAUSED and done(a) == paused_at and paused_at < 6)
check("... a paused render can't be published", api.actions(
    dict(rs.read_info(a["folder"]), folder=a["folder"]))[:2] == [api.RESUME, api.KILL]
      and api.PUBLISH not in api.actions(dict(rs.read_info(a["folder"]), folder=a["folder"])))
api.send("test", api.RESUME, a["folder"], start=False); step()
check("resume: rendering again and frames carry on",
      status(a) == rs.RENDERING and wait_for(lambda: done(a) > paused_at, 5, step)
      and rs.read_info(a["folder"]).get("paused_s", 0) >= 1.0)
api.send("test", api.KILL, a["folder"], start=False)
check("kill: cancelled, with the frames that finished kept",
      wait_for(lambda: status(a) == rs.CANCELLED, 10, step) and 0 < done(a) < 6)
check("... and the waiting one starts", wait_for(lambda: status(b) == rs.RENDERING, 5, step))
killed_with = done(a)
check("the window offers Restart, RV and Publish for the killed one",
      api.actions(dict(rs.read_info(a["folder"]), folder=a["folder"])) == [api.RESTART, api.RV, api.PUBLISH])
api.send("test", api.RESTART, a["folder"], start=False); step()
info_a = rs.read_info(a["folder"])
check("restart: queued again for just the frames still missing",
      info_a["status"] == rs.QUEUED and info_a["render_frames"] == list(range(1001 + killed_with, 1007))
      and info_a["restarts"] == 1)
check("... it waits for the render already running, then finishes every frame",
      wait_for(lambda: status(b) == rs.DONE and status(a) == rs.DONE, 20, step)
      and done(a) == 6 and "render_frames" not in rs.read_info(a["folder"]))

c = rs.plan_render(ctx, scene, [1001, 1002, 1003], cam)
d = rs.plan_render(ctx, scene, [1001], cam)
api.send("test", api.SUBMIT, c["folder"], start=False)
api.send("test", api.SUBMIT, d["folder"], start=False)
step()
api.send("test", api.KILL, d["folder"], start=False); step()
check("kill a waiting render: taken out of the queue, cancelled",
      status(d) == rs.CANCELLED and not svc.waiting)

# The service stops (a crash, a restart) while c renders: the next one
# carries on watching its Render.exe, and keeps the queue.
e = rs.plan_render(ctx, scene, [1001], cam)
api.send("test", api.SUBMIT, e["folder"], start=False); step()
running_pid = rs.read_info(c["folder"])["pid"]
svc2 = scout_service.Service("test", job_class=FakeJob, idle_exit=3600)
check("a new service picks the queue up: watches the running render, keeps the waiting one",
      isinstance(svc2.job, scout_service.AdoptedJob) and svc2.job.pid == running_pid
      and svc2.waiting == [e["folder"]])
svc.job = None; svc.waiting = []           # the old one is gone
check("... and finishes both", wait_for(lambda: status(c) == rs.DONE and status(e) == rs.DONE,
                                        20, svc2.step))
svc3 = scout_service.Service("test", job_class=FakeJob, idle_exit=0)
svc3.step()
check("with nothing to do, the service quits (idle)", svc3.quit)

# --- the window's view of a project --------------------------------------------
check("projects: the film folder is found from a scratch root",
      any(rs._same(p, film) for p in api.find_projects([scratch])))
rows = api.project_renders(film)
by_version = dict((r["version"], r) for r in rows)
check("project renders: every render, newest first, with how it stands",
      [r["render_id"] for r in rows] == sorted([r["render_id"] for r in rows], reverse=True)
      and by_version[a["version"]]["status"] == rs.DONE and by_version[a["version"]]["frames_done"] == 6
      and by_version[d["version"]]["status"] == rs.CANCELLED)
check("a done render offers RV and Publish, nothing to control",
      by_version[a["version"]]["actions"] == [api.RV, api.PUBLISH])
check("a render from another machine can't be controlled from here",
      not api.controllable(dict(rs.read_info(a["folder"]), where={"kind": "local", "machine": "ELSEWHERE"})))
shutil.rmtree(b["folder"])
check("a render deleted from scratch still lists, with nothing to do",
      [r for r in api.project_renders(film) if r["version"] == b["version"]][0]["actions"] == []
      and api.describe([r for r in api.project_renders(film) if r["version"] == b["version"]][0])
      == "deleted from scratch")

# A render from before render IDs: in the shot's folder, not in the ledger.
old = rs.plan_render(ctx, scene, [1001], cam)
legacy = rs.read_info(old["folder"]); legacy_id = legacy.pop("render_id")
os.remove(os.path.join(rs.ledger_dir(legacy), legacy_id + ".json"))
with open(os.path.join(old["folder"], rs.INFO_NAME), "w") as f:
    json.dump(legacy, f)
found = [r for r in api.project_renders(film) if rs._same(r["folder"], old["folder"])]
check("a render from before render IDs is found in its shot, and given an ID",
      len(found) == 1 and found[0]["render_id"] and rs.read_info(old["folder"])["render_id"]
      == found[0]["render_id"] and os.path.isfile(os.path.join(rs.ledger_dir(legacy),
                                                               found[0]["render_id"] + ".json")))
# A batch render that finished with nothing watching it (SEQ010_170 v007).
gone = subprocess.Popen([sys.executable, "-c", "pass"]); gone.wait()
lost = rs.plan_render(ctx, scene, [1001], cam)
open(rs.frame_path(lost["folder"], lost["prefix"], 1001), "wb").write(b"x" * 1000)
with open(os.path.join(lost["folder"], rs.LOG_NAME), "w") as f:
    f.write("Scene %s completed.\n" % scene)
rs.write_info(lost["folder"], dict(lost, pid=gone.pid))
row = [r for r in api.project_renders(film) if rs._same(r["folder"], lost["folder"])][0]
check("a render nothing runs any more is stale; settling it records it done",
      api.stale(row) and api.settle_row(row)["status"] == rs.DONE
      and not api.stale([r for r in api.project_renders(film) if rs._same(r["folder"], lost["folder"])][0]))
check("a render queued in a live service isn't stale",
      not api.stale(dict(row, info=dict(row["info"], status=rs.QUEUED, pid=os.getpid()))))

# The window runs in plain mayapy, as Scout does (Maya's standalone makes a
# Qt application that can't show widgets).
api.write_settings({"projects": [film], "project": film, "filter": "all"})
window_py = os.path.join(os.environ["SCOUT_HOME"], "window_check.py")
with open(window_py, "w") as f:
    f.write("""import sys, json
from PySide6 import QtWidgets
import scout_ui, scout_api as api
app = QtWidgets.QApplication([])
win = scout_ui.ScoutWindow()
out = {"project": win.project.currentData(), "rows": win.table.rowCount()}
win.search.setText(sys.argv[1])
win.table.selectRow(0)
out.update(found=win.table.rowCount(), details=win.details.toPlainText(),
           enabled=[a for a, _, _ in scout_ui.BUTTONS if win.buttons[a].isEnabled()])
win.timer.stop()
print("RESULT " + json.dumps(out))
""")
env = dict(os.environ, MAYA_SKIP_USERSETUP_PY="1")
shown = subprocess.run([sys.executable, window_py, a["render_id"]], capture_output=True, text=True,
                       env=env, timeout=300).stdout
import json
shown = json.loads(([l[7:] for l in shown.splitlines() if l.startswith("RESULT ")] or ["{}"])[0])
check("window: opens on the project and lists its renders",
      rs._same(shown.get("project") or "", film) and shown.get("rows") == len(api.project_renders(film)))
check("window: find by render ID; a done render's buttons are RV and Publish",
      shown.get("found") == 1 and shown.get("enabled") == [api.RV, api.PUBLISH]
      and a["render_id"] in shown.get("details", ""))

# --- publish runs in its own mayapy, and refuses what it should ----------------
empty = tempfile.mkdtemp(prefix="scout_nothing_")
proc, result = api.start_worker(cmds.about(version=True), api.PUBLISH, empty, "notes")
proc.wait(timeout=300)
out = api.read_result(result) or {}
check("worker: a folder that isn't a render is refused, with the reason",
      out.get("ok") is False and "render.json" in out.get("message", ""))

# --- renderSub hands a real render to a real service ---------------------------
real = rs.plan_render(ctx, scene, [1001, 1002], cam)
rs.copy_scene(real)
job = api.ScoutJob.submit(real)
check("renderSub's hand-over: queued in Scout, and the service starts",
      rs.read_info(real["folder"])["scout"]["maya"] == cmds.about(version=True)
      and wait_for(lambda: api.service_state(cmds.about(version=True)) is not None, 120))
check("... it renders with Render.exe and finishes; renderSub's job sees it end",
      wait_for(lambda: job.poll() is not None, 400) and job.finish()["status"] == rs.DONE
      and len(rs.finished_frames(dict(rs.read_info(real["folder"]), folder=real["folder"]))) == 2)
check("... the frames carry the render ID",
      rs.exr_attribute(rs.beauty_path(dict(rs.read_info(real["folder"]), folder=real["folder"]), 1001))
      == real["render_id"])
check("... and Maya closing doesn't stop it (renderSub leaves it to Scout)",
      job.carries_on)
pid = api.service_state(cmds.about(version=True))["pid"]
api.send(cmds.about(version=True), api.QUIT, start=False)
check("quit: the service stops", wait_for(lambda: not api.alive(pid), 30))

shutil.rmtree(scratch, ignore_errors=True); shutil.rmtree(h_root, ignore_errors=True)
shutil.rmtree(os.environ["SCOUT_HOME"], ignore_errors=True)
print("%d/%d passed" % (sum(ok), len(ok)))
