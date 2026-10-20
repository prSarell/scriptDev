r"""Headless test: a rig publish carries its textures, and Build pulls them
into shots (spec §4 "Texture workflow through rigging", 2026-10-20).

    "C:\Program Files\Autodesk\Maya2025\bin\mayapy.exe" pipeDev/publishDev/test_rigTextures_mayapy.py

Throwaway folders in %TEMP% and a throwaway drive-settings file; never
touches the real H drive, scratch drive or Maya prefs. The "textures" are
small dummy files: only copying and paths are tested, not images.
"""
import os, sys, stat, shutil, tempfile

import maya.standalone
maya.standalone.initialize()
import maya.cmds as cmds

DEV = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(DEV, "publishDev"), os.path.join(DEV, "buildDev")]
import publishTool_api as api
import publishTool_textures as tex
import buildTool_api as build
import pipeEnv

base = tempfile.mkdtemp(prefix="rigtex_")
H, S = os.path.join(base, "H"), os.path.join(base, "S")
FILM = "NWF_SHF"
_cfg = os.path.join(base, "pipeline_config.json")
api._config_path = lambda: _cfg
api.set_root(api.H_DRIVE, H)
api.set_root(api.SCRATCH, S)
api.save_config(dict(api.load_config(), publish_as="scout"))
os.environ.pop(pipeEnv.VAR, None)
results = []


def check(name, ok):
    results.append(bool(ok)); print(("PASS " if ok else "FAIL ") + name)


def touch(path, data=b"tex"):
    if not os.path.isdir(os.path.dirname(path)):
        os.makedirs(os.path.dirname(path))
    with open(path, "wb") as f:
        f.write(data)
    return path


# Folders: the asset on H and scratch, one shot.
asset_s = os.path.join(S, FILM, "maya", "assets", "character", "scout")
os.makedirs(os.path.join(H, FILM, "maya", "assets", "character", "scout", "scenes"))
os.makedirs(os.path.join(asset_s, "scenes"))
open(os.path.join(asset_s, "workspace.mel"), "w").write("")
shot = build.shot_folder(S, FILM, "EAP_010", "EAP_010_010")
os.makedirs(os.path.join(shot, "scenes")); open(os.path.join(shot, "workspace.mel"), "w").write("")
os.makedirs(build.shot_folder(H, FILM, "EAP_010", "EAP_010_010"))

# Textures in the working asset's sourceimages: a plain one with a .tx
# beside it, UDIM tiles, and a second skin.png from another folder.
src = os.path.join(asset_s, "sourceimages")
skin = touch(os.path.join(src, "skin.png"), b"skin")
touch(os.path.join(src, "skin.tx"), b"skin tx")
tiles = [touch(os.path.join(src, "body.%d.png" % t)) for t in (1001, 1002)]
other_skin = touch(os.path.join(base, "elsewhere", "skin.png"), b"other skin")
prop_tex = touch(os.path.join(src, "prop.png"))


def shader(name, geo, path, udim=False):
    sh = cmds.shadingNode("lambert", asShader=True, name=name + "_MTL")
    sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=name + "SG")
    cmds.connectAttr(sh + ".outColor", sg + ".surfaceShader")
    f = cmds.shadingNode("file", asTexture=True, name=name + "_file")
    cmds.setAttr(f + ".fileTextureName", path, type="string")
    if udim:
        cmds.setAttr(f + ".uvTilingMode", 3)
    cmds.connectAttr(f + ".outColor", sh + ".color")
    cmds.sets(geo, edit=True, forceElement=sg)
    return f


def rig_scene():
    cmds.file(new=True, force=True)
    cmds.workspace(asset_s, openWorkspace=True)
    root = cmds.group(empty=True, name="scout_rig")
    head = cmds.parent(cmds.polyCube(name="head_geo")[0], root)[0]
    body = cmds.parent(cmds.polyCube(name="body_geo")[0], root)[0]
    eye = cmds.parent(cmds.polySphere(name="eye_geo")[0], root)[0]
    shader("skin", head, "sourceimages/skin.png")              # project-relative
    shader("body", body, tiles[0], udim=True)                  # UDIM tiles
    shader("eye", eye, other_skin)                             # clashing name
    prop = cmds.polyCube(name="prop_geo")[0]                   # not in the rig
    shader("prop", prop, prop_tex)
    scene = os.path.join(asset_s, "scenes", "rig_work.ma")
    cmds.file(rename=scene); cmds.file(save=True, type="mayaAscii")
    return scene


# --- what a selected-objects rig publish carries
scene = rig_scene()
entries = tex.collect(["scout_rig"])
by = dict((e["node"].split("|")[-1], e) for e in entries)
check("only the rig's shaders' textures (not the prop beside it)",
      sorted(by) == ["body_file", "eye_file", "skin_file"])
check("project-relative path found, with its .tx",
      sorted(os.path.basename(f) for f in by["skin_file"]["files"]) == ["skin.png", "skin.tx"])
check("UDIM: every tile", sorted(os.path.basename(f) for f in by["body_file"]["files"])
      == ["body.1001.png", "body.1002.png"])
check("whole scene: every texture node", len(tex.collect([])) == 4)

# --- missing texture refuses
os.rename(other_skin, other_skin + ".gone")
try:
    tex.collect(["scout_rig"]); refused = False
except api.PublishError as e:
    refused = "eye_file" in str(e) and "missing" in str(e)
check("missing texture -> refused, names the node", refused)
os.rename(other_skin + ".gone", other_skin)

