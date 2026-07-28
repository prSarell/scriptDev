# ------------------------------------------------------------
# shotgridConnect.py
#
# shotSub's own standalone ShotGrid connection/publish backend.
#
# Adapted from timeManagementDev/jiffySGDev/jiffySG.py's backend section.
# JiffySG (the ShotGrid-integrated scheduling app) is paused -- not enough
# ShotGrid/pipeline literacy in the current student cohort to support it
# yet, and the tool itself isn't mature enough -- but ShotGrid playblast
# review is still needed, so shotSub now owns its own connection instead
# of importing jiffySG. This is a deliberate copy, not a shared import:
# jiffySG.py stays untouched while paused.
#
# Auth model: a single Script API key authenticates all API calls;
# sudo_as_login applies the impersonated student's own ShotGrid permissions
# to each call and attributes it to them in the event log. The key itself
# is never hardcoded here or committed to the repo -- it's read from a
# local config file created on each machine.
#
# Config file:
#   <Maya userPrefDir>/shotSub_config.json
#   {
#     "site_url": "https://nfw.shotgrid.autodesk.com",
#     "script_name": "<Script Name from ShotGrid Admin > Scripts>",
#     "api_key": "<the Application Key from ShotGrid Admin > Scripts>",
#     "sudo_as_login": "<optional override -- see current_login() below>"
#   }
#
# Deliberately does NOT create Shots -- Shots are created directly in
# ShotGrid's web UI by the lecturer/TD. shotSub only ever links to and
# publishes against an existing Shot (see shotSub.py's link_to_shotgrid()).
#
# Deliberately does NOT look up rvio/RV itself -- shotSub.py already has
# find_rv_executable()/_rv_install_roots_from_registry() (inherited from
# pbTool); callers pass the resolved rvio path into upload_playblast().
# ------------------------------------------------------------

import os
import re
import glob
import json
import getpass
import subprocess

import maya.cmds as cmds

import shotgun_api3


_CONFIG_FILENAME = "shotSub_config.json"
_REQUIRED_KEYS = ("site_url", "script_name", "api_key")

# For deriving a student's real ShotGrid login from shotSub's own
# student-identity file (see shotSub.py's ensure_student_identity()) --
# NOT imported from shotSub.py directly to avoid a circular import
# (shotSub.py imports this module), just the same filename by convention.
_STUDENT_IDENTITY_FILENAME = "shotSub_student.json"
_STUDENT_EMAIL_DOMAIN = "student.rmit.edu.au"
_STUDENT_ID_DIGITS_RE = re.compile(r"^s?(\d+)$", re.IGNORECASE)

# Cached after the first successful load -- see jiffySG.py's identical
# cache for why this matters (cmds.internalVar is main-thread-only), kept
# here even though shotSub calls this backend synchronously on the main
# thread, so behaviour matches if that ever changes.
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
            "shotSub: no ShotGrid config file found at {0}\n\n"
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
            raise RuntimeError("shotSub: config at {0} is not valid JSON — {1}".format(path, exc))

    missing = [key for key in _REQUIRED_KEYS if not config.get(key)]
    if missing:
        raise RuntimeError(
            "shotSub: config at {0} is missing: {1}".format(path, ", ".join(missing))
        )

    _config_cache = config
    return config


def _student_login_from_identity_file():
    """Best-effort derivation of a ShotGrid login from shotSub's own
    student-identity file (<Maya userPrefDir>/shotSub_student.json's
    "student_id", written by shotSub.py's ensure_student_identity()) --
    converts it to the RMIT student email format
    (s<digits>@student.rmit.edu.au) that matches every real student login
    on this site, e.g. "S4177501" -> "s4177501@student.rmit.edu.au". This
    is what lets a shared, no-personal-login config file (the one
    distributed to the whole class) still resolve to each student's own
    identity, with no manual JSON editing on their end.

    Returns None if the file doesn't exist yet, or its student_id has no
    digits in it at all (e.g. a staff/mentor identity like
    "patrick.sarell2" -- current_login() falls through to an explicit
    sudo_as_login/getpass.getuser() in that case, same as before this
    existed)."""
    try:
        prefs = cmds.internalVar(userPrefDir=True)
    except Exception:
        return None
    path = os.path.join(prefs, _STUDENT_IDENTITY_FILENAME).replace("\\", "/")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r") as f:
            data = json.load(f)
    except (ValueError, OSError):
        return None
    match = _STUDENT_ID_DIGITS_RE.search((data.get("student_id") or "").strip())
    if not match:
        return None
    return "s{0}@{1}".format(match.group(1), _STUDENT_EMAIL_DOMAIN)


