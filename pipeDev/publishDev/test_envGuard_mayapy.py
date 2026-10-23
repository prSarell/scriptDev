# Publish guard (user, 2026-10-23): in a scene with an environment_SET, "+"
# with Modeling asks first, since a shed environment went out as Modeling
# and left its image planes behind. "Publish as Environment" adds an
# Environment row instead, "Keep Modeling" a Modeling row, Cancel nothing.
# A scene without environment_SET isn't asked. Runs the real window offscreen.
# Run: mayapy test_envGuard_mayapy.py
import sys, os, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), "layoutDev")]
from PySide6 import QtWidgets
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
import maya.standalone; maya.standalone.initialize()
import maya.cmds as cmds
import publishTool_api as api
import publishTool_ui as ui
import layoutTool_env as lay

ok = []
def check(label, cond):
    ok.append(bool(cond)); print("PASS" if cond else "FAIL", label)

base = tempfile.mkdtemp(prefix="envguard_")
H, SC = os.path.join(base, "H"), os.path.join(base, "scratch")
asset_rel = ["NWF_SHF", "maya", "assets", "environment", "shed"]
os.makedirs(os.path.join(H, *asset_rel, "scenes"))
os.makedirs(os.path.join(SC, *asset_rel, "scenes"))
api.who = lambda: "scout"
api.artist_name = lambda l: ""
api.get_root = lambda key: H if key == api.H_DRIVE else SC
api.follow_open_scene = lambda *a: None
api.check_script_nodes = lambda: None

# The answer to the question, by button text; asked records each question.
asked, CHOICE = [], ["Publish as Environment"]
PARENT = QtWidgets.QWidget()
def fake_exec(box):
    asked.append(box.text())
    [b for b in box.buttons() if b.text().replace("&", "") == CHOICE[0]][0].click()
    return 0
QtWidgets.QMessageBox.exec = fake_exec


def scene_with(environment):
    cmds.file(new=True, force=True)
    if environment:
        lay.make_environment_structure()
        cmds.parent(cmds.polyPlane(name="ground")[0], "|environment|landscape")
        shed = cmds.group(empty=True, name="shed", parent="|environment|buildings")
        cmds.parent(cmds.polyCube(name="shedBox")[0], shed)
    else:
        cmds.polyCube(name="shedBox")
    path = os.path.join(SC, *(asset_rel + ["scenes", "shed_001.ma"]))
    cmds.file(rename=path); cmds.file(save=True, type="mayaAscii", force=True)


def add_as_model(choice):
    del asked[:]
    CHOICE[0] = choice
    w = ui.PublishToolUI(PARENT)
    w.refresh()
    w.picker.set_current(film="NWF_SHF", code="model", group="environment", name="shed")
    cmds.select(clear=True)
    w._add_row()
    return w, [r["code"] for r in w._rows]


scene_with(True)
w, codes = add_as_model("Publish as Environment")
check("environment scene + Modeling: asked", len(asked) == 1 and "environment_SET" in asked[0])
check("Publish as Environment: an Environment row, picker switched",
      codes == ["env"] and w.picker.department() == "env")
w, codes = add_as_model("Keep Modeling")
check("Keep Modeling: a Modeling row", codes == ["model"])
w, codes = add_as_model("Cancel")
check("Cancel: nothing added", codes == [])
scene_with(False)
w, codes = add_as_model("Publish as Environment")
check("no environment_SET: not asked, Modeling row", not asked and codes == ["model"])

print("%d/%d passed" % (sum(ok), len(ok)))
maya.standalone.uninitialize()
os._exit(0 if all(ok) else 1)
