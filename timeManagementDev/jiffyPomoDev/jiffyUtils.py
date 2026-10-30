# JiffyPomo shared helpers and default file paths

import os
import shutil

DEFAULT_LOCAL_DATA_DIR = os.path.join(os.path.expanduser("~"), "jiffyData")
DEFAULT_PROMPTS_FILE = os.path.join(DEFAULT_LOCAL_DATA_DIR, "jiffypomo_prompts.json")
DEFAULT_NOTES_FILE = os.path.join(DEFAULT_LOCAL_DATA_DIR, "jiffypomo_notes.json")

# Shot data (tasks, summary) lives in the Maya project's data folder, not
# beside the scenes (user, 2026-10-30): a scene in <project>\scenes\<rel>
# keeps its shot data in <project>\data\jiffyShotData\<rel>, so each shot
# (or, on the pipe, each department and artist) still has its own. Show
# data (prompts, notes) stays in DEFAULT_LOCAL_DATA_DIR.
SHOT_DATA_FOLDER = "jiffyShotData"


def project_data_folder(scene_dir, tool_folder):
    """<project>\\data\\<tool_folder>\\<rel> for a folder <project>\\scenes\\<rel>
    (the last "scenes" folder in its path), or None if it isn't under one."""
    parts = os.path.normpath(scene_dir).split(os.sep)
    lower = [p.lower() for p in parts]
    if "scenes" not in lower:
        return None
    i = len(lower) - 1 - lower[::-1].index("scenes")
    return os.sep.join(parts[:i] + ["data", tool_folder] + parts[i + 1:])


def shot_data_file(scene_dir, name):
    """The shot data file `name` for a scene folder. One left beside the
    scenes by an earlier JiffyPomo (<scene folder>\\jiffyShotData\\<name>)
    is copied across the first time, so nothing is lost."""
    old = os.path.join(scene_dir, SHOT_DATA_FOLDER, name)
    folder = project_data_folder(scene_dir, SHOT_DATA_FOLDER)
    if not folder:
        return old
    new = os.path.join(folder, name)
    if not os.path.exists(new) and os.path.isfile(old):
        try:
            os.makedirs(folder, exist_ok=True)
            shutil.copy2(old, new)
        except OSError:
            return old
    return new


def get_ordinal_suffix(day):
    if 11 <= day % 100 <= 13:
        return "th"
    else:
        suffixes = {1: "st", 2: "nd", 3: "rd"}
        return suffixes.get(day % 10, "th")
