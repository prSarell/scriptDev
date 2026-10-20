r"""Headless test: rig control sets (spec §4 "Rig sets: controls and render
geo", 2026-10-20).

    "C:\Program Files\Autodesk\Maya2025\bin\mayapy.exe" pipeDev/publishDev/test_rigControlSets_mayapy.py

A Scout-like rig (mGear sets + a MetaHuman face, laid out as in
scoutPrevis_rig_002): body_controls_SET (+ face_controls_SET) required, made
by the rigger; Publish gathers them with cache_SET in RMIT_publishSet; sets inside sets count; MetaHuman face
controls added automatically in the published file only. The MetaHuman DNA
node needs a plug-in, so its node type is swapped for "network" here.
Throwaway folders in %TEMP%; nothing real is touched.
"""
import os, sys, stat, shutil, tempfile

import maya.standalone
maya.standalone.initialize()
import maya.cmds as cmds

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import publishTool_api as api
import rig_rules

base = tempfile.mkdtemp(prefix="ctrlsets_")
results = []
MH = rig_rules.METAHUMAN
REAL_DNA_TYPE = MH["dna_node_type"]


def check(name, ok):
    results.append(bool(ok)); print(("PASS " if ok else "FAIL ") + name)


def refused(text, objects=()):
    try:
        api.check_control_sets(list(objects))
    except api.PublishError as e:
        if text not in str(e):
            print("    (message was: %s)" % str(e).splitlines()[0])
        return text in str(e)
    return False


FACE = ["CTRL_C_jaw", "CTRL_L_eye_blink", "CTRL_R_eye_blink", "CTRL_C_mouth"]
PRESS = ["CTRL_L_mouth_lipsPressD", "CTRL_R_mouth_lipsPressD"]


def scout(metahuman=True):
    """mGear-style body controls in rig1_controllers_grp, a MetaHuman face
    board under headGui_grp, the rigger's FacialControls set (leaving out
    the lipsPressD controls, as in the real rig), and a cache_SET."""
    cmds.file(new=True, force=True)
    root = cmds.group(empty=True, name="scout_rig")
    geo = cmds.polyCube(name="body_geo")[0]; cmds.parent(geo, root)
    body = []
    for name in ("global_C0_ctl", "body_C0_ctl", "arm_L0_fk0_ctl"):
        body.append(cmds.parent(cmds.circle(name=name)[0], root)[0])
    cmds.sets(body, name="rig1_controllers_grp")
    cmds.sets(["rig1_controllers_grp"], name="rig1_sets_grp")
    if metahuman:
        head = cmds.group(empty=True, name="headRig_grp", parent=root)
        gui = cmds.group(empty=True, name=MH["face_gui_group"], parent=head)
        for name in FACE + PRESS + MH["not_controls"]:
            cmds.group(empty=True, name=name, parent=gui)
        cmds.sets(FACE, name="FacialControls")
        cmds.createNode("network", name="head_dna")
    cmds.sets([geo], name=api.CACHE_SET)
    return root


def pipe_sets(face=None):
    """The sets a rigger makes: body = mGear's set dropped in, face = given."""
    cmds.sets(["rig1_controllers_grp"], name=api.BODY_CONTROLS_SET)
    if face is not None:
        cmds.sets(face, name=api.FACE_CONTROLS_SET) if face \
            else cmds.sets(empty=True, name=api.FACE_CONTROLS_SET)


MH["dna_node_type"] = "network"      # stands in for embeddedNodeRL4

# --- refusals, with messages that say what to do
scout()
check("no control sets -> refused", refused("has no body_controls_SET"))
check("message says how, and names mGear's set and FacialControls",
      refused("rig1_controllers_grp: mGear's controllers set: put it in body_controls_SET")
      and refused("FacialControls: looks like face controls"))
check("message says Publish makes RMIT_publishSet", refused("Publish puts them in RMIT_publishSet"))
cmds.sets(empty=True, name=api.BODY_CONTROLS_SET)
check("empty body_controls_SET -> refused", refused("has no controls in it"))

# --- a rig with no face: face set optional
scout(metahuman=False)
pipe_sets()
r = api.check_control_sets([])
check("non-MetaHuman rig, no face set -> accepted", r["face"] is None and r["metahuman_count"] == 0)
check("body controls found through mGear's nested set",
      sorted(c.split("|")[-1] for c in api.set_controls(r["body"]))
      == ["arm_L0_fk0_ctl", "body_C0_ctl", "global_C0_ctl"])
check("every nested set goes with the export",
      sorted(r["sets"]) == ["body_controls_SET", "rig1_controllers_grp"])
scout(metahuman=False)
pipe_sets(face=[])
check("non-MetaHuman rig with an empty face set -> refused", refused("face_controls_SET is empty"))

# --- MetaHuman: face set required, filled automatically
scout()
pipe_sets()
check("MetaHuman rig without face_controls_SET -> refused", refused("This is a MetaHuman rig"))
scout()
pipe_sets(face=[])
r = api.check_control_sets([])
check("MetaHuman face controls found: CTRL_ under headGui_grp minus board/utility nodes",
      r["metahuman_count"] == len(FACE) + len(PRESS)
      and not any(c.split("|")[-1] in MH["not_controls"] for c in r["metahuman_missing"]))
