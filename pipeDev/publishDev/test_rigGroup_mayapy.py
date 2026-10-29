r"""Headless test: rig publish group + MetaHuman DNA (spec §4, 2026-10-20).

    "C:\Program Files\Autodesk\Maya2025\bin\mayapy.exe" pipeDev/publishDev/test_rigGroup_mayapy.py

The published rig sits in a stamped <asset>_rig_GRP (pipe icon, locked)
listing its textures, DNA files and plug-ins; DNA files are collected from
wherever they are; DNA nodes can't read $PIPE_SCRATCH, so Build and the
after-open hook fill in the real path for the drive. The MetaHuman DNA node
needs its plug-in, so a "network" node with a dnaFilePath attribute stands
in for it. Throwaway folders in %TEMP%; nothing real is touched.
"""
import os, sys, json, stat, shutil, tempfile

import maya.standalone
maya.standalone.initialize()
import maya.cmds as cmds

DEV = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(DEV, "publishDev"), os.path.join(DEV, "buildDev")]
import publishTool_api as api
import publishTool_textures as tex
import rig_rules
import buildTool_api as build
import pipeEnv

base = tempfile.mkdtemp(prefix="riggrp_")
H, S = os.path.join(base, "H"), os.path.join(base, "S")
FILM = "NWF_SHF"
_cfg = os.path.join(base, "pipeline_config.json")
api._config_path = lambda: _cfg
api.set_root(api.H_DRIVE, H)
api.set_root(api.SCRATCH, S)
api.save_config(dict(api.load_config(), publish_as="scout"))
api.artist_name = lambda login: "Scout Test"
os.environ.pop(pipeEnv.VAR, None)
rig_rules.METAHUMAN["dna_node_type"] = "network"      # stands in for embeddedNodeRL4
results = []
n = lambda p: os.path.normcase(os.path.normpath(p))


def check(name, ok):
    results.append(bool(ok)); print(("PASS " if ok else "FAIL ") + name)


def touch(path, data=b"x"):
    if not os.path.isdir(os.path.dirname(path)):
        os.makedirs(os.path.dirname(path))
    open(path, "wb").write(data)
    return path


asset_s = os.path.join(S, FILM, "maya", "assets", "character", "scout")
os.makedirs(os.path.join(H, FILM, "maya", "assets", "character", "scout", "scenes"))
os.makedirs(os.path.join(asset_s, "scenes")); open(os.path.join(asset_s, "workspace.mel"), "w").write("")
shot = build.shot_folder(S, FILM, "EAP_010", "EAP_010_010")
os.makedirs(os.path.join(shot, "scenes")); open(os.path.join(shot, "workspace.mel"), "w").write("")
os.makedirs(build.shot_folder(H, FILM, "EAP_010", "EAP_010_010"))
skin = touch(os.path.join(asset_s, "sourceimages", "skin.png"))
dump = os.path.join(base, "Downloads", "scout_from_unreal")     # off-pipe dump spot
head_dna = touch(os.path.join(dump, "head.dna"), b"head dna")
body_dna = touch(os.path.join(dump, "body.dna"), b"body dna")


def rig_scene():
    cmds.file(new=True, force=True)
    cmds.workspace(asset_s, openWorkspace=True)
    root = cmds.group(empty=True, name="scout_rig")
    cmds.setAttr(root + ".ty", 2)                       # its own values must survive
    geo = cmds.parent(cmds.polyCube(name="body_geo")[0], root)[0]
    ctl = cmds.parent(cmds.circle(name="root_ctl")[0], root)[0]
    sh = cmds.shadingNode("lambert", asShader=True, name="skin_MTL")
    sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name="skinSG")
    cmds.connectAttr(sh + ".outColor", sg + ".surfaceShader")
    f = cmds.shadingNode("file", asTexture=True, name="skin_file")
    cmds.setAttr(f + ".fileTextureName", skin, type="string")
    cmds.connectAttr(f + ".outColor", sh + ".color")
    cmds.sets(geo, edit=True, forceElement=sg)
    for name, path in (("head_rl4", head_dna), ("body_rl4", body_dna)):
        node = cmds.createNode("network", name=name)
        cmds.addAttr(node, longName="dnaFilePath", dataType="string")
        cmds.setAttr(node + ".dnaFilePath", path, type="string")
    cmds.sets([geo], name=api.CACHE_SET)
    cmds.sets([ctl], name=api.BODY_CONTROLS_SET)
    scene = os.path.join(asset_s, "scenes", "rig_work.ma")
    cmds.file(rename=scene); cmds.file(save=True, type="mayaAscii")
    return scene


def publish(objects):
    scene = cmds.file(query=True, sceneName=True)
    plan = api.plan_publish(scene, H, S, "rig")
    plan.update(objects=objects, sg_asset={"type": "Asset", "id": 99}, cache_set=api.CACHE_SET,
                control_sets={"body": api.BODY_CONTROLS_SET, "face": None})
    plan["set_uuids"] = cmds.ls([api.CACHE_SET, api.BODY_CONTROLS_SET], uuid=True)
    api.export_rig_to_h_drive(objects, plan, scene, tex.collect(objects), tex.collect_dna())
    return plan


