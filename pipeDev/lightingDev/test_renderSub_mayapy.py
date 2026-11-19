# renderSub (user, 2026-11-13): renders a shot locally in the background,
# then publishes the frames to H and a movie to ShotGrid. Builds a throwaway
# film folder, really renders a few tiny Arnold frames with Render.exe, and
# publishes to a temp "H drive" with ShotGrid stood in.
# Run: mayapy test_renderSub_mayapy.py
import sys, os, stat, time, glob, shutil, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
for sub in ("", "../publishDev", "../buildDev"):
    sys.path.insert(0, os.path.normpath(os.path.join(HERE, sub)))
import maya.standalone; maya.standalone.initialize()
import maya.cmds as cmds
import publishTool_api as pub
pub.who = lambda: "tester"              # never the machine's settings
import renderSub_api as rs
from publishTool_api import PublishError
ok = []
def check(label, cond): ok.append(bool(cond)); print("PASS" if cond else "FAIL", label)
def refuses(fn, *a, **k):
    try:
        fn(*a, **k)
    except PublishError:
        return True
    return False

# --- frames -----------------------------------------------------------------
cmds.playbackOptions(minTime=1001, maxTime=1010)
check("whole shot = the timeline", rs.frames_for("shot") == list(range(1001, 1011)))
check("custom range", rs.frames_for("custom", 1003, 1005) == [1003, 1004, 1005])
check("lighting check: start, end, middle and halfway each side (SEQ010_140's range)",
      rs.check_frames(1001, 1118) == [1001, 1030, 1060, 1089, 1118])
check("lighting check: evenly spread on any length", rs.check_frames(1001, 1101) == [1001, 1026, 1051, 1076, 1101])
check("lighting check: a shot shorter than 5 frames renders each frame once",
      rs.check_frames(1001, 1003) == [1001, 1002, 1003] and rs.check_frames(1001, 1001) == [1001])
check("lighting check follows the timeline", rs.frames_for("check") == rs.check_frames(1001, 1010))
check("every Nth frame, ending on the end frame",
      rs.frames_for("step", 1001, 1010, 4) == [1001, 1005, 1009, 1010])
check("frame list with ranges, sorted, no repeats",
      rs.frames_for("list", text="1050, 1001 1003-1005 1001") == [1001, 1003, 1004, 1005, 1050])
check("bad frame list refused", refuses(rs.frames_for, "list", text="10a"))
check("end before start refused", refuses(rs.frames_for, "custom", 1010, 1001))
check("-seq string compresses runs", rs.seq_string([1001, 1002, 1003, 1050, 1060, 1061])
      == "1001..1003 1050 1060..1061")

# --- a shot on a temp scratch drive -------------------------------------------
scratch, h_root = tempfile.mkdtemp(prefix="rs_scratch_"), tempfile.mkdtemp(prefix="rs_h_")
shot_dir = os.path.join(scratch, "RST_TST", "maya", "sequences", "SEQ010", "SEQ010_010")
work = os.path.join(shot_dir, "scenes", "lighting", "tester")
os.makedirs(work)
cmds.file(new=True, force=True)
cmds.loadPlugin("mtoa", quiet=True)
cmds.playbackOptions(minTime=1001, maxTime=1005)
cmds.polyCube()
cmds.directionalLight(rotation=(-45, 30, 0))
cam = cmds.camera()[0]
cmds.xform(cam, translation=(4, 3, 6))
cmds.viewPlace(cam, lookAt=(0, 0, 0))
cmds.setAttr("defaultResolution.width", 160)
cmds.setAttr("defaultResolution.height", 90)
check("Arnold's render options made for a scene without them", rs.ensure_arnold()
      and cmds.objExists("defaultArnoldDriver") and not rs.ensure_arnold())
scene = os.path.join(work, "light_001.ma")
cmds.file(rename=scene); cmds.file(save=True, type="mayaAscii")

ctx = rs.shot_of(scene, h_root)
check("renders go to the shot's images\\lighting\\<login>",
      ctx["local"] == os.path.join(shot_dir, "images", "lighting", "tester"))
check("publishes go to the same place on H",
      ctx["h"] == os.path.join(h_root, "RST_TST", "maya", "sequences", "SEQ010", "SEQ010_010",
                               "images", "lighting", "tester"))
check("a scene opened from H is refused", refuses(rs.shot_of, scene, scratch))
check("an unsaved scene is refused", refuses(rs.shot_of, "", h_root))
check("first version is tester_render_v001",
      os.path.basename(rs.next_version(ctx)) == "tester_render_v001")
os.makedirs(os.path.join(ctx["h"], "tester_render_v004"))
check("numbering carries on from H (v004 published -> next is v005)",
      os.path.basename(rs.next_version(ctx)) == "tester_render_v005")
