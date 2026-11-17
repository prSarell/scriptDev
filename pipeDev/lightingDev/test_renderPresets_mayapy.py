# Render presets (user, 2026-11-17): save one shot's Arnold settings, AOVs
# and lights as a named preset, apply it in any other shot of the film.
# Builds a lit shot in a throwaway film folder, saves it, then applies it to
# a second shot and checks everything came across.
# Run: mayapy test_renderPresets_mayapy.py
import sys, os, json, shutil, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
for sub in ("", "../publishDev", "../buildDev"):
    sys.path.insert(0, os.path.normpath(os.path.join(HERE, sub)))
import maya.standalone; maya.standalone.initialize()
import maya.cmds as cmds
import renderPresets_api as rp
ok = []
def check(label, cond): ok.append(bool(cond)); print("PASS" if cond else "FAIL", label)
def close(a, b, tol=1e-4): return all(abs(x - y) < tol for x, y in zip(a, b))
def matrix(node): return cmds.xform(node, q=True, worldSpace=True, matrix=True)

scratch = tempfile.mkdtemp(prefix="rp_scratch_")
def shot(name):
    folder = os.path.join(scratch, "RPT_TST", "maya", "sequences", "SEQ010", name)
    os.makedirs(os.path.join(folder, "scenes", "lighting", "tester"))
    cmds.workspace(folder, openWorkspace=True)
    return os.path.join(folder, "scenes", "lighting", "tester", "light_001.ma")

# --- shot A: the look to save ---------------------------------------------------
cmds.file(new=True, force=True)
scene_a = shot("SEQ010_010")
cmds.file(rename=scene_a); cmds.file(save=True, type="mayaAscii")
rp.ensure_arnold()
cmds.setAttr("defaultArnoldRenderOptions.AA_samples", 7)
cmds.setAttr("defaultArnoldRenderOptions.GI_diffuse_samples", 4)
cmds.setAttr("defaultArnoldRenderOptions.GI_diffuse_depth", 3)
cmds.setAttr("defaultArnoldDriver.exrCompression", 2)
cmds.setAttr("defaultArnoldFilter.width", 2.5)
cmds.setAttr("defaultResolution.width", 1280); cmds.setAttr("defaultResolution.height", 720)
cmds.setAttr("defaultRenderGlobals.startFrame", 1); cmds.setAttr("defaultRenderGlobals.endFrame", 50)
cmds.setAttr("defaultRenderGlobals.preMel", "print('from shot A')", type="string")
aovs = rp._aov_interface(); aovs.addAOV("N", aovType="vector"); aovs.addAOV("Z", aovType="float")
cmds.setAttr(cmds.ls(type="aiAOV")[0] + ".enabled", 0)

rig = cmds.group(empty=True, name="lightRig")
cmds.xform(rig, translation=(0, 2, 0))
key = cmds.shadingNode("spotLight", asLight=True); key = cmds.rename(key, "key")
cmds.parent(key, rig)
cmds.xform("key", worldSpace=True, translation=(5, 6, 7), rotation=(-30, 45, 0))
cmds.setAttr("keyShape.intensity", 3.5); cmds.setAttr("keyShape.coneAngle", 55)
cmds.setAttr("keyShape.color", 1, 0.8, 0.6, type="double3"); cmds.setAttr("keyShape.aiExposure", 1.5)
barn = cmds.createNode("aiBarndoor", name="keyBarn"); cmds.setAttr(barn + ".barndoorTopLeft", 0.2)
cmds.connectAttr(barn + ".message", "keyShape.aiFilters[0]")
rim = cmds.shadingNode("aiAreaLight", asLight=True); rim = cmds.rename(rim, "rim")
cmds.xform("rim", worldSpace=True, translation=(-4, 3, -2), scale=(2, 2, 2))
rim_shape = cmds.listRelatives("rim", shapes=True)[0]
cmds.setAttr(rim_shape + ".aiSamples", 3); cmds.setAttr(rim_shape + ".aiSpread", 0.4)
cmds.setKeyframe(rim_shape, attribute="intensity", time=1, value=2.0)
cmds.setKeyframe(rim_shape, attribute="intensity", time=10, value=9.0)
cmds.currentTime(1)
sky = cmds.shadingNode("aiSkyDomeLight", asLight=True); sky = cmds.rename(sky, "sky")
sky_shape = cmds.listRelatives("sky", shapes=True)[0]
hdri = cmds.shadingNode("file", asTexture=True, name="skyHDRI")
cmds.setAttr(hdri + ".fileTextureName", "C:/hdri/studio_small.exr", type="string")
cmds.connectAttr(hdri + ".outColor", sky_shape + ".color")
cmds.setAttr(sky_shape + ".aiExposure", -0.5)
want = {"key": matrix("key"), "rim": matrix("rim"), "sky": matrix("sky")}

