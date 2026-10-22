r"""Headless test for Build putting published keys back on an asset.

    "C:\Program Files\Autodesk\Maya2025\bin\mayapy.exe" pipeDev/buildDev/test_shotKeys_mayapy.py

Works on throwaway folders in %TEMP%; never touches the real H drive,
scratch drive or Maya prefs. Keys are written by Publish's own
publishTool_anim.export_keys, so the format is the real one.

Covers spec §4 item 7 "Build Shot pulling animation back in" (DECIDED
2026-10-23): keys listed per asset from a shot's Layout and Animation
publishes, newest first; items made in the shot and the camera left out;
keys replace the asset's existing keys, on the same frames; keys from
another shot; a rig version with missing or locked controls (applied
anyway, mismatches listed); None; the record saved with the scene; the
rig's own driven keys left alone.
"""
import os, sys, json, time, shutil, tempfile

import maya.standalone
maya.standalone.initialize()
import maya.cmds as cmds

DEV = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(DEV, "publishDev"), os.path.join(DEV, "buildDev")]
import buildTool_api as api
import publishTool_anim as anim

base = tempfile.mkdtemp(prefix="shotkeys_")
H, S = os.path.join(base, "H"), os.path.join(base, "S")
FILM, SEQ, SHOT, OTHER = "NWF_SHF", "SEQ010", "SEQ010_120", "SEQ010_110"
LOGIN = "anna"
_cfg = os.path.join(base, "pipeline_config.json")
api.pub._config_path = lambda: _cfg
results = []


def check(name, ok):
    results.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name)


def save_as(path):
    if not os.path.isdir(os.path.dirname(path)):
        os.makedirs(os.path.dirname(path))
    cmds.file(rename=path)
    cmds.file(save=True, type="mayaAscii", force=True)


# Scout's rig on the H drive. v001: ctrl, tail_ctrl, locked_ctrl.
# v002: no tail_ctrl, locked_ctrl.tx locked, and a driven key of its own.
rig_dir = os.path.join(H, FILM, "maya", "assets", "character", "scout", "scenes", LOGIN)
rigs = {}
for v in (1, 2):
    cmds.file(new=True, force=True)
    group = cmds.group(empty=True, name="scout_rig_GRP")
    for name, value in (("sgAssetId", 7), ("asset", "scout"), ("assetType", "character"),
                        ("department", "rig"), ("version", v), ("artistId", LOGIN)):
        attr = "pipe_" + name
        if isinstance(value, int):
            cmds.addAttr(group, longName=attr, attributeType="long")
            cmds.setAttr("%s.%s" % (group, attr), value)
        else:
            cmds.addAttr(group, longName=attr, dataType="string")
            cmds.setAttr("%s.%s" % (group, attr), value, type="string")
    names = ["ctrl", "locked_ctrl"] + (["tail_ctrl"] if v == 1 else [])
    for name in names:
        cmds.parent(cmds.spaceLocator(name=name)[0], group)
    if v == 2:
        cmds.setAttr("locked_ctrl.tx", lock=True)
        cmds.setDrivenKeyframe("locked_ctrl.sy", currentDriver="ctrl.ty",
                               driverValue=0, value=1)
        cmds.setDrivenKeyframe("locked_ctrl.sy", currentDriver="ctrl.ty",
                               driverValue=1, value=2)
    rigs[v] = os.path.join(rig_dir, "scout_%s_rig_v%03d.ma" % (LOGIN, v))
    save_as(rigs[v])


def publish_keys(shot, code, version, tx_at_10, extra=True):
    """An animator's scene with rig v001 referenced and keyed, published
    through Publish's export_keys."""
    cmds.file(new=True, force=True)
    cmds.file(rigs[1], reference=True, namespace="scout_rig")
    cmds.setKeyframe("scout_rig:ctrl", attribute="translateX", time=1, value=0)
    cmds.setKeyframe("scout_rig:ctrl", attribute="translateX", time=10, value=tx_at_10)
    if extra:
        cmds.setKeyframe("scout_rig:tail_ctrl", attribute="rotateY", time=1, value=0)
        cmds.setKeyframe("scout_rig:tail_ctrl", attribute="rotateY", time=10, value=90)
        cmds.setKeyframe("scout_rig:locked_ctrl", attribute="translateX", time=1, value=3)
    scene = os.path.join(base, "work", "%s_%s.ma" % (shot, code))
    save_as(scene)
    item = anim.classify(["scout_rig:ctrl"])[0]
    folder = os.path.join(H, FILM, "maya", "sequences", SEQ, shot, "scenes", LOGIN)
    if not os.path.isdir(folder):
        os.makedirs(folder)
    stem = os.path.join(folder, "%s_%s_%s_%s_v%03d" % (shot, LOGIN, item["name"], code, version))
    plan = {"shot": shot, "login": LOGIN, "version": version, "stage": code}
    anim.export_keys(item, {"keys": stem + ".ma", "map": stem + ".json"}, plan, 1, 10, scene)
    time.sleep(1.1)     # publish times must differ (newest first)
    return stem


