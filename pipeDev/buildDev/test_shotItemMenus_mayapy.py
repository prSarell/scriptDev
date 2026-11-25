# Build's Type and Item dropdowns (user, 2026-11-25): on Add to list's Shot
# side, after the shot, Type lists what the picked department published for
# that shot (Camera, Cache) and Item which one (scout_ABC, scout_USD,
# scout_FBX); + adds just that one. Animation publishes caches as ABC, USD
# and FBX (skeleton + skin); Build references the ABC and FBX and loads the
# USD as a USD stage. Every department, Lighting included, builds them.
# Run: mayapy test_shotItemMenus_mayapy.py
import sys, os, json, stat, shutil, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), "publishDev")]
from PySide6 import QtWidgets
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
import maya.standalone; maya.standalone.initialize()
import maya.cmds as cmds
import buildTool_api as api
import buildTool_ui as ui
import pipePicker as picker
import publishTool_anim as anim
import publishTool_camera as pcam
import publishTool_textures as tex
import pipeEnv

pub = api.pub
ok = []
def check(label, cond):
    ok.append(bool(cond)); print("PASS" if cond else "FAIL", label)

base = tempfile.mkdtemp(prefix="shotitems_")
H, SC = os.path.join(base, "H"), os.path.join(base, "scratch")
FILM, SEQ, SHOT, LOGIN = "NWF_SHF", "EAP_010", "EAP_010_010", "scout"
OTHER = "EAP_010_020"
_cfg = os.path.join(base, "pipeline_config.json")
pub._config_path = lambda: _cfg
pub.set_root(pub.H_DRIVE, H)
pub.set_root(pub.SCRATCH, SC)
pub.save_config(dict(pub.load_config(), publish_as=LOGIN))
os.environ.pop(pipeEnv.VAR, None)
for plugin in ("AbcImport", "AbcExport", "fbxmaya", api.USD_PLUGIN):
    cmds.loadPlugin(plugin, quiet=True)

scout_s = api.asset_folder(SC, FILM, "character", "scout")
os.makedirs(os.path.join(scout_s, "scenes"))
open(os.path.join(scout_s, "workspace.mel"), "w").write("")
os.makedirs(os.path.join(H, FILM, "maya", "assets", "character", "scout", "scenes"))
shots = {}
for shot in (SHOT, OTHER):
    d = api.shot_folder(SC, FILM, SEQ, shot)
    os.makedirs(os.path.join(d, "scenes")); open(os.path.join(d, "workspace.mel"), "w").write("")
    os.makedirs(os.path.join(api.shot_folder(H, FILM, SEQ, shot), "scenes"))
    shots[shot] = d
shot_s, other_s = shots[SHOT], shots[OTHER]

# --- Scout's rig: a skinned mesh driven by a control through two joints
cmds.file(new=True, force=True)
cmds.workspace(scout_s, openWorkspace=True)
rig = cmds.group(empty=True, name="scout_rig")
cmds.select(clear=True)
hip = cmds.joint(name="hip_JNT", position=(0, 0, 0))
cmds.joint(name="spine_JNT", position=(0, 2, 0))
cmds.parent(hip, rig)
body = cmds.parent(cmds.polyCylinder(name="body_geo", height=2, subdivisionsY=4)[0], rig)[0]
cmds.move(0, 1, 0, body)
cmds.skinCluster(["hip_JNT", "spine_JNT"], body, toSelectedBones=True)
ctl = cmds.parent(cmds.circle(name="root_ctl")[0], rig)[0]
cmds.parentConstraint(ctl, "hip_JNT", maintainOffset=True)
cmds.sets(["body_geo"], name=pub.CACHE_SET)
cmds.sets([ctl], name=pub.BODY_CONTROLS_SET)
rig_scene = os.path.join(scout_s, "scenes", "rig_work.ma")
cmds.file(rename=rig_scene); cmds.file(save=True, type="mayaAscii")
plan = pub.plan_publish(rig_scene, H, SC, "rig")
plan.update(objects=["scout_rig"], sg_asset={"type": "Asset", "id": 99}, cache_set=pub.CACHE_SET,
            control_sets={"body": pub.BODY_CONTROLS_SET, "face": None})
plan["set_uuids"] = cmds.ls([pub.CACHE_SET, pub.BODY_CONTROLS_SET], uuid=True)
pub.export_rig_to_h_drive(["scout_rig"], plan, rig_scene, tex.collect(["scout_rig"]), [])
rig_file = plan["dest"]

