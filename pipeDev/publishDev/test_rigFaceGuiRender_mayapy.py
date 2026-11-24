r"""Headless test: a rig publish sets a MetaHuman face board's meshes not to
render (user, 2026-11-24).

    "C:\Program Files\Autodesk\Maya2027\bin\mayapy.exe" pipeDev/publishDev/test_rigFaceGuiRender_mayapy.py

The meshes under headGui_grp (frames, sliders, text) render by default.
In the published file their render stats are off; the body geo is left
alone, and the working scene ends as it was (locks included). A stat
driven by a connection is left as it is, with a warning. Throwaway folders
in %TEMP%; nothing real is touched.
"""
import os, sys, stat, shutil, tempfile

import maya.standalone
maya.standalone.initialize()
import maya.cmds as cmds
try:
    cmds.loadPlugin("mtoa", quiet=True)     # for the Arnold visibility checks
except RuntimeError:
    pass

DEV = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(DEV, "publishDev"), os.path.join(DEV, "buildDev")]
import publishTool_api as api
import publishTool_textures as tex
import pipeEnv

base = tempfile.mkdtemp(prefix="riggui_")
H, S = os.path.join(base, "H"), os.path.join(base, "S")
FILM = "NWF_SHF"
_cfg = os.path.join(base, "pipeline_config.json")
api._config_path = lambda: _cfg
api.set_root(api.H_DRIVE, H)
api.set_root(api.SCRATCH, S)
api.save_config(dict(api.load_config(), publish_as="scout"))
api.artist_name = lambda login: "Scout Test"
os.environ.pop(pipeEnv.VAR, None)
results = []
STATS = ("primaryVisibility", "castsShadows", "receiveShadows",
         "visibleInReflections", "visibleInRefractions")


def check(name, ok):
    results.append(bool(ok)); print(("PASS " if ok else "FAIL ") + name)


asset_s = os.path.join(S, FILM, "maya", "assets", "character", "scout")
os.makedirs(os.path.join(H, FILM, "maya", "assets", "character", "scout", "scenes"))
os.makedirs(os.path.join(asset_s, "scenes")); open(os.path.join(asset_s, "workspace.mel"), "w").write("")


def rig_scene():
    cmds.file(new=True, force=True)
    cmds.workspace(asset_s, openWorkspace=True)
    root = cmds.group(empty=True, name="scout_rig")
    geo = cmds.parent(cmds.polyCube(name="body_geo")[0], root)[0]
    ctl = cmds.parent(cmds.circle(name="root_ctl")[0], root)[0]
    gui = cmds.group(empty=True, name="headGui_grp", parent=root)
    frame = cmds.parent(cmds.polyPlane(name="FRM_faceGUI")[0], gui)[0]
    text = cmds.parent(cmds.polyPlane(name="TEXT_mouth")[0], frame)[0]
    slider = cmds.parent(cmds.polyPlane(name="CTRL_C_mouth")[0], frame)[0]
    cmds.setAttr("TEXT_mouthShape.primaryVisibility", lock=True)      # locked: still turned off
    driver = cmds.createNode("network", name="driver")
    cmds.addAttr(driver, longName="on", attributeType="bool", defaultValue=True)
    cmds.connectAttr(driver + ".on", "CTRL_C_mouthShape.castsShadows")  # driven: left alone
    cmds.sets([geo], name=api.CACHE_SET)
    cmds.sets([ctl], name=api.BODY_CONTROLS_SET)
    scene = os.path.join(asset_s, "scenes", "rig_work.ma")
    cmds.file(rename=scene); cmds.file(save=True, type="mayaAscii")
    return scene


def stats(shape):
    return [cmds.getAttr("%s.%s" % (shape, a)) for a in STATS]


scene = rig_scene()
gui_shapes = ["FRM_faceGUIShape", "TEXT_mouthShape", "CTRL_C_mouthShape"]
check("face board meshes found under headGui_grp (body geo not among them)",
      sorted(s.split("|")[-1] for s in api.metahuman_face_gui_geo(["scout_rig"])) == sorted(gui_shapes))
check("a face board outside the selection isn't touched",
      api.metahuman_face_gui_geo(["|scout_rig|body_geo"]) == [])
before = dict((s, stats(s)) for s in gui_shapes + ["body_geoShape"])

plan = api.plan_publish(scene, H, S, "rig")
plan.update(objects=["scout_rig"], sg_asset={"type": "Asset", "id": 99}, cache_set=api.CACHE_SET,
            control_sets={"body": api.BODY_CONTROLS_SET, "face": None})
plan["set_uuids"] = cmds.ls([api.CACHE_SET, api.BODY_CONTROLS_SET], uuid=True)
api.export_rig_to_h_drive(["scout_rig"], plan, scene, tex.collect(["scout_rig"]), tex.collect_dna())
print("   ", plan.get("warnings"))

check("working scene as it was (render stats and the lock)",
      dict((s, stats(s)) for s in before) == before
      and cmds.getAttr("TEXT_mouthShape.primaryVisibility", lock=True))
check("plan counts 3 face board meshes", plan.get("face_gui_not_renderable") == 3)
check("warning names the driven stat",
      any("CTRL_C_mouthShape.castsShadows" in w for w in plan.get("warnings", [])))

cmds.file(new=True, force=True)
cmds.file(plan["dest"], open=True, force=True)
G = "|scout_rig_GRP|scout_rig"
frame = G + "|headGui_grp|FRM_faceGUI|FRM_faceGUIShape"
text = G + "|headGui_grp|FRM_faceGUI|TEXT_mouth|TEXT_mouthShape"
slider = G + "|headGui_grp|FRM_faceGUI|CTRL_C_mouth|CTRL_C_mouthShape"
check("published: face board frame doesn't render", not any(stats(frame)))
check("published: locked text mesh doesn't render, and is locked again",
      not any(stats(text)) and cmds.getAttr(text + ".primaryVisibility", lock=True))
check("published: driven castsShadows left on, the rest off",
      stats(slider) == [False, True, False, False, False])
arnold = [a for a in api.NOT_RENDERABLE if a.startswith("ai")
          and cmds.attributeQuery(a, node=frame, exists=True)]
check("published: Arnold visibility off too (where MtoA is loaded)",
      not any(cmds.getAttr(frame + "." + a) for a in arnold))
check("published: body geo still renders", all(stats(G + "|body_geo|body_geoShape")))
check("published: still visible in the viewport", cmds.getAttr(frame + ".visibility"))
check("stamp: faceGuiNotRenderable = 3",
      cmds.getAttr("|scout_rig_GRP." + api.PIPE_ATTR_PREFIX + "faceGuiNotRenderable") == 3)

print("\n%d/%d passed" % (sum(results), len(results)))
for root, dirs, files in os.walk(base):
    for f in files:
        os.chmod(os.path.join(root, f), stat.S_IWRITE)
shutil.rmtree(base, ignore_errors=True)
maya.standalone.uninitialize()
