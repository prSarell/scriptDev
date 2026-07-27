# ------------------------------------------------------------
# jiffySG.py
#
# Jiffy SG — ShotGrid-integrated fork of JiffySchedule.
# See timeManagementDev/jiffySG_brief.md for the full design.
#
# Structure:
#   1. Backend — auth/connection + Shot/Sequence create/delete against
#      ShotGrid via shotgun_api3. Usable standalone (e.g. by pbTool's
#      "Send to ShotGrid" hand-off) without the UI below.
#   2. UI — a fork of timeManagementDev/jiffyScheduleDev/jiffySchedule.py.
#      Assets tab, Progress/Milestones tab, Artists tab, and the "Jiffy
#      Pomo" hand-off are carried over unchanged; only the Shots tab
#      pushes to ShotGrid (Shot/Sequence creation and deletion,
#      automatically, the instant something is added/removed locally).
#      jiffySchedule.py itself is untouched and keeps working
#      independently — this is a genuine fork, not a live dependency.
#
# Auth model (per the brief): a single Script API key authenticates all
# API calls; sudo_as_login applies the impersonated student's own
# ShotGrid permissions to each call and attributes it to them in the
# event log. The key itself is never hardcoded here or committed to the
# repo — it's read from a local config file created on each machine.
#
# Config file:
#   <Maya userPrefDir>/jiffySG_config.json
#   {
#     "site_url": "https://nfw.shotgrid.autodesk.com",
#     "script_name": "JiffySG_001",
#     "api_key": "<the Application Key from ShotGrid Admin > Scripts>",
#     "sudo_as_login": "<optional override — see current_login() below>"
#   }
#
# Quick connection test (Script Editor, inside Maya):
#   import jiffySG
#   jiffySG.test_connection()
#
# Launch the UI (Script Editor, inside Maya):
#   import jiffySG
#   jiffySG.run_jiffySG()
# ------------------------------------------------------------

import os
import re
import glob
import json
import getpass
import time
import shutil
import threading
import subprocess
import urllib.request
from datetime import date as _date, datetime as _datetime, timedelta as _timedelta

import maya.cmds as cmds
import maya.utils
from maya import OpenMayaUI as omui

from PySide6 import QtWidgets, QtCore, QtGui
from shiboken6 import wrapInstance

import shotgun_api3


_CONFIG_FILENAME = "jiffySG_config.json"
_REQUIRED_KEYS = ("site_url", "script_name", "api_key")

# Cached after the first successful load. NEEDED, not just an optimisation:
# every ShotGrid call (test_connection/create_shot/etc.) runs inside
# _run_sg_async's background thread, and maya.cmds is not safe to call off
# Maya's main thread — cmds.internalVar(userPrefDir=True) was confirmed to
# silently return "" there instead of raising, which made _config_file()
# build a bare relative "jiffySG_config.json" path and _load_config() report
# "no config file found" even when the file existed at the correct prefs
# path. _run_sg_async() below primes this cache synchronously on the main
# thread (where it's always called from — UI signal handlers) before ever
# starting the worker thread, so the background thread only ever hits this
# cache, never cmds.internalVar directly.
_config_cache = None


def _config_file():
    prefs = cmds.internalVar(userPrefDir=True)
    return os.path.join(prefs, _CONFIG_FILENAME).replace("\\", "/")


def _load_config():
    global _config_cache
    if _config_cache is not None:
        return _config_cache
    path = _config_file()
    if not os.path.isfile(path):
        raise RuntimeError(
            "jiffySG: no config file found at {0}\n\n"
            "Create it with:\n"
            '{{\n'
            '  "site_url": "https://nfw.shotgrid.autodesk.com",\n'
            '  "script_name": "<Script Name from ShotGrid Admin > Scripts>",\n'
            '  "api_key": "<Application Key from ShotGrid Admin > Scripts>"\n'
            '}}'.format(path)
        )

    with open(path, "r") as f:
        try:
            config = json.load(f)
        except ValueError as exc:
            raise RuntimeError("jiffySG: config at {0} is not valid JSON — {1}".format(path, exc))

    missing = [key for key in _REQUIRED_KEYS if not config.get(key)]
    if missing:
        raise RuntimeError(
            "jiffySG: config at {0} is missing: {1}".format(path, ", ".join(missing))
        )

    _config_cache = config
    return config


def current_login():
    """The identity to sudo_as_login as. OS-username auto-detect
    (getpass.getuser()) is CONFIRMED BROKEN — tested failing on two
    separate machines, ShotGrid rejects it outright (real logins on this
    site are full email addresses, e.g. 'patrick.sarell2@rmit.edu.au', not
    OS usernames). Until per-student identity detection is solved (see
    jiffySG_brief.md), an explicit "sudo_as_login" key in the local config
    file is used as an override; getpass.getuser() is only a last-resort
    fallback for the case where no config file exists yet at all."""
    try:
        config = _load_config()
    except RuntimeError:
        return getpass.getuser()
    return config.get("sudo_as_login") or getpass.getuser()


def get_connection(as_login=None):
    """Return an authenticated shotgun_api3.Shotgun connection, impersonating
    as_login (defaults to current_login()) via sudo_as_login."""
    config = _load_config()
    return shotgun_api3.Shotgun(
        config["site_url"],
        script_name=config["script_name"],
        api_key=config["api_key"],
        sudo_as_login=as_login or current_login(),
    )


def test_connection(as_login=None):
    """Proves the Script API key + sudo_as_login combination actually
    authenticates, using a genuinely-authenticated call. Deliberately NOT
    sg.info() — the brief's own testing (2026-07-16) found sg.info() gives
    a false positive, since it doesn't require authentication at all and
    will "succeed" even when the credentials are broken.

    Returns the list of Projects visible to as_login. An empty list is a
    legitimate result (the student's Project may not exist/be shared yet)
    — what matters is that this doesn't raise AuthenticationFault."""
    projects = list_visible_projects(as_login=as_login)
    print("jiffySG: connected as '{0}' — {1} visible project(s):".format(
        as_login or current_login(), len(projects)))
    for p in projects:
        print("  {0}".format(p.get("name")))
    return projects


def _find_or_create_sequence(sg, project, sequence_name):
    """Find or create a ShotGrid Sequence by code within project. Named to
    match ShotGrid's own entity/field names directly (Sequence, sg_sequence)
    rather than JiffySchedule's "Scene" grouping label elsewhere in the
    toolset — deliberate divergence, since Jiffy SG code talks to ShotGrid's
    schema constantly and a translation layer just adds confusion there."""
    sequence = sg.find_one(
        "Sequence", [["project", "is", project], ["code", "is", sequence_name]], ["id", "code"]
    )
    if sequence:
        return sequence

    sequence = sg.create("Sequence", {"project": project, "code": sequence_name})
    print("jiffySG: created Sequence '{0}' (id {1})".format(sequence_name, sequence["id"]))
    return sequence


def _find_project(sg, project_name, as_login=None):
    """Look up a Project by exact name, or raise a clear RuntimeError if it's
    not visible to as_login. Shared by create_shot() and create_sequence()
    so both fail the same way on a typo'd/wrong Project name."""
    project = sg.find_one("Project", [["name", "is", project_name]], ["id", "name"])
    if not project:
        raise RuntimeError(
            "jiffySG: no ShotGrid Project named '{0}' visible to '{1}'".format(
                project_name, as_login or current_login())
        )
    return project


def create_sequence(sequence_name, project_name, as_login=None):
    """Public wrapper around _find_or_create_sequence, for callers (like
    Jiffy SG's "Add Sequence" flow) that need to create/resolve a Sequence
    without also creating a Shot in it."""
    sg = get_connection(as_login=as_login)
    project = _find_project(sg, project_name, as_login=as_login)
    return _find_or_create_sequence(sg, project, sequence_name)


def _find_or_create_asset(sg, project, asset_name):
    """Find or create a ShotGrid Asset by code within project — same
    idempotent pattern as _find_or_create_sequence above. Unlike Shots,
    Assets in Jiffy SG are never scheduled/synced to ShotGrid otherwise (no
    Task/stage/due/artist push) — this exists purely so an asset's
    published playblast Versions have a real entity to attach to. No
    sg_asset_type/category is set: local Jiffy SG categories (Sets,
    Environments, Rigs, ...) are a purely local/folder-structure concept,
    never pushed to ShotGrid."""
    asset = sg.find_one(
        "Asset", [["project", "is", project], ["code", "is", asset_name]], ["id", "code"]
    )
    if asset:
        return asset

    asset = sg.create("Asset", {"project": project, "code": asset_name})
    print("jiffySG: created Asset '{0}' (id {1})".format(asset_name, asset["id"]))
    return asset


def find_or_create_asset(asset_name, project_name, as_login=None):
    """Public wrapper around _find_or_create_asset, used by Jiffy SG's
    "Set Project" action (ItemDialog._do_set_project) the first time an
    Asset row gets linked to a local Maya project folder."""
    sg = get_connection(as_login=as_login)
    project = _find_project(sg, project_name, as_login=as_login)
    return _find_or_create_asset(sg, project, asset_name)


def delete_shot(shot_id, as_login=None):
    """Soft-delete (retire) a Shot by id. Recoverable by a ShotGrid admin
    (revive) — not a permanent destructive operation, so a student mistake
    is always correctable."""
    sg = get_connection(as_login=as_login)
    ok = sg.delete("Shot", shot_id)
    print("jiffySG: retired Shot id {0} — {1}".format(
        shot_id, "ok" if ok else "already retired or not found"))
    return ok


def delete_sequence(sequence_id, as_login=None):
    """Soft-delete (retire) a Sequence by id — see delete_shot() above."""
    sg = get_connection(as_login=as_login)
    ok = sg.delete("Sequence", sequence_id)
    print("jiffySG: retired Sequence id {0} — {1}".format(
        sequence_id, "ok" if ok else "already retired or not found"))
    return ok


def create_shot(shot_code, project_name, sequence_name=None, as_login=None):
    """Create a Shot in the named Project, or return the existing one if a
    Shot with that code already exists there. sequence_name is optional —
    if given, the Shot is linked to a Sequence (see _find_or_create_sequence
    above), created first if it doesn't exist yet. Minimal on purpose
    otherwise: no Task/status/frame-range fields — those need the Task
    status codes set up per project first (see jiffySG_brief.md's Stage
    mapping), which hasn't happened yet."""
    sg = get_connection(as_login=as_login)

    project = _find_project(sg, project_name, as_login=as_login)

    sequence = _find_or_create_sequence(sg, project, sequence_name) if sequence_name else None

    existing = sg.find_one(
        "Shot", [["project", "is", project], ["code", "is", shot_code]], ["id", "code", "sg_sequence"]
    )
    if existing:
        if sequence and not existing.get("sg_sequence"):
            sg.update("Shot", existing["id"], {"sg_sequence": sequence})
            print("jiffySG: linked existing Shot '{0}' to Sequence '{1}'".format(shot_code, sequence_name))
        else:
            print("jiffySG: Shot '{0}' already exists in '{1}' (id {2})".format(
                shot_code, project_name, existing["id"]))
        return existing

    shot_data = {"project": project, "code": shot_code}
    if sequence:
        shot_data["sg_sequence"] = sequence

    shot = sg.create("Shot", shot_data)
    print("jiffySG: created Shot '{0}' in '{1}'{2} (id {3})".format(
        shot_code, project_name,
        " under Sequence '{0}'".format(sequence_name) if sequence_name else "",
        shot["id"]))
    return shot


def _dmy_to_iso(s):
    """Convert Jiffy SG's DD-MM-YYYY due-date string to ShotGrid's
    YYYY-MM-DD. Returns None if blank/unparseable."""
    if not s:
        return None
    try:
        return _datetime.strptime(s.strip(), "%d-%m-%Y").strftime("%Y-%m-%d")
    except ValueError:
        return None


def update_shot_frame_range(shot_id, frame_start, frame_end, as_login=None):
    """Push Frame Start/End to Shot.cut_in/cut_out. No blocker on this one —
    unlike Stage/Due Date/Artist below, these are plain fields on the Shot
    entity itself, no Task/Pipeline Step setup required. Silently no-ops on
    blank/unparseable values (e.g. a brand-new item with no frames set yet)."""
    try:
        cut_in, cut_out = int(frame_start), int(frame_end)
    except (TypeError, ValueError):
        return None
    sg = get_connection(as_login=as_login)
    return sg.update("Shot", shot_id, {"cut_in": cut_in, "cut_out": cut_out})


def upload_shot_thumbnail(shot_id, image_path, as_login=None):
    """Push Jiffy SG's own captured/browsed thumbnail (ItemRowWidget's
    ThumbnailLabel) up as the Shot's ShotGrid thumbnail. Silently no-ops on
    a blank/missing path — a brand-new item may not have a thumbnail yet,
    and that's not an error.

    NOTE for whoever builds upload_playblast(): ShotGrid does NOT
    automatically cascade a Version's thumbnail up to its linked Shot just
    because the Version has one — if playblasts should keep the Shot's
    thumbnail current (the assumption this feature was built under), that
    function needs to explicitly call this too after uploading the
    Version's own thumbnail."""
    if not image_path or not os.path.isfile(image_path):
        return None
    sg = get_connection(as_login=as_login)
    return sg.upload_thumbnail("Shot", shot_id, image_path)


def upload_entity_thumbnail(entity_type, entity_id, image_path, as_login=None):
    """Generalized sibling of upload_shot_thumbnail() above, for
    upload_playblast()'s use — Shots and Assets both push through here so
    the same function works for either. upload_shot_thumbnail() itself is
    left untouched since it's still used directly by the existing
    Shot-only schedule-sync push paths (_push_shot_create/
    _push_shot_field_sync), which never apply to Assets."""
    if not image_path or not os.path.isfile(image_path):
        return None
    sg = get_connection(as_login=as_login)
    return sg.upload_thumbnail(entity_type, entity_id, image_path)


def _find_or_create_task(sg, shot, project, step_code="Animation"):
    """Find or create the one Task Jiffy SG manages per Shot, under
    step_code. Jiffy SG tracks a single Task per Shot (matching
    JiffySchedule's single Stage/Due Date/Artist per shot model) rather
    than one Task per pipeline step. step_code must be an existing
    Shot-type Pipeline Step on the site — raises RuntimeError if not."""
    step = sg.find_one(
        "Step", [["code", "is", step_code], ["entity_type", "is", "Shot"]], ["id", "code"]
    )
    if not step:
        raise RuntimeError(
            "jiffySG: no Shot-type Pipeline Step named '{0}' on this site".format(step_code)
        )

    task = sg.find_one("Task", [["entity", "is", shot], ["step", "is", step]], ["id"])
    if task:
        return task

    task = sg.create("Task", {"project": project, "entity": shot, "content": step_code, "step": step})
    print("jiffySG: created Task '{0}' on Shot id {1} (id {2})".format(
        step_code, shot["id"], task["id"]))
    return task


def _resolve_artist(sg, project, artist_name):
    """Best-effort HumanUser lookup by exact name, scoped to project
    members. Returns None (not an error) on no match — the Artist field's
    value may have fallen out of the project's real roster (e.g. someone
    removed from the Project since being assigned), so a non-match is an
    expected, non-fatal outcome rather than an error."""
    if not artist_name:
        return None
    return sg.find_one(
        "HumanUser", [["projects", "is", project], ["name", "is", artist_name]], ["id", "name"]
    )


def list_visible_projects(as_login=None):
    """All ShotGrid Projects visible to as_login (defaults to
    current_login()), as a list of {"id","name"} dicts, name-sorted.
    ShotGrid itself — not Jiffy SG — is what scopes this: a student on the
    Artist permission group only ever sees the Project(s) their instructor
    added them to, so this is exactly the set of Projects that login is
    allowed to work in. Used by test_connection() (diagnostic) and by the
    Nav panel's "Add Project" flow, which now only lets a student attach a
    real ShotGrid Project they're actually a member of — see
    jiffySG_brief.md's "Project linking" design."""
    sg = get_connection(as_login=as_login)
    return sg.find(
        "Project", [], ["id", "name"], order=[{"field_name": "name", "direction": "asc"}]
    )


def list_project_shots(project_name, as_login=None):
    """All ShotGrid Shots that exist in the named Project — read-only, and
    deliberately never creates one: shotSub's "Link to ShotGrid" flow (see
    shotSub.py link_to_shotgrid()) may only attach a shot-level Maya
    project to a Shot an instructor or student already created via Jiffy
    SG's own Shots tab (create_shot() above), never spin up a new Shot
    itself. Returns {"id","code"} dicts, code-sorted, so shotSub can
    resolve an explicit ShotGrid Shot id to store in its local
    shotgrid_link.json marker file instead of guessing a shot name from
    folder structure."""
    sg = get_connection(as_login=as_login)
    project = _find_project(sg, project_name, as_login=as_login)
    return sg.find(
        "Shot", [["project", "is", project]], ["id", "code"],
        order=[{"field_name": "code", "direction": "asc"}],
    )


def list_project_artists(project_name, as_login=None):
    """All ShotGrid HumanUsers who are members of the named Project — the
    real, ShotGrid-backed artist roster for that Project. Read-only (Jiffy
    SG never writes Project membership, per jiffySG_brief.md); feeds both
    the Artists tab display and the Shot/Asset Artist dropdown, replacing
    the old free-text local roster so an assignable name is always a real
    member of that Project rather than anything a student happens to type."""
    sg = get_connection(as_login=as_login)
    project = _find_project(sg, project_name, as_login=as_login)
    return sg.find(
        "HumanUser", [["projects", "is", project]], ["id", "name"],
        order=[{"field_name": "name", "direction": "asc"}],
    )


# ShotGrid's Task.sg_status_list only accepts these three status *codes*
# on this site (confirmed via schema_field_read, 2026-07-24) — rather than
# asking the site to be reconfigured to match a richer stage list, Jiffy
# SG's own SHOT_STAGES (below, in the UI section) was shrunk to match
# these exactly. Keys are the human-readable labels shown in Jiffy SG's
# UI (and in SHOT_STAGES); values are the actual codes ShotGrid expects.
SHOT_STAGE_TO_SG_STATUS = {
    "Waiting to Start": "wtg",
    "In Progress":      "ip",
    "Final":            "fin",
}


