# Looks from rigs whose shaders came in with namespaces (2026-11-25, scout
# on SEQ010_120: dress, boots and hair lost their shaders on the cache):
#  - boots:lambert3SG and lambert3SG clean to the same name: the look keeps
#    both (the boots' was overwritten);
#  - a namespaced material (dress:dressMTL) keeps its namespace in the look
#    .ma: Build still finds it (it made an empty shading group);
#  - faces f[0:N] covering the whole mesh go on as the whole mesh, and real
#    per-face assignments take the mesh off Maya's default shader.
# Run: mayapy test_lookNamespaces_mayapy.py
import sys, os, json, stat, shutil, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), "publishDev")]
import maya.standalone; maya.standalone.initialize()
import maya.cmds as cmds
import buildTool_api as api
import publishTool_anim as anim
import publishTool_textures as tex
import publishTool_look as look
import pipeEnv

pub = api.pub
ok = []
def check(label, cond):
    ok.append(bool(cond)); print("PASS" if cond else "FAIL", label)

base = tempfile.mkdtemp(prefix="lookns_")
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

scout_s = api.asset_folder(SC, FILM, "character", "scout")
os.makedirs(os.path.join(scout_s, "scenes"))
open(os.path.join(scout_s, "workspace.mel"), "w").write("")
os.makedirs(os.path.join(H, FILM, "maya", "assets", "character", "scout", "scenes"))
shot_s = api.shot_folder(SC, FILM, SEQ, SHOT)
os.makedirs(os.path.join(shot_s, "scenes")); open(os.path.join(shot_s, "workspace.mel"), "w").write("")
os.makedirs(os.path.join(api.shot_folder(H, FILM, SEQ, SHOT), "scenes"))


def shader(name, namespace=""):
    """A lambert and its shading group, both in namespace (made like an
    imported file's)."""
    if namespace and not cmds.namespace(exists=":" + namespace):
        cmds.namespace(add=namespace)
    prefix = namespace + ":" if namespace else ""
    sh = cmds.shadingNode("lambert", asShader=True, name=prefix + name + "MTL")
    sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=prefix + name + "SG")
    cmds.connectAttr(sh + ".outColor", sg + ".surfaceShader")
    return sg


# --- the look collector: boots:lambert3SG and lambert3SG both kept. (Publish
# now refuses that clash, but scout's rig went out before it did.)
cmds.file(new=True, force=True)
grp = cmds.group(empty=True, name="clash_rig")
for name in ("body_geo", "boots_geo"):
    cmds.parent(cmds.polyCube(name=name)[0], grp)
cmds.sets("body_geo", edit=True, forceElement=shader("lambert3"))
cmds.sets("boots_geo.f[0:5]", edit=True, forceElement=shader("lambert3", "boots"))
sgs = look.collect(["clash_rig"])
members = dict((m["path"].split("|")[-1], sg) for sg, e in sgs.items() for m in e["members"])
check("look: boots and body both kept (same name without namespaces)",
      len(sgs) == 2 and members.get("boots_geo") and members.get("body_geo")
      and members["boots_geo"] != members["body_geo"])
check("look: boots' material named with its namespace, as in the look .ma",
      sgs[members["boots_geo"]]["inputs"] == {"surfaceShader": "boots:lambert3MTL.outColor"})

# Scout's rig: body, boots (boots:bootsSG, all faces), dress (dress:dressSG,
# all faces), skirt half dress half trim.
cmds.file(new=True, force=True)
cmds.workspace(scout_s, openWorkspace=True)
rig = cmds.group(empty=True, name="scout_rig")
ctl = cmds.parent(cmds.circle(name="root_ctl")[0], rig)[0]
meshes = {}
for name in ("body_geo", "boots_geo", "dress_geo", "skirt_geo"):
    meshes[name] = cmds.parent(cmds.polyCube(name=name)[0], ctl)[0]
cmds.sets("body_geo", edit=True, forceElement=shader("body"))
cmds.sets("boots_geo.f[0:5]", edit=True, forceElement=shader("boots", "boots"))
cmds.sets("dress_geo.f[0:5]", edit=True, forceElement=shader("dress", "dress"))
cmds.sets("skirt_geo.f[0:2]", edit=True, forceElement="dress:dressSG")
cmds.sets("skirt_geo.f[3:5]", edit=True, forceElement=shader("trim"))
cmds.sets(list(meshes), name=pub.CACHE_SET)
cmds.sets([ctl], name=pub.BODY_CONTROLS_SET)
rig_scene = os.path.join(scout_s, "scenes", "rig_work.ma")
cmds.file(rename=rig_scene); cmds.file(save=True, type="mayaAscii")
plan = pub.plan_publish(rig_scene, H, SC, "rig")
plan.update(objects=["scout_rig"], sg_asset={"type": "Asset", "id": 99}, cache_set=pub.CACHE_SET,
            control_sets={"body": pub.BODY_CONTROLS_SET, "face": None})
