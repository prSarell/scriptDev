# USD hierarchy and names for a model publish (user, 2026-11-20):
# geo|render|proxy, <asset>_<part>_GEO / <part>_GRP, names that clash fixed,
# and the publish's .usd + .usdz with the default prim, kind, purposes and
# textures beside it.
# Run: mayapy test_modelUsd_mayapy.py
import sys, os, shutil, tempfile, zipfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HERE = os.path.dirname(os.path.abspath(__file__))
for sub in ("", "../publishDev"):
    sys.path.insert(0, os.path.normpath(os.path.join(HERE, sub)))
from PySide6 import QtWidgets, QtGui
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
import maya.standalone; maya.standalone.initialize()
import maya.cmds as cmds
import publishTool_api as api
import publishTool_textures as tex
import publishTool_outputs as out
import modelTool_usd as usd
api.artist_name = lambda login: "Test Person"      # no ShotGrid in the test

ok = []
def check(label, cond):
    ok.append(bool(cond)); print("PASS" if cond else "FAIL", label)

def refuses(call, *args, **kw):
    try:
        call(*args, **kw)
    except api.PublishError as e:
        return str(e) or True
    return False

base = tempfile.mkdtemp(prefix="model_usd_")
FILM = "NWF_SHF"
work = os.path.join(base, "scratch", FILM, "maya", "assets", "prop", "chair")
os.makedirs(os.path.join(work, "scenes")); os.makedirs(os.path.join(work, "sourceimages"))
scene = os.path.join(work, "scenes", "chair_work.ma")


def new_scene():
    cmds.file(new=True, force=True)
    cmds.file(rename=scene); cmds.file(save=True, type="mayaAscii")


def world(node):
    return [round(v, 4) for v in cmds.xform(node, q=True, worldSpace=True, translation=True)]


# --- the asset and the hierarchy ---------------------------------------------
new_scene()
check("the asset's name comes from the scene's folder", usd.asset_name() == "chair")
s = usd.build()
check("build: geo|render|proxy at the world root",
      s == {"geo": "|geo", "render": "|geo|render", "proxy": "|geo|proxy"})
check("build again: nothing new", usd.build() == s and len(cmds.ls("geo")) == 1)

seat = cmds.polyCube(name="seat")[0]; cmds.move(1, 2, 3, seat)
legs = cmds.group(empty=True, name="legs")
leg_a = cmds.parent(cmds.polyCylinder(name="legA")[0], legs)[0]
cmds.move(4, 0, 0, legs)
cam = cmds.camera(name="lookCam")[0]
check("left out: the geometry outside geo (not cameras)",
      sorted(usd.left_out()) == ["|legs", "|seat"])
moved = usd.add([seat, legs, leg_a, cam])
check("add: picked ones go into render, a group with what's in it, a child "
      "picked with its parent only once, cameras stay",
      sorted(moved) == ["|geo|render|legs", "|geo|render|seat"]
      and cmds.objExists("|geo|render|legs|legA") and cmds.objExists("|" + cam))
check("add: nothing moves in the world",
      world("|geo|render|seat") == [1, 2, 3] and world("|geo|render|legs|legA") == [4, 0, 0])
check("add again: already there, nothing moves", usd.add(["|geo|render|seat"]) == [])
box = cmds.polyCube(name="box")[0]
check("add to proxy", usd.add([box], purpose=usd.PROXY) == ["|geo|proxy|box"])
check("nothing left out", usd.left_out() == [])

new_scene()
cmds.group(empty=True, name="render")
check("build: refuses when something else is already called render",
      "render" in str(refuses(usd.build)) and not cmds.objExists("|geo"))

# --- naming --------------------------------------------------------------------
check("part names cleaned: spaces, asset name and suffix typed by the artist",
      usd.clean_part(" Chair seat back_GEO", "chair") == "seat_back"
      and usd.clean_part("chair_seat_GEO", "chair") == "seat"
      and usd.clean_part("3legs!", "chair") == "legs")
new_scene()
usd.build()
one = cmds.polyCube(name="pCube1")[0]
done = usd.name([one], "seat")
check("name one mesh: <asset>_<part>_GEO, its shape after it",
      done == [("pCube1", "chair_seat_GEO")] and cmds.objExists("chair_seat_GEOShape"))
three = [cmds.polyCylinder()[0] for _ in range(3)]
done = usd.name(three, "leg")
check("name several: numbered 01, 02, 03",
      [n for _, n in done] == ["chair_leg01_GEO", "chair_leg02_GEO", "chair_leg03_GEO"])
