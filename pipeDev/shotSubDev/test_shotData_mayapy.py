r"""Headless test: shotSub / Jiffy shot data lives in the project's data
folder, not beside the scenes (user, 2026-10-30).

    "C:\Program Files\Autodesk\Maya2025\bin\mayapy.exe" pipeDev/shotSubDev/test_shotData_mayapy.py

A scene in <project>\scenes\<rel> keeps its data in <project>\data\<tool>\<rel>:
    shotSub + Jiffy SG link and publish log -> data\shotgrid\<rel>
    JiffyPomo tasks + summary               -> data\jiffyShotData\<rel>
JiffyPomo's show data (prompts, notes) stays in ~\jiffyData. Files left by
the old tools are copied across the first time. Throwaway folders in %TEMP%.
"""
import os, sys, json, shutil, tempfile

import maya.standalone
maya.standalone.initialize()
import maya.cmds as cmds

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path[:0] = [os.path.join(ROOT, "shelfDev", "mpAnim", "tools"),
                os.path.join(ROOT, "timeManagementDev", "jiffyPomoDev"),
                os.path.join(ROOT, "timeManagementDev", "jiffySGDev")]
import shotSub
import jiffyUtils
import jiffySG

results = []


def check(name, ok):
    results.append(bool(ok)); print(("PASS " if ok else "FAIL ") + name)


base = tempfile.mkdtemp(prefix="shotdata_")


def project(name, rel):
    """A Maya project with a saved scene in scenes\\<rel>; returns the scene folder."""
    proj = os.path.join(base, name)
    scene_dir = os.path.join(proj, "scenes", *rel)
    os.makedirs(scene_dir)
    open(os.path.join(proj, "workspace.mel"), "w").write('workspace -fr "scene" "scenes";\n')
    cmds.workspace(proj, openWorkspace=True)
    cmds.file(new=True, force=True)
    cmds.file(rename=os.path.join(scene_dir, "shot.ma"))
    cmds.file(save=True, type="mayaAscii")
    return proj, scene_dir


tool = shotSub.ShotSub.__new__(shotSub.ShotSub)     # the paths need no UI

# --- one project for the whole film (students off the pipe)
proj, scene_dir = project("film", ["seq010", "sh010"])
want = os.path.join(proj, "data", "shotgrid", "seq010", "sh010")
check("shotSub: data\\shotgrid\\<seq>\\<shot>",
      os.path.normcase(tool.get_shot_data_folder()) == os.path.normcase(want))
link = tool.write_shotgrid_link(1, "Film", "Shot", 42, "sh010")
check("shotSub: link written to the data folder",
      os.path.isfile(os.path.join(want, "shotgrid_link.json")))
check("shotSub: nothing beside the scenes",
      not os.path.exists(os.path.join(scene_dir, "shotgrid_link.json")))
check("shotSub: link reads back", tool.read_shotgrid_link()["sg_entity_id"] == 42)
tool.mark_version_published("v001", 7)
check("shotSub: publish log in the data folder", tool.is_version_published("v001")
      and os.path.isfile(os.path.join(want, "shotgrid_publish_log.json")))
check("Jiffy SG maps a picked scene folder to the same place",
      os.path.normcase(jiffySG._shotgrid_data_folder(scene_dir)) == os.path.normcase(want))
check("Jiffy SG: a folder outside scenes\\ keeps the link in place",
      jiffySG._shotgrid_data_folder(base) == base)

# --- a shot linked by the old shotSub: copied across, old file left alone
proj, scene_dir = project("oldfilm", ["seq010", "sh020"])
old_link = os.path.join(scene_dir, "shotgrid_link.json")
json.dump({"schema_version": 2, "sg_entity_type": "Shot", "sg_entity_id": 99}, open(old_link, "w"))
json.dump({"v003": {"sg_version_id": 5}}, open(os.path.join(scene_dir, "shotgrid_publish_log.json"), "w"))
check("old link still found", (tool.read_shotgrid_link() or {}).get("sg_entity_id") == 99)
check("old publish log still found", tool.is_version_published("v003"))
new_dir = os.path.join(proj, "data", "shotgrid", "seq010", "sh020")
check("both copied to the data folder, old ones left",
      os.path.isfile(os.path.join(new_dir, "shotgrid_link.json"))
      and os.path.isfile(os.path.join(new_dir, "shotgrid_publish_log.json"))
      and os.path.isfile(old_link))

# --- the pipe: the project is the shot, scenes\anim\<login>
proj, scene_dir = project("SEQ010_140", ["anim", "e131988"])
check("pipe: data\\shotgrid\\anim\\<login>",
      os.path.normcase(tool.get_shot_data_folder()) == os.path.normcase(
          os.path.join(proj, "data", "shotgrid", "anim", "e131988")))

# --- JiffyPomo shot data
proj, scene_dir = project("pomo", ["seq010", "sh030"])
tasks = jiffyUtils.shot_data_file(scene_dir, "jiffypomo_tasks.json")
check("JiffyPomo: tasks in data\\jiffyShotData\\<seq>\\<shot>",
      os.path.normcase(tasks) == os.path.normcase(os.path.join(
          proj, "data", "jiffyShotData", "seq010", "sh030", "jiffypomo_tasks.json")))
old = os.path.join(scene_dir, "jiffyShotData")
os.makedirs(old)
json.dump({"stage": "blocking"}, open(os.path.join(old, "jiffypomo_summary.json"), "w"))
summary = jiffyUtils.shot_data_file(scene_dir, "jiffypomo_summary.json")
check("JiffyPomo: old summary copied across",
      json.load(open(summary)) == {"stage": "blocking"} and summary.startswith(os.path.join(proj, "data")))
loose = os.path.join(base, "loose")
check("JiffyPomo: a scene outside scenes\\ keeps the old place",
      jiffyUtils.shot_data_file(loose, "jiffypomo_tasks.json")
      == os.path.join(loose, "jiffyShotData", "jiffypomo_tasks.json"))
check("JiffyPomo: show data stays in ~\\jiffyData",
      os.path.dirname(jiffyUtils.DEFAULT_PROMPTS_FILE) == jiffyUtils.DEFAULT_LOCAL_DATA_DIR
      and os.path.dirname(jiffyUtils.DEFAULT_NOTES_FILE) == jiffyUtils.DEFAULT_LOCAL_DATA_DIR)

print("\n%d/%d passed" % (sum(results), len(results)))
shutil.rmtree(base, ignore_errors=True)
