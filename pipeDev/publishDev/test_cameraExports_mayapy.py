r"""Headless test for the camera for other software (user, 2026-11-26: "send
camera to blender houdini Unreal gaffer etc"): a Camera row's ABC / USD /
FBX ticks write the baked camera to the shot's cache folders.

    "C:\Program Files\Autodesk\Maya2027\bin\mayapy.exe" pipeDev/publishDev/test_cameraExports_mayapy.py

Each file is read back (Maya import, or pxr for the USD) and its keys
checked, not just its existence. Throwaway folders in %TEMP% only.
"""
import os, sys, json, tempfile

import maya.standalone
maya.standalone.initialize()
import maya.cmds as cmds

DEV = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(DEV, "publishDev"), os.path.join(DEV, "buildDev")]
import buildTool_api as api
import publishTool_camera as pcam
import pipeEnv

base = tempfile.mkdtemp(prefix="camexports_")
H, S = os.path.join(base, "H"), os.path.join(base, "S")
FILM = "NWF_SHF"
_cfg = os.path.join(base, "pipeline_config.json")
api.pub._config_path = lambda: _cfg
api.pub.set_root(api.pub.H_DRIVE, H)
api.pub.set_root(api.pub.SCRATCH, S)
api.pub.save_config(dict(api.pub.load_config(), publish_as="scout"))
api.pub.artist_name = lambda login: "Scout Test"
os.environ.pop(pipeEnv.VAR, None)
results = []


def check(name, ok):
    results.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name)


def files_under(folder):
    return sorted(os.path.relpath(os.path.join(d, f), folder)
                  for d, _, fs in os.walk(folder) for f in fs)


shot = api.shot_folder(S, FILM, "EAP_010", "EAP_010_010")
os.makedirs(os.path.join(shot, "scenes"))
open(os.path.join(shot, "workspace.mel"), "w").write("")
h_shot = api.shot_folder(H, FILM, "EAP_010", "EAP_010_010")
os.makedirs(os.path.join(h_shot, "scenes"))


def layout_scene():
    """Moving, focal length keyed, parented under a moving group (so only a
    world-space bake gets it right)."""
    cmds.file(new=True, force=True)
    cmds.playbackOptions(minTime=1, maxTime=10)
    rig = cmds.group(empty=True, name="camRig")
    cmds.setKeyframe(rig + ".tz", time=1, value=0); cmds.setKeyframe(rig + ".tz", time=10, value=-20)
    tr = cmds.rename(cmds.camera()[0], "layoutCam")
    tr = cmds.parent(tr, rig)[0]
    sh = cmds.listRelatives(tr, shapes=True)[0]
    cmds.setKeyframe(tr + ".tx", time=1, value=0); cmds.setKeyframe(tr + ".tx", time=10, value=10)
    cmds.setKeyframe(sh + ".focalLength", time=1, value=35); cmds.setKeyframe(sh + ".focalLength", time=10, value=50)
    cmds.setAttr(sh + ".horizontalFilmAperture", 1.5)
    scene = os.path.join(shot, "scenes", "layout.ma")
    cmds.file(rename=scene); cmds.file(save=True, type="mayaAscii")
    return cmds.ls(tr, long=True)[0], scene


def publish(camera, scene, formats):
    plan = pcam.plan_camera(scene, H, S, camera=camera)
    plan["sg_shot"] = {"type": "Shot", "id": 2560}
    pcam.export_camera(camera, plan, 1, 10, scene, formats)
    return plan


# --- v001: no ticks, nothing in cache\
cam, scene = layout_scene()
plan = publish(cam, scene, ())
check("no ticks: no cache folder", not os.path.isdir(os.path.join(h_shot, "cache")))
check("no ticks: written = the three Maya-side files",
      sorted(plan["written"]) == sorted([plan["dest"], plan["keys_dest"], plan["map_dest"]]))