shutil.rmtree(os.path.join(ctx["h"], "tester_render_v004"))
check("the shot camera list skips top/front/side",
      not any(c.split("|")[-1] in ("top", "front", "side") for c in rs.cameras()))
check("half size is even pixels", rs.render_size(50) == (80, 44))
check("department starts from the scene's scenes/<dept> folder",
      rs.department_of(scene) == "lighting"
      and rs.department_of(os.path.join(shot_dir, "scenes", "anim", "tester", "a.ma")) == "anim"
      and rs.department_of(os.path.join(shot_dir, "scenes", "lookdev", "tester", "a.ma")) == "lookDev")
check("a scene outside a department folder starts as Lighting",
      rs.department_of(os.path.join(shot_dir, "scenes", "a.ma")) == "lighting")

# --- a real background render: every 2nd frame -----------------------------
info = rs.plan_render(ctx, scene, rs.frames_for("step", 1001, 1005, 2), cam, percent=100,
                      department="anim")
check("render.json written before rendering", rs.read_info(info["folder"])["status"] == "rendering")
check("the picked department is recorded, not the folder's", info["department"] == "anim")
rs.copy_scene(info)
command = rs.render_command(info)
check("-cam comes before -seq (MtoA's -cam drops an earlier -seq)",
      command.index("-cam") < command.index("-seq"))
check("Render.exe renders the version's own copy of the scene (user, 2026-11-19)",
      command[-1] == os.path.join(info["folder"], "light_001.ma")
      and os.path.isfile(command[-1]) and info["scene"] == os.path.normpath(scene))
job = rs.RenderJob(info)
deadline = time.time() + 600
while job.poll() is None and time.time() < deadline:
    time.sleep(1)
info = job.finish()
print(rs.log_tail(info) if info["status"] != "done" else "")
check("Render.exe rendered frames 1001, 1003, 1005",
      info["status"] == "done" and info["missing"] == [] and
      all(os.path.isfile(rs.frame_path(info["folder"], info["prefix"], f)) for f in (1001, 1003, 1005)))
check("frames named <shot>_<login>_render_v###.####.exr",
      os.path.isfile(os.path.join(info["folder"], "SEQ010_010_tester_render_v001.1003.exr")))
check("progress counts the finished frames", job.frames_done() == 3)
check("only the asked-for frames rendered (no fallback to the scene's range)",
      len(glob.glob(os.path.join(info["folder"], "*.exr"))) == 3)
print("INFO Arnold licence: %s" % ("none, watermarked" if info["watermarked"] else "licensed"))
check("every render gets its own render ID (date, time, shot, random tag)",
      info["render_id"].startswith("R") and "-SEQ010_010-" in info["render_id"])
check("batch render: the render ID is in every frame's EXR header (Render.exe -preRender)",
      all(rs.exr_attribute(rs.frame_path(info["folder"], info["prefix"], f)) == info["render_id"]
          for f in (1001, 1003, 1005)))
check("file names are left as they were (no ID in them)",
      not any(info["render_id"] in n for n in os.listdir(info["folder"])))

# --- render times ------------------------------------------------------------
check("the render records where it ran (this computer)",
      info["where"]["kind"] == rs.LOCAL and info["where"]["machine"])
check("the real render was timed and added to the shot's history",
      info["timing"]["done"] == 3 and len(rs.read_history(shot_dir)) == 1)
fake = {"folder": tempfile.mkdtemp(prefix="rs_time_"), "prefix": "t", "frames": [1, 2, 3, 4, 5],
        "started_ts": 1000.0, "version": "tester_render_v009", "login": "tester",
        "size": [480, 270], "project": shot_dir, "where": {"kind": "local", "machine": "LAB01"}}
check("no frames yet: no timing", rs.timing(fake) is None and rs.time_left(fake) is None)
# File creation times can't be set, so stand them in: frame 1 started at
# 1020 (20 s of loading), and each frame finished 10 s after the last.
real_created = rs._created
rs._created = lambda path: 1020.0
for frame, written in ((1, 1030.0), (2, 1040.0), (3, 1050.0)):
    open(rs.frame_path(fake["folder"], "t", frame), "w").close()
    os.utime(rs.frame_path(fake["folder"], "t", frame), (written, written))
t = rs.timing(fake)
check("render ended: every frame on disk is finished", t["done"] == 3 and rs.frames_done(fake) == 3)
check("seconds per frame from the gaps between finished frames", t["per_frame"] == 10.0)
check("loading time = until the first frame's file was made", t["startup"] == 20.0)
running = rs.timing(fake, running=True)
check("while rendering, the newest file is the frame in progress, not a finished one",
      running["done"] == 2 and rs.frames_done(fake, running=True) == 2)
