# Build loads a published model's USD (spec §4h, user 2026-11-23: "I was
# hoping that publishing a model as USD would mean loading it as usd in
# another scene"). A Modeling publish with USD ticked has
# <name>_exports\<name>.usd beside its .ma; Build's USD tick pulls that .usd
# and its textures (not the .ma) into scratch's publish\ and loads it as a
# USD stage by $PIPE_SCRATCH path. One asset is a Maya reference or a USD
# stage, never both: switching asks, removes the other, keeps placement.
# Never touches the real drives or Maya prefs. Run: mayapy test_buildUsd_mayapy.py
import sys, os, json, shutil, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HERE = os.path.dirname(os.path.abspath(__file__))
PIPE = os.path.dirname(HERE)
sys.path[:0] = [HERE, os.path.join(PIPE, "publishDev")]
from PySide6 import QtWidgets
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
import maya.standalone; maya.standalone.initialize()
import maya.cmds as cmds
import buildTool_api as api
import buildTool_ui as ui
import pipeEnv
import publishTool_outputs as outputs
import publishTool_anim as anim
pub = api.pub

ok = []
def check(label, cond):
    ok.append(bool(cond)); print("PASS" if cond else "FAIL", label)

def refused(call, *args, **kw):
    try:
        call(*args, **kw)
    except api.BuildError as e:
        return str(e)
    return ""

base = tempfile.mkdtemp(prefix="buildUsd_")
_cfg = os.path.join(base, "pipeline_config.json")
pub._config_path = lambda: _cfg
H, S = os.path.join(base, "H"), os.path.join(base, "scratch")
FILM = "NWF_SHF"
pub.save_config({pub.H_DRIVE: H, "scratch_root": S, "publish_as": "e131988"})
pub.set_root(pub.SCRATCH, S)
api.load_usd_plugin()

# -- grassB published three times: v001 and v003 with USD, v002 without -------
h_scenes = os.path.join(H, FILM, "maya", "assets", "environment", "grassB", "scenes",
                        "model", "e131988")
os.makedirs(h_scenes)
src_tex = os.path.join(base, "grass.png")
open(src_tex, "wb").write(b"png")

def publish(version, usd):
    stem = "grassB_e131988_model_v%03d" % version
    cmds.file(new=True, force=True)
    blade = cmds.polyCube(name="grassB_blade_GEO", height=version)[0]
    shader = cmds.shadingNode("lambert", asShader=True, name="grass_mtl")
    sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name="grass_mtlSG")
    cmds.connectAttr(shader + ".outColor", sg + ".surfaceShader")
    cmds.sets(blade, edit=True, forceElement=sg)
    f = cmds.shadingNode("file", asTexture=True, name="grass_file")
    cmds.setAttr(f + ".fileTextureName", src_tex, type="string")
    cmds.connectAttr(f + ".outColor", shader + ".color")
    render = cmds.group(blade, name="render")
    geo = cmds.group(render, name="geo")
    grp = pub.make_pipe_group("grassB_model_GRP")
    cmds.parent(geo, grp)
    pub._stamp(grp, [("sgAssetId", 1600), ("asset", "grassB"), ("assetType", "environment"),
                     ("department", "model"), ("version", version), ("artistId", "e131988")])
    pub.finish_pipe_group(grp)
    if usd:
        folder = os.path.join(h_scenes, stem + api.EXPORTS_SUFFIX)
        os.makedirs(folder)
        outputs._usd([cmds.ls(grp, long=True)[0]], os.path.join(folder, stem + ".usd"),
                     {"grass.png": src_tex})
    cmds.file(rename=os.path.join(h_scenes, stem + ".ma"))
    cmds.file(save=True, type="mayaAscii")

for v, usd in ((1, True), (2, False), (3, True)):
    publish(v, usd)
check("the exports folder name matches Publish's",
      api.EXPORTS_SUFFIX == outputs.FOLDER_SUFFIX)

grass = [p for p in api.list_buildable(H, FILM) if p["asset"] == "grassB"][0]
v1, v2, v3 = ("e131988/v%03d" % v for v in (1, 2, 3))
check("usd_export finds v001's .usd on H",
      (api.usd_export(grass["versions"][v1]) or "").endswith(
          os.path.join("grassB_e131988_model_v001_exports", "grassB_e131988_model_v001.usd")))
check("has_usd: v001 and v003 yes, v002 (no USD ticked) no",
      api.has_usd(grass, v1) and api.has_usd(grass, v3) and not api.has_usd(grass, v2))
check("only models and environments can load as USD",
      api.can_load_usd(grass) and not api.can_load_usd(dict(grass, code="rig"))
      and not api.can_load_usd(dict(grass, kind="camera")))
