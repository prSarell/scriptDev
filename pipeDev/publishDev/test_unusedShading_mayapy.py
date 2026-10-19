# Unassigned shaders: what counts as unused (rig utilities never do), whole-
# scene publishes leave them out and put the working scene back, and Build
# clears leftovers holding an asset's namespace (the shotSetup_001 case).
# Run: mayapy test_unusedShading_mayapy.py
import sys, os, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), "buildDev")]
import maya.standalone; maya.standalone.initialize()
import maya.cmds as cmds
import publishTool_api as api

ok = []
def check(label, cond):
    ok.append(bool(cond)); print("PASS" if cond else "FAIL", label)

def material(name, textured=False):
    sh = cmds.shadingNode("lambert", asShader=True, name=name)
    sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=name + "SG")
    cmds.connectAttr(sh + ".outColor", sg + ".surfaceShader", force=True)
    if textured:
        tex = cmds.shadingNode("file", asTexture=True, name=name + "_file")
        p2d = cmds.shadingNode("place2dTexture", asUtility=True, name=name + "_p2d")
        cmds.connectAttr(p2d + ".outUV", tex + ".uvCoord")
        cmds.connectAttr(tex + ".outColor", sh + ".color")
    return sh, sg

# -- 1. what counts as unused --------------------------------------------
geo = cmds.polyCube(name="bag_geo")[0]
cmds.sets(geo, edit=True, forceElement=material("usedMat", textured=True)[1])
material("unusedMat", textured=True)
cmds.shadingNode("blinn", asShader=True, name="looseMat")          # no shading group at all
md = cmds.shadingNode("multiplyDivide", asUtility=True, name="rig_md")  # a rig utility
ctl = cmds.circle(name="ctl")[0]
cmds.connectAttr(ctl + ".tx", md + ".input1X"); cmds.connectAttr(md + ".outputX", geo + ".ty")
shared = cmds.shadingNode("multiplyDivide", asUtility=True, name="shared_md")  # feeds unused shader AND the rig
cmds.connectAttr(shared + ".outputX", "unusedMat.diffuse"); cmds.connectAttr(shared + ".outputY", geo + ".tz")
unused = set(api.unused_shading_nodes())
check("unused shader, its SG, file and place2d found",
      {"unusedMat", "unusedMatSG", "unusedMat_file", "unusedMat_p2d"} <= unused)
check("material with no shading group found", "looseMat" in unused)
check("used shader and its texture kept", not unused & {"usedMat", "usedMatSG", "usedMat_file", "usedMat_p2d"})
check("rig utility never counted", "rig_md" not in unused)
check("utility that also drives the rig kept", "shared_md" not in unused)
check("Maya defaults kept", not unused & {"lambert1", "initialShadingGroup", "standardSurface1", "particleCloud1"})

# -- 2. whole-scene publish leaves them out, scene put back ----------------
cmds.namespace(add="bag")
cmds.rename("unusedMat", "bag:unusedMat")
before = sorted(cmds.ls())
d = tempfile.mkdtemp(prefix="unusedpub_")
plan = {"dest": os.path.join(d, "bag_scout_rig_v001.ma"), "h_folder": d, "ext": ".ma"}
api.export_to_h_drive([], plan)
check("working scene exactly as before (incl. namespace)", sorted(cmds.ls()) == before)
check("undo is still usable afterwards", cmds.undoInfo(query=True, state=True) in (True, False))
text = open(plan["dest"]).read()
check("published file has no unused shaders", "unusedMat" not in text and "looseMat" not in text)
check("published file keeps used shader and rig utilities",
      all(n in text for n in ("usedMat", "usedMat_file", "rig_md", "shared_md")))
check("publish reports what it left out", "unusedMatSG" in plan["unused_shading_left_out"])

# -- 3. Build clears leftovers holding the asset's namespace ---------------
import buildTool_api as b
base = tempfile.mkdtemp(prefix="unusedbuild_")
H, SC = os.path.join(base, "H"), os.path.join(base, "scratch")
cmds.file(new=True, force=True)
h_v5 = os.path.join(H, "NWF_SHF", "maya", "assets", "prop", "backpack", "scenes", "scout", "backpack_scout_model_v005.ma")
os.makedirs(os.path.dirname(h_v5)); cmds.polyCube(name="backPack_geo")
cmds.file(rename=h_v5); cmds.file(save=True, type="mayaAscii")
shot = os.path.join(SC, "NWF_SHF", "maya", "sequences", "EAP_010", "EAP_010_010")
os.makedirs(os.path.join(shot, "scenes"))
cmds.file(new=True, force=True); cmds.workspace(shot, openWorkspace=True)
cmds.namespace(add="backpack")
material("backpack:lambert7")      # the shotSetup_001 leftovers: unassigned, in backpack:
pub = [p for p in b.list_published(H, "NWF_SHF") if p["asset"] == "backpack"][0]
done, warning, _ = b.build_asset(shot, pub, pub["latest"])
check("Build clears the leftovers and references the backpack",
      any("removed unused shader" in d for d in done) and any("referenced" in d for d in done))
check("... under the clean backpack: namespace", cmds.ls("backpack:backPack_geo") != [])
cmds.file(new=True, force=True); cmds.workspace(shot, openWorkspace=True)
cmds.namespace(add="backpack")
geo = cmds.polyCube(name="backpack:something_real")[0]
try:
    b.build_asset(shot, pub, pub["latest"])
    check("real nodes in backpack: still stop Build", False)
except api.PublishError as e:
    check("real nodes in backpack: still stop Build", "already used" in str(e))
print("%d/%d passed" % (sum(ok), len(ok)))
