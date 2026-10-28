r"""Headless test: a model publish carries the textures its shaders use, like
the rig's (user, 2026-10-28: "the pipe should be able to find their file
location by looking at the models shader networks"); a model with no
textures publishes as before.

    "C:\Program Files\Autodesk\Maya2025\bin\mayapy.exe" pipeDev/publishDev/test_modelTextures_mayapy.py

Throwaway folders in %TEMP% and a throwaway drive-settings file; never
touches the real H drive, scratch drive or Maya prefs. The "textures" are
small dummy files: only copying and paths are tested, not images.
"""
import os, sys, stat, shutil, tempfile, json

import maya.standalone
maya.standalone.initialize()
import maya.cmds as cmds

DEV = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(DEV, "publishDev"), os.path.join(DEV, "buildDev")]
import publishTool_api as api
import publishTool_textures as tex
import buildTool_api as build
import pipeEnv

base = tempfile.mkdtemp(prefix="modeltex_")
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


asset_s = os.path.join(S, FILM, "maya", "assets", "prop", "backpack")
os.makedirs(os.path.join(H, FILM, "maya", "assets", "prop", "backpack", "scenes"))
os.makedirs(os.path.join(asset_s, "scenes"))
open(os.path.join(asset_s, "workspace.mel"), "w").write("")
shot = build.shot_folder(S, FILM, "EAP_010", "EAP_010_010")
os.makedirs(os.path.join(shot, "scenes")); open(os.path.join(shot, "workspace.mel"), "w").write("")
os.makedirs(build.shot_folder(H, FILM, "EAP_010", "EAP_010_010"))

# Textures "exported from another program" into the asset's sourceimages,
# plus UDIM tiles from somewhere else on disk.
src = os.path.join(asset_s, "sourceimages")
cloth = touch(os.path.join(src, "cloth_BaseColor.png"), b"cloth")
tiles = [touch(os.path.join(base, "painter_export", "strap.%d.png" % t)) for t in (1001, 1002)]


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


def model_scene(textured=True):
    cmds.file(new=True, force=True)
    cmds.workspace(asset_s, openWorkspace=True)
    root = cmds.group(empty=True, name="backpack_geo")
    bag = cmds.parent(cmds.polyCube(name="bag_geo")[0], root)[0]
    strap = cmds.parent(cmds.polyCube(name="strap_geo")[0], root)[0]
    if textured:
        shader("cloth", bag, "sourceimages/cloth_BaseColor.png")   # project-relative
        shader("strap", strap, tiles[0], udim=True)
    scene = os.path.join(asset_s, "scenes", "model_work.ma")
    cmds.file(rename=scene); cmds.file(save=True, type="mayaAscii")
    return scene


def publish_model(scene, objects):
    plan = api.plan_publish(scene, H, S, "model")
    plan["objects"] = objects
    textures = tex.collect(api._model_roots(objects))
    api.export_model_to_h_drive(objects, plan, scene, textures)
    return plan, textures


# --- textured model, selected objects
scene = model_scene()
before = dict((n, cmds.getAttr(n + ".fileTextureName")) for n in cmds.ls(type="file"))
plan, textures = publish_model(scene, ["backpack_geo"])
check("both texture nodes found through the model's shaders", len(textures) == 2)
folder = plan["textures"]["folder"]
check("textures in <asset>\\sourceimages\\<login>\\<published name>",
      folder == os.path.join(H, FILM, "maya", "assets", "prop", "backpack", "sourceimages",
                             "scout", "backpack_scout_model_v001"))
names = sorted(os.path.relpath(os.path.join(d, f), folder).replace("\\", "/")
               for d, _, fs in os.walk(folder) for f in fs)
print("   ", names)
check("all files copied, UDIM tiles included",
      names == ["cloth_BaseColor.png", "strap.1001.png", "strap.1002.png"])
check("working scene's texture paths unchanged",
      dict((n, cmds.getAttr(n + ".fileTextureName")) for n in cmds.ls(type="file")) == before)
