r"""Headless test for Build Shot's shared publish folder and PIPE_SCRATCH.

    "C:\Program Files\Autodesk\Maya2025\bin\mayapy.exe" pipeDev/buildDev/test_buildTool_mayapy.py

Works on throwaway folders in %TEMP% and a throwaway drive-settings file;
never touches the real H drive, scratch drive or Maya prefs. If the real
D:\NWF_SHF\...\shotSetup_002.ma exists, a COPY of it is used to check that
old in-shot references get repointed.

Covers spec §3i: "One shared publish folder on scratch", "Each version is
its own file", "Clearing old versions", "Reference paths that work on any
drive (PIPE_SCRATCH)", "Scratch drive follows the work".
Also covers spec §4 "Personal work folders" (2026-10-15): publishes in
scenes\<login>\ named <asset>_<login>_<code>_v###, per-person version
series, latest = newest by publish time across people, publish_as, and a
camera published by Publish's own code and built by Build Shot.
"""
import os, sys, json, stat, shutil, tempfile

import maya.standalone
maya.standalone.initialize()
import maya.cmds as cmds

DEV = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(DEV, "publishDev"), os.path.join(DEV, "buildDev")]
import buildTool_api as api

base = tempfile.mkdtemp(prefix="pubfolder_")
H, S = os.path.join(base, "H"), os.path.join(base, "S")
FILM = "NWF_SHF"
results = []

# Throwaway drive settings: never touch the real Maya prefs pipeline_config.json.
_cfg = os.path.join(base, "pipeline_config.json")
api.pub._config_path = lambda: _cfg
api.pub.set_root(api.pub.H_DRIVE, H)
api.pub.set_root(api.pub.SCRATCH, S)
import pipeEnv
os.environ.pop(pipeEnv.VAR, None)


def check(name, ok):
    results.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name)


# H drive publishes: v001 and v002 of the backpack by "anna", a locator
# "ctrl" in both. Publishes are personal: scenes\<login>\.
LOGIN = "anna"
scenes_h = os.path.join(H, FILM, "maya", "assets", "prop", "backpack", "scenes", LOGIN)
os.makedirs(scenes_h)
for v in (1, 2):
    cmds.file(new=True, force=True)
    cmds.polyCube(name="backPack_geo")
    cmds.spaceLocator(name="ctrl")
    if v == 2:
        cmds.polySphere(name="strap_geo")
    p = os.path.join(scenes_h, "backpack_%s_model_v%03d.ma" % (LOGIN, v))
    cmds.file(rename=p); cmds.file(save=True, type="mayaAscii")
    os.chmod(p, stat.S_IREAD)

shots = {}
for shot in ("EAP_010_010", "EAP_010_020", "EAP_010_030"):
    d = api.shot_folder(S, FILM, "EAP_010", shot)
    os.makedirs(os.path.join(d, "scenes"))
    open(os.path.join(d, "workspace.mel"), "w").write("")
    shots[shot] = d
maya_dir = os.path.join(S, FILM, "maya")
published = [p for p in api.list_published(H, FILM) if p["code"] == "model"][0]
V1, V2 = api.version_id(LOGIN, 1), api.version_id(LOGIN, 2)
check("listing keys versions by person", sorted(published["versions"]) == [V1, V2])
check("latest is the newest", published["latest"] == V2)
v1_local = os.path.join(maya_dir, "publish", "assets", "prop", "backpack", "scenes", LOGIN,
                        "backpack_%s_model_v001.ma" % LOGIN)
v2_local = v1_local.replace("v001", "v002")


def open_shot(shot, scene=None):
    cmds.file(new=True, force=True)
    api.ensure_maya_project(shots[shot])
    if scene:
        cmds.file(scene, open=True, force=True)


def ref_paths():
    return [os.path.normcase(os.path.normpath(r)) for _, _, _, r in api.scene_references()]


n = os.path.normcase

# --- shot 010 builds v1 and keys the control
open_shot("EAP_010_010")
done, warn, old = api.build_asset(shots["EAP_010_010"], published, V1)
check("010 v1 pulled into publish folder", os.path.isfile(v1_local))
check("publish copy is read-only", not os.access(v1_local, os.W_OK))
check("010 references the publish copy", ref_paths() == [n(v1_local)])
m = api.read_manifest(shots["EAP_010_010"])["prop/backpack/model"]
check("manifest records shared path + version + login", m["version"] == 1 and m["login"] == LOGIN
      and m["shared"].endswith("scenes/anna/backpack_anna_model_v001.ma"))
