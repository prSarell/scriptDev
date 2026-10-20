r"""Headless test for the camera group (user, 2026-10-20):

    <shot>_cam_GRP        pipe stamp like the model group, image plane info
      camera1             every animated attribute driven 1:1 by...
      camera1_DATA        ...an attribute here, which the keys drive

    "C:\Program Files\Autodesk\Maya2025\bin\mayapy.exe" pipeDev/buildDev/test_cameraGroup_mayapy.py

Publishes with Publish's own code and builds with Build's, on throwaway
folders in %TEMP%; never touches the real drives or Maya prefs.
"""
import os, sys, json, stat, shutil, tempfile

import maya.standalone
maya.standalone.initialize()
import maya.cmds as cmds

DEV = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(DEV, "publishDev"), os.path.join(DEV, "buildDev")]
import buildTool_api as api
import publishTool_camera as pcam
import pipeEnv

base = tempfile.mkdtemp(prefix="camgroup_")
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


def make_shot(seq, shot):
    d = api.shot_folder(S, FILM, seq, shot)
    os.makedirs(os.path.join(d, "scenes"))
    open(os.path.join(d, "workspace.mel"), "w").write("")
    os.makedirs(os.path.join(api.shot_folder(H, FILM, seq, shot), "scenes"))
    return d


shot = make_shot("EAP_010", "EAP_010_010")
other = make_shot("EAP_020", "EAP_020_030")
PLATE = "D:/NWF_SHF/plates/EAP_010_010/plate.####.png"


def layout_scene(shot_dir, tx_end):
    """A layout camera: moving, focal length keyed, an image plane."""
    cmds.file(new=True, force=True)
    cmds.playbackOptions(minTime=1, maxTime=10)
    tr = cmds.rename(cmds.camera()[0], "layoutCam")
    sh = cmds.listRelatives(tr, shapes=True)[0]
    cmds.setKeyframe(tr + ".tx", time=1, value=0); cmds.setKeyframe(tr + ".tx", time=10, value=tx_end)
    cmds.setKeyframe(tr + ".ry", time=1, value=0); cmds.setKeyframe(tr + ".ry", time=10, value=45)
    cmds.setKeyframe(sh + ".focalLength", time=1, value=35); cmds.setKeyframe(sh + ".focalLength", time=10, value=50)
    cmds.setAttr(sh + ".horizontalFilmAperture", 1.5)        # a static setting
    ip = cmds.imagePlane(camera=tr)[1]
    cmds.setAttr(ip + ".imageName", PLATE, type="string")
    cmds.setAttr(ip + ".useFrameExtension", 1)
    cmds.setAttr(ip + ".frameOffset", 1000)
    scene = os.path.join(shot_dir, "scenes", "layout.ma")
    cmds.file(rename=scene); cmds.file(save=True, type="mayaAscii")
    return tr, scene


def publish(shot_dir, camera, scene):
    plan = pcam.plan_camera(scene, H, S, camera=camera)
    plan["sg_shot"] = {"type": "Shot", "id": 2560}
    pcam.export_camera(camera, plan, 1, 10, scene)
    return plan


# --- Publish v001 from layout
cam, scene = layout_scene(shot, 10)
plan = publish(shot, cam, scene)
check("publish leaves nothing behind in the open scene",
      not cmds.ls("shotCam*") and not cmds.ls("*_cam_GRP") and cmds.objExists("layoutCam"))

mapping = json.load(open(plan["map_dest"]))
check("map: format 2, group named from the shot", mapping["format"] == 2
      and mapping["group"] == "EAP_010_010_cam_GRP" and mapping["data"] == "shotCam_DATA")
check("map: curves drive data attributes", set(mapping["curves"].values()) >= {
    "cam_translateX", "cam_rotateY", "camShape_focalLength"})
check("map: data attributes say which camera attribute they drive",
      mapping["attrs"]["camShape_focalLength"] == ["shape", "focalLength"]
      and mapping["attrs"]["cam_translateX"] == ["transform", "translateX"])
check("map: image plane recorded", mapping["image_planes"][0]["image"] == PLATE)

# The published camera file on its own.
cmds.file(plan["dest"], open=True, force=True)
grp = "|EAP_010_010_cam_GRP"
check("camera file: one group at the top, camera + data node under it",
      sorted(cmds.ls(assemblies=True)) == ["EAP_010_010_cam_GRP", "front", "persp", "side", "top"]
      and sorted(cmds.listRelatives(grp, children=True)) == ["shotCam", "shotCam_DATA"])
