# ------------------------------------------------------------
# provision_shotgrid_class.py
#
# One-off admin utility: bulk-creates a Sequence + one Shot per student
# under an EXISTING ShotGrid Project, adds each student as a Project
# member, and assigns them as the Artist on their own Shot(s) -- driven
# by a class list CSV with "First Name","Last Name","Email" columns (RMIT
# student email format: s<ID>@student.rmit.edu.au). ShotGrid has no
# direct "artist" field on Shot itself -- assignment is done via each
# Shot's Task (same "Animation" Pipeline Step convention jiffySG.py's
# update_shot_task() already uses on this site).
#
# Deliberately does NOT create the Project itself (stays manual, per
# shotSub/jiffySG's existing design -- see shotgridConnect.py's module
# docstring) and does NOT create HumanUser accounts -- a student must
# already have logged into ShotGrid at least once via RMIT SSO for their
# account to exist; this script only looks accounts up, never creates
# them, to avoid provisioning broken/duplicate logins.
#
# Idempotent -- safe to re-run: skips a Shot that already exists (by
# code, matching jiffySG.create_shot()'s pattern), and only ever ADDS to
# a Project's member list (via multi_entity_update_modes), never
# removes/replaces existing members.
#
# Uses the same ShotGrid connection as shotSub (shotgridConnect.py,
# colocated in this same folder) -- reads shotSub_config.json, connects
# as the instructor's own login (current_login()), same permission tier
# as doing this by hand in ShotGrid's web UI.
#
# Run via mayapy from this folder:
#   mayapy provision_shotgrid_class.py <csv_path> <project_name> <sequence_name> <shot_prefix> <shot_types>
#
# shot_types is a comma-separated list of per-student exercise names, one
# Shot created per (student, type) pair, all under the same Sequence --
# e.g. "tail,walkCycle" for an assignment that requires a tail-animation
# Shot and a walk-cycle Shot from every student. Use a single entry
# (e.g. "main") for an assignment that only needs one Shot per student.
#
# Example (Assignment 1 -- tail + walk cycle, two Shots per student):
#   mayapy provision_shotgrid_class.py "C:\path\to\classlist.csv" "3DcharacterPerformance" "Assignment1" "asgn1" "tail,walkCycle"
# ------------------------------------------------------------
import sys
import os
import csv
import re

_DEV_DIR = os.path.dirname(os.path.abspath(__file__))
if _DEV_DIR not in sys.path:
    sys.path.insert(0, _DEV_DIR)

try:
    import maya.standalone
    maya.standalone.initialize(name="python")
except Exception:
    pass  # already running inside an interactive Maya session

import shotgridConnect


_EMAIL_ID_RE = re.compile(r"^s(\d+)@", re.IGNORECASE)


def _student_id_from_email(email):
    """Extracts the numeric RMIT student id from an s<ID>@student.rmit.edu.au
    login, upper-cased with its 'S' prefix for shot-code naming (e.g.
    's4177501@student.rmit.edu.au' -> 'S4177501'). Falls back to the
    email's local part unmodified if it doesn't match that pattern (e.g.
    a staff/mentor row slipped into the class list), so the script still
    runs for those rows rather than crashing."""
    match = _EMAIL_ID_RE.match(email.strip())
    if match:
        return "S" + match.group(1)
    return email.split("@", 1)[0]


