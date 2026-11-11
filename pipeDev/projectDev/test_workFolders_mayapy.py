# Asset working folders (user, 2026-10-28): scenes\model, rig, creature and
# lookDev, each with a folder per person (never scenes\<login> on scratch,
# 2026-11-11); staff named by their
# e-number (shotgrid_as) instead of the machine's Windows login. Set
# Project makes the person's folders, Save Here uses the department's,
# Build never mistakes a working file for a publish. ShotGrid not needed.
# Run: mayapy test_workFolders_mayapy.py
import sys, os, getpass, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
PIPE = os.path.dirname(HERE)
sys.path[:0] = [HERE, os.path.join(PIPE, "publishDev"), os.path.join(PIPE, "buildDev")]
import maya.standalone; maya.standalone.initialize()
import publishTool_api as pub
import projectTool_api as api
import buildTool_api as build

ok = []
def check(label, cond):
    ok.append(bool(cond)); print("PASS" if cond else "FAIL", label)

base = tempfile.mkdtemp(prefix="workfolders_")
try:
    import studiolibrary
    studiolibrary.config.set("settingsPath", os.path.join(base, "LibraryWidget.json"))
except ImportError:
    pass
# Throwaway settings: never the real Maya prefs pipeline_config.json.
_cfg = os.path.join(base, "pipeline_config.json")
pub._config_path = lambda: _cfg

# -- who: publish_as, else shotgrid_as, else the Windows login -------------
pub.save_config({})
check("who: the Windows login by default", pub.who() == pub.clean_login(getpass.getuser()))
pub.save_config({"shotgrid_as": "E131988"})
check("who: shotgrid_as (staff e-number) beats the Windows login", pub.who() == "e131988")
pub.save_config({"shotgrid_as": "e131988", "publish_as": "s1234567"})
check("who: publish_as beats shotgrid_as", pub.who() == "s1234567")
pub.save_config({"shotgrid_as": "e131988"})
check("Project Tool finds staff in ShotGrid by the same number", api.rmit_id() == "e131988")

# -- Set Project makes the person's folders ----------------------------------
H, SC = os.path.join(base, "H"), os.path.join(base, "scratch")
os.makedirs(SC)


def project(*rel):
    path = os.path.join(H, "NWF_SHF", "maya", *rel)
    for sub in ("scenes", "images"):
        os.makedirs(os.path.join(path, sub), exist_ok=True)
    with open(os.path.join(path, "workspace.mel"), "w") as f:
        f.write('workspace -fr "scene" "scenes";\n')
    return path


asset_h = project("assets", "character", "scout")
for w in pub.WORK_FOLDERS:
    os.makedirs(os.path.join(asset_h, "scenes", w))
project("sequences", "EAP_010", "EAP_010_010")
with open(os.path.join(H, "NWF_SHF", "pipeline.json"), "w") as f:
    f.write('{"film": "NWF_SHF", "shotgrid_project_id": 157}')

path, done = api.set_project(H, SC, ["NWF_SHF", "maya", "assets", "character", "scout"])
check("asset: model, rig, creature and lookDev\\e131988",
      all(os.path.isdir(os.path.join(path, "scenes", *p)) for p in
          (("model", "e131988"), ("rig", "e131988"), ("creature", "e131988"),
           ("lookDev", "e131988"))))
check("asset: no scenes\\e131988 on scratch (publishes only, on the H drive)",
      not os.path.exists(os.path.join(path, "scenes", "e131988")))
check("... and says so", any("rig\\e131988" in d for d in done))
shot, _ = api.set_project(H, SC, ["NWF_SHF", "maya", "sequences", "EAP_010", "EAP_010_010"])
check("shot: layout, anim, fx and lighting\\e131988, no asset ones, no scenes\\e131988",
      all(os.path.isdir(os.path.join(shot, "scenes", *p)) for p in
          (("layout", "e131988"), ("anim", "e131988"), ("fx", "e131988"),
           ("lighting", "e131988")))
      and not os.path.exists(os.path.join(shot, "scenes", "model"))
      and not os.path.exists(os.path.join(shot, "scenes", "e131988")))

