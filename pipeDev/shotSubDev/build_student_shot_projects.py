# ------------------------------------------------------------
# build_student_shot_projects.py
#
# One-off admin utility: bulk-creates a standard Maya project per Shot
# under an existing ShotGrid Project (matching shot_prefix), for shots
# that already have a student assigned via their "Animation" Task
# (see provision_shotgrid_class.py -- same Task/assignee convention,
# but this script never creates or assigns Tasks itself, only reads
# them).
#
# Each Shot becomes its own real Maya project (built via Maya's own
# "setProject" -- same workspace.mel + default folder rules as File >
# Project Window > New/Accept, not a hand-rolled folder set), with the
# student's id added as a subfolder inside that project's own scenes/
# file-rule folder:
#
#   <output_root>/<shot_code>/                  <- Maya project root
#       workspace.mel
#       scenes/
#           <STUDENT_ID>/                       <- e.g. S4177501
#       sourceimages/
#       images/
#       ...(Maya's other default project folders)
#
# No scene file is created -- landscape/camera/character-geo assets are
# being planned as a separate self-serve download for students to set
# up themselves, so this script's job stops at folder structure.
#
# A Shot with more than one Task assignee gets one student subfolder
# per assignee, all inside the same project (still one Shot). A Shot
# with zero assignees is skipped and listed at the end -- assign it in
# ShotGrid and re-run.
#
# Idempotent -- safe to re-run: setProject leaves existing folders/
# workspace.mel alone, and an existing student subfolder is skipped.
#
# Run via mayapy from this folder:
#   mayapy build_student_shot_projects.py <project_name> <shot_prefix> <output_root>
#
# Example (NWF sequence, "Not Worth Fixing"):
#   mayapy build_student_shot_projects.py "3DcharacterPerformance" "NWF_EAP_" "D:\NWF_studentProjects"
# ------------------------------------------------------------
import sys
import os
import re

_DEV_DIR = os.path.dirname(os.path.abspath(__file__))
if _DEV_DIR not in sys.path:
    sys.path.insert(0, _DEV_DIR)

try:
    import maya.standalone
    maya.standalone.initialize(name="python")
except Exception:
    pass  # already running inside an interactive Maya session

import maya.mel as mel
import shotgridConnect


# Same login -> student-id convention as provision_shotgrid_class.py's
# _student_id_from_email() -- deliberately duplicated (not imported)
# since that script is a standalone __main__ utility, not a shared
# library; keeps this script runnable on its own. A login that doesn't
# match the RMIT student-email pattern (e.g. an external ex-student or
# mentor assigned as a stand-in artist, using a personal Gmail login)
# falls back to their ShotGrid display name instead -- readable, unlike
# an arbitrary personal-email local part.
_EMAIL_ID_RE = re.compile(r"^s(\d+)@", re.IGNORECASE)
_NON_ALNUM_RE = re.compile(r"[^A-Za-z0-9]+")


def _student_folder_name(login, name):
    match = _EMAIL_ID_RE.match(login.strip())
    if match:
        return "S" + match.group(1)
    if name:
        return _NON_ALNUM_RE.sub("", name)
    return login.split("@", 1)[0]


_ARTIST_STEP_CODE = "Animation"


def _shot_assignees(sg, shot):
    """(login, name) pairs from the Shot's own 'Animation' Task assignees
    -- the same source of truth shotSub/provision_shotgrid_class.py use.
    Returns an empty list if the Task doesn't exist yet or has nobody
    assigned."""
    step = sg.find_one(
        "Step", [["code", "is", _ARTIST_STEP_CODE], ["entity_type", "is", "Shot"]], ["id"]
    )
    if not step:
        return []
    task = sg.find_one("Task", [["entity", "is", shot], ["step", "is", step]], ["id", "task_assignees"])
    if not task:
        return []
    assignees = task.get("task_assignees") or []
    result = []
    for assignee in assignees:
        if assignee.get("type") != "HumanUser":
            continue
        user = sg.find_one("HumanUser", [["id", "is", assignee["id"]]], ["login", "name"])
        if user and user.get("login"):
            result.append((user["login"], user.get("name")))
    return result