# --- The shot: animated, published Final with all three cache formats, and
# a camera from Animation.
cmds.file(new=True, force=True)
cmds.file(rig_file, reference=True, namespace="scout_rig")
ctl = cmds.ls("scout_rig:root_ctl")[0]
cmds.setKeyframe(ctl + ".tx", time=1, value=0)
cmds.setKeyframe(ctl + ".tx", time=10, value=5)
cmds.playbackOptions(minTime=1, maxTime=10)
anim_scene = os.path.join(shot_s, "scenes", "anim", LOGIN, "anim_work.ma")
os.makedirs(os.path.dirname(anim_scene))
cmds.file(rename=anim_scene); cmds.file(save=True, type="mayaAscii")
items = anim.classify([ctl])
p = anim.plan_anim(anim_scene, H, SC, items, anim.ANIM_CODE)
p["stage"], p["caches"] = anim.FINAL, ["abc", "usd", "fbx"]
anim.write_anim(items, p, 1, 10, anim_scene)
files = p["item_files"][items[0]["name"]]["caches"]
check("Publish: ABC, USD and FBX caches, each with its .json",
      all(os.path.isfile(f) and os.path.isfile(j) for f, j in files.values())
      and os.sep + os.path.join("cache", "fbx", "anim", LOGIN) + os.sep in files["fbx"][0])
check("FBX cache's .json says fbx", json.load(open(files["fbx"][1]))["format"] == "fbx")

cam_tr = cmds.rename(cmds.camera()[0], "animCam")
cmds.setKeyframe(cam_tr + ".tx", time=1, value=0)
cmds.setKeyframe(cam_tr + ".tx", time=10, value=3)
cmds.file(save=True, type="mayaAscii")
cplan = pcam.plan_camera(anim_scene, H, SC, camera=cam_tr)
cplan["sg_shot"] = {"type": "Shot", "id": 2560}
cplan["publish_for"] = "anim"
pcam.export_camera(cam_tr, cplan, 1, 10, anim_scene)

# The FBX carries the skeleton and the skin.
cmds.file(new=True, force=True)
cmds.file(files["fbx"][0], i=True, type="FBX")
named = lambda name, **kw: cmds.ls(name, recursive=True, long=True, **kw)
check("FBX cache: joints and a skinned mesh",
      named("hip_JNT", type="joint") and named("spine_JNT", type="joint")
      and cmds.ls(cmds.listHistory(named("body_geo")[0]) or [], type="skinCluster"))
check("... no controls or constraints", not named("root_ctl")
      and not cmds.ls(type="parentConstraint"))
cmds.currentTime(10)
check("FBX cache: the joints are baked (hip moved to x=5)",
      abs(cmds.xform(named("hip_JNT")[0], query=True, worldSpace=True, translation=True)[0] - 5)
      < 0.01)

# --- Build lists a cache per format, labelled for the Item dropdown
caches = api.list_shot_caches(H, FILM, SEQ, SHOT)
check("three cache entries: abc, usd, fbx",
      [(c["format"], c["asset"]) for c in caches]
      == [("abc", "scoutrig"), ("usd", "scoutrig_usd"), ("fbx", "scoutrig_fbx")])
check("labelled by the cached asset and format, no shot or rig",
      [c["label"] for c in caches] == ["scout_ABC", "scout_USD", "scout_FBX"])
twins = [dict(item=i, stamp_asset="scout", format="abc") for i in ("scout1", "scout2")]
api.label_caches(twins)
check("two of the same asset: the animator's item names",
      [c["label"] for c in twins] == ["scout1_ABC", "scout2_ABC"])
vid = api.version_id(LOGIN, 1)
by_fmt = dict((c["format"], c) for c in caches)

# --- USD cache: a USD stage
cmds.file(new=True, force=True)
light_scene = os.path.join(shot_s, "scenes", "lighting", LOGIN, "light.ma")
os.makedirs(os.path.dirname(light_scene))
cmds.file(rename=light_scene); cmds.file(save=True, type="mayaAscii")
cmds.workspace(shot_s, openWorkspace=True)
done, warning, _ = api.build_asset(shot_s, by_fmt["usd"], vid, "lighting")
print("   ", done, warning)
stage = api.stage_of(by_fmt["usd"])
check("USD cache loaded as a USD stage in its pipe group",
      stage and cmds.getAttr(stage[1] + ".filePath").startswith("$PIPE_SCRATCH/")
      and "/cache/usd/anim/scout/" in cmds.getAttr(stage[1] + ".filePath")
      and stage[0].split("|")[1] == "scoutrig_usd_cache_GRP")
