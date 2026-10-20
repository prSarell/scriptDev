# Camera publish records the shot's frame range from the latest edit on
# ShotGrid (user 2026-10-20): newest Cut holding the shot wins (head/tail
# from the Shot), else the Shot's cut fields, else nothing + a warning.
# Fake ShotGrid; no network. Run: mayapy test_cameraEditRange_mayapy.py
import sys, os
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import maya.standalone; maya.standalone.initialize()
import publishTool_camera as cam
ok = []
def check(label, cond): ok.append(bool(cond)); print("PASS" if cond else "FAIL", label)


class FakeSG(object):
    def __init__(self, shot, items):
        self.shot, self.items = shot, items
    def find_one(self, entity, filters, fields):
        return dict(self.shot)
    def find(self, entity, filters, fields):
        return [dict(i) for i in self.items]


def item(cut_id, code, day, cin, cout):
    return {"cut": {"type": "Cut", "id": cut_id}, "cut.Cut.code": code,
            "cut.Cut.created_at": datetime(2026, 10, day, 12, 0), "cut_item_in": cin,
            "cut_item_out": cout, "cut_item_duration": cout - cin + 1, "edit_in": 100,
            "edit_out": 100 + cout - cin, "cut_order": 3}


SHOT = {"sg_cut_in": 5, "sg_cut_out": 50, "sg_cut_duration": 46, "sg_cut_order": 9,
        "sg_head_in": -8, "sg_tail_out": 58}
NO_CUT = dict((k, None) for k in SHOT)
S = {"type": "Shot", "id": 1}

e = cam.shot_edit_range(FakeSG(SHOT, [item(1, "old_v001", 5, 0, 99), item(2, "new_v002", 15, 0, 79),
                                      item(3, "mid_v003", 10, 0, 49)]), S)
check("newest Cut wins (by date, not by id)", e["source"] == "cut" and e["cut"] == "new_v002" and e["cutId"] == 2)
check("frames from the Cut item", (e["cutIn"], e["cutOut"], e["cutDuration"], e["editIn"]) == (0, 79, 80, 100))
check("head/tail from the Shot", (e["headIn"], e["tailOut"]) == (-8, 58))

e = cam.shot_edit_range(FakeSG(SHOT, []), S)
check("no Cut: the Shot's own cut fields", e["source"] == "shot" and (e["cutIn"], e["cutOut"], e["cutOrder"]) == (5, 50, 9))

e = cam.shot_edit_range(FakeSG(NO_CUT, []), S)
check("nothing on ShotGrid: source none, no frame fields", e == {"source": "none", "cut": ""})
check("nothing -> warning, not a refusal", "no edit range" in cam.edit_range_warning(e, 1001, 1080))

e = cam.shot_edit_range(FakeSG(SHOT, [item(2, "new_v002", 15, 0, 79)]), S)
check("timeline matches the edit length -> no warning", cam.edit_range_warning(e, 1001, 1080) is None)
check("timeline a different length -> warning names the Cut",
      "new_v002" in (cam.edit_range_warning(e, 1001, 1100) or ""))

plan = {"shot": "EAP_010_010", "version": 3, "login": "scout", "sg_shot": {"id": 1}, "edit_range": e}
cam.api.artist_name = lambda login: "Scout Test"
stamp = dict(cam.camera_stamp(plan, r"D:\x.ma", [], 1001, 1080))
check("stamp: baked range + edit range + which Cut",
      (stamp["frameStart"], stamp["frameEnd"], stamp["editSource"], stamp["editCut"], stamp["editCutId"],
       stamp["cutIn"], stamp["cutOut"], stamp["headIn"], stamp["tailOut"])
      == (1001, 1080, "cut", "new_v002", 2, 0, 79, -8, 58))
stamp = dict(cam.camera_stamp(dict(plan, edit_range=None), r"D:\x.ma", [], 1001, 1080))
check("no edit range: stamp says none, no frame fields", stamp["editSource"] == "none" and "cutIn" not in stamp)

print("\n%d/%d passed" % (sum(ok), len(ok)))
