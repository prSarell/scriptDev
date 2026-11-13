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

# --- a real background render: every 2nd frame -----------------------------
info = rs.plan_render(ctx, scene, rs.frames_for("step", 1001, 1005, 2), cam, percent=100)
check("render.json written before rendering", rs.read_info(info["folder"])["status"] == "rendering")
command = rs.render_command(info)
check("-cam comes before -seq (MtoA's -cam drops an earlier -seq)",
      command.index("-cam") < command.index("-seq"))
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
check("sequence render: recorded as one, for the estimates",
      rs.read_history(shot_dir)[-1]["how"] == rs.SEQUENCE)
stopped = rs.plan_render(ctx, scene, [1001, 1002, 1003], cam, percent=25, how=rs.SEQUENCE)
stopped = rs.render_in_maya(stopped, lambda d, n: d < 1)          # Esc after the first frame
check("sequence render: Esc stops between frames (cancelled, one frame made)",
      stopped["status"] == "cancelled" and len(rs.frame_files(stopped)) == 1)
rs.delete_version(stopped["folder"])

# --- publish -------------------------------------------------------------------
class FakeSG(object):
    calls = []
    def upload_playblast(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return {"id": 99}
sg = FakeSG()
lookup = lambda c: ({"type": "Shot", "id": 7, "code": "SEQ010_010"}, {"type": "Task", "id": 3})

broken = rs.plan_render(ctx, scene, [1001], cam)        # never rendered
check("an unfinished render won't publish",
      refuses(rs.publish, ctx, broken["folder"], lookup=lookup, shotgrid=sg))
rs.delete_version(broken["folder"])

if has_rvio:
    result = rs.publish(ctx, info["folder"], "first light", lookup=lookup, shotgrid=sg)
    dest = os.path.join(ctx["h"], "tester_render_v001")
    check("frames, movie, thumbnail and render.json copied to H",
          result["dest"] == dest and all(os.path.isfile(os.path.join(dest, n)) for n in (
              "SEQ010_010_tester_render_v001.1001.exr", "SEQ010_010_tester_render_v001.1005.exr",
              "SEQ010_010_tester_render_v001.mp4", "SEQ010_010_tester_render_v001.thumb.jpg",
              "render.json")))
    check("the render log stays on scratch", not os.path.isfile(os.path.join(dest, rs.LOG_NAME)))
    check("published files are read-only",
          not os.stat(os.path.join(dest, "SEQ010_010_tester_render_v001.1003.exr")).st_mode & stat.S_IWRITE)
    args, kwargs = sg.calls[-1]
    check("ShotGrid Version on the Shot, pointing at the frames on H, on the Lighting task",
          args[:3] == ("Shot", 7, dest) and kwargs["task_id"] == 3
          and kwargs["movie_path"].startswith(dest))
    check("the artist's notes come first in the ShotGrid note",
          kwargs["notes"].startswith("first light\n\n---\nRender tester_render_v001: 3 frame(s)"))
    check("marked published locally, with the ShotGrid id",
          rs.read_info(info["folder"])["published"]["sg_version_id"] == 99)
    again = rs.publish(ctx, info["folder"], lookup=lookup, shotgrid=sg)
    check("publishing again (e.g. after a ShotGrid failure) reuses the H copy",
          again["sg_error"] is None and len(sg.calls) == 2)
    no_task = rs.publish(ctx, info["folder"], lookup=lambda c: (lookup(c)[0], None), shotgrid=sg)
    check("no Lighting task: still publishes, with a warning",
          sg.calls[-1][1]["task_id"] is None and any("Lighting task" in w for w in no_task["warnings"]))

# --- prune ------------------------------------------------------------------------
for _ in range(3):
    rs.plan_render(ctx, scene, [1001], cam)
lost = rs.prune(ctx, 2)
names = [v["name"] for v in rs.local_versions(ctx)]
# Local now: v001 (batch, published), v002 (sequence), v003-v005 (empty).
check("prune keeps the newest local versions", names == ["tester_render_v005", "tester_render_v004"])
check("prune reports unpublished versions it deleted", "tester_render_v003" in lost
      and "tester_render_v002" in lost and ("tester_render_v001" not in lost if has_rvio else True))

def _writable(func, path, _):
    os.chmod(path, stat.S_IWRITE); func(path)
shutil.rmtree(scratch, onerror=_writable); shutil.rmtree(h_root, onerror=_writable)
print("\n%d/%d passed" % (sum(ok), len(ok)))
