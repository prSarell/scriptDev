# One folder layout on scratch and H (spec §4g, user 2026-11-23): every
# publish goes in <asset or shot>\scenes\<department>\<login>\, the same path
# as the working folder on scratch; versions count across the old
# scenes\<login>\ too; Build reads both; the Project Tool still copies H's
# folders 1:1 (other people's included) but never the old scenes\<login>\.
# Run: mayapy test_deptFolders_mayapy.py
import sys, os, shutil, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
for sub in ("", "../buildDev", "../projectDev"):
    sys.path.insert(0, os.path.normpath(os.path.join(HERE, sub)))
import maya.standalone; maya.standalone.initialize()
import maya.cmds as cmds
import publishTool_api as api
import publishTool_camera as cam
import publishTool_anim as anim
import publishTool_env as env
import publishTool_textures as tex
import buildTool_api as build
import projectTool_api as project
api.who = lambda: "e131988"
api.artist_name = lambda login: "Test Person"

ok = []
def check(label, cond):
    ok.append(bool(cond)); print("PASS" if cond else "FAIL", label)

def refuses(call, *args, **kw):
    try:
        call(*args, **kw)
    except (api.PublishError, ValueError) as e:
        return str(e) or True
    return False

def touch(path):
    if not os.path.isdir(os.path.dirname(path)):
        os.makedirs(os.path.dirname(path))
    open(path, "w").close()
    return path

base = tempfile.mkdtemp(prefix="deptFolders_")
H, SC = os.path.join(base, "H"), os.path.join(base, "scratch")
FILM = "NWF_SHF"
shed = [FILM, "maya", "assets", "environment", "shed"]
chair = [FILM, "maya", "assets", "prop", "chair"]
shot = [FILM, "maya", "sequences", "SEQ010", "SEQ010_160"]
for root in (H, SC):
    for rel in (shed, chair, shot):
        os.makedirs(os.path.join(root, *(rel + ["scenes"])))
j = lambda *p: os.path.normcase(os.path.normpath(os.path.join(*p)))
same = lambda a, b: os.path.normcase(os.path.normpath(a)) == os.path.normcase(os.path.normpath(b))

# --- the helpers -----------------------------------------------------------------
check("DEPT_FOLDERS: the locked departments' codes",
      api.DEPT_FOLDERS == ("model", "rig", "creature", "lookDev", "layout", "anim", "fx",
                           "lighting"))
check("personal_folder: scenes\\<dept>\\<login>",
      same(api.personal_folder(H, shot, "e131988", "anim"),
           os.path.join(H, *(shot + ["scenes", "anim", "e131988"]))))
check("personal_folder: refuses something that isn't a department",
      refuses(api.personal_folder, H, shot, "e131988", "e131988"))
check("scene_department: the folder after scenes, as its code",
      api.scene_department(shot + ["scenes", "ANIM", "e131988", "x.ma"]) == "anim"
      and api.scene_department(chair + ["scenes", "lookdev", "e131988", "x.ma"]) == "lookDev"
      and api.scene_department(shot + ["scenes", "x.ma"]) is None
      and api.scene_department(shot + ["scenes", "New Folder", "x.ma"]) is None)

# --- asset publish: scenes\<code>\<login>, versions across the old folder ----------
for v in (1, 2, 3):
    touch(os.path.join(H, *(chair + ["scenes", "e131988", "chair_e131988_model_v%03d.ma" % v])))
work = touch(os.path.join(SC, *(chair + ["scenes", "model", "e131988", "chairWork.ma"])))
plan = api.plan_publish(work, H, SC, "model")
check("asset publish goes in scenes\\model\\e131988 on H",
      same(plan["h_folder"], os.path.join(H, *(chair + ["scenes", "model", "e131988"]))))
check("... v004: the old folder's v001-v003 are counted", plan["version"] == 4
      and plan["dest"].endswith("chair_e131988_model_v004.ma"))
