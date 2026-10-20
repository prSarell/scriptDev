r"""Headless test for rigs as a fixed name per shot, hardlinked to a version
in the shared publish folder (spec §4a, option C, built 2026-10-20).

    "C:\Program Files\Autodesk\Maya2025\bin\mayapy.exe" pipeDev/buildDev/test_rigLink_mayapy.py

Works on throwaway folders in %TEMP% (NTFS, so hardlinks work) and a
throwaway drive-settings file; never touches the real H drive, scratch
drive or Maya prefs.

Covers: the reference path never changes on update or rollback; keys
survive; every shot follows an update; one shot rolls back on its own; one
copy of the data however many shots; publish files stay read-only; Maya
can't save over a link; a version cleared from publish\ doesn't break a
shot; Repair relinks a missing link; a copied shot folder is relinked;
fallback to a copy where the drive can't hardlink.
"""
import os, sys, stat, shutil, tempfile, filecmp

import maya.standalone
maya.standalone.initialize()
import maya.cmds as cmds

DEV = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(DEV, "publishDev"), os.path.join(DEV, "buildDev")]
import buildTool_api as api
import pipeEnv

base = tempfile.mkdtemp(prefix="riglink_")
H, S = os.path.join(base, "H"), os.path.join(base, "S")
FILM = "NWF_SHF"
results = []

_cfg = os.path.join(base, "pipeline_config.json")
api.pub._config_path = lambda: _cfg
api.pub.set_root(api.pub.H_DRIVE, H)
api.pub.set_root(api.pub.SCRATCH, S)
os.environ.pop(pipeEnv.VAR, None)


def check(name, ok):
    results.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name)


n = os.path.normcase

# H drive: scout rig v001 and v002 by anna. v002 adds a hat.
LOGIN = "anna"
scenes_h = os.path.join(H, FILM, "maya", "assets", "character", "scout", "scenes", LOGIN)
os.makedirs(scenes_h)
for v in (1, 2):
    cmds.file(new=True, force=True)
    cmds.polyCube(name="body_geo")
    cmds.spaceLocator(name="ctrl")
    if v == 2:
        cmds.polySphere(name="hat_geo")
    p = os.path.join(scenes_h, "scout_%s_rig_v%03d.ma" % (LOGIN, v))
    cmds.file(rename=p); cmds.file(save=True, type="mayaAscii")
    os.chmod(p, stat.S_IREAD)

shots = {}
for shot in ("EAP_010_010", "EAP_010_020", "EAP_010_030"):
    d = api.shot_folder(S, FILM, "EAP_010", shot)
    os.makedirs(os.path.join(d, "scenes"))
    open(os.path.join(d, "workspace.mel"), "w").write("")
    shots[shot] = d
maya_dir = os.path.join(S, FILM, "maya")
rig = [p for p in api.list_published(H, FILM) if p["code"] == "rig"][0]
V1, V2 = api.version_id(LOGIN, 1), api.version_id(LOGIN, 2)
NS = api.namespace_for("scout", "rig")


def link(shot):
    return os.path.join(shots[shot], "assets", "character", "scout", "rig", "scout_rig.ma")


def pub_v(v):
    return os.path.join(maya_dir, "publish", "assets", "character", "scout", "scenes", LOGIN,
                        "scout_%s_rig_v%03d.ma" % (LOGIN, v))


def written():
    return [w for _, w, _, _ in api.scene_references()]


def expected_written(shot):
    return ["$PIPE_SCRATCH/%s/maya/sequences/EAP_010/%s/assets/character/scout/rig/scout_rig.ma"
            % (FILM, shot)]


def open_shot(shot, scene=None):
    cmds.file(new=True, force=True)
    api.ensure_maya_project(shots[shot])
    if scene:
        cmds.file(scene, open=True, force=True)


def keys(attr):
    return cmds.keyframe("%s:ctrl.%s" % (NS, attr), query=True, keyframeCount=True) or 0


def scene(shot):
    return os.path.join(shots[shot], "scenes", "anim.ma")


def save(shot):
    cmds.file(rename=scene(shot)); cmds.file(save=True, type="mayaAscii")


