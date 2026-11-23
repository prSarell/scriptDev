r"""Headless test: the mpRig shelf's Rig Sets tool (rigDev/rigSets.py) and
Publish's control sets by asset type (user, 2026-11-11): a character has
body_controls_SET (+ face_controls_SET); an environment, prop, vehicle...
has one controls_SET and no face set.

    "C:\Program Files\Autodesk\Maya2025\bin\mayapy.exe" pipeDev/publishDev/test_rigSetsTool_mayapy.py

Throwaway folders in %TEMP%; nothing real is touched.
"""
import os, sys, shutil, tempfile

import maya.standalone
maya.standalone.initialize()
import maya.cmds as cmds

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "..", "rigDev")))
import publishTool_api as api
import rig_rules
import rigSets

base = tempfile.mkdtemp(prefix="rigsets_")
results = []


def check(name, ok):
    results.append(bool(ok)); print(("PASS " if ok else "FAIL ") + name)


def refused(text, objects, asset_type):
    try:
        api.check_control_sets(list(objects), asset_type)
    except api.PublishError as e:
        if text not in str(e):
            print("    (message was: %s)" % str(e).splitlines()[0])
        return text in str(e)
    return False


def grass_rig(asset_type="environment"):
    """Like grassBladeA: one top group, a skinned blade, hidden blendshape
    targets, *_CTL / *_ctl controls and *_CRV rig curves. Saved in an
    asset's scenes folder of the given type."""
    cmds.file(new=True, force=True)
    top = cmds.group(empty=True, name="grassA")
    geo = cmds.group(empty=True, name="bladeGeo", parent=top)
    blade = cmds.polyPlane(name="grassBladeA001")[0]
    cmds.parent(blade, geo)
    targets = cmds.group(empty=True, name="bladeProfile_blendShapes", parent=top)
    fat = cmds.polyPlane(name="grassBladeA_fatBS_001")[0]
    cmds.parent(fat, targets)
    cmds.blendShape(fat, blade)
    cmds.setAttr(targets + ".visibility", 0)
    rig = cmds.group(empty=True, name="rigBuild", parent=top)
    for name in ("blade_Top_CTL", "blade_FK_000_CTL"):
        cmds.parent(cmds.circle(name=name)[0], rig)
    cmds.parent(cmds.curve(name="blade_000_CRV", p=[(0, 0, 0), (0, 1, 0)], d=1), rig)
    cmds.parent(cmds.circle(name="grassA_master_ctl")[0], top)
    folder = os.path.join(base, "NWF_SHF", "maya", "assets", asset_type, "grassBladeA",
                          "scenes", "rig", "e131988")
    os.makedirs(folder, exist_ok=True)
    cmds.file(rename=os.path.join(folder, "grassA_001.ma"))
    cmds.file(save=True, type="mayaAscii")
    cmds.select(clear=True)
    return "|" + top