def update_shot_task(shot_id, project_name, stage=None, due_date=None, artist_name=None, as_login=None):
    """Push Stage/Due Date/Artist to the Shot's single Jiffy SG Task
    (created under the "Animation" Pipeline Step if it doesn't exist yet).

    Stage is converted from Jiffy SG's readable label to ShotGrid's actual
    status code via SHOT_STAGE_TO_SG_STATUS above before being written to
    Task.sg_status_list (falls back to the raw value unconverted if it's
    not a recognised label, so a future stage added to SHOT_STAGES without
    updating this map still gets sent — and fails loudly rather than
    silently, per the same "no ShotGrid Project" clarity elsewhere here).

    Due date is converted from Jiffy SG's DD-MM-YYYY to ShotGrid's
    YYYY-MM-DD. Artist is resolved to a ShotGrid HumanUser by exact name
    match within the Project — silently skipped (not an error) if no
    match is found."""
    sg = get_connection(as_login=as_login)
    project = _find_project(sg, project_name, as_login=as_login)
    shot = {"type": "Shot", "id": shot_id}
    task = _find_or_create_task(sg, shot, project)

    updates = {}
    if stage:
        updates["sg_status_list"] = SHOT_STAGE_TO_SG_STATUS.get(stage, stage)
    if due_date:
        iso_date = _dmy_to_iso(due_date)
        if iso_date:
            updates["due_date"] = iso_date
    if artist_name:
        person = _resolve_artist(sg, project, artist_name)
        if person:
            updates["task_assignees"] = [person]

    if updates:
        sg.update("Task", task["id"], updates)
        print("jiffySG: updated Task id {0} on Shot id {1} — {2}".format(
            task["id"], shot_id, ", ".join(updates.keys())))
    return task


def _create_note(sg, shot, project, version, note_text):
    """One new Note per publish (never an overwrite) — a real ShotGrid Note,
    so a mentor reviewing directly in ShotGrid sees/adds to the same feed.
    Jiffy SG's own UI still only ever displays the single latest one (see
    jiffySG_brief.md's 2026-07-26 scope decision) — full history lives in
    ShotGrid itself."""
    note_links = [shot] + ([version] if version else [])
    return sg.create("Note", {
        "project": project,
        "subject": "Playblast — {0}".format(shot.get("code", "")),
        "content": note_text,
        "note_links": note_links,
    })


_RVIO_NAME = "rvio"


def _frame_sequence_prefix(version_folder):
    """Strip the trailing .####.jpg off any one frame file in version_folder
    to get the sequence prefix rvio/RV need (e.g. .../shotName.#.jpg). Jiffy
    SG doesn't know the original Maya scene's filename the way shotSub's own
    prefix construction does, so this derives it generically instead."""
    files = sorted(glob.glob(os.path.join(version_folder, "*.jpg")))
    if not files:
        return None
    match = re.search(r"^(.*)\.\d+\.jpg$", os.path.basename(files[0]), flags=re.IGNORECASE)
    return os.path.join(version_folder, match.group(1)) if match else None


def _encode_to_mp4(version_folder, fps):
    """Best-effort JPEG-sequence -> mp4 transcode via RV's bundled rvio (no
    separate ffmpeg dependency — RV is already a hard requirement for this
    pipeline's review workflow). Returns the mp4 path, or None on any
    failure (missing rvio, no frames, encode error) — publish must still
    succeed thumbnail-only if this doesn't work, never block on it.

    Skips re-encoding if <prefix>.mp4 already exists and is newer than the
    newest .jpg in the folder, so a notes-only re-publish doesn't re-encode."""
    prefix = _frame_sequence_prefix(version_folder)
    if not prefix:
        return None
    out_path = prefix + ".mp4"

    jpgs = sorted(glob.glob(os.path.join(version_folder, "*.jpg")))
    if os.path.isfile(out_path) and jpgs:
        newest_jpg = max(os.path.getmtime(f) for f in jpgs)
        if os.path.getmtime(out_path) >= newest_jpg:
            return out_path

    rvio = find_rv_executable(_RVIO_NAME)
    if not rvio:
        print("jiffySG: rvio not found — publishing thumbnail-only, no scrubbable movie.")
        return None

    cmd = [rvio, prefix + ".#.jpg", "-o", out_path]
    if fps:
        cmd += ["-fps", str(fps)]
    try:
        subprocess.run(
            cmd, capture_output=True, text=True, check=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception as exc:
        print("jiffySG: rvio encode failed (publishing thumbnail-only instead) — {0}".format(exc))
        return None

    return out_path if os.path.isfile(out_path) else None


def _push_publish_to_open_window(entity_type, entity_id, note_text, thumbnail_path, version_folder):
    """Best-effort live push into an already-open Jiffy SG window (see
    _jiffysg_window global, defined further below) — the "catch the note on
    the way through" mechanism: since shotSub already calls this function
    synchronously on Maya's main thread, in the same live session Jiffy SG's
    own window may be open in, we can update that window's UI instantly
    instead of waiting for any refresh. Must never let a UI-push failure
    break the ShotGrid write that already succeeded above."""
    window = _jiffysg_window
    if window is None:
        return
    try:
        window.apply_remote_publish(entity_type, entity_id, note_text, thumbnail_path, version_folder)
    except Exception as exc:
        print("jiffySG: live UI push after publish failed (non-fatal) — {0}".format(exc))


def upload_playblast(entity_type, entity_id, version_folder, files=None, notes=None, fps=None, as_login=None):
    """Hand-off target for shotSub's "Publish Selected Version" button (see
    shotSub.py publish_version()). shotSub resolves entity_type/entity_id
    itself, from an explicit ShotGrid Project id + Shot-or-Asset id pair
    stored in a local shotgrid_link.json marker file at the shot/asset's
    own (nested) Maya project root — written either by shotSub's "Link to
    ShotGrid" flow (Shots only, see list_project_shots() above, may only
    attach to an existing Shot, never create one) or by Jiffy SG's own
    "Set Project" action (Shots and Assets — see ItemDialog._do_set_project,
    which find-or-creates the Asset via find_or_create_asset() above since
    Assets are never otherwise synced to ShotGrid). entity_id is a global
    ShotGrid id, so project_name/project_id isn't needed as an input — the
    Project is looked up directly off the Shot/Asset itself.

    Idempotent on (entity, code): re-publishing the same version_folder
    finds and reuses the existing Version rather than creating a
    duplicate, matching create_shot()/create_sequence()'s pattern.

    Publishes a real scrubbable movie (Version.sg_uploaded_movie, encoded
    via rvio — see _encode_to_mp4) alongside the thumbnail. Also stores
    Version.sg_path_to_frames (the local version_folder) so Jiffy SG's
    "launch latest playblast" click can find the real frames later, and
    creates a ShotGrid Note per publish (see _create_note above), plus a
    best-effort live push into an already-open Jiffy SG window (see
    _push_publish_to_open_window).

    Task linking (Stage/Due Date/Artist's single managed Task) only applies
    to Shots — Assets are never scheduled/synced to ShotGrid otherwise, so
    there's no Task for an Asset's Version to link to."""
    sg = get_connection(as_login=as_login)

    entity = sg.find_one(entity_type, [["id", "is", entity_id]], ["id", "code", "project"])
    if not entity:
        raise RuntimeError(
            "jiffySG: no {0} found with id {1} — was it deleted/retired in "
            "ShotGrid since this project was linked?".format(entity_type, entity_id)
        )
    project = entity["project"]

    if files is None:
        files = sorted(glob.glob(os.path.join(version_folder, "*.jpg")))
    if not files:
        raise RuntimeError("jiffySG: no frames found in {0} to publish".format(version_folder))

    version_folder_norm = os.path.normpath(version_folder).replace("\\", "/")
    version_name = os.path.basename(version_folder_norm)
    code = "{0}_{1}".format(entity["code"], version_name)

    existing = sg.find_one("Version", [["entity", "is", entity], ["code", "is", code]], ["id"])
    if existing:
        print("jiffySG: Version '{0}' already exists on {1} '{2}' (id {3}) — not re-creating".format(
            code, entity_type, entity["code"], existing["id"]))
        version = existing
        sg.update("Version", version["id"], {"sg_path_to_frames": version_folder_norm})
    else:
        # Best-effort link to the same single Task Jiffy SG manages per Shot
        # (see _find_or_create_task/update_shot_task above) — Shots only,
        # not fatal if the "Animation" Step isn't set up on this Project,
        # since a Version without a linked Task is still a valid publish.
        task = None
        if entity_type == "Shot":
            try:
                task = _find_or_create_task(sg, entity, project)
            except Exception as exc:
                print("jiffySG: could not resolve/create a Task to link this Version to — {0}".format(exc))

        version_data = {
            "project": project, "code": code, "entity": entity,
            "sg_path_to_frames": version_folder_norm,
        }
        if task:
            version_data["sg_task"] = task

        version = sg.create("Version", version_data)
        print("jiffySG: created Version '{0}' on {1} '{2}' (id {3})".format(
            code, entity_type, entity["code"], version["id"]))

    representative_frame = files[len(files) // 2]
    sg.upload_thumbnail("Version", version["id"], representative_frame)

    # ShotGrid does not cascade a Version's thumbnail up to its linked
    # Shot/Asset on its own (see upload_shot_thumbnail()'s docstring) — do
    # it explicitly so the Shot/Asset's thumbnail stays current as new
    # playblasts get published.
    upload_entity_thumbnail(entity_type, entity_id, representative_frame, as_login=as_login)

    mp4_path = _encode_to_mp4(version_folder_norm, fps)
    if mp4_path:
        sg.upload("Version", version["id"], mp4_path, field_name="sg_uploaded_movie")
        print("jiffySG: uploaded movie '{0}' to Version id {1}".format(mp4_path, version["id"]))

    if notes:
        try:
            _create_note(sg, entity, project, version, notes)
        except Exception as exc:
            print("jiffySG: could not create ShotGrid Note — {0}".format(exc))

    _push_publish_to_open_window(entity_type, entity_id, notes, representative_frame, version_folder_norm)

    return version


def get_latest_playblast_path(entity_type, entity_id, as_login=None):
    """The local frame-sequence folder (Version.sg_path_to_frames) of the
    most recently published Version on this Shot/Asset, or None.
    Deliberately a live lookup (not cached) — used at RV-launch click-time
    in Jiffy SG's UI, where a brief round-trip for an explicit user action
    is fine and guarantees "launch latest" really is the latest."""
    sg = get_connection(as_login=as_login)
    entity = {"type": entity_type, "id": entity_id}
    version = sg.find_one(
        "Version", [["entity", "is", entity], ["sg_path_to_frames", "is_not", None]],
        ["sg_path_to_frames"],
        order=[{"field_name": "created_at", "direction": "desc"}],
    )
    return version.get("sg_path_to_frames") if version else None


def list_entity_latest_activity(project_name, entity_type, as_login=None):
    """{entity_id: {"note": str|None, "image_url": str|None}} for every
    Shot or Asset in project_name — 2 ShotGrid calls total regardless of
    entity count, used to batch-refresh Jiffy SG's rows (latest note +
    thumbnail) as the pull-based fallback for when the live push
    (_push_publish_to_open_window above) couldn't reach an open window at
    publish time."""
    sg = get_connection(as_login=as_login)
    project = _find_project(sg, project_name, as_login=as_login)
    entities = sg.find(entity_type, [["project", "is", project]], ["id", "image"])
    result = {e["id"]: {"note": None, "image_url": e.get("image")} for e in entities}
    if not entities:
        return result

    entity_refs = [{"type": entity_type, "id": e["id"]} for e in entities]
    notes = sg.find(
        "Note", [["note_links", "in", entity_refs]], ["content", "created_at", "note_links"],
        order=[{"field_name": "created_at", "direction": "desc"}],
    )
    seen = set()
    for note in notes:
        for link in note.get("note_links") or []:
            if link.get("type") != entity_type:
                continue
            eid = link.get("id")
            if eid in result and eid not in seen:
                result[eid]["note"] = note.get("content") or ""
                seen.add(eid)
    return result


def _thumb_cache_dir():
    """Must be called on Maya's main thread (cmds.internalVar) — see
    _config_cache's docstring above for why this can't happen inside an
    _run_sg_async worker thread."""
    prefs = cmds.internalVar(userPrefDir=True)
    d = os.path.join(prefs, "jiffySG_thumb_cache")
    os.makedirs(d, exist_ok=True)
    return d


def _download_shot_thumbnail(shot_id, image_url, cache_dir):
    """Best-effort download of a Shot's ShotGrid thumbnail (a signed,
    directly-fetchable HTTPS URL) to a stable local per-shot cache file.
    Always overwrites — signed URLs differ on every fetch, so there's no
    cheap way to diff-and-skip an unchanged image."""
    if not image_url:
        return None
    try:
        dest = os.path.join(cache_dir, "shot_{0}.jpg".format(shot_id))
        urllib.request.urlretrieve(image_url, dest)
        return dest
    except Exception as exc:
        print("jiffySG: could not download thumbnail for Shot id {0} — {1}".format(shot_id, exc))
        return None


# ---------------------------------------------------------------------------
# UI — forked from timeManagementDev/jiffyScheduleDev/jiffySchedule.py.
# Everything below this point is UI, not backend. Assets/Progress/Artists
# tabs and the Jiffy Pomo hand-off are carried over unchanged; only the
# Shots tab (create_shot/create_sequence/delete_shot/delete_sequence above)
# pushes to ShotGrid.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DARK_BG    = "#1e1e1e"
PANEL_BG   = "#252525"
ITEM_BG    = "#2e2e2e"
ITEM_HOVER = "#363636"
BORDER     = "#444444"
TEXT       = "#ffffff"
SUBTEXT    = "#aaaaaa"

_DATA_DIR_PREF = "jiffySGDataDir"

# Matches ShotGrid's actual Task status codes exactly (see backend section's
# SHOT_STAGE_TO_SG_STATUS) rather than the richer 6-stage list this was
# originally forked from in JiffySchedule — shrunk 2026-07-24 once the real
# site's Task statuses turned out to be fixed at Waiting to Start/In
# Progress/Final rather than reconfigurable to match a custom list.
SHOT_STAGES  = ["Waiting to Start", "In Progress", "Final"]
ASSET_STAGES = ["WIP", "Testing", "Production Ready", "Omit"]

STAGE_COLORS = {
    "Waiting to Start": "#607d8b",
    "In Progress":      "#e0a030",
    "Final":            "#4caf50",
    "WIP":              "#7a93ad",
    "Testing":          "#e0a030",
    "Production Ready": "#4caf50",
    "Omit":             "#e05050",
}

THUMB_W, THUMB_H = 128, 72
_ITEM_MIME = "application/x-jiffy-item"

_LIST_STYLE = (
    f"QListWidget{{background:{PANEL_BG};border:none;color:white;outline:none;}}"
    f"QListWidget::item{{padding:8px 12px;border-bottom:1px solid {BORDER};}}"
    f"QListWidget::item:selected{{background:#3a3a3a;color:white;}}"
    f"QListWidget::item:hover{{background:#303030;}}"
)
_MENU_STYLE = (
    f"QMenu{{background:{PANEL_BG};color:white;border:1px solid {BORDER};}}"
    f"QMenu::item:selected{{background:#444;}}"
)

# ---------------------------------------------------------------------------
# Date helpers  (DD-MM-YYYY throughout the tool)
# ---------------------------------------------------------------------------
def _parse_dmy(s):
    """Parse a date string → date, accepts DD-MM-YYYY, DD/MM/YYYY, or YYYY-MM-DD."""
    if not s or not s.strip():
        return None
    s = s.strip()
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return _datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None

def _today_dmy():
    return _date.today().strftime("%d-%m-%Y")

def _proximity_badge(due_str):
    """Return (text, color_hex) countdown badge for a DD-MM-YYYY due date."""
    d = _parse_dmy(due_str)
    if d is None:
        return "—", SUBTEXT
    days = (d - _date.today()).days
    if days < 0:   return "OVERDUE",      "#e05050"
    if days == 0:  return "TODAY",        "#e05050"
    if days <= 7:  return f"{days}d  ⚠",  "#e0a030"
    if days <= 30: return f"{days}d",     "#c8a000"
    return f"{days}d",                    "#4a7a4a"

def _prod_week(target, w1_start, hol_start=None, hol_end=None):
    """
    Production week number for *target* (date), counting from w1_start (date).
    Holiday period [hol_start, hol_end] is excluded from the week count.
    Returns None if w1_start is None or target < w1_start.
    """
    if w1_start is None or target < w1_start:
        return None
    days = (target - w1_start).days
    if hol_start and hol_end and hol_start <= hol_end:
        ov_s = max(w1_start, hol_start)
        ov_e = min(target,   hol_end)
        if ov_e >= ov_s:
            days -= (ov_e - ov_s).days + 1
    return max(1, days // 7 + 1) if days >= 0 else None


# ---------------------------------------------------------------------------
# RV launch — ported from pipeDev/shotSubDev/shotSub.py (same working
# implementation, adapted to module-level functions with a distinct RV tag
# so Jiffy SG's RV window doesn't collide with shotSub's). Used by
# ItemRowWidget._do_launch_rv (Shot thumbnail click) and _encode_to_mp4
# above (rvio, from the same RV install).
# ---------------------------------------------------------------------------
_JIFFYSG_RV_TAG = "jiffySG"


def _rv_install_roots_from_registry():
    """Reads InstallLocation from the Windows Uninstall registry for any
    RV / Shotgun / ShotGrid / Flow Production Tracking entry. Install paths
    and version-folder names vary by machine/imaging, but the installer
    always registers the real path here."""
    try:
        import winreg
    except ImportError:
        return []

    hives_and_keys = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]

    roots = []
    for hive, key_path in hives_and_keys:
        try:
            key = winreg.OpenKey(hive, key_path)
        except OSError:
            continue

        for i in range(winreg.QueryInfoKey(key)[0]):
            try:
                subkey = winreg.OpenKey(key, winreg.EnumKey(key, i))
                display_name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                if re.search(r"\bRV\b|Shotgun|ShotGrid|Flow Production Tracking", display_name, re.IGNORECASE):
                    install_location = winreg.QueryValueEx(subkey, "InstallLocation")[0]
                    if install_location:
                        roots.append(install_location)
            except OSError:
                continue

    return roots


def find_rv_executable(exe_name):
    """Locates an RV binary by name (e.g. "rvpush", "rv", "rvio"). Checks,
    in order: the SHOTSUB_RV_HOME env var override (shared with shotSub.py
    deliberately, same RV install), PATH, the Windows registry install
    location, then common Autodesk/Shotgun RV install locations on Windows
    and Mac. Returns the highest version found."""
    env_home = os.environ.get("SHOTSUB_RV_HOME")
    if env_home:
        for candidate in (
            os.path.join(env_home, exe_name + ".exe"),
            os.path.join(env_home, "bin", exe_name + ".exe"),
            os.path.join(env_home, exe_name),
            os.path.join(env_home, "bin", exe_name),
        ):
            if os.path.isfile(candidate):
                return candidate
        print("jiffySG: SHOTSUB_RV_HOME is set to '{0}' but no {1} was found there.".format(env_home, exe_name))

    found = shutil.which(exe_name)
    if found:
        return found

    candidates = []

    if cmds.about(nt=True):
        for install_root in _rv_install_roots_from_registry():
            for candidate in (
                os.path.join(install_root, exe_name + ".exe"),
                os.path.join(install_root, "bin", exe_name + ".exe"),
            ):
                if os.path.isfile(candidate):
                    candidates.append(candidate)

        search_globs = [
            r"C:\Program Files\Autodesk\RV-*\bin\{0}.exe".format(exe_name),
            r"C:\Program Files\Shotgun\RV-*\bin\{0}.exe".format(exe_name),
            r"C:\Program Files\ShotGrid\RV-*\bin\{0}.exe".format(exe_name),
        ]
    elif cmds.about(mac=True):
        search_globs = [
            "/Applications/RV*.app/Contents/MacOS/{0}".format(exe_name),
            "/Applications/Autodesk/RV-*.app/Contents/MacOS/{0}".format(exe_name),
            "/Applications/Shotgun/RV*.app/Contents/MacOS/{0}".format(exe_name),
            os.path.expanduser("~/Applications/RV*.app/Contents/MacOS/{0}".format(exe_name)),
        ]
    else:
        search_globs = [
            "/usr/bin/{0}".format(exe_name),
            "/usr/local/bin/{0}".format(exe_name),
        ]

    for pattern in search_globs:
        candidates.extend(glob.glob(pattern))

    if not candidates:
        return ""

    def version_key(path):
        match = re.search(r"RV-([\d.]+)", path)
        if not match:
            return (0,)
        return tuple(int(part) for part in match.group(1).split("."))

    candidates.sort(key=version_key)
    return candidates[-1]


def _warn_from_thread(message):
    maya.utils.executeInMainThreadWithResult(lambda: QtWidgets.QMessageBox.warning(None, "Launch in RV", message))


def _push_to_rv(cmd):
    # Maya has no console of its own, so each subprocess.run() below would
    # otherwise flash open a new console window for rvpush -- CREATE_NO_WINDOW
    # stops that (Windows-only flag; harmless no-op value on other platforms).
    no_window_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    # When no tagged RV is running, rvpush's cold start spawns RV but does not
    # forward the media (exit code 15) -- the sequence only loads once that new
    # session's network listener comes up, so retry the push briefly until it does.
    # Only the first attempt is allowed to spawn: exit 15 means "started a new RV",
    # so retrying the same command with spawning still enabled would cold-start a
    # second (and third...) RV every second a slow-starting session takes to bring
    # its listener up. RVPUSH_RV_EXECUTABLE_PATH=none on every retry after the first
    # tells rvpush not to spawn anything -- it just fails to connect (exit 11) until
    # the one RV we already started is ready.
    no_spawn_env = os.environ.copy()
    no_spawn_env["RVPUSH_RV_EXECUTABLE_PATH"] = "none"

    for attempt in range(15):
        spawning_allowed = (attempt == 0)
        env = os.environ if spawning_allowed else no_spawn_env
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, env=env,
                creationflags=no_window_flags,
            )
        except Exception as exc:
            _warn_from_thread("Failed to launch RV: {0}".format(exc))
            return

        if result.returncode == 0:
            return

        if result.returncode == 15 or (result.returncode == 11 and not spawning_allowed):
            time.sleep(1)
            continue

        _warn_from_thread("Failed to open sequence in RV (rvpush exit {0}): {1}".format(
            result.returncode, (result.stderr or result.stdout or "").strip()
        ))
        return

    _warn_from_thread("Timed out waiting for a newly-launched RV to accept the playblast sequence.")


def open_in_rv(prefix):
    rvpush = find_rv_executable("rvpush")
    if not rvpush:
        QtWidgets.QMessageBox.warning(None, "Launch in RV", "Could not find RV (rvpush) on this machine.")
        return

    sequence_pattern = prefix + ".#.jpg"
    cmd = [rvpush, "-tag", _JIFFYSG_RV_TAG, "set", sequence_pattern]

    # rvpush blocks synchronously while it connects -- see _push_to_rv's own
    # comment for why this runs on a background thread rather than Maya's
    # main thread (mirrors shotSub.py's open_in_rv/_push_to_rv exactly).
    thread = threading.Thread(target=_push_to_rv, args=(cmd,))
    thread.daemon = True
    thread.start()


# ---------------------------------------------------------------------------
# ShotGrid async helper — every ShotGrid network call from the UI goes
# through this. ShotGrid calls are blocking HTTP; running them on Maya's
# main thread would freeze the whole UI for the round trip. Mirrors the
# threading pattern already established in mpToolSet/mpAnim/scripts/
# pbTool.py (_push_to_rv/_warn_from_thread) for exactly this reason.
# ---------------------------------------------------------------------------
def _run_sg_async(fn, on_done):
    """Run fn() on a daemon thread. on_done(result, error) is always called
    back on Maya's main thread — error is the caught Exception, or None.

    Primes the config cache synchronously, on the caller's thread, before
    starting the worker — see _config_cache's docstring above for why this
    matters (cmds.internalVar is not safe to call from the worker thread)."""
    try:
        _load_config()
    except Exception as exc:
        on_done(None, exc)
        return

    def worker():
        try:
            result = fn()
        except Exception as exc:
            maya.utils.executeInMainThreadWithResult(lambda: on_done(None, exc))
            return
        maya.utils.executeInMainThreadWithResult(lambda: on_done(result, None))
    threading.Thread(target=worker, daemon=True).start()


# ---------------------------------------------------------------------------
# Stage badge
# ---------------------------------------------------------------------------
class StageBadge(QtWidgets.QLabel):
    stage_changed = QtCore.Signal(str)

    def __init__(self, stage="Blocking", stages=None, parent=None):
        super().__init__(parent)
        self._stages = stages or SHOT_STAGES
        self.setFixedSize(90, 24)
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.set_stage(stage)

    def set_stage(self, stage):
        if stage not in self._stages:
            stage = self._stages[0]
        color = STAGE_COLORS.get(stage, "#888")
        self.setText(stage)
        self.setStyleSheet(
            f"background:{color}; color:white; border-radius:4px;"
            f"font-weight:bold; font-size:11px; padding:2px 6px;"
        )

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            menu = QtWidgets.QMenu(self)
            menu.setStyleSheet(_MENU_STYLE)
            actions = {menu.addAction(s): s for s in self._stages}
            chosen = menu.exec_(self.mapToGlobal(event.pos()))
            if chosen in actions:
                self.set_stage(actions[chosen])
                self.stage_changed.emit(actions[chosen])
        super().mousePressEvent(event)


# ---------------------------------------------------------------------------
# Thumbnail label
# ---------------------------------------------------------------------------
class ThumbnailLabel(QtWidgets.QLabel):
    """Read-only display of the Shot/Asset's latest published playblast
    thumbnail (set via ItemRowWidget._refresh_labels from
    item_data["thumbnail"] — either a live-pushed local frame path, or a
    downloaded ShotGrid-thumbnail cache file, see jiffySG.py's backend
    list_entity_latest_activity/_download_shot_thumbnail). Click launches
    that playblast in RV — no more local capture/browse, killed in favour
    of this being purely ShotGrid-driven."""
    launch_requested = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(THUMB_W, THUMB_H)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self._set_placeholder()

    def _set_placeholder(self):
        self.clear()
        self.setText("No playblast yet")
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setStyleSheet(
            f"background:#333; border:1px solid {BORDER}; color:{SUBTEXT}; font-size:10px;"
        )

    def set_image(self, path):
        if path and os.path.exists(path):
            pix = QtGui.QPixmap(path).scaled(
                THUMB_W, THUMB_H,
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation,
            )
            self.setPixmap(pix)
            self.setAlignment(QtCore.Qt.AlignCenter)
            self.setStyleSheet(f"background:#333; border:1px solid {BORDER};")
        else:
            self._set_placeholder()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.launch_requested.emit()
        super().mousePressEvent(event)


class _InlineNotesEdit(QtWidgets.QPlainTextEdit):
    """Read-only display of the Shot's latest ShotGrid Note (see
    ItemRowWidget._refresh_labels, item_data["sg_latest_note"]) — no longer
    a local free-text field; Jiffy SG only ever shows the single latest
    note, full history stays in ShotGrid itself."""


# ---------------------------------------------------------------------------
# Item row
# ---------------------------------------------------------------------------
class ItemRowWidget(QtWidgets.QFrame):
    edit_requested   = QtCore.Signal(dict)
    delete_requested = QtCore.Signal(str)
    data_changed     = QtCore.Signal(dict)

    def __init__(self, item_data, item_label="Shot", stages=None, parent=None):
        super().__init__(parent)
        self.item_data  = item_data
        self.item_label = item_label
        self._stages    = stages or SHOT_STAGES
        self._drag_start = None
        self.setFixedHeight(90)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setStyleSheet(
            f"ItemRowWidget, QFrame{{background:{ITEM_BG};}}"
            f"ItemRowWidget:hover, QFrame:hover{{background:{ITEM_HOVER};}}"
        )
        self._build()
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu)

    def _build(self):
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(4, 8, 14, 8)
        row.setSpacing(14)

        self._handle = QtWidgets.QLabel("⠿")
        self._handle.setFixedWidth(16)
        self._handle.setAlignment(QtCore.Qt.AlignCenter)
        self._handle.setStyleSheet(f"color:{SUBTEXT}; font-size:16px;")
        self._handle.setCursor(QtCore.Qt.SizeVerCursor)
        self._handle.installEventFilter(self)
        row.addWidget(self._handle)

        self.thumb = ThumbnailLabel()
        self.thumb.set_image(self.item_data.get("thumbnail", ""))
        self.thumb.launch_requested.connect(self._do_launch_rv)
        row.addWidget(self.thumb)

        col = QtWidgets.QVBoxLayout()
        col.setSpacing(3)
        self.name_lbl   = QtWidgets.QLabel()
        self.name_lbl.setStyleSheet("font-weight:bold; font-size:13px; color:white;")
        self.frames_lbl = QtWidgets.QLabel()
        self.frames_lbl.setStyleSheet(f"font-size:11px; color:{SUBTEXT};")
        self.due_lbl    = QtWidgets.QLabel()
        self.due_lbl.setStyleSheet(f"font-size:11px; color:{SUBTEXT};")
        self.artist_lbl = QtWidgets.QLabel()
        self.artist_lbl.setStyleSheet(f"font-size:11px; color:{SUBTEXT};")
        for lbl in (self.name_lbl, self.frames_lbl, self.due_lbl, self.artist_lbl):
            col.addWidget(lbl)
        row.addLayout(col)

        self.notes_edit = _InlineNotesEdit()
        self.notes_edit.setReadOnly(True)
        self.notes_edit.setPlaceholderText("No notes yet")
        self.notes_edit.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.notes_edit.setStyleSheet(
            f"QPlainTextEdit{{background:{DARK_BG}; color:{SUBTEXT}; font-size:11px;"
            f"border:1px solid {BORDER}; border-radius:3px; padding:3px;}}"
        )
        row.addWidget(self.notes_edit, stretch=1)

        if self.item_label == "Shot":
            self.pomo_btn = QtWidgets.QPushButton("Jiffy Pomo")
            self.pomo_btn.setFixedSize(78, 24)
            self.pomo_btn.setToolTip("Send stage, due date and notes to Jiffy Pomo")
            self.pomo_btn.setStyleSheet(
                "QPushButton{background:#2e5a2e;color:white;border:none;border-radius:3px;font-size:11px;}"
                "QPushButton:hover{background:#3a7a3a;}"
            )
            self.pomo_btn.clicked.connect(self._send_to_pomo)
            row.addWidget(self.pomo_btn, alignment=QtCore.Qt.AlignVCenter)

        self.badge = StageBadge(stages=self._stages)
        self.badge.stage_changed.connect(self._on_stage_changed)
        row.addWidget(self.badge, alignment=QtCore.Qt.AlignVCenter)

        self._refresh_labels()

    def eventFilter(self, obj, event):
        if obj is self._handle:
            t = event.type()
            if t == QtCore.QEvent.MouseButtonPress and event.button() == QtCore.Qt.LeftButton:
                self._drag_start = QtCore.QPoint(event.pos())
                return True
            if t == QtCore.QEvent.MouseMove and self._drag_start is not None:
                if (event.pos() - self._drag_start).manhattanLength() >= QtWidgets.QApplication.startDragDistance():
                    self._start_drag(self._handle.mapTo(self, event.pos()))
                    self._drag_start = None
                return True
            if t == QtCore.QEvent.MouseButtonRelease:
                self._drag_start = None
        return super().eventFilter(obj, event)

    def _start_drag(self, hotspot):
        drag = QtGui.QDrag(self)
        mime = QtCore.QMimeData()
        mime.setData(_ITEM_MIME, QtCore.QByteArray(self.item_data.get("name", "").encode()))
        drag.setMimeData(mime)
        drag.setPixmap(self.grab())
        drag.setHotSpot(hotspot)
        drag.exec_(QtCore.Qt.MoveAction)

    def _refresh_labels(self):
        d = self.item_data
        self.name_lbl.setText(d.get("name", ""))
        fs, fe = d.get("frame_start", ""), d.get("frame_end", "")
        self.frames_lbl.setText(f"Frames: {fs} – {fe}" if fs or fe else "")
        due = d.get("due_date", "")
        self.due_lbl.setText(f"Due: {due}" if due else "Due: —")
        artist = d.get("artist", "")
        self.artist_lbl.setText(f"Artist: {artist}" if artist else "Artist: —")
        self.notes_edit.setPlainText(d.get("sg_latest_note", ""))
        self.badge.set_stage(d.get("stage", self._stages[0]))
        self.thumb.set_image(d.get("thumbnail", ""))

    def _do_launch_rv(self):
        entity_type = self.item_label   # "Shot" or "Asset"
        entity_id = self.item_data.get("sg_shot_id" if entity_type == "Shot" else "sg_asset_id")
        if not entity_id:
            QtWidgets.QMessageBox.information(
                self, "Launch in RV",
                "This {0} isn't linked to ShotGrid yet — no published playblast to open.".format(entity_type)
            )
            return

        cmds.inViewMessage(amg='Loading RV…', pos='midCenter', fade=True)

        def work():
            return get_latest_playblast_path(entity_type, entity_id)   # live ShotGrid lookup, not cached

        def done(result, error):
            if error is not None:
                QtWidgets.QMessageBox.warning(
                    self, "Launch in RV", "Could not reach ShotGrid:\n\n{0}".format(error)
                )
            elif not result:
                QtWidgets.QMessageBox.information(
                    self, "Launch in RV", "No published playblast found for this Shot yet."
                )
            elif not os.path.isdir(result):
                QtWidgets.QMessageBox.warning(
                    self, "Launch in RV",
                    "The published playblast folder isn't reachable from this machine:\n\n"
                    "{0}\n\n(playblasts on portable drives / different machines don't "
                    "resolve here.)".format(result)
                )
            else:
                prefix = _frame_sequence_prefix(result)
                if prefix:
                    open_in_rv(prefix)
                else:
                    QtWidgets.QMessageBox.warning(
                        self, "Launch in RV", "No frames found in:\n\n{0}".format(result)
                    )

        _run_sg_async(work, done)

    def _on_stage_changed(self, stage):
        self.item_data["stage"] = stage
        self.data_changed.emit(self.item_data)

    def _send_to_pomo(self):
        try:
            import Jiffypomo
        except ImportError:
            QtWidgets.QMessageBox.warning(
                self, "JiffyPomo", "JiffyPomo isn't installed alongside JiffySchedule."
            )
            return
        window = Jiffypomo.run_jiffypomo()
        window.stage.setText(self.item_data.get("stage", ""))
        window.due.setText(self.item_data.get("due_date", ""))
        window.task_text.setPlainText(self.item_data.get("notes", ""))
        window.save_state_auto()

    def _context_menu(self, pos):
        menu = QtWidgets.QMenu(self)
        menu.setStyleSheet(_MENU_STYLE)
        edit_act   = menu.addAction(f"Edit {self.item_label}")
        delete_act = menu.addAction(f"Delete {self.item_label}")
        action = menu.exec_(self.mapToGlobal(pos))
        if action == edit_act:
            self.edit_requested.emit(self.item_data)
        elif action == delete_act:
            self.delete_requested.emit(self.item_data.get("name", ""))


