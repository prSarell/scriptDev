# Build brings in a shot's animation caches (spec §4 "Shaders on caches,
# automatic", step 2, 2026-10-28): a Final animation publish's Alembic per
# item, listed from the .json beside it, referenced in its own namespace and
# group (display: Reference) beside the live rig, updated in place to a
# newer version. Animation's Build offers them, Layout's doesn't.
# Run: mayapy test_buildCache_mayapy.py
import sys, os, json, stat, shutil, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), "publishDev")]
from PySide6 import QtWidgets, QtCore
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
import maya.standalone; maya.standalone.initialize()
import maya.cmds as cmds
import buildTool_api as api
import buildTool_ui as ui
import publishTool_anim as anim
import publishTool_textures as tex
import pipeEnv

pub = api.pub
ok = []
def check(label, cond):
    ok.append(bool(cond)); print("PASS" if cond else "FAIL", label)

base = tempfile.mkdtemp(prefix="buildcache_")
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

# Scout's rig on H: body_geo in cache_SET, with a shader (so it has a look).
cmds.file(new=True, force=True)
cmds.workspace(scout_s, openWorkspace=True)
rig = cmds.group(empty=True, name="scout_rig")
body = cmds.parent(cmds.polyCube(name="body_geo")[0], rig)[0]
ctl = cmds.parent(cmds.circle(name="root_ctl")[0], rig)[0]
cmds.parent(body, ctl)
sh = cmds.shadingNode("lambert", asShader=True, name="skin_MTL")
sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name="skinSG")
cmds.connectAttr(sh + ".outColor", sg + ".surfaceShader")
cmds.sets("body_geo", edit=True, forceElement=sg)
# A textured shader on two faces, so the look carries a texture and a
# per-face assignment.
tex_path = os.path.join(scout_s, "sourceimages", "eye.png")
os.makedirs(os.path.dirname(tex_path))
open(tex_path, "wb").write(b"eye")
eye = cmds.shadingNode("lambert", asShader=True, name="eye_MTL")
eye_sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name="eyeSG")
cmds.connectAttr(eye + ".outColor", eye_sg + ".surfaceShader")
f = cmds.shadingNode("file", asTexture=True, name="eye_file")
cmds.setAttr(f + ".fileTextureName", "sourceimages/eye.png", type="string")
cmds.connectAttr(f + ".outColor", eye + ".color")
cmds.sets("body_geo.f[0:1]", edit=True, forceElement=eye_sg)
cmds.sets(["body_geo"], name=pub.CACHE_SET)
cmds.sets([ctl], name=pub.BODY_CONTROLS_SET)
rig_scene = os.path.join(scout_s, "scenes", "rig_work.ma")
cmds.file(rename=rig_scene); cmds.file(save=True, type="mayaAscii")
plan = pub.plan_publish(rig_scene, H, SC, "rig")
plan.update(objects=["scout_rig"], sg_asset={"type": "Asset", "id": 99}, cache_set=pub.CACHE_SET,
            control_sets={"body": pub.BODY_CONTROLS_SET, "face": None})
plan["set_uuids"] = cmds.ls([pub.CACHE_SET, pub.BODY_CONTROLS_SET], uuid=True)
pub.export_rig_to_h_drive(["scout_rig"], plan, rig_scene, tex.collect(["scout_rig"]), [])
rig_file = plan["dest"]
check("rig published with a look", plan.get("look", {}).get("shading_groups") == 2)

# The shot: the rig referenced and animated, then two Final publishes.
cmds.file(new=True, force=True)
cmds.file(rig_file, reference=True, namespace="scout_rig")
ctl = cmds.ls("scout_rig:root_ctl")[0]
cmds.setKeyframe(ctl + ".tx", time=1, value=0)
cmds.setKeyframe(ctl + ".tx", time=10, value=5)
cmds.playbackOptions(minTime=1, maxTime=10)
anim_scene = os.path.join(shot_s, "scenes", "anim", LOGIN, "anim_work.ma")
os.makedirs(os.path.dirname(anim_scene))
cmds.file(rename=anim_scene); cmds.file(save=True, type="mayaAscii")


def publish_final():
    items = anim.classify([ctl])
    p = anim.plan_anim(anim_scene, H, SC, items, anim.ANIM_CODE)
    p["stage"] = anim.FINAL
    anim.write_anim(items, p, 1, 10, anim_scene)
    return items[0], p


item, p1 = publish_final()
files = p1["item_files"][item["name"]]
info = json.load(open(files["cache_info"]))
check("cache .json beside the Alembic", os.path.isfile(files["cache"])
      and os.path.dirname(files["cache_info"]) == os.path.dirname(files["cache"]))
