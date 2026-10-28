# Build into an asset scene (user, 2026-10-28): a published asset pulled
# into asset development is imported, never referenced. It comes in as
# published (stamped pipe group, no namespace); its textures and DNA are
# copied into the asset's own sourceimages and the nodes point there; a
# second import is spotted from the stamps. Never touches the real drives
# or Maya prefs. Run: mayapy test_assetImport_mayapy.py
import sys, os, json, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), "publishDev")]
from PySide6 import QtWidgets
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
import maya.standalone; maya.standalone.initialize()
import maya.cmds as cmds
import buildTool_api as api
pub = api.pub

ok = []
def check(label, cond):
    ok.append(bool(cond)); print("PASS" if cond else "FAIL", label)

base = tempfile.mkdtemp(prefix="assetimport_")
_cfg = os.path.join(base, "pipeline_config.json")
pub._config_path = lambda: _cfg
H, S = os.path.join(base, "H"), os.path.join(base, "scratch")
FILM = "NWF_SHF"
pub.save_config({pub.H_DRIVE: H, "scratch_root": S, "publish_as": "e131988"})

# -- a published backpack model: textured, with a DNA stamp -----------------
stem = "backpack_e131988_model_v001"
h_scenes = os.path.join(H, FILM, "maya", "assets", "prop", "backpack", "scenes", "e131988")
h_tex = os.path.join(H, FILM, "maya", "assets", "prop", "backpack", "sourceimages", "e131988", stem)
os.makedirs(h_scenes); os.makedirs(os.path.join(h_tex, "dna"))
open(os.path.join(h_tex, "skin.png"), "wb").write(b"png")
open(os.path.join(h_tex, "dna", "head.dna"), "wb").write(b"dna")
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
holder = cmds.createNode("transform", name="dnaHolder")
cmds.addAttr(holder, longName="dnaFilePath", dataType="string")
cmds.setAttr(holder + ".dnaFilePath", var_tex + "/dna/head.dna", type="string")
grp = cmds.container(type="dagContainer", name="backpack_model_GRP")
cmds.parent(cube, holder, grp)
for name, value in (("pipe_asset", "backpack"), ("pipe_assetType", "prop"),
                    ("pipe_department", "model"), ("pipe_artistId", "e131988"),
                    ("pipe_dna", json.dumps([{"node": "dnaHolder", "attr": "dnaFilePath",
                                              "published": var_tex + "/dna/head.dna"}]))):
    cmds.addAttr(grp, longName=name, dataType="string")
    cmds.setAttr(grp + "." + name, value, type="string")
    cmds.setAttr(grp + "." + name, lock=True)
cmds.addAttr(grp, longName="pipe_version", attributeType="long")
cmds.setAttr(grp + ".pipe_version", 1, lock=True)
cmds.file(rename=os.path.join(h_scenes, stem + ".ma"))
cmds.file(save=True, type="mayaAscii")

published = [p for p in api.list_published(H, FILM) if p["asset"] == "backpack"][0]
vid = published["latest"]

# -- an asset scene on scratch: Scout's rig work ------------------------------
asset_dir = api.asset_folder(S, FILM, "character", "scout")
scene = os.path.join(asset_dir, "scenes", "rig", "e131988", "scout_rig_001.ma")
os.makedirs(os.path.dirname(scene))
cmds.file(new=True, force=True)
cmds.file(rename=scene)
cmds.file(save=True, type="mayaAscii")
check("asset_of_scene finds the asset", api.asset_of_scene(scene, S) == (FILM, "character", "scout"))
check("... and shot_of_scene doesn't", api.shot_of_scene(scene, S) is None)
check("nothing imported yet", api.imported_versions(published) == [])

done = api.import_into_asset(asset_dir, published, vid)
check("imported, not referenced", not cmds.ls(type="reference") or
      cmds.ls(type="reference") == ["sharedReferenceNode"])
check("as published: the stamped group, no namespace",
      cmds.objExists("|backpack_model_GRP|backpack_geo")
      and cmds.getAttr("backpack_model_GRP.pipe_version") == 1
      and not [n for n in cmds.namespaceInfo(":", listOnlyNamespaces=True) or []
               if n not in ("UI", "shared")])