def _create_maya_project(path):
    """Builds a real Maya project at path via sp_createAndSetDefaultProject
    -- the same core MEL proc setProject.mel's own non-popup path
    (sp_setLocalWorkspaceWithoutPopupDialog) calls to create a brand new
    project, i.e. the actual "create workspace.mel + default project
    folders" logic behind File > Project Window > New/Accept. Deliberately
    NOT setProject/sp_setLocalWorkspaceWithoutPopupDialog themselves --
    both go on afterwards to call addRecentProject -> savePrefs, which
    needs Maya's interactive UI/prefs machinery and hard-crashes under
    mayapy (RuntimeError: procedure "savePrefs" not found). Calling the
    inner proc directly skips that UI bookkeeping entirely -- harmless to
    skip, since a batch-generated student project was never opened
    interactively on this machine to begin with.

    Also naturally idempotent: sp_createAndSetDefaultProject checks for an
    existing workspace.mel itself and warns + no-ops rather than
    overwriting one, so re-running this script leaves an already-built
    project's folders/workspace.mel untouched."""
    if not os.path.isdir(path):
        os.makedirs(path)
    # sp_createAndSetDefaultProject is a secondary global proc in
    # setProject.mel -- Maya's MEL autoloader only auto-sources a file for
    # its *primary* (name-matching) proc, so calling setProject() once
    # would pull the file in, but this helper needs it sourced explicitly.
    mel.eval('source "setProject.mel";')
    mel.eval('sp_createAndSetDefaultProject("{0}", true)'.format(path.replace("\\", "/")))


def _scenes_root(project_path):
    # Matches shotSub.py's get_scenes_root() -- query the project's own
    # "scene" file rule rather than assuming it's literally "scenes".
    scene_rule = mel.eval('workspace -q -fileRuleEntry "scene";') or "scenes"
    return os.path.join(project_path, scene_rule)


def build(project_name, shot_prefix, output_root):
    sg = shotgridConnect.get_connection()

    project = sg.find_one("Project", [["name", "is", project_name]], ["id", "name"])
    if not project:
        raise RuntimeError(
            "build_student_shot_projects: no ShotGrid Project named '{0}'".format(project_name)
        )

    shots = sg.find(
        "Shot", [["project", "is", project], ["code", "starts_with", shot_prefix]],
        ["id", "code"], order=[{"field_name": "code", "direction": "asc"}],
    )
    print("build_student_shot_projects: {0} shots found matching '{1}*'".format(
        len(shots), shot_prefix))

    if not os.path.isdir(output_root):
        os.makedirs(output_root)

    created_projects, created_subfolders, skipped_subfolders = 0, 0, 0
    unassigned_shots = []

    for shot in shots:
        assignees = _shot_assignees(sg, shot)
        if not assignees:
            unassigned_shots.append(shot["code"])
            continue

        project_path = os.path.join(output_root, shot["code"])
        _create_maya_project(project_path)
        created_projects += 1
        scenes_root = _scenes_root(project_path)

        for login, name in assignees:
            student_id = _student_folder_name(login, name)
            student_folder = os.path.join(scenes_root, student_id)
            if os.path.isdir(student_folder):
                skipped_subfolders += 1
                continue
            os.makedirs(student_folder)
            created_subfolders += 1
            print("build_student_shot_projects: {0} -> scenes/{1}".format(shot["code"], student_id))

    print()
    print("build_student_shot_projects: {0} shot projects touched, {1} student subfolders created "
          "({2} already existed)".format(created_projects, created_subfolders, skipped_subfolders))
    if unassigned_shots:
        print("build_student_shot_projects: skipped {0} shot(s) with no Animation Task assignee: {1}".format(
            len(unassigned_shots), ", ".join(unassigned_shots)))


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(
            "Usage: mayapy build_student_shot_projects.py <project_name> <shot_prefix> <output_root>"
        )
    build(sys.argv[1], sys.argv[2], sys.argv[3])