check("nothing copied into the shot's assets", not os.path.isdir(os.path.join(shots["EAP_010_010"], "assets", "prop")))
cmds.setKeyframe("backpack:ctrl.tx", time=1, value=0); cmds.setKeyframe("backpack:ctrl.tx", time=10, value=5)
s010 = os.path.join(shots["EAP_010_010"], "scenes", "shot010.ma")
cmds.file(rename=s010); cmds.file(save=True, type="mayaAscii")
done, warn, old = api.build_asset(shots["EAP_010_010"], published, V1)
check("rebuild same version: already up to date", done == ["already up to date"] and old is None)

# --- shot 020 builds v1, keys, then updates to v2
open_shot("EAP_010_020")
api.build_asset(shots["EAP_010_020"], published, V1)
cmds.setKeyframe("backpack:ctrl.ty", time=1, value=0); cmds.setKeyframe("backpack:ctrl.ty", time=20, value=3)
done, warn, old = api.build_asset(shots["EAP_010_020"], published, V2)
check("020 update switched reference to v2", ref_paths() == [n(v2_local)])
check("020 update reported", "scene reference switched to v002 (anna)" in done)
check("020 keys survived the switch", cmds.keyframe("backpack:ctrl.ty", query=True, keyframeCount=True) == 2)
check("020 sees new v2 content", cmds.objExists("backpack:strap_geo"))
check("old v1 reported as replaced", old and n(old) == n(v1_local))
check("v1 still used by 010 -> not offered for removal", api.unused_versions([old], maya_dir) == [])
check("v1 file still there for 010", os.path.isfile(v1_local))
s020 = os.path.join(shots["EAP_010_020"], "scenes", "shot020.ma")
cmds.file(rename=s020); cmds.file(save=True, type="mayaAscii")

# --- shot 010 still on v1 after 020's update
open_shot("EAP_010_010", s010)
check("010 still references v1", ref_paths() == [n(v1_local)])
check("010 keys intact", cmds.keyframe("backpack:ctrl.tx", query=True, keyframeCount=True) == 2)

# --- 010 updates too: v1 now unused
done, warn, old = api.build_asset(shots["EAP_010_010"], published, V2)
check("010 switched to v2", ref_paths() == [n(v2_local)])
check("010 keys survived", cmds.keyframe("backpack:ctrl.tx", query=True, keyframeCount=True) == 2)
check("v1 now unused by any shot", api.unused_versions([old], maya_dir) == [old])
os.chmod(v1_local, stat.S_IWRITE); os.remove(v1_local)   # (the UI sends it to the Recycle Bin)

# --- roll 010 back to v1: pulled again from H
done, warn, old = api.build_asset(shots["EAP_010_010"], published, V1)
check("rollback pulled v1 again", os.path.isfile(v1_local))
check("rollback switched reference to v1", ref_paths() == [n(v1_local)])
check("rollback: v2 still used by 020", api.unused_versions([old], maya_dir) == [])
cmds.file(save=True, type="mayaAscii")

# --- Repair: delete v1, reopen 010, repair pulls it back
os.chmod(v1_local, stat.S_IWRITE); os.remove(v1_local)
open_shot("EAP_010_010", s010)
fixed, not_fixed = api.repair_scene(H)
check("repair pulled v1 back", os.path.isfile(v1_local) and len(fixed) == 1 and not not_fixed)
check("repair loaded the reference", cmds.objExists("backpack:ctrl")
      and cmds.keyframe("backpack:ctrl.tx", query=True, keyframeCount=True) == 2)
fixed, not_fixed = api.repair_scene(H)
check("repair again: nothing to do", fixed == [] and not_fixed == [])