# --- DNA found wherever it is; missing DNA refuses
rig_scene()
dna = tex.collect_dna()
check("DNA collected from an off-pipe dump folder",
      sorted(n(e["files"][0]) for e in dna) == sorted([n(head_dna), n(body_dna)]))
cmds.setAttr("head_rl4.dnaFilePath", os.path.join(dump, "gone.dna"), type="string")
try:
    tex.collect_dna(); refused = False
except api.PublishError as e:
    refused = "head_rl4" in str(e) and "missing" in str(e)
check("missing DNA -> refused, names the node", refused)

# --- publish (selected rig)
rig_scene()
before = (cmds.listRelatives("scout_rig", parent=True), cmds.getAttr("scout_rig.ty"),
          cmds.getAttr("head_rl4.dnaFilePath"), cmds.getAttr("skin_file.fileTextureName"))
plan = publish(["scout_rig"])
print("   ", plan.get("warnings"))
after = (cmds.listRelatives("scout_rig", parent=True), cmds.getAttr("scout_rig.ty"),
         cmds.getAttr("head_rl4.dnaFilePath"), cmds.getAttr("skin_file.fileTextureName"))
check("working scene as it was (no group, rig root at the top, paths unchanged)",
      before == after and not cmds.objExists("scout_rig_GRP"))
folder = plan["textures"]["folder"]
check("H: textures and DNA in the version folder (dna\\ for DNA)",
      os.path.isfile(os.path.join(folder, "skin.png"))
      and os.path.isfile(os.path.join(folder, "dna", "head.dna"))
      and os.path.isfile(os.path.join(folder, "dna", "body.dna")))
check("summary lists the DNA nodes and files (to spot a head/body mix-up)",
      any("head_rl4 -> head.dna" in w for w in plan.get("warnings", [])))

cmds.file(new=True, force=True)
cmds.file(plan["dest"], open=True, force=True)
G = "|scout_rig_GRP"
check("published file: rig root under scout_rig_GRP, its values kept",
      cmds.objExists(G + "|scout_rig") and abs(cmds.getAttr(G + "|scout_rig.ty") - 2) < 1e-6)
check("published file: RMIT_publishSet made by Publish, holding cache_SET + body_controls_SET",
      sorted(cmds.sets(api.PUBLISH_SET, query=True) or []) == ["body_controls_SET", "cache_SET"])
check("group is a dagContainer, the rig root a member of it",
      cmds.nodeType(G) == "dagContainer"
      and cmds.container(query=True, findContainer=[G + "|scout_rig"]) == "scout_rig_GRP")
check("group: pipe icon, locked at the origin",
      cmds.getAttr(G + ".iconName") == api.PIPE_ICON and cmds.getAttr(G + ".tx", lock=True))
stamp = dict((a, cmds.getAttr("%s.%s" % (G, a))) for a in cmds.listAttr(G, userDefined=True))
check("stamp: asset id, department, version, artist",
      stamp["pipe_sgAssetId"] == 99 and stamp["pipe_department"] == "rig"
      and stamp["pipe_version"] == 1 and stamp["pipe_artistName"] == "Scout Test")
dna_list = json.loads(stamp["pipe_dna"])
print("    pipe_dna:", dna_list)
check("stamp: DNA nodes with file name, where it came from, portable path",
      sorted(d["node"] for d in dna_list) == ["body_rl4", "head_rl4"]
      and all(d["published"].startswith("$PIPE_SCRATCH/NWF_SHF/maya/publish/assets/character/"
                                        "scout/sourceimages/scout/scout_scout_rig_v001/dna/")
              for d in dna_list)
      and any(n(d["original"]) == n(head_dna) for d in dna_list))
textures = json.loads(stamp["pipe_textures"])
check("stamp: textures with original and published path",
      textures[0]["node"] == "skin_file" and textures[0]["files"] == ["skin.png"]
      and n(textures[0]["original"]) == n(skin))
check("stamp: plug-ins and rules version recorded",
      isinstance(json.loads(stamp["pipe_plugins"]), list) and stamp["pipe_rigRulesVersion"] == rig_rules.VERSION)
check("stamp locked", cmds.getAttr(G + ".pipe_dna", lock=True))
check("published DNA path = the publisher's real scratch path (DNA can't read $PIPE_SCRATCH)",
      n(cmds.getAttr("head_rl4.dnaFilePath")) == n(os.path.join(
          S, FILM, "maya", "publish", "assets", "character", "scout", "sourceimages", "scout",
          "scout_scout_rig_v001", "dna", "head.dna")))

