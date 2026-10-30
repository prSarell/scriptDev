r"""Headless test: namespace clashes refuse the publish (review #7, 2026-10-30).

    "C:\Program Files\Autodesk\Maya2025\bin\mayapy.exe" pipeDev/publishDev/test_namespaceClash_mayapy.py

Published files never carry a namespace, so Publish takes them off for the
export. If the plain name is already taken, Maya quietly renames instead
(wip:head_rl4 -> head_rl5), which can cut a MetaHuman DNA node off with no
error. Publish now refuses, and the working scene is left as it was.
Throwaway folders in %TEMP%; nothing real is touched.
"""
import os, sys, shutil, tempfile

import maya.standalone
maya.standalone.initialize()
import maya.cmds as cmds

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import publishTool_api as api

base = tempfile.mkdtemp(prefix="nsclash_")
results = []


def check(name, ok):
    results.append(bool(ok)); print(("PASS " if ok else "FAIL ") + name)


def names():
    return sorted(cmds.ls(recursive=True))


def refused(text):
    before = names()
    try:
        api.check_namespace_clashes()
    except api.PublishError as e:
        if text not in str(e):
            print("    (message was: %s)" % str(e))
        return text in str(e) and names() == before
    return False


def fresh():
    cmds.file(new=True, force=True)
    cmds.namespace(add="wip")


# --- a DG node (like a DNA node) whose plain name is taken
fresh()
cmds.createNode("network", name="head_rl4")
cmds.createNode("network", name="wip:head_rl4")
check("DG clash -> refused, names both, scene unchanged", refused("wip:head_rl4 -> head_rl4 (taken)"))

# --- DAG nodes under the same parent
fresh()
cmds.polyCube(name="head_geo"); cmds.polyCube(name="wip:head_geo")
check("DAG clash at the same level -> refused", refused("wip:head_geo -> head_geo (taken)"))

# --- two namespaces giving the same name
fresh()
cmds.namespace(add="old")
cmds.createNode("network", name="wip:body_rl4"); cmds.createNode("network", name="old:body_rl4")
check("two namespaces, same name -> refused", refused("-> body_rl4 (taken)"))

# --- DAG nodes with the same name in different groups are fine in Maya
fresh()
a = cmds.group(empty=True, name="grpA"); cmds.parent(cmds.polyCube(name="eye_geo")[0], a)
b = cmds.group(empty=True, name="wip:grpB"); cmds.parent(cmds.polyCube(name="wip:eye_geo")[0], b)
before = names()
api.check_namespace_clashes()
check("same name in different groups -> accepted, scene unchanged", names() == before)

# --- no clash: the export still takes namespaces off
fresh()
cmds.polyCube(name="wip:backpack_geo")
dest = os.path.join(base, "clean.ma")
plan = {"dest": dest, "h_folder": base, "ext": ".ma"}
api.export_to_h_drive(["wip:backpack_geo"], plan)
check("no clash: published without the namespace, working scene keeps it",
      plan["namespaces_removed"] == ["wip"] and cmds.objExists("wip:backpack_geo"))
cmds.file(new=True, force=True); cmds.file(dest, open=True, force=True)
check("no clash: published name is clean", cmds.objExists("backpack_geo"))

# --- the export itself refuses too, and leaves nothing on H
fresh()
cmds.createNode("network", name="head_rl4"); cmds.createNode("network", name="wip:head_rl4")
cmds.polyCube(name="wip:head_geo")
dest = os.path.join(base, "never.ma")
try:
    api.export_to_h_drive(["wip:head_geo"], {"dest": dest, "h_folder": base, "ext": ".ma"})
    check("export with a clash -> refused", False)
except api.PublishError:
    check("export with a clash -> refused, nothing written", not os.path.exists(dest))
check("export refused: working scene names put back",
      cmds.objExists("wip:head_rl4") and cmds.objExists("head_rl4") and cmds.objExists("wip:head_geo"))

# --- publish() refuses before ShotGrid or the playblast
calls = []
api.plan_publish = lambda *a, **k: calls.append("plan") or {
    "dest": dest, "h_folder": base, "ext": ".ma"}
api.find_shotgrid_asset = lambda *a: calls.append("shotgrid")
api.playblast_frames = lambda *a, **k: calls.append("playblast")
try:
    api.publish("x.ma", base, base, "model", objects=["wip:head_geo"])
    check("publish() with a clash -> refused", False)
except api.PublishError as e:
    check("publish() with a clash -> refused before anything else", "(taken)" in str(e) and calls == [])

print("\n%d/%d passed" % (sum(results), len(results)))
shutil.rmtree(base, ignore_errors=True)