try:
    # --- the tool's built-in names match the pipe's rig_rules ---------------
    # The defaults it uses without the pipe: the module's text up to where
    # it reads rig_rules, run with rig_rules "missing".
    src = open(rigSets.__file__).read()
    ns = {}
    exec(compile(src.split("if _rules is not None:")[0].replace(
        "import rig_rules as _rules", "raise ImportError"), "rigSets_defaults", "exec"), ns)
    check("without the pipe it really uses its own names", ns["_rules"] is None)
    check("built-in names = rig_rules (cache, character, other, control names)",
          ns["CACHE_SET"] == rig_rules.CACHE_SET
          and ns["CHARACTER_TYPES"] == rig_rules.CHARACTER_TYPES
          and ns["CHARACTER_CONTROL_SETS"] == rig_rules.CHARACTER_CONTROL_SETS
          and ns["OTHER_CONTROL_SETS"] == rig_rules.OTHER_CONTROL_SETS
          and ns["CONTROL_NAMES"] == rig_rules.CONTROL_NAMES
          and [k[:2] for k in ns["KNOWN_SETS"]] == [k[:2] for k in rig_rules.KNOWN_SETS])
    check("rig_rules: prop/environment/vehicle -> controls_SET, no face",
          all(rig_rules.control_sets_for(t) == {"body": "controls_SET", "face": None}
              for t in ("prop", "environment", "vehicle")))
    check("rig_rules: character (and unknown None) -> body + face",
          rig_rules.control_sets_for("character")["body"] == "body_controls_SET"
          and rig_rules.control_sets_for(None)["face"] == "face_controls_SET")

    # --- environment rig, nothing made yet -----------------------------------
    top = grass_rig("environment")
    check("asset type from the scene's folder", rigSets.scene_asset_type() == "environment")
    check("top group found with nothing selected", rigSets.top_group() == top)
    rows = rigSets.check("environment", top)
    check("environment rig: cache_SET + controls_SET, no face row",
          [r["name"] for r in rows] == ["cache_SET", "controls_SET"])
    check("both missing and required", all(not r["ok"] and r["required"] for r in rows))
    cache_s = [rigSets._short(n) for n in rows[0]["suggestion"]]
    check("cache suggestion: the blade only, not the blendshape target", cache_s == ["grassBladeA001"])
    ctrl_s = sorted(rigSets._short(n) for n in rows[1]["suggestion"])
    check("controls suggestion: *_CTL / *_ctl, not *_CRV",
          ctrl_s == ["blade_FK_000_CTL", "blade_Top_CTL", "grassA_master_ctl"])
    check("Publish refuses: no cache_SET", "no cache_SET" in (rigSets.publish_check("environment", top) or ""))
    check("Publish refuses: no controls_SET, explained for an environment",
          refused("This rig has no controls_SET", [top], "environment")
          and refused("An environment rig needs one controls set", [top], "environment"))

    made = rigSets.build_missing(rows)
    check("Build Missing Sets made both", sorted(n for n, _ in made) == ["cache_SET", "controls_SET"])
    rows = rigSets.check("environment", top)
    check("rows all OK after building", all(r["ok"] for r in rows))
    check("Publish's own check: ready", rigSets.publish_check("environment", top) is None)
    r = api.check_control_sets([top], "environment")
    check("check_control_sets: controls_SET is the body, no face",
          r["body"] == "controls_SET" and r["face"] is None and r["sets"] == ["controls_SET"])
    check("same rig as a character -> refused, told to rename",
          refused("controls are in controls_SET, but a character rig uses body_controls_SET",
                  [top], "character"))
    check("undo removes what Build made", (cmds.undo() or True) and not cmds.objExists("cache_SET")
          and not cmds.objExists("controls_SET"))

    # --- prop rig carrying a character's set name -----------------------------
    top = grass_rig("prop")
    rigSets.make_set("cache_SET", rigSets.suggest_cache(top))
    rigSets.make_set("body_controls_SET", rigSets.suggest_controls(top, "body", False))
    check("prop with body_controls_SET -> Publish says rename",
          refused("controls are in body_controls_SET, but a prop rig uses controls_SET", [top], "prop"))
    check("an environment gets 'an'",
          refused("but an environment rig uses controls_SET", [top], "environment"))
    rows = rigSets.check("prop", top)
    body = [r for r in rows if r["key"] == "body"][0]
    check("tool flags it as misnamed", body["wrong"] == "body_controls_SET" and "rename" in body["status"])
    check("Build skips a misnamed set", rigSets.build_missing(rows) == [])
    rigSets.rename_set(body["wrong"], body["name"])
    check("after Rename: ready", rigSets.publish_check("prop", top) is None)
    rigSets.make_set("face_controls_SET", [])
    check("left-over face set reported on a prop", rigSets.wrong_kind_sets("prop") == ["face_controls_SET"])
    check("a left-over face set doesn't stop a prop publish", rigSets.publish_check("prop", top) is None)

    # --- character rig: unchanged rules ---------------------------------------
    top = grass_rig("character")
    rows = rigSets.check("character", top)
    check("character: cache_SET, body_controls_SET, optional face_controls_SET",
          [(r["name"], r["required"]) for r in rows] ==
          [("cache_SET", True), ("body_controls_SET", True), ("face_controls_SET", False)])
    rigSets.build_missing(rows)
    check("Build makes only the required ones", not cmds.objExists("face_controls_SET")
          and cmds.objExists("body_controls_SET"))
    check("character ready", rigSets.publish_check("character", top) is None)
    check("unknown type (None) still means character",
          api.check_control_sets([top])["body"] == "body_controls_SET")

    # --- hints in the right names ---------------------------------------------
    cmds.sets(empty=True, name="rig1_controllers_grp")
    check("mGear hint names controls_SET on a prop",
          "put it in controls_SET" in api._known_set_hints("prop")
          and "put it in body_controls_SET" in api._known_set_hints("character"))
    check("tool suggests the mGear set as the controls",
          rigSets.suggest_controls(top, "body", False) == ["rig1_controllers_grp"])

    # --- name clash -----------------------------------------------------------
    cmds.file(new=True, force=True)
    cmds.group(empty=True, name="cache_SET")
    try:
        rigSets.make_set("cache_SET", [])
        clash = False
    except RuntimeError:
        clash = True
    check("make_set refuses a name that's taken", clash and not cmds.ls("cache_SET1"))
finally:
    cmds.file(new=True, force=True)
    shutil.rmtree(base, ignore_errors=True)

print("%d/%d passed" % (sum(results), len(results)))