# --- a rig publishes its selected top group only (user, 2026-10-30)
rig_scene()
cmds.pointLight(name="stray_light")
cmds.camera(name="extra_cam")
cmds.group(empty=True, name="other_rig")


def selection_refused(objects):
    try:
        api.check_rig_selection(objects)
    except api.PublishError as e:
        return "top group" in str(e)
    return False


check("rig: nothing selected (whole scene) refused", selection_refused([]))
check("rig: two top groups refused", selection_refused(["scout_rig", "other_rig"]))
check("rig: a shape selected refused", selection_refused(["body_geoShape"]))
check("rig: the top group accepted", not selection_refused(["scout_rig"]))
check("rig: the top group plus something inside it accepted",
      not selection_refused(["scout_rig", "body_geo"]))
calls = []
real_plan, real_sg = api.plan_publish, api.find_shotgrid_asset
api.plan_publish = lambda *a, **k: {"dest": os.path.join(base, "never.ma"), "h_folder": base, "ext": ".ma"}
api.find_shotgrid_asset = lambda *a: calls.append("shotgrid")
try:
    api.publish("x.ma", base, base, "rig")
    check("publish(): whole-scene rig refused", False)
except api.PublishError as e:
    check("publish(): whole-scene rig refused, before ShotGrid", "top group" in str(e) and calls == [])
api.plan_publish, api.find_shotgrid_asset = real_plan, real_sg

# --- selection rig publish: an existing node with the group's name steps
# aside, and stray nodes outside the group stay behind
cmds.group(empty=True, name="scout_rig_GRP")
plan2 = publish(["scout_rig"])
check("selection: published, and the scene's own scout_rig_GRP is back",
      os.path.isfile(plan2["dest"]) and cmds.objExists("|scout_rig_GRP")
      and cmds.listRelatives("scout_rig", parent=True) is None)
cmds.file(new=True, force=True); cmds.file(plan2["dest"], open=True, force=True)
check("selection: rig under the group in the file", cmds.objExists("|scout_rig_GRP|scout_rig"))
check("selection: stray light, camera and other rig left behind",
      not cmds.ls("stray_light*") and not cmds.ls("extra_cam*") and not cmds.ls("other_rig"))

# --- a failed export leaves the scene as it was and no files behind
rig_scene()
real_export = api.export_to_h_drive
api.export_to_h_drive = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("export failed"))
try:
    publish(["scout_rig"])
except RuntimeError:
    pass
api.export_to_h_drive = real_export
check("failed export: rig root back at the top, no group, DNA path unchanged",
      cmds.listRelatives("scout_rig", parent=True) is None and not cmds.objExists("scout_rig_GRP")
      and n(cmds.getAttr("head_rl4.dnaFilePath")) == n(head_dna))
check("failed export: no version folder left",
      not os.path.exists(os.path.join(os.path.dirname(folder), "scout_scout_rig_v003")))

# --- Build: DNA comes with the rig and points at this drive
rig = [p for p in build.list_published(H, FILM) if p["code"] == "rig"][0]
cmds.file(new=True, force=True)
build.ensure_maya_project(shot)
done, warn, old = build.build_asset(shot, rig, build.version_id("scout", 1))
print("   ", done)
pulled_dna = os.path.join(S, FILM, "maya", "publish", "assets", "character", "scout", "sourceimages",
                          "scout", "scout_scout_rig_v001", "dna", "head.dna")
check("Build pulled the DNA into scratch publish\\", os.path.isfile(pulled_dna))
check("referenced rig is under scout_rig:scout_rig_GRP",
      cmds.objExists("scout_rig:scout_rig_GRP|scout_rig:scout_rig"))
check("DNA node points at the pulled file", n(cmds.getAttr("scout_rig:head_rl4.dnaFilePath")) == n(pulled_dna))
anim = os.path.join(shot, "scenes", "anim.ma")
cmds.file(rename=anim); cmds.file(save=True, type="mayaAscii")

# --- The film moves to another drive: the after-open hook follows it
pipeEnv.install()
S2 = os.path.join(base, "S2")
cmds.file(new=True, force=True)
shutil.copytree(os.path.join(S, FILM), os.path.join(S2, FILM))
cmds.file(anim.replace(S, S2), open=True, force=True)
check("on the new drive the DNA node points at the new drive's file (after-open hook)",
      n(cmds.getAttr("scout_rig:head_rl4.dnaFilePath")) == n(pulled_dna.replace(S, S2)))

print("\n%d/%d passed" % (sum(results), len(results)))
for attr in ("_pipeEnv_callback_id", "_pipeEnv_after_open_id"):
    if hasattr(sys, attr):
        import maya.api.OpenMaya as om
        om.MMessage.removeCallback(getattr(sys, attr)); delattr(sys, attr)
for root, dirs, files in os.walk(base):
    for f in files:
        os.chmod(os.path.join(root, f), stat.S_IWRITE)
shutil.rmtree(base, ignore_errors=True)
maya.standalone.uninitialize()