files, missing = api.usd_files(api.usd_export(grass["versions"][v1]))
check("usd_files: the .usd and its texture, nothing missing",
      [os.path.basename(f) for f in files] == ["grassB_e131988_model_v001.usd", "grass.png"]
      and not missing)

# -- a shot scene on scratch ---------------------------------------------------
shot_dir = api.shot_folder(S, FILM, "SEQ010", "SEQ010_120")
os.makedirs(os.path.join(H, FILM, "maya", "sequences", "SEQ010", "SEQ010_120"))
scene = os.path.join(shot_dir, "scenes", "anim", "e131988", "shot_001.ma")
os.makedirs(os.path.dirname(scene))
open(os.path.join(shot_dir, "workspace.mel"), "w").write("")
cmds.workspace(shot_dir, openWorkspace=True)
cmds.file(new=True, force=True)
cmds.file(rename=scene)
cmds.file(save=True, type="mayaAscii")
maya_dir = api.maya_dir_of_shot(shot_dir)
pulled_usd = os.path.join(api.publish_dir(maya_dir), "assets", "environment", "grassB",
                          "scenes", "model", "e131988", "grassB_e131988_model_v001_exports",
                          "grassB_e131988_model_v001.usd")
pulled_ma = os.path.join(api.publish_dir(maya_dir), "assets", "environment", "grassB",
                         "scenes", "model", "e131988", "grassB_e131988_model_v001.ma")

check("v002 has no USD: refused, saying to publish with USD ticked",
      "published without USD ticked" in refused(api.build_asset, shot_dir, grass, v2, usd=True))
done, warning, replaced = api.build_asset(shot_dir, grass, v1, usd=True)
stage = api.stage_of(grass)
check("built as USD: a stage grassB_USD", stage and stage[0] == "|grassB_USD"
      and "loaded as a USD stage" in done[-1] and not warning)
check("... reading the pulled .usd by $PIPE_SCRATCH path",
      stage[2].startswith("$" + pipeEnv.VAR + "/") and stage[2].endswith(
          "grassB_e131988_model_v001_exports/grassB_e131988_model_v001.usd"))
check("... the .usd and its texture pulled, the .ma not",
      os.path.isfile(pulled_usd)
      and os.path.isfile(os.path.join(os.path.dirname(pulled_usd), "textures", "grass.png"))
      and not os.path.isfile(pulled_ma))
check("... read-only, like every pulled publish", not os.access(pulled_usd, os.W_OK))
import mayaUsd.ufe
usd_stage = mayaUsd.ufe.getStage(stage[1])
check("... Maya's stage has the model (default prim, the blade mesh)",
      usd_stage and usd_stage.GetDefaultPrim().GetName() == "grassB_model_GRP"
      and usd_stage.GetPrimAtPath("/grassB_model_GRP/geo/render/grassB_blade_GEO").IsValid())
entry = api.read_manifest(shot_dir)[api.manifest_key("environment", "grassB", "model")]
check("manifest: usd, the .usd as the shot's file",
      entry.get("usd") is True and entry["shared"].endswith(".usd") and entry["version"] == 1)
check("scene_version reads the stage's version", api.scene_version(shot_dir, grass) == v1)
check("building it again: already up to date",
      api.build_asset(shot_dir, grass, v1, usd=True)[0] == ["already up to date"])
check("nothing referenced (no Maya reference made)", not api.scene_references())

# -- version update ------------------------------------------------------------
cmds.xform("grassB_USD", worldSpace=True, translation=(5, 0, -3))
done, warning, replaced = api.build_asset(shot_dir, grass, v3, usd=True)
stage = api.stage_of(grass)
check("v003: the same stage now reads v003, where it was placed",
      stage[0] == "|grassB_USD" and stage[2].endswith("grassB_e131988_model_v003.usd")
      and done == ["v001 -> v003 (e131988)"]
      and cmds.xform("grassB_USD", query=True, worldSpace=True, translation=True) == [5, 0, -3])
check("... v001's .usd is offered for clearing", replaced and pub._same_path(replaced, pulled_usd))
check("... and not in use any more (unused_versions)",
      api.unused_versions([replaced], maya_dir) == [replaced])
v3_pulled = api.shared_path(shot_dir, api.read_manifest(shot_dir)[
    api.manifest_key("environment", "grassB", "model")])
check("... v003's is in use (the stage reads it)", api.unused_versions([v3_pulled], maya_dir) == [])
check("version_files of a pulled .usd: it and its textures",
      sorted(os.path.basename(f) for f in api.version_files(v3_pulled))
      == ["grass.png", "grassB_e131988_model_v003.usd"])

# -- save and reopen: the path stays drive-independent ---------------------------
cmds.file(save=True, type="mayaAscii")
cmds.file(new=True, force=True)
cmds.file(scene, open=True, force=True)
stage = api.stage_of(grass)
check("reopened: the stage still reads $PIPE_SCRATCH/... v003",
      stage and stage[2].startswith("$" + pipeEnv.VAR) and api.scene_version(shot_dir, grass) == v3
      and mayaUsd.ufe.getStage(stage[1]).GetDefaultPrim().IsValid())

