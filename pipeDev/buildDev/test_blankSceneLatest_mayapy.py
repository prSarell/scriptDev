# Build Shot in a blank scene starts every row at the LATEST published
# version, whatever the shot's manifest says it used before; in a scene that
# already references the shot's assets, rows start at the version it has.
# Runs the real Build tab offscreen. Run: mayapy test_blankSceneLatest_mayapy.py
import sys, os, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), "publishDev")]
from PySide6 import QtWidgets
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
import maya.standalone; maya.standalone.initialize()
import maya.cmds as cmds
import buildTool_api as api
import buildTool_ui as ui

ok = []
def check(label, cond):
    ok.append(bool(cond)); print("PASS" if cond else "FAIL", label)

base = tempfile.mkdtemp(prefix="blanklatest_")
H, SC = os.path.join(base, "H"), os.path.join(base, "scratch")
pub_dir = os.path.join(H, "NWF_SHF", "maya", "assets", "prop", "backpack", "scenes", "scout")
os.makedirs(pub_dir)
for v in (3, 5):
    cmds.file(new=True, force=True)
    cmds.polyCube(name="backPack_geo")
    cmds.file(rename=os.path.join(pub_dir, "backpack_scout_model_v%03d.ma" % v))
    cmds.file(save=True, type="mayaAscii")
    os.utime(cmds.file(query=True, sceneName=True), (1000 + v, 1000 + v))   # v005 newest
shot = api.shot_folder(SC, "NWF_SHF", "EAP_010", "EAP_010_010")
os.makedirs(os.path.join(shot, "scenes"))
os.makedirs(api.shot_folder(H, "NWF_SHF", "EAP_010", "EAP_010_010"))
published = [p for p in api.list_published(H, "NWF_SHF") if p["asset"] == "backpack"][0]
api.pull(shot, published, "scout/v003")          # the shot used v003 before

parent = QtWidgets.QWidget()
tab = ui.BuildShotTab(lambda: (H, SC), parent)


def chosen():
    tab.refresh()
    return [r["chosen"] for r in tab._rows if r["asset"] == "backpack"]


cmds.file(new=True, force=True)
api.ensure_maya_project(shot)       # a new scene builds into the Maya project's shot
check("blank scene: starts at the latest (v005), not the shot's old v003", chosen() == ["scout/v005"])
cmds.file(os.path.join(pub_dir, "backpack_scout_model_v003.ma"), reference=True, namespace="backpack")
check("scene with the shot's assets: starts at the version it has (v003)", chosen() == ["scout/v003"])
print("%d/%d passed" % (sum(ok), len(ok)))
