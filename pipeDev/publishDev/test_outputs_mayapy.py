# Output files for other software (user, 2026-10-30): a Modeling publish can
# also write ABC, USD, FBX and OBJ, ticked per row. They're made from the
# published copy and go in <published name>_exports\ beside the .ma,
# carrying their textures (FBX embedded, USDZ packed, OBJ + textures\). Each
# asset remembers its ticks on H. A failed export fails the publish.
# Run: mayapy test_outputs_mayapy.py
import sys, os, json, zipfile, shutil, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from PySide6 import QtWidgets, QtGui, QtCore
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
import maya.standalone; maya.standalone.initialize()
import maya.cmds as cmds
import publishTool_api as api
import publishTool_textures as tex
import publishTool_outputs as out
api.artist_name = lambda login: "Test Person"      # no ShotGrid in the test

ok = []
def check(label, cond):
    ok.append(bool(cond)); print("PASS" if cond else "FAIL", label)

base = tempfile.mkdtemp(prefix="outputs_")
FILM = "NWF_SHF"
H = os.path.join(base, "H")
asset_h = os.path.join(H, FILM, "maya", "assets", "prop", "rock")
work = os.path.join(base, "scratch", FILM, "maya", "assets", "prop", "rock")
os.makedirs(os.path.join(work, "sourceimages")); os.makedirs(os.path.join(work, "scenes"))
png = os.path.join(work, "sourceimages", "moss.png")
img = QtGui.QImage(16, 16, QtGui.QImage.Format_RGB32); img.fill(0x55aa33); img.save(png)


def rock_scene():
    cmds.file(new=True, force=True)
    grp = cmds.group(empty=True, name="rock_grp")
    geo = cmds.parent(cmds.polyCube(name="rock_geo")[0], grp)[0]
    mat = cmds.shadingNode("lambert", asShader=True, name="rockMat")
    sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name="rockMatSG")
    cmds.connectAttr(mat + ".outColor", sg + ".surfaceShader")
    cmds.sets(geo, edit=True, forceElement=sg)
    f = cmds.shadingNode("file", asTexture=True, name="moss_file")
    cmds.setAttr(f + ".fileTextureName", png.replace("\\", "/"), type="string")
    cmds.connectAttr(f + ".outColor", mat + ".color")
    scene = os.path.join(work, "scenes", "rock_work.ma")
    cmds.file(rename=scene); cmds.file(save=True, type="mayaAscii")
    return scene


def plan_for(version, formats):
    h_folder = os.path.join(asset_h, "scenes", "scout")
    os.makedirs(h_folder, exist_ok=True)
    return {"dest": os.path.join(h_folder, "rock_scout_model_v%03d.ma" % version),
            "h_folder": h_folder, "ext": ".ma", "asset": "rock", "asset_type": "prop",
            "code": "model", "version": version, "login": "scout", "film": FILM,
            "sg_asset": {"id": 1}, "outputs": formats, "root": os.path.join(base, "scratch")}


# --- all four, from a textured model ----------------------------------------
scene = rock_scene()
plan = plan_for(1, out.FORMAT_KEYS)
api.export_model_to_h_drive(["rock_grp"], plan, scene, tex.collect(["rock_grp"]))
folder = out.folder_of(plan["dest"])
stem = "rock_scout_model_v001"
check("exports folder beside the .ma: rock_scout_model_v001_exports",
      os.path.isdir(folder) and os.path.basename(folder) == stem + "_exports")
check("ABC, USDZ, FBX, OBJ written", all(os.path.isfile(os.path.join(folder, stem + e))
                                       for e in (".abc", ".usdz", ".fbx", ".obj", ".mtl")))
check("recorded for the ShotGrid note", len(plan["outputs_written"]) == 4)
check("USDZ carries the texture", any(n.endswith("moss.png") for n in
                                      zipfile.ZipFile(os.path.join(folder, stem + ".usdz")).namelist()))
check("FBX embeds the texture", b"moss.png" in open(os.path.join(folder, stem + ".fbx"), "rb").read()
      and os.path.getsize(os.path.join(folder, stem + ".fbx")) > os.path.getsize(png))
mtl = open(os.path.join(folder, stem + ".mtl")).read()
check("OBJ: texture copied to textures\\ and the .mtl points there",
      os.path.isfile(os.path.join(folder, "textures", "moss.png")) and "textures/moss.png" in mtl)