# -- Save Here's folder --------------------------------------------------------
check("work_folder: every department its own, Creature too; never scenes\\<login>",
      [os.path.relpath(pub.work_folder(path, c, "e131988"), path)
       for c in ("model", "rig", "creature", "lookDev")]
      == [os.path.join("scenes", c, "e131988") for c in ("model", "rig", "creature", "lookDev")])
check("work_folder: shot departments get their own",
      [os.path.relpath(pub.work_folder(shot, c, "e131988"), shot) for c in ("anim", "lighting")]
      == [os.path.join("scenes", "anim", "e131988"), os.path.join("scenes", "lighting", "e131988")])

# -- Project Tool names someone's new working folder on the H drive --------
os.makedirs(os.path.join(asset_h, "scenes", "rig", "s7654321"))
os.makedirs(os.path.join(asset_h, "scenes", "s1111111"))
# Maya's own folder inside scenes (workspace offlineEdit rule): still structure.
os.makedirs(os.path.join(asset_h, "scenes", "edits"))
with open(os.path.join(asset_h, "workspace.mel"), "a") as f:
    f.write('workspace -fr "offlineEdit" "scenes/edits";\n')
shot_h = os.path.join(H, "NWF_SHF", "maya", "sequences", "EAP_010", "EAP_010_010")
os.makedirs(os.path.join(shot_h, "scenes", "lighting", "s2222222"))
diff = api.structure_diff(H, SC, "NWF_SHF")
check("a new person in scenes\\rig or a shot's scenes\\lighting is named, not "
      "'lighting' itself", api.describe_diff(diff) ==
      "new people's folders: s2222222 (in EAP_010_010), s7654321 (in scout); "
      "1 other new folder(s)")
check("someone's scenes\\<login> publish folder on H isn't mirrored to scratch",
      not any(r[-1] == "s1111111" for r in diff["missing"]))
api.update_structure(H, SC, "NWF_SHF", diff)
check("... and Update leaves scratch without it",
      not os.path.exists(os.path.join(path, "scenes", "s1111111"))
      and os.path.isdir(os.path.join(path, "scenes", "rig", "s7654321")))
check("... but Maya's scenes\\edits (workspace offlineEdit rule) is still mirrored",
      os.path.isdir(os.path.join(path, "scenes", "edits")))

# -- Build lists publishes only ----------------------------------------------
pubs = os.path.join(asset_h, "scenes", "e131988")
os.makedirs(pubs)
open(os.path.join(pubs, "scout_e131988_rig_v001.ma"), "w").write("//")
# A working file that happens to look like a publish.
work = os.path.join(asset_h, "scenes", "rig", "e131988")
os.makedirs(work)
open(os.path.join(work, "scout_e131988_rig_v009.ma"), "w").write("//")
found = build.list_published(H, "NWF_SHF")
check("Build: the publish is listed, the working file in scenes\\rig isn't",
      [sorted(e["versions"]) for e in found] == [["e131988/v001"]])
# Same in a shot: a camera-publish lookalike in scenes\anim\<login>.
cam_work = os.path.join(shot_h, "scenes", "anim", "e131988")
os.makedirs(cam_work)
for name in ("EAP_010_010_e131988_cam_v001.ma", "EAP_010_010_e131988_camAnim_v001.ma",
             "EAP_010_010_e131988_camAnim_v001.json"):
    open(os.path.join(cam_work, name), "w").write("{}")
shot_pubs = os.path.join(shot_h, "scenes", "e131988")
os.makedirs(shot_pubs, exist_ok=True)
open(os.path.join(shot_pubs, "EAP_010_010_e131988_anim_v001.ma"), "w").write("//")
seen = [n for _, names in build._walk_shot_publishes(os.path.join(shot_h, "scenes")) for n in names]
check("Build: a shot's publishes are looked at, its scenes\\anim etc. working files aren't",
      seen == ["EAP_010_010_e131988_anim_v001.ma"])
print("%d/%d passed" % (sum(ok), len(ok)))
