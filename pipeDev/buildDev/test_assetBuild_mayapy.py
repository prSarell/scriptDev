# Build into an asset (user, 2026-10-30): the same as building into a shot.
# One Build button, no context: a published asset is referenced into the
# asset scene, the asset keeps a list per department on H
# (<asset>\data\build\<dept>.json), and Keys stay shot-only. Making a
# referenced model editable is Convert to Model's job (mpModel shelf): it
# imports it and copies its textures into the asset's own sourceimages.
# Replaces the Import into Asset test (2026-10-28). Never touches the real
# drives or Maya prefs. Run: mayapy test_assetBuild_mayapy.py
import sys, os, json, shutil, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HERE = os.path.dirname(os.path.abspath(__file__))
PIPE = os.path.dirname(HERE)
sys.path[:0] = [HERE, os.path.join(PIPE, "publishDev"), os.path.join(PIPE, "modelDev")]
from PySide6 import QtWidgets
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
import maya.standalone; maya.standalone.initialize()
import maya.cmds as cmds
import buildTool_api as api
import buildTool_ui as ui
import modelTool_convert as convert
pub = api.pub

ok = []
def check(label, cond):
    ok.append(bool(cond)); print("PASS" if cond else "FAIL", label)

base = tempfile.mkdtemp(prefix="assetbuild_")
_cfg = os.path.join(base, "pipeline_config.json")
pub._config_path = lambda: _cfg
H, S = os.path.join(base, "H"), os.path.join(base, "scratch")
FILM = "NWF_SHF"
pub.save_config({pub.H_DRIVE: H, "scratch_root": S, "publish_as": "e131988"})
pub.set_root(pub.SCRATCH, S)

# -- a published backpack model with a texture, as Publish makes it -----------
stem = "backpack_e131988_model_v001"
h_scenes = os.path.join(H, FILM, "maya", "assets", "prop", "backpack", "scenes", "e131988")
h_tex = os.path.join(H, FILM, "maya", "assets", "prop", "backpack", "sourceimages", "e131988", stem)
os.makedirs(h_scenes); os.makedirs(h_tex)
open(os.path.join(h_tex, "skin.png"), "wb").write(b"png")
var_tex = "$PIPE_SCRATCH/%s/maya/publish/assets/prop/backpack/sourceimages/e131988/%s" % (FILM, stem)
cmds.file(new=True, force=True)
cube = cmds.polyCube(name="backpack_geo")[0]
shader = cmds.shadingNode("lambert", asShader=True, name="backpack_mtl")
sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name="backpack_mtlSG")
cmds.connectAttr(shader + ".outColor", sg + ".surfaceShader")
cmds.sets(cube, edit=True, forceElement=sg)
f = cmds.shadingNode("file", asTexture=True, name="skin_file")
cmds.setAttr(f + ".fileTextureName", var_tex + "/skin.png", type="string")
cmds.connectAttr(f + ".outColor", shader + ".color")
grp = pub.make_pipe_group("backpack_model_GRP")
cmds.parent(cube, grp)
pub._stamp(grp, [("sgAssetId", 1577), ("asset", "backpack"), ("assetType", "prop"),
                 ("department", "model"), ("version", 1), ("artistId", "e131988")])
pub.finish_pipe_group(grp)
cmds.file(rename=os.path.join(h_scenes, stem + ".ma"))
cmds.file(save=True, type="mayaAscii")

# -- an asset scene on scratch: the shed, Modeling, its project set -----------
asset_dir = api.asset_folder(S, FILM, "environment", "shed")
scene = os.path.join(asset_dir, "scenes", "model", "e131988", "shed_001.ma")
os.makedirs(os.path.dirname(scene))
open(os.path.join(asset_dir, "workspace.mel"), "w").write("")
os.makedirs(api.asset_folder(H, FILM, "environment", "shed"))
cmds.workspace(asset_dir, openWorkspace=True)
cmds.file(new=True, force=True)
cmds.file(rename=scene)
cmds.file(save=True, type="mayaAscii")

parent = QtWidgets.QWidget()
tab = ui.BuildShotTab(lambda: (H, S), parent)
tab.refresh()
check("Build into the asset, Modeling",
      tab._target_asset == (FILM, "environment", "shed") and tab._target_shot is None
      and tab.department() == "model" and "Building into asset <b>shed</b>" in tab.target_lbl.text())
check("one Build button, the same as for a shot", tab.build_btn.text() == "Build")
check("no Keys from (keys come from shots)", tab.keys_combo.isHidden())
check("the list starts empty (no saved list yet)", tab._rows == [])
tab.picker.set_current(film=FILM, code="model", group="prop", name="backpack")
tab._add_asset()
check("+ adds the backpack, ticked, ready to build, no keys",
      [(r["asset"], r["checked"], r["keys_chosen"]) for r in tab._rows]
      == [("backpack", True, None)] and tab.table.item(0, 6).text() == "Ready to build")
tab._build_shot()
cmds.file(save=True, type="mayaAscii")
check("Build references it (namespace backpack), not an import",
      cmds.referenceQuery("backpack:backpack_model_GRP", isNodeReferenced=True))
check("recorded in the asset's manifest on scratch",
      api.manifest_key("prop", "backpack", "model") in api.read_manifest(asset_dir))
check("the row now shows it's in the scene, up to date, unticked",
      not tab._rows[0]["checked"] and tab.table.item(0, 6).text().startswith("Up to date"))
h_list = api.build_list_path(api.asset_folder(H, FILM, "environment", "shed"), "model")
check("Modeling's list for the asset saved on H (data\\build\\model.json)",
      json.load(open(h_list))["assets"] == [api.manifest_key("prop", "backpack", "model")])

# Another scratch drive: the list comes back from H.
S2 = os.path.join(base, "scratch2")
asset2 = api.asset_folder(S2, FILM, "environment", "shed")
scene2 = os.path.join(asset2, "scenes", "model", "e131988", "shed_002.ma")
os.makedirs(os.path.dirname(scene2))
open(os.path.join(asset2, "workspace.mel"), "w").write("")
cmds.workspace(asset2, openWorkspace=True)
cmds.file(new=True, force=True)
cmds.file(rename=scene2)
cmds.file(save=True, type="mayaAscii")
tab2 = ui.BuildShotTab(lambda: (H, S2), parent)
tab2.refresh()
check("another drive: the asset's list comes back from H, ticked",
      [(r["asset"], r["checked"]) for r in tab2._rows] == [("backpack", True)])
tab2._repair()
check("Repair works in an asset scene too", "Repair fixes a shot's" not in tab2.status._text)

# -- Convert to Model makes the referenced backpack the shed's own -----------
cmds.workspace(asset_dir, openWorkspace=True)
cmds.file(scene, open=True, force=True)
convert.convert_selected(["backpack:backpack_model_GRP"])
own = os.path.join(asset_dir, "sourceimages", stem, "skin.png")
check("Convert: imported, no group, no namespace",
      not api.scene_references() and cmds.ls("|backpack_geo") and not cmds.ls("*backpack_model_GRP*"))
check("Convert: texture copied into the asset's sourceimages, writable",
      os.path.isfile(own) and os.access(own, os.W_OK))
check("Convert: the file node points at the asset's copy",
      os.path.normcase(os.path.normpath(cmds.getAttr("skin_file.fileTextureName")))
      == os.path.normcase(own))

print("\n%d/%d passed" % (sum(ok), len(ok)))
shutil.rmtree(base, ignore_errors=True)