check("empty face set: all of them will be added", len(r["metahuman_missing"]) == 6)
scout()
pipe_sets(face=["FacialControls"])
r = api.check_control_sets([])
check("rigger's FacialControls inside: only the lipsPressD pair is added",
      sorted(c.split("|")[-1] for c in r["metahuman_missing"]) == sorted(PRESS))
cmds.rename("headGui_grp", "faceBoard_grp")
check("MetaHuman renamed things -> refused, says update rig_rules.py", refused("update rig_rules.py"))
cmds.rename("faceBoard_grp", "headGui_grp")

# --- other cases
cmds.namespace(add="extra"); cmds.sets(empty=True, name="extra:body_controls_SET")
check("two body_controls_SETs -> refused", refused("more than one body_controls_SET"))
cmds.delete("extra:body_controls_SET")
outside = cmds.circle(name="stray_ctl")[0]
cmds.sets([outside], add="rig1_controllers_grp")
check("controls outside the published objects -> refused",
      refused("aren't in this publish", objects=["scout_rig"]))
cmds.sets([outside], remove="rig1_controllers_grp")
check("publishing the rig root -> accepted", api.check_control_sets(["scout_rig"])["face"] == "face_controls_SET")

# --- export: sets travel with the rig; MetaHuman controls added in the file only;
# Publish makes RMIT_publishSet holding the pipe's sets
r = api.check_control_sets(["scout_rig"])
dest = os.path.join(base, "scout_scout_rig_v001.ma")
plan = {"dest": dest, "h_folder": base, "ext": ".ma",
        "set_uuids": cmds.ls(["cache_SET"] + r["sets"], uuid=True)}
before = sorted(cmds.sets("face_controls_SET", query=True))
with api._AddedToSet(r["face"], r["metahuman_missing"]), \
        api._PublishSet(plan, ["cache_SET", r["body"], r["face"]]):
    api.export_to_h_drive(["scout_rig"], plan)
check("working scene's face set unchanged afterwards",
      sorted(cmds.sets("face_controls_SET", query=True)) == before)
check("working scene: no RMIT_publishSet left behind", not cmds.objExists(api.PUBLISH_SET))
cmds.file(new=True, force=True)
cmds.file(dest, open=True, force=True)
check("published file has RMIT_publishSet > cache_SET + body_controls_SET + face_controls_SET",
      sorted(cmds.sets(api.PUBLISH_SET, query=True)) == ["body_controls_SET", "cache_SET", "face_controls_SET"])
check("mGear's set still nested in body_controls_SET",
      cmds.sets("body_controls_SET", query=True) == ["rig1_controllers_grp"])
face = sorted(n.split("|")[-1] for n in api.set_controls("face_controls_SET"))
check("published face set: rigger's set + the added lipsPressD pair = all 6 face controls",
      face == sorted(FACE + PRESS))
check("cache_SET still there", cmds.objExists("cache_SET"))

# --- the rigger already made an RMIT_publishSet (with something extra in it):
# the published one holds just the pipe's sets; the scene's is put back
scout(); pipe_sets(face=["FacialControls"])
cmds.sets(["cache_SET", "rig1_sets_grp"], name=api.PUBLISH_SET)
r = api.check_control_sets(["scout_rig"])
dest = os.path.join(base, "scout_scout_rig_v002.ma")
plan = {"dest": dest, "h_folder": base, "ext": ".ma",
        "set_uuids": cmds.ls(["cache_SET"] + r["sets"], uuid=True)}
with api._PublishSet(plan, ["cache_SET", r["body"], r["face"]]):
    api.export_to_h_drive(["scout_rig"], plan)
check("rigger's own RMIT_publishSet put back as it was",
      sorted(cmds.sets(api.PUBLISH_SET, query=True)) == ["cache_SET", "rig1_sets_grp"])
cmds.file(new=True, force=True)
cmds.file(dest, open=True, force=True)
check("published RMIT_publishSet: only the pipe's sets, one of it",
      sorted(cmds.sets(api.PUBLISH_SET, query=True)) == ["body_controls_SET", "cache_SET", "face_controls_SET"]
      and len(cmds.ls(api.PUBLISH_SET + "*", type="objectSet")) == 1)

# --- publish() refuses before anything is written or uploaded
api.plan_publish = lambda *a, **k: {"dest": os.path.join(base, "never.ma"), "h_folder": base,
                                     "ext": ".ma"}
calls = []
api.find_shotgrid_asset = lambda *a: calls.append("shotgrid")
api.playblast_frames = lambda *a, **k: calls.append("playblast")
api.check_script_nodes = lambda: None
scout()
try:
    api.publish("x.ma", base, base, "rig")
    check("publish() refuses a rig with no control sets", False)
except api.PublishError as e:
    check("publish() refuses a rig with no control sets", "body_controls_SET" in str(e))
check("refused before ShotGrid or playblast", calls == [])

MH["dna_node_type"] = REAL_DNA_TYPE
check("real rule: no MetaHuman plug-in/DNA here -> not a MetaHuman", api.metahuman_face_controls() is None)

print("\n%d/%d passed" % (sum(results), len(results)))
for root, dirs, files in os.walk(base):
    for f in files:
        os.chmod(os.path.join(root, f), stat.S_IWRITE)
shutil.rmtree(base, ignore_errors=True)
maya.standalone.uninitialize()
