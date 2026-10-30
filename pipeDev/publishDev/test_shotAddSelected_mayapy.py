# The Publish window's picker row (user, 2026-10-22). In a shot scene, +
# with Layout/Animation sorts each selected thing (camera / published
# asset / made in the shot), and one Publish click = ONE animation publish
# with every ticked item, carrying the camera of the same stage (one movie,
# 2026-10-28); a camera on its own still publishes by itself. In an asset
# scene, + adds the picked asset. Runs the real window offscreen.
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
p = w.picker
check("shot scene: picker starts on Animation for this shot",
      (p.film(), p.department(), p.kind(), p.group(), p.name())
      == ("NWF_SHF", "anim", "shot", "EAP_010", "EAP_010_010")
      and p.kind_combo.currentText() == "Shot" and p.kind_combo.isEnabled())
def dept_list():
    model = p.dept_combo.model()
    return [(model.item(i).text(), model.item(i).isEnabled()) for i in range(model.rowCount())]
# The pipe's department list, LOCKED (user, 2026-10-30), whatever Asset or
# Shot says. No Environment; FX and Lighting can't publish yet.
LOCKED = [("Modeling", True), ("Rigging", True), ("Creature", True), ("LookDev", True),
          ("Layout", True), ("Animation", True), ("FX (coming soon)", False),
          ("Lighting (coming soon)", False)]
check("Shot: Department is the locked list", dept_list() == LOCKED)
p.kind_combo.setCurrentIndex(p.kind_combo.findData("asset"))
check("picking Asset: the same list, Animation kept",
      dept_list() == LOCKED and p.department() == "anim"
      and p.group_combo.toolTip() == "Asset type" and p.name_combo.toolTip() == "Asset")
w._add_row()
check("Animation with Asset picked: + says pick Shot", not w._rows
      and "pick Shot" in w.status._text)
p.kind_combo.setCurrentIndex(p.kind_combo.findData("shot"))
p.set_current(code="model")
cmds.select("ball", replace=True)
w._add_row()
check("Modeling with Shot picked: + says pick Asset", not w._rows
      and "pick Asset" in w.status._text)
p.set_current(code="model", group="prop", kind="asset")
w._add_row()
check("a prop's Modeling in a shot scene is refused", not w._rows
      and "published from an asset's scene" in w.status._text)
p.set_current(code=anim.ANIM_CODE, group="EAP_010", name="EAP_010_010", kind="shot")

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

# Publish: the animation items and the camera as ONE publish.
calls = []
cam.publish_camera = lambda *a, **k: (calls.append(("cam", k["camera"])), {
    "version": 1, "login": "scout", "sg_error": None, "sg_shot": {"code": "EAP_010_010"},
    "movie_warning": None})[1]
anim.publish_anim = lambda *a, **k: (calls.append((k["publish_for"], sorted(k["objects"]),
                                                    k.get("camera"))), {
    "version": 1, "login": "scout", "sg_error": None, "sg_shot": {"code": "EAP_010_010"},
    "movie_warning": None, "stage": "blocking"})[1]
w._publish()
check("ONE animation publish with both items and the camera: no camera publish of its own",
      [c[0] for c in calls] == ["anim"] and calls[0][1] == ["backpack:backpack_model_GRP", "ball"]
      and calls[0][2].split("|")[-1] == "camera1")

# Untick the ball: only ticked rows publish.
row = [i for i, r in enumerate(w._rows) if r["asset"] == "ball"][0]
w.table.item(row, 0).setCheckState(ui.QtCore.Qt.Unchecked)
app.processEvents()
calls[:] = []
w._publish()
check("an unticked row isn't published", [c[1] for c in calls if c[0] == "anim"]
      == [["backpack:backpack_model_GRP"]])

# Take them off and add them again for Layout: Layout publish.
w.table.selectAll()
w._remove_rows()
check("- takes the highlighted rows off", not w._rows)
p.set_current(code=anim.LAYOUT_CODE)
cmds.select(["backpack:backPack_geo", "ball", "camera1"], replace=True)
w._add_row()
depts = dict((w.table.item(i, 0).text(), w.table.item(i, 2).text()) for i in range(w.table.rowCount()))
publishes = dict((w.table.item(i, 0).text(), w.table.item(i, 4).text()) for i in range(w.table.rowCount()))
check("Layout picked: list says Layout and layout file names",
      depts["ball"] == "Layout" and publishes["ball"] == "EAP_010_010_scout_ball_layout_v001.ma  + map")
calls[:] = []
w._publish()
check("Layout publish gets publish_for=layout", [c[0] for c in calls if c[0] != "cam"] == ["layout"])

# Asset scenes: the picker starts on the scene's asset, + adds it.
cmds.file(new=True, force=True)
os.makedirs(os.path.join(H, "NWF_SHF", "maya", "assets", "prop", "backpack"))
asset_scene = os.path.join(SC, "NWF_SHF", "maya", "assets", "prop", "backpack", "scenes",
                           "backpack_rig_work.ma")
os.makedirs(os.path.dirname(asset_scene))
cmds.file(rename=asset_scene)
cmds.file(save=True, type="mayaAscii")
w.refresh()
check("asset scene: picker on Rigging (from the file name), prop, backpack",
      (p.department(), p.kind(), p.group(), p.name()) == ("rig", "asset", "prop", "backpack")
      and w.objects_btn.isVisibleTo(w))
p.set_current(code=anim.ANIM_CODE, group="EAP_010", name="EAP_010_010", kind="shot")
w._rows[:] = []
w._add_row()
check("a shot department from an asset scene is refused", not w._rows
      and "open one of its scenes first" in w.status._text)
p.set_current(code="model", group="prop", name="backpack", kind="asset")
cmds.polyCube(name="box")
cmds.select("box", replace=True)
w._add_row()
check("+ adds the asset with the selection", [(r["asset"], r["code"], r["objects"])
                                                for r in w._rows] == [("backpack", "model", ["box"])])
print("%d/%d passed" % (sum(ok), len(ok)))