# --- v002: all three
cam, scene = layout_scene()
plan = publish(cam, scene, ["fbx", "abc", "usd", "obj"])     # obj isn't a camera format
names = files_under(os.path.join(h_shot, "cache"))
print("    cache:", names)
check("exports: in cache\\<format>\\layout\\scout\\, named like the camera file",
      names == sorted(os.path.join(folder, "layout", "scout", "EAP_010_010_scout_cam_v002" + ext)
                      for folder in ("alembic", "usd", "fbx") for ext in (
                          {"alembic": ".abc", "usd": ".usd", "fbx": ".fbx"}[folder], ".json")))
check("exports: listed in written", all(p in plan["written"]
                                        for fmt in ("abc", "usd", "fbx") for p in plan["exports"][fmt]))
info = json.load(open(plan["exports"]["abc"][1]))
check("json: says it's a camera, its frames and film back",
      info["kind"] == "camera" and info["format"] == "abc" and info["version"] == 2
      and info["start"] == 1 and info["end"] == 10 and info["department"] == "layout"
      and abs(info["film_back_mm"][0] - 38.1) < 1e-3 and info["camera"] == "shotCam")
check("exports locked", not os.access(plan["exports"]["abc"][0], os.W_OK))
check("publish leaves nothing behind", not cmds.ls("shotCam*") and not cmds.ls("*_cam_GRP"))


def world_tx(node, t):
    cmds.currentTime(t)
    return cmds.xform(node, query=True, worldSpace=True, translation=True)


# ABC, read back
cmds.file(new=True, force=True)
cmds.loadPlugin("AbcImport", quiet=True)
cmds.AbcImport(plan["exports"]["abc"][0].replace("\\", "/"), mode="import")
cams = cmds.ls(type="camera")
abc = [c for c in cams if "shotCam" in c]
check("ABC: one camera, shotCam", len(abc) == 1)
if abc:
    tr = cmds.listRelatives(abc[0], parent=True, fullPath=True)[0]
    p1, p10 = world_tx(tr, 1), world_tx(tr, 10)
    print("    ABC frame 1 / 10:", p1, p10, cmds.getAttr(abc[0] + ".focalLength", time=10))
    check("ABC: moves in world space (tx 0->10, tz 0->-20)",
          abs(p1[0]) < 1e-3 and abs(p10[0] - 10) < 1e-3 and abs(p10[2] + 20) < 1e-3)
    check("ABC: focal length animated 35 -> 50",
          abs(cmds.getAttr(abc[0] + ".focalLength", time=1) - 35) < 1e-3
          and abs(cmds.getAttr(abc[0] + ".focalLength", time=10) - 50) < 1e-3)
    check("ABC: film back kept", abs(cmds.getAttr(abc[0] + ".horizontalFilmAperture", time=5) - 1.5) < 1e-3)

# FBX, read back
cmds.file(new=True, force=True)
cmds.loadPlugin("fbxmaya", quiet=True)
cmds.file(plan["exports"]["fbx"][0], i=True, type="FBX")
fbx = [c for c in cmds.ls(type="camera") if "shotCam" in c]
check("FBX: one camera, shotCam", len(fbx) == 1)
if fbx:
    tr = cmds.listRelatives(fbx[0], parent=True, fullPath=True)[0]
    p1, p10 = world_tx(tr, 1), world_tx(tr, 10)
    print("    FBX frame 1 / 10:", p1, p10, cmds.getAttr(fbx[0] + ".focalLength", time=10))
    check("FBX: keyed on the camera itself",
          cmds.keyframe(tr + ".translateX", query=True, keyframeCount=True) >= 2)
    check("FBX: moves in world space (tx 0->10, tz 0->-20)",
          abs(p1[0]) < 1e-3 and abs(p10[0] - 10) < 1e-3 and abs(p10[2] + 20) < 1e-3)
    check("FBX: focal length animated 35 -> 50",
          abs(cmds.getAttr(fbx[0] + ".focalLength", time=1) - 35) < 1e-2
          and abs(cmds.getAttr(fbx[0] + ".focalLength", time=10) - 50) < 1e-2)