# --- Legacy: an old scene referencing a fixed-name copy inside the shot
shot30 = shots["EAP_010_030"]
legacy = os.path.join(shot30, "assets", "prop", "backpack", "backpack.ma")
os.makedirs(os.path.dirname(legacy))
shutil.copy2(os.path.join(scenes_h, "backpack_anna_model_v001.ma"), legacy)
os.chmod(legacy, stat.S_IWRITE)
open_shot("EAP_010_030")
cmds.file(legacy, reference=True, namespace="backpack")
cmds.setKeyframe("backpack:ctrl.tz", time=1, value=0); cmds.setKeyframe("backpack:ctrl.tz", time=5, value=2)
s030 = os.path.join(shot30, "scenes", "old.ma")
cmds.file(rename=s030); cmds.file(save=True, type="mayaAscii")
os.remove(legacy)       # what we did to EAP_010_010 on the real scratch drive
open_shot("EAP_010_030", s030)
fixed, not_fixed = api.repair_scene(H)
check("repair explains old in-shot copy", not fixed and len(not_fixed) == 1 and "Build Shot" in not_fixed[0])
done, warn, old = api.build_asset(shot30, published, V2)
check("build repoints legacy reference to publish v2", ref_paths() == [n(v2_local)])
check("legacy keys survived", cmds.keyframe("backpack:ctrl.tz", query=True, keyframeCount=True) == 2)
check("only one reference (not doubled)", len(api.scene_references()) == 1)

# --- Real-world legacy: a copy of the user's shotSetup_002.ma (relative
# reference to assets/prop/backpack/backpack.ma, file now deleted)
real = r"D:\NWF_SHF\maya\sequences\EAP_010\EAP_010_010\scenes\shotSetup_002.ma"
if os.path.isfile(real):
    shot10 = shots["EAP_010_010"]
    copy = os.path.join(shot10, "scenes", "shotSetup_002_copy.ma")
    shutil.copy2(real, copy)
    open_shot("EAP_010_010", copy)
    fixed, not_fixed = api.repair_scene(H)
    check("real scene: repair explains old copy", not fixed and len(not_fixed) == 1
          and "Build Shot" in not_fixed[0])
    print("   ", not_fixed)
    done, warn, old = api.build_asset(shot10, published, V2)
    print("   ", done)
    check("real scene: relative legacy reference repointed to v2",
          ref_paths() == [n(v2_local)] and len(api.scene_references()) == 1)
    check("real scene: backpack loaded", cmds.ls("backpack:*", type="mesh"))

# =========================================================================
# PIPE_SCRATCH
# =========================================================================
check("references are written with $PIPE_SCRATCH",
      all(w.startswith("$PIPE_SCRATCH/NWF_SHF/maya/publish/") for _, w, _, _ in api.scene_references()))
check("variable holds only the drive root", pipeEnv.current() == S.replace("\\", "/"))

# A reference written the old way (full path) is rewritten on rebuild.
open_shot("EAP_010_020")
cmds.file(v2_local, reference=True, namespace="backpack")
done, warn, old = api.build_asset(shots["EAP_010_020"], published, V2)
check("full-path reference rewritten to $PIPE_SCRATCH",
      "reference path made drive-independent" in done
      and api.scene_references()[0][1].startswith("$PIPE_SCRATCH/"))
check("still loaded after rewrite", cmds.objExists("backpack:strap_geo"))
cmds.setKeyframe("backpack:ctrl.ty", time=1, value=0); cmds.setKeyframe("backpack:ctrl.ty", time=20, value=3)
cmds.file(rename=s020); cmds.file(save=True, type="mayaAscii")

# Rebuild again: nothing to do.
done, warn, old = api.build_asset(shots["EAP_010_020"], published, V2)
check("rebuild after rewrite: already up to date", done == ["already up to date"])

# Install the startup callback, then move the whole film to another drive.
cid = pipeEnv.install()
check("install() keeps an existing value", pipeEnv.current() == S.replace("\\", "/"))
pipeEnv.install()   # twice: must not add a second callback
check("callback stored once", isinstance(getattr(sys, "_pipeEnv_callback_id", None), object))

S2 = os.path.join(base, "S2")
cmds.file(new=True, force=True)
shutil.copytree(os.path.join(S, FILM), os.path.join(S2, FILM))
for root, dirs, files in os.walk(S):
    for f in files:
        os.chmod(os.path.join(root, f), stat.S_IWRITE)
shutil.rmtree(S)
s020_b = s020.replace(S, S2)
cmds.file(s020_b, open=True, force=True)
check("callback pointed the variable at the new drive", pipeEnv.current() == S2.replace("\\", "/"))
check("shot opened from the new drive loads its reference", cmds.objExists("backpack:strap_geo"))
check("keys still there on the new drive",
      cmds.keyframe("backpack:ctrl.ty", query=True, keyframeCount=True) == 2)

