r"""Headless test: a Rigging publish needs a hand-made cache_SET.

    "C:\Program Files\Autodesk\Maya2025\bin\mayapy.exe" pipeDev/publishDev/test_rigCacheSet_mayapy.py

Throwaway folders in %TEMP%; ShotGrid and the playblast are stubbed, so
nothing real is touched. Spec: filmPipeline_spec.md §4, "cache_SET".
"""
import os, sys, stat, shutil, tempfile

import maya.standalone
maya.standalone.initialize()
import maya.cmds as cmds

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import publishTool_api as api

base = tempfile.mkdtemp(prefix="cacheset_")
results = []


def check(name, ok):
    results.append(bool(ok)); print(("PASS " if ok else "FAIL ") + name)


def refused(objects, text):
    try:
        api.check_cache_set(objects)
    except api.PublishError as e:
        return text in str(e)
    return False


def rig_scene(with_set=True, members=("body_geo",)):
    cmds.file(new=True, force=True)
    root = cmds.group(empty=True, name="scout_rig")
    geo = cmds.group(empty=True, name="geo", parent=root)
    cmds.polyCube(name="body_geo"); cmds.parent("body_geo", geo)
    cmds.polySphere(name="eye_geo"); cmds.parent("eye_geo", geo)
    ctrl = cmds.circle(name="root_CTRL")[0]; cmds.parent(ctrl, root)
    if with_set:
        cmds.sets(list(members), name=api.CACHE_SET) if members else \
            cmds.sets(empty=True, name=api.CACHE_SET)
    return root


# --- the check
rig_scene(with_set=False)
check("no cache_SET -> refused", refused([], "has no cache_SET"))
check("message tells the rigger how to make one", refused([], "Create > Sets > Set"))
rig_scene(members=())
check("empty cache_SET -> refused", refused([], "is empty"))
rig_scene(members=("root_CTRL",))
check("cache_SET with only a control (no geometry) -> refused", refused([], "no geometry"))
rig_scene(members=("geo",))
check("cache_SET holding a group of meshes -> accepted", api.check_cache_set([]) == "cache_SET")
rig_scene()
check("whole-scene rig with cache_SET -> accepted", api.check_cache_set([]) == "cache_SET")
check("objects include the geometry -> accepted", api.check_cache_set(["scout_rig"]) == "cache_SET")
check("set members outside the published objects -> refused",
      refused(["root_CTRL"], "aren't in this publish"))
cmds.namespace(add="extra"); cmds.sets(["eye_geo"], name="extra:cache_SET")
check("two cache_SETs -> refused", refused([], "more than one"))

# --- export keeps the set (selected objects, with a namespace taken off)
rig_scene()
cmds.namespace(add="wip")
for n in ("scout_rig", "cache_SET"):
    cmds.rename(n, "wip:" + n)
dest = os.path.join(base, "scout_rig_v001.ma")
plan = {"dest": dest, "h_folder": base, "ext": ".ma",
        "cache_set_uuid": cmds.ls(api.check_cache_set(["wip:scout_rig"]), uuid=True)[0]}
api.export_to_h_drive(["wip:scout_rig"], plan)
cmds.file(new=True, force=True)
cmds.file(dest, open=True, force=True)
check("published rig file contains cache_SET (namespace taken off)", cmds.objExists("cache_SET"))
check("cache_SET still lists body_geo",
      [m.split("|")[-1] for m in cmds.sets("cache_SET", query=True) or []] == ["body_geo"])

# --- publish() refuses before anything is written or uploaded
api.plan_publish = lambda *a, **k: {"dest": os.path.join(base, "never.ma"), "h_folder": base,
                                     "ext": ".ma"}
calls = []
api.find_shotgrid_asset = lambda *a: calls.append("shotgrid")
api.playblast_frames = lambda *a, **k: calls.append("playblast")
rig_scene(with_set=False)
try:
    api.publish("x.ma", base, base, "rig")
    check("publish() refuses a rig with no cache_SET", False)
except api.PublishError:
    check("publish() refuses a rig with no cache_SET", True)
check("refused before ShotGrid or playblast", calls == [])
check("nothing written to the H drive", not os.path.exists(os.path.join(base, "never.ma")))
try:
    api.publish("x.ma", base, base, "model")
except Exception:
    pass
check("model publishes don't need a cache_SET", calls[:1] == ["shotgrid"])

print("\n%d/%d passed" % (sum(results), len(results)))
for root, dirs, files in os.walk(base):
    for f in files:
        os.chmod(os.path.join(root, f), stat.S_IWRITE)
shutil.rmtree(base, ignore_errors=True)
maya.standalone.uninitialize()
