# One shared build list per shot or asset, the same for every department
# (user, 2026-11-27, spec §4n), on H in <shot>\data\build\build_list.json,
# read-only, written only by Build. The per-department lists from
# 2026-10-30 (<department>.json) and the older one list (build_list.json,
# no "shared" mark) are merged into the first shared list read. Load list
# adds another shot's saved list to the one in Build.
# Run: mayapy test_buildSharedList_mayapy.py
import sys, os, json, stat, shutil, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), "publishDev")]
from PySide6 import QtWidgets
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
import maya.standalone; maya.standalone.initialize()
import maya.cmds as cmds
import buildTool_api as api
import buildTool_ui as ui
import pipePicker as picker
import pipeEnv

ok = []
def check(label, cond):
    ok.append(bool(cond)); print("PASS" if cond else "FAIL", label)

base = tempfile.mkdtemp(prefix="buildsharedlist_")
H, SC = os.path.join(base, "H"), os.path.join(base, "scratch")
FILM, SEQ, SHOT, OLD, LOGIN = "NWF_SHF", "SEQ010", "SEQ010_120", "SEQ010_130", "scout"
_cfg = os.path.join(base, "pipeline_config.json")
api.pub._config_path = lambda: _cfg
api.pub.set_root(api.pub.H_DRIVE, H)
api.pub.set_root(api.pub.SCRATCH, SC)
api.pub.save_config(dict(api.pub.load_config(), publish_as=LOGIN))
os.environ.pop(pipeEnv.VAR, None)

RIG = api.manifest_key("character", "scout", "rig")
MODEL = api.manifest_key("prop", "backpack", "model")
for shot in (SHOT, OLD):
    os.makedirs(api.shot_folder(H, FILM, SEQ, shot))

# --- the API
path = api.shot_list_path(H, FILM, SEQ, SHOT)
check(r"the list lives in <shot>\data\build\build_list.json on H",
      path == os.path.join(api.shot_folder(H, FILM, SEQ, SHOT), "data", "build",
                           "build_list.json"))
check("no list yet -> None", api.read_shot_list(H, FILM, SEQ, SHOT) is None)
api.write_shot_list(H, FILM, SEQ, SHOT, [RIG, MODEL], usd=[MODEL])
check("one list for everyone", api.read_shot_list(H, FILM, SEQ, SHOT) == [RIG, MODEL])
check("... with what loads as USD",
      api.read_build_list_usd(api.shot_folder(H, FILM, SEQ, SHOT)) == {MODEL})
saved = json.load(open(path))
check("saved as the shared list, with who and when",
      saved["shared"] is True and saved["saved_by"] == LOGIN and saved["saved"])
check("locked read-only on H", not os.access(path, os.W_OK))
api.write_shot_list(H, FILM, SEQ, SHOT, [RIG])
check("Build can save it again (and it's locked again)",
      api.read_shot_list(H, FILM, SEQ, SHOT) == [RIG] and not os.access(path, os.W_OK))

# The older lists of a shot: merged into its first shared list.
old_dir = os.path.join(api.shot_folder(H, FILM, SEQ, OLD), "data", "build")
os.makedirs(old_dir)
json.dump({"assets": [RIG], "department": "anim"}, open(os.path.join(old_dir, "anim.json"), "w"))
json.dump({"assets": [MODEL, RIG], "usd": [MODEL], "department": "layout"},
          open(os.path.join(old_dir, "layout.json"), "w"))
check("per-department lists merged, each item once",
      sorted(api.read_shot_list(H, FILM, SEQ, OLD)) == sorted([RIG, MODEL])
      and api.read_build_list_usd(api.shot_folder(H, FILM, SEQ, OLD)) == {MODEL})
api.write_shot_list(H, FILM, SEQ, OLD, [RIG])
check("once the shared list is saved, it wins (a - sticks)",
      api.read_shot_list(H, FILM, SEQ, OLD) == [RIG])
check("... and the old lists are left as they were",
      json.load(open(os.path.join(old_dir, "layout.json")))["assets"] == [MODEL, RIG])


# --- the Build tab
def published(asset_type, asset, code):
    p = os.path.join(H, FILM, "maya", "assets", asset_type, asset, "scenes", LOGIN,
                     "%s_%s_%s_v001.ma" % (asset, LOGIN, code))
    os.makedirs(os.path.dirname(p))
    open(p, "w").write("//Maya ASCII\n")


