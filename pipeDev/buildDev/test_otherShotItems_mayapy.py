r"""Headless test: another shot's camera and caches, built into any shot or
asset (user, 2026-11-12: "we need to be able to get any asset from any shot
or department if we need it", e.g. a shot camera in an environment to check
its layout; "cameras can be published by layout or animation").

    "C:\Program Files\Autodesk\Maya2027\bin\mayapy.exe" pipeDev/buildDev/test_otherShotItems_mayapy.py

Publishes cameras with Publish's own code and builds with Build's, on
throwaway folders in %TEMP%; never touches the real drives or Maya prefs.
"""
import os, sys, json, shutil, stat, tempfile

import maya.standalone
maya.standalone.initialize()
import maya.cmds as cmds

DEV = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(DEV, "publishDev"), os.path.join(DEV, "buildDev")]
import buildTool_api as api
import publishTool_camera as pcam
import pipeEnv

base = tempfile.mkdtemp(prefix="othershot_")
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
    results.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name)


def make_shot(seq, shot):
    d = api.shot_folder(S, FILM, seq, shot)
    os.makedirs(os.path.join(d, "scenes"))
    open(os.path.join(d, "workspace.mel"), "w").write("")
    os.makedirs(os.path.join(api.shot_folder(H, FILM, seq, shot), "scenes"))
    return d


def make_asset(asset_type, asset):
    d = api.asset_folder(S, FILM, asset_type, asset)
    os.makedirs(os.path.join(d, "scenes"))
    open(os.path.join(d, "workspace.mel"), "w").write("")
    os.makedirs(os.path.join(api.asset_folder(H, FILM, asset_type, asset), "scenes"))
    return d


def publish_camera(shot_dir, stage, tx_end, start=1, end=10):
    """A moving camera, published from the shot's layout scene as stage."""
    cmds.file(new=True, force=True)
    cmds.playbackOptions(minTime=start, maxTime=end)
    tr = cmds.rename(cmds.camera()[0], "layoutCam")
    cmds.setKeyframe(tr + ".tx", time=start, value=0)
    cmds.setKeyframe(tr + ".tx", time=end, value=tx_end)
    scene = os.path.join(shot_dir, "scenes", "layout_%s.ma" % stage)
    cmds.file(rename=scene); cmds.file(save=True, type="mayaAscii")
    plan = pcam.plan_camera(scene, H, S, camera=tr)
    plan["sg_shot"] = {"type": "Shot", "id": 2560}
    plan["publish_for"] = stage
    pcam.export_camera(tr, plan, start, end, scene)
    return plan


SEQ, SHOT = "EAP_010", "EAP_010_010"
shot_a = make_shot(SEQ, SHOT)
shot_b = make_shot("EAP_020", "EAP_020_030")
env_dir = make_asset("environment", "fieldA")

publish_camera(shot_a, "layout", 10)            # v001, Layout
publish_camera(shot_a, "anim", 20)              # v002, Animation
publish_camera(shot_b, "layout", 5, 101, 140)   # shot B's own camera

# --- What a shot offers, by department
lay = api.shot_items(H, FILM, SEQ, SHOT, "layout")
anim = api.shot_items(H, FILM, SEQ, SHOT, "anim")
check("Layout: the shot's camera, only the version Layout published",
      len(lay) == 1 and lay[0]["kind"] == "camera" and list(lay[0]["versions"]) == ["scout/v001"]
      and lay[0]["from_shot"] == (SEQ, SHOT))
check("Animation: the camera with only Animation's version",
      [p["kind"] for p in anim] == ["camera"] and list(anim[0]["versions"]) == ["scout/v002"])
check("a department that publishes nothing for shots: nothing",
      api.shot_items(H, FILM, SEQ, SHOT, "lighting") == [])
check("everything (a list coming back): both versions",
      sorted(api.shot_items(H, FILM, SEQ, SHOT, None)[0]["versions"]) == ["scout/v001", "scout/v002"])

# --- Into an environment asset (the layout check)
cmds.file(new=True, force=True)
cmds.playbackOptions(minTime=50, maxTime=60, animationStartTime=50, animationEndTime=60)
cmds.polyCube(name="ground")
mine = cmds.rename(cmds.camera()[0], "camera1")     # the artist's own camera1
cam = lay[0]
done, warning, _ = api.build_asset(env_dir, cam, cam["latest"])
print("   ", done)
grp = "|EAP_010_010_cam_GRP"
other = grp + "|camera1"
check("into an asset: arrives as camera1 in EAP_010_010_cam_GRP, locked",
      cmds.objExists(other) and cmds.getAttr(other + ".tx", lock=True)
      and cmds.objExists(grp + "|camera1_DATA"))
check("... only one camera1 (the viewport shortcut finds it by name)",
      len(cmds.ls("camera1", type="transform")) == 1 and cmds.ls("camera1", long=True) == [other])
check("... it moves with the shot's keys",
      round(cmds.getAttr(other + ".tx", time=10), 3) == 10)
