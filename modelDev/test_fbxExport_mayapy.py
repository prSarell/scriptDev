"""
mayapy test for fbxExport: run with
    mayapy modelDev/test_fbxExport_mayapy.py
Works in a temp folder laid out like a film (<film>\\maya, <film>\\substancePainter).
"""
import os, sys, shutil, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import maya.standalone; maya.standalone.initialize()
import maya.cmds as cmds
import fbxExport as fx

results = []


def check(label, ok):
    results.append(bool(ok))
    print("%s  %s" % ("PASS" if ok else "FAIL", label))


def refused(fn, *a, **k):
    try:
        fn(*a, **k)
    except fx.ExportError as e:
        return str(e)
    return ""


base = tempfile.mkdtemp(prefix="fbxExport_")
film = os.path.join(base, "NWF_SHF")
asset_dir = os.path.join(film, "maya", "assets", "environment", "hillShed", "scenes", "model",
                         "e131988")
shot_dir = os.path.join(film, "maya", "sequences", "SEQ010", "SEQ010_160", "scenes", "layout",
                        "e131988")
for d in (asset_dir, shot_dir, os.path.join(film, "substancePainter")):
    os.makedirs(d)
sp_asset = os.path.join(film, "substancePainter", "assets", "environment", "hillShed")
sp_shot = os.path.join(film, "substancePainter", "sequences", "SEQ010", "SEQ010_160")

try:
    # --- where it goes -------------------------------------------------------
    scene = os.path.join(asset_dir, "hillShed_model_v001.ma")
    check("asset scene -> substancePainter\\assets\\<type>\\<asset>",
          fx.target(scene) == (sp_asset, "hillShed", "assets"))
    check("shot scene -> substancePainter\\sequences\\<seq>\\<shot>",
          fx.target(os.path.join(shot_dir, "SEQ010_160_layout_v001.ma"))
          == (sp_shot, "SEQ010_160", "sequences"))
    check("a scene outside assets / sequences is refused",
          "isn't in an asset or shot folder" in refused(fx.target, os.path.join(base, "x.ma")))
    check("a drive-root film works (D:\\NWF_SHF\\...)",
          fx.target("D:\\NWF_SHF\\maya\\assets\\environment\\hillShed\\scenes\\a.ma")[0]
          == "D:\\NWF_SHF\\substancePainter\\assets\\environment\\hillShed")

    # --- an asset --------------------------------------------------------------
    cmds.file(new=True, force=True)
    cmds.file(rename=scene); cmds.file(save=True, type="mayaAscii")
    check("unsaved / nothing picked: refused",
          "Pick the geometry" in refused(fx.export, selection=[]))
    shed = cmds.polyCube(name="shed_GEO")[0]
    grp = cmds.group(shed, name="shed_GRP")
    light = cmds.pointLight(name="sun")
    light_t = cmds.listRelatives(light, parent=True)[0]
    cmds.select("shed_GEO.vtx[0]", light_t)        # a component counts as its mesh
    roots, cams, skipped = fx.picked()
    check("picked: the mesh's top picked transform, the light left out",
          [r.split("|")[-1] for r in roots] == ["shed_GEO"] and not cams
          and [n.split("|")[-1] for n, _ in skipped] == [light_t])
    path, roots, cams, skipped = fx.export(selection=[grp, light_t])
    check("asset export: hillShed_v001.fbx in its Substance Painter folder",
          path == os.path.join(sp_asset, "hillShed_v001.fbx") and os.path.isfile(path))
    check("... the selection is put back", cmds.ls(selection=True) == ["shed_GEO.vtx[0]", light_t]
          or cmds.ls(selection=True) == [])
    path2 = fx.export(selection=[grp])[0]
    check("again: v002, v001 kept",
          path2.endswith("hillShed_v002.fbx") and os.path.isfile(path))
    with open(path, "rb") as f:
        data = f.read()
    check("... the FBX holds the mesh, not the light",
          b"shed_GEO" in data and b"sun" not in data)

    # --- an asset scene with a camera driven by a data node in a locked group (a Build
    # shot camera: SEQ010_120_cam_GRP|camera1, user 2026-11-24) -----------------
    cam_grp = cmds.group(empty=True, name="SEQ010_120_cam_GRP")
    for a in ("tx", "ty", "tz", "rx", "ry", "rz"):
        cmds.setAttr(cam_grp + "." + a, lock=True)
    asset_cam = cmds.parent(cmds.camera(name="turnCam")[0], cam_grp)[0]
    data = cmds.createNode("transform", name="camera1_DATA")   # Build: keys live here
    cmds.setKeyframe(data, attribute="ry", time=1, value=0)
    cmds.setKeyframe(data, attribute="ry", time=24, value=90)
    cmds.connectAttr(data + ".ry", asset_cam + ".ry")
    cmds.playbackOptions(minTime=1, maxTime=24)
    path3 = fx.export(selection=[cam_grp, grp])[0]
    cmds.file(save=True, force=True)
    cmds.file(new=True, force=True)
    cmds.file(path3, i=True, type="FBX", ignoreVersion=True)
    back = [t for t in cmds.ls("turnCam*", type="transform")]
    keys = cmds.keyframe(back, query=True, timeChange=True) if back else None
    check("asset scene: the camera's animation comes back from the FBX, baked 1-24",
          back and keys and min(keys) == 1 and max(keys) == 24
          and round(cmds.getAttr(back[0] + ".ry", time=24), 2) == 90)

    # --- a shot, with an animated camera ---------------------------------------
    cmds.file(new=True, force=True)
    cmds.file(rename=os.path.join(shot_dir, "SEQ010_160_layout_v001.ma"))
    cmds.file(save=True, type="mayaAscii")
    cam = cmds.camera(name="shotCam")[0]
    cmds.setKeyframe(cam, attribute="tx", time=1, value=0)
    cmds.setKeyframe(cam, attribute="tx", time=10, value=10)
    cmds.playbackOptions(minTime=1, maxTime=10)
    ground = cmds.polyPlane(name="ground_GEO")[0]
    path, roots, cams, skipped = fx.export(selection=[cam, ground])
    check("shot export: SEQ010_160_v001.fbx with the camera",
          path == os.path.join(sp_shot, "SEQ010_160_v001.fbx") and os.path.isfile(path)
          and [c.split("|")[-1] for c in cams] == ["shotCam1"])
    with open(path, "rb") as f:
        data = f.read()
    check("... the camera and its animation are in the FBX",
          b"shotCam1" in data and b"AnimationCurve" in data)

    # --- a film without a substancePainter folder --------------------------------
    other = os.path.join(base, "OTHER", "maya", "assets", "prop", "cup", "scenes")
    os.makedirs(other)
    cmds.file(new=True, force=True)
    cmds.file(rename=os.path.join(other, "cup.ma")); cmds.file(save=True, type="mayaAscii")
    cup = cmds.polyCube(name="cup_GEO")[0]
    check("no substancePainter folder in the film: refused",
          "no substancePainter folder" in refused(fx.export, selection=[cup]))
finally:
    cmds.file(new=True, force=True)
    shutil.rmtree(base, ignore_errors=True)

print("\n%d/%d passed" % (sum(results), len(results)))
maya.standalone.uninitialize()
sys.exit(0 if all(results) else 1)