# Opening a published file on the H drive must not move the variable.
cmds.file(os.path.join(scenes_h, "backpack_anna_model_v001.ma"), open=True, force=True)
check("opening an H-drive file leaves the variable alone", pipeEnv.current() == S2.replace("\\", "/"))

# Repair on the new drive: delete the v2 copy there, reopen, repair.
v2_b = v2_local.replace(S, S2)
os.chmod(v2_b, stat.S_IWRITE); os.remove(v2_b)
cmds.file(s020_b, open=True, force=True)
fixed, not_fixed = api.repair_scene(H)
check("repair on new drive pulls into the new drive", os.path.isfile(v2_b) and len(fixed) == 1)
check("repair keeps the $PIPE_SCRATCH path", api.scene_references()[0][1].startswith("$PIPE_SCRATCH/"))

# Repair with the variable missing (mpPipe not installed) explains it.
saved = os.environ.pop(pipeEnv.VAR)
fixed, not_fixed = api.repair_scene(H)
check("repair with no variable: nothing missing while loaded", True)
os.environ[pipeEnv.VAR] = saved

# =========================================================================
# Scratch drive follows the open scene (steps 1-3)
# =========================================================================
api.pub.set_root(api.pub.SCRATCH, S)        # saved setting still says the old drive
moved = api.pub.follow_open_scene(H, S)
check("step 1: tool follows the open scene's drive", moved and n(moved) == n(S2))
check("step 1: new drive saved as the setting", n(api.pub.get_root(api.pub.SCRATCH)) == n(S2))
check("step 1: no change when already there", api.pub.follow_open_scene(H, S2) is None)
cmds.file(new=True, force=True)
check("step 2: no scene open -> keep the saved setting", api.pub.follow_open_scene(H, S2) is None)
try:
    api.pub.check_roots(H, os.path.join(base, "not_here"))
    check("step 3: missing drive explained", False)
except api.BuildError as e:
    check("step 3: missing drive explained", "isn't on this machine" in str(e))
    print("   ", str(e).replace("\n", " | "))

# =========================================================================
# Installer userSetup block
# =========================================================================
sys.path.insert(0, os.path.join(DEV, "pipelineInstaller"))
import install as mp_install, uninstall as mp_uninstall
fake_scripts = os.path.join(base, "scripts"); os.makedirs(fake_scripts)
us = os.path.join(fake_scripts, "userSetup.py")
open(us, "w").write("# mpToolSet stuff\nprint('hello')\n")
mp_install._scripts_dir = lambda: fake_scripts.replace("\\", "/")
mp_install._patch_usersetup(); mp_install._patch_usersetup()   # twice: one block only
text = open(us).read()
check("userSetup: other lines kept", "print('hello')" in text)
check("userSetup: exactly one mpPipe block", text.count(mp_install._US_START) == 1)
exec(compile(text, us, "exec"), {})
check("userSetup block runs", pipeEnv.current() != "")
mp_uninstall._strip_usersetup(us)
text = open(us).read()
check("uninstall: block removed, rest kept", mp_install._US_START not in text and "print('hello')" in text)
check("uninstall: callback removed", not hasattr(sys, "_pipeEnv_callback_id"))
S = S2   # for the listing below

# =========================================================================
# Personal publishes (spec §4 "Personal work folders", 2026-10-15)
# =========================================================================
import time
pub = api.pub

# Who: the Windows login, unless publish_as overrides it (cleaned for file names).
check("who() is the Windows login by default", pub.who() == pub.clean_login(os.environ.get("USERNAME")))
pub.save_config(dict(pub.load_config(), publish_as="Ben.Smith"))
check("publish_as overrides, cleaned", pub.who() == "bensmith")

# A working file anywhere in the asset, called anything: the publish goes to
# the person's own folder, with their own version numbers.
wip = os.path.join(S, FILM, "maya", "assets", "prop", "backpack", "scenes", "my stuff", "Final FINAL 2.ma")
os.makedirs(os.path.dirname(wip))
cmds.file(new=True, force=True); cmds.polyCube(name="backPack_geo")
cmds.file(rename=wip); cmds.file(save=True, type="mayaAscii")
plan = pub.plan_publish(wip, H, S, "model")
check("ben's first publish is his v001, in his folder",
      plan["version"] == 1 and n(plan["dest"]) == n(os.path.join(
          H, FILM, "maya", "assets", "prop", "backpack", "scenes", "bensmith",
          "backpack_bensmith_model_v001.ma")))
