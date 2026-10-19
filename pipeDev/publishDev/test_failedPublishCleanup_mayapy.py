# A publish that fails after the playblast leaves no frames on scratch
# (playblast cancelled, H-drive write failed; asset and camera publishes).
# Run: mayapy test_failedPublishCleanup_mayapy.py
import sys, os, glob, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import maya.standalone; maya.standalone.initialize()
import maya.cmds as cmds
import publishTool_api as api
import publishTool_camera as cam

ok = []
def check(label, cond):
    ok.append(bool(cond)); print("PASS" if cond else "FAIL", label)

project = os.path.join(tempfile.mkdtemp(prefix="pubclean_"), "backpack")
os.makedirs(os.path.join(project, "images"))
cmds.polyCube()
plan = {"asset_project": project, "shot_project": project, "asset": "backpack", "code": "model",
        "version": 7, "login": "scout", "film": "NWF_SHF", "asset_type": "prop"}
publish_root = os.path.join(project, "images", "publish")

def leftovers():
    return glob.glob(os.path.join(publish_root, "**", "*.jpg"), recursive=True)

# 1. A playblast that works leaves its frames (until the upload).
folder, files = api.playblast_frames(dict(plan), 2)
check("playblast makes frames", len(files) == 2)
api.remove_frames(folder, project)

# 2. A playblast that fails half way leaves nothing.
real_playblast = cmds.playblast
def half_then_fail(**kw):
    real_playblast(**dict(kw, endTime=kw["startTime"]))
    raise RuntimeError("cancelled")
cmds.playblast = half_then_fail
try:
    api.playblast_frames(dict(plan), 3)
except RuntimeError:
    pass
cmds.playblast = real_playblast
check("cancelled playblast: no frames left", not leftovers())
check("... and no empty publish folders", not os.path.exists(publish_root))
check("... images folder itself kept", os.path.isdir(os.path.join(project, "images")))

# 3. Asset publish: H-drive write fails after the playblast.
api.plan_publish = lambda *a, **k: dict(plan)
api.find_shotgrid_asset = lambda p, h: {"id": 1}
api.check_rv = lambda: None
def fail(*a, **k):
    raise api.PublishError("H drive full")
api.export_model_to_h_drive = fail
try:
    api.publish("x.ma", "H", "S", "model")
    check("asset publish failure raised", False)
except api.PublishError as e:
    check("asset publish failure raised", "H drive full" in str(e))
check("asset publish failure: no frames left", not leftovers() and not os.path.exists(publish_root))

# 4. Camera publish: H-drive write fails after the playblast.
cam.check_camera = lambda objs: objs[0]
cam.plan_camera = lambda *a, **k: dict(plan, code="cam")
cam.find_shotgrid_shot = lambda p, h: {"id": 1}
cam.export_camera = fail
try:
    cam.publish_camera("x.ma", "H", "S", camera="persp")
    check("camera publish failure raised", False)
except api.PublishError:
    check("camera publish failure raised", True)
check("camera publish failure: no frames left", not leftovers() and not os.path.exists(publish_root))

print("%d/%d passed" % (sum(ok), len(ok)))
