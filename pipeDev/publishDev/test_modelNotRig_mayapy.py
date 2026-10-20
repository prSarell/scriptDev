# A rig must never go through the Model publish (freeze + delete history
# would break it; user 2026-10-20): check_not_a_rig refuses joints, skins,
# blendShapes, IK and constraints; a plain model passes; the rig export
# keeps transforms and history. Run: mayapy test_modelNotRig_mayapy.py
import sys, os, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import maya.standalone; maya.standalone.initialize()
import maya.cmds as cmds
import publishTool_api as api
api.artist_name = lambda login: "Test Person"      # no ShotGrid in the test
ok = []
def check(label, cond): ok.append(bool(cond)); print("PASS" if cond else "FAIL", label)
def refused(objects):
    try:
        api.check_not_a_rig(objects)
    except api.PublishError as e:
        return str(e)
    return ""

# Plain model: fine, selected or whole scene.
geo = cmds.polyCube(name="box_geo")[0]
cmds.polyBevel(geo + ".e[0]")
check("plain model (with history) passes, selected", not refused([geo]))
check("plain model passes, whole scene", not refused([]))

# A skinned mesh under a rig group.
rig = cmds.group(empty=True, name="scout_rig")
body = cmds.polyCylinder(name="body_geo")[0]
cmds.select(clear=True)
j1 = cmds.joint(name="root_jnt"); j2 = cmds.joint(name="tip_jnt", position=(0, 2, 0))
cmds.parent(body, j1, rig)
cmds.skinCluster(j1, body, toSelectedBones=True)
msg = refused([rig])
check("rig refused, selected group", "Rigging" in msg and "joint" in msg and "skinCluster" in msg)
print("   ", msg.splitlines()[0])
check("rig refused, whole scene", refused([]))
check("skinned mesh alone refused (skin found through history)", "skinCluster" in refused([rig + "|body_geo"]))

# Constraint / blendShape on their own count too.
cmds.file(new=True, force=True)
a = cmds.polySphere(name="a_geo")[0]; b = cmds.spaceLocator(name="drv")[0]
cmds.parentConstraint(b, a)
check("constraint refused", "constraint" in refused([a]))
cmds.file(new=True, force=True)
base = cmds.polySphere(name="face_geo")[0]; tgt = cmds.polySphere(name="smile")[0]
cmds.blendShape(tgt, base)
check("blendShape refused", "blendShape" in refused([base]))

# publish() refuses before anything is made.
cmds.file(new=True, force=True)
cmds.joint(name="j")
calls = []
api.plan_publish = lambda *a, **k: {"objects": []}
api.find_shotgrid_asset = lambda *a, **k: calls.append("sg")
try:
    api.publish("D:/x.ma", "D:/", "D:/", "model", objects=[])
    check("publish() refuses a rig as Model", False)
except api.PublishError as e:
    check("publish() refuses a rig as Model, before ShotGrid", "Rigging" in str(e) and not calls)
except TypeError as e:
    print("   publish signature:", e); check("publish() refuses a rig as Model", False)

print("\n%d/%d passed" % (sum(ok), len(ok)))
