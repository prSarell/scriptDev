# Environment publish (spec §4c, DECIDED 2026-10-21): published from a
# shot's layout scene to an environment asset by its sets. landscape_SET
# stays put and is cleaned up like a model; building_SET holds one
# buildings group with a group per building (named freely, 2026-10-22),
# transforms kept, a <group>_LOC per building; sky_SET keeps transforms, locked,
# its image travels; a one-frame .abc of landscape + buildings goes beside
# the publish; the working scene is never changed. Built like the user's
# SEQ010_140 environment_001.ma. ShotGrid and the playblast are stubbed.
# Run: mayapy test_envPublish_mayapy.py
import sys, os, stat, json, shutil, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), "buildDev")]
from PySide6 import QtGui
import maya.standalone; maya.standalone.initialize()
import maya.cmds as cmds
import publishTool_api as api
import publishTool_env as env
import buildTool_api as build

ok = []
def check(label, cond):
    ok.append(bool(cond)); print("PASS" if cond else "FAIL", label)

base = tempfile.mkdtemp(prefix="envpub_")
H, SC = os.path.join(base, "H"), os.path.join(base, "scratch")
FILM = "NWF_SHF"
for asset in ("scoutsHouseLandscape", "shed"):
    os.makedirs(os.path.join(H, FILM, "maya", "assets", "environment", asset, "scenes"))
shot_scenes = os.path.join(SC, FILM, "maya", "sequences", "SEQ010", "SEQ010_140", "scenes")
os.makedirs(shot_scenes)
outside = os.path.join(base, "projects", "nwf_PREVIS", "sourceimages", "skys")
os.makedirs(outside)
sky_png = os.path.join(outside, "sky_blue_wispy_001.png")
image = QtGui.QImage(4, 4, QtGui.QImage.Format_RGB32); image.fill(0x6699cc); image.save(sky_png)

api.who = lambda: "scout"
api.artist_name = lambda login: "Test Person"
api.check_rv = lambda: None
api.find_rvio = lambda: ""
api.find_shotgrid_asset = lambda plan, h_root: {"id": 4242, "code": plan["asset"]}
frames = os.path.join(base, "frames")
def fake_playblast(plan, count, objects=None, camera=None):
    shown.append(sorted(o.split("|")[-1] for o in objects or []))
    os.makedirs(frames, exist_ok=True)
    return frames, []
shown = []
api.playblast_frames = fake_playblast
class FakeSG(object):
    def upload_playblast(self, *a, **k): return {"id": 1, "type": "Version"}
    def get_connection(self): raise RuntimeError("no ShotGrid in the test")
api._shotgrid = lambda: FakeSG()
TARGET = ("environment", "scoutsHouseLandscape")