stamp = dict((a, cmds.getAttr("%s.%s" % (grp, a))) for a in cmds.listAttr(grp, userDefined=True))
print("    stamp:", dict((k, v) for k, v in stamp.items() if k != "pipe_imagePlanes"))
check("group stamp: shot, department, version, artist, ShotGrid id, source scene",
      stamp["pipe_shot"] == "EAP_010_010" and stamp["pipe_department"] == "cam"
      and stamp["pipe_version"] == 1 and stamp["pipe_artistId"] == "scout"
      and stamp["pipe_artistName"] == "Scout Test" and stamp["pipe_sgShotId"] == 2560
      and stamp["pipe_sourceScene"].endswith("layout.ma") and stamp["pipe_publishedFrom"] == "layout")
planes = json.loads(stamp["pipe_imagePlanes"])
check("group stamp: image sequence location and name",
      planes[0]["folder"] == "D:/NWF_SHF/plates/EAP_010_010" and planes[0]["file"] == "plate.####.png"
      and planes[0]["useFrameExtension"] and planes[0]["frameOffset"] == 1000)
check("group stamp locked", cmds.getAttr(grp + ".pipe_version", lock=True))
check("group is a dagContainer", cmds.nodeType(grp) == "dagContainer")
check("group: pipe icon, locked at the origin, channels hidden",
      cmds.getAttr(grp + ".iconName") == "iconPipeOutliner.png"
      and all(cmds.getAttr("%s.%s" % (grp, a), lock=True) and not cmds.getAttr("%s.%s" % (grp, a), channelBox=True)
              for a in api.pub.GROUP_CHANNELS))
check("camera file: no keys", not cmds.ls(type="animCurve"))
check("camera file: no image plane", not cmds.ls(type="imagePlane"))
check("camera file: data node drives camera 1:1",
      cmds.listConnections(grp + "|shotCam.translateX", source=True, plugs=True)
      == ["shotCam_DATA.cam_translateX"]
      and cmds.listConnections(grp + "|shotCam|shotCamShape.focalLength", source=True, plugs=True)
      == ["shotCam_DATA.camShape_focalLength"])
check("camera file: static settings kept on the camera",
      abs(cmds.getAttr(grp + "|shotCam|shotCamShape.horizontalFilmAperture") - 1.5) < 1e-6)

# --- Build v001
cams = api.list_shot_cameras(H, FILM, "EAP_010", "EAP_010_010")
V1 = api.version_id("scout", 1)
cmds.file(new=True, force=True)
api.ensure_maya_project(shot)
cmds.rename(cmds.camera()[0], "camera1")    # the student's own camera1, to be kept
done, warn, old = api.build_asset(shot, cams[0], V1)
print("   ", done)
g = "|EAP_010_010_cam_GRP"
check("build: group with camera1 + camera1_DATA",
      cmds.objExists(g + "|camera1") and cmds.objExists(g + "|camera1_DATA"))
check("build: student's camera1 kept as camera1_old", cmds.objExists("|camera1_old"))
check("build: shot_camera finds it by the group stamp", api.shot_camera() == (g + "|camera1", V1))
check("build: keys drive the data node",
      cmds.nodeType(cmds.listConnections(g + "|camera1_DATA.cam_translateX", source=True,
                                         destination=False)[0])
      .startswith("animCurve"))
check("build: camera1 driven 1:1 by the data node",
      cmds.listConnections(g + "|camera1.translateX", source=True, plugs=True) == ["camera1_DATA.cam_translateX"]
      and cmds.listConnections(g + "|camera1|cameraShape1.focalLength", source=True, plugs=True)
      == ["camera1_DATA.camShape_focalLength"])
cmds.currentTime(10)
check("build: camera plays (tx 10, ry 45, focal 50)",
      abs(cmds.getAttr(g + "|camera1.tx") - 10) < 1e-3 and abs(cmds.getAttr(g + "|camera1.ry") - 45) < 1e-3
      and abs(cmds.getAttr(g + "|camera1|cameraShape1.focalLength") - 50) < 1e-3)
check("build: camera1 is the only camera1 (playblast/shotSub by name still work)",
      len(cmds.ls("camera1")) == 1)
check("build: no reference", not cmds.ls(type="reference") or cmds.ls(type="reference") == ["sharedReferenceNode"])


def blocked(fn):
    try:
        fn(); return False
    except RuntimeError:
        return True


