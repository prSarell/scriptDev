# One build list per shot per department (user, 2026-10-30: "everyone on the
# same shot should see the same list"), on H in the shot's data folder:
# <shot>\data\build\<department>.json. Animation's picks never show up in
# Layout's (or Lighting's) list. The one list per shot from before
# (<shot>\build_list.json) is read as the starting list for Layout and
# Animation only, and never written again.
# Run: mayapy test_buildListDepartment_mayapy.py
import sys, os, json, shutil, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), "publishDev")]
from PySide6 import QtWidgets
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
import maya.standalone; maya.standalone.initialize()
import maya.cmds as cmds
import buildTool_api as api
import buildTool_ui as ui
import pipeEnv

ok = []
def check(label, cond):
    ok.append(bool(cond)); print("PASS" if cond else "FAIL", label)

base = tempfile.mkdtemp(prefix="buildlistdept_")
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
path = api.shot_list_path(H, FILM, SEQ, SHOT, "anim")
check(r"the list lives in <shot>\data\build\anim.json on H",
      path == os.path.join(api.shot_folder(H, FILM, SEQ, SHOT), "data", "build", "anim.json"))
check("no list yet -> None", api.read_shot_list(H, FILM, SEQ, SHOT, "anim") is None)
api.write_shot_list(H, FILM, SEQ, SHOT, "anim", [RIG])
api.write_shot_list(H, FILM, SEQ, SHOT, "layout", [MODEL])
check("Animation gets its own list", api.read_shot_list(H, FILM, SEQ, SHOT, "anim") == [RIG])
check("Layout gets its own list", api.read_shot_list(H, FILM, SEQ, SHOT, "layout") == [MODEL])
check("Lighting has none", api.read_shot_list(H, FILM, SEQ, SHOT, "lighting") is None)
saved = json.load(open(path))
check("saved with department, who and when",
      saved["department"] == "anim" and saved["saved_by"] == LOGIN and saved["saved"])
check("nothing written to the old shot list",
      not os.path.exists(os.path.join(api.shot_folder(H, FILM, SEQ, SHOT), "build_list.json")))

# The old one-per-shot list: the starting list for Layout and Animation.
old = os.path.join(api.shot_folder(H, FILM, SEQ, OLD), api.OLD_SHOT_LIST_NAME)
json.dump({"assets": [RIG]}, open(old, "w"))
check("old list -> Animation's starting list", api.read_shot_list(H, FILM, SEQ, OLD, "anim") == [RIG])
check("old list -> Layout's starting list", api.read_shot_list(H, FILM, SEQ, OLD, "layout") == [RIG])
check("old list never Lighting's", api.read_shot_list(H, FILM, SEQ, OLD, "lighting") is None)
api.write_shot_list(H, FILM, SEQ, OLD, "anim", [])
check("once Animation saves, its own list wins", api.read_shot_list(H, FILM, SEQ, OLD, "anim") == [])
check("...and the old list is left as it was", json.load(open(old)) == {"assets": [RIG]})


# --- the Build tab: switching department switches the list
def published(asset_type, asset, code):
    p = os.path.join(H, FILM, "maya", "assets", asset_type, asset, "scenes", LOGIN,
                     "%s_%s_%s_v001.ma" % (asset, LOGIN, code))
    os.makedirs(os.path.dirname(p))
    open(p, "w").write("//Maya ASCII\n")


published("character", "scout", "rig")
published("prop", "backpack", "model")
shot_s = api.shot_folder(SC, FILM, SEQ, SHOT)
scene = os.path.join(shot_s, "scenes", "anim", LOGIN, "anim_work.ma")
os.makedirs(os.path.dirname(scene))
open(os.path.join(shot_s, "workspace.mel"), "w").write("")
cmds.file(new=True, force=True)
cmds.file(rename=scene); cmds.file(save=True, type="mayaAscii", force=True)
cmds.workspace(shot_s, openWorkspace=True)

parent = QtWidgets.QWidget()
tab = ui.BuildShotTab(lambda: (H, SC), parent)
tab.refresh()
keys = lambda: [tab._key(r) for r in tab._rows if r.get("kind") != "cache"]
check("Animation scene: Animation's list", tab.department() == "anim" and keys() == [RIG])
tab.target_picker.set_current(code="layout")
tab._on_department_changed()
check("switch to Layout: Layout's list", keys() == [MODEL])
tab._save_shot_list()
check("saving as Layout leaves Animation's list alone",
      api.read_shot_list(H, FILM, SEQ, SHOT, "anim") == [RIG]
      and api.read_shot_list(H, FILM, SEQ, SHOT, "layout") == [MODEL])
tab.target_picker.set_current(code="anim")
tab._on_department_changed()
check("back to Animation: Animation's list again", keys() == [RIG])

print("\n%d/%d passed" % (sum(ok), len(ok)))
shutil.rmtree(base, ignore_errors=True)