rig_plan = api.plan_publish(work, H, SC, "rig")
check("a Rigging publish of the same asset goes in scenes\\rig\\, its own v001",
      same(rig_plan["h_folder"], os.path.join(H, *(chair + ["scenes", "rig", "e131988"])))
      and rig_plan["version"] == 1)
check("textures: <asset>\\sourceimages\\<login>\\<published name>",
      same(tex.texture_folder(plan), os.path.join(H, *(chair + [
          "sourceimages", "e131988", "chair_e131988_model_v004"]))))
old_plan = dict(plan, h_folder=os.path.join(H, *(chair + ["scenes", "e131988"])))
check("textures: an old-folder plan still finds the asset folder",
      same(tex.texture_folder(old_plan), os.path.join(H, *(chair + [
          "sourceimages", "e131988", "chair_e131988_model_v004"]))))

# --- environment: Modeling, from a shot or an asset --------------------------------
touch(os.path.join(H, *(shed + ["scenes", "e131988", "shed_e131988_model_v002.ma"])))
in_shot = touch(os.path.join(SC, *(shot + ["scenes", "layout", "e131988", "setDress.ma"])))
eplan = env.plan_environment(in_shot, H, SC, ("environment", "shed"))
check("environment publish goes in shed\\scenes\\model\\e131988, v003 after the old v002",
      same(eplan["h_folder"], os.path.join(H, *(shed + ["scenes", "model", "e131988"])))
      and eplan["version"] == 3)

# --- shots: camera by the scene's folder, anim / layout by the stage ---------------
touch(os.path.join(H, *(shot + ["scenes", "e131988", "SEQ010_160_e131988_cam_v001.ma"])))
anim_scene = touch(os.path.join(SC, *(shot + ["scenes", "anim", "e131988", "setUP_v012.ma"])))
cplan = cam.plan_camera(anim_scene, H, SC)
check("a camera published from an anim scene goes in scenes\\anim\\e131988, v002",
      same(cplan["h_folder"], os.path.join(H, *(shot + ["scenes", "anim", "e131988"])))
      and cplan["version"] == 2 and cplan["department"] == "anim")
layout_scene = touch(os.path.join(SC, *(shot + ["scenes", "layout", "e131988", "lay.ma"])))
check("a camera published for Animation goes in scenes\\anim\\, even from a layout scene",
      same(cam.plan_camera(layout_scene, H, SC, department="anim")["h_folder"],
           os.path.join(H, *(shot + ["scenes", "anim", "e131988"]))))
check("... and with no stage given, the scene's folder: scenes\\layout\\",
      same(cam.plan_camera(layout_scene, H, SC)["h_folder"],
           os.path.join(H, *(shot + ["scenes", "layout", "e131988"]))))
loose = touch(os.path.join(SC, *(shot + ["scenes", "loose.ma"])))
check("a camera from a scene in no department folder publishes as Layout",
      same(cam.plan_camera(loose, H, SC)["h_folder"],
           os.path.join(H, *(shot + ["scenes", "layout", "e131988"]))))
touch(os.path.join(H, *(shot + ["scenes", "e131988", "SEQ010_160_e131988_anim_v001.ma"])))
aplan = anim.plan_anim(anim_scene, H, SC)
check("an Animation publish goes in scenes\\anim\\e131988, v002 after the old v001",
      same(aplan["h_folder"], os.path.join(H, *(shot + ["scenes", "anim", "e131988"])))
      and aplan["version"] == 2 and aplan["dest"].endswith("SEQ010_160_e131988_anim_v002.ma"))
check("... its caches go in cache\\alembic\\anim\\e131988",
      same(aplan["cache_folder"], os.path.join(H, *(shot + ["cache", "alembic", "anim",
                                                            "e131988"]))))
lplan = anim.plan_anim(anim_scene, H, SC, publish_for=anim.LAYOUT_CODE)
check("a Layout publish goes in scenes\\layout\\e131988, from any scene",
      same(lplan["h_folder"], os.path.join(H, *(shot + ["scenes", "layout", "e131988"])))
      and lplan["version"] == 1)