check("time left = frames to go x seconds per frame", rs.time_left(fake) == 30.0)
os.remove(rs.frame_path(fake["folder"], "t", 3)); os.remove(rs.frame_path(fake["folder"], "t", 2))
one = rs.timing(fake)
check("one finished frame: its own time (last write - created), loading kept apart",
      one["per_frame"] == 10.0 and one["startup"] == 20.0)
check("one frame still rendering: no timing yet", rs.timing(fake, running=True) is None)
for frame, written in ((2, 1040.0), (3, 1050.0)):
    open(rs.frame_path(fake["folder"], "t", frame), "w").close()
    os.utime(rs.frame_path(fake["folder"], "t", frame), (written, written))
rs._created = lambda path: None             # a system that doesn't keep creation times
check("without creation times, loading = first frame minus one frame's time",
      rs.timing(fake)["startup"] == 20.0)
os.remove(rs.history_path(shot_dir))
rs.record_timing(fake)
rs._created = real_created
guess = rs.predict(shot_dir, 10, (1920, 1080), machine="LAB01")
check("predicted from this machine's renders, scaled by pixels (25% -> 100% is 16x)",
      guess["this_machine"] and guess["per_frame"] == 160.0 and guess["total"] == 20.0 + 1600.0)
check("another machine falls back to the shot's local renders, and says so",
      rs.predict(shot_dir, 10, (480, 270), machine="LAB02")["this_machine"] is False)
check("no farm renders yet: no farm estimate",
      rs.predict(shot_dir, 10, (480, 270), kind=rs.FARM) is None)
check("durations read naturally", (rs.duration(42), rs.duration(400), rs.duration(7300))
      == ("42 s", "6 min 40 s", "2 h 1 min"))
check("RV gets each frame of a step render, so they play one after another",
      rs.rv_media(info) == [rs.frame_path(info["folder"], info["prefix"], f) for f in (1001, 1003, 1005)])
check("RV gets one sequence for a gap-free range",
      rs.rv_media(dict(fake, frames=[1, 2, 3])) == [os.path.join(fake["folder"], "t.1-3#.exr")])
check("RV gets nothing when there are no frames", rs.rv_media(dict(fake, frames=[7])) == [])
shutil.rmtree(fake["folder"])
has_rvio = bool(pub.find_rvio())
if has_rvio:
    check("review movie and thumbnail made",
          os.path.isfile(rs.movie_path(info)) and os.path.isfile(rs.thumbnail_path(info)))
else:
    print("SKIP no RV on this machine: movie not checked")

# --- sequence render: in this Maya ------------------------------------------------
# mayapy is a batch session: without an Arnold batch licence Arnold aborts
# here, where a Maya with its UI renders unwatermarked (checked by hand,
# 2026-11-13). Let it render watermarked for the test.
cmds.setAttr("defaultArnoldRenderOptions.abortOnLicenseFail", False)
cmds.setAttr("defaultRenderGlobals.imageFilePrefix", "myShot", type="string")
cam_shape = cmds.listRelatives(cam, shapes=True)[0]
cmds.setAttr(cam_shape + ".renderable", 0)
cmds.file(save=True)
seq_info = rs.plan_render(ctx, scene, [1002, 1004], cam, percent=50, how=rs.SEQUENCE)
calls = []
seq_info = rs.render_in_maya(seq_info, lambda d, n: calls.append((d, n)))
check("sequence render: frames written in this Maya, named like batch frames",
      seq_info["status"] == "done" and all(os.path.isfile(rs.frame_path(seq_info["folder"], seq_info["prefix"], f))
                                            for f in (1002, 1004)))
check("sequence render: no stray files (e.g. MtoA's interactive '_1' names)",
      sorted(n for n in os.listdir(seq_info["folder"]) if n.endswith(".exr"))
      == ["%s.1002.exr" % seq_info["prefix"], "%s.1004.exr" % seq_info["prefix"]])
check("sequence render: progress before each frame and at the end", calls == [(0, 2), (1, 2), (2, 2)])
check("sequence render: the scene's render settings are put back",
      cmds.getAttr("defaultRenderGlobals.imageFilePrefix") == "myShot"
      and cmds.getAttr("defaultResolution.width") == 160 and not cmds.getAttr(cam_shape + ".renderable"))
check("sequence render: the scene isn't left 'unsaved' by the render", not cmds.file(q=True, modified=True))
check("sequence render: the render ID is in the EXR header too",
      rs.exr_attribute(rs.frame_path(seq_info["folder"], seq_info["prefix"], 1002)) == seq_info["render_id"])
check("... and the scene's own driver attributes are left as they were (no ID slot left behind)",
      rs.ID_INDEX not in (cmds.getAttr("defaultArnoldDriver.customAttributes", multiIndices=True) or []))
