# A USD stage in an Animation publish (user, 2026-11-25: "If a student wants
# it as an alembic cache even though it is a usd they should be able to
# select it and publish it as an ABC and vice versa"), and the publish's
# contents record ("We want to know everything in the animation scene is
# 1:1 in the lighting scene"):
#  - a stage Build loaded is an item: cached as ABC and USD through a Maya
#    copy that follows the stage (keys on its transform included), proxy
#    geometry left out, the copy deleted afterwards;
#  - its cache carries the model's stamp, so Build puts the model's look on;
#  - <published>_contents.json lists every pipe asset, USD stage and thing
#    made in the shot, and what the publish wrote for each.
# Run: mayapy test_stageCache_mayapy.py
import sys, os, json, stat, shutil, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), "publishDev")]
import maya.standalone; maya.standalone.initialize()
import maya.cmds as cmds
import buildTool_api as api
import publishTool_anim as anim
import publishTool_outputs as outputs
import publishTool_textures as tex
import pipeEnv

pub = api.pub
ok = []
def check(label, cond):
    ok.append(bool(cond)); print("PASS" if cond else "FAIL", label)

base = tempfile.mkdtemp(prefix="stagecache_")
H, SC = os.path.join(base, "H"), os.path.join(base, "scratch")
FILM, SEQ, SHOT, LOGIN = "NWF_SHF", "EAP_010", "EAP_010_010", "scout"
_cfg = os.path.join(base, "pipeline_config.json")
pub._config_path = lambda: _cfg
pub.set_root(pub.H_DRIVE, H)
pub.set_root(pub.SCRATCH, SC)
pub.save_config(dict(pub.load_config(), publish_as=LOGIN))
os.environ.pop(pipeEnv.VAR, None)
for plugin in ("AbcImport", "AbcExport"):
    cmds.loadPlugin(plugin, quiet=True)
api.load_usd_plugin()

hut_s = api.asset_folder(SC, FILM, "environment", "hut")
os.makedirs(os.path.join(hut_s, "scenes")); open(os.path.join(hut_s, "workspace.mel"), "w").write("")
os.makedirs(os.path.join(H, FILM, "maya", "assets", "environment", "hut", "scenes"))
shot_s = api.shot_folder(SC, FILM, SEQ, SHOT)
os.makedirs(os.path.join(shot_s, "scenes")); open(os.path.join(shot_s, "workspace.mel"), "w").write("")
os.makedirs(os.path.join(api.shot_folder(H, FILM, SEQ, SHOT), "scenes"))

# --- the hut: a Modeling publish (with its look), USD ticked
cmds.file(new=True, force=True)
cmds.workspace(hut_s, openWorkspace=True)
geo = cmds.group(empty=True, name="geo")
render = cmds.group(empty=True, name="render", parent=geo)
proxy = cmds.group(empty=True, name="proxy", parent=geo)
wall = cmds.parent(cmds.polyCube(name="hut_wall_GEO")[0], render)[0]
cmds.parent(cmds.polyCube(name="hut_wall_PRX")[0], proxy)
sh = cmds.shadingNode("lambert", asShader=True, name="wood_MTL")
sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name="woodSG")
cmds.connectAttr(sh + ".outColor", sg + ".surfaceShader")
cmds.sets(wall, edit=True, forceElement=sg)
scene = os.path.join(hut_s, "scenes", "hut_work.ma")
cmds.file(rename=scene); cmds.file(save=True, type="mayaAscii")
plan = pub.plan_publish(scene, H, SC, "model")
plan["objects"] = ["geo"]
pub.export_model_to_h_drive(["geo"], plan, scene, tex.collect(["geo"]))
cmds.file(plan["dest"], open=True, force=True)
stem = os.path.splitext(os.path.basename(plan["dest"]))[0]
exports = os.path.join(os.path.dirname(plan["dest"]), stem + api.EXPORTS_SUFFIX)
os.makedirs(exports)
outputs._usd([cmds.ls("hut_model_GRP", long=True)[0]], os.path.join(exports, stem + ".usd"), {})
hut = [p for p in api.list_published(H, FILM) if p["asset"] == "hut"][0]
check("the hut model is published with a look and a USD",
      os.path.isfile(os.path.splitext(plan["dest"])[0] + "_look.ma")
      and os.path.isfile(os.path.join(exports, stem + ".usd")))

# --- the anim scene: the hut as a USD stage, moved by keys; a ball made in
# the shot (published) and a box (left out of the publish)
cmds.file(new=True, force=True)
anim_scene = os.path.join(shot_s, "scenes", "anim", LOGIN, "anim_work.ma")
os.makedirs(os.path.dirname(anim_scene))
cmds.file(rename=anim_scene); cmds.file(save=True, type="mayaAscii")
done, warning, _ = api.build_asset(shot_s, hut, hut["latest"], usd=True)
stage = api.stage_of(hut)
check("hut built as a USD stage", stage)
stage = stage[0]
cmds.setKeyframe(stage + ".tx", time=1, value=0)
cmds.setKeyframe(stage + ".tx", time=10, value=5)
cmds.playbackOptions(minTime=1, maxTime=10)
ball = cmds.polySphere(name="ball")[0]
cmds.polyCube(name="box")
cmds.file(save=True, type="mayaAscii")

