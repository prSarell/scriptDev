# Model publish: clean copy (frozen, no history) in <asset>_model_GRP with
# the pipe stamp; working scene untouched; republish replaces the group.
# Spec §4 item 6a. Run: mayapy test_modelGroup_mayapy.py
import sys, os, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import maya.standalone; maya.standalone.initialize()
import maya.cmds as cmds
import publishTool_api as api
api.artist_name = lambda login: "Test Person"      # no ShotGrid in the test
d = tempfile.mkdtemp(prefix="modelgrp_")
ok = []
def check(label, cond): ok.append(bool(cond)); print("PASS" if cond else "FAIL", label)
def plan(v): return {"dest": os.path.join(d, "backpack_scout_model_v%03d.ma" % v), "h_folder": d, "ext": ".ma",
                     "asset": "backpack", "asset_type": "prop", "code": "model", "version": v, "login": "scout",
                     "sg_asset": {"id": 1577}}
cmds.namespace(add="backpack")
grp = cmds.group(empty=True, name="backpack:props_grp"); cmds.setAttr(grp + ".tx", 10)
geo = cmds.polyCube(name="backpack:backPack_geo")[0]
cmds.polyBevel(geo + ".e[0]")
cmds.parent(geo, grp)
geo = "backpack:props_grp|backpack:backPack_geo"
cmds.setAttr(geo + ".ty", 3); cmds.setAttr(geo + ".rz", 30)
sh = cmds.shadingNode("lambert", asShader=True, name="backpack:bagMat"); sg = cmds.sets(renderable=True, empty=True, name="backpack:bagMatSG")
cmds.connectAttr(sh + ".outColor", sg + ".surfaceShader", force=True); cmds.sets(geo, edit=True, forceElement=sg)
cmds.select("backpack:props_grp")
bb0 = cmds.exactWorldBoundingBox(geo)
before = (cmds.ls(long=True, type="transform"), cmds.getAttr(geo + ".ty"), len(cmds.listHistory(geo)), cmds.ls(selection=True))
p = plan(4)
api.export_model_to_h_drive(["backpack:props_grp|backpack:backPack_geo"], p, r"D:\x\scenes\scout\backpack_work.ma")
after = (cmds.ls(long=True, type="transform"), cmds.getAttr(geo + ".ty"), len(cmds.listHistory(geo)), cmds.ls(selection=True))
check("working scene unchanged (names, transform, history, selection)", before == after)
check("namespaces reported", p["namespaces_removed"] == ["backpack"])
cmds.file(new=True, force=True); cmds.file(p["dest"], open=True, force=True)
check("top node is backpack_model_GRP", "backpack_model_GRP" in cmds.ls(assemblies=True) and len(cmds.ls(assemblies=True)) == 5)
check("model inside, original name, no namespace", cmds.ls("backpack_model_GRP|backPack_geo") != [])
g = "backpack_model_GRP|backPack_geo"
check("transforms frozen", cmds.getAttr(g + ".translate")[0] == (0, 0, 0) and cmds.getAttr(g + ".rotate")[0] == (0, 0, 0))
bb = cmds.exactWorldBoundingBox(g); check("model still exactly where it was", all(abs(a - b) < 0.001 for a, b in zip(bb, bb0)))
check("no history (no polyBevel)", not cmds.ls(type="polyBevel") and not cmds.ls(type="polyCube"))
check("shader kept", "bagMatSG" in (cmds.listConnections(cmds.listRelatives(g, shapes=True)[0], type="shadingEngine") or []))
check("stamp: id/version/artist/date", (cmds.getAttr("backpack_model_GRP.pipe_sgAssetId"), cmds.getAttr("backpack_model_GRP.pipe_version"),
       cmds.getAttr("backpack_model_GRP.pipe_artistName")) == (1577, 4, "Test Person") and cmds.getAttr("backpack_model_GRP.pipe_published")[:4] == "2026")
print("   attrs:", [(a, cmds.getAttr("backpack_model_GRP." + a)) for a in cmds.listAttr("backpack_model_GRP", userDefined=True)])
check("stamp locked", cmds.getAttr("backpack_model_GRP.pipe_sgAssetId", lock=True))
# Pipe group look and lock (user, 2026-10-20): RMIT icon, locked at the origin,
# channels hidden; only the group, the model inside stays free.
G = "backpack_model_GRP"
chans = [G + "." + a for a in api.GROUP_CHANNELS]
check("group shows the pipe icon in the Outliner", cmds.getAttr(G + ".iconName") == "iconPipeOutliner.png")
check("group is a dagContainer (the Outliner only shows iconName on one)", cmds.nodeType(G) == "dagContainer")
check("group locked at the origin, channels hidden",
      all(cmds.getAttr(c, lock=True) and not cmds.getAttr(c, keyable=True)
          and not cmds.getAttr(c, channelBox=True) for c in chans)
      and cmds.getAttr(G + ".translate")[0] == (0, 0, 0) and cmds.getAttr(G + ".scale")[0] == (1, 1, 1))
check("model inside not locked", not cmds.getAttr(g + ".tx", lock=True) and cmds.getAttr(g + ".tx", keyable=True))
# Referenced into a shot: the model moves by its own transforms or a constraint;
# report whether a student could unlock the group.
cmds.file(new=True, force=True)
cmds.file(p["dest"], reference=True, namespace="backpack")
RG, RM = "backpack:backpack_model_GRP", "backpack:backpack_model_GRP|backpack:backPack_geo"
check("referenced: icon and locks come through", cmds.getAttr(RG + ".iconName") == "iconPipeOutliner.png"
      and cmds.getAttr(RG + ".tx", lock=True))
