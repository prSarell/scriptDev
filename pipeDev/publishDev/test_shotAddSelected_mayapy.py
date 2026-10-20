# The Publish window in a shot scene: no Asset/Department pickers, one Add
# Selected that sorts each selected thing (camera / published asset / made
# in the shot), and one Publish click = the camera publish(es) + ONE
# animation publish with every item. Runs the real window offscreen.
# Run: mayapy test_shotAddSelected_mayapy.py
import sys, os, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from PySide6 import QtWidgets
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
import maya.standalone; maya.standalone.initialize()
import maya.cmds as cmds
import publishTool_api as api
import publishTool_camera as cam
import publishTool_anim as anim
import publishTool_ui as ui

ok = []
def check(label, cond):
    ok.append(bool(cond)); print("PASS" if cond else "FAIL", label)

base = tempfile.mkdtemp(prefix="shotadd_")
H, SC = os.path.join(base, "H"), os.path.join(base, "scratch")
shot_rel = ["NWF_SHF", "maya", "sequences", "EAP_010", "EAP_010_010"]
os.makedirs(os.path.join(H, *shot_rel, "scenes"))
os.makedirs(os.path.join(SC, *shot_rel, "scenes"))
api.who = lambda: "scout"
api.artist_name = lambda l: ""
api.get_root = lambda key: H if key == api.H_DRIVE else SC
api.follow_open_scene = lambda *a: None
api.check_script_nodes = lambda: None

cmds.polyCube(name="backPack_geo")
model = os.path.join(base, "backpack_scout_model_v008.ma")
api.export_model_to_h_drive([], {"dest": model, "h_folder": base, "ext": ".ma", "asset": "backpack",
                                 "asset_type": "prop", "code": "model", "version": 8, "login": "scout",
                                 "sg_asset": {"id": 1577}}, "work.ma")
cmds.file(new=True, force=True)
cmds.file(model, reference=True, namespace="backpack")
cmds.setKeyframe("backpack:backPack_geo.tx", time=1, value=0)
cmds.polySphere(name="ball")
cmds.setKeyframe("ball.ty", time=1, value=0)
cmds.setKeyframe("ball.ty", time=10, value=3)
cmds.rename(cmds.camera()[0], "camera1")
scene = os.path.join(SC, *shot_rel, "scenes", "anim_001.ma")
cmds.file(rename=scene)
cmds.file(save=True, type="mayaAscii")

parent = QtWidgets.QWidget()
w = ui.PublishToolUI(parent)
w.refresh()
check("shot scene: Asset/Department pickers hidden", not w.asset_combo.isVisibleTo(w)
      and not w.dept_combo.isVisibleTo(w) and w.shot_hint.isVisibleTo(w))
check("shot scene: the button says Add Selected", w.add_btn.text() == "Add Selected")
model = w.publish_for_combo.model()
stages = [(model.item(i).text(), model.item(i).isEnabled()) for i in range(model.rowCount())]
check("shot scene: Publish for dropdown, Animation picked, Lighting/FX coming soon",
      w.publish_for_combo.isVisibleTo(w) and w.publish_for_combo.currentText() == "Animation"
      and stages == [("Layout", True), ("Animation", True),
                     ("Lighting (coming soon)", False), ("FX (coming soon)", False)])

# One click, a mixed selection (geo inside the backpack, the ball, the camera).
cmds.select(["backpack:backPack_geo", "ball", "camera1"], replace=True)
w._add_row()
rows = [(r["asset"], r["code"]) for r in w._rows]
check("one click adds all three, each sorted", sorted(rows) == sorted(
    [("backpack", "anim"), ("ball", "anim"), ("EAP_010_010", "cam")]))
types = dict((w.table.item(i, 0).text(), w.table.item(i, 1).text()) for i in range(w.table.rowCount()))
check("list says what each is", types == {"backpack": "model v008", "ball": "made in the shot",
                                          "EAP_010_010": "camera"})
publishes = dict((w.table.item(i, 0).text(), w.table.item(i, 4).text()) for i in range(w.table.rowCount()))
check("list says where each goes", publishes["ball"] == "EAP_010_010_scout_ball_anim_v001.ma  + map")
cmds.select("backpack:backpack_model_GRP", replace=True)
w._add_row()
check("adding the same thing again doesn't duplicate it", len(w._rows) == 3)

# Publish: cameras one by one, the animation items as ONE publish.
calls = []
cam.publish_camera = lambda *a, **k: (calls.append(("cam", k["camera"])), {
    "version": 1, "login": "scout", "sg_error": None, "sg_shot": {"code": "EAP_010_010"},
    "movie_warning": None})[1]
anim.publish_anim = lambda *a, **k: (calls.append((k["publish_for"], sorted(k["objects"]))), {
    "version": 1, "login": "scout", "sg_error": None, "sg_shot": {"code": "EAP_010_010"},
    "movie_warning": None, "stage": "blocking"})[1]
w._publish()
check("one camera publish + ONE animation publish with both items",
      sorted(c[0] for c in calls) == ["anim", "cam"]
      and [c for c in calls if c[0] == "anim"][0][1] == ["backpack:backpack_model_GRP", "ball"])

# Switch to Layout: same items, Layout publish.
w.publish_for_combo.setCurrentIndex(w.publish_for_combo.findData(anim.LAYOUT_CODE))
depts = dict((w.table.item(i, 0).text(), w.table.item(i, 2).text()) for i in range(w.table.rowCount()))
publishes = dict((w.table.item(i, 0).text(), w.table.item(i, 4).text()) for i in range(w.table.rowCount()))
check("Layout picked: list says Layout and layout file names",
      depts["ball"] == "Layout" and publishes["ball"] == "EAP_010_010_scout_ball_layout_v001.ma  + map")
calls[:] = []
w._publish()
check("Layout publish gets publish_for=layout", [c[0] for c in calls if c[0] != "cam"] == ["layout"])

# Asset scenes keep the pickers.
cmds.file(new=True, force=True)
asset_scene = os.path.join(SC, "NWF_SHF", "maya", "assets", "prop", "backpack", "scenes", "work.ma")
os.makedirs(os.path.dirname(asset_scene))
cmds.file(rename=asset_scene)
cmds.file(save=True, type="mayaAscii")
w.refresh()
check("asset scene: pickers back, button says Add to List",
      w.asset_combo.isVisibleTo(w) and w.add_btn.text() == "Add to List")
print("%d/%d passed" % (sum(ok), len(ok)))
