# USD Edit (spec §4i, user 2026-11-24): pick a USD model in a shot, edit it
# for this shot or for the asset (every shot), save; the asset's edits go
# into its Maya model in the asset scene, ready to publish.
# Never touches the real drives or Maya prefs. Run: mayapy test_usdEdit_mayapy.py
import sys, os, shutil, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HERE = os.path.dirname(os.path.abspath(__file__))
PIPE = os.path.dirname(HERE)
sys.path[:0] = [HERE, os.path.join(PIPE, "publishDev"), os.path.join(PIPE, "buildDev")]
from PySide6 import QtWidgets
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
import maya.standalone; maya.standalone.initialize()
import maya.cmds as cmds
import buildTool_api as build
import publishTool_outputs as outputs
import modelTool_usd as usd
import modelTool_usdEdit as edit
import modelTool_usdEdit_ui      # the window must at least import
pub = build.pub

ok = []
def check(label, cond):
    ok.append(bool(cond)); print("PASS" if cond else "FAIL", label)

def refused(call, *args, **kw):
    try:
        call(*args, **kw)
    except pub.PublishError as e:
        return str(e)
    return ""

base = tempfile.mkdtemp(prefix="usdEdit_")
_cfg = os.path.join(base, "pipeline_config.json")
pub._config_path = lambda: _cfg
H, S = os.path.join(base, "H"), os.path.join(base, "scratch")
FILM = "NWF_SHF"
pub.save_config({pub.H_DRIVE: H, "scratch_root": S, "publish_as": "e131988"})
pub.set_root(pub.SCRATCH, S)
build.load_usd_plugin()
import mayaUsd.ufe, ufe
from pxr import Usd, UsdGeom, Gf

# -- the model scene on scratch, and shed v001 published with USD -------------
asset_dir = os.path.join(S, FILM, "maya", "assets", "environment", "shed")
model_scene = os.path.join(asset_dir, "scenes", "model", "e131988", "shed_work.ma")
os.makedirs(os.path.dirname(model_scene))
cmds.file(new=True, force=True)
cmds.file(rename=model_scene); cmds.file(save=True, type="mayaAscii")
usd.build()
wall = cmds.parent(cmds.polyCube(name="shed_wall_GEO")[0], "|geo_USD|render")[0]
roof = cmds.parent(cmds.polyCube(name="shed_roof_GEO")[0], "|geo_USD|render")[0]
cmds.move(0, 2, 0, "|geo_USD|render|shed_roof_GEO")
cmds.file(save=True, type="mayaAscii")

h_scenes = os.path.join(H, FILM, "maya", "assets", "environment", "shed", "scenes", "model",
                        "e131988")
os.makedirs(h_scenes)
stem = "shed_e131988_model_v001"
cmds.file(rename=os.path.join(base, "tmp_publish.ma"))
copy = cmds.duplicate("|geo_USD")[0]
copy = cmds.rename(copy, "geo")
grp = pub.make_pipe_group("shed_model_GRP")
cmds.parent(copy, grp)
pub._stamp(grp, [("sgAssetId", 1700), ("asset", "shed"), ("assetType", "environment"),
                 ("department", "model"), ("version", 1), ("artistId", "e131988")])
pub.finish_pipe_group(grp)
folder = os.path.join(h_scenes, stem + build.EXPORTS_SUFFIX)
os.makedirs(folder)
outputs._usd([cmds.ls(grp, long=True)[0]], os.path.join(folder, stem + ".usd"), {})
cmds.select(grp); cmds.file(os.path.join(h_scenes, stem + ".ma"), exportSelected=True,
                            type="mayaAscii", force=True)

shed = [p for p in build.list_buildable(H, FILM) if p["asset"] == "shed"][0]
v1 = "e131988/v001"

# -- a shot with shed loaded as USD ------------------------------------------------
shot_dir = build.shot_folder(S, FILM, "SEQ010", "SEQ010_160")
shot_scene = os.path.join(shot_dir, "scenes", "layout", "e131988", "shot.ma")
os.makedirs(os.path.dirname(shot_scene))
os.makedirs(os.path.join(H, FILM, "maya", "sequences", "SEQ010", "SEQ010_160"))
open(os.path.join(shot_dir, "workspace.mel"), "w").write("")
cmds.workspace(shot_dir, openWorkspace=True)
cmds.file(new=True, force=True)
cmds.file(rename=shot_scene); cmds.file(save=True, type="mayaAscii")
build.build_asset(shot_dir, shed, v1, usd=True)
transform, shape, _ = build.stage_of(shed)
stage = mayaUsd.ufe.getStage(shape)
WALL = "/shed_model_GRP/geo/render/shed_wall_GEO"
ROOF = "/shed_model_GRP/geo/render/shed_roof_GEO"

# -- picking -------------------------------------------------------------------------
cmds.select(clear=True)
check("nothing picked: no stage", edit.picked() == (None, None))
cmds.select("|shed_model_GRP")
check("the stage's pipe group picked: its stage", edit.picked() == (shape, None))
ufe.GlobalSelection.get().replaceWith(ufe.Selection())
ufe.GlobalSelection.get().append(ufe.Hierarchy.createItem(ufe.PathString.path(
    "%s,%s" % (shape, WALL))))
check("a USD prim picked (viewport / Outliner): its stage and prim path",
      edit.picked() == (shape, WALL))