check("planning wrote nothing on H",
      not os.path.exists(os.path.join(H, *(shot + ["scenes", "anim", "e131988"]))))

# --- Build reads the old and the new folders --------------------------------------
touch(os.path.join(H, *(chair + ["scenes", "model", "e131988", "chair_e131988_model_v004.ma"])))
touch(os.path.join(H, *(chair + ["scenes", "rig", "s7654321", "chair_s7654321_rig_v001.ma"])))
touch(os.path.join(H, *(chair + ["scenes", "model", "e131988", "chair_s7654321_model_v009.ma"])))
found = dict(((p["asset"], p["code"]), p) for p in build.list_published(H, FILM))
model_versions = sorted(found[("chair", "model")]["versions"])
check("Build lists the model's old v001-v003 and new v004",
      model_versions == ["e131988/v001", "e131988/v002", "e131988/v003", "e131988/v004"])
check("... and another person's rig in scenes\\rig\\s7654321",
      list(found[("chair", "rig")]["versions"]) == ["s7654321/v001"])
check("... but not a file whose login doesn't match its folder", all(
      "s7654321/v009" not in p["versions"] for p in found.values()))
stamp = {"assetType": "prop", "asset": "chair", "department": "model",
         "artistId": "e131988", "version": 4}
check("a stamp finds its publish in the new folder",
      same(build._published_source(H, FILM, stamp) or "",
           os.path.join(H, *(chair + ["scenes", "model", "e131988",
                                      "chair_e131988_model_v004.ma"]))))
check("... and one in the old folder",
      same(build._published_source(H, FILM, dict(stamp, version=2)) or "",
           os.path.join(H, *(chair + ["scenes", "e131988", "chair_e131988_model_v002.ma"]))))
cams = cam.camera_file_names("SEQ010_160", "e131988", 3)
for folder in (["scenes", "anim", "e131988"], ["scenes", "e131988"]):
    v = 3 if "anim" in folder else 1
    names = cam.camera_file_names("SEQ010_160", "e131988", v)
    for key in ("camera", "keys"):
        touch(os.path.join(H, *(shot + folder + [names[key]])))
    with open(os.path.join(H, *(shot + folder + [names["map"]])), "w") as f:
        f.write('{"format": %d}' % build.CAMERA_MAP_FORMAT)
shot_cams = build.list_shot_cameras(H, FILM, "SEQ010", "SEQ010_160")
check("Build lists cameras from scenes\\anim\\ and the old folder",
      shot_cams and sorted(shot_cams[0]["files"]) == ["e131988/v001", "e131988/v003"])
for folder, v in ((["cache", "alembic", "anim", "e131988"], 2),
                  (["cache", "alembic", "e131988"], 1)):
    abc = touch(os.path.join(H, *(shot + folder + ["SEQ010_160_crate_anim_v%03d.abc" % v])))
    with open(os.path.splitext(abc)[0] + ".json", "w") as f:
        f.write('{"item": "crate"}')
caches = build.list_shot_caches(H, FILM, "SEQ010", "SEQ010_160")
check("Build lists caches from cache\\alembic\\anim\\ and the old folder",
      caches and sorted(caches[0]["versions"]) == ["e131988/v001", "e131988/v002"])

# --- the Project Tool: 1:1, other people's folders included, never scenes\<login> --
os.makedirs(os.path.join(H, *(shot + ["scenes", "anim", "s7654321"])))
diff = project.structure_diff(H, SC, FILM)
missing = set(diff["missing"])
check("structure copy brings everyone's scenes\\<dept>\\<login>\\ (1:1, user 2026-11-23)",
      tuple(shot + ["scenes", "anim", "s7654321"]) in missing
      and tuple(chair + ["scenes", "rig", "s7654321"]) in missing)
check("... but never the old scenes\\<login>\\ publish folder",
      tuple(chair + ["scenes", "e131988"]) not in missing
      and tuple(shot + ["scenes", "e131988"]) not in missing)

shutil.rmtree(base, ignore_errors=True)
print("%d/%d passed" % (sum(ok), len(ok)))
