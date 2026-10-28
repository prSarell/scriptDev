r"""Headless test: rig and model publishes write their look (spec §4 "Shaders
on caches, automatic", 2026-10-28): the material networks in <published>_look.ma
(no meshes, no shading groups) and <published>_look.json (what fed each
shading group and which meshes / faces it was on), so Build can put the
shaders back on an animation cache.

    "C:\Program Files\Autodesk\Maya2025\bin\mayapy.exe" pipeDev/publishDev/test_look_mayapy.py

Throwaway folders in %TEMP% and a throwaway drive-settings file; never
touches the real H drive, scratch drive or Maya prefs.
"""
import os, sys, stat, shutil, tempfile, json

import maya.standalone
maya.standalone.initialize()
import maya.cmds as cmds

DEV = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(DEV, "publishDev"), os.path.join(DEV, "buildDev")]
import publishTool_api as api
import publishTool_textures as tex
import publishTool_look as look
import pipeEnv

base = tempfile.mkdtemp(prefix="look_")
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


def asset(asset_type, name):
    s = os.path.join(S, FILM, "maya", "assets", asset_type, name)
    os.makedirs(os.path.join(H, FILM, "maya", "assets", asset_type, name, "scenes"))
    os.makedirs(os.path.join(s, "scenes"))
    open(os.path.join(s, "workspace.mel"), "w").write("")
    return s


bag_s = asset("prop", "backpack")
scout_s = asset("character", "scout")
cloth = touch(os.path.join(bag_s, "sourceimages", "cloth.png"))
skin = touch(os.path.join(scout_s, "sourceimages", "skin.png"))


def shader(name, path=None):
    sh = cmds.shadingNode("lambert", asShader=True, name=name + "_MTL")
    sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=name + "SG")
    cmds.connectAttr(sh + ".outColor", sg + ".surfaceShader")
    if path:
        f = cmds.shadingNode("file", asTexture=True, name=name + "_file")
        cmds.setAttr(f + ".fileTextureName", path, type="string")
        cmds.connectAttr(f + ".outColor", sh + ".color")
    return sg


def save(folder, name):
    scene = os.path.join(folder, "scenes", name)
    cmds.file(rename=scene); cmds.file(save=True, type="mayaAscii")
    return scene


def assignments():
    return dict((sg, sorted(cmds.sets(sg, query=True) or []))
                for sg in cmds.ls(type="shadingEngine"))


def read(path):
    with open(path) as f:
        return json.load(f)


# --- model: two shaders, one of them on some faces only; a mesh left on lambert1
cmds.file(new=True, force=True)
cmds.workspace(bag_s, openWorkspace=True)
root = cmds.group(empty=True, name="backpack_geo")
bag = cmds.parent(cmds.polyCube(name="bag_geo")[0], root)[0]
strap = cmds.parent(cmds.polyCube(name="strap_geo")[0], root)[0]
cmds.parent(cmds.polyCube(name="plain_geo")[0], root)
cmds.sets(bag, edit=True, forceElement=shader("cloth", "sourceimages/cloth.png"))
cmds.sets(strap + ".f[0:1]", edit=True, forceElement=shader("buckle"))
scene = save(bag_s, "model_work.ma")
before = assignments()
plan = api.plan_publish(scene, H, S, "model")
plan["objects"] = ["backpack_geo"]
api.export_model_to_h_drive(["backpack_geo"], plan, scene, tex.collect(["backpack_geo"]))
ma, js = look.look_paths(plan)
check("model: look .ma and .json next to the published file",
      os.path.isfile(ma) and os.path.isfile(js)
      and os.path.basename(ma) == "backpack_scout_model_v001_look.ma")
check("model: look files read-only", not os.access(ma, os.W_OK) and not os.access(js, os.W_OK))
check("working scene's shader assignments unchanged", assignments() == before)
data = read(js)
sgs = data["shading_groups"]
check("model: one entry per shading group, lambert1 left out", sorted(sgs) == ["buckleSG", "clothSG"])
check("model: clothSG fed by cloth_MTL.outColor",
      sgs["clothSG"]["inputs"] == {"surfaceShader": "cloth_MTL.outColor"})
check("model: clothSG on bag_geo inside the model group",
      sgs["clothSG"]["members"] == [{"path": "|backpack_model_GRP|backpack_geo|bag_geo",
                                     "faces": None}])
check("model: buckleSG on two faces of strap_geo",
      sgs["buckleSG"]["members"] == [{"path": "|backpack_model_GRP|backpack_geo|strap_geo",
                                      "faces": "f[0:1]"}])
check("model: json says what it belongs to",
      (data["published"], data["department"], data["version"], data["login"])
      == ("backpack_scout_model_v001.ma", "model", 1, "scout"))

cmds.file(new=True, force=True)
cmds.file(plan["dest"], open=True, force=True)
check("model group stamp names the look",
      cmds.getAttr("backpack_model_GRP.pipe_look") == "backpack_scout_model_v001_look.ma")
cmds.file(new=True, force=True)
cmds.file(ma, open=True, force=True)
check("look file: no geometry", not cmds.ls(type=api.GEOMETRY_TYPES))
check("look file: no shading groups but Maya's own",
      sorted(cmds.ls(type="shadingEngine")) == ["initialParticleSE", "initialShadingGroup"])