def current_login():
    """The identity to sudo_as_login as, in priority order:
    (1) an explicit "sudo_as_login" in the local ShotGrid config file --
        for staff/instructor use, or any one-off manual override;
    (2) derived from shotSub's own student-identity file (see
        _student_login_from_identity_file() above) -- the normal case for
        a real student, who never has to hand-edit any JSON for this;
    (3) getpass.getuser() as an absolute last resort. OS-username
        auto-detect does NOT match real ShotGrid logins on this site
        (they're full email addresses) -- this only avoids a hard crash,
        it does not actually authenticate correctly."""
    try:
        config = _load_config()
    except RuntimeError:
        config = {}
    if config.get("sudo_as_login"):
        return config["sudo_as_login"]
    derived = _student_login_from_identity_file()
    if derived:
        return derived
    return getpass.getuser()


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


def _find_project(sg, project_name, as_login=None):
    """Look up a Project by exact name, or raise a clear RuntimeError if it's
    not visible to as_login."""
    project = sg.find_one("Project", [["name", "is", project_name]], ["id", "name"])
    if not project:
        raise RuntimeError(
            "shotSub: no ShotGrid Project named '{0}' visible to '{1}'".format(
                project_name, as_login or current_login())
        )
    return project


def list_visible_projects(as_login=None):
    """All ShotGrid Projects visible to as_login (defaults to
    current_login()), as a list of {"id","name"} dicts, name-sorted.
    ShotGrid itself scopes this: a student on the Artist permission group
    only ever sees the Project(s) their instructor added them to."""
    sg = get_connection(as_login=as_login)
    return sg.find(
        "Project", [], ["id", "name"], order=[{"field_name": "name", "direction": "asc"}]
    )


def list_project_shots(project_name, as_login=None):
    """All ShotGrid Shots that exist in the named Project -- read-only,
    never creates one (Shots are created directly in ShotGrid's web UI).
    Returns {"id","code"} dicts, code-sorted, so shotSub can resolve an
    explicit ShotGrid Shot id to store in its local shotgrid_link.json
    marker file instead of guessing a shot name from folder structure."""
    sg = get_connection(as_login=as_login)
    project = _find_project(sg, project_name, as_login=as_login)
    return sg.find(
        "Shot", [["project", "is", project]], ["id", "code"],
        order=[{"field_name": "code", "direction": "asc"}],
    )


def upload_entity_thumbnail(entity_type, entity_id, image_path, as_login=None):
    """Push image_path up as entity_type/entity_id's ShotGrid thumbnail.
    Silently no-ops on a blank/missing path."""
    if not image_path or not os.path.isfile(image_path):
        return None
    sg = get_connection(as_login=as_login)
    return sg.upload_thumbnail(entity_type, entity_id, image_path)


def _create_note(sg, entity, project, version, note_text):
    """One new Note per publish (never an overwrite) -- a real ShotGrid
    Note, so a mentor reviewing directly in ShotGrid sees/adds to the same
    feed."""
    note_links = [entity] + ([version] if version else [])
    return sg.create("Note", {
        "project": project,
        "subject": "Playblast — {0}".format(entity.get("code", "")),
        "content": note_text,
        "note_links": note_links,
    })


def _frame_sequence_prefix(version_folder):
    """Strip the trailing .####.jpg off any one frame file in version_folder
    to get the sequence prefix rvio/RV need (e.g. .../shotName.#.jpg)."""
    files = sorted(glob.glob(os.path.join(version_folder, "*.jpg")))
    if not files:
        return None
    match = re.search(r"^(.*)\.\d+\.jpg$", os.path.basename(files[0]), flags=re.IGNORECASE)
    return os.path.join(version_folder, match.group(1)) if match else None


