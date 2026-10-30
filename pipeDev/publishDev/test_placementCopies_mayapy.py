# A texture placement in the hierarchy (place3dTexture under the geometry)
# stays inside the pipe group in a Model publish (user, 2026-10-30: fieldA's
# snowLand_snowPlace came out with its parents, outside the publish node).
# The copies share the originals' shaders; while exporting, the copied
# placement drives them, then the original is connected back.
# Run: mayapy test_placementCopies_mayapy.py
import sys, os, shutil, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import maya.standalone; maya.standalone.initialize()
import maya.cmds as cmds
import publishTool_api as api
api.artist_name = lambda login: "Test Person"      # no ShotGrid in the test

ok = []
def check(label, cond):
    ok.append(bool(cond)); print("PASS" if cond else "FAIL", label)

d = tempfile.mkdtemp(prefix="placement_")
cmds.file(new=True, force=True)
grp = cmds.group(empty=True, name="rock_grp")
rock = cmds.parent(cmds.polySphere(name="rock_geo")[0], grp)[0]
place = cmds.parent(cmds.shadingNode("place3dTexture", asUtility=True, name="mossPlace"),
                    rock)[0]
proj = cmds.shadingNode("projection", asTexture=True, name="mossProj")
cmds.connectAttr(place + ".worldInverseMatrix[0]", proj + ".placementMatrix")
mat = cmds.shadingNode("lambert", asShader=True, name="mossMat")
cmds.connectAttr(proj + ".outColor", mat + ".color")
sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name="mossMatSG")
cmds.connectAttr(mat + ".outColor", sg + ".surfaceShader")
cmds.sets(rock, edit=True, forceElement=sg)
before = (sorted(cmds.ls(long=True)), cmds.listConnections(proj + ".placementMatrix", plugs=True))

plan = {"dest": os.path.join(d, "rock_scout_model_v001.ma"), "h_folder": d, "ext": ".ma",
        "asset": "rock", "asset_type": "prop", "code": "model", "version": 1, "login": "scout",
        "sg_asset": {"id": 1}}
api.export_model_to_h_drive(["rock_grp"], plan, os.path.join(d, "rock_work.ma"))
after = (sorted(cmds.ls(long=True)), cmds.listConnections(proj + ".placementMatrix", plugs=True))
check("working scene unchanged: the original placement still drives the projection",
      before == after and after[1] == ["mossPlace.worldInverseMatrix"])

cmds.file(new=True, force=True); cmds.file(plan["dest"], open=True, force=True)
G = "rock_model_GRP"
check("nothing outside the pipe group",
      [a for a in cmds.ls(assemblies=True) if a not in ("persp", "top", "front", "side")] == [G]
      and not cmds.ls("pipeTmp_*", recursive=True))
found = cmds.ls("mossPlace", long=True)
check("one placement, inside the group, driving the projection",
      len(found) == 1 and found[0].startswith("|%s|rock_grp|rock_geo|" % G)
      and cmds.ls(cmds.listConnections("mossProj.placementMatrix")[0], long=True) == found)

print("\n%d/%d passed" % (sum(ok), len(ok)))
shutil.rmtree(d, ignore_errors=True)
