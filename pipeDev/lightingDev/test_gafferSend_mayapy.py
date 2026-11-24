r"""Headless test: Send to Gaffer (gafferSend.py, user 2026-11-24).

    "C:\Program Files\Autodesk\Maya2027\bin\mayapy.exe" pipeDev/lightingDev/test_gafferSend_mayapy.py

Folders and versions, the _latest pointer, the launcher and startup stubs,
and (when Gaffer is found on this computer) Gaffer itself: the student's
first Gaffer file, reading the send through ${PIPE_SCRATCH} from another
drive, and a batch Arnold render with `gaffer execute`. Gaffer is looked for
in GAFFER_TEST_ROOT or Documents\maya\gaffer, the Arnold SDK in
ARNOLD_TEST_ROOT or Documents\maya\Arnold-*. Arnold shaders only export in
the Maya GUI, so they aren't checked here (hand test).
Throwaway folders in %TEMP%; nothing real is touched.
"""
import glob
import re
import os
import shutil
import stat
import subprocess
import sys
import tempfile

import maya.standalone
maya.standalone.initialize()
import maya.cmds as cmds

DEV = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(DEV)
sys.path[:0] = [os.path.join(DEV, "lightingDev"), os.path.join(DEV, "publishDev"),
                os.path.join(DEV, "buildDev"), os.path.join(REPO, "modelDev")]
import publishTool_api as pub
import gafferSend as gs

base = tempfile.mkdtemp(prefix="gafferSend_")
S = os.path.join(base, "S")
FILM = "NWF_SHF"
_cfg = os.path.join(base, "pipeline_config.json")
pub._config_path = lambda: _cfg
pub.save_config({pub.SCRATCH: S, "publish_as": "e131988"})
HOME = os.path.join(base, "gafferHome")          # launcher + stubs go here, not the real one
gs.gaffer_home = lambda gaffer: HOME
results = []


def check(name, ok):
    results.append(bool(ok)); print(("PASS " if ok else "FAIL ") + name)


home_docs = os.path.join(os.path.expanduser("~"), "Documents", "maya")
GAFFER = gs.find_gaffer(os.environ.get("GAFFER_TEST_ROOT") or os.path.join(home_docs, "gaffer"))
sdks = [p for p in ([os.environ.get("ARNOLD_TEST_ROOT", "")] +
                    sorted(glob.glob(os.path.join(home_docs, "Arnold-*")))) if gs.is_arnold_sdk(p)]
ARNOLD = sdks[-1] if sdks else None
print("    Gaffer: %s\n    Arnold SDK: %s %s" % (GAFFER, ARNOLD, gs.arnold_version(ARNOLD)))

shot = os.path.join(S, FILM, "maya", "sequences", "SEQ010", "SEQ010_140")
work = os.path.join(shot, "scenes", "lighting", "e131988")
os.makedirs(work)
open(os.path.join(shot, "workspace.mel"), "w").write("")
SHED_USD = os.path.join(S, FILM, "maya", "publish", "assets", "prop", "shed", "scenes", "model",
                        "e131988", "shed_e131988_model_v001_exports", "shed_e131988_model_v001.usda")
os.makedirs(os.path.dirname(SHED_USD))
open(SHED_USD, "w").write('#usda 1.0\n(\n    defaultPrim = "shed"\n    metersPerUnit = 0.01\n'
                          '    upAxis = "Y"\n)\n\ndef Xform "shed" (\n    kind = "component"\n)\n'
                          '{\n    def Cube "roof_GEO"\n    {\n        double size = 2\n    }\n}\n')


def scene():
    cmds.file(new=True, force=True)
    cmds.playbackOptions(minTime=1, maxTime=5)
    grp = cmds.group(empty=True, name="set_GRP")
    box = cmds.parent(cmds.polyCube(name="box_GEO")[0], grp)[0]
    cmds.parent(cmds.circle(name="root_ctl")[0], grp)       # a rig control: not sent
    cmds.setKeyframe(box, attribute="ty", time=1, value=0)
    cmds.setKeyframe(box, attribute="ty", time=5, value=10)
    # A Build camera: keys on camera1_DATA, driven by a connection (not keys).
    cam = cmds.camera(name="camera1")[0]
    data = cmds.createNode("transform", name="camera1_DATA")
    cmds.setKeyframe(data, attribute="tz", time=1, value=20)
    cmds.setKeyframe(data, attribute="tz", time=5, value=40)
    cmds.connectAttr(data + ".tz", cam + ".tz")
    light = cmds.pointLight(name="key_LGT")
    light = cmds.listRelatives(light, parent=True)[0] if cmds.nodeType(light) != "transform" else light
    loc = cmds.spaceLocator(name="empty_LOC")[0]
    # A model Build loaded as a USD stage (spec §4h), placed in the set.
    cmds.loadPlugin("mayaUsdPlugin", quiet=True)
    stage_t = cmds.createNode("transform", name="shed_USD", parent=grp)
    stage = cmds.createNode("mayaUsdProxyShape", name="shed_USDShape", parent=stage_t)
    os.environ["PIPE_SCRATCH"] = S.replace("\\", "/")     # as Build writes it
    cmds.setAttr(stage + ".filePath", "$PIPE_SCRATCH/" + os.path.relpath(SHED_USD, S).replace("\\", "/"),
                 type="string")
    cmds.setAttr(stage_t + ".tx", 7)
    path = os.path.join(work, "SEQ010_140_light_001.ma")
    cmds.file(rename=path); cmds.file(save=True, type="mayaAscii")
    return grp, cam, light, loc


