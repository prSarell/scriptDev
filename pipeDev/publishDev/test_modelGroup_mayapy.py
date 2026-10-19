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
# Republish from that file (whole scene): the old group is replaced, not nested.
cmds.file(rename=os.path.join(d, "work2.ma"))
p5 = plan(5); api.export_model_to_h_drive([], p5, "work2.ma")
check("republish leaves working scene's group alone", cmds.getAttr("backpack_model_GRP.pipe_version") == 4)
cmds.file(new=True, force=True); cmds.file(p5["dest"], open=True, force=True)
check("republish: one group, not nested", cmds.ls("backpack_model_GRP", long=True) == ["|backpack_model_GRP"]
      and cmds.listRelatives("backpack_model_GRP", children=True, type="transform") == ["backPack_geo"]
      and cmds.getAttr("backpack_model_GRP.pipe_version") == 5)
check("file is read-only", not os.access(p5["dest"], os.W_OK))
print("%d/%d passed" % (sum(ok), len(ok)))
