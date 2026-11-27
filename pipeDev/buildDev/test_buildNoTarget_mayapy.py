# Build without "Build into" (user, 2026-11-27, spec §4n): one row of
# dropdowns, Add to list (every department, LOCKED list); the shot or asset
# is where the open scene is saved, whatever the Maya project is; Build
# never touches the project and never refuses over it; Keys come from the
# scene's own shot. department_of_scene and builds_for are still the API's.
# Run: mayapy test_buildNoTarget_mayapy.py
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
check("shot lighting -> Lighting (builds since 2026-11-25)",
      d(scene_in(shot_s, "lighting", LOGIN, "a.ma")) == "lighting")
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
# Every department builds everything (project lead, 2026-11-25).
everything = ["model", "rig", "creature", "lookDev", api.ENV_CODE, "cam", "cache"]
check("every department, Lighting and FX included, builds everything",
      all(api.builds_for(c) == everything for _, c, _ in api.BUILD_FOR)
      and set(api.live_departments()) == set(c for _, c in api.DEPARTMENTS))


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
# shed also has a Modeling publish, as on the T7: its old env publish isn't
# listed (user, 2026-10-30: "we don't need to see the old bad publishes").
published("environment", "shed", "model")
_old = api.list_published
def _shed_model_older(*a, **k):
    found = _old(*a, **k)
    for pp in found:
        if (pp["asset"], pp["code"]) == ("shed", "model"):
            for info in pp["info"].values():
                info["time"] -= 3600
    return found
api.list_published = _shed_model_older
OTHER = "SEQ010_130"
other_s = api.shot_folder(SC, FILM, SEQ, OTHER)
os.makedirs(api.shot_folder(H, FILM, SEQ, OTHER))
for folder in (shot_s, other_s):
    if not os.path.isdir(folder):
        os.makedirs(folder)
    open(os.path.join(folder, "workspace.mel"), "w").write("")
# The other shot already has a saved list: Scout's rig.
api.write_shot_list(H, FILM, SEQ, OTHER, [api.manifest_key("character", "scout", "rig")])

# --- no Build into (user, 2026-11-27, spec §4n): one row of dropdowns
parent = QtWidgets.QWidget()
open_new(scene_in(shot_s, "anim", LOGIN, "anim_work.ma"))
cmds.workspace(other_s, openWorkspace=True)         # the project somewhere else
tab = ui.BuildShotTab(lambda: (H, SC), parent)
tab.refresh()
p = tab.picker
check("no Build into row, no Keys from, no project banner",
      not hasattr(tab, "target_picker") and not hasattr(tab, "keys_combo")
      and not hasattr(tab, "project_banner"))
check("the shot is where the scene is saved, whatever the project is",
      tab._target_shot == (FILM, SEQ, SHOT) and "SEQ010_120" in tab.target_lbl.text())
# The Department dropdown: the pipe's department list, LOCKED (user,
# 2026-10-30), whatever Asset or Shot says. No Environment.
LOCKED = ["model", "rig", "creature", "lookDev", "layout", "anim", "fx", "lighting"]
def all_enabled(pk):
    m = pk.dept_combo.model()
    return all(m.item(i).isEnabled() for i in range(m.rowCount()))
check("Add to list: the locked department list", codes(p) == LOCKED and all_enabled(p))
p.kind_combo.setCurrentIndex(p.kind_combo.findData(picker.SHOT))
check("Add to list, Shot side: the same list", codes(p) == LOCKED)
check("Load list sits on the Add to list row", p.layout().indexOf(tab.load_btn) >= 0)
p.kind_combo.setCurrentIndex(p.kind_combo.findData(picker.ASSET))
p.set_current(film=FILM, code="rig", group="character", name="scout")
tab._add_asset()
check("+ adds the picked publish", [(r["asset"], r["code"]) for r in tab._rows]
      == [("scout", "rig")])
check("Add to list, Modeling: environment publishes listed under it (shed)",
      (p.set_current(code="model", group="environment") or True)
      and (p.group(), p.name()) == ("environment", "shed"))
check("shed listed once, though it has a Modeling and an environment publish",
      [n for g, n in p._items if g == "environment"] == ["shed"])
before = len(tab._rows)
tab._add_asset()
check("+ adds shed's Modeling publish; the old env one isn't listed",
      [(r["asset"], r["code"]) for r in tab._rows[before:]] == [("shed", "model")]
      and not [pp for pp in tab._published if pp["code"] == "env"])
tab._add_asset()
check("+ again: shed is already in the list", len(tab._rows) == before + 1
      and "already in the list" in tab.status._text)
del tab._rows[before:]
tab._render_table()
check("Keys: the scene's own shot", tab._keys_source() == (FILM, SEQ, SHOT))

# Build never touches the project, and never refuses over it.
built = []
_real = api.build_asset
api.build_asset = lambda *a, **k: (built.append(a[0]), (["built"], None, None))[1]
tab._build_shot()
api.build_asset = _real
check("Build runs with the project elsewhere, into the scene's shot",
      built and all(os.path.normcase(b) == os.path.normcase(shot_s) for b in built))
check("... and the Maya project is left as it was",
      os.path.normcase(os.path.normpath(cmds.workspace(query=True, rootDirectory=True)))
      == os.path.normcase(os.path.normpath(other_s)))

# Another scene opened, in another shot: Build follows the scene.
open_new(scene_in(other_s, "lighting", LOGIN, "light_work.ma"))
tab.check_target()
check("a scene in SEQ010_130 opened: its shot and its list (Scout's rig)",
      tab._target_shot == (FILM, SEQ, OTHER)
      and [(r["asset"], r["code"]) for r in tab._rows if r.get("kind") != "camera"]
      == [("scout", "rig")])

# An asset's rig scene: Build into the asset.
open_new(scene_in(asset_s, "rig", LOGIN, "rig_work.ma"))
tab.check_target()
check("asset rig scene: building into the asset", tab._target_asset == (FILM, "character", "scout")
      and tab._target_shot is None)
check("asset: the same Build button as a shot", tab.build_btn.text() == "Build")

print("\n%d/%d passed" % (sum(ok), len(ok)))
shutil.rmtree(base, ignore_errors=True)
maya.standalone.uninitialize()