def read_class_list(csv_path):
    with open(csv_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            email = (row.get("Email") or "").strip().lower()
            if not email:
                continue
            rows.append({
                "email": email,
                "student_id": _student_id_from_email(email),
            })
        return rows


_ARTIST_STEP_CODE = "Animation"


def _find_or_create_task(sg, shot, project, step_code=_ARTIST_STEP_CODE):
    """Find or create the one Task per Shot that jiffySG.py's own
    _find_or_create_task() manages (same site, same 'Animation' Pipeline
    Step convention -- reused here so a shot assigned by this script and
    one assigned later via jiffySG/shotSub land on the same Task, not two
    competing ones). Raises if the Step doesn't exist on this site yet."""
    step = sg.find_one(
        "Step", [["code", "is", step_code], ["entity_type", "is", "Shot"]], ["id", "code"]
    )
    if not step:
        raise RuntimeError(
            "provision: no Shot-type Pipeline Step named '{0}' on this site — "
            "create it in ShotGrid first.".format(step_code)
        )
    task = sg.find_one("Task", [["entity", "is", shot], ["step", "is", step]], ["id"])
    if task:
        return task
    return sg.create("Task", {"project": project, "entity": shot, "content": step_code, "step": step})


def provision(csv_path, project_name, sequence_name, shot_prefix, shot_types):
    sg = shotgridConnect.get_connection()
    students = read_class_list(csv_path)
    print("provision: {0} students read from class list".format(len(students)))

    project = sg.find_one("Project", [["name", "is", project_name]], ["id", "name"])
    if not project:
        raise RuntimeError(
            "provision: no ShotGrid Project named '{0}' — create it in ShotGrid's "
            "web UI first (Project creation stays manual by design).".format(project_name)
        )

    # -- Project membership: look up each student's HumanUser by login,
    # add (never remove/replace) to the Project's member list. Never
    # creates a HumanUser -- an account with no ShotGrid login yet needs
    # its first real SSO sign-in before it can be added here.
    user_by_email = {}
    missing_logins = []
    for student in students:
        user = sg.find_one("HumanUser", [["login", "is", student["email"]]], ["id", "login"])
        if user:
            user_by_email[student["email"]] = user
        else:
            missing_logins.append(student["email"])

    found_users = list(user_by_email.values())
    if found_users:
        sg.update(
            "Project", project["id"],
            {"users": found_users},
            multi_entity_update_modes={"users": "add"},
        )
    print("provision: added {0}/{1} students to Project '{2}' ({3} had no ShotGrid "
          "account yet — they need to log in via RMIT SSO once first)".format(
              len(found_users), len(students), project_name, len(missing_logins)))
    if missing_logins:
        print("provision: no ShotGrid account found for: {0}".format(", ".join(missing_logins)))

    # -- Sequence (find-or-create, idempotent)
    sequence = sg.find_one(
        "Sequence", [["project", "is", project], ["code", "is", sequence_name]], ["id", "code"]
    )
    if not sequence:
        sequence = sg.create("Sequence", {"project": project, "code": sequence_name})
        print("provision: created Sequence '{0}'".format(sequence_name))
    else:
        print("provision: Sequence '{0}' already exists — reusing".format(sequence_name))

    # -- One Shot per (student, shot_type) pair (find-or-create by code,
    # idempotent -- same shape as jiffySG.create_shot(), just batched over
    # the whole class list x exercise list). e.g. shot_types=["tail",
    # "walkCycle"] creates "asgn1_tail_S4177501" AND "asgn1_walkCycle_S4177501"
    # for every student, all under the one Sequence.
    created, existing, relinked, assigned, unassignable = 0, 0, 0, 0, 0
    for student in students:
        artist = user_by_email.get(student["email"])
        for shot_type in shot_types:
            shot_code = "{0}_{1}_{2}".format(shot_prefix, shot_type, student["student_id"])
            shot = sg.find_one(
                "Shot", [["project", "is", project], ["code", "is", shot_code]], ["id", "sg_sequence"]
            )
            if shot:
                existing += 1
                if not shot.get("sg_sequence"):
                    sg.update("Shot", shot["id"], {"sg_sequence": sequence})
                    relinked += 1
            else:
                shot = sg.create("Shot", {"project": project, "code": shot_code, "sg_sequence": sequence})
                created += 1

            # -- Artist assignment: the corresponding student is set as
            # this Shot's Task assignee (ShotGrid has no direct "artist"
            # field on Shot itself -- assignment lives on a Task, same
            # convention jiffySG.py's update_shot_task() already uses).
            # Skipped for students with no ShotGrid account found above.
            if artist:
                task = _find_or_create_task(sg, shot, project)
                sg.update("Task", task["id"], {"task_assignees": [artist]})
                # Mirrors the Task assignee onto Shot.sg_artist (see
                # setup_shot_schema.py) purely so it shows as a plain
                # column in ShotGrid's Shot List view -- the Task
                # assignee above remains the source of truth.
                sg.update("Shot", shot["id"], {"sg_artist": artist})
                assigned += 1
            else:
                unassignable += 1
    print("provision: Shots — {0} created, {1} already existed ({2} re-linked to '{3}')".format(
        created, existing, relinked, sequence_name))
    print("provision: Artist assigned on {0} Shots ({1} skipped — no ShotGrid account found)".format(
        assigned, unassignable))


if __name__ == "__main__":
    if len(sys.argv) != 6:
        print(__doc__)
        sys.exit(
            "Usage: mayapy provision_shotgrid_class.py <csv_path> <project_name> "
            "<sequence_name> <shot_prefix> <shot_types_comma_separated>"
        )
    shot_types_arg = [t.strip() for t in sys.argv[5].split(",") if t.strip()]
    provision(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], shot_types_arg)
