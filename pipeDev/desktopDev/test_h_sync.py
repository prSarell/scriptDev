# h_sync (staff desktop tool, first piece): plain Python, no Maya, no
# ShotGrid connection needed (ShotGrid's answers are faked). Run with any
# Python 3 on Windows or macOS:  python test_h_sync.py
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import h_sync

ok = []
def check(label, cond):
    ok.append(bool(cond)); print("PASS" if cond else "FAIL", label)

check("names: Scout's House / AT-KS / bakedBeans_Can / scoutsHouse_landscape",
      [h_sync.asset_folder_name(c) for c in ("Scout's House", "AT-KS", "bakedBeans_Can", "scoutsHouse_landscape")]
      == ["scoutsHouse", "ATKS", "bakedBeansCan", "scoutsHouseLandscape"])

H = tempfile.mkdtemp(prefix="hsync_")
film = "TST_SHF"
maya = os.path.join(H, film, "maya")
for rel in (("assets", "prop", "backpack"), ("sequences", "SEQ010", "SEQ010_010")):
    p = os.path.join(maya, *rel)
    for sub in (("scenes", "anna"), ("images",), ("cache", "alembic")):
        os.makedirs(os.path.join(p, *sub))
    open(os.path.join(p, "workspace.mel"), "w").write("// layout\n")
    open(os.path.join(p, "scenes", "anna", "work.ma"), "w").write("// someone's work\n")
os.makedirs(os.path.join(maya, "assets", "prop", "oldThing"))
shots = [{"code": "SEQ010_010", "sequence": "SEQ010"}, {"code": "SEQ010_020", "sequence": "SEQ010"},
         {"code": "SEQ010_FULL_CUT", "sequence": "SEQ010"}, {"code": "LOOSE_010", "sequence": None}]
assets = [{"code": "Backpack", "type": "Prop"}, {"code": "Scout's House", "type": "Environment"},
          {"code": "Style Guide", "type": "Graphic"}, {"code": "Mystery", "type": None}]
plan = h_sync.plan_sync(H, film, shots, assets)
check("only what's new gets built", sorted(l for _, l, _ in plan["build"]) == [
    "SEQ010_020", "Scout's House (Environment)"])
check("reference shots, no sequence, Graphic, no type: skipped with a reason",
      sorted(l for l, _ in plan["skipped"]) == ["LOOSE_010", "Mystery", "SEQ010_FULL_CUT", "Style Guide"])
check("folder not in ShotGrid reported, not touched",
      [os.path.basename(p) for p in plan["not_in_shotgrid"]] == ["oldThing"])
logs = []
built = h_sync.apply_sync(H, film, plan, log=logs.append)
house = os.path.join(maya, "assets", "environment", "scoutsHouse")
check("built with the film's layout and workspace.mel",
      os.path.isfile(os.path.join(house, "workspace.mel")) and os.path.isdir(os.path.join(house, "cache", "alembic"))
      and os.path.isfile(os.path.join(maya, "sequences", "SEQ010", "SEQ010_020", "workspace.mel")))
check("no files or people's folders copied",
      not os.path.exists(os.path.join(house, "scenes", "anna"))
      and [f for _, _, fs in os.walk(house) for f in fs] == ["workspace.mel"])
check("second run: nothing to build", not h_sync.plan_sync(H, film, shots, assets)["build"])
open(os.path.join(house, "workspace.mel"), "w").write("// edited")
try:
    h_sync.build_project(h_sync.template_project(H, film, "asset"), house)
    check("never writes over an existing folder", False)
except RuntimeError:
    check("never writes over an existing folder", open(os.path.join(house, "workspace.mel")).read() == "// edited")
check("case differences count as the same folder (macOS)",
      h_sync._key(os.path.join(maya, "assets", "prop", "Backpack")) == h_sync._key(os.path.join(maya, "assets", "prop", "backpack")))
# -- Studio Library show folders (spec §4b) ----------------------------------
chars = assets + [{"code": "Scout", "type": "Character"}, {"code": "Willie Wagtail", "type": "Character"}]
plan = h_sync.plan_sync(H, film, shots, chars)
lib = os.path.join(maya, "studioLibrary")
check("library: characters from ShotGrid, folder-named", plan["characters"] == ["scout", "willieWagtail"])
check("library: 2 characters x (show + 2 shots) x 8 end folders",
      len(plan["library"]) == 2 * 3 * 8)
check("library: no folders for reference or sequence-less shots",
      not any("FULL_CUT" in p or "LOOSE" in p for p in plan["library"]))
h_sync.apply_sync(H, film, plan, log=logs.append)
check("library: show + shot folders built",
      os.path.isdir(os.path.join(lib, "show", "scout", "keyframe", "face", "pose"))
      and os.path.isdir(os.path.join(lib, "sequences", "SEQ010", "SEQ010_020", "willieWagtail",
                                     "mocap", "body", "motion")))
pose = os.path.join(lib, "show", "scout", "keyframe", "face", "pose", "smile.pose")
os.makedirs(pose)
open(os.path.join(pose, "pose.json"), "w").write("{}")
plan = h_sync.plan_sync(H, film, shots, chars)
check("library: second run adds nothing", not plan["library"])
h_sync.apply_sync(H, film, plan, log=logs.append)
check("library: what students saved is never touched", os.path.isfile(os.path.join(pose, "pose.json")))
plan = h_sync.plan_sync(H, film, shots, chars + [{"code": "ATKS", "type": "Character"}])
check("library: a new character gets folders everywhere, the rest left as is",
      len(plan["library"]) == 3 * 8 and all(os.sep + "ATKS" + os.sep in p for p in plan["library"]))
check("Maya never loaded", not any(m == "maya" or m.startswith("maya.") for m in sys.modules))
print("%d/%d passed" % (sum(ok), len(ok)))