# ---------------------------------------------------------------------------
# Item dialog
# ---------------------------------------------------------------------------
class ItemDialog(QtWidgets.QDialog):
    def __init__(self, item_data=None, item_label="Shot", stages=None, artist_names=None,
                 project_name=None, parent=None):
        super().__init__(parent)
        self._stages       = stages or SHOT_STAGES
        self._artist_names = artist_names or []
        self.item_label     = item_label
        self._project_name  = project_name
        self._is_new    = item_data is None
        self.setWindowTitle(f"Add {item_label}" if self._is_new else f"Edit {item_label}")
        self.setMinimumWidth(340)
        self.setStyleSheet(
            f"QDialog{{background:{DARK_BG};color:white;}}"
            f"QLabel{{color:white;}}"
            f"QLineEdit{{background:{ITEM_BG};color:white;border:1px solid {BORDER};padding:4px;}}"
            f"QComboBox{{background:{ITEM_BG};color:white;border:1px solid {BORDER};padding:4px;}}"
            f"QComboBox QAbstractItemView{{background:{ITEM_BG};color:white;selection-background-color:#444;}}"
            f"QPlainTextEdit{{background:{ITEM_BG};color:white;border:1px solid {BORDER};padding:4px;}}"
            f"QPushButton{{background:#444;color:white;border:1px solid {BORDER};padding:4px 12px;}}"
            f"QPushButton:hover{{background:#555;}}"
        )
        self._data = item_data.copy() if item_data else {}
        self._build()

    def _build(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)
        self.name_edit        = QtWidgets.QLineEdit(self._data.get("name", ""))
        self.frame_start_edit = QtWidgets.QLineEdit(str(self._data.get("frame_start", "")))
        self.frame_end_edit   = QtWidgets.QLineEdit(str(self._data.get("frame_end", "")))
        default_due = self._data.get("due_date", _today_dmy())
        self.due_edit    = QtWidgets.QLineEdit(default_due)
        self.due_edit.setPlaceholderText("DD-MM-YYYY")
        self.artist_edit = QtWidgets.QComboBox()
        # Deliberately NOT setEditable(True): the Artist list is now the
        # Project's real ShotGrid roster (see list_project_artists()), and
        # letting a student type an arbitrary name here would defeat the
        # whole point of restricting assignment to real project members.
        self.artist_edit.addItem("")  # explicit "unassigned"
        self.artist_edit.addItems(self._artist_names)
        current_artist = self._data.get("artist", "")
        if current_artist and current_artist not in self._artist_names:
            # Preserve an already-assigned name even if they've since fallen
            # out of the roster (e.g. removed from the Project) rather than
            # silently discarding it.
            self.artist_edit.addItem(current_artist)
        self.artist_edit.setCurrentText(current_artist)
        self.stage_combo = QtWidgets.QComboBox()
        for s in self._stages:
            self.stage_combo.addItem(s)
        self.stage_combo.setCurrentText(self._data.get("stage", self._stages[0]))
        self.notes_edit = QtWidgets.QPlainTextEdit(self._data.get("notes", ""))
        self.notes_edit.setFixedHeight(70)
        layout.addRow(f"{self.item_label} Name:", self.name_edit)
        if self.item_label != "Asset":
            layout.addRow("Frame Start:", self.frame_start_edit)
            layout.addRow("Frame End:",   self.frame_end_edit)
        layout.addRow("Due Date:",  self.due_edit)
        layout.addRow("Artist:",    self.artist_edit)
        layout.addRow("Stage:",     self.stage_combo)
        layout.addRow("Notes:",     self.notes_edit)

        # "Set Project" line — links this row's local Maya project folder to
        # ShotGrid (writes shotgrid_link.json there) and switches Maya's
        # active project to it. See _do_set_project(). ShotGrid Project is
        # read-only here, inherited from whichever Project is active in the
        # Nav panel — no per-row picker, since a row's Project is already
        # unambiguous (see jiffySG_brief.md's access-control reasoning).
        self._path_lbl = QtWidgets.QLabel(self._data.get("local_project_path") or "Not set")
        self._path_lbl.setStyleSheet(f"color:{SUBTEXT};")
        self._change_btn = QtWidgets.QPushButton("Change…")
        self._change_btn.setVisible(bool(self._data.get("local_project_path")))
        self._change_btn.clicked.connect(self._do_change_folder)
        self._set_project_btn = QtWidgets.QPushButton("Set Project")
        self._set_project_btn.clicked.connect(self._do_set_project)
        project_row = QtWidgets.QWidget()
        project_row_layout = QtWidgets.QHBoxLayout(project_row)
        project_row_layout.setContentsMargins(0, 0, 0, 0)
        project_row_layout.addWidget(self._path_lbl, stretch=1)
        project_row_layout.addWidget(self._change_btn)
        project_row_layout.addWidget(self._set_project_btn)
        layout.addRow(f"ShotGrid Project: {self._project_name or '—'}", project_row)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def _do_change_folder(self):
        self._data["local_project_path"] = ""
        self._do_set_project()

    def _do_set_project(self):
        """Deliberately synchronous (not _run_sg_async) — an occasional,
        explicit "link" action can afford a brief blocking pause, same
        reasoning as shotSub.link_to_shotgrid(), and avoids new
        async/dialog-lifetime complexity (the modal dialog could be closed
        before an async callback fires)."""
        entity_type = self.item_label   # "Shot" or "Asset"
        entity_code = self.name_edit.text().strip()
        if not entity_code:
            QtWidgets.QMessageBox.warning(self, "Set Project", "Name this {0} first.".format(entity_type))
            return

        if entity_type == "Shot":
            entity_id = self._data.get("sg_shot_id")
            if not entity_id:
                QtWidgets.QMessageBox.warning(
                    self, "Set Project",
                    "This Shot is still linking to ShotGrid — try again in a moment."
                )
                return
        else:
            entity_id = self._data.get("sg_asset_id")
            if not entity_id:
                if not self._project_name:
                    QtWidgets.QMessageBox.warning(self, "Set Project", "No active ShotGrid Project selected.")
                    return
                try:
                    asset = find_or_create_asset(entity_code, self._project_name)
                except Exception as exc:
                    QtWidgets.QMessageBox.warning(
                        self, "Set Project", "Could not reach ShotGrid:\n\n{0}".format(exc)
                    )
                    return
                entity_id = asset["id"]
                self._data["sg_asset_id"] = entity_id

        path = self._data.get("local_project_path", "")
        if not path or not os.path.isdir(path):
            chosen = QtWidgets.QFileDialog.getExistingDirectory(
                self, "Select Maya Project Folder", path or os.path.expanduser("~")
            )
            if not chosen:
                return
            path = chosen
            self._data["local_project_path"] = path

        try:
            cmds.workspace(path, openWorkspace=True)
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Set Project", "Failed to set Maya project:\n\n{0}".format(exc))
            return

        try:
            self._write_link_marker(path, entity_type, entity_id, entity_code)
        except Exception as exc:
            QtWidgets.QMessageBox.warning(
                self, "Set Project",
                "Maya project set, but failed to write the ShotGrid link marker:\n\n{0}".format(exc)
            )
            return

        self._path_lbl.setText(path)
        self._change_btn.setVisible(True)
        cmds.inViewMessage(
            amg='Maya project set to <hl>{0}</hl>.'.format(entity_code), pos='midCenter', fade=True
        )

    def _write_link_marker(self, project_root, entity_type, entity_id, entity_code):
        """Writes the same shotgrid_link.json shape shotSub.py reads (see
        shotSub.py's write_shotgrid_link()/read_shotgrid_link() — schema
        generalized to sg_entity_type/sg_entity_id/sg_entity_code so it
        covers both Shots and Assets). Deliberately a small self-contained
        write here rather than a shared function with shotSub.py — keeps
        the two files decoupled, matching the existing precedent of
        hand-porting small blocks (e.g. the RV-launch functions) instead of
        creating a new cross-file dependency for something this small."""
        sg = get_connection()
        project = _find_project(sg, self._project_name)
        data = {
            "schema_version": 2,
            "sg_project_id": project["id"],
            "sg_project_name": project["name"],
            "sg_entity_type": entity_type,
            "sg_entity_id": entity_id,
            "sg_entity_code": entity_code,
            "linked_at": _datetime.now().isoformat(timespec="seconds"),
            "linked_by": current_login(),
        }
        with open(os.path.join(project_root, "shotgrid_link.json"), "w") as f:
            json.dump(data, f, indent=2)

    def get_data(self):
        return {
            "name":              self.name_edit.text().strip(),
            "frame_start":       self.frame_start_edit.text().strip(),
            "frame_end":         self.frame_end_edit.text().strip(),
            "due_date":          self.due_edit.text().strip(),
            "artist":            self.artist_edit.currentText().strip(),
            "stage":             self.stage_combo.currentText(),
            "notes":             self.notes_edit.toPlainText().strip(),
            "thumbnail":         self._data.get("thumbnail", ""),
            "sg_shot_id":        self._data.get("sg_shot_id"),
            "sg_asset_id":       self._data.get("sg_asset_id"),
            "sg_latest_note":    self._data.get("sg_latest_note", ""),
            "local_project_path": self._data.get("local_project_path", ""),
        }