def layout_scene(pieces_moved=False):
    """environment > sky / landscape / shed, as in environment_001.ma, but
    with shed's placement on the group (or on its pieces, the problem case)."""
    cmds.file(new=True, force=True)
    top = cmds.group(empty=True, name="environment")
    sky = cmds.group(empty=True, name="sky", parent=top)
    plane = cmds.imagePlane(fileName=sky_png.replace("\\", "/"))
    plane = cmds.parent(cmds.rename(plane[0], "imagePlanesky"), sky)[0]
    cmds.rename(cmds.listRelatives(plane, shapes=True, fullPath=True)[0], "imagePlaneskyShape")
    cmds.setAttr("imagePlanesky.translate", -6700, 11748, -89214)
    land = cmds.group(empty=True, name="landscape", parent=top)
    ground = cmds.polyPlane(name="ground")[0]
    cmds.parent(ground, land)
    cmds.setAttr(ground + ".translate", 0, -169, -41792); cmds.setAttr(ground + ".scale", 800, 800, 800)
    # A projected texture whose placement sits under the ground, like
    # fieldA's snowLand_snowPlace (2026-10-30: the original came out with
    # its parents, outside the pipe group).
    place = cmds.parent(cmds.shadingNode("place3dTexture", asUtility=True,
                                         name="snowLand_snowPlace"), ground)[0]
    proj = cmds.shadingNode("projection", asTexture=True, name="snowProj")
    cmds.connectAttr(place + ".worldInverseMatrix[0]", proj + ".placementMatrix")
    mat = cmds.shadingNode("lambert", asShader=True, name="snowMat")
    cmds.connectAttr(proj + ".outColor", mat + ".color")
    sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name="snowMatSG")
    cmds.connectAttr(mat + ".outColor", sg + ".surfaceShader")
    cmds.sets(ground, edit=True, forceElement=sg)
    buildings = cmds.group(empty=True, name="buildings", parent=top)
    shed = cmds.group(empty=True, name="shed", parent=buildings)
    box = cmds.polyCube(name="pCube1")[0]
    cmds.parent(box, shed)
    cmds.setAttr(box + ".scale", 24, 5, 58)
    where = (shed if not pieces_moved else box)
    cmds.setAttr(where + ".translate", -8759, 61, -64975); cmds.setAttr(where + ".rotateY", -9.67)
    # A second building, named freely (no such asset on H).
    barn = cmds.group(empty=True, name="oldBarn", parent=buildings)
    cmds.parent(cmds.polyCube(name="barnBox")[0], barn)
    cmds.setAttr(barn + ".translate", 500, 0, -60000)
    camera = cmds.camera(name="camera1")[0]
    sets = [cmds.sets(["environment|landscape|ground"], name="landscape_SET"),
            cmds.sets(["environment|buildings"], name="building_SET"),
            cmds.sets(["environment|sky|imagePlanesky"], name="sky_SET")]
    cmds.sets(sets, name="environment_SET")
    scene = os.path.join(shot_scenes, "environment_001.ma")
    cmds.file(rename=scene); cmds.file(save=True, type="mayaAscii")
    return scene


def refused(text, **kw):
    try:
        api.publish(scene, H, SC, env.ENV_CODE, target=TARGET, **kw)
    except api.PublishError as e:
        print("   ", str(e).splitlines()[0])
        return text in str(e)
    return False

# -- Refusals, before anything is made -----------------------------------------
scene = layout_scene()
cmds.delete("environment_SET")
check("no environment_SET: refused, explaining the sets", refused("no environment_SET"))
scene = layout_scene()
cmds.sets("environment|buildings|shed", add="landscape_SET")
check("one thing in two roles: refused", refused("Each thing has one role"))
scene = layout_scene()
cmds.sets("environment|buildings", remove="building_SET")
cmds.sets("environment|buildings|shed", add="building_SET")
check("building_SET holding a building, not the buildings group: refused",
      refused("just one group called buildings"))
scene = layout_scene()
cmds.parent(cmds.polyCube(name="looseBox")[0], "environment|buildings")
check("a loose mesh inside buildings (not in its own group): refused", refused("isn't a group"))
check("nothing reached the H drive", not os.listdir(os.path.join(
    H, FILM, "maya", "assets", "environment", "scoutsHouseLandscape", "scenes")))

# -- The publish ---------------------------------------------------------------
scene = layout_scene()
before = (sorted(cmds.ls(long=True, type="transform")), cmds.getAttr("environment|buildings|shed.translate"),
          cmds.getAttr("ground.translate"), len(cmds.listHistory("ground")),
          sorted(cmds.ls(type="objectSet")), cmds.getAttr("imagePlaneskyShape.imageName"))
plan = api.publish(scene, H, SC, env.ENV_CODE, target=TARGET, frame_count=2)
check("working scene: the projection still placed by the original snowLand_snowPlace",
      cmds.listConnections("snowProj.placementMatrix")
      == ["snowLand_snowPlace"] and cmds.ls("environment|landscape|ground|snowLand_snowPlace"))