check("presets live in the film's renderPresets folder, shared by every shot",
      rp.preset_folder() == os.path.join(scratch, "RPT_TST", "maya", "renderPresets"))
check("names are cleaned like the camera presets", rp.clean_name(" look dev/001! ") == "look_dev001")
try:
    rp.save("  "); refused = False
except rp.PresetError:
    refused = True
check("a nameless preset is refused", refused)
path, saved = rp.save("lookdev 001")
check("saved as lookdev_001.json", os.path.basename(path) == "lookdev_001.json" and os.path.isfile(path))
check("the preset holds every light, with names and types",
      sorted((l["name"], l["type"]) for l in saved["lights"])
      == [("key", "spotLight"), ("rim", "aiAreaLight"), ("sky", "aiSkyDomeLight")])
check("Arnold settings are in it", saved["render"]["defaultArnoldRenderOptions"]["AASamples"] == 7
      and saved["render"]["defaultArnoldFilter"]["width"] == 2.5
      and len(saved["render"]["defaultArnoldRenderOptions"]) > 50)
check("the shot's frame range and image name are not",
      "startFrame" not in saved["render"]["defaultRenderGlobals"]
      and "imageFilePrefix" not in saved["render"]["defaultRenderGlobals"])
check("pre/post render scripts are never stored",
      not any(rp.SCRIPT_ATTR.search(a) for n in saved["render"].values() for a in n
              if isinstance(n[a], str)))
check("an animated setting is stored as its value now", next(
      l for l in saved["lights"] if l["name"] == "rim")["attrs"]["intensity"] == 2.0)
check("outputs aren't stored as settings", "outColorR" not in next(
      l for l in saved["lights"] if l["name"] == "rim")["attrs"])
check("the skydome's HDRI and the barndoor come with their lights",
      saved["inputs"]["skyHDRI"]["attrs"]["fileTextureName"] == "C:/hdri/studio_small.exr"
      and saved["inputs"]["keyBarn"]["type"] == "aiBarndoor")
check("describe says what's in it", rp.describe(saved).startswith("3 light(s), 2 AOV(s). Saved from light_001"))
rp.save("blocking_001")

# --- shot B: different lights, then the preset -------------------------------
cmds.file(new=True, force=True)
scene_b = shot("SEQ010_020")
cmds.file(rename=scene_b); cmds.file(save=True, type="mayaAscii")
check("another shot of the film sees the same presets",
      rp.list_presets() == ["blocking_001", "lookdev_001"])
rp.ensure_arnold()
cmds.setAttr("defaultRenderGlobals.startFrame", 1001)
rp._aov_interface().addAOV("diffuse", aovType="rgb")
old_key = cmds.rename(cmds.shadingNode("spotLight", asLight=True), "key")
cmds.xform(old_key, translation=(0, 0, 0))
cmds.setAttr("keyShape.intensity", 1)
fill = cmds.rename(cmds.shadingNode("pointLight", asLight=True), "fill_old")
cmds.undoInfo(state=True, infinity=True)
preset = rp.read_preset("lookdev_001")
check("lights the preset doesn't have are found (to ask about)",
      [rp._short(rp._transform(s)) for s in rp.extra_lights(preset)] == ["fill_old"])
counts = rp.apply(preset, remove_extra=False)
print("INFO", rp.summary(counts))
check("the existing key light is used, two lights are made",
      counts["lights_set"] == 1 and counts["lights_made"] == 2 and len(cmds.ls("key")) == 1)