check("cache .json: item, the rig version it came from, frames, roots",
      info["item"] == "scoutrig" and info["kind"] == "rig"
      and info["asset"]["department"] == "rig" and info["asset"]["version"] == 1
      and (info["start"], info["end"]) == (1, 10) and info["roots"] == ["body_geo"])
check("cache .json read-only", not os.access(files["cache_info"], os.W_OK))

# --- Build lists it
caches = api.list_shot_caches(H, FILM, SEQ, SHOT)
check("one cache entry for the item, typed by its asset",
      len(caches) == 1 and (caches[0]["kind"], caches[0]["asset_type"], caches[0]["asset"],
                            caches[0]["code"]) == ("cache", "character", "scoutrig", "cache"))
c = caches[0]
vid1 = api.version_id(LOGIN, 1)
check("version v001 (scout), latest", list(c["versions"]) == [vid1] and c["latest"] == vid1
      and c["cache_info"][vid1]["asset"]["version"] == 1)

# --- Build references it beside the live rig
cmds.file(new=True, force=True)
cmds.file(rig_file, reference=True, namespace="scout_rig")
build_scene = os.path.join(shot_s, "scenes", "anim", LOGIN, "compare.ma")
cmds.file(rename=build_scene); cmds.file(save=True, type="mayaAscii")
done, warning, replaced = api.build_asset(shot_s, c, vid1)
print("   ", done, warning)
refs = [(n, w) for n, w, _, _ in api.scene_references() if w.lower().endswith(".abc")]
check("cache referenced, through $PIPE_SCRATCH, from scratch publish\\",
      len(refs) == 1 and refs[0][1].startswith("$PIPE_SCRATCH/")
      and "/publish/sequences/EAP_010/EAP_010_010/cache/alembic/scout/" in refs[0][1])
check("cache in its own namespace beside the rig", cmds.objExists("scoutrig_cache:body_geo")
      and cmds.objExists("scout_rig:body_geo"))
group = cmds.ls("scoutrig_cache_GRP")
check("cache in scoutrig_cache_GRP, display type Reference",
      group and cmds.getAttr(group[0] + ".overrideEnabled")
      and cmds.getAttr(group[0] + ".overrideDisplayType") == 2)
cmds.currentTime(10)
check("cache plays the animation", abs(cmds.xform("scoutrig_cache:body_geo", query=True,
                                                    worldSpace=True, translation=True)[0] - 5) < 0.01)
check("scene_version sees the cache", api.scene_version(shot_s, c) == vid1)


def engine_of(member):
    """Shading groups the cache mesh (or some of its faces) is a member of.
    Membership, not connections: the Alembic's own default assignment can
    leave a stale component connection to initialShadingGroup inside the
    reference, which Maya ignores."""
    name = member.split("|")[-1]
    return set(sg for sg in cmds.ls(type="shadingEngine")
               if any(m == name or m.startswith(name + ".") or m.startswith(name + "Shape")
                      for m in cmds.sets(sg, query=True) or []))


cache_body = cmds.ls("scoutrig_cache:body_geo", long=True)[0]
engines = engine_of(cache_body)
check("the rig's look is on the cache: its two shading groups",
      engines == {"scoutrig_cache_look:skinSG", "scoutrig_cache_look:eyeSG"})
check("look's shading group fed by its imported material",
      cmds.listConnections("scoutrig_cache_look:skinSG.surfaceShader") == ["scoutrig_cache_look:skin_MTL"])
check("per-face: eyeSG on the cache's two faces",
      sorted(cmds.sets("scoutrig_cache_look:eyeSG", query=True) or []) == ["body_geo.f[0:1]"]
      or any(m.endswith(".f[0:1]") for m in cmds.sets("scoutrig_cache_look:eyeSG", query=True) or []))
p = cmds.getAttr("scoutrig_cache_look:eye_file.fileTextureName")
check("look's texture resolves on this drive (pulled with the look)",
      p.startswith("$PIPE_SCRATCH/") and os.path.isfile(os.path.expandvars(p)))
check("cache group records the look it wears",
      cmds.getAttr("scoutrig_cache_GRP.pipe_look") == "scout_scout_rig_v001_look.ma")
check("the build said so", any("look v001 put on (2 shaders)" in d for d in done))
done, _, _ = api.build_asset(shot_s, c, vid1)
check("building again: already up to date, look not imported twice",
      done == ["already up to date"] and len(cmds.ls("scoutrig_cache_look*:skin_MTL")) == 1)