# --- publish: textures to H in the version folder, paths rewritten in the file only
plan = api.plan_publish(scene, H, S, "rig")
plan["objects"] = ["scout_rig"]
before = dict((n, cmds.getAttr(n + ".fileTextureName")) for n in cmds.ls(type="file"))
with tex.PublishedTextures(entries, plan):
    api.export_to_h_drive(["scout_rig"], plan)
folder = plan["textures"]["folder"]
check("textures in <asset>\\sourceimages\\<login>\\<published name>",
      folder == os.path.join(H, FILM, "maya", "assets", "character", "scout", "sourceimages",
                             "scout", "scout_scout_rig_v001"))
names = sorted(os.path.relpath(os.path.join(d, f), folder).replace("\\", "/")
               for d, _, fs in os.walk(folder) for f in fs)
print("   ", names)
check("all files copied; the clashing skin.png in its own subfolder",
      len(names) == 5 and "skin.png" in names and "skin.tx" in names and "body.1002.png" in names
      and any(n.endswith("/skin.png") for n in names))
check("published textures are read-only", not os.access(os.path.join(folder, "skin.png"), os.W_OK))
check("working scene's texture paths unchanged",
      dict((n, cmds.getAttr(n + ".fileTextureName")) for n in cmds.ls(type="file")) == before)
cmds.file(new=True, force=True)
cmds.file(plan["dest"], open=True, force=True)
paths = dict((n, cmds.getAttr(n + ".fileTextureName")) for n in cmds.ls(type="file"))
print("   ", paths)
check("published file points at $PIPE_SCRATCH/.../publish/.../sourceimages/scout/scout_scout_rig_v001/",
      all(p.startswith("$PIPE_SCRATCH/NWF_SHF/maya/publish/assets/character/scout/sourceimages/"
                       "scout/scout_scout_rig_v001/") for p in paths.values()))
check("UDIM node still on its tile pattern", paths["body_file"].endswith("/body.1001.png")
      and cmds.getAttr("body_file.uvTilingMode") == 3)

# --- a failed export leaves no textures behind and the scene as it was
scene = rig_scene()
plan2 = api.plan_publish(scene, H, S, "rig")
skin_before = cmds.getAttr("skin_file.fileTextureName")
try:
    with tex.PublishedTextures(tex.collect(["scout_rig"]), plan2):
        raise RuntimeError("export failed")
except RuntimeError:
    pass
check("failed export: version texture folder removed", not os.path.exists(tex.texture_folder(plan2)))
check("failed export: scene paths put back", cmds.getAttr("skin_file.fileTextureName") == skin_before)

# --- Build pulls the rig with its textures into scratch publish\
rig = [p for p in build.list_published(H, FILM) if p["code"] == "rig"][0]
cmds.file(new=True, force=True)
build.ensure_maya_project(shot)
done, warn, old = build.build_asset(shot, rig, build.version_id("scout", 1))
print("   ", done)
pulled = os.path.join(S, FILM, "maya", "publish", "assets", "character", "scout", "sourceimages",
                      "scout", "scout_scout_rig_v001")
check("Build pulled the textures into scratch publish\\",
      os.path.isfile(os.path.join(pulled, "skin.png")) and os.path.isfile(os.path.join(pulled, "body.1002.png")))
ns_file = [n for n in cmds.ls(type="file") if n.endswith("skin_file")][0]
p = cmds.getAttr(ns_file + ".fileTextureName")
check("in the shot the texture path resolves on this drive",
      p.startswith("$PIPE_SCRATCH/") and os.path.isfile(os.path.expandvars(p)))
pulled_version = os.path.join(S, FILM, "maya", "publish", "assets", "character", "scout", "scenes",
                              "scout", "scout_scout_rig_v001.ma")
check("clearing the version takes its textures too",
      len(build.version_files(pulled_version)) == 1 + 5)

# --- Repair after a wipe of publish\: textures come back with the rig
cmds.file(rename=os.path.join(shot, "scenes", "anim.ma")); cmds.file(save=True, type="mayaAscii")
cmds.file(new=True, force=True)
for d, _, fs in os.walk(os.path.join(S, FILM, "maya", "publish")):
    for f in fs:
        os.chmod(os.path.join(d, f), stat.S_IWRITE)
shutil.rmtree(os.path.join(S, FILM, "maya", "publish"))
cmds.file(os.path.join(shot, "scenes", "anim.ma"), open=True, force=True)
fixed, not_fixed = build.repair_scene(H)
print("   ", fixed, not_fixed)
check("repair brings back the rig link and its textures",
      not not_fixed and os.path.isfile(os.path.join(pulled, "skin.png")))

# --- publish() refuses a rig with a missing texture before ShotGrid/playblast
calls = []
api.find_shotgrid_asset = lambda *a: calls.append("shotgrid")
api.playblast_frames = lambda *a, **k: calls.append("playblast")
api.check_script_nodes = lambda: None
scene = rig_scene()
cmds.sets(["head_geo", "body_geo"], name=api.CACHE_SET)
cmds.sets([cmds.parent(cmds.circle(name="root_ctl")[0], "scout_rig")[0]], name=api.BODY_CONTROLS_SET)
cmds.file(save=True, type="mayaAscii")
os.rename(other_skin, other_skin + ".gone")
try:
    api.publish(scene, H, S, "rig", objects=["scout_rig"])
    refused = False
except api.PublishError as e:
    refused = "missing" in str(e)
check("publish() refuses a missing texture before ShotGrid or playblast", refused and calls == [])

print("\n%d/%d passed" % (sum(results), len(results)))
for root, dirs, files in os.walk(base):
    for f in files:
        os.chmod(os.path.join(root, f), stat.S_IWRITE)
shutil.rmtree(base, ignore_errors=True)
maya.standalone.uninitialize()
