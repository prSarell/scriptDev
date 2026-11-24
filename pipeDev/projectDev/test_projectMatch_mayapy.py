# Open scene vs Maya project (user, 2026-10-28: "I keep changing the
# project expecting that to effect where the build tool is building from and
# where the publish tool is publishing to"). Build and Publish go by the
# open scene; when it's in another shot/asset than the Maya project they show
# a red banner and ask before acting (warn, let me carry on). Set Project
# offers to open the newest scene there or start a new one. Real windows,
# offscreen, throwaway folders. Run: mayapy test_projectMatch_mayapy.py
import sys, os, json, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HERE = os.path.dirname(os.path.abspath(__file__))
DEV = os.path.dirname(HERE)
sys.path[:0] = [HERE, os.path.join(DEV, "publishDev"), os.path.join(DEV, "buildDev")]
from PySide6 import QtWidgets
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
import maya.standalone; maya.standalone.initialize()
import maya.cmds as cmds
import publishTool_api as pub

ok = []
def check(label, cond):
    ok.append(bool(cond)); print("PASS" if cond else "FAIL", label)

base = tempfile.mkdtemp(prefix="projmatch_")
H, S = os.path.join(base, "H"), os.path.join(base, "S")
_cfg = os.path.join(base, "pipeline_config.json")
pub._config_path = lambda: _cfg
pub.save_config({pub.H_DRIVE: H, "scratch_root": S, "publish_as": "e131988"})
pub.artist_name = lambda l: ""
SHOT = ["NWF_SHF", "maya", "sequences", "SEQ010", "SEQ010_140"]
SHED = ["NWF_SHF", "maya", "assets", "environment", "shed"]
for rel in (SHOT, SHED):
    for root in (H, S):
        os.makedirs(os.path.join(root, *(rel + ["scenes", "e131988"])))
shot_dir, shed_dir = os.path.join(S, *SHOT), os.path.join(S, *SHED)


def save(path):
    cmds.file(rename=path); cmds.file(save=True, type="mayaAscii", force=True)


cmds.file(new=True, force=True)
shot_scene = os.path.join(shot_dir, "scenes", "e131988", "SEQ010_140_anim_001.ma")
save(shot_scene)
older = os.path.join(shed_dir, "scenes", "shed_001.ma")
save(older)
os.utime(older, (1000000000, 1000000000))
shed_scene = os.path.join(shed_dir, "scenes", "e131988", "shed_002.ma")
save(shed_scene)

# -- what's where -------------------------------------------------------------
place = pub.pipe_place(shot_scene)
check("a scene's place: the shot", (place["kind"], place["name"], place["group"]) ==
      ("shot", "SEQ010_140", "SEQ010") and pub._same_path(place["folder"], shot_dir))
check("a project folder's place: the asset", pub.pipe_place(shed_dir + "/")["name"] == "shed")
check("outside the pipe: no place", pub.pipe_place(base) is None)
check("newest scene in a project", pub._same_path(pub.latest_scene(shed_dir), shed_scene))

pub.set_maya_project(shed_dir)
cmds.file(shot_scene, open=True, force=True)
m = pub.project_mismatch()
check("shot scene open, shed project set: a mismatch",
      m and m["scene"]["name"] == "SEQ010_140" and m["project"]["name"] == "shed")
text = pub.mismatch_text(m, "Publish")
check("the banner says both, and which one wins",
      "shot SEQ010_140" in text and "asset shed" in text and "Publish uses the open scene" in text)
pub.set_maya_project(shot_dir)
check("scene in the project: no mismatch", pub.project_mismatch() is None)
cmds.file(new=True, force=True)
check("unsaved scene: no mismatch", pub.project_mismatch() is None)
other_drive = os.path.join(base, "S2", *SHOT)
os.makedirs(os.path.join(other_drive, "scenes"))
pub.set_maya_project(other_drive)
cmds.file(shot_scene, open=True, force=True)
check("same shot on another drive: no mismatch", pub.project_mismatch() is None)

# -- the Publish window ---------------------------------------------------------
import publishTool_ui as pui
import pipePicker as picker
answers = []
real_confirm = picker.confirm_mismatch
picker.confirm_mismatch = lambda parent, text, action: (answers.append(action), False)[1]
pub.set_maya_project(shed_dir)
cmds.file(shot_scene, open=True, force=True)
PARENT = QtWidgets.QWidget()
w = pui.PublishToolUI(PARENT)
check("Publish: red banner shown", w.project_banner.isVisibleTo(w)
      and "asset shed" in w.project_banner.label.text())
