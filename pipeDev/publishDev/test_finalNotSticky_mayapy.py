# Final doesn't stick (user, 2026-10-28): a publish is Final only when the
# newest Version on the shot's Final task is Approved. Each publish makes a
# new Version, Pending Review, so the one after a final publish is
# iterative unless that Version is approved too. ShotGrid is faked.
# Run: mayapy test_finalNotSticky_mayapy.py
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import maya.standalone; maya.standalone.initialize()
import publishTool_api as api
import publishTool_anim as anim

ok = []
def check(label, cond):
    ok.append(bool(cond)); print("PASS" if cond else "FAIL", label)

FINAL_TASK = {"type": "Task", "id": 12, "content": "Final"}
LAYOUT_TASK = {"type": "Task", "id": 10, "content": "Layout"}
versions = []           # what the fake ShotGrid holds, oldest first


def version(status, task=FINAL_TASK):
    versions.append({"id": len(versions) + 1, "sg_status_list": status,
                     "sg_task": task and {"type": "Task", "id": task["id"]},
                     "sg_task.Task.content": task and task["content"]})


class FakeSG(object):
    def find(self, entity, filters, fields, order=None):
        found = [v for v in versions if v["sg_task"]]       # ["sg_task", "is_not", None]
        if order:                                           # created_at desc = newest first
            found = sorted(found, key=lambda v: v["id"], reverse=True)
        return found


class FakeConnect(object):
    @staticmethod
    def get_connection():
        return FakeSG()


api._shotgrid = lambda: FakeConnect()
api.task_on = lambda shot, name: {"Final": FINAL_TASK, "Layout": LAYOUT_TASK}[name]
SHOT = {"type": "Shot", "id": 1736}
stage = lambda: anim.publish_stage(SHOT)[0]

check("nothing published yet: iterative", stage() == anim.ANIMATION)
version("rev")                                  # anim_v001
check("v001 pending: iterative", stage() == anim.ANIMATION)
versions[-1]["sg_status_list"] = "apr"          # teacher approves v001
check("v001 approved: next publish is Final", stage() == anim.FINAL)
version("rev")                                  # anim_v002 = the final publish
check("after the final publish (v002 pending): iterative again", stage() == anim.ANIMATION)
versions[-1]["sg_status_list"] = "vwd"
check("v002 viewed, not approved: still iterative", stage() == anim.ANIMATION)
versions[-1]["sg_status_list"] = "apr"
check("v002 approved: Final again", stage() == anim.FINAL)
version(None, task=None)                        # a shotSub review: no task
check("a shotSub Version (no task) doesn't change it", stage() == anim.FINAL)
version("rev", task=LAYOUT_TASK)                # a camera publish on Layout
check("a newer Version on another task doesn't change it", stage() == anim.FINAL)
check("Final goes on the Final task", anim.publish_stage(SHOT)[1]["id"] == FINAL_TASK["id"])
check("Layout never Final, even with Final approved",
      anim.publish_stage(SHOT, anim.LAYOUT_CODE)[0] == anim.LAYOUT)
print("%d/%d passed" % (sum(ok), len(ok)))
sys.stdout.flush()
os._exit(0 if all(ok) else 1)