# -- Repair: the .usd wiped from scratch ----------------------------------------
os.chmod(v3_pulled, 0o666); os.remove(v3_pulled)
fixed, not_fixed = api.repair_scene(H)
check("Repair pulls a missing .usd back and reloads the stage",
      os.path.isfile(v3_pulled) and any("USD pulled again" in f for f in fixed) and not not_fixed)

# -- Animation publish refuses a stage -----------------------------------------
try:
    anim.classify(["grassB_USD"])
    refusal = ""
except pub.PublishError as e:
    refusal = str(e)
check("Animation publish refuses a USD stage, saying how to animate it",
      "is a USD stage" in refusal and "untick USD" in refusal)

# -- switching to a Maya reference and back --------------------------------------
check("as a Maya reference while it's a stage: refused unless asked",
      "is in this scene as a USD stage" in refused(api.build_asset, shot_dir, grass, v3))
done, warning, replaced = api.build_asset(shot_dir, grass, v3, replace=True)
check("replace: the stage goes, the .ma is referenced, placed where the stage was (on geo: the pipe group is locked)",
      not api.stage_of(grass) and cmds.referenceQuery("grassB:grassB_model_GRP",
                                                       isNodeReferenced=True)
      and [round(x, 3) for x in cmds.xform("grassB:geo", query=True,
                                           worldSpace=True, translation=True)] == [5, 0, -3])
check("... manifest: back to the .ma", not api.read_manifest(shot_dir)[
    api.manifest_key("environment", "grassB", "model")].get("usd"))
check("... the .usd is offered for clearing", replaced and replaced.endswith(".usd"))
cmds.xform("grassB:geo", worldSpace=True, translation=(1, 2, 3))
check("as USD while it's a Maya reference: refused unless asked",
      "is in this scene as a Maya reference" in refused(api.build_asset, shot_dir, grass, v3,
                                                        usd=True))
done, warning, replaced = api.build_asset(shot_dir, grass, v3, usd=True, replace=True)
check("replace: the reference goes, the stage is placed where the group was",
      not api.scene_references() and api.stage_of(grass)
      and [round(x, 3) for x in cmds.xform("grassB_USD", query=True, worldSpace=True,
                                           translation=True)] == [1, 2, 3]
      and "Maya reference removed" in done)

# -- the department's list remembers USD ----------------------------------------
h_shot = api.shot_folder(H, FILM, "SEQ010", "SEQ010_120")
key = api.manifest_key("environment", "grassB", "model")
api.write_build_list(h_shot, "anim", [key], usd=[key])
check("the build list saves which rows load as USD",
      api.read_build_list(h_shot, "anim") == [key] and api.read_build_list_usd(h_shot, "anim") == {key})

# -- the UI: a USD column ---------------------------------------------------------
cmds.file(save=True, type="mayaAscii")
cmds.file(new=True, force=True)
scene2 = os.path.join(shot_dir, "scenes", "anim", "e131988", "shot_002.ma")
cmds.file(rename=scene2)
cmds.file(save=True, type="mayaAscii")
parent = QtWidgets.QWidget()
tab = ui.BuildShotTab(lambda: (H, S), parent)
tab.refresh()
row = [i for i, r in enumerate(tab._rows) if r["asset"] == "grassB"]
check("a new scene: grassB comes back from the list, USD ticked", row and
      tab._rows[row[0]]["usd_chosen"]
      and tab.table.horizontalHeaderItem(ui.COL_USD).text() == "USD"
      and tab.table.item(row[0], ui.COL_USD).checkState() == ui.QtCore.Qt.Checked)
check("... no Keys menu on a USD row", tab.table.item(row[0], ui.COL_KEYS).text() == "-")
p = tab._rows[row[0]]
tab._on_version_changed(p, v2)
check("picking v002 (no USD) unticks USD and greys it out", not p["usd_chosen"]
      and not tab.table.item(row[0], ui.COL_USD).flags() & ui.QtCore.Qt.ItemIsEnabled)
tab._on_version_changed(p, v3)
tab.table.item(row[0], ui.COL_USD).setCheckState(ui.QtCore.Qt.Checked)
check("ticking USD again", p["usd_chosen"])
tab._build_shot()
check("Build loads it as a USD stage", api.stage_of(grass) and not api.scene_references()
      and "loaded as a USD stage" in tab.status._text)
check("the row now says it's in the scene as USD",
      ", USD" in tab.table.item(row[0], ui.COL_IN).text() and not p["checked"])

print("\n%d/%d passed" % (sum(ok), len(ok)))
shutil.rmtree(base, ignore_errors=True)