check("two renders never share an ID", seq_info["render_id"] != info["render_id"])
check("sequence render: recorded as one, for the estimates",
      rs.read_history(shot_dir)[-1]["how"] == rs.SEQUENCE)
stopped = rs.plan_render(ctx, scene, [1001, 1002, 1003], cam, percent=25, how=rs.SEQUENCE)
stopped = rs.render_in_maya(stopped, lambda d, n: d < 1)          # Esc after the first frame
check("sequence render: Esc stops between frames (cancelled, one frame made)",
      stopped["status"] == "cancelled" and len(rs.frame_files(stopped)) == 1)
check("... and that one frame counts as finished (an in-Maya cancel stops between frames)",
      rs.finished_frames(stopped) == [1001] and rs.partial(stopped))
rs.delete_version(stopped["folder"])

# --- publish -------------------------------------------------------------------
class FakeSG(object):
    calls = []
    def upload_playblast(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return {"id": 99}
sg = FakeSG()
lookup = lambda c: ({"type": "Shot", "id": 7, "code": "SEQ010_010"}, {"type": "Task", "id": 3})

import subprocess
def _writable(func, path, _):
    os.chmod(path, stat.S_IWRITE); func(path)

broken = rs.plan_render(ctx, scene, [1001], cam)        # never rendered
check("a render with no finished frames won't publish",
      refuses(rs.publish, ctx, broken["folder"], lookup=lookup, shotgrid=sg))
rs.delete_version(broken["folder"])

# A power cut (user, 2026-11-13): Maya died mid-render, so render.json still
# says rendering, two frames finished and the third is a half-written stub.
cut = rs.plan_render(ctx, scene, [1001, 1002, 1003, 1004], cam)
for f in (1001, 1002):
    shutil.copy2(rs.frame_path(info["folder"], info["prefix"], 1001 if f == 1001 else 1003),
                 rs.frame_path(cut["folder"], cut["prefix"], f))
with open(rs.frame_path(info["folder"], info["prefix"], 1005), "rb") as src, \
        open(rs.frame_path(cut["folder"], cut["prefix"], 1003), "wb") as dst:
    dst.write(src.read(400))                            # the header, nothing more
sleeper = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
rs.write_info(cut["folder"], dict(cut, pid=sleeper.pid))
check("a render whose process is still running is left alone (another Maya, or Render.exe)",
      rs.settle(rs.read_info(cut["folder"]))["status"] == rs.RENDERING
      and refuses(rs.publish, ctx, cut["folder"], lookup=lookup, shotgrid=sg))
sleeper.kill(); sleeper.wait()
gone = rs.settle(rs.read_info(cut["folder"]))
check("once nothing is rendering it, it's marked interrupted",
      gone["status"] == rs.INTERRUPTED and rs.read_info(cut["folder"])["status"] == rs.INTERRUPTED)
check("... the half-written frame doesn't count: two of four finished",
      rs.finished_frames(gone) == [1001, 1002] and gone["missing"] == [1003, 1004] and rs.partial(gone))
check("... RV is shown only the finished frames",
      rs.rv_media(gone) == [os.path.join(gone["folder"], "%s.1001-1002#.exr" % gone["prefix"])])
# 2026-11-20: Render.exe finished every frame overnight with nothing left
# watching it (the queue was lost), so render.json still said rendering.
whole = rs.plan_render(ctx, scene, [1001, 1002], cam)
for f, src in ((1001, 1001), (1002, 1003)):
    shutil.copy2(rs.frame_path(info["folder"], info["prefix"], src), rs.frame_path(whole["folder"], whole["prefix"], f))
ended = subprocess.Popen([sys.executable, "-c", "pass"]); ended.wait()
rs.write_info(whole["folder"], dict(whole, status=rs.RENDERING, how=rs.BATCH, pid=ended.pid))
with open(os.path.join(whole["folder"], rs.LOG_NAME), "w") as f:
    f.write("Scene %s completed.\n" % scene)
check("a batch render that finished unwatched (log says completed, every frame there) is done",
      rs.settle(rs.read_info(whole["folder"]))["status"] == rs.DONE
      and rs.read_info(whole["folder"])["missing"] == [])
half = rs.plan_render(ctx, scene, [1001, 1002], cam)
shutil.copy2(rs.frame_path(info["folder"], info["prefix"], 1001), rs.frame_path(half["folder"], half["prefix"], 1001))
rs.write_info(half["folder"], dict(half, status=rs.RENDERING, how=rs.BATCH, pid=ended.pid))
with open(os.path.join(half["folder"], rs.LOG_NAME), "w") as f:
    f.write("Scene %s completed.\n" % scene)
check("... with a frame missing it's still interrupted",
      rs.settle(rs.read_info(half["folder"]))["status"] == rs.INTERRUPTED)
rs.delete_version(whole["folder"]); rs.delete_version(half["folder"])
check("rendered on another machine: interrupted too (its process can't be checked)",
      rs.settle(dict(cut, status=rs.RENDERING, pid=os.getpid() + 1,
                     where={"kind": "local", "machine": "ELSEWHERE"}), None)["status"] == rs.INTERRUPTED)
rs.write_info(cut["folder"], gone)
if has_rvio:
    calls_before = len(sg.calls)
    part = rs.publish(ctx, cut["folder"], "power went", lookup=lookup, shotgrid=sg)
    names = os.listdir(part["dest"])
    check("an interrupted render publishes its finished frames, with a movie made now",
          part["partial"] and len(sg.calls) == calls_before + 1
          and "%s.1001.exr" % cut["prefix"] in names and "%s.1002.exr" % cut["prefix"] in names
          and "%s.mp4" % cut["prefix"] in names)
    check("... the half-written frame stays on scratch", "%s.1003.exr" % cut["prefix"] not in names)
    check("... the ShotGrid note says it's partial and which frames it has",
          "Partial render (interrupted): 2 of 4 frame(s) finished; 1001..1004 was asked for."
          in sg.calls[-1][1]["notes"] and "2 frame(s) (1001..1002)" in sg.calls[-1][1]["notes"])
    check("... and render.json records the frames published",
          rs.read_info(cut["folder"])["published"]["frames"] == [1001, 1002])
    del sg.calls[calls_before:]
    shutil.rmtree(part["dest"], onerror=_writable)
rs.delete_version(cut["folder"])

if has_rvio:
    result = rs.publish(ctx, info["folder"], "first light", lookup=lookup, shotgrid=sg)
    dest = os.path.join(ctx["h"], "tester_render_v001")
    check("frames, movie, thumbnail and render.json copied to H",
          result["dest"] == dest and all(os.path.isfile(os.path.join(dest, n)) for n in (
              "SEQ010_010_tester_render_v001.1001.exr", "SEQ010_010_tester_render_v001.1005.exr",
              "SEQ010_010_tester_render_v001.mp4", "SEQ010_010_tester_render_v001.thumb.jpg",
              "render.json")))
    check("the render log stays on scratch", not os.path.isfile(os.path.join(dest, rs.LOG_NAME)))
    check("the scene it was rendered from is published with the frames",
          os.path.isfile(os.path.join(dest, "light_001.ma")))
    check("... and the ShotGrid note lists it on H, with the working file's name",
          ("Rendered from (on the H drive):\n%s\nWorking file: light_001.ma"
           % os.path.join(dest, "light_001.ma")) in sg.calls[-1][1]["notes"])
    check("published files are read-only",
          not os.stat(os.path.join(dest, "SEQ010_010_tester_render_v001.1003.exr")).st_mode & stat.S_IWRITE)
    args, kwargs = sg.calls[-1]
    check("ShotGrid Version on the Shot, pointing at the frames on H, on the Lighting task",
          args[:3] == ("Shot", 7, dest) and kwargs["task_id"] == 3
          and kwargs["movie_path"].startswith(dest))
    check("the artist's notes come first in the ShotGrid note",
          kwargs["notes"].startswith("first light\n\n---\nRender tester_render_v001 (render ID %s) from "
                                     "Animation: 3 frame(s)" % info["render_id"]))
    check("marked published locally, with the ShotGrid id",
          rs.read_info(info["folder"])["published"]["sg_version_id"] == 99)
    again = rs.publish(ctx, info["folder"], lookup=lookup, shotgrid=sg)
    check("publishing again (e.g. after a ShotGrid failure) reuses the H copy",
          again["sg_error"] is None and len(sg.calls) == 2)
    no_task = rs.publish(ctx, info["folder"], lookup=lambda c: (lookup(c)[0], None), shotgrid=sg)
    check("no Lighting task: still publishes, with a warning",
          sg.calls[-1][1]["task_id"] is None and any("Lighting task" in w for w in no_task["warnings"]))
    # The render finished after another shot was opened (user, 2026-11-19):
    # it publishes to its own shot, on H and in ShotGrid.
    other_work = os.path.join(scratch, "RST_TST", "maya", "sequences", "SEQ010", "SEQ010_020",
                              "scenes", "lighting", "tester")
    os.makedirs(other_work, exist_ok=True)
    other_ctx = rs.shot_of(os.path.join(other_work, "light_001.ma"), h_root)
    asked_for = []
    moved = rs.publish(other_ctx, info["folder"], shotgrid=sg,
                       lookup=lambda c: asked_for.append(c["shot"]) or lookup(c))
    check("another shot open: still publishes to its own shot's H folder and ShotGrid Shot",
          moved["dest"] == dest and asked_for == ["SEQ010_010"]
          and not os.path.exists(os.path.join(other_ctx["h"], "tester_render_v001")))
    real_root, rs.pub.get_root = rs.pub.get_root, lambda key: h_root   # never the real H
    check("... and with no shot open at all (an unsaved scene)",
          rs.publish(None, info["folder"], lookup=lookup, shotgrid=sg)["dest"] == dest)
    rs.pub.get_root = real_root

stash = tempfile.mkdtemp(prefix="rs_frames_")      # real EXRs for the AOV checks (prune deletes v001)
for f in (1001, 1003, 1005):
    shutil.copy2(rs.frame_path(info["folder"], info["prefix"], f), rs.frame_path(stash, "f", f))

# --- render IDs: the ledger, Find Render and frames found by ID -------------------
ledger = rs.ledger_dir(info)
check("the ledger is on the scratch drive under the film, one file per render",
      ledger == os.path.join(scratch, "RST_TST", "maya", "data", "renderSub", "renders")
      and os.path.isfile(os.path.join(ledger, info["render_id"] + ".json")))
entry = rs.find_render(info["render_id"][:-2], roots=[scratch])
check("Find Render: by ID (or a unique start of one), with its status and frames",
      entry and entry["version"] == info["version"] and entry["status"] == rs.DONE
      and entry["frames_found"] == 3 and entry["published"])
check("Find Render: an ID that matches several renders needs more of it",
      rs.find_render("R", roots=[scratch]) is None)
check("the ledger keeps up with render.json (published, ShotGrid id)",
      entry["published"]["sg_version_id"] == 99)
found_h = rs.find_published(info["render_id"], h_root)
check("Find Render: a published render is found on H too (read only)",
      found_h and found_h["on_h"] and found_h["version"] == info["version"]
      and "Published" in rs.describe_render(entry) and info["render_id"] in rs.describe_render(found_h))
check("the shot's history names the render ID", any(e.get("render_id") == seq_info["render_id"]
                                                     for e in rs.read_history(shot_dir)))
stray = tempfile.mkdtemp(prefix="rs_stray_")
shutil.copy2(rs.frame_path(info["folder"], info["prefix"], 1003), os.path.join(stray, "x.1003.exr"))
shutil.copy2(rs.frame_path(seq_info["folder"], seq_info["prefix"], 1002), os.path.join(stray, "y.1002.exr"))
check("frames are found anywhere by the ID in their header, never another render's",
      rs.frames_with_id(info["render_id"], [stray]) == [os.path.join(stray, "x.1003.exr")])
check("a file that isn't an EXR has no ID", rs.exr_attribute(rs.history_path(shot_dir)) is None)
shutil.rmtree(stray)
check("Render.exe's stamp is MEL for every Arnold driver", "ls -type aiAOVDriver" in rs.id_mel("R1")
      and "customAttributes[%d]" % rs.ID_INDEX in rs.id_mel("R1"))


# --- prune ------------------------------------------------------------------------
for _ in range(3):
    rs.plan_render(ctx, scene, [1001], cam)
lost = rs.prune(ctx, 2)
names = [v["name"] for v in rs.local_versions(ctx)]
# Local now: v001 (batch, published), v002 (sequence), v003-v005 (empty).
check("prune keeps the newest local versions", names == ["tester_render_v005", "tester_render_v004"])
check("prune reports unpublished versions it deleted", "tester_render_v003" in lost
      and "tester_render_v002" in lost and ("tester_render_v001" not in lost if has_rvio else True))

# --- AOVs: Arnold writes each AOV, beauty included, to its own subfolder -----
# (SEQ010_140, 2026-11-16: all 118 frames rendered into beauty\ and the
# denoising AOV folders, and renderSub called it failed.)
aov = rs.plan_render(ctx, scene, [1001, 1002, 1003], cam)
for sub in ("beauty", "N_noice", "Z_noice"):
    os.makedirs(os.path.join(aov["folder"], sub))
    for f, src in ((1001, 1001), (1002, 1003), (1003, 1005)):
        shutil.copy2(rs.frame_path(stash, "f", src),
                     rs.frame_path(os.path.join(aov["folder"], sub), aov["prefix"], f))
aov = rs.finish_render(aov, 0)
check("AOV render: frames found in beauty\\, so it's done, not failed",
      aov["status"] == rs.DONE and aov["missing"] == [] and rs.finished_frames(aov) == [1001, 1002, 1003])
check("AOV render: RV gets the beauty sequence",
      rs.rv_media(aov) == [os.path.join(aov["folder"], "beauty", "%s.1001-1003#.exr" % aov["prefix"])])
check("AOV render: timed from the beauty frames", aov["timing"]["done"] == 3)
os.makedirs(os.path.join(aov["folder"], "flow_download"))
open(os.path.join(aov["folder"], "flow_download", "junk.txt"), "w").close()
if has_rvio:
    check("AOV render: review movie made from the beauty", os.path.isfile(rs.movie_path(aov)))
    aov_pub = rs.publish(ctx, aov["folder"], lookup=lookup, shotgrid=sg)
    d = aov_pub["dest"]
    check("AOV render: every AOV folder's frames published to H",
          all(os.path.isfile(rs.frame_path(os.path.join(d, sub), aov["prefix"], f))
              for sub in ("beauty", "N_noice", "Z_noice") for f in (1001, 1002, 1003))
          and os.path.isfile(os.path.join(d, "%s.mp4" % aov["prefix"])))
    check("AOV render: other subfolders stay on scratch", not os.path.exists(os.path.join(d, "flow_download")))
    check("AOV render: published AOV frames are read-only",
          not os.stat(rs.frame_path(os.path.join(d, "N_noice"), aov["prefix"], 1002)).st_mode & stat.S_IWRITE)
cut_aov = rs.plan_render(ctx, scene, [1001, 1002, 1003], cam)
for sub in ("beauty", "N_noice"):
    os.makedirs(os.path.join(cut_aov["folder"], sub))
    for f in (1001, 1002):
        shutil.copy2(rs.frame_path(stash, "f", 1001),
                     rs.frame_path(os.path.join(cut_aov["folder"], sub), cut_aov["prefix"], f))
    with open(rs.frame_path(os.path.join(cut_aov["folder"], sub), cut_aov["prefix"], 1003), "w") as stub:
        stub.write("x")
cut_aov["status"] = rs.INTERRUPTED
names = rs._published_files(cut_aov)
check("stopped AOV render: half-written last frame left out of every AOV folder",
      os.path.join("N_noice", "%s.1002.exr" % cut_aov["prefix"]) in names
      and not any(n.endswith(".1003.exr") for n in names))

# --- the working file is versioned up on every render (user, 2026-11-19) ---
check("version up: the next number", os.path.basename(rs.version_up_path(
    os.path.join(work, "NFW_SEQ010_170_001.ma"))) == "NFW_SEQ010_170_002.ma")
open(os.path.join(work, "light_007.ma"), "w").close()
check("version up: past any version already in the folder",
      os.path.basename(rs.version_up_path(scene)) == "light_008.ma")
check("version up: a name with no number gets _001",
      os.path.basename(rs.version_up_path(os.path.join(work, "light.mb"))) == "light_001.mb")
cmds.file(scene, open=True, force=True)
saved = rs.save_version_up()
check("save_version_up: saved as the next version and carries on in it",
      saved == os.path.join(work, "light_008.ma") and os.path.isfile(saved)
      and os.path.normpath(cmds.file(q=True, sceneName=True)) == saved
      and os.path.isfile(scene))

# --- the render queue: any shot, batch renders one at a time ----------------
class FakeBatch(object):
    started = []
    def __init__(self, info):
        self.info, self.done, self.cancelled = info, False, False
        FakeBatch.started.append(info["version"])
    def poll(self): return 0 if self.done or self.cancelled else None
    def frames_done(self): return 0
    def cancel(self): self.cancelled = True
    def finish(self): return rs.finish_render(self.info, 0, self.cancelled)
q = rs.RenderQueue(start_batch=FakeBatch)
a = rs.plan_render(ctx, scene, [1001], cam)
b = rs.plan_render(other_ctx if has_rvio else ctx, scene, [1001], cam)
c = rs.plan_render(ctx, scene, [1001], cam)
first = q.add_batch(a)
check("queue: the first batch render starts", first is not None and FakeBatch.started == [a["version"]])
check("queue: the next ones wait, from any shot",
      q.add_batch(b) is None and q.add_batch(c) is None
      and rs.read_info(b["folder"])["status"] == rs.QUEUED and q.place(c["folder"]) == 2)
check("queue: a queued render isn't settled as interrupted while it waits",
      rs.settle(dict(rs.read_info(b["folder"]), folder=b["folder"]), q.folders())["status"] == rs.QUEUED)
# 2026-11-20: another Maya opening the shot marked a render queued in a
# Maya still open as interrupted. Its queue is that Maya's, not this one's.
other_maya = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
check("queue: a render queued in another Maya still open is left alone",
      rs.settle(dict(rs.read_info(b["folder"]), folder=b["folder"], pid=other_maya.pid))["status"] == rs.QUEUED)
other_maya.kill(); other_maya.wait()
check("... once that Maya has closed, it's interrupted",
      rs.settle(dict(rs.read_info(b["folder"]), folder=b["folder"], pid=other_maya.pid))["status"]
      == rs.INTERRUPTED)
rs.write_info(b["folder"], dict(rs.read_info(b["folder"]), status=rs.QUEUED))
# 2026-11-20: a shelf click reloads renderSub_ui (shelf_config RELOAD_ORDER),
# which used to start an empty queue, so the running render was never
# finished and the waiting ones never started.
import importlib
import renderSub_ui as ui
ui._QUEUE.jobs, ui._QUEUE.waiting = list(q.jobs), list(q.waiting)
importlib.reload(rs); importlib.reload(ui)
check("queue: a shelf click (reloading renderSub) keeps the renders running and waiting",
      [j.info["version"] for j in ui._QUEUE.jobs] == [j.info["version"] for j in q.jobs]
      and [i["version"] for i in ui._QUEUE.waiting] == [b["version"], c["version"]]
      and isinstance(ui._QUEUE, rs.RenderQueue))
ui._QUEUE.jobs, ui._QUEUE.waiting = [], []
check("queue: queued and running renders aren't pruned", not any(
    n in rs.prune(ctx, 0, q.folders()) for n in (a["version"], c["version"]))
      and os.path.isdir(a["folder"]) and os.path.isdir(c["folder"]))
check("queue: a queued render won't publish", refuses(rs.publish, ctx, c["folder"], lookup=lookup, shotgrid=sg,
                                                       running=q.folders()))
first.done = True
done = q.step()
check("queue: when one finishes, the next starts",
      [i["version"] for i in done] == [a["version"]] and FakeBatch.started[-1] == b["version"]
      and rs.read_info(b["folder"])["status"] == rs.RENDERING)
q.cancel(c["folder"])
check("queue: a waiting render can be cancelled", not q.waiting
      and rs.read_info(c["folder"])["status"] == rs.CANCELLED)
d = rs.plan_render(ctx, scene, [1001], cam)
q.add_batch(d)
class FakeCloud(object):
    def __init__(self, info, state):
        self.info = dict(info, how=rs.FLOW, flow={"state": state})
    def poll(self): return None
    def frames_done(self): return 0
cloud_up = q.add(FakeCloud(rs.plan_render(ctx, scene, [1001], cam), "in the cloud"))
cloud_uploading = q.add(FakeCloud(rs.plan_render(ctx, scene, [1001], cam), "uploading"))
check("queue: a cloud render doesn't hold up the batch renders", q.batch_running() and q.place(d["folder"]) == 1)
lines = q.stop_for_quit()
check("Maya closing: the batch render is stopped, the waiting one too",
      q.jobs[0].info["version"] == cloud_up.info["version"] and len(q.jobs) == 1 and not q.waiting
      and rs.read_info(b["folder"])["status"] == rs.INTERRUPTED
      and rs.read_info(d["folder"])["status"] == rs.INTERRUPTED
      and rs.read_info(d["folder"])["stopped_why"] == rs.MAYA_CLOSED)
check("... the uploaded cloud render carries on, the one still uploading doesn't",
      cloud_up in q.jobs and cloud_uploading not in q.jobs
      and rs.read_info(cloud_uploading.info["folder"])["status"] == rs.INTERRUPTED)
check("... and says what was stopped, render by render", len(lines) == 3
      and any(b["version"] in l and "no frames had finished" in l for l in lines)
      and any("still uploading" in l for l in lines))
prefs = tempfile.mkdtemp(prefix="rs_prefs_")
rs._jobs_path = lambda: os.path.join(prefs, rs.JOBS_FILE)     # never the real Maya prefs
rs.write_jobs(stopped=lines, cloud=[cloud_up.info["folder"]])
warned = rs.warn_stopped_renders()
check("next Maya: the stopped renders are warned about once, the cloud one remembered",
      warned == lines and rs.read_jobs() == {"stopped": [], "cloud": [cloud_up.info["folder"]]}
      and rs.warn_stopped_renders() == [])
shutil.rmtree(prefs)

old = rs.plan_render(ctx, scene, [1001], cam)
legacy = dict(rs.read_info(old["folder"])); legacy.pop("render_id")
with open(os.path.join(old["folder"], rs.INFO_NAME), "w") as f:
    import json; json.dump(legacy, f)
listed = [v for v in rs.local_versions(ctx) if v["path"] == old["folder"]][0]
check("a version made before render IDs gets one when it's listed (kept after)",
      listed["info"].get("render_id", "").startswith("R")
      and rs.read_info(old["folder"])["render_id"] == listed["info"]["render_id"])

shutil.rmtree(stash); shutil.rmtree(scratch, onerror=_writable); shutil.rmtree(h_root, onerror=_writable)
print("\n%d/%d passed" % (sum(ok), len(ok)))