own = os.path.join(asset_dir, "sourceimages", stem)
check("textures and DNA copied into the asset's sourceimages",
      os.path.isfile(os.path.join(own, "skin.png")) and os.path.isfile(os.path.join(own, "dna", "head.dna")))
check("... and writable (the asset's own)", os.access(os.path.join(own, "skin.png"), os.W_OK))
check("file node points at the asset's copy",
      os.path.normcase(os.path.normpath(cmds.getAttr("skin_file.fileTextureName")))
      == os.path.normcase(os.path.join(own, "skin.png")))
dna = json.loads(cmds.getAttr("backpack_model_GRP.pipe_dna"))[0]["published"]
check("DNA stamp and node point at the asset's copy",
      os.path.normcase(os.path.normpath(dna)) == os.path.normcase(os.path.join(own, "dna", "head.dna"))
      and os.path.normcase(os.path.normpath(cmds.getAttr("dnaHolder.dnaFilePath")))
      == os.path.normcase(os.path.join(own, "dna", "head.dna")))
check("says what it did", done[0].startswith("imported v001 (e131988)") and len(done) == 3)
check("the import is spotted from its stamp", api.imported_versions(published) == [vid])

# Saved and reopened: the textures and DNA still point at the asset's copies.
cmds.file(save=True, type="mayaAscii")
cmds.file(scene, open=True, force=True)
check("after reopening: still the asset's copies",
      os.path.normcase(os.path.normpath(cmds.getAttr("skin_file.fileTextureName")))
      == os.path.normcase(os.path.join(own, "skin.png")))

# Importing again is allowed (the window asks first): a second group.
api.import_into_asset(asset_dir, published, vid)
check("a second import gives a second group, both spotted",
      len(cmds.ls("backpack_model_GRP*", type="dagContainer")) == 2
      and api.imported_versions(published) == [vid, vid])
try:
    api.import_into_asset(asset_dir, {"kind": "camera"}, vid)
    check("a shot's camera can't be imported into an asset", False)
except api.BuildError:
    check("a shot's camera can't be imported into an asset", True)

# -- the Build window in an asset scene -----------------------------------
import buildTool_ui as ui
pub.set_root(pub.SCRATCH, S)
cmds.file(new=True, force=True)
cmds.file(rename=scene)
cmds.file(save=True, type="mayaAscii")
parent = QtWidgets.QWidget()
tab = ui.BuildShotTab(lambda: (H, S), parent)
tab.refresh()
check("window: imports into the asset, says it's not referenced",
      tab._target_asset == (FILM, "character", "scout") and tab._target_shot is None
      and "Importing into asset <b>scout</b>" in tab.target_lbl.text()
      and "not referenced" in tab.target_lbl.text()
      and tab.build_btn.text() == "Import into Asset")
check("window: the list starts empty", tab._rows == [])
tab.picker.set_current(film=FILM, code="model", group="prop", name="backpack")
tab._add_asset()
check("window: + adds the backpack, ticked, ready to import",
      [(r["asset"], r["checked"]) for r in tab._rows] == [("backpack", True)]
      and tab.table.item(0, 6).text() == "Ready to import")
tab._build_shot()
check("window: Import into Asset imports it, no reference",
      cmds.objExists("|backpack_model_GRP") and not api.scene_references()
      and "imported v001 (e131988)" in tab.status._text)
check("window: the row now shows it's in the scene, unticked",
      not tab._rows[0]["checked"] and tab.table.item(0, 5).text() == "v001 (e131988)"
      and tab.table.item(0, 6).text().startswith("Already imported"))
asked = []
QtWidgets.QMessageBox.exec = lambda box: asked.append(box.text())     # answered Skip
tab._rows[0]["checked"] = True
tab._build_shot()
check("window: importing again asks first, and Skip imports nothing",
      len(asked) == 1 and "already in this scene" in asked[0]
      and len(cmds.ls("backpack_model_GRP*", type="dagContainer")) == 1
      and "skipped" in tab.status._text)
tab._repair()
check("window: Repair says it's for shots", "Repair fixes a shot's" in tab.status._text)
print("%d/%d passed" % (sum(ok), len(ok)))
