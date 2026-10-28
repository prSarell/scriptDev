# Shot animation publish v0 (spec §4 item 6a): what each selected thing is,
# nothing blocked by approval (only caches wait for an approved Final),
# files per stage (Animation / Layout), all or nothing on failure, and the
# camera's stamp. ShotGrid is faked.
# Run: mayapy test_animPublish_mayapy.py
import sys, os, json, glob, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import maya.standalone; maya.standalone.initialize()
import maya.cmds as cmds
import publishTool_api as api
import publishTool_camera as cam
import publishTool_anim as anim

ok = []
def check(label, cond):
    ok.append(bool(cond)); print("PASS" if cond else "FAIL", label)

base = tempfile.mkdtemp(prefix="animpub_")
H, SC = os.path.join(base, "H"), os.path.join(base, "scratch")
shot_rel = ["NWF_SHF", "maya", "sequences", "EAP_010", "EAP_010_010"]
os.makedirs(os.path.join(H, *shot_rel, "scenes"))
os.makedirs(os.path.join(SC, *shot_rel, "scenes"))
api.who = lambda: "scout"
api.artist_name = lambda l: "Test Person"
api.check_rv = lambda: None
api.find_rvio = lambda: None

# A real stamped backpack model publish, plus an old unstamped one.
cmds.polyCube(name="backPack_geo")
model = os.path.join(base, "backpack_scout_model_v008.ma")
api.export_model_to_h_drive([], {"dest": model, "h_folder": base, "ext": ".ma", "asset": "backpack",
                                 "asset_type": "prop", "code": "model", "version": 8, "login": "scout",
                                 "sg_asset": {"id": 1577}}, "work.ma")
cmds.file(new=True, force=True)
cmds.polyCube(name="oldThing")
old = os.path.join(base, "oldprop_model_v001.ma")
cmds.file(rename=old)
cmds.file(save=True, type="mayaAscii")

# The shot scene.
cmds.file(new=True, force=True)
cmds.file(model, reference=True, namespace="backpack")
cmds.file(old, reference=True, namespace="oldprop")
cmds.setKeyframe("backpack:backPack_geo.tx", time=1, value=0)     # the model; the pipe group is locked
cmds.setKeyframe("backpack:backPack_geo.tx", time=10, value=5)
ball = cmds.polySphere(name="ball")[0]
cmds.setKeyframe(ball + ".ty", time=1, value=0)
cmds.setKeyframe(ball + ".ty", time=10, value=3)
cmds.polyCube(name="rock")
cmds.rename(cmds.camera()[0], "camera1")
cmds.playbackOptions(minTime=1, maxTime=10)
scene = os.path.join(SC, *shot_rel, "scenes", "anim_001.ma")
cmds.file(rename=scene)
cmds.file(save=True, type="mayaAscii")
objs = ["backpack:backPack_geo", "ball", "rock"]

# -- what each thing is ---------------------------------------------------
items = anim.classify(objs)
by = dict((i["name"], i) for i in items)
check("geo inside the backpack -> the published backpack model",
      by.get("backpack", {}).get("kind") == "model" and by["backpack"]["stamp"].get("sgAssetId") == 1577)
check("backpack keyed, ball keyed, rock not",
      by["backpack"]["animated"] and by["ball"]["animated"] and not by["rock"]["animated"])
check("ball and rock are made in the shot", by["ball"]["kind"] == by["rock"]["kind"] == "shot")
check("labels read well", by["backpack"]["label"] == "backpack (model v008, keyed)")
for sel, words, label in ((["camera1"], "Camera row", "a camera is refused"),
                          (["oldprop:oldThing"], "before the pipe stamp", "unstamped reference is refused"),
                          ([], "Select what you animated", "nothing selected is refused"),
                          (["gone"], "Not in the scene any more", "a deleted object is refused")):
    try:
        anim.classify(sel)
        check(label, False)
    except api.PublishError as e:
        check(label, words in str(e))

# -- fake ShotGrid --------------------------------------------------------
updates = []


class FakeConn(object):
    def update(self, t, i, data):
        updates.append((t, i, data))


class FakeSG(object):
    def get_connection(self):
        return FakeConn()

    def upload_playblast(self, *a, **k):
        return {"type": "Version", "id": 55}


