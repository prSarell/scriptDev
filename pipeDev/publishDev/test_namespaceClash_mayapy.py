r"""Headless test: namespace clashes refuse the publish (review #7, 2026-10-30).

    "C:\Program Files\Autodesk\Maya2025\bin\mayapy.exe" pipeDev/publishDev/test_namespaceClash_mayapy.py

Published files never carry a namespace, so Publish takes them off for the
export. If the plain name is already taken, Maya quietly renames instead
(wip:head_rl4 -> head_rl5), which can cut a MetaHuman DNA node off with no
error. Publish now refuses, and the working scene is left as it was.
Throwaway folders in %TEMP%; nothing real is touched.
"""
import os, sys, shutil, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), "layoutDev"),
                os.path.join(os.path.dirname(HERE), "projectDev")]
from PySide6 import QtWidgets
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

import maya.standalone
maya.standalone.initialize()
import maya.cmds as cmds

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

# --- 2026-11-12, fieldA: grass imported twice left namespaced copies of its
#     curves and shaders. Unassigned shaders are never published, so they
#     don't clash; real clashes get a Fix button.
def fieldA_like():
    fresh()
    cmds.namespace(add="tuft"); cmds.namespace(add="tuft:fieldA")
    # Ours, plain names: the ground and its shader.
    ground = cmds.polyPlane(name="ground")[0]
    mat = cmds.shadingNode("lambert", asShader=True, name="lambert_ground")
    sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name="lambert3SG")
    cmds.connectAttr(mat + ".outColor", sg + ".surfaceShader")
    cmds.sets(ground, edit=True, forceElement=sg)
    # The import's copy of it, assigned to nothing.
    mat2 = cmds.shadingNode("lambert", asShader=True, name="tuft:fieldA:lambert_ground")
    sg2 = cmds.sets(renderable=True, noSurfaceShader=True, empty=True,
                    name="tuft:fieldA:lambert3SG")
    cmds.connectAttr(mat2 + ".outColor", sg2 + ".surfaceShader")
    return ground, mat2, sg2

ground, mat2, sg2 = fieldA_like()
before = names()
api.check_namespace_clashes()
check("unassigned namespaced shader with a plain twin: no clash, scene unchanged",
      names() == before)

ground, mat2, sg2 = fieldA_like()
blade = cmds.polyCube(name="tuft:blade")[0]
cmds.sets(blade, edit=True, forceElement=sg2)            # now it's in use: published
cmds.createNode("animCurveTL", name="root_ctl_translateX")
loose = cmds.createNode("animCurveTL", name="tuft:root_ctl_translateX")
cmds.setKeyframe(loose, time=1, value=0)
cmds.lockNode(loose, lock=False)
try:
    api.check_namespace_clashes()
    clash = None
except api.NamespaceClash as e:
    clash = e
check("shader on a mesh + a loose curve: refused, as a NamespaceClash with the nodes",
      clash is not None and sorted(cmds.ls(clash.uuids)) == sorted(
          ["tuft:fieldA:lambert3SG", "tuft:fieldA:lambert_ground", "tuft:root_ctl_translateX"]))
fix = api.plan_namespace_fix(clash.uuids)
check("plan: the loose curve deleted, the shader in use renamed, flattened",
      [n.split("|")[-1] for n in fix["delete"]] == ["tuft:root_ctl_translateX"]
      and sorted(new for _, new in fix["rename"])
      == ["tuft_fieldA_lambert3SG", "tuft_fieldA_lambert_ground"] and fix["manual"] == [])
removed = api.fix_namespace_clashes(fix)
check("fixed: the blade keeps its shader, ours untouched, the curve gone",
      cmds.sets("tuft:bladeShape", isMember="tuft_fieldA_lambert3SG")
      and cmds.listConnections("tuft_fieldA_lambert3SG.surfaceShader") == ["tuft_fieldA_lambert_ground"]
      and cmds.sets("groundShape", isMember="lambert3SG") and not cmds.objExists("tuft:root_ctl_translateX")
      and cmds.objExists("root_ctl_translateX"))
check("fixed: empty namespace tuft:fieldA removed, tuft kept (the blade's still in it)",
      removed == ["tuft:fieldA"] and cmds.namespace(exists=":tuft"))
cmds.undo()
check("one Ctrl+Z puts it all back", cmds.objExists("tuft:fieldA:lambert3SG")
      and cmds.objExists("tuft:root_ctl_translateX") and not cmds.objExists("tuft_fieldA_lambert3SG"))
cmds.redo()
before = names()
api.check_namespace_clashes()
check("... and after the fix the publish's check passes", names() == before)

# --- MetaHuman DNA (linked by name, review #7) is left for the student
fresh()
cmds.createNode("network", name="head_rl4"); cmds.createNode("network", name="wip:head_rl4")
api.MANUAL_FIX_TYPES = ("network",)          # stands in for embeddedNodeRL4
try:
    api.check_namespace_clashes()
    fix = None
except api.NamespaceClash as e:
    fix = api.plan_namespace_fix(e.uuids)
api.MANUAL_FIX_TYPES = ("embeddedNodeRL4",)
check("DNA node: left for the student, nothing renamed or deleted",
      fix and fix["manual"] == ["wip:head_rl4"] and not fix["rename"] and not fix["delete"])

# --- The window's popup lists the plan and fixes on the button
import publishTool_ui as ui
ground, mat2, sg2 = fieldA_like()
cmds.sets(cmds.polyCube(name="tuft:blade")[0], edit=True, forceElement=sg2)
try:
    api.check_namespace_clashes()
except api.NamespaceClash as e:
    dialog = ui.NamespaceFixDialog("fieldA env — nothing published:\n" + str(e),
                                   api.plan_namespace_fix(e.uuids))
buttons = dict((b.text(), b) for b in dialog.findChildren(QtWidgets.QPushButton))
check("popup: Fix Namespace Clashes and Not Now", sorted(buttons) == ["Fix Namespace Clashes", "Not Now"])
buttons["Fix Namespace Clashes"].click()
check("... the button fixes the scene", dialog.fixed and cmds.objExists("tuft_fieldA_lambert3SG"))

print("\n%d/%d passed" % (sum(results), len(results)))
shutil.rmtree(base, ignore_errors=True)