# ---------------------------------------------------------------------------
# Drop container — used by ItemListPanel for drag-to-reorder
# ---------------------------------------------------------------------------
class _InsertLine(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        self.setFixedHeight(2)
        self.hide()

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.fillRect(self.rect(), QtGui.QColor("#4caf50"))
        p.end()


class _DropContainer(QtWidgets.QWidget):
    drop_performed = QtCore.Signal(str, int)  # (item_name, target_index)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._line = _InsertLine(self)

    def _gap_at(self, y):
        """Return (line_y, insert_index) for the gap nearest to y."""
        layout = self.layout()
        if layout is None:
            return 0, 0
        count = layout.count() - 1  # last item is stretch
        for i in range(count):
            w = layout.itemAt(i).widget()
            if w and y < w.y() + w.height() // 2:
                return w.y(), i
        last = layout.itemAt(count - 1).widget() if count > 0 else None
        end_y = (last.y() + last.height()) if last else y
        return end_y, count

    def _show_line(self, y):
        self._line.setGeometry(0, max(0, y - 1), self.width(), 2)
        self._line.show()
        self._line.raise_()

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(_ITEM_MIME):
            line_y, _ = self._gap_at(event.pos().y())
            self._show_line(line_y)
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat(_ITEM_MIME):
            line_y, _ = self._gap_at(event.pos().y())
            self._show_line(line_y)
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self._line.hide()

    def dropEvent(self, event):
        if event.mimeData().hasFormat(_ITEM_MIME):
            name = bytes(event.mimeData().data(_ITEM_MIME)).decode()
            _, target_idx = self._gap_at(event.pos().y())
            self._line.hide()
            self.drop_performed.emit(name, target_idx)
            event.acceptProposedAction()


# ---------------------------------------------------------------------------
# Item list panel
# ---------------------------------------------------------------------------
class ItemListPanel(QtWidgets.QWidget):
    data_changed          = QtCore.Signal()
    sg_status             = QtCore.Signal(str, str)   # state "ok"|"error", message
    sg_sequence_resolved  = QtCore.Signal(str, str, int)  # project, group, sg_sequence_id
    refresh_requested     = QtCore.Signal()

    def __init__(self, item_label="Shot", stages=None, parent=None):
        super().__init__(parent)
        self.item_label     = item_label
        self._stages        = stages or SHOT_STAGES
        self._artist_names  = []
        self.items          = []
        self._project       = ""
        self._group         = ""
        self._build()

    def set_artist_names(self, names):
        self._artist_names = list(names)

    def set_context(self, project, group):
        self._project, self._group = project, group

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QtWidgets.QWidget()
        header.setFixedHeight(38)
        header.setStyleSheet(f"background:{PANEL_BG}; border-bottom:1px solid {BORDER};")
        hl = QtWidgets.QHBoxLayout(header)
        hl.setContentsMargins(12, 0, 12, 0)
        self.header_lbl = QtWidgets.QLabel(f"All {self.item_label}s")
        self.header_lbl.setStyleSheet("font-weight:bold; font-size:13px; color:white;")
        hl.addWidget(self.header_lbl)
        hl.addStretch()
        self.add_btn = QtWidgets.QPushButton(f"+ Add {self.item_label}")
        self.add_btn.setEnabled(False)
        self.add_btn.setStyleSheet(
            "QPushButton{background:#2e5a2e;color:white;border:none;padding:4px 14px;border-radius:3px;}"
            "QPushButton:hover{background:#3a7a3a;}"
            "QPushButton:disabled{background:#333;color:#666;}"
        )
        self.add_btn.clicked.connect(self._add_item)
        hl.addWidget(self.add_btn)
        refresh_btn = QtWidgets.QPushButton("⟳ Refresh")
        refresh_btn.setToolTip("Re-pull latest notes/thumbnails from ShotGrid for this Project")
        refresh_btn.setStyleSheet(
            "QPushButton{background:#444;color:white;border:none;padding:4px 14px;border-radius:3px;}"
            "QPushButton:hover{background:#555;}"
        )
        refresh_btn.clicked.connect(self.refresh_requested)
        hl.addWidget(refresh_btn)
        layout.addWidget(header)

        col_bar = QtWidgets.QWidget()
        col_bar.setFixedHeight(24)
        col_bar.setStyleSheet(f"background:{PANEL_BG}; border-bottom:1px solid {BORDER};")
        cl = QtWidgets.QHBoxLayout(col_bar)
        cl.setContentsMargins(10, 0, 14, 0)
        cl.setSpacing(14)
        for text, w in [("Thumbnail", THUMB_W), (f"{self.item_label} Details", 0), ("Stage", 90)]:
            lbl = QtWidgets.QLabel(text)
            lbl.setStyleSheet(f"font-size:10px; color:{SUBTEXT};")
            if w:
                lbl.setFixedWidth(w)
                cl.addWidget(lbl)
            else:
                cl.addWidget(lbl, stretch=1)
        layout.addWidget(col_bar)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea{{border:none; background:{DARK_BG};}}")
        self.container = _DropContainer()
        self.container.setStyleSheet(f"background:{DARK_BG};")
        self.container.drop_performed.connect(self._on_drop)
        self.vbox = QtWidgets.QVBoxLayout(self.container)
        self.vbox.setContentsMargins(0, 0, 0, 0)
        self.vbox.setSpacing(1)
        self.vbox.addStretch()
        scroll.setWidget(self.container)
        layout.addWidget(scroll)

    def set_content(self, label, items, writable=False):
        self.header_lbl.setText(label)
        self.items = list(items)
        self.add_btn.setEnabled(writable)
        self._rebuild()

    def _rebuild(self):
        while self.vbox.count() > 1:
            item = self.vbox.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for item in self.items:
            self._append_row(item)

    def _append_row(self, item_data):
        row = ItemRowWidget(item_data, item_label=self.item_label, stages=self._stages)
        row.edit_requested.connect(self._edit_item)
        row.delete_requested.connect(self._delete_item)
        row.data_changed.connect(self._on_row_changed)
        self.vbox.insertWidget(self.vbox.count() - 1, row)

    def _add_item(self):
        defaults = {}
        if self.item_label == "Shot":
            defaults["frame_start"] = str(int(cmds.playbackOptions(q=True, minTime=True)))
            defaults["frame_end"]   = str(int(cmds.playbackOptions(q=True, maxTime=True)))
            scene_path = cmds.file(query=True, sceneName=True)
            defaults["name"] = os.path.splitext(os.path.basename(scene_path))[0] if scene_path else ""

        dlg = ItemDialog(item_data=defaults if defaults else None,
                         item_label=self.item_label, stages=self._stages,
                         artist_names=self._artist_names, project_name=self._project, parent=self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            data = dlg.get_data()
            if data["name"]:
                self.items.append(data)
                self._append_row(data)
                self.data_changed.emit()
                if self.item_label == "Shot" and self._project and self._group:
                    self._push_shot_create(data)

    def _push_shot_create(self, item_data):
        project, group, shot_code = self._project, self._group, item_data.get("name", "")
        frame_start, frame_end = item_data.get("frame_start"), item_data.get("frame_end")
        stage, due_date, artist = item_data.get("stage"), item_data.get("due_date"), item_data.get("artist")
        thumbnail = item_data.get("thumbnail")

        def work():
            shot = create_shot(shot_code, project, sequence_name=group)
            seq  = create_sequence(group, project) if group else None
            warnings = []
            try:
                update_shot_frame_range(shot["id"], frame_start, frame_end)
            except Exception as exc:
                warnings.append(str(exc))
            try:
                update_shot_task(shot["id"], project, stage=stage, due_date=due_date, artist_name=artist)
            except Exception as exc:
                warnings.append(str(exc))
            try:
                upload_shot_thumbnail(shot["id"], thumbnail)
            except Exception as exc:
                warnings.append(str(exc))
            return shot, seq, warnings

        def done(result, error):
            if error is not None:
                self.sg_status.emit("error", str(error))
                return
            shot, seq, warnings = result
            if any(existing is item_data for existing in self.items):
                item_data["sg_shot_id"] = shot["id"]
                self.data_changed.emit()
            else:
                print("jiffySG: Shot '{0}' created (id {1}) but local item no longer present".format(
                    shot_code, shot["id"]))
            if seq:
                self.sg_sequence_resolved.emit(project, group, seq["id"])
            self.sg_status.emit("error", "; ".join(warnings)) if warnings else self.sg_status.emit("ok", "")

        _run_sg_async(work, done)

    def _push_shot_field_sync(self, item_data):
        """Re-push Frame Start/End + Stage/Due Date/Artist + Thumbnail for an
        already-created Shot (has sg_shot_id). Fires on every local edit/row
        change to a Shot item — cheap idempotent overwrite, simpler than
        diffing which specific field actually changed (yes, this means a
        thumbnail gets silently re-uploaded to ShotGrid on any unrelated
        edit too — same tradeoff already accepted for the other fields)."""
        shot_id = item_data.get("sg_shot_id")
        if not shot_id or not self._project:
            return
        project = self._project
        frame_start, frame_end = item_data.get("frame_start"), item_data.get("frame_end")
        stage, due_date, artist = item_data.get("stage"), item_data.get("due_date"), item_data.get("artist")
        thumbnail = item_data.get("thumbnail")

        def work():
            warnings = []
            try:
                update_shot_frame_range(shot_id, frame_start, frame_end)
            except Exception as exc:
                warnings.append(str(exc))
            try:
                update_shot_task(shot_id, project, stage=stage, due_date=due_date, artist_name=artist)
            except Exception as exc:
                warnings.append(str(exc))
            try:
                upload_shot_thumbnail(shot_id, thumbnail)
            except Exception as exc:
                warnings.append(str(exc))
            return warnings

        def done(result, error):
            if error is not None:
                self.sg_status.emit("error", str(error))
            elif result:
                self.sg_status.emit("error", "; ".join(result))
            else:
                self.sg_status.emit("ok", "")

        _run_sg_async(work, done)

    def _edit_item(self, item_data):
        idx = next((i for i, s in enumerate(self.items) if s.get("name") == item_data.get("name")), None)
        if idx is None:
            return
        dlg = ItemDialog(item_data=item_data, item_label=self.item_label, stages=self._stages,
                         artist_names=self._artist_names, project_name=self._project, parent=self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            self.items[idx] = dlg.get_data()
            self._rebuild()
            self.data_changed.emit()
            if self.item_label == "Shot":
                self._push_shot_field_sync(self.items[idx])

    def _delete_item(self, name):
        reply = QtWidgets.QMessageBox.question(
            self, f"Delete {self.item_label}", f"Delete '{name}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )
        if reply == QtWidgets.QMessageBox.Yes:
            removed = next((s for s in self.items if s.get("name") == name), None)
            self.items = [s for s in self.items if s.get("name") != name]
            self._rebuild()
            self.data_changed.emit()
            if self.item_label == "Shot" and removed and removed.get("sg_shot_id"):
                self._push_shot_delete(removed["sg_shot_id"])

    def _push_shot_delete(self, shot_id):
        def work():
            return delete_shot(shot_id)

        def done(result, error):
            if error is not None:
                self.sg_status.emit("error", str(error))
            else:
                self.sg_status.emit("ok", "")

        _run_sg_async(work, done)

    def _on_row_changed(self, item_data):
        idx = next((i for i, s in enumerate(self.items) if s.get("name") == item_data.get("name")), None)
        if idx is not None:
            self.items[idx] = item_data
        self.data_changed.emit()
        if self.item_label == "Shot":
            self._push_shot_field_sync(item_data)

    def _on_drop(self, name, target_idx):
        src_idx = next((i for i, s in enumerate(self.items) if s.get("name") == name), None)
        if src_idx is None or src_idx == target_idx:
            return
        item = self.items.pop(src_idx)
        if target_idx > src_idx:
            target_idx -= 1
        self.items.insert(target_idx, item)
        self._rebuild()
        self.data_changed.emit()


# ---------------------------------------------------------------------------
# Schedule page — data management + ItemListPanel
# ---------------------------------------------------------------------------
class SchedulePage(QtWidgets.QWidget):
    data_changed          = QtCore.Signal()
    sg_status             = QtCore.Signal(str, str)
    sg_sequence_resolved  = QtCore.Signal(str, str, int)
    refresh_requested     = QtCore.Signal()

    def __init__(self, item_label="Shot", stages=None, parent=None):
        super().__init__(parent)
        self.item_label       = item_label
        self._stages          = stages or SHOT_STAGES
        self._data            = {}
        self._current_project = ""
        self._active_group    = ""

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.item_panel = ItemListPanel(item_label=item_label, stages=self._stages)
        self.item_panel.data_changed.connect(self._on_items_changed)
        self.item_panel.sg_status.connect(self.sg_status)
        self.item_panel.sg_sequence_resolved.connect(self.sg_sequence_resolved)
        self.item_panel.refresh_requested.connect(self.refresh_requested)
        layout.addWidget(self.item_panel)

    def set_artist_names(self, names):
        self.item_panel.set_artist_names(names)

    def set_project(self, project):
        self._flush()
        self._current_project = project
        self._active_group    = ""
        self._refresh_view()

    def select_group(self, group):
        self._flush()
        self._active_group = group
        if group:
            self._data.setdefault(self._current_project, {}).setdefault(group, [])
        self._refresh_view()

    def project_added(self, name):
        self._data.setdefault(name, {})

    def project_removed(self, name):
        if self._current_project == name:
            self._current_project = ""
            self._active_group = ""
        self._data.pop(name, None)

    def get_groups_for_project(self, project):
        return list(self._data.get(project, {}).keys())

    def _flush(self):
        if self._current_project and self._active_group:
            self._data.setdefault(self._current_project, {})[self._active_group] = list(self.item_panel.items)

    def _refresh_view(self):
        proj  = self._current_project
        group = self._active_group
        if not proj:
            items = [i for p in self._data.values() for g in p.values() for i in g]
            self.item_panel.set_content(f"All {self.item_label}s", items, writable=False)
            self.item_panel.set_context("", "")
        elif not group:
            items = [i for g in self._data.get(proj, {}).values() for i in g]
            self.item_panel.set_content(f"{proj}  —  All {self.item_label}s", items, writable=False)
            self.item_panel.set_context(proj, "")
        else:
            items = self._data.get(proj, {}).get(group, [])
            self.item_panel.set_content(group, items, writable=True)
            self.item_panel.set_context(proj, group)

    def _on_items_changed(self):
        self._flush()
        self.data_changed.emit()

    def get_data(self):
        self._flush()
        return dict(self._data)

    def load_data(self, data):
        if any(isinstance(v, list) for v in data.values()):
            data = {}
        self._data = data
        self._refresh_view()


# ---------------------------------------------------------------------------
# Pie chart — donut style, % complete in centre
# ---------------------------------------------------------------------------
class PieChartWidget(QtWidgets.QWidget):
    def __init__(self, title="", complete_stages=None, parent=None):
        super().__init__(parent)
        self.title           = title
        self.complete_stages = complete_stages or []
        self._counts         = {}
        self.setFixedSize(200, 220)

    def set_data(self, counts):
        self._counts = {k: v for k, v in counts.items() if v > 0}
        self.update()

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        side = 172
        cx, cy = self.width() / 2, side / 2 + 4
        cr = QtCore.QRectF(cx - side / 2, cy - side / 2, side, side)
        total = sum(self._counts.values())
        if total == 0:
            p.setPen(QtGui.QColor(BORDER))
            p.setBrush(QtGui.QColor("#333"))
            p.drawEllipse(cr)
            p.setPen(QtGui.QColor(SUBTEXT))
            p.drawText(cr, QtCore.Qt.AlignCenter, "No data")
        else:
            start = 90 * 16
            for stage, count in self._counts.items():
                span = max(1, int(round(count / total * 360 * 16)))
                p.setBrush(QtGui.QColor(STAGE_COLORS.get(stage, "#888")))
                p.setPen(QtCore.Qt.NoPen)
                p.drawPie(cr, start, -span)
                start -= span
            hole = side * 0.44
            hr = QtCore.QRectF(cx - hole / 2, cy - hole / 2, hole, hole)
            p.setBrush(QtGui.QColor(DARK_BG))
            p.setPen(QtCore.Qt.NoPen)
            p.drawEllipse(hr)
            complete = sum(v for k, v in self._counts.items() if k in self.complete_stages)
            pct = int(complete / total * 100)
            f = QtGui.QFont()
            f.setBold(True)
            f.setPixelSize(22)
            p.setFont(f)
            p.setPen(QtGui.QColor(TEXT))
            p.drawText(hr, QtCore.Qt.AlignCenter, f"{pct}%")
        if self.title:
            tr = QtCore.QRectF(0, side + 10, self.width(), 20)
            f2 = QtGui.QFont()
            f2.setPixelSize(11)
            p.setFont(f2)
            p.setPen(QtGui.QColor(SUBTEXT))
            p.drawText(tr, QtCore.Qt.AlignCenter, self.title)
        p.end()


# ---------------------------------------------------------------------------
# Milestone dialog — DD-MM-YYYY, today default, optional extension note
# ---------------------------------------------------------------------------
class MilestoneDialog(QtWidgets.QDialog):
    def __init__(self, data=None, prod_settings=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Milestone" if data is None else "Edit Milestone")
        self.setMinimumWidth(340)
        self.setStyleSheet(
            f"QDialog{{background:{DARK_BG};color:white;}}"
            f"QLabel{{color:white;}}"
            f"QLineEdit{{background:{ITEM_BG};color:white;border:1px solid {BORDER};padding:4px;}}"
            f"QPushButton{{background:#444;color:white;border:1px solid {BORDER};padding:4px 12px;}}"
            f"QPushButton:hover{{background:#555;}}"
        )
        self._data = data.copy() if data else {}
        self._is_new = data is None
        self._prod_settings = prod_settings or {}
        self._build()

    def _build(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)
        self.name_edit = QtWidgets.QLineEdit(self._data.get("name", ""))
        default_date = self._data.get("due_date", "")
        self.date_edit = QtWidgets.QLineEdit(default_date)
        self.date_edit.setPlaceholderText("DD-MM-YYYY or W8")
        layout.addRow("Milestone:", self.name_edit)
        layout.addRow("Due Date:",  self.date_edit)
        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def get_data(self):
        raw = self.date_edit.text().strip()
        if raw and _parse_dmy(raw) is None:
            raw = self._week_input_to_date(raw)
        return {
            "name":     self.name_edit.text().strip(),
            "due_date": raw,
        }

    def _week_input_to_date(self, s):
        """Convert 'W8' or '8' to DD-MM-YYYY using production settings. Returns s unchanged if it can't."""
        w1 = _parse_dmy(self._prod_settings.get("week1_start", ""))
        if w1 is None:
            return s
        token = s.strip().upper().lstrip("W")
        try:
            wk = int(token)
        except ValueError:
            return s
        return (w1 + _timedelta(days=7 * (wk - 1))).strftime("%d-%m-%Y")


# ---------------------------------------------------------------------------
# Production schedule settings dialog (opened by clicking the week number)
# ---------------------------------------------------------------------------
class _ProductionSettingsDialog(QtWidgets.QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Production Schedule Settings")
        self.setMinimumWidth(360)
        self.setStyleSheet(
            f"QDialog{{background:{DARK_BG};color:white;}}"
            f"QLabel{{color:white;}}"
            f"QLineEdit{{background:{ITEM_BG};color:white;border:1px solid {BORDER};"
            f"padding:5px;font-size:12px;border-radius:3px;}}"
            f"QSpinBox{{background:{ITEM_BG};color:white;border:1px solid {BORDER};"
            f"padding:5px;font-size:12px;border-radius:3px;}}"
            f"QPushButton{{background:#444;color:white;border:1px solid {BORDER};padding:5px 14px;}}"
            f"QPushButton:hover{{background:#555;}}"
        )
        self._settings = settings
        self._build()

    def _build(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setLabelAlignment(QtCore.Qt.AlignRight)

        self.week1_edit = QtWidgets.QLineEdit(self._settings.get("week1_start", "") or _today_dmy())
        self.week1_edit.setPlaceholderText("DD-MM-YYYY  or  YYYY-MM-DD")

        self.total_weeks_edit = QtWidgets.QLineEdit(str(self._settings.get("total_weeks", 12)))
        self.total_weeks_edit.setValidator(QtGui.QIntValidator(1, 52))

        self.hol_start_edit = QtWidgets.QLineEdit(self._settings.get("holiday_start", ""))
        self.hol_start_edit.setPlaceholderText("DD-MM-YYYY  or  YYYY-MM-DD  (optional)")
        self.hol_end_edit   = QtWidgets.QLineEdit(self._settings.get("holiday_end", ""))
        self.hol_end_edit.setPlaceholderText("DD-MM-YYYY  or  YYYY-MM-DD  (optional)")

        layout.addRow("Week 1 Start:",  self.week1_edit)
        layout.addRow("Total Weeks:",   self.total_weeks_edit)

        sep_lbl = QtWidgets.QLabel("Mid-term break")
        sep_lbl.setStyleSheet(
            f"font-size:10px; font-weight:bold; color:{SUBTEXT}; letter-spacing:1px; padding-top:6px;"
        )
        layout.addRow("", sep_lbl)
        layout.addRow("Break Start:",   self.hol_start_edit)
        layout.addRow("Break End:",     self.hol_end_edit)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def get_data(self):
        return {
            "week1_start":   self.week1_edit.text().strip(),
            "total_weeks":   int(self.total_weeks_edit.text() or "12"),
            "holiday_start": self.hol_start_edit.text().strip(),
            "holiday_end":   self.hol_end_edit.text().strip(),
        }


# ---------------------------------------------------------------------------
# Week timeline bar — drawn with paintEvent
# ---------------------------------------------------------------------------
class _WeekTimelineWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._settings = {}
        self._milestones = []
        self.setMinimumHeight(100)

    def set_settings(self, settings, milestones=None):
        self._settings = settings
        self._milestones = milestones or []
        self.update()

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)

        s    = self._settings
        w1   = _parse_dmy(s.get("week1_start", ""))
        tw   = s.get("total_weeks", 12)
        hs   = _parse_dmy(s.get("holiday_start", ""))
        he   = _parse_dmy(s.get("holiday_end", ""))
        curr = _prod_week(_date.today(), w1, hs, he)

        if w1 is None:
            f = QtGui.QFont()
            f.setPixelSize(11)
            p.setFont(f)
            p.setPen(QtGui.QColor(SUBTEXT))
            p.drawText(
                self.rect(), QtCore.Qt.AlignCenter,
                "Click the week number  ▶  to set up your production schedule"
            )
            p.end()
            return

        # Determine break position (0-based index: insert break BEFORE slot break_slot)
        has_break  = hs is not None and he is not None
        break_slot = None
        if has_break:
            days_to_hol = max(0, (hs - w1).days)
            break_slot  = min(days_to_hol // 7, tw)  # insert break before week (break_slot+1)

        # Build draw list: each entry is ('week', week_num) or ('break',)
        draw_list = []
        for wk in range(1, tw + 1):
            if has_break and break_slot == wk - 1 and wk > 1:
                draw_list.append(("break",))
            draw_list.append(("week", wk))
        # if break is before week 1 (start of semester) still insert at front
        if has_break and break_slot == 0:
            draw_list.insert(0, ("break",))

        n_slots    = len(draw_list)
        ms_strip_h = 18
        margin_x   = 14
        margin_y   = 6
        label_h    = 24
        usable_w   = self.width() - 2 * margin_x
        avail_h    = self.height() - ms_strip_h - 2 * margin_y - label_h
        box_h      = min(avail_h, 28)
        box_y      = ms_strip_h + margin_y + (avail_h - box_h) / 2
        slot_w     = usable_w / n_slots if n_slots else usable_w

        for idx, item in enumerate(draw_list):
            sx = margin_x + idx * slot_w
            bw = max(1.0, slot_w - 3)

            if item[0] == "break":
                p.setBrush(QtGui.QColor("#2a2a2a"))
                p.setPen(QtCore.Qt.NoPen)
                p.drawRoundedRect(QtCore.QRectF(sx + 1.5, box_y, bw, box_h), 3, 3)
                f = QtGui.QFont()
                f.setPixelSize(8)
                p.setFont(f)
                p.setPen(QtGui.QColor(SUBTEXT))
                p.drawText(
                    QtCore.QRectF(sx, box_y, slot_w, box_h),
                    QtCore.Qt.AlignCenter, "BRK"
                )
                p.drawText(
                    QtCore.QRectF(sx, box_y + box_h + 2, slot_w, label_h),
                    QtCore.Qt.AlignCenter, "break"
                )
            else:
                wk      = item[1]
                is_curr = curr is not None and wk == curr
                bg  = QtGui.QColor("#484848") if is_curr else QtGui.QColor("#303030")
                fg  = QtGui.QColor("white")

                p.setBrush(bg)
                p.setPen(QtCore.Qt.NoPen)
                p.drawRoundedRect(QtCore.QRectF(sx + 1.5, box_y, bw, box_h), 3, 3)

                if is_curr:
                    p.setBrush(QtCore.Qt.NoBrush)
                    p.setPen(QtGui.QPen(QtGui.QColor("white"), 1.5))
                    p.drawRoundedRect(QtCore.QRectF(sx + 1.5, box_y, bw, box_h), 3, 3)

                f = QtGui.QFont()
                f.setPixelSize(11)
                f.setBold(is_curr)
                p.setFont(f)
                p.setPen(fg)
                p.drawText(
                    QtCore.QRectF(sx, box_y, slot_w, box_h),
                    QtCore.Qt.AlignCenter, str(wk)
                )
                f2 = QtGui.QFont()
                f2.setPixelSize(8)
                p.setFont(f2)
                p.setPen(QtGui.QColor("white") if is_curr else QtGui.QColor(SUBTEXT))
                p.drawText(
                    QtCore.QRectF(sx, box_y + box_h + 2, slot_w, 11),
                    QtCore.Qt.AlignCenter, f"W{wk}"
                )
                wk_start = w1 + _timedelta(days=7 * (wk - 1))
                f3 = QtGui.QFont()
                f3.setPixelSize(7)
                p.setFont(f3)
                p.setPen(QtGui.QColor(SUBTEXT))
                p.drawText(
                    QtCore.QRectF(sx, box_y + box_h + 13, slot_w, 11),
                    QtCore.Qt.AlignCenter,
                    f"{wk_start.day} {wk_start.strftime('%b')}",
                )

        # Draw milestone markers in the strip above the week blocks
        MS_COLOR = "#e0c030"
        for ms in self._milestones:
            due_d = _parse_dmy(ms.get("due_date", ""))
            if due_d is None:
                continue
            wk = _prod_week(due_d, w1, hs, he)
            if wk is None:
                continue
            for slot_idx, item in enumerate(draw_list):
                if item[0] == "week" and item[1] == wk:
                    sx      = margin_x + slot_idx * slot_w
                    mid_x   = sx + slot_w / 2
                    tip_y   = ms_strip_h - 2
                    tri = QtGui.QPolygonF([
                        QtCore.QPointF(mid_x,     tip_y),
                        QtCore.QPointF(mid_x - 4, tip_y - 7),
                        QtCore.QPointF(mid_x + 4, tip_y - 7),
                    ])
                    p.setBrush(QtGui.QColor(MS_COLOR))
                    p.setPen(QtCore.Qt.NoPen)
                    p.drawPolygon(tri)
                    name = ms.get("name", "")
                    if len(name) > 9:
                        name = name[:8] + "…"
                    f_ms = QtGui.QFont()
                    f_ms.setPixelSize(7)
                    p.setFont(f_ms)
                    p.setPen(QtGui.QColor(MS_COLOR))
                    p.drawText(
                        QtCore.QRectF(sx, 1, slot_w, tip_y - 9),
                        QtCore.Qt.AlignCenter, name,
                    )
                    break

        p.end()


# ---------------------------------------------------------------------------
# Clickable big week-count display (right 1/3 of production panel)
# ---------------------------------------------------------------------------
class _WeekCountWidget(QtWidgets.QWidget):
    clicked = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hovered = False
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self._build()

    def _build(self):
        vl = QtWidgets.QVBoxLayout(self)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(0)
        vl.setAlignment(QtCore.Qt.AlignCenter)

        inner = QtWidgets.QWidget()
        inner.setObjectName("weekInner")
        il = QtWidgets.QVBoxLayout(inner)
        il.setContentsMargins(16, 16, 16, 12)
        il.setSpacing(0)
        il.setAlignment(QtCore.Qt.AlignCenter)

        self._top_lbl  = QtWidgets.QLabel("")
        self._top_lbl.setAlignment(QtCore.Qt.AlignCenter)
        self._top_lbl.setStyleSheet(
            f"font-size:10px; font-weight:bold; color:{SUBTEXT}; letter-spacing:2px;"
        )
        self._num_lbl  = QtWidgets.QLabel("—")
        self._num_lbl.setAlignment(QtCore.Qt.AlignCenter)
        self._num_lbl.setStyleSheet("font-size:68px; font-weight:bold; color:#444;")
        self._of_lbl   = QtWidgets.QLabel("")
        self._of_lbl.setAlignment(QtCore.Qt.AlignCenter)
        self._of_lbl.setStyleSheet(
            f"font-size:11px; color:{SUBTEXT}; letter-spacing:1px;"
        )
        self._hint_lbl = QtWidgets.QLabel("click to configure")
        self._hint_lbl.setAlignment(QtCore.Qt.AlignCenter)
        self._hint_lbl.setStyleSheet(f"font-size:9px; color:{SUBTEXT}; padding-top:6px;")

        il.addStretch()
        il.addWidget(self._top_lbl)
        il.addWidget(self._num_lbl)
        il.addWidget(self._of_lbl)
        il.addWidget(self._hint_lbl)
        il.addStretch()
        vl.addWidget(inner, stretch=1)

    def update_settings(self, settings):
        w1   = _parse_dmy(settings.get("week1_start", ""))
        tw   = settings.get("total_weeks", 12)
        hs   = _parse_dmy(settings.get("holiday_start", ""))
        he   = _parse_dmy(settings.get("holiday_end", ""))
        curr = _prod_week(_date.today(), w1, hs, he)

        if curr is None:
            self._top_lbl.setText("")
            self._num_lbl.setText("—")
            self._num_lbl.setStyleSheet("font-size:68px; font-weight:bold; color:#444;")
            self._of_lbl.setText("")
            self._hint_lbl.setText("click to configure")
        else:
            remaining = max(0, tw - curr)
            if curr > tw:
                color = "#e05050"
            elif remaining <= 2:
                color = "#e0a030"
            else:
                color = "#4caf50"
            self._top_lbl.setText("WEEK")
            self._num_lbl.setText(str(curr))
            self._num_lbl.setStyleSheet(
                f"font-size:68px; font-weight:bold; color:{color};"
            )
            self._of_lbl.setText(f"OF {tw}")
            self._hint_lbl.setText("click to edit")

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        color = ITEM_HOVER if self._hovered else ITEM_BG
        p.fillRect(self.rect(), QtGui.QColor(color))
        p.end()

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


# ---------------------------------------------------------------------------
# Compact milestone row for the NavPanel (170 px wide)
# ---------------------------------------------------------------------------
class _NavMilestoneRow(QtWidgets.QFrame):
    delete_requested = QtCore.Signal(int)
    edit_requested   = QtCore.Signal(int)

    def __init__(self, index, data, parent=None):
        super().__init__(parent)
        self._index = index
        self.setFixedHeight(40)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setStyleSheet(
            f"_NavMilestoneRow, QFrame{{background:{PANEL_BG};}}"
            f"_NavMilestoneRow:hover, QFrame:hover{{background:{ITEM_HOVER};}}"
        )
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(10, 0, 10, 0)
        row.setSpacing(6)

        name_lbl = QtWidgets.QLabel(data.get("name", ""))
        name_lbl.setStyleSheet("font-size:11px; color:white;")
        row.addWidget(name_lbl, stretch=1)

        due = data.get("due_date", "")
        if due:
            badge_text, badge_color = _proximity_badge(due)
            badge = QtWidgets.QLabel(badge_text)
            badge.setFixedHeight(18)
            badge.setMinimumWidth(36)
            badge.setAlignment(QtCore.Qt.AlignCenter)
            badge.setStyleSheet(
                f"background:{badge_color}; color:white; border-radius:3px;"
                f"font-size:9px; font-weight:bold; padding:0 4px;"
            )
            row.addWidget(badge)

        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._ctx)

    def _ctx(self, pos):
        menu = QtWidgets.QMenu(self)
        menu.setStyleSheet(_MENU_STYLE)
        edit_act = menu.addAction("Edit Milestone")
        del_act  = menu.addAction("Delete Milestone")
        act = menu.exec_(self.mapToGlobal(pos))
        if act == edit_act:
            self.edit_requested.emit(self._index)
        elif act == del_act:
            self.delete_requested.emit(self._index)


# ---------------------------------------------------------------------------
# Full milestone row for the Progress page content area
# ---------------------------------------------------------------------------
class _ProgressMilestoneRow(QtWidgets.QFrame):
    delete_requested = QtCore.Signal(int)
    edit_requested   = QtCore.Signal(int)

    def __init__(self, index, data, prod_settings, parent=None):
        super().__init__(parent)
        self._index  = index
        self.setMinimumHeight(44)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setStyleSheet(
            f"_ProgressMilestoneRow, QFrame{{background:{ITEM_BG}; border-bottom:1px solid {BORDER};}}"
            f"_ProgressMilestoneRow:hover, QFrame:hover{{background:{ITEM_HOVER};}}"
        )

        vl = QtWidgets.QVBoxLayout(self)
        vl.setContentsMargins(14, 6, 14, 6)
        vl.setSpacing(2)

        # Main info row
        main = QtWidgets.QHBoxLayout()
        main.setSpacing(12)

        # Production week badge
        due     = data.get("due_date", "")
        due_d   = _parse_dmy(due)
        w1_d    = _parse_dmy(prod_settings.get("week1_start", ""))
        hs_d    = _parse_dmy(prod_settings.get("holiday_start", ""))
        he_d    = _parse_dmy(prod_settings.get("holiday_end", ""))
        wk_num  = _prod_week(due_d, w1_d, hs_d, he_d) if (due_d and w1_d) else None

        if wk_num is not None:
            wk_badge = QtWidgets.QLabel(f"Wk {wk_num}")
            wk_badge.setFixedSize(38, 20)
            wk_badge.setAlignment(QtCore.Qt.AlignCenter)
            wk_badge.setStyleSheet(
                f"background:#3a4a5a; color:#a0c4e0; border-radius:3px;"
                f"font-size:10px; font-weight:bold;"
            )
            main.addWidget(wk_badge)

        # Name
        name_lbl = QtWidgets.QLabel(data.get("name", ""))
        name_lbl.setStyleSheet("font-size:13px; color:white; font-weight:bold;")
        main.addWidget(name_lbl, stretch=1)

        # Due date text
        if due:
            due_lbl = QtWidgets.QLabel(f"Due: {due}")
            due_lbl.setStyleSheet(f"font-size:11px; color:{SUBTEXT};")
            main.addWidget(due_lbl)

            badge_text, badge_color = _proximity_badge(due)
            badge = QtWidgets.QLabel(badge_text)
            badge.setFixedSize(80, 22)
            badge.setAlignment(QtCore.Qt.AlignCenter)
            badge.setStyleSheet(
                f"background:{badge_color}; color:white; border-radius:4px;"
                f"font-weight:bold; font-size:11px;"
            )
            main.addWidget(badge)

        vl.addLayout(main)

        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._ctx)

    def _ctx(self, pos):
        menu = QtWidgets.QMenu(self)
        menu.setStyleSheet(_MENU_STYLE)
        edit_act = menu.addAction("Edit Milestone")
        del_act  = menu.addAction("Delete Milestone")
        act = menu.exec_(self.mapToGlobal(pos))
        if act == edit_act:
            self.edit_requested.emit(self._index)
        elif act == del_act:
            self.delete_requested.emit(self._index)


# ---------------------------------------------------------------------------
# Progress page — stats strip + charts + production schedule + milestones
# ---------------------------------------------------------------------------
class ProgressPage(QtWidgets.QWidget):
    data_changed   = QtCore.Signal()
    save_requested = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._milestones      = {}   # {project: [{name, due_date, extension}]}
        self._production      = {}   # {project: {week1_start, total_weeks, holiday_start, holiday_end}}
        self._current_project = ""
        self._shots_data      = {}
        self._assets_data     = {}
        self._build()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._hdr_lbl = QtWidgets.QLabel("Select a project to view progress")
        self._hdr_lbl.setFixedHeight(38)
        self._hdr_lbl.setStyleSheet(
            f"font-weight:bold; font-size:13px; color:white; background:{PANEL_BG};"
            f"border-bottom:1px solid {BORDER}; padding-left:14px;"
        )
        layout.addWidget(self._hdr_lbl)

        self._scroll = QtWidgets.QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet(f"QScrollArea{{border:none; background:{DARK_BG};}}")
        self._content_widget = QtWidgets.QWidget()
        self._content_widget.setStyleSheet(f"background:{DARK_BG};")
        self._content_layout = QtWidgets.QVBoxLayout(self._content_widget)
        self._content_layout.setContentsMargins(20, 20, 20, 20)
        self._content_layout.setSpacing(16)
        self._content_layout.addStretch()
        self._scroll.setWidget(self._content_widget)
        layout.addWidget(self._scroll)

    # ── public API ──────────────────────────────────────────────────────────

    def set_project(self, project, shots_data, assets_data):
        self._current_project = project
        self._shots_data      = shots_data
        self._assets_data     = assets_data
        self._refresh()

    def refresh_data(self, shots_data, assets_data):
        self._shots_data  = shots_data
        self._assets_data = assets_data
        if self._current_project:
            self._refresh()

    def project_added(self, name):
        self._milestones.setdefault(name, [])
        self._production.setdefault(name, {"week1_start": "", "total_weeks": 12,
                                           "holiday_start": "", "holiday_end": ""})

    def project_removed(self, name):
        self._milestones.pop(name, None)
        self._production.pop(name, None)

    def add_milestone(self):
        prod = self._production.get(self._current_project, {})
        dlg = MilestoneDialog(prod_settings=prod, parent=self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            data = dlg.get_data()
            if data["name"]:
                self._milestones.setdefault(self._current_project, []).append(data)
                self.data_changed.emit()

    def delete_milestone(self, idx):
        proj = self._current_project
        ms = self._milestones.get(proj, [])
        if 0 <= idx < len(ms):
            del ms[idx]
            self.data_changed.emit()

    def get_milestones_for_project(self, project):
        return list(self._milestones.get(project, []))

    def get_milestones(self):
        return dict(self._milestones)

    def load_milestones(self, data):
        self._milestones = {k: v for k, v in data.items() if isinstance(v, list)}

    def get_production(self):
        return dict(self._production)

    def load_production(self, data):
        self._production = {k: v for k, v in data.items() if isinstance(v, dict)}

    # ── internal ────────────────────────────────────────────────────────────

    def _refresh(self):
        while self._content_layout.count() > 1:
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()

        proj = self._current_project
        if not proj:
            self._hdr_lbl.setText("Select a project to view progress")
            return

        self._hdr_lbl.setText(f"{proj}  —  Progress")
        shots_counts  = self._stage_counts(self._shots_data.get(proj, {}),  SHOT_STAGES)
        assets_counts = self._stage_counts(self._assets_data.get(proj, {}), ASSET_STAGES)
        prod_settings = self._production.get(proj, {})

        widgets = [
            self._build_date_panel(),
            self._build_summary_strip(shots_counts, assets_counts),
            self._build_charts_panel(shots_counts, assets_counts),
            self._build_combined_panel(proj, prod_settings),
        ]
        for i, w in enumerate(widgets):
            self._content_layout.insertWidget(i, w)

    @staticmethod
    def _stage_counts(project_groups, all_stages):
        counts = {}
        for items in project_groups.values():
            for item in items:
                s = item.get("stage", all_stages[0])
                counts[s] = counts.get(s, 0) + 1
        return {s: counts.get(s, 0) for s in all_stages if counts.get(s, 0) > 0}

    @staticmethod
    def _build_date_panel():
        today = _date.today()
        panel = QtWidgets.QWidget()
        panel.setStyleSheet(f"background:{PANEL_BG}; border-radius:6px;")
        row = QtWidgets.QHBoxLayout(panel)
        row.setContentsMargins(28, 18, 28, 18)
        row.setSpacing(0)
        day_lbl = QtWidgets.QLabel(today.strftime("%A"))
        day_lbl.setStyleSheet("font-size:34px; font-weight:bold; color:white; background:transparent;")
        sep_lbl = QtWidgets.QLabel("  —  ")
        sep_lbl.setStyleSheet(f"font-size:34px; color:{SUBTEXT}; background:transparent;")
        date_lbl = QtWidgets.QLabel(today.strftime("%d %B %Y"))
        date_lbl.setStyleSheet(f"font-size:34px; color:{SUBTEXT}; background:transparent;")
        row.addWidget(day_lbl)
        row.addWidget(sep_lbl)
        row.addWidget(date_lbl)
        row.addStretch()
        return panel

    @staticmethod
    def _build_summary_strip(shots_counts, assets_counts):
        total_shots  = sum(shots_counts.values())
        finaled      = shots_counts.get("Final", 0)
        total_assets = sum(assets_counts.values())
        prod_ready   = assets_counts.get("Production Ready", 0)

        strip = QtWidgets.QWidget()
        strip.setStyleSheet(f"background:{PANEL_BG}; border-radius:6px;")
        row = QtWidgets.QHBoxLayout(strip)
        row.setContentsMargins(20, 14, 20, 14)
        row.setSpacing(0)

        cards = [
            ("TOTAL SHOTS",      str(total_shots),  TEXT),
            ("FINAL",            str(finaled),      "#9575cd"),
            ("TOTAL ASSETS",     str(total_assets), TEXT),
            ("PRODUCTION READY", str(prod_ready),   "#4caf50"),
        ]
        for i, (label, value, val_color) in enumerate(cards):
            if i > 0:
                sep = QtWidgets.QFrame()
                sep.setFrameShape(QtWidgets.QFrame.VLine)
                sep.setFixedHeight(44)
                sep.setStyleSheet(f"color:{BORDER};")
                row.addWidget(sep)
                row.addSpacing(20)
            card = QtWidgets.QWidget()
            card.setStyleSheet("background:transparent;")
            cvl = QtWidgets.QVBoxLayout(card)
            cvl.setContentsMargins(0, 0, 0, 0)
            cvl.setSpacing(2)
            val_lbl = QtWidgets.QLabel(value)
            val_lbl.setStyleSheet(f"font-size:28px; font-weight:bold; color:{val_color};")
            val_lbl.setAlignment(QtCore.Qt.AlignCenter)
            lbl = QtWidgets.QLabel(label)
            lbl.setStyleSheet(f"font-size:10px; color:{SUBTEXT}; letter-spacing:1px;")
            lbl.setAlignment(QtCore.Qt.AlignCenter)
            cvl.addWidget(val_lbl)
            cvl.addWidget(lbl)
            row.addWidget(card, stretch=1)
        return strip

    def _build_charts_panel(self, shots_counts, assets_counts):
        panel = QtWidgets.QWidget()
        panel.setStyleSheet(f"background:{PANEL_BG}; border-radius:6px;")
        row = QtWidgets.QHBoxLayout(panel)
        row.setContentsMargins(28, 20, 28, 20)
        row.setSpacing(32)

        shots_pie = PieChartWidget(title="Shots", complete_stages=["Final"])
        shots_pie.set_data(shots_counts)
        row.addWidget(shots_pie, alignment=QtCore.Qt.AlignTop)
        row.addLayout(self._stats_col(shots_counts, SHOT_STAGES))

        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.VLine)
        sep.setStyleSheet(f"color:{BORDER};")
        row.addWidget(sep)

        assets_pie = PieChartWidget(title="Assets", complete_stages=["Production Ready"])
        assets_pie.set_data(assets_counts)
        row.addWidget(assets_pie, alignment=QtCore.Qt.AlignTop)
        row.addLayout(self._stats_col(assets_counts, ASSET_STAGES))
        row.addStretch()
        return panel

    @staticmethod
    def _stats_col(counts, all_stages):
        col = QtWidgets.QVBoxLayout()
        col.setSpacing(7)
        total = sum(counts.values())
        col.addSpacing(8)
        for stage in all_stages:
            count = counts.get(stage, 0)
            pct   = int(count / total * 100) if total else 0
            color = STAGE_COLORS.get(stage, "#888")
            rw = QtWidgets.QWidget()
            rl = QtWidgets.QHBoxLayout(rw)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.setSpacing(8)
            dot = QtWidgets.QLabel("●")
            dot.setFixedWidth(14)
            dot.setStyleSheet(f"color:{color}; font-size:13px;")
            rl.addWidget(dot)
            name_lbl = QtWidgets.QLabel(stage)
            name_lbl.setFixedWidth(130)
            name_lbl.setStyleSheet(f"font-size:11px; color:{'white' if count else SUBTEXT};")
            rl.addWidget(name_lbl)
            cnt_lbl = QtWidgets.QLabel(f"{count}  ({pct}%)")
            cnt_lbl.setStyleSheet(f"font-size:11px; color:{SUBTEXT};")
            rl.addWidget(cnt_lbl)
            rl.addStretch()
            col.addWidget(rw)
        col.addStretch()
        return col

    def _sorted_milestones_with_idx(self, proj):
        """Return [(original_index, data), ...] sorted ascending by due date; undated at end."""
        ms = self._milestones.get(proj, [])
        indexed = list(enumerate(ms))
        return sorted(
            indexed,
            key=lambda x: _parse_dmy(x[1].get("due_date", "")) or _date.max
        )

    def _build_combined_panel(self, proj, prod_settings):
        """Milestones list (left 2/3, sorted by date) + big week counter (right 1/3)."""
        panel = QtWidgets.QWidget()
        panel.setStyleSheet(f"background:{PANEL_BG}; border-radius:6px;")
        panel.setMinimumHeight(220)
        vl = QtWidgets.QVBoxLayout(panel)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(0)

        # ── Header ──
        hdr_w = QtWidgets.QWidget()
        hdr_w.setFixedHeight(38)
        hdr_w.setStyleSheet(f"border-bottom:1px solid {BORDER};")
        hl = QtWidgets.QHBoxLayout(hdr_w)
        hl.setContentsMargins(14, 0, 14, 0)
        hdr_lbl = QtWidgets.QLabel("MILESTONES")
        hdr_lbl.setStyleSheet(
            f"font-size:10px; font-weight:bold; color:{SUBTEXT}; letter-spacing:1px;"
        )
        hl.addWidget(hdr_lbl)
        vl.addWidget(hdr_w)

        # ── Week timeline ──
        timeline = _WeekTimelineWidget()
        timeline.set_settings(prod_settings, milestones=self._milestones.get(proj, []))
        timeline.setFixedHeight(100)
        timeline.setStyleSheet(f"background:{PANEL_BG}; border-bottom:1px solid {BORDER};")
        vl.addWidget(timeline)

        # ── Body: milestone list (2/3) | separator | week count (1/3) ──
        body = QtWidgets.QWidget()
        body.setStyleSheet("background:transparent;")
        body_row = QtWidgets.QHBoxLayout(body)
        body_row.setContentsMargins(0, 0, 0, 0)
        body_row.setSpacing(0)

        # Left 2/3 — sorted milestone rows in a scroll area
        ms_widget = QtWidgets.QWidget()
        ms_widget.setStyleSheet(f"background:{DARK_BG};")
        ms_vl = QtWidgets.QVBoxLayout(ms_widget)
        ms_vl.setContentsMargins(0, 0, 0, 0)
        ms_vl.setSpacing(1)

        sorted_ms = self._sorted_milestones_with_idx(proj)
        if sorted_ms:
            for orig_idx, ms_data in sorted_ms:
                row = _ProgressMilestoneRow(orig_idx, ms_data, prod_settings)
                row.edit_requested.connect(lambda idx, p=proj: self._edit_milestone(p, idx))
                row.delete_requested.connect(self._delete_ms_and_refresh)
                ms_vl.addWidget(row)
        else:
            empty = QtWidgets.QLabel("No milestones yet — use  + Add  above")
            empty.setStyleSheet(f"color:{SUBTEXT}; font-size:11px; padding:18px 14px;")
            ms_vl.addWidget(empty)
        ms_vl.addStretch()

        ms_scroll = QtWidgets.QScrollArea()
        ms_scroll.setWidgetResizable(True)
        ms_scroll.setStyleSheet(f"QScrollArea{{border:none; background:{DARK_BG};}}")
        ms_scroll.setWidget(ms_widget)
        body_row.addWidget(ms_scroll, stretch=2)

        # Vertical separator
        vsep = QtWidgets.QFrame()
        vsep.setFrameShape(QtWidgets.QFrame.VLine)
        vsep.setStyleSheet(f"color:{BORDER};")
        body_row.addWidget(vsep)

        # Right 1/3 — big clickable week number
        self._week_count_widget = _WeekCountWidget()
        self._week_count_widget.update_settings(prod_settings)
        self._week_count_widget.clicked.connect(
            lambda: self._open_prod_settings_dialog(proj)
        )
        body_row.addWidget(self._week_count_widget, stretch=1)

        vl.addWidget(body, stretch=1)
        return panel

    def _open_prod_settings_dialog(self, proj):
        dlg = _ProductionSettingsDialog(self._production.get(proj, {}), parent=self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            self._production[proj] = dlg.get_data()
            self._refresh()
            self.save_requested.emit()

    def _edit_milestone(self, proj, idx):
        ms = self._milestones.get(proj, [])
        if 0 <= idx < len(ms):
            prod = self._production.get(proj, {})
            dlg = MilestoneDialog(data=ms[idx], prod_settings=prod, parent=self)
            if dlg.exec_() == QtWidgets.QDialog.Accepted:
                ms[idx] = dlg.get_data()
                self._refresh()
                self.data_changed.emit()

    def _delete_ms_and_refresh(self, idx):
        self.delete_milestone(idx)
        self._refresh()


# ---------------------------------------------------------------------------
# Artists tab — global artist roster (name + role)
# ---------------------------------------------------------------------------
class _ArtistRow(QtWidgets.QFrame):
    """Read-only — Jiffy SG never writes ShotGrid Project membership, so
    there's no edit/delete here, just a display of one real project member."""

    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.setFixedHeight(44)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setStyleSheet(
            f"_ArtistRow, QFrame{{background:{ITEM_BG}; border-bottom:1px solid {BORDER};}}"
        )
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(14, 8, 14, 8)
        name_lbl = QtWidgets.QLabel(data.get("name", ""))
        name_lbl.setStyleSheet("font-weight:bold; font-size:13px; color:white;")
        row.addWidget(name_lbl)
        row.addStretch()


class ArtistsPage(QtWidgets.QWidget):
    """Read-only, live-pulled from ShotGrid — replaces the old free-text
    local roster. Shows exactly the HumanUsers who are members of the
    currently-active Project (see list_project_artists()), and is the same
    list fed to the Shot/Asset Artist dropdown, so "who can be assigned"
    always matches "who ShotGrid says is actually on this Project." Jiffy SG
    never writes Project membership — add/remove students in ShotGrid
    itself, then hit Refresh here (or just reselect the Project)."""
    sg_status      = QtCore.Signal(str, str)   # state "ok"|"error", message
    artists_loaded = QtCore.Signal(list)       # list of artist names

    def __init__(self, parent=None):
        super().__init__(parent)
        self._artists = []
        self._project = ""
        self._build()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QtWidgets.QWidget()
        header.setFixedHeight(38)
        header.setStyleSheet(f"background:{PANEL_BG}; border-bottom:1px solid {BORDER};")
        hl = QtWidgets.QHBoxLayout(header)
        hl.setContentsMargins(12, 0, 12, 0)
        self._header_lbl = QtWidgets.QLabel("Artists")
        self._header_lbl.setStyleSheet("font-weight:bold; font-size:13px; color:white;")
        hl.addWidget(self._header_lbl)
        hl.addStretch()
        refresh_btn = QtWidgets.QPushButton("⟳ Refresh")
        refresh_btn.setToolTip("Re-pull this Project's members from ShotGrid")
        refresh_btn.setStyleSheet(
            "QPushButton{background:#444;color:white;border:none;padding:4px 14px;border-radius:3px;}"
            "QPushButton:hover{background:#555;}"
        )
        refresh_btn.clicked.connect(self._refresh)
        hl.addWidget(refresh_btn)
        layout.addWidget(header)

        self._empty_lbl = QtWidgets.QLabel("Select a Project to see its ShotGrid members.")
        self._empty_lbl.setStyleSheet(f"color:{SUBTEXT}; font-size:12px; padding:14px;")
        self._empty_lbl.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(self._empty_lbl)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea{{border:none; background:{DARK_BG};}}")
        self._container = QtWidgets.QWidget()
        self._container.setStyleSheet(f"background:{DARK_BG};")
        self._vbox = QtWidgets.QVBoxLayout(self._container)
        self._vbox.setContentsMargins(0, 0, 0, 0)
        self._vbox.setSpacing(1)
        self._vbox.addStretch()
        scroll.setWidget(self._container)
        layout.addWidget(scroll)

    def set_project(self, project_name):
        self._project = project_name
        if not project_name:
            self._artists = []
            self._rebuild()
            self.artists_loaded.emit([])
            return
        self._refresh()

    def _refresh(self):
        project_name = self._project
        if not project_name:
            return
        self._header_lbl.setText(f"Artists — {project_name}")

        def work():
            return list_project_artists(project_name)

        def done(result, error):
            if error is not None:
                self.sg_status.emit("error", str(error))
                return
            self._artists = result
            self._rebuild()
            self.sg_status.emit("ok", "")
            self.artists_loaded.emit([a.get("name", "") for a in result if a.get("name")])

        _run_sg_async(work, done)

    def _rebuild(self):
        while self._vbox.count() > 1:
            item = self._vbox.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for artist in self._artists:
            self._vbox.insertWidget(self._vbox.count() - 1, _ArtistRow(artist))
        if not self._project:
            self._empty_lbl.setText("Select a Project to see its ShotGrid members.")
            self._empty_lbl.show()
        elif not self._artists:
            self._empty_lbl.setText(f"No ShotGrid members found on '{self._project}'.")
            self._empty_lbl.show()
        else:
            self._empty_lbl.hide()


# ---------------------------------------------------------------------------
# NavPanel — Projects (top) + Groups or Milestones (bottom)
# ---------------------------------------------------------------------------
class NavPanel(QtWidgets.QWidget):
    project_changed            = QtCore.Signal(str)
    project_add_requested      = QtCore.Signal()
    project_added              = QtCore.Signal(str)
    project_removed            = QtCore.Signal(str)
    group_changed              = QtCore.Signal(str)
    group_added                = QtCore.Signal(str)
    group_removed              = QtCore.Signal(str)
    milestone_add_requested    = QtCore.Signal()
    milestone_delete_requested = QtCore.Signal(int)
    milestone_edit_requested   = QtCore.Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._group_label = "Sequence"
        self.setMinimumWidth(140)
        self.setStyleSheet(f"background:{PANEL_BG};")
        self._build()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._make_section_widget(
            "PROJECTS", self._add_project, self._remove_project
        ))
        self.project_list = self._make_list()
        self.project_list.currentTextChanged.connect(
            lambda t: self.project_changed.emit(t or "")
        )
        self.project_list.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.project_list.customContextMenuRequested.connect(
            lambda pos: self._list_ctx(self.project_list, pos, "Project")
        )
        layout.addWidget(self.project_list)

        self._bottom_stack = QtWidgets.QStackedWidget()

        # ── Stack 0: Groups ──
        groups_page = QtWidgets.QWidget()
        groups_page.setStyleSheet(f"background:{PANEL_BG};")
        gvl = QtWidgets.QVBoxLayout(groups_page)
        gvl.setContentsMargins(0, 0, 0, 0)
        gvl.setSpacing(0)
        gvl.addWidget(self._make_section_widget(
            "SEQUENCES", self._add_group, self._remove_group,
            store_add_btn_as="_group_add_btn",
            store_remove_btn_as="_group_remove_btn",
            store_label_as="_group_header_lbl",
        ))
        self.group_list = self._make_list()
        self.group_list.currentTextChanged.connect(self._on_group_text_changed)
        self.group_list.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.group_list.customContextMenuRequested.connect(
            lambda pos: self._list_ctx(self.group_list, pos, self._group_label)
        )
        gvl.addWidget(self.group_list)
        self._bottom_stack.addWidget(groups_page)

        # ── Stack 1: Milestones ──
        ms_page = QtWidgets.QWidget()
        ms_page.setStyleSheet(f"background:{PANEL_BG};")
        mvl = QtWidgets.QVBoxLayout(ms_page)
        mvl.setContentsMargins(0, 0, 0, 0)
        mvl.setSpacing(0)
        mvl.addWidget(self._make_section_widget(
            "MILESTONES", lambda: self.milestone_add_requested.emit(),
            self._remove_milestone,
        ))
        ms_scroll = QtWidgets.QScrollArea()
        ms_scroll.setWidgetResizable(True)
        ms_scroll.setStyleSheet(f"QScrollArea{{border:none; background:{PANEL_BG};}}")
        self._ms_container = QtWidgets.QWidget()
        self._ms_container.setStyleSheet(f"background:{PANEL_BG};")
        self._ms_vbox = QtWidgets.QVBoxLayout(self._ms_container)
        self._ms_vbox.setContentsMargins(0, 0, 0, 0)
        self._ms_vbox.setSpacing(1)
        self._ms_vbox.addStretch()
        ms_scroll.setWidget(self._ms_container)
        mvl.addWidget(ms_scroll)
        self._bottom_stack.addWidget(ms_page)

        layout.addWidget(self._bottom_stack)

    def _make_section_widget(self, title, add_cb, remove_cb=None,
                              store_add_btn_as=None, store_remove_btn_as=None,
                              store_label_as=None):
        _GREEN_BTN = (
            "QPushButton{background:#2e5a2e;color:white;border:none;border-radius:3px;"
            "font-size:16px;font-weight:bold;}"
            "QPushButton:hover{background:#3a7a3a;}"
            "QPushButton:disabled{background:#333;color:#555;}"
        )
        h = QtWidgets.QWidget()
        h.setFixedHeight(32)
        h.setStyleSheet(
            f"background:{PANEL_BG};"
            f"border-top:1px solid {BORDER}; border-bottom:1px solid {BORDER};"
        )
        hl = QtWidgets.QHBoxLayout(h)
        hl.setContentsMargins(12, 0, 8, 0)
        hl.setSpacing(4)
        lbl = QtWidgets.QLabel(title)
        lbl.setStyleSheet(
            f"font-size:10px; font-weight:bold; color:{SUBTEXT}; letter-spacing:1px;"
        )
        hl.addWidget(lbl)
        hl.addStretch()
        add_btn = QtWidgets.QPushButton("+")
        add_btn.setFixedSize(24, 24)
        add_btn.setStyleSheet(_GREEN_BTN)
        add_btn.clicked.connect(add_cb)
        hl.addWidget(add_btn)
        if store_add_btn_as:
            setattr(self, store_add_btn_as, add_btn)
            add_btn.setEnabled(False)
        rem_btn = QtWidgets.QPushButton("−")
        rem_btn.setFixedSize(24, 24)
        rem_btn.setStyleSheet(_GREEN_BTN)
        if remove_cb:
            rem_btn.clicked.connect(remove_cb)
        hl.addWidget(rem_btn)
        if store_remove_btn_as:
            setattr(self, store_remove_btn_as, rem_btn)
            rem_btn.setEnabled(False)
        if store_label_as:
            setattr(self, store_label_as, lbl)
        return h

    def _make_list(self):
        lw = QtWidgets.QListWidget()
        lw.setStyleSheet(_LIST_STYLE)
        return lw

    def _on_group_text_changed(self, t):
        self.group_changed.emit(t or "")

    def show_bottom_section(self, visible):
        self._bottom_stack.setVisible(visible)

    def show_milestones(self, milestones):
        self._bottom_stack.setCurrentIndex(1)
        self._bottom_stack.setVisible(True)
        while self._ms_vbox.count() > 1:
            item = self._ms_vbox.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for i, ms in enumerate(milestones):
            row = _NavMilestoneRow(i, ms)
            row.edit_requested.connect(self.milestone_edit_requested)
            row.delete_requested.connect(self.milestone_delete_requested)
            self._ms_vbox.insertWidget(self._ms_vbox.count() - 1, row)

    def set_groups(self, groups, group_label="Sequence", enabled=True):
        self._group_label = group_label
        self._group_header_lbl.setText(f"{group_label.upper()}S")
        self._group_add_btn.setEnabled(enabled)
        self._group_remove_btn.setEnabled(enabled)
        self.group_list.blockSignals(True)
        self.group_list.clear()
        for g in groups:
            self.group_list.addItem(g)
        self.group_list.setCurrentRow(0)
        self.group_list.blockSignals(False)
        self._bottom_stack.setCurrentIndex(0)
        self._bottom_stack.setVisible(True)
        self.group_changed.emit(groups[0] if groups else "")

    def get_groups(self):
        return [
            self.group_list.item(i).text()
            for i in range(self.group_list.count())
        ]

    def set_projects(self, projects):
        self.project_list.blockSignals(True)
        self.project_list.clear()
        for p in projects:
            self.project_list.addItem(p)
        self.project_list.setCurrentRow(0)
        self.project_list.blockSignals(False)

    def get_projects(self):
        return [
            self.project_list.item(i).text()
            for i in range(self.project_list.count())
        ]

    def _add_project(self):
        # No local free-text entry point anymore — a student can only attach
        # a Project they're actually a ShotGrid member of. JiffySG (the
        # parent, which owns the ShotGrid connection) handles the async
        # lookup + picker and calls add_project() below once one is chosen.
        self.project_add_requested.emit()

    def add_project(self, name):
        """Add an already-validated ShotGrid Project name to the local list.
        Called by JiffySG after the user picks one from the real, ShotGrid-
        scoped choices — never called with arbitrary free text."""
        existing = [self.project_list.item(i).text() for i in range(self.project_list.count())]
        if name in existing:
            QtWidgets.QMessageBox.warning(self, "Add Project", f"'{name}' already exists.")
            return
        self.project_list.addItem(name)
        self.project_added.emit(name)
        self.project_list.setCurrentRow(self.project_list.count() - 1)

    def _remove_project(self):
        item = self.project_list.currentItem()
        if not item:
            return
        name = item.text()
        reply = QtWidgets.QMessageBox.question(
            self, "Remove Project",
            f"Remove '{name}' and all its contents?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )
        if reply == QtWidgets.QMessageBox.Yes:
            self.project_list.blockSignals(True)
            self.project_list.takeItem(self.project_list.row(item))
            self.project_list.setCurrentRow(0)
            self.project_list.blockSignals(False)
            self.project_removed.emit(name)
            next_item = self.project_list.currentItem()
            self.project_changed.emit(next_item.text() if next_item else "")

    def _remove_group(self):
        item = self.group_list.currentItem()
        if not item:
            return
        name = item.text()
        reply = QtWidgets.QMessageBox.question(
            self, f"Remove {self._group_label}",
            f"Remove '{name}' and all its contents?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )
        if reply == QtWidgets.QMessageBox.Yes:
            self.group_list.blockSignals(True)
            self.group_list.takeItem(self.group_list.row(item))
            self.group_list.setCurrentRow(0)
            self.group_list.blockSignals(False)
            self.group_removed.emit(name)
            next_group = self.group_list.currentItem()
            self.group_changed.emit(next_group.text() if next_group else "")

    def _remove_milestone(self):
        ms_count = self._ms_vbox.count() - 1
        if ms_count <= 0:
            return
        last_idx = ms_count - 1
        self.milestone_delete_requested.emit(last_idx)

    def _add_group(self):
        name, ok = QtWidgets.QInputDialog.getText(
            self, f"Add {self._group_label}", f"{self._group_label} name:"
        )
        name = name.strip()
        if not (ok and name): return
        existing = [self.group_list.item(i).text() for i in range(self.group_list.count())]
        if name in existing:
            QtWidgets.QMessageBox.warning(self, f"Add {self._group_label}", f"'{name}' already exists.")
            return
        self.group_list.addItem(name)
        self.group_added.emit(name)
        self.group_list.setCurrentRow(self.group_list.count() - 1)

    def _list_ctx(self, list_widget, pos, label):
        item = list_widget.itemAt(pos)
        if not item:
            return
        menu = QtWidgets.QMenu(self)
        menu.setStyleSheet(_MENU_STYLE)
        remove_act = menu.addAction(f"Remove {label}")
        action = menu.exec_(list_widget.mapToGlobal(pos))
        if action == remove_act:
            reply = QtWidgets.QMessageBox.question(
                self, f"Remove {label}",
                f"Remove '{item.text()}' and all its contents?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            )
            if reply == QtWidgets.QMessageBox.Yes:
                name = item.text()
                list_widget.blockSignals(True)
                list_widget.takeItem(list_widget.row(item))
                list_widget.setCurrentRow(0)
                list_widget.blockSignals(False)
                if label == "Project":
                    self.project_removed.emit(name)
                    next_item = list_widget.currentItem()
                    self.project_changed.emit(next_item.text() if next_item else "")
                else:
                    self.group_removed.emit(name)
                    next_item = list_widget.currentItem()
                    self.group_changed.emit(next_item.text() if next_item else "")


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------
class JiffySG(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setWindowTitle("Jiffy SG")
        self.resize(1200, 900)
        self.setStyleSheet(f"QWidget{{background:{DARK_BG};color:white;}}")
        self._active_project = ""
        self._workspace_job = None
        self._sg_sequence_ids = {}   # {project: {sequence_name: sg_id}}
        self._data_dir = cmds.optionVar(q=_DATA_DIR_PREF) if cmds.optionVar(exists=_DATA_DIR_PREF) else ""
        self._build()
        self._make_dockable()
        if self._data_dir:
            self.load_data()
        else:
            QtCore.QTimer.singleShot(300, self._prompt_data_dir)
        self._workspace_job = cmds.scriptJob(
            event=['workspaceChanged', self._update_project_banner])
        self._check_sg_connection()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title_bar = QtWidgets.QWidget()
        title_bar.setFixedHeight(42)
        title_bar.setStyleSheet(f"background:#1a1a1a; border-bottom:1px solid {BORDER};")
        tl = QtWidgets.QHBoxLayout(title_bar)
        tl.setContentsMargins(16, 0, 8, 0)
        tl.setSpacing(0)
        name_lbl = QtWidgets.QLabel("Jiffy SG")
        name_lbl.setStyleSheet("font-size:17px; font-weight:bold; color:white;")
        tl.addWidget(name_lbl)
        tl.addSpacing(24)
        self.tab_bar = QtWidgets.QTabBar()
        self.tab_bar.addTab("Shots")
        self.tab_bar.addTab("Assets")
        self.tab_bar.addTab("Progress")
        self.tab_bar.addTab("Artists")
        self.tab_bar.setStyleSheet(
            "QTabBar{background:transparent;}"
            f"QTabBar::tab{{background:transparent;color:{SUBTEXT};padding:0 20px;"
            f"height:42px;border:none;border-bottom:2px solid transparent;font-size:13px;}}"
            "QTabBar::tab:selected{color:white;border-bottom:2px solid #4caf50;}"
            "QTabBar::tab:hover{color:white;}"
        )
        self.tab_bar.currentChanged.connect(self._on_tab_changed)
        tl.addWidget(self.tab_bar)
        tl.addStretch()

        self._sg_status_lbl = QtWidgets.QLabel("●")
        self._sg_status_lbl.setFixedSize(20, 30)
        self._sg_status_lbl.setAlignment(QtCore.Qt.AlignCenter)
        self._sg_status_lbl.setCursor(QtCore.Qt.PointingHandCursor)
        self._sg_status_lbl.mousePressEvent = lambda e: self._check_sg_connection()
        self._set_sg_status("checking", "")
        tl.addWidget(self._sg_status_lbl)

        folder_btn = QtWidgets.QPushButton("📁")
        folder_btn.setFixedSize(30, 30)
        folder_btn.setToolTip("Change data folder")
        folder_btn.setStyleSheet(
            "QPushButton{background:transparent;color:#666;border:none;font-size:14px;}"
            "QPushButton:hover{color:white;}"
        )
        folder_btn.clicked.connect(self._choose_data_dir)
        tl.addWidget(folder_btn)
        layout.addWidget(title_bar)

        workspace = cmds.workspace(query=True, rootDirectory=True).rstrip("/\\")
        project_name = os.path.basename(workspace)
        if not project_name or project_name == "default":
            banner_text = "Project:  No project set"
            banner_color = "#e05050"
        else:
            banner_text = f"Project:  {project_name}"
            banner_color = "#4caf50"
        self._project_banner = QtWidgets.QLabel(banner_text)
        self._project_banner.setFixedHeight(36)
        self._project_banner.setStyleSheet(
            f"background:#1a1a1a; color:{banner_color}; font-size:15px; font-weight:bold;"
            f"padding-left:16px; border-bottom:1px solid {BORDER};"
        )
        layout.addWidget(self._project_banner)

        body = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        body.setHandleWidth(1)
        body.setStyleSheet(f"QSplitter::handle{{background:{BORDER};}}")

        self.nav = NavPanel()
        self.nav.project_changed.connect(self._on_project_changed)
        self.nav.project_add_requested.connect(self._on_project_add_requested)
        self.nav.project_added.connect(self._on_project_added)
        self.nav.project_removed.connect(self._on_project_removed)
        self.nav.group_changed.connect(self._on_group_changed)
        self.nav.group_added.connect(self._on_group_added)
        self.nav.group_removed.connect(self._on_group_removed)
        self.nav.milestone_add_requested.connect(self._on_milestone_add)
        self.nav.milestone_delete_requested.connect(self._on_milestone_delete)
        self.nav.milestone_edit_requested.connect(self._on_milestone_edit)

        self.shots_page    = SchedulePage(item_label="Shot",  stages=SHOT_STAGES)
        self.assets_page   = SchedulePage(item_label="Asset", stages=ASSET_STAGES)
        self.progress_page = ProgressPage()
        self.artists_page  = ArtistsPage()

        self.shots_page.data_changed.connect(self._on_shots_changed)
        self.shots_page.sg_status.connect(self._on_sg_status)
        self.shots_page.sg_sequence_resolved.connect(self._on_sequence_resolved)
        self.shots_page.refresh_requested.connect(
            lambda: self._refresh_entity_activity(self.shots_page, self._active_project, "Shot"))
        self.assets_page.data_changed.connect(self._on_assets_changed)
        self.assets_page.refresh_requested.connect(
            lambda: self._refresh_entity_activity(self.assets_page, self._active_project, "Asset"))
        self.progress_page.data_changed.connect(self._on_milestone_data_changed)
        self.progress_page.save_requested.connect(self.save_data)
        self.artists_page.sg_status.connect(self._on_sg_status)
        self.artists_page.artists_loaded.connect(self._on_artists_loaded)

        self.stack = QtWidgets.QStackedWidget()
        self.stack.addWidget(self.shots_page)
        self.stack.addWidget(self.assets_page)
        self.stack.addWidget(self.progress_page)
        self.stack.addWidget(self.artists_page)

        body.addWidget(self.nav)
        body.addWidget(self.stack)
        body.setSizes([220, 980])
        body.setStretchFactor(0, 0)
        body.setStretchFactor(1, 1)
        layout.addWidget(body)

    def _set_sg_status(self, state, message):
        color = {"checking": "#666", "ok": "#4caf50", "error": "#e05050"}[state]
        self._sg_status_lbl.setStyleSheet(f"color:{color}; font-size:16px; background:transparent;")
        self._sg_status_lbl.setToolTip(
            message or ("Connected to ShotGrid" if state == "ok" else "Checking ShotGrid connection…")
        )

    def _check_sg_connection(self):
        self._set_sg_status("checking", "")

        def work():
            return test_connection()

        def done(result, error):
            if error is not None:
                self._set_sg_status("error", str(error))
            else:
                self._set_sg_status("ok", "{0} visible project(s)".format(len(result)))

        _run_sg_async(work, done)

    def _on_sg_status(self, state, message):
        self._set_sg_status(state, message)

    def _on_sequence_resolved(self, project, group, sg_id):
        if self._sg_sequence_ids.get(project, {}).get(group) != sg_id:
            self._sg_sequence_ids.setdefault(project, {})[group] = sg_id
            self.save_data()

    def _push_sequence_create(self, project_name, sequence_name):
        def work():
            return create_sequence(sequence_name, project_name)

        def done(result, error):
            if error is not None:
                self._set_sg_status("error", str(error))
                return
            self._sg_sequence_ids.setdefault(project_name, {})[sequence_name] = result["id"]
            self.save_data()
            self._set_sg_status("ok", "")

        _run_sg_async(work, done)

    def _push_sequence_delete(self, sequence_id, shot_ids):
        def work():
            errors = []
            for sid in shot_ids:
                try:
                    delete_shot(sid)
                except Exception as exc:
                    errors.append(str(exc))
            if sequence_id:
                try:
                    delete_sequence(sequence_id)
                except Exception as exc:
                    errors.append(str(exc))
            return errors

        def done(result, error):
            if error is not None:
                self._set_sg_status("error", str(error))
            elif result:
                self._set_sg_status("error", "; ".join(result))
            else:
                self._set_sg_status("ok", "")

        _run_sg_async(work, done)

    def _active_page(self):
        idx = self.tab_bar.currentIndex()
        if idx == 0: return self.shots_page
        if idx == 1: return self.assets_page
        return None

    def _group_label_for_tab(self, index):
        return "Sequence" if index == 0 else "Asset"

    def _on_tab_changed(self, index):
        self.stack.setCurrentIndex(index)
        if index == 2:
            self._enter_progress_tab()
        elif index == 3:
            self.nav.show_bottom_section(False)
        else:
            page    = self._active_page()
            label   = self._group_label_for_tab(index)
            groups  = page.get_groups_for_project(self._active_project)
            self.nav.set_groups(groups, group_label=label, enabled=bool(self._active_project))

    def _enter_progress_tab(self):
        proj = self._active_project
        self.progress_page.set_project(
            proj, self.shots_page.get_data(), self.assets_page.get_data()
        )
        if proj:
            self.nav.show_milestones(self.progress_page.get_milestones_for_project(proj))
        else:
            self.nav.show_bottom_section(False)

    def _refresh_nav_milestones(self):
        if self.tab_bar.currentIndex() == 2 and self._active_project:
            self.nav.show_milestones(
                self.progress_page.get_milestones_for_project(self._active_project)
            )

    def _on_project_changed(self, project):
        self._active_project = project
        self.shots_page.set_project(project)
        self.assets_page.set_project(project)
        self.artists_page.set_project(project)
        self._refresh_entity_activity(self.shots_page, project, "Shot")
        self._refresh_entity_activity(self.assets_page, project, "Asset")
        idx = self.tab_bar.currentIndex()
        if idx == 2:
            self.progress_page.set_project(
                project, self.shots_page.get_data(), self.assets_page.get_data()
            )
            if project:
                self.nav.show_milestones(self.progress_page.get_milestones_for_project(project))
            else:
                self.nav.show_bottom_section(False)
        elif idx == 3:
            pass  # artists tab's own project label/refresh is handled by set_project above
        else:
            label  = self._group_label_for_tab(idx)
            groups = self._active_page().get_groups_for_project(project)
            self.nav.set_groups(groups, group_label=label, enabled=bool(project))

    def _on_project_add_requested(self):
        """Look up which real ShotGrid Projects the current login can see,
        then let the user pick one to attach — see NavPanel.add_project()'s
        docstring for why this replaced free-text project naming."""
        existing = set(self.nav.get_projects())

        def work():
            return list_visible_projects()

        def done(result, error):
            if error is not None:
                QtWidgets.QMessageBox.warning(
                    self, "Add Project",
                    "Couldn't reach ShotGrid to list your Projects:\n\n{0}".format(error)
                )
                return
            choices = [p["name"] for p in result if p["name"] not in existing]
            if not choices:
                QtWidgets.QMessageBox.information(
                    self, "Add Project",
                    "All ShotGrid Projects visible to your account are already added."
                    if result else
                    "No ShotGrid Projects are visible to your account yet — "
                    "ask your instructor to add you to one."
                )
                return
            name, ok = QtWidgets.QInputDialog.getItem(
                self, "Add Project", "ShotGrid Project:", choices, 0, False
            )
            if ok and name:
                self.nav.add_project(name)

        _run_sg_async(work, done)

    def _on_artists_loaded(self, names):
        self.shots_page.set_artist_names(names)
        self.assets_page.set_artist_names(names)

    def _on_project_added(self, name):
        self.shots_page.project_added(name)
        self.assets_page.project_added(name)
        self.progress_page.project_added(name)
        self.save_data()

    def _on_project_removed(self, name):
        self.shots_page.project_removed(name)
        self.assets_page.project_removed(name)
        self.progress_page.project_removed(name)
        self._sg_sequence_ids.pop(name, None)
        self.save_data()

    def _on_group_changed(self, group):
        page = self._active_page()
        if page: page.select_group(group)

    def _on_group_added(self, name):
        page = self._active_page()
        if page:
            page.project_added(self._active_project)
            page.select_group(name)
        self.save_data()
        if self.tab_bar.currentIndex() == 0 and self._active_project:
            self._push_sequence_create(self._active_project, name)

    def _on_group_removed(self, name):
        page = self._active_page()
        is_shots_tab = self.tab_bar.currentIndex() == 0
        sequence_id, shot_ids = None, []
        if is_shots_tab and page:
            sequence_id = self._sg_sequence_ids.get(self._active_project, {}).pop(name, None)
            shot_ids = [
                it.get("sg_shot_id")
                for it in page._data.get(self._active_project, {}).get(name, [])
                if it.get("sg_shot_id")
            ]
        if page:
            page._data.get(self._active_project, {}).pop(name, None)
            page.select_group("")
        self.save_data()
        if is_shots_tab and (sequence_id or shot_ids):
            self._push_sequence_delete(sequence_id, shot_ids)

    def _entity_id_key(self, entity_type):
        return "sg_shot_id" if entity_type == "Shot" else "sg_asset_id"

    def _page_for_entity_type(self, entity_type):
        return self.shots_page if entity_type == "Shot" else self.assets_page

    def _find_item(self, entity_type, entity_id):
        """Scans every loaded Project/Sequence-or-category row of the given
        entity_type (not just the currently-displayed one) for the
        item_data dict matching entity_id. SchedulePage._data holds all
        projects at once (see load_data() below), so a publish can land
        even if the student is looking at a different Project/tab right
        now."""
        key = self._entity_id_key(entity_type)
        page = self._page_for_entity_type(entity_type)
        for groups in page._data.values():
            for items in groups.values():
                for item in items:
                    if item.get(key) == entity_id:
                        return item
        return None

    def apply_remote_publish(self, entity_type, entity_id, note_text, thumbnail_path, playblast_folder):
        """Live push from jiffySG.upload_playblast() (see
        _push_publish_to_open_window) — called on Maya's main thread the
        instant a shotSub publish completes, while this window is open, so
        the note/thumbnail appear without waiting for any refresh.

        Always rebuilds the current view (matching _apply_entity_activity's
        pull-fallback pattern) rather than trying to surgically find/repaint
        just the one visible row — the published Shot/Asset may belong to a
        different Project/group than whatever's currently on screen, in
        which case a single-row lookup would silently find nothing while
        the underlying data (and save_data() below) is still correctly
        updated. _refresh_view() is a safe no-op if the row isn't part of
        the current view."""
        item_data = self._find_item(entity_type, entity_id)
        if item_data is None:
            return
        item_data["sg_latest_note"] = note_text or ""
        if thumbnail_path and os.path.isfile(thumbnail_path):
            item_data["thumbnail"] = thumbnail_path
        self._page_for_entity_type(entity_type)._refresh_view()
        self.save_data()

    def _refresh_entity_activity(self, page, project, entity_type):
        """Pull-based fallback for when the live push above couldn't reach
        an open window at publish time (Jiffy SG wasn't open, or was open
        to a different project/session) — re-pulls latest note + thumbnail
        for every Shot/Asset in project from ShotGrid. Triggered on Project
        select/load and by each tab's '⟳ Refresh' button."""
        if not project:
            return
        cache_dir = _thumb_cache_dir()   # main thread only, see its docstring

        def work():
            activity = list_entity_latest_activity(project, entity_type)
            for entity_id, info in activity.items():
                url = info.get("image_url")
                info["thumbnail_path"] = _download_shot_thumbnail(entity_id, url, cache_dir) if url else None
            return activity

        def done(result, error):
            if error is not None:
                self._set_sg_status("error", str(error))
                return
            self._apply_entity_activity(page, project, result, entity_type)
            self._set_sg_status("ok", "")

        _run_sg_async(work, done)

    def _apply_entity_activity(self, page, project, activity, entity_type):
        """project is the one actually queried by _refresh_entity_activity
        above (closed over from its caller), not necessarily self._active_
        project — the user may have switched Projects while this async
        pull was in flight, and applying to the wrong Project's data here
        would silently corrupt it."""
        key = self._entity_id_key(entity_type)
        groups = page._data.get(project, {})
        changed = False
        for items in groups.values():
            for item in items:
                info = activity.get(item.get(key))
                if not info:
                    continue
                if info.get("note") is not None and info["note"] != item.get("sg_latest_note"):
                    item["sg_latest_note"] = info["note"]
                    changed = True
                tp = info.get("thumbnail_path")
                if tp and tp != item.get("thumbnail"):
                    item["thumbnail"] = tp
                    changed = True
        if changed:
            page._refresh_view()
            self.save_data()

    def _on_shots_changed(self):
        self.progress_page.refresh_data(self.shots_page.get_data(), self.assets_page.get_data())
        self.save_data()

    def _on_assets_changed(self):
        self.progress_page.refresh_data(self.shots_page.get_data(), self.assets_page.get_data())
        self.save_data()

    def _on_milestone_add(self):
        self.progress_page.add_milestone()

    def _on_milestone_delete(self, idx):
        self.progress_page.delete_milestone(idx)
        if self.tab_bar.currentIndex() == 2:
            self.progress_page._refresh()

    def _on_milestone_edit(self, idx):
        self.progress_page._edit_milestone(self.progress_page._current_project, idx)

    def _on_milestone_data_changed(self):
        self._refresh_nav_milestones()
        self.progress_page._refresh()
        self.save_data()

    def save_data(self):
        path = self._save_path()
        if not path:
            return
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            g = self.geometry()
            payload = {
                "projects":     self.nav.get_projects(),
                "shots":        self.shots_page.get_data(),
                "assets":       self.assets_page.get_data(),
                "milestones":   self.progress_page.get_milestones(),
                "production":   self.progress_page.get_production(),
                "sg_sequences": self._sg_sequence_ids,
                "window":       {"x": g.x(), "y": g.y(), "w": g.width(), "h": g.height()},
            }
            with open(path + ".tmp", "w") as f:
                json.dump(payload, f, indent=4)
            os.replace(path + ".tmp", path)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Save Error", str(e))

    def load_data(self):
        path = self._save_path()
        if not path or not os.path.exists(path):
            return
        try:
            with open(path, "r") as f:
                saved = json.load(f)

            if "shots" in saved and isinstance(saved["shots"], dict) and "data" in saved["shots"]:
                saved = {
                    "projects": saved["shots"].get("projects", []),
                    "shots":    saved["shots"].get("data", {}),
                    "assets":   saved.get("assets", {}).get("data", {})
                        if isinstance(saved.get("assets"), dict) else {},
                }
            elif "data" in saved and "shots" not in saved:
                saved = {
                    "projects": saved.get("projects", []),
                    "shots":    saved.get("data", {}),
                    "assets":   {},
                }

            projects = saved.get("projects", [])
            self.nav.set_projects(projects)
            for p in projects:
                self.shots_page.project_added(p)
                self.assets_page.project_added(p)
                self.progress_page.project_added(p)
            self.shots_page.load_data(saved.get("shots", {}))
            self.assets_page.load_data(saved.get("assets", {}))
            self.progress_page.load_milestones(saved.get("milestones", {}))
            self.progress_page.load_production(saved.get("production", {}))
            self._sg_sequence_ids = saved.get("sg_sequences", {})
            # Artist names are no longer stored locally — they're pulled live
            # from ShotGrid via artists_page.set_project(), triggered below by
            # _on_project_changed() once a project is selected.
            win = saved.get("window", {})
            if win:
                self.setGeometry(
                    win.get("x", 100), win.get("y", 100),
                    win.get("w", 1200), win.get("h", 900)
                )
            if projects:
                self._on_project_changed(projects[0])
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Load Error", str(e))

    def _update_project_banner(self):
        workspace = cmds.workspace(query=True, rootDirectory=True).rstrip("/\\")
        project_name = os.path.basename(workspace)
        if not project_name or project_name == "default":
            self._project_banner.setText("Project:  No project set")
            self._project_banner.setStyleSheet(
                f"background:#1a1a1a; color:#e05050; font-size:15px; font-weight:bold;"
                f"padding-left:16px; border-bottom:1px solid {BORDER};"
            )
        else:
            self._project_banner.setText(f"Project:  {project_name}")
            self._project_banner.setStyleSheet(
                f"background:#1a1a1a; color:#4caf50; font-size:15px; font-weight:bold;"
                f"padding-left:16px; border-bottom:1px solid {BORDER};"
            )

    def _save_path(self):
        if not self._data_dir:
            return None
        os.makedirs(self._data_dir, exist_ok=True)
        return os.path.join(self._data_dir, "jiffysg.json")

    def _prompt_data_dir(self):
        QtWidgets.QMessageBox.information(
            self, "Jiffy SG — Choose data folder",
            "Please choose a folder where Jiffy SG will store your project data.\n"
            "This only needs to be done once.",
        )
        self._choose_data_dir()

    def _choose_data_dir(self):
        start = self._data_dir or os.path.expanduser("~")
        d = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Jiffy SG — Choose data folder", start,
        )
        if d:
            self._data_dir = d
            cmds.optionVar(sv=(_DATA_DIR_PREF, d))
            self.load_data()

    def closeEvent(self, event):
        global _jiffysg_window
        _jiffysg_window = None
        if self._workspace_job is not None:
            try:
                cmds.scriptJob(kill=self._workspace_job, force=True)
            except Exception:
                pass
            self._workspace_job = None
        super().closeEvent(event)

    def _make_dockable(self):
        ptr = omui.MQtUtil.mainWindow()
        if ptr:
            maya_win = wrapInstance(int(ptr), QtWidgets.QMainWindow)
            self.setParent(maya_win)
            self.setWindowFlags(QtCore.Qt.Window)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
_jiffysg_window = None

def run_jiffySG():
    global _jiffysg_window
    if _jiffysg_window is not None:
        try:
            _jiffysg_window.raise_()
            _jiffysg_window.activateWindow()
            return _jiffysg_window
        except RuntimeError:
            _jiffysg_window = None
    _jiffysg_window = JiffySG()
    _jiffysg_window.show()
    _jiffysg_window.raise_()
    return _jiffysg_window


if __name__ == "__main__":
    run_jiffySG()
