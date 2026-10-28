# Build by department (spec §4 "Build by department", user 2026-10-28): the
# picker reads Film | Asset or Shot | the artist's department | Asset type |
# Asset ("you can be working in a shot for layout or a shot for lighting").
# The department decides which publishes are offered ("scout (Rigging)");
# it starts on the open scene's department (working folder, else file name),
# and FX / Lighting are "coming soon" until caches build.
# Run: mayapy test_buildDepartment_mayapy.py
import sys, os, shutil, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), "publishDev")]
from PySide6 import QtWidgets, QtCore
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


# --- the Build tab
def open_new(path):
    cmds.file(new=True, force=True)
    if not os.path.isdir(os.path.dirname(path)):
        os.makedirs(os.path.dirname(path))
    cmds.file(rename=path); cmds.file(save=True, type="mayaAscii", force=True)


def codes(tab):
    m = tab.picker.dept_combo.model()
    return [m.item(i).data(QtCore.Qt.UserRole) for i in range(m.rowCount())]


def names(tab):
    """Everything the picker's last two dropdowns offer, as (type, label)."""
    return sorted(tab._items_for(FILM, tab.department(), picker.ASSET))


# Published on H: Scout's model, rig and lookDev, a backpack model and the
# shed environment (near-empty files: only the listing matters).
def published(asset_type, asset, code):
    path = os.path.join(H, FILM, "maya", "assets", asset_type, asset, "scenes", LOGIN,
                        "%s_%s_%s_v001.ma" % (asset, LOGIN, code))
    if not os.path.isdir(os.path.dirname(path)):
        os.makedirs(os.path.dirname(path))
    open(path, "w").write("//Maya ASCII\n")


for args in (("character", "scout", "model"), ("character", "scout", "rig"),
             ("prop", "backpack", "model"), ("environment", "shed", "env"),
             ("character", "scout", "lookDev")):
    published(*args)

parent = QtWidgets.QWidget()
open_new(scene_in(shot_s, "anim", LOGIN, "anim_work.ma"))
tab = ui.BuildShotTab(lambda: (H, SC), parent)
tab.refresh()
check("anim scene: Shot side, Animation", tab.department() == "anim"
      and tab.picker.kind() == picker.SHOT)
i = codes(tab).index("lighting") if "lighting" in codes(tab) else 0
check("Shot side lists the shot departments, Lighting coming soon",
      codes(tab) == ["layout", "anim", "fx", "lighting"]
      and not tab.picker.dept_combo.model().item(i).isEnabled()
      and "coming soon" in tab.picker.dept_combo.itemText(i))
check("Animation's picker: models, rigs and environments, labelled, no lookDev", names(tab) == [
    ("character", "scout (Modeling)"), ("character", "scout (Rigging)"),
    ("environment", "shed (Environment)"), ("prop", "backpack (Modeling)")])
tab.picker.set_current(code="anim", group="character", name="scout (Rigging)")
tab._add_asset()
check("+ adds the picked publish (scout's rig, not its model)",
      [(r["asset"], r["code"]) for r in tab._rows] == [("scout", "rig")])
check("shot work: Keys from, on this shot", not tab.keys_combo.isHidden()
      and tab._keys_source() == (FILM, SEQ, SHOT))

tab.picker.kind_combo.setCurrentIndex(tab.picker.kind_combo.findData(picker.ASSET))
check("Asset side: the asset departments", codes(tab) == ["model", "rig", "creature", "lookDev"])
tab.picker.set_current(code="model")
check("Modeling's picker: models only", names(tab) == [
    ("character", "scout (Modeling)"), ("prop", "backpack (Modeling)")])
tab.picker.set_current(code="lookDev")
check("LookDev's picker: models and lookDev", ("character", "scout (LookDev)") in names(tab)
      and ("character", "scout (Rigging)") not in names(tab))

tab.picker.set_current(code="layout")
tab.refresh()
check("same scene: refresh keeps the department picked", tab.department() == "layout")

open_new(scene_in(asset_s, "rig", LOGIN, "rig_work.ma"))
tab.check_target()
check("another scene opened (an asset's rig scene): Asset side, Rigging",
      tab.department() == "rig" and tab.picker.kind() == picker.ASSET)
check("Rigging's picker: models", names(tab) == [
    ("character", "scout (Modeling)"), ("prop", "backpack (Modeling)")])
check("asset work: no Keys from", tab.keys_combo.isHidden())

print("\n%d/%d passed" % (sum(ok), len(ok)))
shutil.rmtree(base, ignore_errors=True)
maya.standalone.uninitialize()