cmds.setAttr(RM + ".tx", 5)
moved = abs(cmds.getAttr(RM + ".tx") - 5) < 1e-3
loc = cmds.spaceLocator(name="carry_LOC")[0]
cmds.parentConstraint(loc, RM, maintainOffset=True)
cmds.setAttr(loc + ".tz", 4)
check("referenced: model moves by its own transform and by a constraint to a locator",
      moved and abs(cmds.getAttr(RM + ".tz") - 4) < 1e-3 and abs(cmds.getAttr(RM + ".tx") - 5) < 1e-3)
try:
    cmds.setAttr(RG + ".tx", lock=False)
    unlockable = not cmds.getAttr(RG + ".tx", lock=True)
except RuntimeError:
    unlockable = False
print("   referenced group can be unlocked by a student:", unlockable)
cmds.file(new=True, force=True); cmds.file(p["dest"], open=True, force=True)
# Republish from that file (whole scene): the old group is replaced, not nested.
cmds.file(rename=os.path.join(d, "work2.ma"))
p5 = plan(5); api.export_model_to_h_drive([], p5, "work2.ma")
check("republish leaves working scene's group alone", cmds.getAttr("backpack_model_GRP.pipe_version") == 4)
cmds.file(new=True, force=True); cmds.file(p5["dest"], open=True, force=True)
check("republish: one group, not nested", cmds.ls("backpack_model_GRP", long=True) == ["|backpack_model_GRP"]
      and cmds.listRelatives("backpack_model_GRP", children=True, type="transform") == ["backPack_geo"]
      and cmds.getAttr("backpack_model_GRP.pipe_version") == 5)
check("file is read-only", not os.access(p5["dest"], os.W_OK))

# -- A group of many models (the scout's house case, 2026-10-19): hidden geo,
#    hidden layer, empty group and unknown plug-in data left out; every mesh
#    stays exactly where it was in world space; .ma still writes. -----------
odd = os.path.join(d, "odd_plugin.ma")
with open(odd, "w") as f:      # a node from a plug-in that isn't loaded
    f.write('//Maya ASCII 2025 scene\nrequires "notARealPlugin" "1.0";\n'
            'createNode notARealNodeType -n "oldEditorBookmark1";\n')
cmds.file(new=True, force=True)
cmds.file(odd, i=True, force=True)
house = cmds.group(empty=True, name="house")
cmds.setAttr(house + ".translate", 5, 0, 0)
wing = cmds.group(empty=True, name="wing", parent=house)
cmds.setAttr(wing + ".rotateY", 90)
cmds.setAttr(wing + ".scale", -1, 2, 1)          # negative + non-uniform scale
wall = cmds.polyCube(name="wall")[0]
cmds.parent(wall, "|house|wing", relative=True)
cmds.setAttr("|house|wing|wall.translate", 1, 2, 3)
door = cmds.polyCube(name="door")[0]
cmds.parent(door, "|house", relative=True)
cmds.setAttr("|house|door.visibility", False)                          # hidden itself
layer_geo = cmds.polyCube(name="crate")[0]
cmds.parent(layer_geo, "|house", relative=True)
layer = cmds.createDisplayLayer(["|house|crate"], name="HIDDEN_LYR", noRecurse=True)
cmds.setAttr(layer + ".visibility", False)                              # hidden by layer
cmds.group(empty=True, name="emptyGrp", parent="|house")                # empty group
before = [round(v, 4) for v in cmds.xform("|house|wing|wall.vtx[*]", q=True, ws=True, t=True)]
pm = plan(1)
pm["dest"] = os.path.join(d, "house_scout_model_v001.ma")
api.export_model_to_h_drive(["|house"], pm, "house.ma")
check("group of models: unknown plug-in data doesn't stop a .ma publish", os.path.isfile(pm["dest"]))
check("hidden, layer-hidden and empty left out, and reported",
      pm["left_out"]["hidden"] == ["crate", "door"] and pm["left_out"]["empty"] == ["emptyGrp"]
      and pm["left_out"]["unknown"] == 1)
check("working scene keeps its unknown node and plug-in requirement",
      cmds.ls("oldEditorBookmark1") != [] and "notARealPlugin" in (cmds.unknownPlugin(q=True, list=True) or []))
text = open(pm["dest"]).read()
check("published file doesn't ask for the missing plug-in", "notARealPlugin" not in text
      and 'requires maya "2025' in text)
crafted = os.path.join(d, "crafted.ma")
with open(crafted, "w") as f:
    f.write('//Maya ASCII 2025 scene\nrequires maya "2025ff03";\n'
            'requires -nodeType "oldNode" "stereoCamera_gone" "1.0";\n'
            'requires "lookdevKit" "1.0";\ncurrentUnit -l centimeter;\ncreateNode transform -n "a";\n'
            '// requires "notAHeader" "1.0"; stays: not in the header\n')
cmds.loadPlugin("lookdevKit", quiet=True)
dropped = api.drop_unknown_requires(crafted)
text = open(crafted).read()
check("requires for unloaded plug-ins stripped from a .ma header, loaded ones kept",
      dropped == ["stereoCamera_gone"] and "stereoCamera_gone" not in text
      and 'requires "lookdevKit"' in text and 'requires maya' in text and "notAHeader" in text)
cmds.file(new=True, force=True)
cmds.file(pm["dest"], open=True, force=True)
check("published: only the visible wall, in its groups",
      cmds.ls("door", "crate", "emptyGrp") == [] and cmds.ls("|backpack_model_GRP|house|wing|wall") != [])
after = [round(v, 4) for v in cmds.xform("|backpack_model_GRP|house|wing|wall.vtx[*]", q=True, ws=True, t=True)]
check("every vertex where it was in world space (negative/non-uniform scale)", after == before)
check("no unknown nodes in the published file", not cmds.ls(type="unknown"))
print("%d/%d passed" % (sum(ok), len(ok)))