plan["set_uuids"] = cmds.ls([pub.CACHE_SET, pub.BODY_CONTROLS_SET], uuid=True)
pub.export_rig_to_h_drive(["scout_rig"], plan, rig_scene, tex.collect(["scout_rig"]), [])
rig_file = plan["dest"]

# --- the published look names the namespaced material as its .ma does
data = json.load(open(look.look_paths(plan)[1]))
sgs = data["shading_groups"]
members = dict((m["path"].split("|")[-1], sg) for sg, e in sgs.items() for m in e["members"])
check("look: four shading groups", len(sgs) == 4)
check("look: dress material named as in the look .ma (with its namespace)",
      sgs[members["dress_geo"]]["inputs"] == {"surfaceShader": "dress:dressMTL.outColor"})

# --- animate, cache, build
cmds.file(new=True, force=True)
cmds.file(rig_file, reference=True, namespace="scout_rig")
ctl = cmds.ls("scout_rig:root_ctl")[0]
cmds.setKeyframe(ctl + ".tx", time=1, value=0)
cmds.setKeyframe(ctl + ".tx", time=5, value=5)
cmds.playbackOptions(minTime=1, maxTime=5)
anim_scene = os.path.join(shot_s, "scenes", "anim", LOGIN, "anim_work.ma")
os.makedirs(os.path.dirname(anim_scene))
cmds.file(rename=anim_scene); cmds.file(save=True, type="mayaAscii")
items = anim.classify([ctl])
p = anim.plan_anim(anim_scene, H, SC, items, anim.ANIM_CODE)
p["stage"], p["caches"] = anim.FINAL, ["abc"]
anim.write_anim(items, p, 1, 5, anim_scene)

cmds.file(new=True, force=True)
light_scene = os.path.join(shot_s, "scenes", "lighting", LOGIN, "light.ma")
os.makedirs(os.path.dirname(light_scene))
cmds.file(rename=light_scene); cmds.file(save=True, type="mayaAscii")
c = api.list_shot_caches(H, FILM, SEQ, SHOT)[0]
done, warning, _ = api.build_asset(shot_s, c, c["latest"])
print("   ", done, warning)


def shaders_on(mesh):
    """{shading group: faces or "whole"} the cache mesh is a member of."""
    found = {}
    for sg in cmds.ls(type="shadingEngine"):
        for m in cmds.sets(sg, query=True) or []:
            node, _, faces = m.partition(".")
            if node.split(":")[-1] in (mesh, mesh + "Shape"):
                found.setdefault(sg, []).append(faces or "whole")
    return found


def material_of(sg):
    return [n.split(":")[-1] for n in cmds.listConnections(sg + ".surfaceShader") or []]


boots, dress, skirt = shaders_on("boots_geo"), shaders_on("dress_geo"), shaders_on("skirt_geo")
print("    boots", boots, "\n    dress", dress, "\n    skirt", skirt)
check("boots: their namespaced material, as the whole mesh, off the default",
      len(boots) == 1 and list(boots.values()) == [["whole"]]
      and material_of(list(boots)[0]) == ["bootsMTL"])
check("dress: the namespaced material, as the whole mesh, off the default",
      len(dress) == 1 and list(dress.values()) == [["whole"]]
      and material_of(list(dress)[0]) == ["dressMTL"])
check("skirt: per face, dress and trim, nothing left on the default",
      "initialShadingGroup" not in skirt and len(skirt) == 2
      and sorted(material_of(sg)[0] for sg in skirt) == ["dressMTL", "trimMTL"])
check("every look shading group has its material",
      all(material_of(sg) for sg in cmds.ls("scoutrig_cache_look:*", type="shadingEngine")))
check("no missed geometry", warning is None)

print("\n%d/%d passed" % (sum(ok), len(ok)))
for root, dirs, fs in os.walk(base):
    for f in fs:
        os.chmod(os.path.join(root, f), stat.S_IWRITE)
shutil.rmtree(base, ignore_errors=True)
sys.stdout.flush()
os._exit(0 if all(ok) else 1)