check("all read-only, like the publish",
      not any(os.access(os.path.join(d, n), os.W_OK) for d, _, ns in os.walk(folder) for n in ns))
check("working scene's texture path put back",
      cmds.getAttr("moss_file.fileTextureName") == png.replace("\\", "/"))

cmds.file(new=True, force=True)
cmds.loadPlugin("AbcImport", quiet=True)
cmds.AbcImport(os.path.join(folder, stem + ".abc").replace("\\", "/"), mode="import")
check("ABC holds the model", cmds.objExists("rock_geo"))

# --- none ticked: no folder ---------------------------------------------------
scene = rock_scene()
plan = plan_for(2, [])
api.export_model_to_h_drive(["rock_grp"], plan, scene, tex.collect(["rock_grp"]))
check("nothing ticked: no exports folder", not os.path.exists(out.folder_of(plan["dest"])))

# --- a failed export fails the publish, nothing left on H ---------------------
scene = rock_scene()
plan = plan_for(3, ["abc", "fbx"])
real_fbx = out.WRITERS["fbx"]
out.WRITERS["fbx"] = lambda roots, path, textures: (_ for _ in ()).throw(RuntimeError("disk full"))
try:
    api.export_model_to_h_drive(["rock_grp"], plan, scene, tex.collect(["rock_grp"]))
    check("FBX failure -> publish refused", False)
except api.PublishError as e:
    check("FBX failure -> publish refused, says which", "FBX export failed" in str(e))
out.WRITERS["fbx"] = real_fbx
check("... no .ma, no exports folder, no textures left on H",
      not os.path.exists(plan["dest"]) and not os.path.exists(out.folder_of(plan["dest"]))
      and not os.path.exists(tex.texture_folder(plan)))

# --- an exporter that won't load stops it before anything ---------------------
real = out.PLUGINS["usd"]
out.PLUGINS["usd"] = "noSuchPlugin_pipeTest"
try:
    out.check(["usd"])
    check("exporter that won't load -> refused", False)
except api.PublishError as e:
    check("exporter that won't load -> refused, names it", "USD" in str(e))
out.PLUGINS["usd"] = real

# --- each asset remembers ------------------------------------------------------
check("nothing remembered yet", out.remembered(H, FILM, "prop", "rock") == [])
out.remember(H, FILM, "prop", "rock", ["fbx", "abc"])
check("remembered on H, in format order",
      out.remembered(H, FILM, "prop", "rock") == ["abc", "fbx"]
      and os.path.isfile(os.path.join(asset_h, "data", "publish", "outputs.json")))

# --- the publish list: a tick per format, Modeling rows only -------------------
import publishTool_ui as ui
api.save_config = lambda *a, **k: None
PARENT = QtWidgets.QWidget()
w = ui.PublishToolUI(PARENT)
w._roots = lambda: (H, os.path.join(base, "scratch"))
w.picker.set_films([FILM], FILM)
headers = [w.table.horizontalHeaderItem(i).text() for i in range(w.table.columnCount())]
check("columns: ... Publishes as, ABC, USD, FBX, OBJ",
      headers[4:] == ["Publishes as", "ABC", "USD", "FBX", "OBJ"])
w._rows = [{"asset_type": "prop", "asset": "rock", "code": "model", "objects": [], "uuids": [],
            "checked": True, "outputs": w._remembered_outputs("prop", "rock")},
           {"asset_type": "character", "asset": "scout", "code": "rig", "objects": [],
            "uuids": [], "checked": True, "outputs": []}]
w._render_table()
ticks = lambda r: [w.table.item(r, ui.OUTPUT_COLUMN + i).checkState() == QtCore.Qt.Checked
                   for i in range(4)]
check("a Modeling row starts with what the asset remembers (ABC, FBX)",
      ticks(0) == [True, False, True, False])
check("a Rigging row has no ticks", w.table.item(1, ui.OUTPUT_COLUMN).text() == "-"
      and not (w.table.item(1, ui.OUTPUT_COLUMN).flags() & QtCore.Qt.ItemIsUserCheckable))
w.table.item(0, ui.OUTPUT_COLUMN + 1).setCheckState(QtCore.Qt.Checked)
check("ticking USD adds it to the row", w._rows[0]["outputs"] == ["abc", "usd", "fbx"])

print("\n%d/%d passed" % (sum(ok), len(ok)))
shutil.rmtree(base, ignore_errors=True)
