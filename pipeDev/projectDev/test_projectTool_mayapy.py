# Project Tool (pipeDev/projectSwitcher_brief.md): a clean scratch drive gets
# the film's full 1:1 folder structure on first Set Project; no H-drive
# change = nothing touched; an H-drive change is seen and only added after
# the student says yes; nothing is ever deleted; the window lists the whole
# film with the student's own work highlighted. ShotGrid is faked.
# Run: mayapy test_projectTool_mayapy.py
import sys, os, shutil, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), "publishDev")]
from PySide6 import QtWidgets
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
import maya.standalone; maya.standalone.initialize()
import maya.cmds as cmds
import publishTool_api as pub
import projectTool_api as api
import projectTool_ui as ui

ok = []
def check(label, cond):
    ok.append(bool(cond)); print("PASS" if cond else "FAIL", label)

base = tempfile.mkdtemp(prefix="projtool_")
# Set Project also sets up Studio Library (spec §4b): its settings go to a
# temp file here, never the real ones.
try:
    import studiolibrary
    studiolibrary.config.set("settingsPath", os.path.join(base, "LibraryWidget.json"))
except ImportError:
    pass
H, SC = os.path.join(base, "H"), os.path.join(base, "scratch")
os.makedirs(SC)


def project(*rel):
    path = os.path.join(H, "NWF_SHF", "maya", *rel)
    for sub in ("scenes", "images", "cache"):
        os.makedirs(os.path.join(path, sub), exist_ok=True)
    with open(os.path.join(path, "workspace.mel"), "w") as f:
        f.write('workspace -fr "scene" "scenes";\n')


project("assets", "prop", "backpack")
project("assets", "character", "scout")
project("sequences", "EAP_010", "EAP_010_010")
project("sequences", "EAP_010", "EAP_010_020")
os.makedirs(os.path.join(H, "NWF_SHF", "premiere", "shotgridMovs"))
os.makedirs(os.path.join(H, "NWF_SHF", "maya", "assets", "prop", "backpack", "scenes", "anna"))
with open(os.path.join(H, "NWF_SHF", "maya", "assets", "prop", "backpack", "scenes", "anna",
                       "backpack_anna_model_v001.ma"), "w") as f:
    f.write("// a publish: files are never copied\n")
with open(os.path.join(H, "NWF_SHF", "pipeline.json"), "w") as f:
    f.write('{"film": "NWF_SHF", "shotgrid_project_id": 157}')
pub.who = lambda: "scout"
pub.get_root = lambda key: H if key == pub.H_DRIVE else SC

# -- 1. clean scratch: Set Project lays down the whole film, 1:1 ------------
path, done = api.set_project(H, SC, ["NWF_SHF", "maya", "sequences", "EAP_010", "EAP_010_010"])
h_dirs, _ = api._dirs(H, "NWF_SHF")
s_dirs, s_ws = api._dirs(SC, "NWF_SHF")
check("clean scratch: every H-drive folder is on scratch", h_dirs <= s_dirs)
check("... with every workspace.mel", len(s_ws) == 4)
check("... and no files from the H drive (no publishes copied)", not os.path.exists(os.path.join(
    SC, "NWF_SHF", "maya", "assets", "prop", "backpack", "scenes", "anna", "backpack_anna_model_v001.ma")))
check("... plus my own scenes folder", os.path.isdir(os.path.join(path, "scenes", "scout")))
check("... and the Maya project is set", os.path.normcase(api.current_project())
      == os.path.normcase(os.path.normpath(path)))
check("says what it did", any("folder structure" in d for d in done))

# -- 2. nothing changed on H: nothing to update ---------------------------
diff = api.structure_diff(H, SC, "NWF_SHF")
check("no H-drive change = nothing to update", not diff["missing"] and not diff["workspaces"]
      and not diff["gone"])
work = os.path.join(SC, "NWF_SHF", "maya", "sequences", "EAP_010", "EAP_010_010", "scenes",
                    "scout", "my_work.ma")
open(work, "w").write("// my work")

# -- 3. H changes: new shot, renamed asset -> seen, flagged, never deleted --
project("sequences", "EAP_010", "EAP_010_030")
os.rename(os.path.join(H, "NWF_SHF", "maya", "assets", "character", "scout"),
          os.path.join(H, "NWF_SHF", "maya", "assets", "character", "scoutGrownUp"))
