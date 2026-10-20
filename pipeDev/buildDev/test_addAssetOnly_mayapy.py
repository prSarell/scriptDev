# Adding one asset to a scene that already has the shot's assets builds
# ONLY the new one (user, 2026-10-20: adding scoutsHouse also rebuilt the
# camera, renamed the existing camera1 and maybe touched the backpack).
# Reproduces it: another scene in the same shot moved the manifest's camera
# to v002 while this scene still has v001. Runs the real Build tab offscreen.
# Run: mayapy test_addAssetOnly_mayapy.py
import sys, os, stat, shutil, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), "publishDev")]
from PySide6 import QtWidgets
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
import maya.standalone; maya.standalone.initialize()
import maya.cmds as cmds
import buildTool_api as api
import buildTool_ui as ui
import publishTool_camera as pcam
import pipeEnv

ok = []
def check(label, cond):
    ok.append(bool(cond)); print("PASS" if cond else "FAIL", label)

base = tempfile.mkdtemp(prefix="addonly_")
H, SC = os.path.join(base, "H"), os.path.join(base, "scratch")
FILM = "NWF_SHF"
_cfg = os.path.join(base, "pipeline_config.json")
api.pub._config_path = lambda: _cfg
api.pub.set_root(api.pub.H_DRIVE, H)
api.pub.set_root(api.pub.SCRATCH, SC)
api.pub.save_config(dict(api.pub.load_config(), publish_as="scout"))
os.environ.pop(pipeEnv.VAR, None)

# H drive: backpack and scoutsHouse models.
for asset_type, asset in (("prop", "backpack"), ("environment", "scoutsHouse")):
    d = os.path.join(H, FILM, "maya", "assets", asset_type, asset, "scenes", "scout")
    os.makedirs(d)
    cmds.file(new=True, force=True)
    cmds.polyCube(name=asset + "_geo")
    cmds.file(rename=os.path.join(d, "%s_scout_model_v001.ma" % asset))
    cmds.file(save=True, type="mayaAscii")
shot = api.shot_folder(SC, FILM, "EAP_010", "EAP_010_010")
os.makedirs(os.path.join(shot, "scenes"))
open(os.path.join(shot, "workspace.mel"), "w").write("")
os.makedirs(os.path.join(api.shot_folder(H, FILM, "EAP_010", "EAP_010_010"), "scenes"))

# Two camera publishes, v001 then v002.
layout = os.path.join(shot, "scenes", "layout.ma")
for v in (1, 2):
    cmds.file(new=True, force=True)
    cam = cmds.camera(name="layoutCam")[0]
    cmds.setKeyframe(cam + ".tx", time=1, value=0); cmds.setKeyframe(cam + ".tx", time=10, value=v)
    cmds.file(rename=layout); cmds.file(save=True, type="mayaAscii")
    pcam.export_camera(cam, pcam.plan_camera(layout, H, SC, camera=cam), 1, 10, layout)


def published(asset):
    return [p for p in api.list_published(H, FILM) + api.list_shot_cameras(H, FILM, "EAP_010", "EAP_010_010")
            if p["asset"] == asset][0]


C1, C2 = api.version_id("scout", 1), api.version_id("scout", 2)

# Scene A: camera v001 + backpack, keyed, saved.
cmds.file(new=True, force=True)
api.ensure_maya_project(shot)
api.build_asset(shot, published("EAP_010_010"), C1)
api.build_asset(shot, published("backpack"), "scout/v001")
cmds.setKeyframe("backpack:backpack_geo.tx", time=1, value=0)
cmds.setKeyframe("backpack:backpack_geo.tx", time=10, value=4)
scene_a = os.path.join(shot, "scenes", "anim_A.ma")
cmds.file(rename=scene_a); cmds.file(save=True, type="mayaAscii")

# Scene B in the same shot builds camera v002: the shot's manifest now says v002.
cmds.file(new=True, force=True)
api.build_asset(shot, published("EAP_010_010"), C2)
check("setup: manifest camera is v002", api.entry_version_id(
    api.read_manifest(shot)["camera/EAP_010_010/cam"]) == C2)

# Back in scene A: open Build Shot, add scoutsHouse, Build.
cmds.file(scene_a, open=True, force=True)
parent = QtWidgets.QWidget()
tab = ui.BuildShotTab(lambda: (H, SC), parent)
tab.refresh()
tab.shot_combo.setCurrentIndex(tab.shot_combo.findData("EAP_010/EAP_010_010"))
rows = dict((r["asset"], r) for r in tab._rows)
check("camera row starts at what the scene has (v001), not the manifest's v002",
      rows["EAP_010_010"]["chosen"] == C1 and rows["EAP_010_010"]["in_scene"] == C1)
tab.asset_combo.setCurrentIndex(tab.asset_combo.findData("environment/scoutsHouse"))
tab._add_asset()
check("scoutsHouse added to the list, not in the scene",
      [r["in_scene"] for r in tab._rows if r["asset"] == "scoutsHouse"] == [None])
tab._build_shot()
print("   ", tab.status._text.replace("\n", " | "))

check("scoutsHouse referenced into the scene", cmds.ls("scoutsHouse:*", type="mesh"))
check("camera1 not renamed, no camera1_old", cmds.objExists("|EAP_010_010_cam_GRP|camera1")
      and not cmds.ls("camera1_old*"))
check("camera1 still v001", api.shot_camera()[1] == C1)
check("backpack untouched, keys kept", api.scene_version(shot, published("backpack")) == "scout/v001"
      and cmds.keyframe("backpack:backpack_geo.tx", query=True, keyframeCount=True) == 2)
check("status says camera and backpack were left as is",
      "EAP_010_010 Camera: already in the scene, left as is" in tab.status._text
      and "backpack Modeling: already in the scene, left as is" in tab.status._text)

# Picking another version in the list still updates it.
rows = dict((r["asset"], r) for r in tab._rows)
rows["EAP_010_010"]["chosen"] = C2
tab._build_shot()
check("picking v002 for the camera does rebuild it", api.shot_camera()[1] == C2)

print("%d/%d passed" % (sum(ok), len(ok)))
for root, dirs, files in os.walk(base):
    for f in files:
        os.chmod(os.path.join(root, f), stat.S_IWRITE)
shutil.rmtree(base, ignore_errors=True)