api._shotgrid = lambda: FakeSG()
cam.find_shotgrid_shot = lambda plan, h: {"type": "Shot", "id": 2560, "code": "EAP_010_010"}
approvals = {}
api.approved_tasks = lambda shot: approvals
TASKS = {"layout": 10, "blocking": 11, "final": 12}
api.task_on = lambda shot, name: {"type": "Task", "id": TASKS[name.lower()], "content": name}
h_scenes = os.path.join(H, *shot_rel, "scenes", "scout")
caches = os.path.join(H, *shot_rel, "cache", "alembic")


def frames_left():
    return glob.glob(os.path.join(SC, *(shot_rel + ["images", "publish", "**", "*.jpg"])), recursive=True)


def listing(folder):
    return sorted(os.listdir(folder)) if os.path.isdir(folder) else []


# -- nothing approved: still publishes (iterative), no caches --------------
plan = anim.publish_anim(scene, H, SC, objs)
names = listing(h_scenes)
check("not approved: publishes anyway, full file + keys/map for keyed items", names == [
    "EAP_010_010_scout_anim_v001.ma",
    "EAP_010_010_scout_backpack_anim_v001.json", "EAP_010_010_scout_backpack_anim_v001.ma",
    "EAP_010_010_scout_ball_anim_v001.json", "EAP_010_010_scout_ball_anim_v001.ma"])
check("not approved: no caches", not listing(caches) and plan["stage"] == "animation")
check("every publish makes a ShotGrid Version", plan["sg_version"] == {"type": "Version", "id": 55})
m = json.load(open(os.path.join(h_scenes, "EAP_010_010_scout_backpack_anim_v001.json")))
check("keys map: names without namespace, stamp and stage recorded",
      list(m["curves"].values()) == [["backPack_geo", "translateX"]]
      and m["asset"]["sgAssetId"] == 1577 and m["namespace"] == "backpack" and m["stage"] == "animation")
text = open(os.path.join(h_scenes, "EAP_010_010_scout_backpack_anim_v001.ma")).read()
check("keys file holds the curve", "animCurveTL" in text and "backpack__backPack_geo_translateX" in text)
check("Animation Version goes on the Final task (for approval)",
      ("Version", 55, {"sg_task": {"type": "Task", "id": 12}}) in updates)
approvals = {"blocking": {"type": "Task", "id": 11}}
plan2 = anim.publish_anim(scene, H, SC, objs)
check("an approved Blocking doesn't trigger caches", not listing(caches) and plan2["stage"] == "animation")
names = listing(h_scenes)
check("scene untouched: no leftover curve copies", not cmds.ls("*__*", type="animCurve"))
check("no frames left on scratch", not frames_left())
check("all published files read-only", all(not os.access(os.path.join(h_scenes, n), os.W_OK) for n in names))

# -- approved Final: also an Alembic per item -----------------------------
approvals = {"blocking": {"type": "Task", "id": 11}, "final": {"type": "Task", "id": 12}}
plan = anim.publish_anim(scene, H, SC, objs)
check("approved Final: the republish is final", plan["stage"] == "final" and plan["version"] == 3)
check("final: one Alembic per item, the static one too", listing(caches) == [
    "EAP_010_010_backpack_anim_v003.abc", "EAP_010_010_ball_anim_v003.abc", "EAP_010_010_rock_anim_v003.abc"])
cmds.file(new=True, force=True)
cmds.loadPlugin("AbcImport", quiet=True)
cmds.AbcImport(os.path.join(caches, "EAP_010_010_ball_anim_v003.abc"), mode="import")
cmds.currentTime(1)
y1 = cmds.exactWorldBoundingBox("ball")[1]
cmds.currentTime(10)
y10 = cmds.exactWorldBoundingBox("ball")[1]
check("ball cache moves 3 units over the shot", abs((y10 - y1) - 3) < 0.05)
cmds.file(scene, open=True, force=True)

# -- a failure part way leaves nothing behind -----------------------------
real = anim.export_cache


def flaky(item, path, s, e):
    if item["name"] == "rock":
        raise RuntimeError("disk full")
    real(item, path, s, e)


anim.export_cache = flaky
before = listing(h_scenes), listing(caches)
try:
    anim.publish_anim(scene, H, SC, objs)
    check("failed publish raised", False)
except RuntimeError:
    check("failed publish raised", True)
check("failed publish: nothing new on the H drive", (listing(h_scenes), listing(caches)) == before)
check("failed publish: no frames left", not frames_left())
anim.export_cache = real