publish_keys(SHOT, "layout", 1, 2.0, extra=False)
publish_keys(SHOT, "anim", 1, 5.0)
publish_keys(OTHER, "anim", 1, 9.0, extra=False)
# Not an asset's keys: an item made in the shot, and the camera's map.
made = os.path.join(H, FILM, "maya", "sequences", SEQ, SHOT, "scenes", LOGIN,
                    "%s_%s_rock_anim_v001" % (SHOT, LOGIN))
shutil.copy(made.replace("rock", "scoutrig") + ".ma", made + ".ma")
with open(made + ".json", "w") as f:
    json.dump({"item": "rock", "asset": {}, "curves": {"a": ["rock", "tx"]}}, f)
with open(os.path.join(os.path.dirname(made), "%s_%s_camAnim_v001.json" % (SHOT, LOGIN)), "w") as f:
    json.dump({"format": 2, "curves": {}}, f)

# -- listing --------------------------------------------------------------
listed = api.list_shot_keys(H, FILM, SEQ, SHOT)
key = api.manifest_key("character", "scout", "rig")
check("only the asset's keys are listed (not made-in-shot, not camera)", list(listed) == [key])
kids = api.sorted_keys(listed[key])
anim_kid = api.keys_id(SHOT, LOGIN, "anim", 1)
layout_kid = api.keys_id(SHOT, LOGIN, "layout", 1)
check("layout and anim in one list, newest first", kids == [anim_kid, layout_kid])
check("label", api.keys_label(anim_kid, this_shot=SHOT, latest=anim_kid)
      == "v001 anim (anna)  (latest)")
other = api.list_shot_keys(H, FILM, SEQ, OTHER)[key]
other_kid = list(other)[0]
check("label shows another shot", "from %s" % OTHER in api.keys_label(other_kid, this_shot=SHOT))
check("made-on rig version recorded", listed[key][anim_kid]["made_on"]["version"] == 1)

# -- building into a shot that has rig v002 -------------------------------
shot_dir = api.shot_folder(S, FILM, SEQ, SHOT)
cmds.file(new=True, force=True)
cmds.file(rigs[2], reference=True, namespace="scout_rig")
cmds.setKeyframe("scout_rig:ctrl", attribute="rotateZ", time=4, value=45)   # by hand
save_as(os.path.join(shot_dir, "scenes", "%s_001.ma" % SHOT))
row = {"asset_type": "character", "asset": "scout", "code": "rig"}
driven_before = len(cmds.ls(type=("animCurveUL", "animCurveUU", "animCurveUA")) or [])
check("nothing recorded before Build puts keys on", api.keys_in_scene(row) is None)

done, warning = api.build_keys(shot_dir, row, anim_kid, listed[key][anim_kid])
cmds.currentTime(10)
check("keys on, same frames", abs(cmds.getAttr("scout_rig:ctrl.tx") - 5.0) < 1e-6)
check("old keys blown away", not cmds.listConnections("scout_rig:ctrl.rz", source=True,
                                                       destination=False))
check("rig's driven keys left alone",
      len(cmds.ls(type=("animCurveUL", "animCurveUU", "animCurveUA")) or []) == driven_before)
check("missing control listed", warning and "tail_ctrl.rotateY" in warning)
check("locked channel listed", warning and "locked_ctrl.translateX (locked)" in warning)
check("no leftover import namespace", not [n for n in cmds.namespaceInfo(":", listOnlyNamespaces=True)
                                           if n.startswith("buildKeys")])
check("recorded", api.keys_in_scene(row) == anim_kid)
cmds.file(save=True, force=True)
cmds.file(cmds.file(query=True, sceneName=True), open=True, force=True)
check("record saved with the scene", api.keys_in_scene(row) == anim_kid)
cmds.currentTime(10)
check("keys still on after reopen", abs(cmds.getAttr("scout_rig:ctrl.tx") - 5.0) < 1e-6)

# Roll back to layout, then keys from another shot, then None.
api.build_keys(shot_dir, row, layout_kid, listed[key][layout_kid])
cmds.currentTime(10)
check("roll back to layout keys", abs(cmds.getAttr("scout_rig:ctrl.tx") - 2.0) < 1e-6)
check("roll back leaves one curve per channel",
      len(cmds.listConnections("scout_rig:ctrl.tx", source=True, destination=False) or []) == 1)
api.build_keys(shot_dir, row, other_kid, other[other_kid])
cmds.currentTime(10)
check("keys from another shot", abs(cmds.getAttr("scout_rig:ctrl.tx") - 9.0) < 1e-6)
done, _ = api.build_keys(shot_dir, row, api.NO_KEYS)
check("None removes the keys", not cmds.listConnections("scout_rig:ctrl.tx", source=True,
                                                        destination=False))
check("None recorded", api.keys_in_scene(row) == api.NO_KEYS)

cmds.file(new=True, force=True)
try:
    api.build_keys(shot_dir, row, anim_kid, listed[key][anim_kid])
    check("asset not in scene refused", False)
except api.BuildError:
    check("asset not in scene refused", True)

shutil.rmtree(base, ignore_errors=True)
failed = [n for n, ok in results if not ok]
print("\n%d/%d passed" % (len(results) - len(failed), len(results)))
maya.standalone.uninitialize()
os._exit(1 if failed else 0)
