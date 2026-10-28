# Build by department (spec §4 "Build by department", user 2026-10-28): the
# tab has two rows ("the difference between build and populate list mode"):
# Add to list (what's published) and Build into (Film | Asset or Shot |
# department | Sequence | Shot), which starts on the Maya project and never
# changes it. The department decides what Add to list offers; it starts on
# the scene's (working folder, else file name). FX / Lighting coming soon.
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


# --- the Build tab: Add to list above, Build into below
def open_new(path):
    cmds.file(new=True, force=True)
    if not os.path.isdir(os.path.dirname(path)):
        os.makedirs(os.path.dirname(path))
    cmds.file(rename=path); cmds.file(save=True, type="mayaAscii", force=True)


def codes(p):
    m = p.dept_combo.model()
    return [m.item(i).data(QtCore.Qt.UserRole) for i in range(m.rowCount())]


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
OTHER = "SEQ010_130"
other_s = api.shot_folder(SC, FILM, SEQ, OTHER)
os.makedirs(api.shot_folder(H, FILM, SEQ, OTHER))
for folder in (shot_s, other_s):
    if not os.path.isdir(folder):
        os.makedirs(folder)
    open(os.path.join(folder, "workspace.mel"), "w").write("")
# The other shot already has a saved list: Scout's rig.
api.write_shot_list(H, FILM, SEQ, OTHER, [api.manifest_key("character", "scout", "rig")])

parent = QtWidgets.QWidget()
open_new(scene_in(shot_s, "anim", LOGIN, "anim_work.ma"))
cmds.workspace(shot_s, openWorkspace=True)          # the Project Tool's job
tab = ui.BuildShotTab(lambda: (H, SC), parent)
tab.refresh()
t, p = tab.target_picker, tab.picker
check("Build into: the Maya project's shot, for Animation (the scene's folder)",
      (t.film(), t.kind(), t.department(), t.group(), t.name())
      == (FILM, picker.SHOT, "anim", SEQ, SHOT) and tab._target_shot == (FILM, SEQ, SHOT))
i = codes(t).index("lighting")
check("Build into, Shot side: the shot departments, Lighting coming soon",
      codes(t) == ["layout", "anim", "fx", "lighting"]
      and not t.dept_combo.model().item(i).isEnabled() and "coming soon" in t.dept_combo.itemText(i))
check("Add to list: what Animation builds (models, rigs, environments; no lookDev)",
      codes(p) == ["model", "rig", "env"])
p.set_current(film=FILM, code="rig", group="character", name="scout")
tab._add_asset()
check("+ adds the picked publish", [(r["asset"], r["code"]) for r in tab._rows]
      == [("scout", "rig")])
check("Add to list, Environment: lists the environments",
      (p.set_current(code="env") or True) and (p.group(), p.name()) == ("environment", "shed"))
check("Keys from: this shot", not tab.keys_combo.isHidden()
      and tab._keys_source() == (FILM, SEQ, SHOT))
check("no banner: building into the scene's shot", tab.target_mismatch() is None
      and tab.project_banner.isHidden())

# Lighting isn't pickable yet; LookDev (Asset side) builds models and lookDev.
t.kind_combo.setCurrentIndex(t.kind_combo.findData(picker.ASSET))
check("Build into, Asset side: the asset departments",
      codes(t) == ["model", "rig", "creature", "lookDev"])
t.set_current(code="lookDev")
tab._on_department_changed()
check("LookDev: Add to list offers models and lookDev", codes(p) == ["model", "lookDev"])
t.set_current(film=FILM, code="anim", group=SEQ, name=SHOT)
tab._on_target_changed()
tab._on_department_changed()

# Build into another shot: its list, a banner, the project left alone.
t.set_current(code="anim", group=SEQ, name=OTHER)
tab._on_target_changed()
check("another shot picked: its list loads (Scout's rig)", tab._target_shot == (FILM, SEQ, OTHER)
      and [(r["asset"], r["code"]) for r in tab._rows] == [("scout", "rig")])
m = tab.target_mismatch()
check("banner: Build into SEQ010_130 isn't the project (SEQ010_120), Build won't run",
      m and m["target"]["name"] == OTHER and m["project"]["name"] == SHOT
      and not tab.project_banner.isHidden()
      and "won't run" in tab.project_banner.label.text()
      and tab.project_banner.match_btn.text() == "Back to the project's shot")
check("the Maya project isn't changed",
      os.path.normcase(os.path.normpath(cmds.workspace(query=True, rootDirectory=True)))
      == os.path.normcase(os.path.normpath(shot_s)))
asked = []
picker.confirm_mismatch = lambda parent, text, action: asked.append(text) or True
refs_before = api.scene_references()
tab._build_shot()
check("Build refuses (no 'build anyway'), builds nothing",
      not asked and "Nothing built" in tab.status._text
      and "Project Tool" in tab.status._text and api.scene_references() == refs_before)
tab.refresh()
check("refresh, same scene and project: Build into keeps the shot picked by hand",
      tab._target_shot == (FILM, SEQ, OTHER))
tab._match_project()
check("banner button: back to the project's shot", tab._target_shot == (FILM, SEQ, SHOT)
      and tab.target_mismatch() is None)

# Set the project to the other shot and save the scene there: allowed.
cmds.workspace(other_s, openWorkspace=True)
open_new(scene_in(other_s, "anim", LOGIN, "anim_work.ma"))
tab.check_target()
check("project set and scene saved in SEQ010_130: Build into it, no banner",
      tab._target_shot == (FILM, SEQ, OTHER) and tab.target_mismatch() is None
      and tab.project_banner.isHidden())
# Project right, scene saved elsewhere: refused too ("help to stay on pipe").
cmds.workspace(shot_s, openWorkspace=True)
tab.check_target()
asked[:] = []
tab._build_shot()
check("scene saved outside the project: refused, not asked",
      tab._target_shot == (FILM, SEQ, SHOT) and not asked
      and "Nothing built" in tab.status._text and "Set Project" in tab.status._text
      and "won't run" in tab.project_banner.label.text()
      and tab.project_banner.match_btn.text() == "Set Project to the scene's")
open_new(scene_in(shot_s, "anim", LOGIN, "anim_work.ma"))

# Another project set (the Project Tool): Build into follows it.
cmds.workspace(other_s, openWorkspace=True)
tab.check_target()
check("project changed: Build into follows it", tab._target_shot == (FILM, SEQ, OTHER))
cmds.workspace(shot_s, openWorkspace=True)

# An asset's rig scene, its project set: Build into the asset, for Rigging.
open_new(scene_in(asset_s, "rig", LOGIN, "rig_work.ma"))
open(os.path.join(asset_s, "workspace.mel"), "w").write("")
cmds.workspace(asset_s, openWorkspace=True)
tab.check_target()
check("asset rig scene: Build into the asset, Rigging",
      (t.kind(), t.department(), t.group(), t.name())
      == (picker.ASSET, "rig", "character", "scout") and tab._target_asset)
check("Rigging: Add to list offers models only", codes(p) == ["model"])
check("asset work: no Keys from; button says Import into Asset",
      tab.keys_combo.isHidden() and tab.build_btn.text() == "Import into Asset")

print("\n%d/%d passed" % (sum(ok), len(ok)))
shutil.rmtree(base, ignore_errors=True)
maya.standalone.uninitialize()