# --- a newer Final: updated in place, never a second reference
item, p2 = publish_final()
c = api.list_shot_caches(H, FILM, SEQ, SHOT)[0]
vid2 = api.version_id(LOGIN, 2)
check("v002 listed as latest", c["latest"] == vid2)
done, warning, replaced = api.build_asset(shot_s, c, vid2)
print("   ", done)
refs = [(n, w) for n, w, _, _ in api.scene_references() if w.lower().endswith(".abc")]
check("updated: still one cache reference, now v002",
      len(refs) == 1 and refs[0][1].endswith("EAP_010_010_scoutrig_anim_v002.abc"))
check("updated: same namespace and group", cmds.objExists("scoutrig_cache:body_geo")
      and cmds.objExists("scoutrig_cache_GRP"))
check("the old version is offered for clearing", replaced and replaced.endswith("_v001.abc"))
cache_body = cmds.ls("scoutrig_cache:body_geo", long=True)[0]
check("updated: same rig, so the look stays on",
      set(engine_of(cache_body)) == {"scoutrig_cache_look:skinSG", "scoutrig_cache_look:eyeSG"})

# --- which look: Lighting takes the newest LookDev look, Animation the rig's
lookdev = os.path.join(H, FILM, "maya", "assets", "character", "scout", "scenes", LOGIN,
                       "scout_scout_lookDev_v001")
shutil.copy2(rig_file, lookdev + ".ma")
rig_look = os.path.splitext(rig_file)[0] + "_look"
for ext in (".ma", ".json"):
    shutil.copy2(rig_look + ext, lookdev + "_look" + ext)
info = c["cache_info"][vid2]
pick = lambda dept: os.path.basename(api.look_for_cache(H, FILM, info, dept)[0])
check("Animation: the rig's look", pick("anim") == "scout_scout_rig_v001_look.ma")
check("Lighting: the LookDev look", pick("lighting") == "scout_scout_lookDev_v001_look.ma")
os.chmod(lookdev + "_look.ma", stat.S_IWRITE); os.remove(lookdev + "_look.ma")
check("Lighting, LookDev has no look: the rig's", pick("lighting") == "scout_scout_rig_v001_look.ma")
check("made in the shot: no look", api.look_for_cache(H, FILM, {"kind": "shot", "asset": {}}) is None)

# --- the Build tab: Animation's list gets the shot's caches by itself
parent = QtWidgets.QWidget()
cmds.file(save=True, type="mayaAscii")
tab = ui.BuildShotTab(lambda: (H, SC), parent)
tab.refresh()
rows = [r for r in tab._rows if r.get("kind") == "cache"]
check("Animation: the shot's caches are in the list, no Keys", tab.department() == "anim"
      and len(rows) == 1 and rows[0]["asset"] == "scoutrig" and rows[0]["keys_chosen"] is None)
check("the cache row knows it's in the scene at v002, unticked",
      rows[0]["in_scene"] == vid2 and not rows[0]["checked"])
check("caches aren't offered by the picker",
      not [n for _, n in tab._items_for(FILM, "anim", "shot") if "cache" in n.lower()])
tab._on_department_changed()
check("no doubles when the department is picked again",
      len([r for r in tab._rows if r.get("kind") == "cache"]) == 1)

# A fresh scene in the shot: the cache joins unticked and stays off the
# shot's saved list until it's built.
cmds.file(new=True, force=True)
fresh = os.path.join(shot_s, "scenes", "anim", LOGIN, "fresh.ma")
cmds.file(rename=fresh); cmds.file(save=True, type="mayaAscii")
tab.refresh()
rows = [r for r in tab._rows if r.get("kind") == "cache"]
check("fresh scene: cache in the list, unticked", len(rows) == 1 and not rows[0]["checked"]
      and rows[0]["in_scene"] is None)
tab._save_shot_list()
check("an unbuilt cache isn't saved to the shot's list",
      not any(k.endswith("/cache") for k in api.read_shot_list(H, FILM, SEQ, SHOT) or []))
check("Layout doesn't build caches", api.CACHE_CODE not in api.builds_for("layout"))
tab.picker.set_current(code="layout")
cmds.file(new=True, force=True)
layout_scene = os.path.join(shot_s, "scenes", "layout", LOGIN, "layout.ma")
os.makedirs(os.path.dirname(layout_scene))
cmds.file(rename=layout_scene); cmds.file(save=True, type="mayaAscii")
tab.refresh()
check("a Layout scene's list has no caches", tab.department() == "layout"
      and not [r for r in tab._rows if r.get("kind") == "cache"])

print("\n%d/%d passed" % (sum(ok), len(ok)))
for root, dirs, fs in os.walk(base):
    for f in fs:
        os.chmod(os.path.join(root, f), stat.S_IWRITE)
shutil.rmtree(base, ignore_errors=True)
maya.standalone.uninitialize()