after = (sorted(cmds.ls(long=True, type="transform")), cmds.getAttr("environment|buildings|shed.translate"),
         cmds.getAttr("ground.translate"), len(cmds.listHistory("ground")),
         sorted(cmds.ls(type="objectSet")), cmds.getAttr("imagePlaneskyShape.imageName"))
# An environment asset's publish is its Modeling publish (user, 2026-10-30).
check("published from the shot's layout scene to the environment asset, as Modeling",
      os.path.basename(plan["dest"]) == "scoutsHouseLandscape_scout_model_v001.ma"
      and plan["code"] == "model"
      and os.sep + os.path.join("environment", "scoutsHouseLandscape", "scenes", "scout") in plan["dest"])
check("read-only on H", not os.access(plan["dest"], os.W_OK))
check("one-frame reference cache beside it", os.path.isfile(env.cache_path(plan)))
check("working scene unchanged (names, placements, history, sets, image path)", before == after)
check("playblast showed the environment's things",
      shown[-1] == ["ground", "imagePlanesky", "oldBarn", "shed"])
check("warned: the sky image isn't in an asset's sourceimages",
      any("sourceimages" in w for w in plan.get("warnings", [])))
check("building names are free: no warning for oldBarn (no such asset on H)",
      not any("oldBarn" in w for w in plan.get("warnings", [])))

cmds.file(new=True, force=True); cmds.file(plan["dest"], open=True, force=True)
G = "scoutsHouseLandscape_model_GRP"
check("top is the stamped pipe group (Modeling), locked", cmds.nodeType(G) == "dagContainer"
      and cmds.getAttr(G + ".pipe_department") == "model" and cmds.getAttr(G + ".tx", lock=True))
check("laid out by role", sorted(cmds.listRelatives(G, children=True)) ==
      ["buildings", "landscape", "locators", "sky"])
check("nothing outside the pipe group (no original environment came along)",
      [a for a in cmds.ls(assemblies=True) if a not in ("persp", "top", "front", "side")]
      == [G] and not cmds.ls("pipeTmp_*", recursive=True))
place = cmds.ls("snowLand_snowPlace", long=True)
check("one texture placement, inside the pipe group, driving the projection",
      len(place) == 1 and place[0].startswith("|" + G + "|landscape|ground|")
      and cmds.listConnections("snowProj.placementMatrix", fullNodeName=True)
      and cmds.ls(cmds.listConnections("snowProj.placementMatrix")[0], long=True) == place)
g = G + "|landscape|ground"
bb = cmds.exactWorldBoundingBox(g)
check("landscape frozen and history gone, but still where it was",
      cmds.getAttr(g + ".translate")[0] == (0, 0, 0) and abs((bb[2] + bb[5]) / 2 + 41792) < 1
      and not cmds.ls(type="polyPlane"))
s = G + "|buildings|shed"
check("building keeps its transforms", [round(v, 2) for v in cmds.getAttr(s + ".translate")[0]]
      == [-8759, 61, -64975] and round(cmds.getAttr(s + ".rotateY"), 2) == -9.67)
loc = G + "|locators|shed_LOC"
same = all(abs(a - b) < 1e-3 for a, b in zip(cmds.xform(loc, query=True, worldSpace=True, matrix=True),
                                             cmds.xform(s, query=True, worldSpace=True, matrix=True)))
check("shed_LOC sits exactly at the building's placement", cmds.objExists(loc) and same)
check("each building has its own locator", sorted(cmds.listRelatives(G + "|locators")) ==
      ["oldBarn_LOC", "shed_LOC"] and [round(v) for v in cmds.xform(
          G + "|locators|oldBarn_LOC", query=True, worldSpace=True, translation=True)]
      == [500, 0, -60000])
k = G + "|sky|imagePlanesky"
check("sky keeps its transforms, locked", round(cmds.getAttr(k + ".tx")) == -6700
      and cmds.getAttr(k + ".tx", lock=True) and cmds.getAttr(k + ".ry", lock=True))