items = anim.classify([cmds.listRelatives(stage, parent=True, fullPath=True)[0], ball])
by = dict((i["name"], i) for i in items)
check("the stage is an item: kind usdStage, the model's stamp, moves",
      by.get("hut", {}).get("kind") == anim.STAGE_KIND and by["hut"]["driven"]
      and (by["hut"]["stamp"].get("asset"), by["hut"]["stamp"].get("department"),
           by["hut"]["stamp"].get("version"), by["hut"]["stamp"].get("artistId"))
      == ("hut", "model", 1, LOGIN))
check("its label says USD stage", "USD stage, model v001" in by["hut"]["label"])
p = anim.plan_anim(anim_scene, H, SC, items, anim.ANIM_CODE)
p["stage"], p["caches"] = anim.FINAL, ["abc", "usd"]
anim.write_anim(items, p, 1, 10, anim_scene)
abc, abc_info = p["item_files"]["hut"]["caches"]["abc"]
usd, _ = p["item_files"]["hut"]["caches"]["usd"]
check("hut cached as ABC and USD", os.path.isfile(abc) and os.path.isfile(usd))
check("the Maya copy is gone afterwards",
      not cmds.namespace(exists=":" + anim.STAGE_TEMP_NAMESPACE)
      and not cmds.ls("hut_wall_GEO*", recursive=True))
check("hut cache: the whole timeline, stamped as the model",
      (json.load(open(abc_info))["start"], json.load(open(abc_info))["end"]) == (1, 10)
      and json.load(open(abc_info))["asset"]["department"] == "model")
from pxr import Usd
usd_stage = Usd.Stage.Open(usd)
names = [prim.GetName() for prim in usd_stage.Traverse()]
print("    usd prims", [str(prim.GetPath()) for prim in usd_stage.Traverse()][:6])
check("USD cache: from the model's group, the render wall, no proxy, no copy",
      str(next(iter(usd_stage.GetPseudoRoot().GetChildren())).GetPath()) == "/hut_model_GRP"
      and "hut_wall_GEO" in names and "hut_wall_PRX" not in names
      and not any("copy" in n or "Constraint" in n for n in names))
from pxr import UsdGeom
wall_prim = [prim for prim in usd_stage.Traverse() if prim.GetName() == "hut_wall_GEO"][0]
check("USD cache: the wall moves like the stage did",
      abs(UsdGeom.Xformable(wall_prim).ComputeLocalToWorldTransform(10).ExtractTranslation()[0]
          - 5) < 0.01)

# --- the contents record
contents = json.load(open(anim.contents_path(p)))
entries = dict((e["name"], e) for e in contents["contents"])
print("   ", sorted(entries))
check("contents beside the full file", os.path.isfile(anim.contents_path(p))
      and not os.access(anim.contents_path(p), os.W_OK))
check("contents: the hut as a USD stage, v001, with its two caches",
      entries.get("hut", {}).get("load") == "usd" and entries["hut"]["key"]
      == "environment/hut/model" and entries["hut"]["version"] == 1
      and sorted(entries["hut"]["published"]["caches"]) == ["abc", "usd"])
check("contents: the ball, made in the shot, cached",
      entries.get("ball", {}).get("load") == "shot"
      and entries["ball"]["published"]["caches"]["abc"].startswith("cache/alembic/anim/"))
check("contents: the box, made in the shot, not published",
      entries.get("box", {}).get("load") == "shot" and entries["box"]["published"] is None)

# --- Lighting builds the hut's ABC: the model's look goes on
cmds.file(new=True, force=True)
light = os.path.join(shot_s, "scenes", "lighting", LOGIN, "light.ma")
os.makedirs(os.path.dirname(light))
cmds.file(rename=light); cmds.file(save=True, type="mayaAscii")
c = [c for c in api.list_shot_caches(H, FILM, SEQ, SHOT)
     if c["item"] == "hut" and c["format"] == "abc"][0]
done, warning, _ = api.build_asset(shot_s, c, c["latest"], "lighting")
print("   ", done, warning)
wall = [n for n in cmds.ls("*:hut_wall_GEO", long=True, recursive=True)]
check("the cache has the render wall and no proxy",
      len(wall) == 1 and not cmds.ls("*:hut_wall_PRX", recursive=True))
cmds.currentTime(10)
check("it moves like the stage did",
      wall and abs(cmds.xform(wall[0], query=True, worldSpace=True, translation=True)[0] - 5) < 0.01)
sgs = [s for s in cmds.ls(type="shadingEngine")
       if any(m.split(".")[0].split(":")[-1] in ("hut_wall_GEO", "hut_wall_GEOShape")
              for m in cmds.sets(s, query=True) or [])]
check("the wall wears the model's look (wood_MTL)", len(sgs) == 1
      and [n.split(":")[-1] for n in cmds.listConnections(sgs[0] + ".surfaceShader") or []]
      == ["wood_MTL"])

print("\n%d/%d passed" % (sum(ok), len(ok)))
for root, dirs, fs in os.walk(base):
    for f in fs:
        os.chmod(os.path.join(root, f), stat.S_IWRITE)
shutil.rmtree(base, ignore_errors=True)
sys.stdout.flush()
os._exit(0 if all(ok) else 1)