w._publish()
check("Publish: asks first, Cancel publishes nothing",
      answers == ["Publish"] and "Not published" in w.status._text)
w.project_banner.match_btn.click()
check("Publish: 'Set Project to the scene's' fixes it, banner goes",
      pub._same_path(cmds.workspace(query=True, rootDirectory=True), shot_dir)
      and not w.project_banner.isVisibleTo(w))
pub.set_maya_project(shed_dir)
cmds.file(new=True, force=True)
w.refresh()
check("Publish: unsaved scene starts the picker on the Maya project",
      w.picker.film() == "NWF_SHF" and w.picker.kind() == picker.ASSET
      and w.picker.name_combo.currentData() == "shed")
w.close()

# -- the Build window -----------------------------------------------------------
import buildTool_ui as bui
cmds.file(shot_scene, open=True, force=True)
tab = bui.BuildShotTab(lambda: (H, S), PARENT)
tab.refresh()
check("Build: red banner shown", tab.project_banner.isVisibleTo(tab)
      and "Build uses the open scene" in tab.project_banner.label.text())
del answers[:]
tab._build_shot()
check("Build: asks first, Cancel builds nothing",
      answers == ["Build"] and "Nothing built" in tab.status._text)
pub.set_maya_project(shot_dir)
tab.check_target()
check("Build: project changed while the window was open, banner goes",
      not tab.project_banner.isVisibleTo(tab))
picker.confirm_mismatch = real_confirm

# -- Set Project offers to switch scene -----------------------------------------
import projectTool_ui as prui
chosen = []
QtWidgets.QMessageBox.exec = lambda box: 0
QtWidgets.QMessageBox.clickedButton = lambda box: next(
    (b for b in box.buttons() if b.text().startswith(chosen[0])), None)
pw = prui.ProjectToolUI(PARENT)
offer = lambda project: pw._switch_scene(pw._ask_scene_switch(project))
cmds.file(shot_scene, open=True, force=True)
chosen[:] = ["Keep"]
check("Set Project: keep the current scene", offer(shed_dir) is None
      and pub._same_path(cmds.file(query=True, sceneName=True), shot_scene))
chosen[:] = ["Open"]
done = offer(shed_dir)
check("Set Project: open the newest scene in the new project",
      done == "opened shed_002.ma"
      and pub._same_path(cmds.file(query=True, sceneName=True), shed_scene))
cmds.file(shot_scene, open=True, force=True)
cmds.polyCube()
chosen[:] = ["New"]
asked = []
real_save = pw._save_or_discard
pw._save_or_discard = lambda scene: (asked.append(scene), False)[1]     # Cancel
check("Set Project: unsaved changes asked about, Cancel there cancels the Set Project",
      pw._ask_scene_switch(shed_dir) == prui.CANCEL and asked
      and pub._same_path(cmds.file(query=True, sceneName=True), shot_scene))
pw._save_or_discard = real_save

# Cancel on the switch question: the project isn't set at all, nothing
# changes (user, 2026-11-24). set_project is stubbed to see if it's called.
import projectTool_api as prapi
pub.set_maya_project(shot_dir)
set_calls = []
real_set, real_items, real_roots = prapi.set_project, pw.tree.selectedItems, pw._roots
prapi.set_project = lambda *a, **k: (set_calls.append(a), (shed_dir, ["Maya project set"]))[1]
class _Item(object):
    def data(self, col, role):
        return tuple(SHED)
pw.tree.selectedItems = lambda: [_Item()]
pw._roots = lambda: (H, S)
pw._save_or_discard = lambda scene: True
chosen[:] = ["Cancel"]
pw._set_project()
check("Set Project + Cancel: project not set, scene kept, status says so",
      not set_calls and pub._same_path(prapi.current_project(), shot_dir)
      and pub._same_path(cmds.file(query=True, sceneName=True), shot_scene)
      and "Project not changed" in pw.status.text())
chosen[:] = ["Keep"]
pw._set_project()
check("Set Project + Keep Current Scene: project set, scene kept",
      len(set_calls) == 1 and pub._same_path(cmds.file(query=True, sceneName=True), shot_scene))
prapi.set_project, pw.tree.selectedItems, pw._roots = real_set, real_items, real_roots
chosen[:] = ["New Scene"]
pw._save_or_discard = lambda scene: True
check("Set Project: new scene", offer(shed_dir) == "started a new scene"
      and not cmds.file(query=True, sceneName=True))
check("Set Project: scene already in the new project, nothing asked",
      offer(shed_dir) is None)
print("%d/%d passed" % (sum(ok), len(ok)))