check("sets come with it, holding the copies",
      sorted(cmds.sets("environment_SET", query=True)) == ["building_SET", "landscape_SET", "sky_SET"]
      and [n.split("|")[-1] for n in cmds.sets("building_SET", query=True)] == ["buildings"])
check("... so the published layout passes the same check (can be published again)",
      sorted(env._short(b) for b in env.check_environment()[env.BUILDINGS])
      == ["oldBarn", "shed"])
imn = cmds.getAttr(cmds.listRelatives(k, shapes=True, fullPath=True)[0] + ".imageName")
check("sky image points at the publish's copy through $PIPE_SCRATCH",
      imn.startswith("$PIPE_SCRATCH/NWF_SHF/maya/publish/assets/environment/scoutsHouseLandscape/"
                     "sourceimages/scout/scoutsHouseLandscape_scout_model_v001/"))
tex_dir = os.path.join(H, FILM, "maya", "assets", "environment", "scoutsHouseLandscape",
                       "sourceimages", "scout", "scoutsHouseLandscape_scout_model_v001")
check("sky image copied to H for this version", os.path.isfile(os.path.join(tex_dir, "sky_blue_wispy_001.png")))
check("stamp lists buildings and locators",
      sorted(json.loads(cmds.getAttr(G + ".pipe_locators"))) == ["oldBarn_LOC", "shed_LOC"]
      and sorted(json.loads(cmds.getAttr(G + ".pipe_buildings"))) == ["oldBarn", "shed"])

cmds.file(new=True, force=True)
cmds.loadPlugin("AbcImport", quiet=True)
cmds.AbcImport(env.cache_path(plan).replace("\\", "/"), mode="import")
check("the cache holds the landscape and buildings, not the sky",
      cmds.objExists("ground") and cmds.objExists("pCube1") and not cmds.ls(type="imagePlane"))

# -- Build: pulled with its cache; a real house snapped to the locator ----------
published = [p for p in build.list_buildable(H, FILM) if p["asset"] == "scoutsHouseLandscape"]
check("Build lists the environment publish, as Modeling", len(published) == 1
      and published[0]["code"] == "model")
maya_dir = os.path.join(SC, FILM, "maya")
dest, _ = build.copy_published(plan["dest"], maya_dir)
check("pulled with its cache and its sky image",
      os.path.isfile(os.path.splitext(dest)[0] + ".abc")
      and os.path.isfile(os.path.join(build.texture_folder_of(dest), "sky_blue_wispy_001.png")))
check("clearing that version takes the cache too", os.path.splitext(dest)[0] + ".abc"
      in build.version_files(dest))
cmds.file(new=True, force=True)
cmds.file(dest, reference=True, namespace="scoutsHouseLandscape_env")
house = api.make_pipe_group("shed_model_GRP")          # a model publish's group: locked at 0,0,0
cube = cmds.polyCube(name="shedModel")[0]
cmds.parent(cube, house)
api.finish_pipe_group(house)
rloc = "scoutsHouseLandscape_env:shed_LOC"
cmds.parent(house, cmds.ls(rloc, long=True)[0], relative=True)
placed = cmds.xform(cmds.ls("shedModel", long=True)[0], query=True, worldSpace=True, translation=True)
check("a published house parented under its locator lands at the placement, still locked",
      [round(v) for v in placed] == [-8759, 61, -64975]
      and cmds.getAttr(cmds.ls("shed_model_GRP", long=True)[0] + ".tx", lock=True))

# -- A building group with no transforms (like environment_001.ma's shed):
#    published, not refused; the locator comes from its pieces ---------------
scene = layout_scene(pieces_moved=True)
box = cmds.exactWorldBoundingBox("environment|buildings|shed")
plan2 = api.publish(scene, H, SC, env.ENV_CODE, target=TARGET, frame_count=2)
check("no transforms on the building: still published", plan2["version"] == 2)
check("... and the report says how its locator was placed",
      any("shed has no transforms" in w and "-9.7" in w for w in plan2.get("warnings", [])))