pub.save_config(dict(pub.load_config(), publish_as=LOGIN))
check("anna's next publish is her v003", pub.plan_publish(wip, H, S, "model")["version"] == 3)
pub.save_config(dict(pub.load_config(), publish_as="bensmith"))

# Ben publishes after anna: his v001 is now the latest, by time.
time.sleep(1.5)
plan = pub.plan_publish(wip, H, S, "model")
pub.copy_to_h_drive(wip, plan)
published = [p for p in api.list_published(H, FILM) if p["code"] == "model"][0]
BEN1 = api.version_id("bensmith", 1)
check("both people's versions listed", sorted(published["versions"]) == [V1, V2, BEN1])
check("latest = newest by time, not highest number", published["latest"] == BEN1)
check("newest first in the version menu", api.sorted_versions(published)[0] == BEN1)
check("label says whose", api.version_label(published, BEN1) == "v001 (bensmith)  (latest)")
entry = api.read_manifest(shots["EAP_010_020"].replace(base + os.sep + "S", base + os.sep + "S2", 1)
                          )["prop/backpack/model"]
check("a shot on anna v002 sees ben's v001 as newer", api.newer_available(published, entry))
check("an old-style entry (no login) counts as older",
      api.newer_available(published, {"version": 9}))

# A file in the wrong person's folder, or named for another login, is ignored.
stray = os.path.join(H, FILM, "maya", "assets", "prop", "backpack", "scenes", LOGIN,
                     "backpack_bensmith_model_v007.ma")
shutil.copy2(wip, stray)
published = [p for p in api.list_published(H, FILM) if p["code"] == "model"][0]
check("file named for another login in anna's folder ignored",
      api.version_id("bensmith", 7) not in published["versions"])

# --- Camera: published by Publish's own code, built by Build Shot.
sys.path.insert(0, os.path.join(DEV, "publishDev"))
import publishTool_camera as pcam
os.makedirs(os.path.join(H, FILM, "maya", "sequences", "EAP_010", "EAP_010_010", "scenes"))
shot10 = os.path.join(S, FILM, "maya", "sequences", "EAP_010", "EAP_010_010")
layout = os.path.join(shot10, "scenes", "layout.ma")
cmds.file(new=True, force=True)
cmds.playbackOptions(minTime=1, maxTime=10)
cam_tr = cmds.camera(name="layoutCam")[0]
cmds.setKeyframe(cam_tr + ".tx", time=1, value=0); cmds.setKeyframe(cam_tr + ".tx", time=10, value=10)
cmds.file(rename=layout); cmds.file(save=True, type="mayaAscii")
cplan = pcam.plan_camera(layout, H, S, camera=cam_tr)
check("camera publish goes to the person's folder, login in the name",
      os.path.basename(cplan["dest"]) == "EAP_010_010_bensmith_cam_v001.ma"
      and os.path.basename(os.path.dirname(cplan["dest"])) == "bensmith")
pcam.export_camera(cam_tr, cplan, 1, 10, layout)
cams = api.list_shot_cameras(H, FILM, "EAP_010", "EAP_010_010")
check("Build lists the camera by person", cams and cams[0]["latest"] == BEN1)
cmds.file(new=True, force=True)
api.ensure_maya_project(shot10)
done, warn, old = api.build_asset(shot10, cams[0], BEN1)
check("camera built as camera1", cmds.objExists("|camera1") and
      "camera1 v001 (bensmith) imported and locked" in done)
check("camera1 stamped with who + version", api.shot_camera()[1] == BEN1)
cmds.currentTime(10)
check("camera1 keys play", abs(cmds.getAttr("camera1.tx") - 10) < 1e-3)
done, warn, old = api.build_asset(shot10, cams[0], BEN1)
check("camera rebuild: already up to date", done[-1] == "already up to date")
check("camera manifest records login",
      api.read_manifest(shot10)["camera/EAP_010_010/cam"]["login"] == "bensmith")

# --- scratch listing still works with shared entries
items = api.scratch_items(S, H, FILM)
check("scratch_items runs", isinstance(items, list))

print("\n%d/%d passed" % (sum(ok for _, ok in results), len(results)))
for root, dirs, files in os.walk(base):
    for f in files:
        os.chmod(os.path.join(root, f), stat.S_IWRITE)
shutil.rmtree(base, ignore_errors=True)
maya.standalone.uninitialize()