published("character", "scout", "rig")
published("prop", "backpack", "model")
shot_s = api.shot_folder(SC, FILM, SEQ, SHOT)
anim_scene = os.path.join(shot_s, "scenes", "anim", LOGIN, "anim_work.ma")
light_scene = os.path.join(shot_s, "scenes", "lighting", LOGIN, "light_work.ma")
for scene in (anim_scene, light_scene):
    os.makedirs(os.path.dirname(scene))
open(os.path.join(shot_s, "workspace.mel"), "w").write("")


def open_new(scene):
    cmds.file(new=True, force=True)
    if scene:
        cmds.file(rename=scene); cmds.file(save=True, type="mayaAscii", force=True)


parent = QtWidgets.QWidget()
tab = ui.BuildShotTab(lambda: (H, SC), parent)
keys = lambda: [tab._key(r) for r in tab._rows if r.get("kind") != "cache"]
open_new(anim_scene)
tab.refresh()
check("Animation scene: the shot's list", tab._target_shot == (FILM, SEQ, SHOT) and keys() == [RIG])
open_new(light_scene)
tab.check_target()
check("Lighting scene in the same shot: the same list", keys() == [RIG])
tab.picker.set_current(film=FILM, code="model", kind=picker.ASSET, group="prop",
                       name="backpack")
tab._add_asset()
tab._save_shot_list()
check("adding as Lighting changes the one list", api.read_shot_list(H, FILM, SEQ, SHOT)
      == [RIG, MODEL])
open_new(anim_scene)
tab.check_target()
check("... which Animation sees too", sorted(keys()) == sorted([RIG, MODEL]))
tab.table.selectRow([tab._key(r) for r in tab._rows].index(MODEL))
tab._remove_rows()
check("- takes it off the shared list", api.read_shot_list(H, FILM, SEQ, SHOT) == [RIG])

# Load list: another shot's saved list joins this one.
api.write_shot_list(H, FILM, SEQ, OLD, [RIG, MODEL])
tab.picker.set_current(film=FILM, code="anim", kind=picker.SHOT, group=SEQ, name=OLD)
print("    picker:", tab.picker.kind(), tab.picker.group(), tab.picker.name())
tab._load_list()
print("   ", tab.status._text)
check("Load list: SEQ010_130's list joins, nothing already here doubled",
      sorted(keys()) == sorted([RIG, MODEL]) and "backpack" in tab.status._text)
check("... the added row ticked", [r for r in tab._rows if tab._key(r) == MODEL][0]["checked"])
tab._load_list()
check("Load list again: nothing new", "already here" in tab.status._text and len(keys()) == 2)

# --- untitled scene: the list starts empty; + works; Build saves it first
open_new(None)
tab.check_target()
check("untitled scene: no shot, empty list, says what to do",
      tab._target_shot is None and tab._rows == [] and "Untitled" in tab.target_lbl.text()
      and "Build asks where to save" in tab.status._text)
tab.picker.set_current(film=FILM, code="rig", kind=picker.ASSET, group="character",
                       name="scout")
tab._add_asset()
check("untitled: + adds a row", keys() == [RIG] and tab._rows[0]["checked"])
tab._save_shot_list()
check("untitled: no shot, so no list is saved anywhere",
      api.read_shot_list(H, FILM, SEQ, SHOT) == [RIG])
tab._ask_save_path = lambda: None
tab._build_shot()
check("Build, Save As cancelled: nothing built", "wasn't saved" in tab.status._text
      and cmds.file(query=True, sceneName=True) == "")
tab._ask_save_path = lambda: os.path.join(base, "loose.ma")
tab._build_shot()
check("saved outside the pipe: refused, says where", "isn't in a shot or asset folder"
      in tab.status._text and cmds.file(query=True, sceneName=True) == "")
new_scene = os.path.join(shot_s, "scenes", "anim", LOGIN, "fresh.ma")
tab._ask_save_path = lambda: new_scene
built = []
api_build = api.build_asset
api.build_asset = lambda *a, **k: (built.append(a[1]["asset"]), (["built"], None, None))[1]
tab._build_shot()
check("saved into the shot: the scene is saved there, Build follows it",
      os.path.normcase(cmds.file(query=True, sceneName=True)) == os.path.normcase(new_scene)
      and tab._target_shot == (FILM, SEQ, SHOT))
check("... the row added before saving is still on the list", RIG in keys())
check("... nothing new joined (the shot's list was the same): built straight away",
      built == ["scout"])
api.build_asset = api_build

print("\n%d/%d passed" % (sum(ok), len(ok)))
for root, dirs, fs in os.walk(base):
    for f in fs:
        os.chmod(os.path.join(root, f), stat.S_IWRITE)
shutil.rmtree(base, ignore_errors=True)