check("look file: the materials", cmds.objExists("cloth_MTL") and cmds.objExists("buckle_MTL"))
check("look file: texture already on the H drive copy",
      cmds.getAttr("cloth_file.fileTextureName").startswith(
          "$PIPE_SCRATCH/NWF_SHF/maya/publish/assets/prop/backpack/sourceimages/scout/"
          "backpack_scout_model_v001/"))

# --- model with only lambert1: no look
cmds.file(new=True, force=True)
cmds.workspace(bag_s, openWorkspace=True)
cmds.polyCube(name="box_geo")
scene = save(bag_s, "plain_work.ma")
plan2 = api.plan_publish(scene, H, S, "model")
api.export_model_to_h_drive([], plan2, scene, [])
check("default shader only: no look files",
      not any(os.path.exists(p) for p in look.look_paths(plan2)) and "look" not in plan2)
cmds.file(new=True, force=True)
cmds.file(plan2["dest"], open=True, force=True)
check("default shader only: no look stamp",
      not cmds.attributeQuery("pipe_look", node="backpack_model_GRP", exists=True))

# --- a model export that fails leaves no look behind
cmds.file(new=True, force=True)
cmds.workspace(bag_s, openWorkspace=True)
cmds.sets(cmds.polyCube(name="box_geo")[0], edit=True, forceElement=shader("box"))
scene = save(bag_s, "fail_work.ma")
plan3 = api.plan_publish(scene, H, S, "model")
real = api._WithoutUnknownData


class Boom(object):
    removed = []
    def __enter__(self):
        raise RuntimeError("export failed")
    def __exit__(self, *a):
        return False


api._WithoutUnknownData = Boom
try:
    api.export_model_to_h_drive([], plan3, scene, [])
except RuntimeError:
    pass
api._WithoutUnknownData = real
check("failed export: look files removed",
      not any(os.path.exists(p) for p in look.look_paths(plan3)))

# --- rig: only what's in cache_SET counts
cmds.file(new=True, force=True)
cmds.workspace(scout_s, openWorkspace=True)
rig = cmds.group(empty=True, name="scout_rig")
body = cmds.parent(cmds.polyCube(name="body_geo")[0], rig)[0]
helper = cmds.parent(cmds.polySphere(name="collide_geo")[0], rig)[0]
ctl = cmds.parent(cmds.circle(name="root_ctl")[0], rig)[0]
cmds.sets(body, edit=True, forceElement=shader("skin", skin))
cmds.sets(helper, edit=True, forceElement=shader("helper"))
cmds.sets([body], name=api.CACHE_SET)
cmds.sets([ctl], name=api.BODY_CONTROLS_SET)
scene = save(scout_s, "rig_work.ma")
before = assignments()
plan4 = api.plan_publish(scene, H, S, "rig")
plan4.update(objects=["scout_rig"], sg_asset={"type": "Asset", "id": 99}, cache_set=api.CACHE_SET,
             control_sets={"body": api.BODY_CONTROLS_SET, "face": None})
plan4["set_uuids"] = cmds.ls([api.CACHE_SET, api.BODY_CONTROLS_SET], uuid=True)
api.export_rig_to_h_drive(["scout_rig"], plan4, scene, tex.collect(["scout_rig"]), [])
ma, js = look.look_paths(plan4)
sgs = read(js)["shading_groups"]
check("rig: look written", os.path.isfile(ma) and plan4["look"]["shading_groups"] == 1)
check("rig: only the cache_SET geometry's shader (no helper)", sorted(sgs) == ["skinSG"])
check("rig: body_geo inside the rig group",
      sgs["skinSG"]["members"] == [{"path": "|scout_rig_GRP|scout_rig|body_geo", "faces": None}])
check("rig: working scene's shader assignments unchanged", assignments() == before)
cmds.file(new=True, force=True)
cmds.file(plan4["dest"], open=True, force=True)
check("rig group stamp names the look",
      cmds.getAttr("scout_rig_GRP.pipe_look") == "scout_scout_rig_v001_look.ma")
cmds.file(new=True, force=True)
cmds.file(ma, open=True, force=True)
check("rig look file: skin material, no helper material, no geometry",
      cmds.objExists("skin_MTL") and not cmds.objExists("helper_MTL")
      and not cmds.ls(type=api.GEOMETRY_TYPES))

# --- Build doesn't take a look file for a publish
sys.path.insert(0, os.path.join(DEV, "buildDev"))
import buildTool_api as build
pubs = build.list_published(H, FILM)
check("Build lists the publishes, not their look files",
      sorted((p["asset"], p["code"]) for p in pubs) == [("backpack", "model"), ("scout", "rig")]
      and all(not f.endswith("_look.ma") for p in pubs for f in p["versions"].values()
              if isinstance(f, str)))

print("\n%d/%d passed" % (sum(results), len(results)))
for root, dirs, files in os.walk(base):
    for f in files:
        os.chmod(os.path.join(root, f), stat.S_IWRITE)
shutil.rmtree(base, ignore_errors=True)
maya.standalone.uninitialize()