grp, cam, light, loc = scene()

# --- where things go ---------------------------------------------------------
folder, from_maya, name = gs.target()
check("target: <film>\\gaffer\\sequences\\<seq>\\<shot>\\<login>, fromMaya inside",
      os.path.normcase(folder) == os.path.normcase(os.path.join(
          S, FILM, "gaffer", "sequences", "SEQ010", "SEQ010_140", "e131988"))
      and os.path.basename(from_maya) == "fromMaya" and name == "SEQ010_140")
check("var path: ${PIPE_SCRATCH}/NWF_SHF/gaffer/...",
      gs.var_path(os.path.join(folder, "x.usda")).startswith("${PIPE_SCRATCH}/NWF_SHF/gaffer/"))
roots, skipped = gs.picked([grp, cam, light, loc])
check("picked: geometry, camera and light go; a bare locator is left out with why",
      sorted(r.split("|")[-1] for r in roots) == sorted([grp, cam, light])
      and [s[0].split("|")[-1] for s in skipped] == [loc])
check("picked: a mesh picked under a picked group isn't sent twice",
      [r.split("|")[-1] for r in gs.picked([grp, "box_GEO"])[0]] == ["set_GRP"])
try:
    gs.target(os.path.join(base, "loose.ma")); refused = False
except gs.SendError:
    refused = True
check("a scene outside the film folders is refused", refused)

# --- versions ----------------------------------------------------------------
os.makedirs(from_maya)
for n in ("SEQ010_140_v001.usd", "SEQ010_140_v007.usd", "other_v009.usd"):
    open(os.path.join(from_maya, n), "w").write("")
check("next send: past the highest of this shot's versions",
      os.path.basename(gs.next_usd(from_maya, name)) == "SEQ010_140_v008.usd")
shutil.rmtree(from_maya)
check("settings: Gaffer folder found inside its home folder",
      GAFFER is None or gs.find_gaffer(os.path.dirname(GAFFER)) == GAFFER)
check("MtoA's own Arnold isn't taken as an SDK (no include\\ai_version.h)",
      not gs.is_arnold_sdk(r"C:\Program Files\Autodesk\Arnold\maya2027"))

if not GAFFER:
    print("SKIP: Gaffer not found on this computer, the rest needs it")