check("every light is at its world-space position", all(close(matrix(n), m) for n, m in want.items()))
check("the key light's settings, Maya and Arnold", cmds.getAttr("keyShape.intensity") == 3.5
      and abs(cmds.getAttr("keyShape.coneAngle") - 55) < 1e-4 and cmds.getAttr("keyShape.aiExposure") == 1.5
      and close(cmds.getAttr("keyShape.color")[0], (1, 0.8, 0.6)))
new_rim = cmds.listRelatives("rim", shapes=True)[0]
check("the new area light has its settings and the animated value",
      cmds.nodeType(new_rim) == "aiAreaLight" and cmds.getAttr(new_rim + ".aiSamples") == 3
      and abs(cmds.getAttr(new_rim + ".aiSpread") - 0.4) < 1e-4 and cmds.getAttr(new_rim + ".intensity") == 2.0)
new_sky = cmds.listRelatives("sky", shapes=True)[0]
src = cmds.listConnections(new_sky + ".color", source=True, destination=False) or []
check("the skydome's HDRI is remade and connected",
      src and cmds.nodeType(src[0]) == "file"
      and cmds.getAttr(src[0] + ".fileTextureName") == "C:/hdri/studio_small.exr")
barns = cmds.listConnections("keyShape.aiFilters", source=True, destination=False) or []
check("the barndoor filter is remade and connected",
      barns and cmds.nodeType(barns[0]) == "aiBarndoor" and abs(cmds.getAttr(barns[0] + ".barndoorTopLeft") - 0.2) < 1e-4)
check("Arnold and resolution settings applied", cmds.getAttr("defaultArnoldRenderOptions.AA_samples") == 7
      and cmds.getAttr("defaultArnoldRenderOptions.GI_diffuse_depth") == 3
      and cmds.getAttr("defaultArnoldDriver.exrCompression") == 2 and cmds.getAttr("defaultResolution.width") == 1280)
check("this shot keeps its own frame range", cmds.getAttr("defaultRenderGlobals.startFrame") == 1001)
check("AOVs are the preset's (diffuse removed), with their settings",
      sorted(cmds.getAttr(n + ".name") for n in cmds.ls(type="aiAOV")) == ["N", "Z"]
      and sorted(cmds.getAttr(n + ".enabled") for n in cmds.ls(type="aiAOV")) == [False, True])
check("asked to keep them, extra lights stay", cmds.objExists("fill_old"))
again = rp.capture("check")
check("saving this shot now gives the same lights and settings back",
      again["render"] == preset["render"]
      and sorted(json.dumps(l["attrs"], sort_keys=True) for l in again["lights"] if l["name"] != "fill_old")
      == sorted(json.dumps(l["attrs"], sort_keys=True) for l in preset["lights"]))
cmds.undo()
check("one undo puts the shot back", not cmds.objExists("rim") and cmds.getAttr("keyShape.intensity") == 1
      and cmds.getAttr("defaultArnoldRenderOptions.AA_samples") != 7
      and sorted(cmds.getAttr(n + ".name") for n in cmds.ls(type="aiAOV")) == ["diffuse"])
counts = rp.apply(preset, remove_extra=True)
check("asked to remove them, extra lights go", not cmds.objExists("fill_old") and counts["lights_removed"] == 1)
twice = rp.apply(preset, remove_extra=True)
check("applying twice makes nothing new", twice["lights_made"] == 0 and twice["lights_set"] == 3
      and len(cmds.ls(type="file")) == 1 and len(cmds.ls(type="aiBarndoor")) == 1)

# --- outside a film folder: the project's data folder -----------------------
cmds.file(new=True, force=True)
loose = tempfile.mkdtemp(prefix="rp_project_")
cmds.workspace(loose, openWorkspace=True)
check("outside a film folder: the project's data\\renderPresets",
      rp.preset_folder("") == os.path.join(loose, "data", "renderPresets"))
rp.delete_preset("blocking_001", os.path.join(scratch, "RPT_TST", "maya", "renderPresets"))
check("delete removes the preset file",
      rp.list_presets(os.path.join(scratch, "RPT_TST", "maya", "renderPresets")) == ["lookdev_001"])

shutil.rmtree(scratch, ignore_errors=True); shutil.rmtree(loose, ignore_errors=True)
print("\n%d/%d passed" % (sum(ok), len(ok)))