cmds.file(new=True, force=True)
cmds.file(plan["dest"], open=True, force=True)
paths = dict((n, cmds.getAttr(n + ".fileTextureName")) for n in cmds.ls(type="file"))
print("   ", paths)
check("published file points at $PIPE_SCRATCH/.../sourceimages/scout/backpack_scout_model_v001/",
      len(paths) == 2 and all(
          p.startswith("$PIPE_SCRATCH/NWF_SHF/maya/publish/assets/prop/backpack/sourceimages/"
                       "scout/backpack_scout_model_v001/") for p in paths.values()))
group = "backpack_model_GRP"
stamp = json.loads(cmds.getAttr(group + ".pipe_textures"))
check("model group stamp lists the textures", sorted(s["node"] for s in stamp)
      == ["cloth_file", "strap_file"])
check("published model still frozen copy in its group",
      cmds.objExists("|backpack_model_GRP|backpack_geo|bag_geo"))

# --- untextured model: no texture folder, no stamp, publishes as before
scene = model_scene(textured=False)
plan2, textures2 = publish_model(scene, [])
check("untextured: nothing collected", textures2 == [])
check("untextured: no texture folder", "textures" not in plan2
      and not os.path.exists(tex.texture_folder(plan2)))
cmds.file(new=True, force=True)
cmds.file(plan2["dest"], open=True, force=True)
check("untextured: published, group has no textures stamp",
      cmds.objExists(group) and not cmds.attributeQuery("pipe_textures", node=group, exists=True))

# --- an empty file node (no texture set) is not a missing texture
scene = model_scene(textured=False)
f = cmds.shadingNode("file", asTexture=True, name="empty_file")
sh = cmds.shadingNode("lambert", asShader=True)
cmds.connectAttr(f + ".outColor", sh + ".color")
cmds.select("bag_geo"); cmds.hyperShade(assign=sh)
check("empty file node: not refused, nothing to carry", tex.collect(["backpack_geo"]) == [])

# --- Build pulls the model with its textures into scratch publish\
model = [p for p in build.list_published(H, FILM) if p["code"] == "model"][0]
cmds.file(new=True, force=True)
build.ensure_maya_project(shot)
done, warn, old = build.build_asset(shot, model, build.version_id("scout", 1))
print("   ", done)
pulled = os.path.join(S, FILM, "maya", "publish", "assets", "prop", "backpack", "sourceimages",
                      "scout", "backpack_scout_model_v001")
check("Build pulled the model's textures into scratch publish\\",
      os.path.isfile(os.path.join(pulled, "cloth_BaseColor.png"))
      and os.path.isfile(os.path.join(pulled, "strap.1002.png")))
node = [n for n in cmds.ls(type="file") if n.endswith("cloth_file")][0]
p = cmds.getAttr(node + ".fileTextureName")
check("in the shot the texture path resolves on this drive",
      p.startswith("$PIPE_SCRATCH/") and os.path.isfile(os.path.expandvars(p)))

# --- publish() refuses a model with a missing texture before ShotGrid/playblast
calls = []
api.find_shotgrid_asset = lambda *a: calls.append("shotgrid")
api.playblast_frames = lambda *a, **k: calls.append("playblast")
api.check_script_nodes = lambda: None
scene = model_scene()
os.rename(cloth, cloth + ".gone")
try:
    api.publish(scene, H, S, "model", objects=["backpack_geo"])
    refused = False
except api.PublishError as e:
    refused = "missing" in str(e) and "cloth_file" in str(e)
check("publish() refuses a missing texture before ShotGrid or playblast", refused and calls == [])
os.rename(cloth + ".gone", cloth)

print("\n%d/%d passed" % (sum(results), len(results)))
for root, dirs, files in os.walk(base):
    for f in files:
        os.chmod(os.path.join(root, f), stat.S_IWRITE)
shutil.rmtree(base, ignore_errors=True)
maya.standalone.uninitialize()
