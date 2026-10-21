# Set Project (user, 2026-10-21: "not setting the project"): Build's and the
# Project Tool's Set Project go through publishTool_api.set_maya_project,
# which does what File > Set Project does, checks the project really
# changed, and explains when it can't. Headless here, so Maya's own
# setProject (file browser, Recent Projects) is only exercised in Maya.
# Run: mayapy test_setProject_mayapy.py
import sys, os, shutil, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), "publishDev")]
from PySide6 import QtWidgets
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
import maya.standalone; maya.standalone.initialize()
import maya.cmds as cmds
import publishTool_api as pub
import buildTool_api as api
import buildTool_ui as ui

ok = []
def check(label, cond):
    ok.append(bool(cond)); print("PASS" if cond else "FAIL", label)

base = tempfile.mkdtemp(prefix="setproj_")
here = lambda p: pub._same_path(cmds.workspace(query=True, rootDirectory=True), p)

with_ws = os.path.join(base, "NWF_SHF", "maya", "sequences", "EAP_010", "EAP_010_010")
os.makedirs(with_ws)
with open(os.path.join(with_ws, "workspace.mel"), "w") as f:
    f.write('workspace -fr "scene" "scenes";\n')
api.set_maya_project(with_ws)
check("a shot with a workspace.mel becomes the project", here(with_ws))

no_ws = os.path.join(base, "NWF_SHF", "maya", "sequences", "EAP_010", "EAP_010_020")
os.makedirs(no_ws)
api.set_maya_project(no_ws)
check("a shot without one becomes the project too", here(no_ws))
check("... and gets Maya's default workspace.mel", os.path.isfile(os.path.join(no_ws, "workspace.mel")))

api.set_maya_project(with_ws)
check("ensure_maya_project: already the project -> nothing to do",
      api.ensure_maya_project(with_ws) is False)
check("ensure_maya_project: another shot -> switched",
      api.ensure_maya_project(no_ws) is True and here(no_ws))

gone = os.path.join(base, "NWF_SHF", "maya", "sequences", "EAP_010", "EAP_010_999")
try:
    api.set_maya_project(gone)
    check("a missing folder is refused, with why", False)
except pub.PublishError as e:
    check("a missing folder is refused, with why", "isn't there" in str(e) and here(no_ws))

# The Build tab's button reports instead of failing silently.
parent = QtWidgets.QWidget()
tab = ui.BuildShotTab(lambda: (base, base), parent)
tab._shot_dir = lambda: gone
tab._set_project()
check("Build's Set Project button shows the problem", "isn't there" in tab.status._text)
tab._shot_dir = lambda: with_ws
tab._set_project()
check("Build's Set Project button sets it and says so",
      here(with_ws) and "Maya project set" in tab.status._text)
print("%d/%d passed" % (sum(ok), len(ok)))
shutil.rmtree(base, ignore_errors=True)