# --- 010 and 020 build v1 and key the control
for shot, attr in (("EAP_010_010", "tx"), ("EAP_010_020", "ty")):
    open_shot(shot)
    done, warn, old = api.build_asset(shots[shot], rig, V1)
    cmds.setKeyframe("%s:ctrl.%s" % (NS, attr), time=1, value=0)
    cmds.setKeyframe("%s:ctrl.%s" % (NS, attr), time=10, value=5)
    save(shot)
check("build: no warning on NTFS", warn is None)
check("scene references the shot's fixed name with $PIPE_SCRATCH",
      written() == expected_written("EAP_010_020"))
check("both shots' names are links to publish v1",
      os.path.samefile(link("EAP_010_010"), pub_v(1)) and os.path.samefile(link("EAP_010_020"), pub_v(1)))
check("one copy of the data: 3 names (publish + 2 shots)", os.stat(pub_v(1)).st_nlink == 3)
m = api.read_manifest(shots["EAP_010_020"])["character/scout/rig"]
check("manifest records version, link and hardlink",
      m["version"] == 1 and m["link"] == "assets/character/scout/rig/scout_rig.ma" and m["hardlink"])
check("link_state: linked", api.link_state(shots["EAP_010_020"], m) == api.LINKED)
check("publish copy and link are read-only",
      not os.access(pub_v(1), os.W_OK) and not os.access(link("EAP_010_020"), os.W_OK))
done, warn, old = api.build_asset(shots["EAP_010_020"], rig, V1)
check("rebuild same version: already up to date", done == ["already up to date"] and old is None)
check("scene_version: rig in the scene at v1", api.scene_version(shots["EAP_010_020"], rig) == V1)
cmds.file(new=True, force=True)
check("scene_version: not in an empty scene", api.scene_version(shots["EAP_010_020"], rig) is None)

# --- Maya can't save over the link (it would change the shared version)
try:
    cmds.file(rename=link("EAP_010_020")); cmds.file(save=True, type="mayaAscii")
    saved_over = True
except RuntimeError:
    saved_over = False
check("Maya can't save over the read-only link", not saved_over
      and filecmp.cmp(pub_v(1), os.path.join(scenes_h, "scout_anna_rig_v001.ma"), shallow=False))

# --- 020 updates to v2 with its scene open: same path, reloaded
open_shot("EAP_010_020", scene("EAP_010_020"))
done, warn, old = api.build_asset(shots["EAP_010_020"], rig, V2)
print("   ", done)
check("update: path unchanged", written() == expected_written("EAP_010_020"))
check("update: reloaded with v2 content", "reloaded in scene" in done and cmds.objExists(NS + ":hat_geo"))
check("update: keys survived", keys("ty") == 2)
check("update: link now points at v2", os.path.samefile(link("EAP_010_020"), pub_v(2)))
check("update: v1 reported as replaced", old and n(old) == n(pub_v(1)))
check("publish v1 read-only again after relink", not os.access(pub_v(1), os.W_OK))
save("EAP_010_020")

# --- Every shot follows the update
others = api.other_shots_using(shots["EAP_010_020"], rig, V2)
check("other shots on an older version: 010", [n(o) for o in others] == [n(shots["EAP_010_010"])])
updated, replaced = api.update_shots(others, rig, V2)
check("update_shots relinked 010", updated == ["EAP_010_010"]
      and os.path.samefile(link("EAP_010_010"), pub_v(2)))
check("v1 now unused by any shot", api.unused_versions(replaced + [old], maya_dir) == [pub_v(1)])
open_shot("EAP_010_010", scene("EAP_010_010"))
check("010 opens on v2 without being repointed",
      written() == expected_written("EAP_010_010") and cmds.objExists(NS + ":hat_geo") and keys("tx") == 2)

# --- Roll back 020 only
open_shot("EAP_010_020", scene("EAP_010_020"))
done, warn, old = api.build_asset(shots["EAP_010_020"], rig, V1)
check("rollback: 020 back on v1, same path, keys kept",
      written() == expected_written("EAP_010_020") and not cmds.objExists(NS + ":hat_geo")
      and keys("ty") == 2 and os.path.samefile(link("EAP_010_020"), pub_v(1)))
check("rollback: 010 still on v2", os.path.samefile(link("EAP_010_010"), pub_v(2)))
check("rollback: other_shots_using lists 010 (on v2), so the UI can ask before touching it",
      [n(o) for o in api.other_shots_using(shots["EAP_010_020"], rig, V1)] == [n(shots["EAP_010_010"])])