# USD, read with pxr
from pxr import Usd, UsdGeom
stage = Usd.Stage.Open(plan["exports"]["usd"][0])
usd_cams = [p for p in stage.Traverse() if p.IsA(UsdGeom.Camera)]
check("USD: one UsdGeomCamera", len(usd_cams) == 1)
if usd_cams:
    gcam = UsdGeom.Camera(usd_cams[0])
    xf = UsdGeom.Xformable(usd_cams[0])
    m1 = xf.ComputeLocalToWorldTransform(1).ExtractTranslation()
    m10 = xf.ComputeLocalToWorldTransform(10).ExtractTranslation()
    print("    USD", usd_cams[0].GetPath(), "frame 1 / 10:", m1, m10)
    check("USD: moves in world space (tx 0->10, tz 0->-20)",
          abs(m1[0]) < 1e-3 and abs(m10[0] - 10) < 1e-3 and abs(m10[2] + 20) < 1e-3)
    check("USD: focal length animated 35 -> 50",
          abs(gcam.GetFocalLengthAttr().Get(1) - 35) < 1e-3
          and abs(gcam.GetFocalLengthAttr().Get(10) - 50) < 1e-3)
    check("USD: frame range 1-10", stage.GetStartTimeCode() == 1 and stage.GetEndTimeCode() == 10)
del stage

# --- v003: an exporter fails -> nothing of v003 is left on H
before = files_under(H)
cam, scene = layout_scene()
real = pcam._export_usd


def broken(*args):
    raise RuntimeError("usd export broke")


pcam._export_usd = broken
try:
    publish(cam, scene, ["abc", "usd", "fbx"])
    failed = False
except RuntimeError:
    failed = True
pcam._export_usd = real
check("a failed export fails the publish", failed)
check("a failed export leaves nothing on H", files_under(H) == before)
check("a failed export leaves nothing in the scene", not cmds.ls("shotCam*") and not cmds.ls("*_cam_GRP"))

# --- From Build's camera1 (driven by camera1_DATA): the export still moves.
# v003 again: the failed v003 left nothing, so its number is free.
cams = api.list_shot_cameras(H, FILM, "EAP_010", "EAP_010_010")
V2 = api.version_id("scout", 2)
cmds.file(new=True, force=True)
api.ensure_maya_project(shot)
api.build_asset(shot, cams[0], V2)
cmds.playbackOptions(minTime=1, maxTime=10)
anim_scene = os.path.join(shot, "scenes", "anim.ma")
cmds.file(rename=anim_scene); cmds.file(save=True, type="mayaAscii")
built = cmds.ls("camera1", long=True, type="transform")[0]
plan = pcam.plan_camera(anim_scene, H, S, camera=built, department="anim")
plan["sg_shot"] = {"type": "Shot", "id": 2560}
plan["publish_for"] = "anim"
pcam.export_camera(built, plan, 1, 10, anim_scene, ["abc"])
check("from Build: anim department folder",
      os.path.normpath(plan["exports"]["abc"][0]).endswith(
          os.path.join("cache", "alembic", "anim", "scout", "EAP_010_010_scout_cam_v003.abc")))
cmds.file(new=True, force=True)
cmds.AbcImport(plan["exports"]["abc"][0].replace("\\", "/"), mode="import")
tr = cmds.listRelatives([c for c in cmds.ls(type="camera") if "shotCam" in c][0],
                        parent=True, fullPath=True)[0]
p10 = world_tx(tr, 10)
check("from Build: camera1's driven move is in the ABC", abs(p10[0] - 10) < 1e-3
      and abs(p10[2] + 20) < 1e-3)

failed = [n for n, ok in results if not ok]
print("\n%d/%d passed" % (len(results) - len(failed), len(results)))
if failed:
    print("FAILED:\n  " + "\n  ".join(failed))
maya.standalone.uninitialize()
os._exit(1 if failed else 0)