grp = cmds.group(["chair_leg01_GEO", "chair_leg02_GEO"], name="group1")
check("name a group: <part>_GRP", usd.name([grp], "legs") == [("group1", "legs_GRP")])
other = cmds.polyCube()[0]
check("a name already taken gets the next number",
      usd.name([other], "seat") == [(other, "chair_seat01_GEO")])
check("name: refuses with no part name or nothing picked",
      refuses(usd.name, [other], " ") and refuses(usd.name, [], "seat"))

# --- clean-up: the names that would clash or break the convention ------------
new_scene()
usd.build()
a = cmds.group(empty=True, name="frontLegs", parent="|geo|render")
b = cmds.group(empty=True, name="backLegs_GRP", parent="|geo|render")
cmds.parent(cmds.polyCube(name="leg")[0], a)
cmds.parent(cmds.polyCube(name="leg")[0], b)
cmds.parent(cmds.polySphere()[0], "|geo|render")                # pSphere1
cmds.namespace(add="old")
ns = cmds.polyCube(name="old:cushion")[0]
cmds.parent(ns, "|geo|render")
good = cmds.parent(cmds.polyCube(name="chair_back_GEO")[0], "|geo|render")[0]
cmds.rename(cmds.listRelatives(good, shapes=True)[0], "wrongShape")
found = dict((f["name"], f) for f in usd.problems())
check("problems: two meshes called leg (and no prefix or suffix)",
      "2 nodes are called leg" in found["leg"]["why"] and "chair_" in found["leg"]["why"])
check("problems: a group without _GRP", found["frontLegs"]["fix"] == "frontLegs_GRP")
check("problems: Maya's default name is listed, for the artist to name",
      found["pSphere1"]["fix"] is None)
check("problems: a namespace", "namespace" in found["old:cushion"]["why"]
      and found["old:cushion"]["fix"] == "chair_cushion_GEO")
check("problems: a shape not named after its transform",
      "wrongShape" in found["chair_back_GEO"]["why"])
check("problems: a good name isn't listed",
      "backLegs_GRP" not in found and "geo" not in found)
done = dict(usd.fix())
names = set(n.split("|")[-1] for n in cmds.ls(dag=True))
check("fix: the two legs get unique names", {"chair_leg_GEO", "chair_leg01_GEO"} <= names
      and "leg" not in names)
check("fix: suffix added, namespace off, shape renamed",
      "frontLegs_GRP" in names and "chair_cushion_GEO" in names
      and not cmds.ls("old:*") and "chair_back_GEOShape" in names)
left = usd.problems()
check("after fix only the default name is left",
      [f["name"] for f in left] == ["pSphere1"] and "pSphere1" not in done)

# --- imported models: unwanted text (user 2026-11-23) ------------------------
check("remove_from: the gap left as one _",
      usd.remove_from("grassB_TypeGrassColor03_0610_GEO", "_TypeGrassColor03_")
      == "grassB_0610_GEO"
      and usd.remove_from("grassB_TypeGrassColor03TypeGrassColor03_0610_GEO",
                          "TypeGrassColor03") == "grassB_0610_GEO")
new_scene()
JUNK = "_TypeGrassColor03_"
grass = cmds.group(empty=True, name="grass_TypeGrassColor03_GRP")
blades = [cmds.parent(cmds.polyPlane(name="grassB%s%04d_GEO" % (JUNK, 610 + i))[0], grass)[0]
          for i in range(3)]
cmds.polyCube(name="grassB_0611_GEO")                        # already has one of the names
digit = cmds.parent(cmds.polyPlane(name="TypeGrassColor03_9_GEO")[0], grass)[0]
plain = cmds.polyCube(name="rock%s01_GEO" % JUNK)[0]          # not picked
before = sorted(cmds.ls(dag=True))
done, skipped = usd.remove_text([grass], JUNK, dry_run=True)
check("remove text, dry run: says what would happen, renames nothing",
      len(done) == 4 and sorted(cmds.ls(dag=True)) == before)
done, skipped = usd.remove_text([grass], "TypeGrassColor03")
names = set(n.split("|")[-1] for n in cmds.ls(dag=True))
check("remove text: the group and everything under it",
      {"grass_GRP", "grassB_0610_GEO", "grassB_0612_GEO"} <= names
      and not any("TypeGrass" in n for n in names if n.startswith("grass")))
check("remove text: a name someone else has gets the next number",
      "grassB_0611_GEO" in names and "grassB_061101_GEO" in names)
check("remove text: shapes follow their transform",
      cmds.listRelatives("grassB_0610_GEO", shapes=True) == ["grassB_0610_GEOShape"])
check("remove text: a name left starting with a digit is skipped",
      [s[0] for s in skipped] == ["TypeGrassColor03_9_GEO"])
