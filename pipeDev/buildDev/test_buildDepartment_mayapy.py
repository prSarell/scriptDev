# Build by department (spec §4 "Build by department", user 2026-10-28): the
# artist's department decides what the Build tab's picker offers; it starts
# on the open scene's department (working folder, else file name), and FX /
# Lighting are "coming soon" until caches build.
# Run: mayapy test_buildDepartment_mayapy.py
import sys, os, shutil, tempfile
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

base = tempfile.mkdtemp(prefix="builddept_")
H, SC = os.path.join(base, "H"), os.path.join(base, "scratch")
FILM, SEQ, SHOT, LOGIN = "NWF_SHF", "SEQ010", "SEQ010_120", "scout"
_cfg = os.path.join(base, "pipeline_config.json")
api.pub._config_path = lambda: _cfg
api.pub.set_root(api.pub.H_DRIVE, H)
api.pub.set_root(api.pub.SCRATCH, SC)
api.pub.save_config(dict(api.pub.load_config(), publish_as=LOGIN))
os.environ.pop(pipeEnv.VAR, None)

shot_s = api.shot_folder(SC, FILM, SEQ, SHOT)
asset_s = api.asset_folder(SC, FILM, "character", "scout")
os.makedirs(api.shot_folder(H, FILM, SEQ, SHOT))
os.makedirs(os.path.join(H, FILM, "maya", "assets", "character", "scout", "scenes"))


def scene_in(folder, *rel):
    return os.path.join(folder, "scenes", *rel)


# --- department_of_scene
d = api.department_of_scene
check("shot working folder anim -> Animation", d(scene_in(shot_s, "anim", LOGIN, "a.ma")) == "anim")
check("shot working folder layout -> Layout", d(scene_in(shot_s, "layout", LOGIN, "a.ma")) == "layout")
check("shot lighting (coming soon) -> Layout",
      d(scene_in(shot_s, "lighting", LOGIN, "a.ma")) == "layout")
check("shot scene by file name: SEQ010_120_layout_v002 -> Layout",
      d(scene_in(shot_s, LOGIN, "SEQ010_120_layout_v002.ma")) == "layout")
check("shot scene, nothing to go on -> Animation", d(scene_in(shot_s, "shot.ma")) == "anim")
check("asset working folder rig -> Rigging", d(scene_in(asset_s, "rig", LOGIN, "a.ma")) == "rig")
check("asset working folder lookDev -> LookDev",
      d(scene_in(asset_s, "lookDev", LOGIN, "a.ma")) == "lookDev")
check("asset scene by file name: scout_rig_v002 -> Rigging",
      d(scene_in(asset_s, "scout_rig_v002.ma")) == "rig")
check("asset scene, nothing to go on -> Modeling", d(scene_in(asset_s, "scout.ma")) == "model")
check("outside the pipe -> None", d(os.path.join(base, "loose.ma")) is None)

# --- what each department builds
check("Lighting / FX coming soon", api.builds_for("lighting") == [] and api.builds_for("fx") == [])
check("Modeling: models only", api.builds_for("model") == ["model"])
check("Animation: no lookDev", "lookDev" not in api.builds_for("anim")
      and "rig" in api.builds_for("anim") and "cam" in api.builds_for("anim"))

# --- the Build tab: starts on the scene's department, picker follows
def open_new(path):
    cmds.file(new=True, force=True)
    if not os.path.isdir(os.path.dirname(path)):
        os.makedirs(os.path.dirname(path))
    cmds.file(rename=path); cmds.file(save=True, type="mayaAscii", force=True)


def codes(tab, kind=None):
    m = tab.picker.dept_combo.model()
    return [m.item(i).data(QtCore.Qt.UserRole) for i in range(m.rowCount())]


from PySide6 import QtCore
parent = QtWidgets.QWidget()
open_new(scene_in(shot_s, "anim", LOGIN, "anim_work.ma"))
tab = ui.BuildShotTab(lambda: (H, SC), parent)
tab.refresh()
check("tab starts on Animation in an anim scene", tab.department() == "anim")
tab.picker.set_current(code="rig")
check("Animation's picker: Rigging on the Asset side", tab.picker.department() == "rig"
      and "lookDev" not in codes(tab))
tab.picker.set_current(code="cam")
check("Animation's picker: Camera on the Shot side", tab.picker.kind() == picker.SHOT
      and set(codes(tab)) == {"cam", "env", "cache"})

tab.dept_combo.setCurrentIndex(tab.dept_combo.findData("model"))
kinds = tab.picker.kind_combo.model()
check("Modeling: only models, on the Asset side", tab.picker.kind() == picker.ASSET
      and codes(tab) == ["model"])
check("Modeling: Shot side greyed out",
      not kinds.item(tab.picker.kind_combo.findData(picker.SHOT)).isEnabled())
i = tab.dept_combo.findData("lighting")
check("Lighting shown as coming soon, not pickable",
      "coming soon" in tab.dept_combo.itemText(i)
      and not tab.dept_combo.model().item(i).isEnabled())

tab.dept_combo.setCurrentIndex(tab.dept_combo.findData("layout"))
tab.refresh()
check("same scene: refresh keeps the department picked", tab.department() == "layout")

open_new(scene_in(asset_s, "rig", LOGIN, "rig_work.ma"))
tab.check_target()
check("another scene opened (an asset's rig scene): Rigging", tab.department() == "rig")
check("Rigging's picker: models", codes(tab) == ["model"])

print("\n%d/%d passed" % (sum(ok), len(ok)))
shutil.rmtree(base, ignore_errors=True)
maya.standalone.uninitialize()
