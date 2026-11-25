# Caches of things made in the shot (2026-11-25, SEQ010_120: the walking
# stick and power pack came through still, grey and with no pipe group):
#  - a prop moved by a constraint (no keys) is cached over the timeline;
#  - its shaders and textures go out with the publish (a look beside its
#    keys file, textures in the shot's sourceimages) and Build puts them on;
#  - Build puts every ABC cache in a pipe group (dagContainer, pipe icon).
# Run: mayapy test_shotItemCaches_mayapy.py
import sys, os, json, stat, shutil, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), "publishDev")]
import maya.standalone; maya.standalone.initialize()
import maya.cmds as cmds
import buildTool_api as api
import publishTool_anim as anim
import pipeEnv

pub = api.pub
ok = []
def check(label, cond):
    ok.append(bool(cond)); print("PASS" if cond else "FAIL", label)

base = tempfile.mkdtemp(prefix="shotcache_")
H, SC = os.path.join(base, "H"), os.path.join(base, "scratch")
FILM, SEQ, SHOT, LOGIN = "NWF_SHF", "EAP_010", "EAP_010_010", "scout"
_cfg = os.path.join(base, "pipeline_config.json")
pub._config_path = lambda: _cfg
pub.set_root(pub.H_DRIVE, H)
pub.set_root(pub.SCRATCH, SC)
pub.save_config(dict(pub.load_config(), publish_as=LOGIN))
os.environ.pop(pipeEnv.VAR, None)
cmds.loadPlugin("AbcImport", quiet=True)
cmds.loadPlugin("AbcExport", quiet=True)
shot_s = api.shot_folder(SC, FILM, SEQ, SHOT)
os.makedirs(os.path.join(shot_s, "scenes")); open(os.path.join(shot_s, "workspace.mel"), "w").write("")
os.makedirs(os.path.join(api.shot_folder(H, FILM, SEQ, SHOT), "scenes"))

# The shot: a keyed hand, a stick constrained to it (textured), a still box.
cmds.file(new=True, force=True)
cmds.workspace(shot_s, openWorkspace=True)
hand = cmds.spaceLocator(name="hand")[0]
cmds.setKeyframe(hand + ".tx", time=1, value=0)
cmds.setKeyframe(hand + ".tx", time=10, value=5)
cmds.playbackOptions(minTime=1, maxTime=10)
stick = cmds.polyCylinder(name="walkingStick")[0]
cmds.parentConstraint(hand, stick)
tex_path = os.path.join(shot_s, "sourceimages", "wood.png")
os.makedirs(os.path.dirname(tex_path))
open(tex_path, "wb").write(b"wood")
sh = cmds.shadingNode("lambert", asShader=True, name="wood_MTL")
sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name="woodSG")
cmds.connectAttr(sh + ".outColor", sg + ".surfaceShader")
f = cmds.shadingNode("file", asTexture=True, name="wood_file")
cmds.setAttr(f + ".fileTextureName", "sourceimages/wood.png", type="string")
cmds.connectAttr(f + ".outColor", sh + ".color")
cmds.sets(stick, edit=True, forceElement=sg)
box = cmds.polyCube(name="box")[0]
anim_scene = os.path.join(shot_s, "scenes", "anim", LOGIN, "anim_work.ma")
os.makedirs(os.path.dirname(anim_scene))
cmds.file(rename=anim_scene); cmds.file(save=True, type="mayaAscii")

items = anim.classify([stick, box])
by = dict((i["name"], i) for i in items)
check("stick: no keys, but constrained, so it moves",
      not by["walkingStick"]["animated"] and by["walkingStick"]["driven"]
      and anim.moves(by["walkingStick"]) and "constrained" in by["walkingStick"]["label"])
check("box: still", not anim.moves(by["box"]) and "no keys" in by["box"]["label"])
p = anim.plan_anim(anim_scene, H, SC, items, anim.ANIM_CODE)
p["stage"], p["caches"] = anim.FINAL, ["abc"]
written = anim.write_anim(items, p, 1, 10, anim_scene)
stick_files = p["item_files"]["walkingStick"]
info = json.load(open(stick_files["caches"]["abc"][1]))
check("stick cache: the whole timeline", (info["start"], info["end"]) == (1, 10))
check("box cache: one frame",
      json.load(open(p["item_files"]["box"]["caches"]["abc"][1]))["end"] == 1)