check("remove text: what isn't picked is left", cmds.objExists(plain))
g2 = cmds.group(empty=True, name="clump_TypeX_GRP")
cmds.parent(cmds.polyCube(name="blade_TypeX_GEO")[0], g2)
usd.remove_text([g2], "_TypeX", below=False)
check("remove text: only the picked one, not what's under it",
      cmds.objExists("clump_GRP") and cmds.objExists("blade_TypeX_GEO"))
check("remove text: refuses no text, or no picked name with it",
      refuses(usd.remove_text, [g2], " ") and refuses(usd.remove_text, [g2], "nothere"))
check("remove_from: * for any number or letters, up to the next _",
      usd.remove_from("grassB_TypeGrassColor003_0610_GEO", "_TypeGrassColor*_")
      == "grassB_0610_GEO"
      and usd.remove_from("grassB_TypeGrassColor03TypeGrassColor03_0610_GEO",
                          "TypeGrassColor*") == "grassB_0610_GEO"
      and usd.remove_from("grassB_0610_GEO", "_TypeGrassColor*_") == "grassB_0610_GEO")
new_scene()
mix = cmds.group(empty=True, name="field_GRP")
for n, code in enumerate(("03", "003", "12b")):
    cmds.parent(cmds.polyPlane(name="grass%d_TypeGrassColor%s_GEO" % (n, code))[0], mix)
done, skipped = usd.remove_text([mix], "_TypeGrassColor*_")
check("remove text with *: every number taken out, the group left",
      sorted(n for _, n in done) == ["grass0_GEO", "grass1_GEO", "grass2_GEO"]
      and cmds.objExists("field_GRP"))
check("remove text: refuses * on its own", refuses(usd.remove_text, [mix], "**"))

# --- renumber, top to bottom in the Outliner (user 2026-11-23) ---------------
new_scene()
field = cmds.group(empty=True, name="field_GRP")
for name in ("grassB_017102_GEO", "grassB_0251_GEO", "grassB_03_GEO", "rock_0610_GEO",
             "grassB_051402_GEO"):
    cmds.parent(cmds.polyPlane(name=name)[0], field)
cmds.reorder("|field_GRP|grassB_03_GEO", front=True)        # the Outliner's order, not names
cmds.polyCube(name="grassB_001_GEO")                         # not picked: its number is skipped
done = usd.renumber([field])
kids = cmds.listRelatives(field, children=True)
check("renumber: from 000, top to bottom in the Outliner, a taken number skipped",
      kids == ["grassB_000_GEO", "grassB_002_GEO", "grassB_003_GEO", "rock_000_GEO",
               "grassB_004_GEO"])
check("renumber: the group keeps its name, shapes follow, the other mesh untouched",
      cmds.objExists("|field_GRP") and cmds.objExists("|grassB_001_GEO")
      and cmds.listRelatives("|field_GRP|grassB_004_GEO", shapes=True) == ["grassB_004_GEOShape"])
cmds.reorder("|field_GRP|grassB_004_GEO", front=True)
done = usd.renumber(["|field_GRP|grassB_004_GEO", "|field_GRP|grassB_000_GEO"], below=False)
check("renumber two picked: they swap 000 and 004 by Outliner order, no clash",
      cmds.listRelatives(field, children=True)[:2] == ["grassB_000_GEO", "grassB_004_GEO"]
      and len(done) == 2)
check("renumber: refuses with nothing to number", refuses(usd.renumber, []))

# --- imported models: namespaces (user 2026-11-23) ---------------------------
new_scene()
cmds.namespace(add="imp"); cmds.namespace(add="imp:deep")
top = cmds.group(empty=True, name="imp:tree_GRP")
trunk = cmds.parent(cmds.polyCylinder(name="imp:deep:trunk_GEO")[0], top)[0]
cmds.polyCube(name="trunk_GEO")                               # already has the name
mat = cmds.shadingNode("lambert", asShader=True, name="imp:barkMat")
other = cmds.polyCube(name="imp:rock_GEO")[0]                 # not picked
done, removed = usd.strip_namespaces(["|imp:tree_GRP"])
names = set(n.split("|")[-1] for n in cmds.ls(dag=True))
check("strip picked: the group and everything under it, nested ones too",
      "tree_GRP" in names and "trunk_GEO01" not in names and "trunk_GEO" in names
      and any(n == "trunk01_GEO" for n in names))
check("strip picked: shape renamed with it, the rest left",
      cmds.listRelatives("|tree_GRP|trunk01_GEO", shapes=True) == ["trunk01_GEOShape"]
      and cmds.objExists("imp:rock_GEO") and cmds.objExists("imp:barkMat"))
check("strip picked: the emptied namespace is removed, a used one stays",
      removed == ["imp:deep"] and cmds.namespace(exists=":imp"))
