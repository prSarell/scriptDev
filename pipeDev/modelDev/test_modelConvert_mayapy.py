r"""Headless test: Convert to Model (mpModel shelf, user 2026-10-30).

    "C:\Program Files\Autodesk\Maya2025\bin\mayapy.exe" pipeDev/modelDev/test_modelConvert_mayapy.py

A published model or environment, referenced (as Build does) or imported,
becomes a plain Maya model: no pipe group, no namespace, nothing moved or
frozen, environment sets kept, the publish's locators and locks gone. Only
the selected asset changes, only in an asset scene; clashes refuse before
anything changes. Throwaway folders in %TEMP%; nothing real is touched.
"""
import os, sys, shutil, tempfile

import maya.standalone
maya.standalone.initialize()
import maya.cmds as cmds

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), "publishDev")]
import publishTool_api as api
import publishTool_env as env
import modelTool_convert as convert

api.artist_name = lambda login: "Test Person"      # no ShotGrid in the test
results = []


def check(name, ok):
    results.append(bool(ok)); print(("PASS " if ok else "FAIL ") + name)


def refused(text, selection):
    before = sorted(cmds.ls(recursive=True))
    try:
        convert.convert_selected(selection)
    except convert.ConvertError as e:
        if text not in str(e):
            print("    (message was: %s)" % e)
        return text in str(e) and sorted(cmds.ls(recursive=True)) == before
    return False


base = tempfile.mkdtemp(prefix="modelconvert_")
H = os.path.join(base, "H", "NWF_SHF", "maya")
asset_scene = os.path.join(base, "scratch", "NWF_SHF", "maya", "assets", "environment", "shed",
                           "scenes", "model", "e131988", "shed_work.ma")
shot_scene = os.path.join(base, "scratch", "NWF_SHF", "maya", "sequences", "SEQ010", "SEQ010_140",
                          "scenes", "anim", "e131988", "anim.ma")
for path in (asset_scene, shot_scene):
    os.makedirs(os.path.dirname(path))


def open_new(path):
    cmds.file(new=True, force=True)
    cmds.file(rename=path)
    cmds.file(save=True, type="mayaAscii")


# --- a real model publish: backpack, in props_grp, with a shader
cmds.file(new=True, force=True)
grp = cmds.group(empty=True, name="props_grp")
geo = cmds.polyCube(name="backPack_geo")[0]
cmds.parent(geo, grp)
cmds.setAttr("props_grp|backPack_geo.ty", 3)
sh = cmds.shadingNode("lambert", asShader=True, name="bagMat")
sg = cmds.sets(renderable=True, empty=True, name="bagMatSG")
cmds.connectAttr(sh + ".outColor", sg + ".surfaceShader", force=True)
cmds.sets("props_grp|backPack_geo", edit=True, forceElement=sg)
model_dir = os.path.join(H, "assets", "prop", "backpack", "scenes", "scout")
model = os.path.join(model_dir, "backpack_scout_model_v004.ma")
api.export_model_to_h_drive(["props_grp"], {
    "dest": model, "h_folder": model_dir, "ext": ".ma", "asset": "backpack",
    "asset_type": "prop", "code": "model", "version": 4, "login": "scout",
    "sg_asset": {"id": 1577}}, asset_scene)

# --- an environment publish as it lands (built by hand): shed_env_GRP >
# landscape / buildings > shed / sky (locked) / locators > shed_LOC, + sets
cmds.file(new=True, force=True)
group = api.make_pipe_group("shed_env_GRP")
land = cmds.group(empty=True, name="landscape", parent=group)
cmds.parent(cmds.polyPlane(name="ground")[0], land)
buildings = cmds.group(empty=True, name="buildings", parent=group)
shed = cmds.group(empty=True, name="shed", parent=buildings)
cmds.parent(cmds.polyCube(name="shedBox")[0], shed)
cmds.setAttr(shed + ".translate", 50, 0, -20)
sky = cmds.group(empty=True, name="sky", parent=group)
dome = cmds.parent(cmds.polySphere(name="skyDome")[0], sky)[0]
cmds.setAttr(dome + ".scale", 900, 900, 900)
env._lock_channels(cmds.ls(dome, long=True)[0])
locs = cmds.group(empty=True, name=env.LOCATOR_GROUP, parent=group)
cmds.parent(cmds.spaceLocator(name="shed_LOC")[0], locs)
role_sets = [cmds.sets(land, name="landscape_SET"), cmds.sets(buildings, name="building_SET"),
             cmds.sets(sky, name="sky_SET")]
env_set = cmds.sets(role_sets, name=env.ENVIRONMENT_SET)
api._stamp(group, [("sgAssetId", 99), ("asset", "shed"), ("assetType", "environment"),
                   ("department", "env"), ("version", 3), ("artistId", "e131988")])
api.finish_pipe_group(group)
env_dir = os.path.join(H, "assets", "environment", "shed", "scenes", "e131988")
os.makedirs(env_dir)
env_file = os.path.join(env_dir, "shed_e131988_env_v003.ma")
cmds.select(group, replace=True)
cmds.select([env_set] + role_sets, add=True, noExpand=True)
cmds.file(env_file, exportSelected=True, type="mayaAscii", force=True)

# --- refusals
open_new(shot_scene)
cmds.file(model, reference=True, namespace="backpack")
check("shot scene -> refused, nothing changed",
      refused("only works in an asset scene", ["backpack:backpack_model_GRP"]))