check("... scene_version sees it", api.scene_version(shot_s, by_fmt["usd"]) == vid)
done, _, _ = api.build_asset(shot_s, by_fmt["usd"], vid, "lighting")
check("... built again: already up to date", done == ["already up to date"])

# --- FBX cache: Lighting imports it (2026-11-26) in its own namespace and group
done, warning, _ = api.build_asset(shot_s, by_fmt["fbx"], vid, "lighting")
print("   ", done, warning)
refs = [w for _, w, _, _ in api.scene_references() if w.lower().endswith(".fbx")]
source = cmds.getAttr("scoutrig_fbx_cache_GRP." + api.CACHE_FILE_ATTR) \
    if cmds.objExists("scoutrig_fbx_cache_GRP") else ""
check("FBX cache imported (not referenced) from scratch, through $PIPE_SCRATCH",
      not refs and source.startswith("$PIPE_SCRATCH/") and "/cache/fbx/anim/scout/" in source)
check("... in scoutrig_fbx_cache_GRP with its skeleton",
      cmds.objExists("scoutrig_fbx_cache_GRP")
      and any(j.split("|")[1] == "scoutrig_fbx_cache_GRP"
              and j.split("|")[-1].startswith("scoutrig_fbx_cache:")
              for j in named("hip_JNT", type="joint")))
check("... scene_version sees it", api.scene_version(shot_s, by_fmt["fbx"]) == vid)

# --- The Build tab: Type and Item
cmds.file(new=True, force=True)
os.makedirs(os.path.join(other_s, "scenes", "lighting", LOGIN))
cmds.file(rename=os.path.join(other_s, "scenes", "lighting", LOGIN, "light.ma"))
cmds.file(save=True, type="mayaAscii")
cmds.workspace(other_s, openWorkspace=True)
parent = QtWidgets.QWidget()
tab = ui.BuildShotTab(lambda: (H, SC), parent)
tab.refresh()
pk = tab.picker
check("building into the other shot as Lighting", tab._target_shot == (FILM, SEQ, OTHER)
      and tab.department() == "lighting")
pk.set_current(film=FILM, code="anim", group=SEQ, name=SHOT, kind=picker.SHOT)
labels = lambda combo: [combo.itemText(i) for i in range(combo.count())]
check("Type and Item sit last, after the shot, before - and +",
      [pk.layout().itemAt(i).widget() for i in range(4, 8)]
      == [pk.name_combo, pk.type_combo, pk.item_combo, pk.remove_btn])
check("Shot side: Type shows Camera and Cache", not pk.type_combo.isHidden()
      and labels(pk.type_combo) == ["Camera", "Cache"])
check("Camera: the shot's camera", labels(pk.item_combo) == ["camera"])
pk.type_combo.setCurrentIndex(1)
check("Cache: scout_ABC, scout_USD, scout_FBX",
      labels(pk.item_combo) == ["scout_ABC", "scout_USD", "scout_FBX"])
pk.item_combo.setCurrentIndex(1)
before = len(tab._rows)
tab._add_asset()
added = tab._rows[before:]
check("+ adds only the picked one (scout_USD), ticked",
      len(added) == 1 and added[0]["format"] == "usd" and added[0]["checked"]
      and added[0]["asset"] == SHOT + "_scoutrig_usd")
tab._add_asset()
check("+ again: not added twice", len(tab._rows) == before + 1)
tab._build_shot()
stage = api.stage_of(added[0])
check("Lighting builds it into the other shot as a USD stage",
      stage and stage[0].split("|")[1] == SHOT + "_scoutrig_usd_cache_GRP")
pk.set_current(code="layout", name=SHOT, kind=picker.SHOT)
check("Layout picked: no caches (they're Animation's), and no camera from Layout here",
      labels(pk.type_combo) == [picker.NONE_TEXT])
pk.set_current(code="model", kind=picker.ASSET)
check("Asset side: Type and Item hidden", pk.type_combo.isHidden() and pk.item_combo.isHidden()
      and pk.item() is None)
check("Build into has no Type or Item", tab.target_picker.type_combo.isHidden())

print("\n%d/%d passed" % (sum(ok), len(ok)))
for root, dirs, fs in os.walk(base):
    for f in fs:
        os.chmod(os.path.join(root, f), stat.S_IWRITE)
shutil.rmtree(base, ignore_errors=True)
maya.standalone.uninitialize()