check("... the artist's own camera1 kept, renamed camera1_old",
      cmds.ls("|camera1_old") == ["camera1_old"])
check("... the timeline takes the shot's range (1-10)",
      (cmds.playbackOptions(query=True, minTime=True),
       cmds.playbackOptions(query=True, maxTime=True)) == (1, 10)
      and any("frame range" in d for d in done))
files = os.path.join(env_dir, "assets", "camera", "shots", SHOT)
check("... its files in a folder of its own", all(
    os.path.isfile(os.path.join(files, f)) for f in ("cam.ma", "camAnim.ma", "camAnim.json")))
entry = api.read_manifest(env_dir).get(api.manifest_key("camera", SHOT, "cam"))
check("... and the asset's record says which shot it's from",
      entry and entry["from_shot"] == [SEQ, SHOT] and entry["version"] == 1)
check("scene version found", api.scene_version(env_dir, cam) == "scout/v001")
done, _, _ = api.build_asset(env_dir, cam, cam["latest"])
check("built again: already up to date", "already up to date" in done)

# Animation's version replaces it; the older one is kept, renamed aside.
done, _, _ = api.build_asset(env_dir, anim[0], anim[0]["latest"])
other = cmds.ls("camera1", long=True)[0]
check("Animation's version: camera1 again, the older one renamed aside",
      other == grp + "|camera1" and round(cmds.getAttr(other + ".tx", time=10), 3) == 20
      and sorted(n for n in cmds.ls("camera1_old*", type="transform") if not n.endswith("_DATA"))
      == ["camera1_old", "camera1_old1"]
      and api.scene_version(env_dir, anim[0]) == "scout/v002")

# A whole-scene Modeling publish leaves the shot camera out.
roots = [r.split("|")[-1] for r in api.pub._model_roots([])]
check("whole-scene Modeling publish: the shot camera isn't in it",
      "ground" in roots and not any("cam_GRP" in r for r in roots))

# --- Into another shot that has its own camera1
cmds.file(new=True, force=True)
own = api.list_shot_cameras(H, FILM, "EAP_020", "EAP_020_030")[0]
api.build_asset(shot_b, own, own["latest"])
before = (cmds.playbackOptions(query=True, minTime=True), cmds.playbackOptions(query=True, maxTime=True))
done, _, _ = api.build_asset(shot_b, cam, cam["latest"])
print("   ", done)
check("into another shot: the other shot's camera is camera1, the shot's own renamed aside",
      cmds.ls("camera1", long=True) == ["|EAP_010_010_cam_GRP|camera1"]
      and cmds.ls("camera1_old", long=True) == ["|EAP_020_030_cam_GRP_old|camera1_old"])
check("... Build knows the shot's own camera isn't in the scene as camera1 any more",
      api.scene_version(shot_b, own) is None and api.scene_version(shot_b, cam) == "scout/v001")
check("... and the shot keeps its own frame range", before == (101, 140) and (
    cmds.playbackOptions(query=True, minTime=True), cmds.playbackOptions(query=True, maxTime=True))
    == before)
check("... the shot's own camera record untouched",
      api.read_manifest(shot_b)[api.manifest_key("camera", "EAP_020_030", "cam")]["file"]
      == "assets/camera/cam.ma")
done, _, _ = api.build_asset(shot_b, own, own["latest"])
check("building the shot's own camera again: it's camera1 again, the other shot's set aside",
      cmds.ls("camera1", long=True) == ["|EAP_020_030_cam_GRP|camera1"]
      and api.scene_version(shot_b, own) == own["latest"])

# --- Caches: Final Animation's, renamed after their shot
cache_dir = os.path.join(api.shot_folder(H, FILM, SEQ, SHOT), "cache", "alembic", "scout")
os.makedirs(cache_dir)
open(os.path.join(cache_dir, SHOT + "_scout_anim_v001.abc"), "w").write("")
json.dump({"item": "scout", "asset": {"assetType": "character", "asset": "scout"}},
          open(os.path.join(cache_dir, SHOT + "_scout_anim_v001.json"), "w"))
anim = api.shot_items(H, FILM, SEQ, SHOT, "anim")
caches = [p for p in anim if p["kind"] == "cache"]
check("Animation also offers the shot's caches, named after the shot",
      [(p["asset_type"], p["asset"]) for p in caches] == [("character", "EAP_010_010_scout")]
      and caches[0]["from_shot"] == (SEQ, SHOT)
      and api.namespace_for(caches[0]["asset"], caches[0]["code"]) == "EAP_010_010_scout_cache")
check("Layout doesn't (caches are Final Animation's)",
      all(p["kind"] == "camera" for p in api.shot_items(H, FILM, SEQ, SHOT, "layout")))

print("\n%d/%d passed" % (sum(results), len(results)))
for root, dirs, fs in os.walk(base):
    for f in fs:
        os.chmod(os.path.join(root, f), stat.S_IWRITE)
shutil.rmtree(base, ignore_errors=True)