diff = api.structure_diff(H, SC, "NWF_SHF")
check("the change is seen and described",
      api.describe_diff(diff) == "new shots: EAP_010_030; new assets: scoutGrownUp")
check("renamed asset flagged as gone from the H drive",
      ("NWF_SHF", "maya", "assets", "character", "scout") in diff["gone"])
check("scratch-only publish folder never flagged", not any("publish" in r for r in diff["gone"]))
# Setting the new shot builds just that shot; the asset waits for the update.
api.set_project(H, SC, ["NWF_SHF", "maya", "sequences", "EAP_010", "EAP_010_030"])
check("setting a new project builds just that one",
      os.path.isfile(os.path.join(SC, "NWF_SHF", "maya", "sequences", "EAP_010", "EAP_010_030", "workspace.mel"))
      and not os.path.isdir(os.path.join(SC, "NWF_SHF", "maya", "assets", "character", "scoutGrownUp")))
folders, workspaces = api.update_structure(H, SC, "NWF_SHF")
check("update adds the rest", os.path.isfile(os.path.join(
    SC, "NWF_SHF", "maya", "assets", "character", "scoutGrownUp", "workspace.mel")) and workspaces == 1)
check("update never deletes: old asset folder and my work kept",
      os.path.isdir(os.path.join(SC, "NWF_SHF", "maya", "assets", "character", "scout"))
      and open(work).read() == "// my work")
ws = os.path.join(SC, "NWF_SHF", "maya", "sequences", "EAP_010", "EAP_010_010", "workspace.mel")
open(ws, "w").write("// my own workspace edits")
api.update_structure(H, SC, "NWF_SHF")
check("update never overwrites an existing workspace.mel", open(ws).read() == "// my own workspace edits")

# -- 4. the window --------------------------------------------------------
api.shotgrid_user = lambda sg=None: {"type": "HumanUser", "id": 7, "name": "Test Person"}
api.user_projects = lambda user, sg=None: [{"id": 157, "name": "Not Worth Fixing"},
                                           {"id": 999, "name": "Some Class"}]
api.assigned = lambda user, pid, sg=None: {("Shot", "EAP_010_020"), ("Asset", "Backpack")}
parent = QtWidgets.QWidget()
w = ui.ProjectToolUI(parent)
model = w.project_combo.model()
check("projects from ShotGrid; one without an H folder is greyed out",
      [(model.item(i).text(), model.item(i).isEnabled()) for i in range(model.rowCount())]
      == [("Not Worth Fixing", True), ("Some Class  (not on the H drive yet)", False)])


def items():
    found = {}
    for i in range(w.tree.topLevelItemCount()):
        top = w.tree.topLevelItem(i)
        for g in range(top.childCount()):
            for c in range(top.child(g).childCount()):
                it = top.child(g).child(c)
                found[it.text(0)] = it
    return found


listed = items()
check("whole film listed (assets and shots)", set(listed) >= {
    "backpack", "scoutGrownUp", "EAP_010_010", "EAP_010_020", "EAP_010_030"})
check("my assignments highlighted (asset matched loosely: Backpack = backpack)",
      listed["EAP_010_020"].text(2) == "yours" and listed["backpack"].text(2) == "yours"
      and listed["EAP_010_010"].text(2) == "")
check("the current Maya project is marked", listed["EAP_010_030"].text(2) == "current project")
check("no H change since the update: no banner", not w.update_box.isVisibleTo(w)
      or not w.update_btn.isVisibleTo(w))
project("sequences", "EAP_010", "EAP_010_040")
w.refresh()
check("H changes: banner asks to update", w.update_box.isVisibleTo(w) and w.update_btn.isVisibleTo(w)
      and "EAP_010_040" in w.update_lbl.text())
w._update_structure()
check("after Update Scratch: banner shows only the kept old folder, no button",
      not w.update_btn.isVisibleTo(w) and "scout" in w.update_lbl.text())
w.mine_chk.setChecked(True)
shown = [n for n, it in items().items() if not it.isHidden()]
check("Only mine filter", sorted(shown) == ["EAP_010_020", "backpack"])
w.mine_chk.setChecked(False)
it = items()["EAP_010_020"]
w.tree.setCurrentItem(it)
w._set_project()
check("Set Project from the window", os.path.normcase(api.current_project()).endswith(
    os.path.normcase(os.path.join("EAP_010", "EAP_010_020"))))
print("%d/%d passed" % (sum(ok), len(ok)))
