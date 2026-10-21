# Studio Library in the pipe (spec §4b): Set Project makes the student's
# data\studioLibrary\<login>, brings the show library and their own shot
# libraries down from H, and points Studio Library at them; every publish
# backs the whole project's libraries up to H. Only adds, never deletes,
# never writes a newer copy over with an older one, never copies Studio
# Library's own cache. Studio Library's settings go to a temp file here,
# never the real ones. Run: mayapy test_studioLibrary_mayapy.py
import sys, os, json, time, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HERE = os.path.dirname(os.path.abspath(__file__))
PIPE = os.path.dirname(HERE)
sys.path[:0] = [HERE, os.path.join(PIPE, "projectDev"), os.path.join(PIPE, "buildDev")]
SCRIPTS = os.path.join(os.path.expanduser("~"), "Documents", "maya", "scripts")
if os.path.isdir(os.path.join(SCRIPTS, "studiolibrary")) and SCRIPTS not in sys.path:
    sys.path.append(SCRIPTS)
from PySide6 import QtWidgets
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
import maya.standalone; maya.standalone.initialize()
import publishTool_api as pub
import projectTool_api as proj
import pipeStudioLibrary as slib
import studiolibrary

ok = []
def check(label, cond):
    ok.append(bool(cond)); print("PASS" if cond else "FAIL", label)

base = tempfile.mkdtemp(prefix="slib_")
H, SC = os.path.join(base, "H"), os.path.join(base, "scratch")
os.makedirs(SC)
SETTINGS = os.path.join(base, "LibraryWidget.json")
studiolibrary.config.set("settingsPath", SETTINGS)
with open(SETTINGS, "w") as f:      # the student's own library, set up by hand
    json.dump({"Default": {"path": "C:/myPoses", "default": True, "theme": {"name": "x"}}}, f)
pub.who = lambda: "scout"
film = "NWF_SHF"
maya = lambda root: os.path.join(root, film, "maya")