def _encode_to_mp4(version_folder, fps, rvio_path):
    """Best-effort JPEG-sequence -> mp4 transcode via RV's bundled rvio.
    rvio_path is resolved by the caller (shotSub.py already has its own
    find_rv_executable()) -- this function never looks up RV itself.
    Returns the mp4 path, or None on any failure (missing rvio, no frames,
    encode error) -- publish must still succeed thumbnail-only if this
    doesn't work, never block on it.

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

    if not rvio_path:
        print("shotSub: rvio not found — publishing thumbnail-only, no scrubbable movie.")
        return None

    cmd = [rvio_path, prefix + ".#.jpg", "-o", out_path]
    if fps:
        cmd += ["-fps", str(fps)]
    try:
        subprocess.run(
            cmd, capture_output=True, text=True, check=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception as exc:
        print("shotSub: rvio encode failed (publishing thumbnail-only instead) — {0}".format(exc))
        return None

    return out_path if os.path.isfile(out_path) else None


def upload_playblast(entity_type, entity_id, version_folder, files=None, notes=None, fps=None,
                      rvio_path=None, as_login=None):
    """Hand-off target for shotSub's "Publish Selected Version" button (see
    shotSub.py publish_version()). shotSub resolves entity_type/entity_id
    itself, from an explicit ShotGrid Shot id stored in a local
    shotgrid_link.json marker file, written by shotSub's "Link to
    ShotGrid" flow (see list_project_shots() above -- links to an existing
    Shot only, never creates one). entity_id is a global ShotGrid id, so
    project_name/project_id isn't needed as an input -- the Project is
    looked up directly off the Shot itself.

    Idempotent on (entity, code): re-publishing the same version_folder
    finds and reuses the existing Version rather than creating a
    duplicate.

    Publishes a real scrubbable movie (Version.sg_uploaded_movie, encoded
    via rvio -- see _encode_to_mp4) alongside the thumbnail. Also stores
    Version.sg_path_to_frames (the local version_folder), and creates a
    ShotGrid Note per publish (see _create_note above) if notes are given.

    No Task/stage linking here -- that's schedule-tracking territory
    (JiffySG's Stage/Due Date/Artist model), not needed for a plain
    publish-for-review flow."""
    sg = get_connection(as_login=as_login)

    entity = sg.find_one(entity_type, [["id", "is", entity_id]], ["id", "code", "project"])
    if not entity:
        raise RuntimeError(
            "shotSub: no {0} found with id {1} — was it deleted/retired in "
            "ShotGrid since this shot was linked?".format(entity_type, entity_id)
        )
    project = entity["project"]

    if files is None:
        files = sorted(glob.glob(os.path.join(version_folder, "*.jpg")))
    if not files:
        raise RuntimeError("shotSub: no frames found in {0} to publish".format(version_folder))

    version_folder_norm = os.path.normpath(version_folder).replace("\\", "/")
    version_name = os.path.basename(version_folder_norm)
    code = "{0}_{1}".format(entity["code"], version_name)

    existing = sg.find_one("Version", [["entity", "is", entity], ["code", "is", code]], ["id"])
    if existing:
        print("shotSub: Version '{0}' already exists on {1} '{2}' (id {3}) — not re-creating".format(
            code, entity_type, entity["code"], existing["id"]))
        version = existing
        sg.update("Version", version["id"], {"sg_path_to_frames": version_folder_norm})
    else:
        version = sg.create("Version", {
            "project": project, "code": code, "entity": entity,
            "sg_path_to_frames": version_folder_norm,
        })
        print("shotSub: created Version '{0}' on {1} '{2}' (id {3})".format(
            code, entity_type, entity["code"], version["id"]))

    representative_frame = files[len(files) // 2]
    sg.upload_thumbnail("Version", version["id"], representative_frame)

    # ShotGrid does not cascade a Version's thumbnail up to its linked
    # Shot on its own -- do it explicitly so the Shot's thumbnail stays
    # current as new playblasts get published.
    upload_entity_thumbnail(entity_type, entity_id, representative_frame, as_login=as_login)

    mp4_path = _encode_to_mp4(version_folder_norm, fps, rvio_path)
    if mp4_path:
        sg.upload("Version", version["id"], mp4_path, field_name="sg_uploaded_movie")
        print("shotSub: uploaded movie '{0}' to Version id {1}".format(mp4_path, version["id"]))

    if notes:
        try:
            _create_note(sg, entity, project, version, notes)
        except Exception as exc:
            print("shotSub: could not create ShotGrid Note — {0}".format(exc))

    return version
