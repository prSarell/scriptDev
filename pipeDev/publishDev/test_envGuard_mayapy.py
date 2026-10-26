# Environment from an asset scene (user, 2026-10-26: Environment is a kind
# of asset, not a department, so it isn't in the asset Department list).
# "+" with Modeling on an environment asset whose scene has an
# environment_SET adds an Environment row by itself (2026-10-23 a shed
# environment went out as Modeling and left its image planes behind);
# without environment_SET, or on another asset type, it stays Modeling.
# Nothing is asked. Runs the real window offscreen.
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
prop_rel = ["NWF_SHF", "maya", "assets", "prop", "crate"]
for rel in (asset_rel, prop_rel):
    os.makedirs(os.path.join(H, *rel, "scenes"))
    os.makedirs(os.path.join(SC, *rel, "scenes"))
api.who = lambda: "scout"
api.artist_name = lambda l: ""
api.get_root = lambda key: H if key == api.H_DRIVE else SC
api.follow_open_scene = lambda *a: None
api.check_script_nodes = lambda: None

asked = []
PARENT = QtWidgets.QWidget()
def fake_exec(box):
    asked.append(box.text())
    return 0
QtWidgets.QMessageBox.exec = fake_exec


def scene_with(environment, rel=asset_rel, name="shed_001.ma"):
    cmds.file(new=True, force=True)
    if environment:
        lay.make_environment_structure()
        cmds.parent(cmds.polyPlane(name="ground")[0], "|environment|landscape")
        shed = cmds.group(empty=True, name="shed", parent="|environment|buildings")
        cmds.parent(cmds.polyCube(name="shedBox")[0], shed)
    else:
        cmds.polyCube(name="shedBox")
    path = os.path.join(SC, *(rel + ["scenes", name]))
    cmds.file(rename=path); cmds.file(save=True, type="mayaAscii", force=True)


def add_as_model(group="environment", name="shed"):
    del asked[:]
    w = ui.PublishToolUI(PARENT)
    w.refresh()
    w.picker.set_current(film="NWF_SHF", code="model", group=group, name=name)
    cmds.select(clear=True)
    w._add_row()
    return w, [r["code"] for r in w._rows]


scene_with(True)
w, codes = add_as_model()
p = w.picker
model = p.dept_combo.model()
check("Environment isn't an asset department",
      "env" not in [model.item(i).data(ui.QtCore.Qt.UserRole) for i in range(model.rowCount())])
check("environment asset + environment_SET: an Environment row, nothing asked",
      codes == ["env"] and not asked)
check("... the list says Environment", w.table.item(0, 2).text() == "Environment")
scene_with(False)
w, codes = add_as_model()
check("environment asset, no environment_SET: a Modeling row", not asked and codes == ["model"])
scene_with(True, prop_rel, "crate_001.ma")
w, codes = add_as_model("prop", "crate")
check("a prop with an environment_SET: still Modeling", not asked and codes == ["model"])

# A shot's layout scene: Environment is picked on the Shot side, beside Layout.
shot_rel = ["NWF_SHF", "maya", "sequences", "SEQ010", "SEQ010_140"]
os.makedirs(os.path.join(H, *shot_rel, "scenes"))
os.makedirs(os.path.join(SC, *shot_rel, "scenes"))
scene_with(True, shot_rel, "layout_001.ma")
w = ui.PublishToolUI(PARENT)
w.refresh()
w.picker.set_current(code="env")
check("shot scene: Environment lists the environment assets",
      w.picker.kind() == "shot" and (w.picker.group(), w.picker.name()) == ("environment", "shed"))
w._add_row()
check("... and + adds the environment row to that asset",
      [(r["code"], r["asset"]) for r in w._rows] == [("env", "shed")])
# An asset made on H while the window is open (fieldA, 2026-10-26) shows up
# when the window is next refreshed, and what's picked stays picked.
os.makedirs(os.path.join(H, "NWF_SHF", "maya", "assets", "environment", "fieldA"))
w.refresh()
names = [w.picker.name_combo.itemData(i) for i in range(w.picker.name_combo.count())]
check("new environment asset on H appears without reopening the window",
      "fieldA" in names and w.picker.name() == "shed" and w.picker.department() == "env")

# Publish after a cancel (user, 2026-10-26): the cancelled publish left Maya
# thinking the scene changed, and the next Publish stopped at the save
# question, doing nothing if it was declined.
answers = []
def answer_exec(box):
    asked.append(box.text())
    answer = answers.pop(0)
    [b for b in box.buttons() if b.text().replace("&", "") == answer][0].click()
    return 0
QtWidgets.QMessageBox.exec = answer_exec
calls = []
def cancelled_publish(*a, **k):
    calls.append(1)
    cmds.file(modified=True)        # what the real playblast can leave behind
    raise api.PublishCancelled("Cancelled after watching the movie: nothing was published.")
api.publish = cancelled_publish
cmds.file(modified=True)
del asked[:]; answers[:] = ["Cancel"]
w._publish()
check("unsaved + Cancel: not published, and the status says why",
      not calls and "Not published" in w.status._text)
answers[:] = ["Save and Publish"]
w._publish()
check("Save and Publish: saved, then published (cancelled in review)", calls == [1])
check("... and the scene isn't left looking changed", not cmds.file(query=True, modified=True))
del asked[:]
w._publish()
check("Publish again: no save question, publish runs", not asked and calls == [1, 1])

print("%d/%d passed" % (sum(ok), len(ok)))
maya.standalone.uninitialize()
os._exit(0 if all(ok) else 1)