check("asset_of reads the manifest key", edit.asset_of(shape) == ("environment", "shed", "model"))

# -- edit for this shot ------------------------------------------------------------
check("not editing yet (the shot layer is Build's default target)",
      edit.editing(shape) == edit.SHOT)
path = edit.begin(shape, edit.SHOT)
check("begin(shot): edits go to the shot layer",
      edit.editing(shape) == edit.SHOT and pub._same_path(path, build.shot_layer_path(shot_dir, shed)))
layers = edit.layers(shape)
check("... the published layer is set not to take edits",
      not layers["published"].permissionToEdit)
UsdGeom.XformCommonAPI(stage.GetPrimAtPath(WALL)).SetTranslate(Gf.Vec3d(3, 0, 0))
check("an edit made: the shot layer has unsaved edits", edit.dirty(shape) == [edit.SHOT])
check("save: the shot layer saved", edit.save(shape) == [edit.SHOT]
      and "xformOp:translate" in open(layers["shot"].realPath).read()
      and edit.dirty(shape) == [])

# -- edit for the asset (every shot) --------------------------------------------------
edit.begin(shape, edit.ASSET)
check("begin(asset): edits go to the asset layer", edit.editing(shape) == edit.ASSET)
UsdGeom.XformCommonAPI(stage.GetPrimAtPath(ROOF)).SetTranslate(Gf.Vec3d(0, 5, 0))
check("save: the asset layer saved, edits back on the shot layer",
      edit.save(shape) == [edit.ASSET] and edit.editing(shape) == edit.SHOT)
asset_text = open(layers["asset"].realPath).read()
check("... the roof's move is in the asset layer at the asset's own path, the wall's isn't",
      "shed_roof_GEO" in asset_text and "shed_wall_GEO" not in asset_text)
check("... the asset layer notes the publish it was made over",
      (layers["asset"].customLayerData["pipe"].get("base") or "").endswith(stem + ".usd"))

# -- discard ------------------------------------------------------------------------------
edit.begin(shape, edit.SHOT)
UsdGeom.XformCommonAPI(stage.GetPrimAtPath(WALL)).SetTranslate(Gf.Vec3d(9, 9, 9))
check("discard: unsaved edits thrown away, the saved one kept",
      edit.discard(shape) == [edit.SHOT]
      and UsdGeom.XformCommonAPI(stage.GetPrimAtPath(WALL)).GetXformVectors(
          Usd.TimeCode.Default())[0] == Gf.Vec3d(3, 0, 0))

# -- a stage loaded before edit layers ------------------------------------------------
old_t = build.make_stage("shedOld", build.manifest_key("environment", "shed", "model"),
                         build.stage_of(shed)[2], "shedOld_model_GRP")
old_shape = cmds.listRelatives(old_t, shapes=True, fullPath=True)[0]
check("an old stage (reads the publish directly) needs an update",
      edit.needs_upgrade(old_shape)
      and "Update Stage" in refused(edit.begin, old_shape, edit.SHOT))
edit.upgrade(old_shape)
check("... upgrade gives it the shot and asset layers",
      not edit.needs_upgrade(old_shape) and edit.layers(old_shape)["asset"] is not None)
cmds.delete("shedOld_model_GRP")
cmds.file(save=True, type="mayaAscii")

# -- the asset's edits into the Maya model ---------------------------------------------
cmds.file(model_scene, open=True, force=True)
moves, missing, other = edit.pending()
check("asset scene: one move waiting (the roof), mapped to its Maya node",
      moves == [(ROOF, "|geo_USD|render|shed_roof_GEO")] and not missing)
moved, missing, other = edit.apply_to_model()
check("apply: the roof moves to the asset layer's place, the wall doesn't",
      moved == ["|geo_USD|render|shed_roof_GEO"]
      and [round(v, 3) for v in cmds.xform("|geo_USD|render|shed_roof_GEO", q=True,
                                           objectSpace=True, translation=True)] == [0, 5, 0]
      and [round(v, 3) for v in cmds.xform("|geo_USD|render|shed_wall_GEO", q=True,
                                           objectSpace=True, translation=True)] == [0, 0, 0])
cmds.undo()
check("... undo puts it back in one step",
      [round(v, 3) for v in cmds.xform("|geo_USD|render|shed_roof_GEO", q=True,
                                       objectSpace=True, translation=True)] == [0, 2, 0])
check("clear: the asset layer emptied", edit.clear_asset_edits() == 1 and edit.pending()[0] == [])

# -- Maya's own move command on a picked prim goes to the chosen layer -------------
cmds.file(shot_scene, open=True, force=True)
transform, shape, _ = build.stage_of(shed)
stage = mayaUsd.ufe.getStage(shape)
layers = edit.layers(shape)
edit.begin(shape, edit.ASSET)
ufe.GlobalSelection.get().replaceWith(ufe.Selection())
ufe.GlobalSelection.get().append(ufe.Hierarchy.createItem(ufe.PathString.path(
    "%s,%s" % (shape, ROOF))))
cmds.move(0, 1, 0, relative=True)
check("Maya's move on a picked USD prim writes to the asset layer, not the shot's",
      layers["asset"].dirty and not layers["shot"].dirty
      and layers["asset"].GetPrimAtPath(ROOF) is not None)
edit.discard(shape)

print("\n%d/%d passed" % (sum(ok), len(ok)))
shutil.rmtree(base, ignore_errors=True)