else:
    pub.save_config(dict(pub.load_config(), gaffer_root=GAFFER, arnold_root=ARNOLD or ""))
    # --- first send ---------------------------------------------------------
    r1 = gs.send(roots, open_gaffer=False)
    check("first send: v001.usd, the _latest pointer and a new Gaffer file v001",
          os.path.basename(r1["usd"]) == "SEQ010_140_v001.usd" and os.path.isfile(r1["usd"])
          and os.path.basename(r1["latest"]) == "SEQ010_140_latest.usda" and r1["made"]
          and os.path.basename(r1["gfr"]) == "SEQ010_140_v001.gfr" and os.path.isfile(r1["gfr"]))
    text = open(r1["latest"]).read()
    check("_latest sublayers the send by a relative path, with the frame range",
          "@./SEQ010_140_v001.usd@" in text and "startTimeCode = 1" in text
          and "endTimeCode = 5" in text)
    launcher = open(gs.launcher_path(GAFFER)).read()
    check("launcher: clears Maya's PYTHONPATH/PXR paths, sets ARNOLD_ROOT and the stubs",
          "set PYTHONPATH=" in launcher and "set PXR_PLUGINPATH_NAME=" in launcher
          and ("ARNOLD_ROOT=%s" % ARNOLD in launcher if ARNOLD else True)
          and "pipeStartup" in launcher)
    check("startup stubs for gui, execute and dispatch, and the module copy",
          all(os.path.isfile(os.path.join(HOME, "pipeStartup", a, "pipe.py"))
              for a in ("gui", "execute", "dispatch"))
          and os.path.isfile(os.path.join(HOME, "pipeStartup", "python", "gafferPipeStartup.py")))
    from pxr import Sdf
    sent = Sdf.Layer.OpenAsAnonymous(r1["usd"]).ExportToString()
    refs = re.findall(r"references = @([^@]+)@", sent)
    print("    stage refs:", refs, r1["stages"])
    check("USD stage: referenced (not copied) by a relative path only, once",
          len(refs) == 1 and refs[0].startswith("../")
          and refs[0].endswith("shed_e131988_model_v001.usda")
          and os.path.isfile(os.path.normpath(os.path.join(os.path.dirname(r1["usd"]), refs[0])))
          and S not in sent and S.replace("\\", "/") not in sent)
    check("rig controls (NURBS curves) aren't sent as curves", "Curves \"" not in sent)
    gfr_text = open(r1["gfr"]).read()
    check("Gaffer file reads the send through ${PIPE_SCRATCH}, no drive letter",
          "${PIPE_SCRATCH}/NWF_SHF/gaffer/sequences/SEQ010/SEQ010_140/e131988/fromMaya/"
          "SEQ010_140_latest.usda" in gfr_text and S.replace("\\", "/") not in gfr_text)

    # --- the Gaffer file opens on another drive ------------------------------
    S2 = os.path.join(base, "S2")
    shutil.copytree(os.path.join(S, FILM), os.path.join(S2, FILM))
    moved = r1["gfr"].replace(S, S2)
    probe = os.path.join(base, "probe.py")
    open(probe, "w").write(
        "import sys, Gaffer, GafferScene, imath\n"
        "sys.path.insert(0, %r)\n"
        "import gafferPipeStartup\n"
        "s = Gaffer.ScriptNode(); s['fileName'].setValue(argv[0]); s.load()\n"
        "print('ROOT', gafferPipeStartup.set_from_script(s))\n"
        "out = s['fromMaya']['out']\n"
        "with Gaffer.Context(s.context()) as c:\n"
        "    print('KIDS', sorted(str(k) for k in out.childNames('/')))\n"
        "    c.setFrame(5)\n"
        "    print('CAMZ', out.fullTransform('/%s').translation().z)\n"
        "    print('BOXY', out.fullTransform('/set_GRP/box_GEO').translation().y)\n"
        "    print('SHED', out.fullTransform('/set_GRP/shed_USD/shed/roof_GEO').translation().x)\n"
        "print('RANGE', s['frameRange']['start'].getValue(), s['frameRange']['end'].getValue())\n"
        % (os.path.join(HOME, "pipeStartup", "python"), cam))
    out = subprocess.run([gs.launcher_path(GAFFER), "python", probe, "-arguments", moved],
                         env=gs.clean_env(), capture_output=True, text=True, timeout=300)
    lines = dict(l.split(" ", 1) for l in out.stdout.splitlines() if l[:4] in ("ROOT", "KIDS", "CAMZ", "BOXY", "RANG", "SHED"))
    print("   ", lines or out.stderr[-800:])
    check("on another drive: PIPE_SCRATCH follows the file, the send loads",
          os.path.normcase(lines.get("ROOT", "")) == os.path.normcase(base.replace("\\", "/") + "/S2")
          and "set_GRP" in lines.get("KIDS", "") and cam in lines.get("KIDS", ""))
    check("animation came through: box at y 10, Build-style driven camera at z 40 (frame 5)",
          abs(float(lines.get("BOXY", "0")) - 10) < 1e-3
          and abs(float(lines.get("CAMZ", "0")) - 40) < 1e-3)
    check("Gaffer file's frame range is the timeline", lines.get("RANGE") == "1 5")
    check("USD stage in Gaffer on the other drive: its geometry, where Maya put it (x 7)",
          abs(float(lines.get("SHED", "0")) - 7) < 1e-3)

    # --- carry on / start again ---------------------------------------------
    cmds.setKeyframe("box_GEO", attribute="ty", time=5, value=3)
    r2 = gs.send(roots, open_gaffer=False)
    check("carry on: v002.usd, same Gaffer file, _latest points at v002, v001 kept",
          os.path.basename(r2["usd"]) == "SEQ010_140_v002.usd" and not r2["made"]
          and r2["gfr"] == r1["gfr"] and "@./SEQ010_140_v002.usd@" in open(r2["latest"]).read()
          and os.path.isfile(r1["usd"]))
    r3 = gs.send(roots, start_again=True, open_gaffer=False)
    check("start again: a new Gaffer file v002, v001 kept",
          os.path.basename(r3["gfr"]) == "SEQ010_140_v002.gfr" and r3["made"]
          and os.path.isfile(r1["gfr"]))

    # --- a batch render through the launcher (execute app + stub) -------------
    if ARNOLD:
        ex = subprocess.run([gs.launcher_path(GAFFER), "execute", "-script", r3["gfr"],
                             "-nodes", "ArnoldRender", "-frames", "1"],
                            env=gs.clean_env(), capture_output=True, text=True, timeout=600)
        frames = glob.glob(os.path.join(folder, "renders", "SEQ010_140_v002", "beauty", "*.exr"))
        print("   ", frames or (ex.stdout + ex.stderr)[-1200:])
        check("gaffer execute renders frame 1 into <login>\\renders\\<gaffer file>\\beauty",
              len(frames) == 1)
    else:
        print("SKIP: no Arnold SDK, no batch render")

print("\n%d/%d passed" % (sum(results), len(results)))
for root, dirs, files in os.walk(base):
    for f in files:
        os.chmod(os.path.join(root, f), stat.S_IWRITE)
print("KEPT", base) if os.environ.get("KEEP_TEST") else shutil.rmtree(base, ignore_errors=True)
os._exit(0 if all(results) else 1)
