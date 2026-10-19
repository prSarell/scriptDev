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
import shutil
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
    "student_id", written by shotSub.py's ensure_student_identity() or its
    inline "Student # / Staff Email" field). Two forms are recognized:

    - A bare student number (e.g. "S4177501") is converted to the RMIT
      student email format (s<digits>@student.rmit.edu.au) that matches
      every real student login on this site, e.g.
      "S4177501" -> "s4177501@student.rmit.edu.au". This is what lets a
      shared, no-personal-login config file (the one distributed to the
      whole class) still resolve to each student's own identity, with no
      manual JSON editing on their end.
    - A full email address (anything containing "@") is used as-is --
      lets a staff/mentor type their real ShotGrid login (e.g.
      "patrick.sarell2@rmit.edu.au") directly into the same field instead
      of needing a config-file sudo_as_login override.

    Returns None if the file doesn't exist yet, or its student_id is
    neither of the above (current_login() falls through to an explicit
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
    value = (data.get("student_id") or "").strip()
    if not value:
        return None
    if "@" in value:
        return value
    match = _STUDENT_ID_DIGITS_RE.search(value)
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


def has_known_identity():
    """True if current_login() would resolve to a real identity (explicit
    sudo_as_login override, or a derived student login) rather than
    falling through to the getpass.getuser() last resort -- which looks
    like a plausible login on RMIT lab machines (OS username is often the
    student ID) but is never actually valid on this site, since real
    logins are full email addresses. Lets a caller ask for identity
    *before* attempting a connection that's certain to fail with
    AuthenticationFault, instead of only reacting after the fact."""
    try:
        config = _load_config()
    except RuntimeError:
        config = {}
    if config.get("sudo_as_login"):
        return True
    return _student_login_from_identity_file() is not None


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


def list_assigned_shots(project_name, as_login=None):
    """Shots in the named Project with a Task assigned to as_login
    (defaults to current_login()), same {"id","code"} shape as
    list_project_shots(). Lets shotSub narrow the Shot dropdown by who's
    actually assigned in ShotGrid rather than by shot naming -- shots
    like Assignment 3's NWF_EAP_010 carry no student ID in their code.
    Returns [] if the login has no matching HumanUser."""
    login = as_login or current_login()
    sg = get_connection(as_login=login)
    project = _find_project(sg, project_name, as_login=login)
    user = sg.find_one("HumanUser", [["login", "is", login]], ["id"])
    if not user:
        return []
    return sg.find(
        "Shot",
        [["project", "is", project], ["tasks.Task.task_assignees", "is", user]],
        ["id", "code"],
        order=[{"field_name": "code", "direction": "asc"}],
    )


def upload_entity_thumbnail(entity_type, entity_id, image_path, as_login=None):
    """Push image_path up as entity_type/entity_id's ShotGrid thumbnail.
    Silently no-ops on a blank/missing path."""
    if not image_path or not os.path.isfile(image_path):
        return None
    sg = get_connection(as_login=as_login)
    return sg.upload_thumbnail(entity_type, entity_id, image_path)


def _create_note(sg, entity, project, version, note_text, subject=None):
    """One new Note per publish (never an overwrite) -- a real ShotGrid
    Note, so a mentor reviewing directly in ShotGrid sees/adds to the same
    feed. subject defaults to the normal student-review-note subject; also
    used by upload_playblast() with a distinct subject for the automatic
    "no review movie" note (see machine_diagnostic below), so the two are
    easy to tell apart in the Shot's Notes feed."""
    note_links = [entity] + ([version] if version else [])
    return sg.create("Note", {
        "project": project,
        "subject": subject or "Playblast — {0}".format(entity.get("code", "")),
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


# RV (and its rvio encoder) is licensed through the person's ShotGrid
# sign-in. When that sign-in has expired, rvio refuses to encode ("can't get
# rvio license") and publishes used to go out silently thumbnail-only --
# the cause of students' missing review movies in class (found 2026-10-19).
RV_SIGN_IN_HELP = (
    "RV isn't signed in to ShotGrid, so it can't make the review movie.\n"
    "Open RV, sign in to ShotGrid with your RMIT login when it asks, "
    "close RV, then try again.")

# Why the last _encode_to_mp4() call made no movie (None if it did, or
# wasn't asked to). Read by upload_playblast() and shotSub.
last_encode_problem = None

_rvio_ok_until = 0.0        # check_rvio() result cache (time.time())


def rvio_problem(output):
    """A plain-language reason from rvio's output, or None if nothing's
    recognisably wrong."""
    text = output or ""
    lowered = text.lower()
    if "license" in lowered or "licence" in lowered or "access token" in lowered:
        return RV_SIGN_IN_HELP
    errors = [line.strip() for line in text.splitlines() if line.strip().startswith("ERROR")]
    if errors:
        return "RV couldn't make the review movie: " + errors[-1]
    return None


def check_rvio(rvio_path, cache_seconds=600):
    """Ask rvio to encode a tiny generated clip (no files needed), so a
    missing ShotGrid sign-in is caught *before* playblasting/publishing.
    Takes a few seconds; a pass is remembered for cache_seconds. Returns
    None if rvio works, else the reason (RV_SIGN_IN_HELP for a sign-in
    problem)."""
    global _rvio_ok_until
    import tempfile
    import time
    if not rvio_path:
        return None     # no RV at all: callers already handle that case
    if time.time() < _rvio_ok_until:
        return None
    folder = tempfile.mkdtemp(prefix="rvio_check_")
    out_path = os.path.join(folder, "check.mp4")
    try:
        result = subprocess.run(
            [rvio_path, "solid,red=0.5,start=1,end=2,width=64,height=64,fps=24.movieproc",
             "-o", out_path, "-codec", "libx264"],
            capture_output=True, text=True, timeout=120,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        output = (result.stdout or "") + (result.stderr or "")
        if result.returncode == 0 and os.path.isfile(out_path):
            _rvio_ok_until = time.time() + cache_seconds
            return None
        return rvio_problem(output) or "RV couldn't make a test movie (rvio exit code {0}).".format(
            result.returncode)
    except Exception as exc:
        return "RV couldn't make a test movie: {0}".format(exc)
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def _encode_to_mp4(version_folder, fps, rvio_path, audio_path=None, audio_offset_seconds=0.0):
    """Best-effort JPEG-sequence -> mp4 transcode via RV's bundled rvio.
    rvio_path is resolved by the caller (shotSub.py already has its own
    find_rv_executable()) -- this function never looks up RV itself.
    Returns the mp4 path, or None on any failure (missing rvio, no frames,
    encode error) -- publish must still succeed thumbnail-only if this
    doesn't work, never block on it.

    Skips re-encoding if <prefix>.mp4 already exists and is newer than the
    newest .jpg in the folder, so a notes-only re-publish doesn't re-encode --
    unless audio_path is given, since an older cached mp4 may be silent.

    audio_path/audio_offset_seconds (from shotSub's scene time slider sound)
    are muxed in via an rvio source group so lip sync reviews work (rvio's
    default PCM audio -- its aac encoder fails, see shotSub)."""
    global last_encode_problem
    last_encode_problem = None
    prefix = _frame_sequence_prefix(version_folder)
    if not prefix:
        return None
    out_path = prefix + ".mp4"

    jpgs = sorted(glob.glob(os.path.join(version_folder, "*.jpg")))
    if os.path.isfile(out_path) and jpgs and not audio_path:
        newest_jpg = max(os.path.getmtime(f) for f in jpgs)
        if os.path.getmtime(out_path) >= newest_jpg:
            return out_path

    if not rvio_path:
        print("shotSub: rvio not found — publishing thumbnail-only, no scrubbable movie.")
        return None

    # Explicit H.264 -- rvio's default .mp4 codec is Motion-JPEG (tagged mp4v),
    # which Premiere / DaVinci Resolve on Windows can't import, so students
    # couldn't cut ShotGrid downloads into an edit.
    sources = [prefix + ".#.jpg"]
    if audio_path and os.path.isfile(audio_path):
        sources = ["[", sources[0], audio_path]
        if audio_offset_seconds:
            sources += ["-ao", str(audio_offset_seconds)]
        sources += ["]"]
    cmd = [rvio_path] + sources + ["-o", out_path, "-codec", "libx264"]
    if fps:
        cmd += ["-fps", str(fps)]
    try:
        subprocess.run(
            cmd, capture_output=True, text=True, check=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception as exc:
        output = (getattr(exc, "stdout", "") or "") + (getattr(exc, "stderr", "") or "")
        last_encode_problem = rvio_problem(output) or "RV couldn't make the review movie: {0}".format(exc)
        print("shotSub: rvio encode failed (publishing thumbnail-only instead) — {0}\n{1}".format(
            exc, last_encode_problem))
        return None

    if not os.path.isfile(out_path):
        last_encode_problem = "RV ran but no review movie was made."
        return None
    return out_path


def upload_playblast(entity_type, entity_id, version_folder, files=None, notes=None, fps=None,
                      rvio_path=None, as_login=None, machine_diagnostic=None,
                      movie_path=None, thumbnail_path=None, audio_path=None,
                      audio_offset_seconds=0.0):
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

    Publishes a real scrubbable movie (Version.sg_uploaded_movie) alongside
    the thumbnail. movie_path/thumbnail_path are the mp4 + still shotSub
    already encoded at playblast time (it no longer keeps the JPEG frames);
    only a version with no movie but frames on disk is encoded here via
    rvio (see _encode_to_mp4). Also stores
    Version.sg_path_to_frames (the local version_folder), and creates a
    ShotGrid Note per publish (see _create_note above) if notes are given.

    machine_diagnostic (str or None): passed straight through from
    shotSub.py's publish_version() when it couldn't find rvio on the
    student's machine -- a movie-less publish used to be silent (a local
    print() nobody sees, see _encode_to_mp4), leaving instructors to
    discover a blank review after the fact with no way to tell why. When
    set, an automatic Note carrying it gets attached directly to the Shot
    (and Version), landing wherever the instructor is already looking
    instead of depending on the student noticing and reporting it.

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

    if movie_path and not os.path.isfile(movie_path):
        movie_path = None
    if files is None:
        files = sorted(glob.glob(os.path.join(version_folder, "*.jpg")))
    if not files and not movie_path:
        raise RuntimeError("shotSub: no movie or frames found in {0} to publish".format(version_folder))

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

    representative_frame = thumbnail_path if thumbnail_path and os.path.isfile(thumbnail_path) else (
        files[len(files) // 2] if files else None)
    if representative_frame:
        sg.upload_thumbnail("Version", version["id"], representative_frame)

        # ShotGrid does not cascade a Version's thumbnail up to its linked
        # Shot on its own -- do it explicitly so the Shot's thumbnail stays
        # current as new playblasts get published.
        upload_entity_thumbnail(entity_type, entity_id, representative_frame, as_login=as_login)

    mp4_path = movie_path or _encode_to_mp4(
        version_folder_norm, fps, rvio_path, audio_path, audio_offset_seconds)
    movie_problem = None
    if mp4_path:
        sg.upload("Version", version["id"], mp4_path, field_name="sg_uploaded_movie")
        print("shotSub: uploaded movie '{0}' to Version id {1}".format(mp4_path, version["id"]))
    else:
        # Why there's no movie, for the caller to show the student and for
        # a Note the instructor sees on the Shot/Version.
        movie_problem = last_encode_problem or (
            "RV's rvio wasn't found on this machine." if not rvio_path else None)
        diagnostic = machine_diagnostic or movie_problem
        if diagnostic:
            try:
                _create_note(
                    sg, entity, project, version, diagnostic,
                    subject="shotSub: no review movie — {0}".format(code),
                )
            except Exception as exc:
                print("shotSub: could not create no-movie diagnostic Note — {0}".format(exc))
    version = dict(version, movie_problem=movie_problem)

    if notes:
        try:
            _create_note(sg, entity, project, version, notes)
        except Exception as exc:
            print("shotSub: could not create ShotGrid Note — {0}".format(exc))

    return version