curve = cmds.listConnections(g + "|camera1_DATA.cam_translateX", source=True, destination=False)[0]
check("locked: data node attribute", blocked(lambda: cmds.setAttr(g + "|camera1_DATA.cam_translateX", 3)))
check("locked: group can't be moved", blocked(lambda: cmds.setAttr(g + ".tx", 3)))
check("locked: keys can't be moved", blocked(lambda: cmds.keyframe(curve, edit=True, relative=True,
                                                                   valueChange=1)))
check("locked: curve can't be deleted", blocked(lambda: cmds.delete(curve)))
done, warn, old = api.build_asset(shot, cams[0], V1)
check("rebuild same version: already up to date", done[-1] == "already up to date")
layout_built = os.path.join(shot, "scenes", "built.ma")
cmds.file(rename=layout_built); cmds.file(save=True, type="mayaAscii")
cmds.file(layout_built, open=True, force=True)
check("save + reopen: still driven and locked",
      cmds.listConnections(g + "|camera1.translateX", source=True, plugs=True) == ["camera1_DATA.cam_translateX"]
      and blocked(lambda: cmds.setAttr(g + "|camera1_DATA.cam_translateX", 3)))

# --- Publish knows the group and data node are part of the camera
import publishTool_anim as panim
check("selecting the group or camera1_DATA means the camera",
      pcam.camera_in_group(g) == g + "|camera1" and pcam.camera_in_group(g + "|camera1_DATA") == g + "|camera1"
      and pcam.camera_in_group("|camera1_old") is None)
try:
    panim.classify([g + "|camera1_DATA"])
    refused = False
except api.pub.PublishError as e:
    refused = "Camera row" in str(e)
check("animation publish refuses camera1_DATA (it goes in a Camera row)", refused)

# --- Republish from the built scene (an animator's camera publish)
plan2 = publish(shot, g + "|camera1", layout_built)
check("republish from a built shot: the scene's group is back as it was",
      cmds.objExists(g + "|camera1") and not cmds.ls("*_publishing"))
check("republish: v002", plan2["version"] == 2)

# --- Build v002: the v001 group moves aside
cams = api.list_shot_cameras(H, FILM, "EAP_010", "EAP_010_010")
V2 = api.version_id("scout", 2)
done, warn, old = api.build_asset(shot, cams[0], V2)
print("   ", done)
check("update: new group is v002", api.shot_camera() == (g + "|camera1", V2))
check("update: v001 kept as EAP_010_010_cam_GRP_old > camera1_old1 + data",
      cmds.objExists("|EAP_010_010_cam_GRP_old|camera1_old1")
      and cmds.objExists("|EAP_010_010_cam_GRP_old|camera1_old1_DATA"))
cmds.currentTime(10)
check("update: v002 plays the same move", abs(cmds.getAttr(g + "|camera1.tx") - 10) < 1e-3)

# --- Old-format publishes are left out of the list
old_dir = os.path.join(api.shot_folder(H, FILM, "EAP_010", "EAP_010_010"), "scenes", "scout")
for name in ("EAP_010_010_scout_cam_v009.ma", "EAP_010_010_scout_camAnim_v009.ma"):
    shutil.copy2(plan["dest"], os.path.join(old_dir, name))
json.dump({"camera": "shotCam", "curves": {}}, open(os.path.join(old_dir, "EAP_010_010_scout_camAnim_v009.json"), "w"))
cams = api.list_shot_cameras(H, FILM, "EAP_010", "EAP_010_010")
check("old three-file format (no group) not listed", api.version_id("scout", 9) not in cams[0]["versions"])

# --- Another shot gets its own group name
cam, scene = layout_scene(other, 3)
plan3 = publish(other, cam, scene)
check("another shot: EAP_020_030_cam_GRP", json.load(open(plan3["map_dest"]))["group"] == "EAP_020_030_cam_GRP")
cmds.file(new=True, force=True)
cams = api.list_shot_cameras(H, FILM, "EAP_020", "EAP_020_030")
api.build_asset(other, cams[0], V1)
check("another shot: built under its own group", cmds.objExists("|EAP_020_030_cam_GRP|camera1"))

print("\n%d/%d passed" % (sum(ok for _, ok in results), len(results)))
for root, dirs, files in os.walk(base):
    for f in files:
        os.chmod(os.path.join(root, f), stat.S_IWRITE)
shutil.rmtree(base, ignore_errors=True)
maya.standalone.uninitialize()