# -- Layout: same as animation, on the Layout task, never caches ----------
approvals = {"final": {"type": "Task", "id": 12}}       # no Layout approval needed
caches_before = listing(caches)
updates[:] = []
plan = anim.publish_anim(scene, H, SC, objs, publish_for=anim.LAYOUT_CODE)
layout_files = [n for n in listing(h_scenes) if "_layout_" in n]
check("Layout publish: own series, full file + keys for keyed items", layout_files == [
    "EAP_010_010_scout_backpack_layout_v001.json", "EAP_010_010_scout_backpack_layout_v001.ma",
    "EAP_010_010_scout_ball_layout_v001.json", "EAP_010_010_scout_ball_layout_v001.ma",
    "EAP_010_010_scout_layout_v001.ma"])
check("Layout publish: no caches, even with Final approved", listing(caches) == caches_before)
check("Layout publish: Version linked to the Layout task",
      ("Version", 55, {"sg_task": {"type": "Task", "id": 10}}) in updates)
try:
    anim.plan_anim(scene, H, SC, publish_for="lighting")
    check("Lighting isn't built yet", False)
except api.PublishError as e:
    check("Lighting isn't built yet", "aren't built yet" in str(e))

# -- cameras aren't blocked either ----------------------------------------
approvals = {}
updates[:] = []
plan = cam.publish_camera(scene, H, SC, camera="camera1")
check("camera publishes with nothing approved, Version on the Layout task",
      os.path.isfile(plan["dest"]) and ("Version", 55, {"sg_task": {"type": "Task", "id": 10}}) in updates)

# -- a camera published from Animation says so ----------------------------
plan = cam.publish_camera(scene, H, SC, camera="camera1", publish_for=anim.ANIM_CODE)
m = json.load(open(plan["map_dest"]))
check("camera map records it came from animation", m["published_from"] == "anim")
cmds.file(new=True, force=True)
cmds.file(plan["dest"], open=True, force=True)
grp = cam.camera_group_name(plan["shot"])      # the stamp is on the camera group (2026-10-20)
stamp = dict((a, cmds.getAttr(grp + "." + a)) for a in cmds.listAttr(grp, userDefined=True) or [])
print("   camera stamp:", stamp)
check("published camera carries the pipe stamp, from animation",
      stamp.get("pipe_publishedFrom") == "anim" and stamp.get("pipe_sgShotId") == 2560
      and stamp.get("pipe_department") == "cam" and stamp.get("pipe_version") == plan["version"])
check("camera stamp locked", cmds.getAttr(grp + ".pipe_publishedFrom", lock=True))

# -- camera + animation from one scene: one movie, one Version (2026-10-28) --
cmds.file(scene, open=True, force=True)
uploads, blasts = [], []
FakeSG.upload_playblast = lambda self, *a, **k: uploads.append(k) or {"type": "Version", "id": 56}
real_blast = api.playblast_frames
api.playblast_frames = lambda plan, n, objects=None, camera=None: (
    blasts.append(camera) or real_blast(plan, n, objects=objects, camera=camera))
cam_before = len(cam.published_camera_versions(h_scenes, "EAP_010_010", "scout"))
plan = anim.publish_anim(scene, H, SC, objs, camera="camera1")
cp = plan["camera_plan"]
check("camera + anim: one playblast, through the camera, one Version",
      len(blasts) == 1 and blasts[0].split("|")[-1] == "camera1" and len(uploads) == 1
      and plan["sg_version"] == {"type": "Version", "id": 56})
check("camera + anim: the camera's own files, next camera version",
      cp["version"] == cam_before + 1
      and all(os.path.isfile(cp[k]) for k in ("dest", "keys_dest", "map_dest"))
      and cp["dest"] in plan["written"])
check("camera + anim: the anim files too", any(n.endswith("_ball_anim_v%03d.ma" % plan["version"])
                                               for n in listing(h_scenes)))
check("camera + anim: the Version's notes list the camera",
      "Camera v%03d" % cp["version"] in (uploads[0].get("notes") or str(uploads[0])))
real_write = anim.write_anim
def broken(*a):
    raise RuntimeError("disk full")
anim.write_anim = broken
before = listing(h_scenes)
try:
    anim.publish_anim(scene, H, SC, objs, camera="camera1")
    check("camera + anim failure raised", False)
except RuntimeError:
    check("camera + anim failure: nothing new on H, camera files too", listing(h_scenes) == before)
anim.write_anim = real_write
api.playblast_frames = real_blast
print("%d/%d passed" % (sum(ok), len(ok)))
