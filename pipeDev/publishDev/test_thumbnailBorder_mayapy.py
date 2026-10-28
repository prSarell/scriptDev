# Publish thumbnail borders (user, 2026-10-28): dark blue = iterative,
# bright green = Final, none for shotSub. Asset publishes are Final when the
# newest Version on the department's Task is Approved. ShotGrid is faked.
# Run: mayapy test_thumbnailBorder_mayapy.py
import sys, os, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), "desktopDev")]
import maya.standalone; maya.standalone.initialize()
from PySide6 import QtGui
import publishTool_api as api

ok = []
def check(label, cond):
    ok.append(bool(cond)); print("PASS" if cond else "FAIL", label)

base = tempfile.mkdtemp(prefix="thumbborder_")
frames = []
for i in range(3):
    image = QtGui.QImage(400, 200, QtGui.QImage.Format_RGB32)
    image.fill(QtGui.QColor(128, 128, 128))
    path = os.path.join(base, "shot.%04d.jpg" % (i + 1))
    image.save(path, "JPG", 95)
    frames.append(path)


def near(colour, rgb, slack=24):         # JPEG isn't exact
    return all(abs(a - b) <= slack for a, b in zip((colour.red(), colour.green(), colour.blue()), rgb))


# -- the border ------------------------------------------------------------
for final, rgb, label in ((False, api.BORDER_ITERATIVE, "iterative: dark blue"),
                          (True, api.BORDER_FINAL, "final: bright green")):
    out = api.bordered_thumbnail(frames[1], final)
    image = QtGui.QImage(out)
    check(label + " border on all four edges",
          all(near(image.pixelColor(x, y), rgb) for x, y in ((2, 100), (397, 100), (200, 2), (200, 197))))
    check(label + ": the picture inside is untouched", near(image.pixelColor(200, 100), (128, 128, 128)))
check("the frame itself is untouched", near(QtGui.QImage(frames[1]).pixelColor(2, 100), (128, 128, 128)))

# -- the upload ------------------------------------------------------------
uploads = []


class FakeSG(object):
    def upload_thumbnail(self, entity_type, entity_id, path):
        uploads.append((entity_type, entity_id, os.path.isfile(path),
                        near(QtGui.QImage(path).pixelColor(2, 100), api.BORDER_FINAL)))


class FakeConnect(object):
    @staticmethod
    def get_connection():
        return FakeSG()


plan = {"final": True}
api.upload_bordered_thumbnail(FakeConnect(), plan, {"id": 99}, "Shot", 1736, frames)
check("Final: the green middle frame goes on the Version and the Shot",
      uploads == [("Version", 99, True, True), ("Shot", 1736, True, True)])
del uploads[:]
api.upload_bordered_thumbnail(FakeConnect(), {}, {"id": 99}, "Shot", 1736, frames)
check("no 'final' in the plan (shotSub's kind of upload): left alone", uploads == [])


class BrokenSG(FakeSG):
    def upload_thumbnail(self, *args):
        raise RuntimeError("site down")


plan = {"final": False}
api.upload_bordered_thumbnail(type("C", (), {"get_connection": staticmethod(BrokenSG)})(),
                              plan, {"id": 99}, "Asset", 1577, frames)
check("an upload failure is a warning, not a failed publish",
      any("iterative (blue)" in w and "site down" in w for w in plan["warnings"]))

# -- what's Final ----------------------------------------------------------
RIG = {"type": "Task", "id": 7, "content": "Rig"}
approved = {}
api.approved_tasks = lambda entity: approved
asset = {"type": "Asset", "id": 1544}
check("no task: never Final", not api.newest_approved(asset, None))
check("task's newest Version not approved: iterative", not api.newest_approved(asset, RIG))
approved = {"rig": RIG}
check("task's newest Version approved: Final", api.newest_approved(asset, RIG))
check("another task's approval doesn't count",
      not api.newest_approved(asset, {"type": "Task", "id": 8, "content": "Model"}))
check("every asset department has a task name",
      all(code in api.ASSET_TASKS for code in ("model", "rig", "creature", "lookDev", "env")))

# -- the staff script that makes the asset Tasks ---------------------------
import asset_tasks
assets = [{"id": 1, "code": "Scout", "sg_asset_type": "Character"},
          {"id": 2, "code": "Shed", "sg_asset_type": "Environment"},
          {"id": 3, "code": "Style Guide", "sg_asset_type": "Graphic"},
          {"id": 4, "code": "Farm Equipment", "sg_asset_type": None}]
existing = [{"content": "model", "entity": {"type": "Asset", "id": 1}},
            {"content": "Model and Texture", "entity": {"type": "Asset", "id": 2}}]
todo = [(a["code"], name) for a, name in asset_tasks.plan_tasks(assets, existing)]
check("asset_tasks: only what's missing, any case; Graphic / no type get none", todo == [
    ("Scout", "Rig"), ("Scout", "Creature"), ("Scout", "LookDev"),
    ("Shed", "Model"), ("Shed", "Environment"), ("Shed", "LookDev")])
check("asset_tasks: names match publishTool_api.ASSET_TASKS",
      set(n for names in asset_tasks.TASKS_BY_TYPE.values() for n in names)
      == set(api.ASSET_TASKS.values()))
check("asset_tasks: every task has a Step", all(n in asset_tasks.STEP_OF for n in api.ASSET_TASKS.values()))
print("%d/%d passed" % (sum(ok), len(ok)))
sys.stdout.flush()
os._exit(0 if all(ok) else 1)
