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
from PySide6 import QtWidgets, QtCore
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
    start, end = (1, 10) if v == 1 else (1001, 1020)     # v002 has its own range
    pcam.export_camera(cam, pcam.plan_camera(layout, H, SC, camera=cam), start, end, layout)


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
p = tab.picker
check("builds into the open scene's shot", tab._target_shot == (FILM, "EAP_010", "EAP_010_010")
      and "EAP_010_010" in tab.target_lbl.text())
rows = dict((r["asset"], r) for r in tab._rows)
check("camera row starts at what the scene has (v001), not the manifest's v002",
      rows["EAP_010_010"]["chosen"] == C1 and rows["EAP_010_010"]["in_scene"] == C1)
check("rows already in the scene start unticked",
      not rows["EAP_010_010"]["checked"] and not rows["backpack"]["checked"])
def dept_codes():
    model = p.dept_combo.model()
    return [model.item(i).data(QtCore.Qt.UserRole) for i in range(model.rowCount())]
p.set_current(film=FILM, code="model")
asset_side = dept_codes()
p.set_current(code="env")
check("picker: Environment is on the Shot side beside Camera, not an asset department "
      "(user, 2026-10-26), and lists assets", "env" not in asset_side
      and dept_codes() == ["cam", "env", "cache"] and p.kind() == "shot"
      and p.group_combo.toolTip() == "Asset type")
p.set_current(film=FILM, code="rig")
check("picker: Rigging lists no assets (nothing published for it)", p.name() is None)
p.set_current(code="model", group="environment", name="scoutsHouse")
check("picker: Modeling lists the published models", (p.kind(), p.group(), p.name())
      == ("asset", "environment", "scoutsHouse"))
tab._add_asset()
check("scoutsHouse added to the list, ticked, not in the scene",
      [(r["in_scene"], r["checked"]) for r in tab._rows if r["asset"] == "scoutsHouse"]
      == [(None, True)])
p.set_current(code="cam", group="EAP_010", name="EAP_010_010")
tab._add_asset()
check("picker: the shot's camera is already in the list", "already in the list" in tab.status._text)
tab._build_shot()
print("   ", tab.status._text.replace("\n", " | "))

check("scoutsHouse referenced into the scene", cmds.ls("scoutsHouse:*", type="mesh"))
check("camera1 not renamed, no camera1_old", cmds.objExists("|EAP_010_010_cam_GRP|camera1")
      and not cmds.ls("camera1_old*"))
check("camera1 still v001", api.shot_camera()[1] == C1)
check("backpack untouched, keys kept", api.scene_version(shot, published("backpack")) == "scout/v001"
      and cmds.keyframe("backpack:backpack_geo.tx", query=True, keyframeCount=True) == 2)
check("only the ticked row was built", "scoutsHouse" in tab.status._text
      and "EAP_010_010" not in tab.status._text and "backpack" not in tab.status._text)
check("a built row is unticked", not [r for r in tab._rows if r["checked"]])

# Picking another version in the list ticks it, and Build updates it.
rows = dict((r["asset"], r) for r in tab._rows)
tab._on_version_changed(rows["EAP_010_010"], C2)
check("picking v002 for the camera ticks it", rows["EAP_010_010"]["checked"])
tab._build_shot()
check("picking v002 for the camera does rebuild it", api.shot_camera()[1] == C2)
check("... and sets the frame range it was published with (user, 2026-10-26)",
      (cmds.playbackOptions(query=True, minTime=True), cmds.playbackOptions(query=True, maxTime=True),
       cmds.playbackOptions(query=True, animationStartTime=True),
       cmds.playbackOptions(query=True, animationEndTime=True)) == (1001, 1020, 1001, 1020)
      and "frame range set to 1001-1020" in tab.status._text)
cmds.playbackOptions(minTime=1, maxTime=24)
rows["EAP_010_010"]["checked"] = True     # ticked again, camera already up to date
tab._build_shot()
check("an up-to-date camera still puts the range back on Build",
      (cmds.playbackOptions(query=True, minTime=True),
       cmds.playbackOptions(query=True, maxTime=True)) == (1001, 1020))

# Loading a shot clears the last message (review 2026-10-21: the status
# line had been cut off _load_shot, so old messages stayed up).
tab._load_shot()
check("loading a shot clears the old status message", tab.status._text == "")

# -- Show filter + Remove from List (user, 2026-10-21) ----------------------
names = lambda: sorted(r["asset"] for r in tab._rows)
shown = lambda: sorted(tab._rows[i]["asset"] for i in range(len(tab._rows))
                       if not tab.table.isRowHidden(i))
labels = [tab.filter_combo.itemText(i) for i in range(tab.filter_combo.count())]
check("Show menu: All + the list's departments", labels[0] == "All departments"
      and "Camera" in labels and "Modeling" in labels)
tab.filter_combo.setCurrentIndex(tab.filter_combo.findData("cam"))
check("Show Camera: only the camera row is shown", shown() == ["EAP_010_010"])
tab.filter_combo.setCurrentIndex(0)
check("Show All: every row again", shown() == names())

refs_before = sorted(n for n, _, _, _ in api.scene_references())
tab.table.clearSelection()
tab._remove_rows()
check("Remove with nothing selected says what to do", "Click the rows" in tab.status._text)
built = [i for i, r in enumerate(tab._rows) if r["asset"] == "backpack"][0]
tab.table.selectRow(built)
tab._remove_rows()
check("a built asset comes off the list", "backpack" not in names()
      and "Taken off this shot's list: backpack" in tab.status._text)
check("... the scene keeps its reference", sorted(n for n, _, _, _ in api.scene_references())
      == refs_before)
check("... and the shot's record keeps it", any(k.endswith("/backpack/model")
                                                 for k in api.read_manifest(shot)))
tab._refresh_list()
check("Refresh doesn't bring it back", "backpack" not in names())
for r in tab._rows:
    r["checked"] = True
tab._build_shot()
check("Build Shot leaves the removed asset alone in the scene",
      sorted(n for n, _, _, _ in api.scene_references()) == refs_before)
p.set_current(code="model", group="prop", name="backpack")
tab.filter_combo.setCurrentIndex(tab.filter_combo.findData("cam"))
tab._add_asset()
check("adding it again puts it back, and the filter shows it",
      "backpack" in names() and "backpack" in shown())
tab._load_shot()
check("re-added but not built: '-' still holds after a reload (user, 2026-10-23)",
      "backpack" not in names())
p.set_current(code="model", group="prop", name="backpack")
tab._add_asset()
tab._build_shot()
tab._load_shot()
check("re-added and built: back on the shot's list after a reload", "backpack" in names())

print("%d/%d passed" % (sum(ok), len(ok)))
for root, dirs, files in os.walk(base):
    for f in files:
        os.chmod(os.path.join(root, f), stat.S_IWRITE)
shutil.rmtree(base, ignore_errors=True)
