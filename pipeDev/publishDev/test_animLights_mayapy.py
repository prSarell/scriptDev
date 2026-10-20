# Lights in a shot (Layout/Animation) publish (user 2026-10-20: sometimes
# important for shot composition): a light made in the shot is its own
# "light" item, written as a small .ma with its settings and keys, never
# cached to Alembic (even on Final). Run: mayapy test_animLights_mayapy.py
import sys, os, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import maya.standalone; maya.standalone.initialize()
import maya.cmds as cmds
import publishTool_api as api
import publishTool_anim as anim

ok = []
def check(label, cond): ok.append(bool(cond)); print("PASS" if cond else "FAIL", label)

base = tempfile.mkdtemp(prefix="animlights_")
H, SC = os.path.join(base, "H"), os.path.join(base, "scratch")
shot_rel = ["NWF_SHF", "maya", "sequences", "EAP_010", "EAP_010_010"]
os.makedirs(os.path.join(H, *shot_rel, "scenes"))
os.makedirs(os.path.join(SC, *shot_rel, "scenes"))
api.who = lambda: "scout"

key = cmds.listRelatives(cmds.spotLight(name="keyLightShape", intensity=2.5, coneAngle=35), parent=True)[0]
key = cmds.rename(key, "keyLight")
cmds.setKeyframe(key + ".intensity", time=1, value=2.5)
cmds.setKeyframe(key + ".intensity", time=10, value=4.0)
fill = cmds.rename(cmds.listRelatives(cmds.pointLight(name="fillShape"), parent=True)[0], "fill")
rig = cmds.group(empty=True, name="lights_grp")
cmds.parent(cmds.rename(cmds.listRelatives(cmds.directionalLight(name="rimShape"), parent=True)[0], "rim"), rig)
ball = cmds.polySphere(name="ball")[0]
mixed = cmds.group(empty=True, name="mixed_grp")
cmds.parent(cmds.rename(cmds.listRelatives(cmds.pointLight(name="bounceShape"), parent=True)[0], "bounce"), mixed)
cmds.parent(cmds.polyCube(name="card")[0], mixed)
cmds.playbackOptions(minTime=1, maxTime=10)
scene = os.path.join(SC, *shot_rel, "scenes", "anim_001.ma")
cmds.file(rename=scene); cmds.file(save=True, type="mayaAscii")

items = anim.classify([key, fill, rig, ball, mixed])
by = dict((i["name"], i) for i in items)
check("spot light (keyed) -> light item", by["keyLight"]["kind"] == "light" and by["keyLight"]["animated"])
check("point light, not keyed -> light item", by["fill"]["kind"] == "light" and not by["fill"]["animated"])
check("group of lights -> one light item", by["lightsgrp"]["kind"] == "light")
check("geometry stays 'made in the shot'", by["ball"]["kind"] == "shot")
check("group with a light AND geometry stays 'made in the shot'", by["mixedgrp"]["kind"] == "shot")
check("label says light", by["keyLight"]["label"] == "keyLight (light, made in the shot, keyed)")

plan = anim.plan_anim(scene, H, SC, items)
plan["stage"] = anim.FINAL          # Final: models get caches, lights never do
files = plan["item_files"]
written = anim.write_anim(items, plan, 1, 10, scene)
check("light file for each light item", all(os.path.isfile(files[n]["light"]) for n in ("keyLight", "fill", "lightsgrp")))
check("no Alembic for lights, even on Final", not any(os.path.exists(files[n]["cache"]) for n in ("keyLight", "fill", "lightsgrp")))
check("geometry still cached on Final", os.path.isfile(files["ball"]["cache"]))
check("keyed light also gets its keys + map", os.path.isfile(files["keyLight"]["keys"]) and os.path.isfile(files["keyLight"]["map"]))
check("light file names", os.path.basename(files["keyLight"]["light"]) == "EAP_010_010_scout_keyLight_anim_v001_light.ma")

cmds.file(new=True, force=True)
cmds.file(files["keyLight"]["light"], i=True)
shape = cmds.listRelatives("keyLight", shapes=True)[0]
check("light file: the spot light with its settings",
      cmds.nodeType(shape) == "spotLight" and abs(cmds.getAttr(shape + ".coneAngle") - 35) < 1e-3)
cmds.currentTime(10)
check("light file: its keys come with it", abs(cmds.getAttr(shape + ".intensity") - 4.0) < 1e-3)
cmds.file(new=True, force=True)
cmds.file(files["lightsgrp"]["light"], i=True)
check("group of lights: group and light inside", cmds.objExists("lights_grp|rim"))

print("\n%d/%d passed" % (sum(ok), len(ok)))