done, removed = usd.strip_namespaces()
check("strip with nothing picked: every own namespace, materials too",
      cmds.objExists("|rock_GEO") and cmds.objExists("barkMat")
      and not cmds.namespace(exists=":imp") and "imp" in removed)
check("strip: nothing left to do", usd.strip_namespaces() == ([], []))
# A referenced model's namespace is left alone.
ref_file = os.path.join(work, "scenes", "ref_src.ma")
new_scene(); cmds.polyCube(name="refBox_GEO")
cmds.file(rename=ref_file); cmds.file(save=True, type="mayaAscii")
new_scene()
cmds.file(ref_file, reference=True, namespace="refd")
cmds.namespace(add="mine"); cmds.polyCube(name="mine:own_GEO")
done, removed = usd.strip_namespaces()
check("strip: a reference's namespace is left alone",
      cmds.objExists("refd:refBox_GEO") and cmds.objExists("|own_GEO") and removed == ["mine"])

# --- the publish: .usd + textures\ + .usdz -----------------------------------
new_scene()
png = os.path.join(work, "sourceimages", "wood.png")
img = QtGui.QImage(16, 16, QtGui.QImage.Format_RGB32); img.fill(0x996633); img.save(png)
usd.build()
seat = cmds.polyCube(name="chair_seat_GEO")[0]
proxy = cmds.polyCube(name="chair_proxy_GEO")[0]
usd.add([seat]); usd.add([proxy], purpose=usd.PROXY)
mat = cmds.shadingNode("lambert", asShader=True, name="woodMat")
sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name="woodMatSG")
cmds.connectAttr(mat + ".outColor", sg + ".surfaceShader")
cmds.sets("|geo|render|chair_seat_GEO", edit=True, forceElement=sg)
f = cmds.shadingNode("file", asTexture=True, name="wood_file")
cmds.setAttr(f + ".fileTextureName", png.replace("\\", "/"), type="string")
cmds.connectAttr(f + ".outColor", mat + ".color")
cmds.file(save=True, type="mayaAscii")
H = os.path.join(base, "H")
h_folder = os.path.join(H, FILM, "maya", "assets", "prop", "chair", "scenes", "scout")
os.makedirs(h_folder)
plan = {"dest": os.path.join(h_folder, "chair_scout_model_v001.ma"), "h_folder": h_folder,
        "ext": ".ma", "asset": "chair", "asset_type": "prop", "code": "model", "version": 1,
        "login": "scout", "film": FILM, "sg_asset": {"id": 1}, "outputs": ["usd"],
        "root": os.path.join(base, "scratch")}
api.export_model_to_h_drive(["geo"], plan, scene, tex.collect(["geo"]))
folder = out.folder_of(plan["dest"])
usd_path = os.path.join(folder, "chair_scout_model_v001.usd")
usdz_path = os.path.join(folder, "chair_scout_model_v001.usdz")
check("publish: a .usd and a .usdz, both recorded",
      os.path.isfile(usd_path) and os.path.isfile(usdz_path)
      and plan["outputs_written"] == [usd_path, usdz_path])
from pxr import Usd, UsdGeom, Sdf
stage = Usd.Stage.Open(usd_path)
top = stage.GetDefaultPrim()
check("USD: the pipe group is the default prim, kind component",
      top and top.GetName() == "chair_model_GRP" and Usd.ModelAPI(top).GetKind() == "component")
check("USD: geo|render and geo|proxy have their purposes",
      UsdGeom.Imageable(stage.GetPrimAtPath("/chair_model_GRP/geo/render")).GetPurposeAttr().Get()
      == "render"
      and UsdGeom.Imageable(stage.GetPrimAtPath("/chair_model_GRP/geo/proxy")).GetPurposeAttr().Get()
      == "proxy"
      and stage.GetPrimAtPath("/chair_model_GRP/geo/render/chair_seat_GEO").IsValid())
assets = [a.Get().path for p in stage.Traverse() for a in p.GetAttributes()
          if a.GetTypeName() == Sdf.ValueTypeNames.Asset and a.Get() and a.Get().path]
check("USD: the texture is beside it, by a relative path",
      "./textures/wood.png" in assets and os.path.isfile(os.path.join(folder, "textures", "wood.png")))
check("USDZ: the texture packed inside",
      any(n.endswith("wood.png") for n in zipfile.ZipFile(usdz_path).namelist()))
print("materials at:", [str(p.GetPath()) for p in stage.Traverse() if p.GetTypeName() == "Material"])

out.remove(folder)
cmds.file(new=True, force=True)
shutil.rmtree(base, ignore_errors=True)
print("%d/%d passed" % (sum(ok), len(ok)))