look_ma = os.path.splitext(stick_files["keys"])[0] + "_look.ma"
check("stick's look written beside its keys file, named in the cache .json",
      os.path.isfile(look_ma) and info.get("look") == "scenes/anim/%s/%s" % (
          LOGIN, os.path.basename(look_ma)))
tex_folder = os.path.join(api.shot_folder(H, FILM, SEQ, SHOT), "sourceimages", LOGIN,
                          os.path.splitext(os.path.basename(stick_files["keys"]))[0])
check("stick's texture copied to the shot's sourceimages on H",
      os.path.isfile(os.path.join(tex_folder, "wood.png")))
check("the working scene's texture path is put back",
      os.path.normcase(os.path.normpath(cmds.getAttr("wood_file.fileTextureName")))
      == os.path.normcase(os.path.normpath(tex_path)))
check("box: no look (only Maya's default shader)",
      "look" not in json.load(open(p["item_files"]["box"]["caches"]["abc"][1])))

# --- Lighting builds them
cmds.file(new=True, force=True)
light = os.path.join(shot_s, "scenes", "lighting", LOGIN, "light.ma")
os.makedirs(os.path.dirname(light))
cmds.file(rename=light); cmds.file(save=True, type="mayaAscii")
caches = dict((c["item"], c) for c in api.list_shot_caches(H, FILM, SEQ, SHOT))
done, warning, _ = api.build_asset(shot_s, caches["walkingStick"],
                                   caches["walkingStick"]["latest"], "lighting")
print("   ", done, warning)
group = cmds.ls("walkingStick_cache_GRP", long=True)
check("cache in a pipe group: dagContainer with the pipe icon",
      group and cmds.nodeType(group[0]) == "dagContainer"
      and cmds.getAttr(group[0] + ".iconName") == pub.PIPE_ICON)
check("... the cache inside it, display Reference",
      cmds.ls("walkingStick_cache:walkingStick", long=True)[0].startswith(group[0] + "|")
      and cmds.getAttr(group[0] + ".overrideDisplayType") == 2)
cmds.currentTime(10)
check("stick moves with the hand",
      abs(cmds.xform("walkingStick_cache:walkingStick", query=True, worldSpace=True,
                     translation=True)[0] - 5) < 0.01)
shape = cmds.listRelatives("walkingStick_cache:walkingStick", shapes=True, fullPath=True,
                           noIntermediate=True)[0]
sgs = [s for s in cmds.ls(type="shadingEngine")
       if any(m.split(".")[0].split(":")[-1] in ("walkingStick", "walkingStickShape")
              for m in cmds.sets(s, query=True) or [])]
check("stick wears its look: wood_MTL", len(sgs) == 1 and
      [n.split(":")[-1] for n in cmds.listConnections(sgs[0] + ".surfaceShader") or []]
      == ["wood_MTL"])
t = cmds.getAttr(cmds.ls("*:wood_file", recursive=True)[0] + ".fileTextureName")
check("its texture resolves on this drive", t.startswith("$PIPE_SCRATCH/")
      and os.path.isfile(os.path.expandvars(t)))
check("the build said so", any("look" in d and "put on" in d for d in done))
done, warning, _ = api.build_asset(shot_s, caches["box"], caches["box"]["latest"], "lighting")
check("box: built, no look, no warning", warning is None
      and not any("look" in d for d in done) and cmds.objExists("box_cache:box"))

print("\n%d/%d passed" % (sum(ok), len(ok)))
for root, dirs, fs in os.walk(base):
    for f in fs:
        os.chmod(os.path.join(root, f), stat.S_IWRITE)
shutil.rmtree(base, ignore_errors=True)
sys.stdout.flush()
os._exit(0 if all(ok) else 1)