cmds.file(new=True, force=True); cmds.file(plan2["dest"], open=True, force=True)
loc = G + "|locators|shed_LOC"
t = cmds.xform(loc, query=True, worldSpace=True, translation=True)
check("locator at the bottom-centre of the pieces",
      abs(t[0] - (box[0] + box[3]) / 2) < 1e-2 and abs(t[1] - box[1]) < 1e-2
      and abs(t[2] - (box[2] + box[5]) / 2) < 1e-2)
check("... turned like the pieces", abs(cmds.xform(loc, query=True, worldSpace=True,
                                                   rotation=True)[1] + 9.67) < 1e-2)
check("... and the building itself is left as it was (group at 0, pieces placed)",
      cmds.getAttr(G + "|buildings|shed.translate")[0] == (0, 0, 0)
      and round(cmds.getAttr(G + "|buildings|shed|pCube1.translateX")) == -8759)

# -- No buildings and no sky (user, 2026-10-26): their groups left empty, as
#    the layout tool makes them, or a set emptied -- published without -------
scene = layout_scene()
cmds.sets("environment|sky|imagePlanesky", remove="sky_SET")
cmds.sets("environment|sky", add="sky_SET")      # the group, as the layout tool sets it up
cmds.delete("environment|buildings|shed", "environment|buildings|oldBarn",
            "environment|sky|imagePlanesky")
plan3 = api.publish(scene, H, SC, env.ENV_CODE, target=TARGET, frame_count=2)
check("landscape only: still published", plan3["version"] == 3)
check("... with a note that there are no buildings or sky",
      any("No buildings or sky" in w for w in plan3.get("warnings", [])))
check("... and only the landscape in it", plan3["environment"][env.BUILDINGS] == []
      and plan3["environment"][env.SKY] == [] and plan3["environment"]["locators"] == [])
cmds.file(new=True, force=True); cmds.file(plan3["dest"], open=True, force=True)
check("... the published landscape-only layout passes the check again",
      [n.split("|")[-1] for n in env.check_environment()[env.LANDSCAPE]] == ["ground"])
scene = layout_scene()
cmds.sets(clear="landscape_SET"); cmds.sets(clear="building_SET"); cmds.sets(clear="sky_SET")
check("all three empty: refused", refused("nothing to publish"))

# -- Output files for other software (2026-10-30): an environment is a
#    Modeling publish, so it can tick them too ---------------------------------
import publishTool_outputs as outputs
scene = layout_scene()
plan4 = api.publish(scene, H, SC, env.ENV_CODE, target=TARGET, frame_count=2,
                    outputs=["fbx", "usd"])
folder = outputs.folder_of(plan4["dest"])
stem = os.path.splitext(os.path.basename(plan4["dest"]))[0]
check("environment + FBX/USD ticked: both in its exports folder, its .abc cache still beside",
      os.path.isfile(os.path.join(folder, stem + ".fbx"))
      and os.path.isfile(os.path.join(folder, stem + ".usdz"))
      and os.path.isfile(env.cache_path(plan4)))
check("the asset remembers FBX and USD",
      outputs.remembered(H, FILM, "environment", "scoutsHouseLandscape") == ["usd", "fbx"])
cmds.file(new=True, force=True); cmds.file(plan4["dest"], open=True, force=True)
check("... and the published .ma is still clean (nothing outside the group)",
      [a for a in cmds.ls(assemblies=True) if a not in ("persp", "top", "front", "side")]
      == ["scoutsHouseLandscape_model_GRP"])
print("%d/%d passed" % (sum(ok), len(ok)))
for root, dirs, files in os.walk(base):
    for f in files:
        os.chmod(os.path.join(root, f), stat.S_IWRITE)
shutil.rmtree(base, ignore_errors=True)
