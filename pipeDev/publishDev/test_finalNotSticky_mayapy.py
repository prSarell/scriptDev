# Final doesn't stick (user, 2026-10-28), and since 2026-11-24 it's a tick:
# an Animation publish is Final only when ABC or USD caches are ticked on
# its row, whatever ShotGrid says ("over complicated this" tying it to the
# shot's Final approval). Each publish decides for itself. ShotGrid faked.
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
api.task_on = lambda shot, name: {"Final": FINAL_TASK, "Layout": LAYOUT_TASK}[name]
asked = []
api.approved_tasks = lambda shot: asked.append(shot) or {"final": FINAL_TASK}
SHOT = {"type": "Shot", "id": 1736}
stage = lambda caches=(), publish_for=anim.ANIM_CODE: anim.publish_stage(SHOT, publish_for, caches)[0]

check("no caches ticked: iterative", stage() == anim.ANIMATION)
check("ABC ticked: Final", stage(["abc"]) == anim.FINAL)
check("USD ticked: Final", stage(["usd"]) == anim.FINAL)
check("both: Final", stage(["abc", "usd"]) == anim.FINAL)
check("the next publish without ticks: iterative again", stage() == anim.ANIMATION)
check("FBX/OBJ aren't caches", stage(["fbx", "obj"]) == anim.ANIMATION)
check("ShotGrid approval isn't asked", not asked)
check("both go on the Final task", anim.publish_stage(SHOT)[1]["id"] == FINAL_TASK["id"]
      and anim.publish_stage(SHOT, anim.ANIM_CODE, ["abc"])[1]["id"] == FINAL_TASK["id"])
check("Layout never Final, even ticked", stage(["abc", "usd"], anim.LAYOUT_CODE) == anim.LAYOUT)
check("cache_formats keeps the list's order", anim.cache_formats(anim.ANIM_CODE, ["usd", "abc"]) == ["abc", "usd"])
print("%d/%d passed" % (sum(ok), len(ok)))
sys.stdout.flush()
os._exit(0 if all(ok) else 1)