save("EAP_010_020")

# --- Clearing a version from publish\ while a shot links it: still opens
os.chmod(pub_v(1), stat.S_IWRITE); os.remove(pub_v(1))
check("link survives its version being cleared", os.path.isfile(link("EAP_010_020")))
check("link_state: copy (has its own data now)",
      api.link_state(shots["EAP_010_020"], api.read_manifest(shots["EAP_010_020"])["character/scout/rig"])
      == api.COPY)
open_shot("EAP_010_020", scene("EAP_010_020"))
check("020 still opens on v1", cmds.objExists(NS + ":ctrl") and not cmds.objExists(NS + ":hat_geo"))

# --- Repair: the link itself is missing (e.g. after a scratch wipe of assets)
cmds.file(new=True, force=True)
os.chmod(link("EAP_010_020"), stat.S_IWRITE); os.remove(link("EAP_010_020"))
open_shot("EAP_010_020", scene("EAP_010_020"))
fixed, not_fixed = api.repair_scene(H)
print("   ", fixed, not_fixed)
check("repair relinked v1 from the manifest", len(fixed) == 1 and not not_fixed
      and os.path.samefile(link("EAP_010_020"), pub_v(1)))
check("repair loaded it, keys intact", cmds.objExists(NS + ":ctrl") and keys("ty") == 2)
check("publish files still read-only after repair",
      not os.access(pub_v(1), os.W_OK) and not os.access(pub_v(2), os.W_OK))

# --- A copied shot folder: link turns into a copy, Build relinks it
cmds.file(new=True, force=True)
api._remove_name(link("EAP_010_010"))
api._lock_publish_folder(maya_dir)
shutil.copy2(pub_v(2), link("EAP_010_010"))     # what copying the shot folder leaves
e10 = api.read_manifest(shots["EAP_010_010"])["character/scout/rig"]
check("copied shot folder: link_state copy", api.link_state(shots["EAP_010_010"], e10) == api.COPY)
open_shot("EAP_010_010", scene("EAP_010_010"))
done, warn, old = api.build_asset(shots["EAP_010_010"], rig, V2)
check("build turns the copy back into a link", os.path.samefile(link("EAP_010_010"), pub_v(2))
      and keys("tx") == 2)

# --- A scene from before the fixed name (references the publish version)
open_shot("EAP_010_030")
cmds.file(pub_v(1), reference=True, namespace=NS)
cmds.setKeyframe(NS + ":ctrl.tz", time=1, value=0); cmds.setKeyframe(NS + ":ctrl.tz", time=5, value=2)
save("EAP_010_030")

# --- Fallback: a drive that can't hardlink gets a read-only copy
real_link = os.link
def no_link(*a, **k):
    raise OSError(1, "Incorrect function")
os.link = no_link
try:
    done, warn, old = api.build_asset(shots["EAP_010_030"], rig, V2)
finally:
    os.link = real_link
print("   ", done, warn)
check("old-style reference switched to the fixed name, keys kept",
      written() == expected_written("EAP_010_030") and keys("tz") == 2
      and len(api.scene_references()) == 1)
check("fallback: copy, warned, still loads", warn and "can't hardlink" in warn
      and not os.path.samefile(link("EAP_010_030"), pub_v(2)) and cmds.objExists(NS + ":hat_geo"))
e30 = api.read_manifest(shots["EAP_010_030"])["character/scout/rig"]
check("fallback: manifest says not hardlinked, state copy",
      e30["hardlink"] is False and api.link_state(shots["EAP_010_030"], e30) == api.COPY)
check("fallback copy is read-only", not os.access(link("EAP_010_030"), os.W_OK))

# --- My Scratch: a shot's link counts as pulled, not unpublished work
items = dict((i["label"], i) for i in api.scratch_items(S, H, FILM) if i["kind"] == "shot")
check("scratch_items: link isn't flagged as risky",
      all(n(link("EAP_010_020")) not in [n(f) for f in i["risky"]] for i in items.values()))

print("\n%d/%d passed" % (sum(ok for _, ok in results), len(results)))
for root, dirs, files in os.walk(base):
    for f in files:
        os.chmod(os.path.join(root, f), stat.S_IWRITE)
shutil.rmtree(base, ignore_errors=True)
maya.standalone.uninitialize()