def write(path, text="{}", when=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        os.chmod(path, 0o666)
    with open(path, "w") as f:
        f.write(text)
    if when:
        os.utime(path, (when, when))


for rel in (("sequences", "EAP_010", "EAP_010_010"), ("sequences", "EAP_010", "EAP_010_020"),
            ("assets", "character", "scout")):
    write(os.path.join(maya(H), *(rel + ("workspace.mel",))), "// ws")
    os.makedirs(os.path.join(maya(H), *(rel + ("data",))), exist_ok=True)
with open(os.path.join(H, film, "pipeline.json"), "w") as f:
    json.dump({"film": film, "shotgrid_project_id": 157}, f)
show_h = slib.show_library(H, film)
os.makedirs(os.path.join(show_h, "show", "scout", "keyframe", "face", "pose"))
shared = os.path.join(show_h, "show", "scout", "keyframe", "body", "pose", "wave.pose", "pose.json")
write(shared, '{"by": "anna"}')
anna_shot = os.path.join(maya(H), "sequences", "EAP_010", "EAP_010_010", "data", "studioLibrary",
                         "anna", "run.anim", "anim.json")
write(anna_shot, '{"by": "anna"}')

# -- Set Project on a shot ----------------------------------------------------
shot = ["NWF_SHF", "maya", "sequences", "EAP_010", "EAP_010_010"]
project, done = proj.set_project(H, SC, shot)
mine = os.path.join(project, "data", "studioLibrary", "scout")
check("shot: my data\\studioLibrary\\scout made", os.path.isdir(mine))
check("shot: said so", any("data\\studioLibrary\\scout" in d for d in done))
check("restore: a pose someone shared in the show library came down",
      os.path.isfile(os.path.join(slib.show_library(SC, film), *os.path.relpath(shared, show_h).split(os.sep))))
check("restore: someone else's shot library didn't",
      not os.path.exists(os.path.join(project, "data", "studioLibrary", "anna", "run.anim")))
settings = studiolibrary.readSettings()
show_name, shot_name = slib.library_names(film, "EAP_010_010")
check("Studio Library lists the show library and my shot library",
      settings.get(show_name, {}).get("path") == slib.show_library(SC, film).replace("\\", "/")
      and settings.get(shot_name, {}).get("path") == mine.replace("\\", "/"))
check("my shot library opens by default (and only it)",
      [n for n, e in settings.items() if e.get("default")] == [shot_name])
check("the student's own library is kept, with its settings",
      settings["Default"]["path"] == "C:/myPoses" and settings["Default"]["theme"] == {"name": "x"})
check("Studio Library looks deep enough for show library items",
      studiolibrary.config.get("recursiveSearchDepth") >= 9)

# -- Saving, then publishing (back_up) ----------------------------------------
show_sc = slib.show_library(SC, film)
my_pose = os.path.join(mine, "blocking", "jump.pose", "pose.json")
write(my_pose, '{"by": "scout"}')
write(os.path.join(mine, "blocking", "jump.pose", ".studiolibrary", "metadata.json"), '{"color": "red"}')
write(os.path.join(mine, ".studiolibrary", "database.json"), '{"cache": 1}')
write(os.path.join(show_sc, ".studiolibrary", "database.json"), '{"cache": 1}')
my_share = os.path.join(show_sc, "sequences", "EAP_010", "EAP_010_010", "scout", "mocap", "face",
                        "motion", "talk.anim", "anim.json")
write(my_share, '{"by": "scout"}')
result = slib.back_up(SC, H, film)
on_h = lambda p: os.path.join(H, os.path.relpath(p, SC))
check("backup: my shot pose is on H", os.path.isfile(on_h(my_pose)))
check("backup: its tags/colour (item metadata) went too",
      os.path.isfile(on_h(os.path.join(mine, "blocking", "jump.pose", ".studiolibrary", "metadata.json"))))
check("backup: what I shared in the show library is on H", os.path.isfile(on_h(my_share)))
check("backup: Studio Library's cache never copied",
      not os.path.exists(on_h(os.path.join(mine, ".studiolibrary", "database.json")))
      and not os.path.exists(os.path.join(show_h, ".studiolibrary", "database.json")))
check("backup: times kept, so a second backup copies nothing",
      not slib.back_up(SC, H, film)["copied"])
check("describe says how many", "backed up" in slib.describe(result, "backed up to the H drive"))

# -- Newer wins, nothing deleted ----------------------------------------------
now = time.time()
write(on_h(my_share), '{"by": "anna, improved"}', when=now + 60)     # someone else, later
write(my_share, '{"by": "scout, old copy"}', when=now)
result = slib.back_up(SC, H, film)
check("an older scratch copy never replaces a newer H copy",
      json.load(open(on_h(my_share)))["by"] == "anna, improved" and result["kept"])
check("... and the student is told", "newer" in slib.describe(result, "backed up"))
write(my_pose, '{"by": "scout, v2"}', when=now + 120)
slib.back_up(SC, H, film)
check("a newer scratch copy does replace the H copy", json.load(open(on_h(my_pose)))["by"] == "scout, v2")
os.remove(my_pose)
slib.back_up(SC, H, film)
check("deleting on scratch never deletes on H", os.path.isfile(on_h(my_pose)))
proj.set_project(H, SC, shot)
check("restore brings a newer H copy down", json.load(open(my_share))["by"] == "anna, improved")
check("... and the deleted item comes back (removing for good is a staff job on H)",
      os.path.isfile(my_pose))

# -- Wiped scratch ------------------------------------------------------------
import shutil
shutil.rmtree(os.path.join(SC, film))
proj.set_project(H, SC, shot)
check("after a wipe, Set Project brings my shot work back", os.path.isfile(my_pose))

# -- Switching project --------------------------------------------------------
proj.set_project(H, SC, ["NWF_SHF", "maya", "sequences", "EAP_010", "EAP_010_020"])
settings = studiolibrary.readSettings()
_, shot2 = slib.library_names(film, "EAP_010_020")
check("another shot: its library replaces the last shot's",
      shot2 in settings and shot_name not in settings and show_name in settings)
check("... still one default", [n for n, e in settings.items() if e.get("default")] == [shot2])
proj.set_project(H, SC, ["NWF_SHF", "maya", "assets", "character", "scout"])
settings = studiolibrary.readSettings()
check("an asset: no shot library, the show library opens by default",
      not any(n.endswith("(mine)") for n in settings)
      and [n for n, e in settings.items() if e.get("default")] == [show_name])
check("an asset project gets no data\\studioLibrary",
      not os.path.exists(os.path.join(maya(SC), "assets", "character", "scout", "data", "studioLibrary")))

# -- Project Tool banner, startup config ---------------------------------------
for i in range(40):
    os.makedirs(os.path.join(show_h, "sequences", "EAP_010", "EAP_010_020", "char%d" % i))
diff = proj.structure_diff(H, SC, film)
check("banner: library folders aren't structure (no nagging when someone shares a pose)",
      not any(slib.FOLDER in r for r in diff["missing"]) and not proj.describe_diff(diff))
check("the 1:1 folder mirror never made empty shells of other people's items",
      not os.path.exists(os.path.join(project, "data", "studioLibrary", "anna")))
os.environ.pop("STUDIO_LIBRARY_CONFIG_PATH", None)
path = slib.use_config(base)
check("startup: Studio Library config with the deeper search",
      json.load(open(path))["recursiveSearchDepth"] == slib.SEARCH_DEPTH
      and os.environ["STUDIO_LIBRARY_CONFIG_PATH"] == path)
os.environ["STUDIO_LIBRARY_CONFIG_PATH"] = "C:/someone/else.json"
check("startup: someone else's Studio Library config is left alone",
      slib.use_config(base) == "C:/someone/else.json")
check("the real Studio Library settings were never used",
      studiolibrary.settingsPath().replace("\\", "/") == SETTINGS.replace("\\", "/"))
print("%d/%d passed" % (sum(ok), len(ok)))