cmds.file(new=True, force=True)
check("untitled scene -> refused", refused("Save this scene", []))
open_new(asset_scene)
check("nothing selected -> refused", refused("Select the top node", []))
cmds.polyCube(name="myOwnCube")
check("not a pipe asset -> refused", refused("Not part of a published pipe asset", ["myOwnCube"]))
rig = api.make_pipe_group("scout_rig_GRP")
api._stamp(rig, [("sgAssetId", 5), ("asset", "scout"), ("department", "rig")])
check("a rig -> refused", refused("is a rig publish", [rig]))
cmds.delete(rig)

# --- a referenced environment, as Build brings it in, next to a referenced model
cmds.file(env_file, reference=True, namespace="shed_env")
cmds.file(model, reference=True, namespace="backpack")
shed_before = cmds.xform("shed_env:shed_env_GRP|shed_env:buildings|shed_env:shed",
                         query=True, worldSpace=True, matrix=True)
done = convert.convert_selected(["shed_env:shed_env_GRP|shed_env:buildings"])
check("selecting something inside the group converts its asset",
      [(a, d) for a, d, _, _ in done] == [("shed", "env")])
check("its history node clashing with the student's cube (polyCube1) was just numbered",
      [w for w, _ in done[0][3]] == ["polyCube1"] and cmds.ls("myOwnCube"))
check("reference imported", not [r for r in cmds.ls(type="reference")
                                 if "shed_env" in r and "sharedReferenceNode" not in r])
check("pipe group gone", not cmds.ls("*shed_env_GRP*", recursive=True))
check("landscape, buildings, sky at the world root, no namespace",
      all(cmds.ls("|" + n) for n in ("landscape", "buildings", "sky")))
check("no shed_env namespace left", not cmds.namespace(exists=":shed_env"))
check("shed exactly where it was, not frozen",
      cmds.xform("|buildings|shed", query=True, worldSpace=True, matrix=True) == shed_before
      and cmds.getAttr("|buildings|shed.tx") == 50)
check("sky unlocked", not any(cmds.getAttr("|sky|skyDome.%s" % a, lock=True)
                              for a in env.TRANSFORM_CHANNELS)
      and cmds.getAttr("|sky|skyDome.sx") == 900)
check("publish's locators removed", not cmds.ls("shed_LOC") and not cmds.ls("|locators"))
check("environment sets kept, with their groups",
      cmds.sets("landscape_SET", query=True) == ["landscape"]
      and sorted(cmds.sets(env.ENVIRONMENT_SET, query=True)) == ["building_SET", "landscape_SET", "sky_SET"])
check("only the selected asset: the backpack is still a referenced publish",
      cmds.referenceQuery("backpack:backpack_model_GRP", isNodeReferenced=True))
check("converted asset selected", sorted(cmds.ls(selection=True)) == ["buildings", "landscape", "sky"])

# --- the env republishes from here: its checks find the sets
check("environment publish checks pass on it", env.check_environment()["sets"][env.LANDSCAPE])

# --- clashes where the name matters refuse before anything changes
open_new(asset_scene)
cmds.file(model, reference=True, namespace="backpack")
cmds.group(empty=True, name="props_grp")
check("top group already at the root (props_grp) -> refused, still referenced",
      refused("props_grp", ["backpack:backpack_model_GRP"])
      and cmds.referenceQuery("backpack:backpack_model_GRP", isNodeReferenced=True))
open_new(asset_scene)
cmds.file(env_file, reference=True, namespace="shed_env")
cmds.sets(empty=True, name=env.ENVIRONMENT_SET)
check("environment_SET already in the scene -> refused",
      refused(env.ENVIRONMENT_SET, ["shed_env:shed_env_GRP"]))

# --- a shader with a name already used is just numbered, still connected
open_new(asset_scene)
cmds.file(model, reference=True, namespace="backpack")
cmds.shadingNode("lambert", asShader=True, name="bagMat")
done = convert.convert_selected(["backpack:backpack_model_GRP"])
check("bagMat clash -> numbered, the model keeps its shader",
      [w for w, _ in done[0][3]] == ["bagMat"]
      and cmds.listConnections(cmds.listConnections(cmds.listRelatives(
          "|props_grp|backPack_geo", shapes=True)[0], type="shadingEngine")[0]
          + ".surfaceShader")[0] != "bagMat")

# --- an imported model (as Build's old Import into Asset did: no namespace)
open_new(asset_scene)
cmds.file(model, i=True, defaultNamespace=True, preserveReferences=False)
y = cmds.xform("backpack_model_GRP|props_grp|backPack_geo", query=True, worldSpace=True,
               translation=True)
convert.convert_selected(["backpack_model_GRP"])
check("imported model: group gone, props_grp at the root",
      not cmds.ls("backpack_model_GRP") and cmds.ls("|props_grp|backPack_geo"))
check("imported model: not moved", cmds.xform("|props_grp|backPack_geo", query=True,
                                             worldSpace=True, translation=True) == y)
check("imported model: shader kept", "bagMatSG" in (cmds.listConnections(
    cmds.listRelatives("|props_grp|backPack_geo", shapes=True)[0], type="shadingEngine") or []))
check("imported model: no pipe stamp left anywhere",
      not [n for n in cmds.ls(recursive=True) if cmds.attributeQuery(api.ID_ATTR, node=n, exists=True)])

print("\n%d/%d passed" % (sum(results), len(results)))
shutil.rmtree(base, ignore_errors=True)
