r"""Headless test for Publish's script-node check (spec §4 "Shot (animation)
publish v0", item 8).

    "C:\Program Files\Autodesk\Maya2025\bin\mayapy.exe" pipeDev/publishDev/test_scriptNodeCheck_mayapy.py

Real scenes (repo test scenes, and the T7 / D: film folders if present)
must pass; scenes with an extra script node, a standard-named node hiding
Python, or a referenced file carrying one must be refused. Works on
throwaway files in %TEMP%; real scenes are only opened, never saved.
"""
import os, sys, glob, shutil, tempfile

import maya.standalone
maya.standalone.initialize()
import maya.cmds as cmds

DEV = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(DEV)
sys.path.insert(0, os.path.join(DEV, "publishDev"))
import publishTool_api as api

results = []


def check(name, ok):
    results.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name)


def refused():
    try:
        api.check_script_nodes()
    except api.PublishError as e:
        return str(e)
    return None


# --- real scenes pass
real = sorted(glob.glob(os.path.join(REPO, "rigDev", "**", "*.ma"), recursive=True))
real += sorted(glob.glob(os.path.join(REPO, "mpToolSet", "studioLibrary", "mutils", "tests",
                                      "data", "*.ma")))
for root in (r"G:\scratch\NWF_SHF", r"G:\H\NWF_SHF", r"D:\NWF_SHF"):
    real += sorted(glob.glob(os.path.join(root, "maya", "**", "*.ma"), recursive=True))
standard_seen = 0
for path in real:
    try:
        cmds.file(path, open=True, force=True, executeScriptNodes=False,
                  loadReferenceDepth="all")
    except RuntimeError:
        pass    # missing references etc. still leave the scene open
    standard_seen += len(cmds.ls(type="script") or [])
    why = refused()
    if why:
        check("real scene passes: %s" % os.path.relpath(path), False)
        print("   ", why.splitlines()[1])
check("%d real scenes pass (%d standard script nodes seen)" % (len(real), standard_seen),
      all(ok for name, ok in results if name.startswith("real scene")) and real)

base = tempfile.mkdtemp(prefix="scriptnode_")

# --- an empty new scene passes
cmds.file(new=True, force=True)
check("new scene passes", refused() is None)

# --- an extra script node is refused, by name
cmds.scriptNode(name="harmlessLooking", beforeScript='print "hi";', scriptType=1)
why = refused()
check("extra script node refused", why and "harmlessLooking" in why)

# --- Maya's standard names pass with ordinary MEL ...
cmds.file(new=True, force=True)
cmds.scriptNode(name="sceneConfigurationScriptNode",
                beforeScript="playbackOptions -min 1 -max 120 -ast 1 -aet 200 ;", scriptType=6)
check("standard name with ordinary MEL passes", refused() is None)

# --- ... but not with Python hidden in them
cmds.file(new=True, force=True)
cmds.scriptNode(name="uiConfigurationScriptNode",
                beforeScript='python("import base64, zlib; exec(zlib.decompress(base64.b64decode(x)))");',
                scriptType=2)
why = refused()
check("standard name hiding Python refused", why and "uiConfigurationScriptNode" in why)

# --- a virus-style node inside a namespace (as in the student's file)
cmds.file(new=True, force=True)
cmds.namespace(add="Vine3_Sculpt_Rigged")
cmds.scriptNode(name="Vine3_Sculpt_Rigged:maya_secure_system_scriptNode",
                beforeScript="import maya.cmds as cmds", sourceType="python", scriptType=2)
why = refused()
check("namespaced virus-style node refused", why and "maya_secure_system_scriptNode" in why)

# --- a referenced file carrying a script node: refused, and says where from
cmds.file(new=True, force=True)
cmds.polyCube(name="box")
cmds.scriptNode(name="sneaky", beforeScript="python(\"print(1)\");", scriptType=1)
dirty = os.path.join(base, "dirtyRig.ma")
cmds.file(rename=dirty); cmds.file(save=True, type="mayaAscii")
cmds.file(new=True, force=True)
cmds.file(dirty, reference=True, namespace="rig")
why = refused()
check("script node in a reference refused", why and "rig:sneaky" in why and "dirtyRig.ma" in why)

# --- publish() checks first, before anything else (no drives needed)
try:
    api.publish(os.path.join(base, "x.ma"), "", "", "model")
    check("publish() refuses before anything else", False)
except api.PublishError as e:
    check("publish() refuses before anything else", "script nodes" in str(e))
print("\nMessage the student sees:\n" + why)

print("\n%d/%d passed" % (sum(ok for _, ok in results), len(results)))
shutil.rmtree(base, ignore_errors=True)
maya.standalone.uninitialize()
