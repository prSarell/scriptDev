"""
Build Tool — core
Pulls published assets from the H drive into a shot on scratch, keeps
track of which version each shot has, and manages what's on scratch.
No UI, so it can be tested under mayapy.

Design: pipeDev/filmPipeline_spec.md §3e (Build owns scratch), §3h
(drives, 1:1 mirror) and §3i (Build Shot workflow, department codes,
scratch management).

    H drive  G:\\H\\NWF_SHF\\maya\\assets\\prop\\backpack\\scenes\\s1234567\\backpack_s1234567_model_v002.ma
    scratch  G:\\scratch\\NWF_SHF\\maya\\publish\\assets\\prop\\backpack\\scenes\\s1234567\\backpack_s1234567_model_v002.ma
             (one copy per version, shared by every shot; each shot's
             assets\\build_manifest.json records the version it uses)
    rig      ...\\sequences\\EAP_010\\EAP_010_010\\assets\\character\\scout\\rig\\scout_rig.ma
             (fixed name the shot references, hardlinked to a version in
             publish\\; spec §4a, option C)
    camera   ...\\sequences\\EAP_010\\EAP_010_010\\assets\\camera\\cam.ma  (stays in its shot)

Shares drive settings, department codes and film-folder helpers with the
Publish tool (pipeDev/publishDev/publishTool_api.py).
"""

import os
import re
import sys
import json
import stat
import ctypes
import shutil
from datetime import datetime

import maya.cmds as cmds

_PUBLISH_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "publishDev")
if os.path.isdir(_PUBLISH_DIR) and _PUBLISH_DIR not in sys.path:
    sys.path.append(_PUBLISH_DIR)

import publishTool_api as pub
from publishTool_api import PublishError as BuildError   # same "student can fix" error
import pipeEnv                                            # $PIPE_SCRATCH reference paths

MANIFEST_NAME = "build_manifest.json"   # in <shot>/assets/, records what was pulled
KEEP_FILES = ("workspace.mel",)          # never removed from scratch

# <asset>_<login>_<code>_v###.<ext>, in <asset>\scenes\<dept>\<login>\
# (spec §4g, 2026-11-23; before that <asset>\scenes\<login>\, still read).
# Publishes are personal (spec §4 "Personal work folders", 2026-10-15).
PUBLISHED_RE = re.compile(r"^(?P<asset>.+)_(?P<login>[a-z0-9]+)_(?P<code>[A-Za-z]+)"
                          r"_v(?P<version>\d{3})\.(?P<ext>ma|mb)$", re.IGNORECASE)
DEPT_CODES = [code for _, code in pub.DEPARTMENTS]
DEPT_LABELS = dict((code, label) for label, code in pub.DEPARTMENTS)
DEPT_LABELS["cam"] = "Camera"


# ---------------------------------------------------------------------------
# Films and shots
# ---------------------------------------------------------------------------

# Shared with the Publish tool's picker.
list_films = pub.list_films
list_shots = pub.list_shots


def shot_folder(root, film, seq, shot):
    return os.path.join(root, film, "maya", "sequences", seq, shot)


def shot_of_scene(scene_path, scratch_root):
    """(film, seq, shot) if the scene is inside a shot on scratch, else None."""
    try:
        root, rel = pub.find_film_folder(scene_path)
    except BuildError:
        return None
    if (not pub._same_path(root, scratch_root) or len(rel) < 5
            or rel[1] != "maya" or rel[2] != "sequences"):
        return None
    return rel[0], rel[3], rel[4]


# ---------------------------------------------------------------------------
# Build by department (spec §4 "Build by department", user 2026-10-28): the
# artist's department decides what Build offers, "it would basically filter
# out rigs for the lighting team". Only what Build can build today is
# listed; caches, lights and lookDev shaders on caches come later, and FX
# and Lighting with them.
# ---------------------------------------------------------------------------

CAMERA_CODE = "cam"
CACHE_CODE = "cache"
DEPT_LABELS[CACHE_CODE] = "Anim Cache"
ENV_CODE = pub.ENV_CODE
# (label, department code, what it builds: published department codes,
# "cam" for the shot camera, "env" for environments, "cache" for the shot's
# animation caches; None = coming soon).
BUILD_FOR = [
    ("Modeling", "model", ["model"]),
    ("Rigging", "rig", ["model"]),
    ("Creature", "creature", ["model", "rig", "creature", "lookDev", ENV_CODE, CAMERA_CODE,
                              CACHE_CODE]),
    ("LookDev", "lookDev", ["model", "lookDev"]),
    ("Layout", "layout", ["model", "rig", ENV_CODE, CAMERA_CODE]),
    # Caches too, "occasionally to compare changes" (user, 2026-10-28).
    ("Animation", "anim", ["model", "rig", ENV_CODE, CAMERA_CODE, CACHE_CODE]),
    ("FX", "fx", None),
    ("Lighting", "lighting", None),
]
BUILD_FOR_LABELS = dict((code, label) for label, code, _ in BUILD_FOR)

# THE PIPE'S DEPARTMENTS — LOCKED (user, 2026-10-30), a fixed design feature:
# Build's Add to the list and Build into Department dropdowns show exactly
# this (publishTool_api.DEPARTMENTS, the one copy). No Environment.
DEPARTMENTS = pub.DEPARTMENTS
DEPT_LABELS.update((code, label) for label, code in DEPARTMENTS)


def list_buildable(h_root, film):
    """list_published without the publishes stamped env, made before
    environment publishes became Modeling publishes (user, 2026-10-30: "we
    don't need to see the old bad publishes")."""
    return [p for p in list_published(h_root, film) if p["code"] != ENV_CODE]


def builds_for(department):
    """What a department's Build offers (codes, see BUILD_FOR); [] for one
    that's coming soon or unknown."""
    return next((list(t or []) for _, c, t in BUILD_FOR if c == department), [])


def live_departments():
    return [c for _, c, t in BUILD_FOR if t]


def department_of_scene(scene_path):
    """The department the open scene is worked in, from its working folder
    (scenes\\<department>\\<login>\\, spec "Shot working folders" and
    "Asset working folders"), else from its file name (scout_rig_v002 ->
    rig, as the Publish tool does), else Animation for a shot and Modeling
    for an asset. Never a coming-soon department: a lighting scene starts
    on Layout until Lighting builds. None outside the pipe."""
    try:
        _, rel = pub.find_film_folder(scene_path)
    except BuildError:
        return None
    if len(rel) < 6 or rel[1] != "maya" or rel[2] not in ("sequences", "assets"):
        return None
    shot = rel[2] == "sequences"
    live = live_departments()
    found = None
    if len(rel) > 7 and rel[5] == "scenes":
        found = next((c for c in BUILD_FOR_LABELS if c.lower() == rel[6].lower()), None)
    if not found:
        words = re.split(r"[_.]", os.path.basename(scene_path).lower())
        found = next((c for c in BUILD_FOR_LABELS if c.lower() in words), None)
    if found in live:
        return found
    return "layout" if shot and found else "anim" if shot else "model"


# ---------------------------------------------------------------------------
# Published assets on the H drive
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Version ids. Publishes are personal, so a version is a person + number
# ("scout/v003"): two people can both have a v003. The latest is the most
# recently published, whoever published it (spec §4 "Personal work
# folders": "Time stamp of the asset defines if it is the latest").
# ---------------------------------------------------------------------------

def version_id(login, version):
    return "%s/v%03d" % (login or "?", version)


def entry_version_id(entry):
    """The version id a manifest entry records. Entries from before personal
    publishes have no login and match no current version."""
    return version_id(entry.get("login"), entry["version"])


def version_label(published, vid, mark_latest=True):
    """'v003 (s1234567)', plus '  (latest)' for the newest."""
    info = published.get("info", {}).get(vid)
    if not info:
        return vid
    text = "v%03d (%s)" % (info["version"], info["login"])
    if mark_latest and vid == published.get("latest"):
        text += "  (latest)"
    return text


def newer_available(published, entry):
    """True if the published entry has something newer than what the
    manifest entry records."""
    if not entry:
        return False
    current = entry_version_id(entry)
    info = published.get("info", {})
    if current not in info:
        return True     # an old or removed version: anything on the H drive is newer
    return info[published["latest"]]["time"] > info[current]["time"]


def _add_version(entry, login, version, path, time_path=None):
    vid = version_id(login, version)
    entry["versions"][vid] = path
    entry["info"][vid] = {"login": login, "version": version,
                          "time": publish_time(time_path or path)}


def _finish(entry):
    entry["latest"] = max(entry["info"], key=lambda v: entry["info"][v]["time"])
    return entry


def sorted_versions(published):
    """Version ids, newest first."""
    return sorted(published["versions"], key=lambda v: published["info"][v]["time"],
                  reverse=True)


def list_published(h_root, film):
    """Every published asset on the H drive, grouped by asset + department.

    Returns a list of dicts sorted by type/asset/department:
      {asset_type, asset, code, versions: {vid: path},
       info: {vid: {login, version, time}}, latest: vid}
    """
    assets_dir = os.path.join(h_root, film, "maya", "assets")
    groups = {}
    for asset_type, asset in pub.list_h_assets(h_root, film):
        scenes = os.path.join(assets_dir, asset_type, asset, "scenes")
        # Publishes are in scenes\<dept>\<login>\ (spec §4g) and, before
        # 2026-11-23, scenes\<login>\: both are read.
        for dirpath, dirnames, filenames in os.walk(scenes):
            login = os.path.basename(dirpath)
            for name in filenames:
                m = PUBLISHED_RE.match(name)
                # Only in the publisher's own folder, named for this asset.
                if (not m or m.group("asset").lower() != asset.lower()
                        or m.group("login").lower() != login.lower()):
                    continue
                code = m.group("code")
                key = (asset_type, asset, code)
                entry = groups.setdefault(key, {
                    "asset_type": asset_type, "asset": asset, "code": code,
                    "versions": {}, "info": {}})
                _add_version(entry, login.lower(), int(m.group("version")),
                             os.path.join(dirpath, name))
    result = []
    for key in sorted(groups, key=lambda k: (k[0], k[1].lower(),
                                             DEPT_CODES.index(k[2]) if k[2] in DEPT_CODES else 99)):
        result.append(_finish(groups[key]))
    return result


CAMERA_TYPE = "camera"              # asset_type used for a shot's camera
CAMERA_NAME = "camera1"             # the shot camera is always live as camera1
OLD_CAMERA_NAME = "camera1_old"     # what an existing camera1 is renamed to
DATA_NAME = CAMERA_NAME + "_DATA"   # holds the keys, drives camera1 1:1
CAMERA_MAP_FORMAT = 2               # camera group + data node (2026-10-20)
CURVE_KEY_ATTRS = ("ktv", "kix", "kiy", "kox", "koy", "kit", "kot", "kwl", "tan", "wgt")
CAMERA_FILES = {"camera": "assets/camera/cam.ma",
                "keys": "assets/camera/camAnim.ma",
                "map": "assets/camera/camAnim.json"}
# The published <shot>_cam_GRP's stamp says which version is built.
DEPT_STAMP, VERSION_STAMP, BY_STAMP = "pipe_department", "pipe_version", "pipe_artistId"
CAMERA_RE = re.compile(r"^(?P<shot>.+)_(?P<login>[a-z0-9]+)_(?P<code>cam|camAnim)"
                       r"_v(?P<version>\d{3})\.(?P<ext>ma|json)$", re.IGNORECASE)


def _walk_shot_publishes(scenes):
    """os.walk over a shot's scenes folder on H: publishes are in each
    person's scenes\\<dept>\\<login>\\ (spec §4g) and, before 2026-11-23,
    scenes\\<login>\\. Callers match the folder's name to the login in the
    file name, so nothing else counts."""
    for dirpath, dirnames, filenames in os.walk(scenes):
        yield dirpath, filenames


def list_shot_cameras(h_root, film, seq, shot):
    """The shot's published cameras on the H drive (everyone's, from each
    person's scenes\\<login>\\), as a list with at most one entry shaped
    like list_published()'s, plus 'kind': 'camera' and
    'files': {vid: {camera, keys, map}}. Only complete versions (all three
    files) in the camera group format count; older publishes are left out
    and need republishing (user, 2026-10-20). The latest is the newest by
    publish time."""
    scenes = os.path.join(shot_folder(h_root, film, seq, shot), "scenes")
    found = {}
    for dirpath, filenames in _walk_shot_publishes(scenes):
        login = os.path.basename(dirpath).lower()
        for name in filenames:
            m = CAMERA_RE.match(name)
            if (not m or m.group("shot").lower() != shot.lower()
                    or m.group("login").lower() != login):
                continue
            part = ("camera" if m.group("code").lower() == "cam" else
                    "keys" if m.group("ext").lower() == "ma" else "map")
            found.setdefault((login, int(m.group("version"))), {})[part] = \
                os.path.join(dirpath, name)
    entry = {"kind": "camera", "asset_type": CAMERA_TYPE, "asset": shot,
             "code": CAMERA_CODE, "files": {}, "versions": {}, "info": {}}
    for (login, version), files in found.items():
        if len(files) == 3 and _camera_map_format(files["map"]) == CAMERA_MAP_FORMAT:
            _add_version(entry, login, version, files["camera"])
            entry["files"][version_id(login, version)] = files
    return [_finish(entry)] if entry["files"] else []


# A Final animation publish's caches (publishTool_anim): one Alembic per
# item, in the shot's cache\alembic\anim\<login>\ (cache\alembic\<login>\
# before 2026-11-23), with a .json beside it saying
# what it is.
CACHE_RE = re.compile(r"^(?P<item>.+)_anim_v(?P<version>\d{3})\.abc$", re.IGNORECASE)


def _read_json(path):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (IOError, OSError, ValueError):
        return None


def list_shot_caches(h_root, film, seq, shot):
    """The shot's published animation caches on the H drive (everyone's),
    one entry per item shaped like list_published()'s, plus 'kind':
    'cache', 'cache_info': {vid: the .json beside it}. asset_type is the
    cached asset's type ('shot' for something made in the shot), code
    'cache'. Caches from before per-person folders, or without their .json
    (published before 2026-10-28), are left out: republish them."""
    caches = os.path.join(shot_folder(h_root, film, seq, shot), "cache", "alembic")
    groups = {}
    if not os.path.isdir(caches):
        return []
    # cache\alembic\<dept>\<login>\ (spec §4g) and, before 2026-11-23,
    # cache\alembic\<login>\.
    people = []
    for name in sorted(os.listdir(caches)):
        folder = os.path.join(caches, name)
        if not os.path.isdir(folder):
            continue
        if name.lower() in [d.lower() for d in pub.DEPT_FOLDERS]:
            people += [(login, os.path.join(folder, login)) for login in sorted(os.listdir(folder))
                       if os.path.isdir(os.path.join(folder, login))]
        else:
            people.append((name, folder))
    for login, folder in people:
        for name in os.listdir(folder):
            if not name.lower().startswith(shot.lower() + "_"):
                continue
            m = CACHE_RE.match(name[len(shot) + 1:])
            path = os.path.join(folder, name)
            info = _read_json(os.path.splitext(path)[0] + ".json") if m else None
            if not info:
                continue
            stamp = info.get("asset") or {}
            asset_type = stamp.get("assetType") or "shot"
            key = (asset_type, info.get("item") or m.group("item"))
            entry = groups.setdefault(key, {
                "kind": "cache", "asset_type": key[0], "asset": key[1], "code": CACHE_CODE,
                "versions": {}, "info": {}, "cache_info": {}})
            _add_version(entry, login.lower(), int(m.group("version")), path)
            entry["cache_info"][version_id(login.lower(), int(m.group("version")))] = info
    return [_finish(groups[k]) for k in sorted(groups, key=lambda k: (k[0], k[1].lower()))]


def _camera_map_format(path):
    try:
        with open(path, "r") as f:
            return json.load(f).get("format", 1)
    except (IOError, OSError, ValueError):
        return None


def publish_time(path):
    """When a file was published. copy2 keeps the source's modified time,
    so use the H-drive file's creation time (Windows) where available."""
    st = os.stat(path)
    return st.st_ctime if os.name == "nt" else st.st_mtime


# ---------------------------------------------------------------------------
# Pulling into the shared publish folder on scratch (spec §3i "One shared
# publish folder on scratch"): one copy per version, used by every shot
# ---------------------------------------------------------------------------

PUBLISH_FOLDER = "publish"      # <scratch>/<film>/maya/publish, mirrors the H drive's maya/


def maya_dir_of_shot(shot_dir):
    """<root>/<film>/maya for a shot folder <root>/<film>/maya/sequences/<seq>/<shot>."""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.normpath(shot_dir))))


def publish_dir(maya_dir):
    return os.path.join(maya_dir, PUBLISH_FOLDER)


def _maya_rel(h_path):
    """The part of an H-drive path below <film>/maya, e.g.
    'assets/prop/backpack/scenes/backpack_model_v002.ma'."""
    _, rel = pub.find_film_folder(h_path)
    if len(rel) < 3 or rel[1] != "maya":
        raise BuildError("Not inside a film's maya folder: %s" % h_path)
    return "/".join(rel[2:])


def legacy_rel_path(asset_type, asset, code, ext):
    """Where Build Shot used to copy an asset inside the shot (fixed name,
    before the shared publish folder). Only used to find and repoint old
    references."""
    parts = ["assets", asset_type, asset]
    if code != "model":
        parts.append(code)
    parts.append(asset + ext)
    return "/".join(parts)


def entry_path(shot_dir, entry):
    """Full path of what the shot's scenes reference for a manifest entry:
    the rig's fixed name in the shot for linked departments, the shared
    publish folder for other assets, the shot itself for cameras (and old
    entries)."""
    if entry.get("link"):
        return os.path.join(shot_dir, *entry["link"].split("/"))
    return shared_path(shot_dir, entry)


def shared_path(shot_dir, entry):
    """Full path of the version file a manifest entry uses (in the shared
    publish folder), or the in-shot file for cameras and old entries."""
    if entry.get("shared"):
        return os.path.join(publish_dir(maya_dir_of_shot(shot_dir)), *entry["shared"].split("/"))
    return os.path.join(shot_dir, *entry["file"].split("/"))


# ---------------------------------------------------------------------------
# Rigs: a fixed name per shot, hardlinked to a version in the publish folder
# (spec §4a, option C, built 2026-10-20). The shot's reference path never
# changes, so updating or rolling back is a relink plus a reload, never a
# Replace Reference. Every shot follows an update by default; one shot can
# be rolled back on its own. Where the drive can't hardlink (exFAT, network
# shares) the fixed name is a read-only copy instead (option B): same path,
# more disk.
# ---------------------------------------------------------------------------

LINKED_CODES = ("rig",)
LINKED, COPY, MISSING, STALE = "linked", "copy", "missing", "stale"


def link_rel_path(asset_type, asset, code, ext):
    """The fixed name inside the shot, e.g.
    'assets/character/scout/rig/scout_rig.ma'."""
    return "/".join(["assets", asset_type, asset, code,
                     "%s_%s.%s" % (asset, code, ext.lstrip(".").lower())])


def _is_current(link, source):
    """True if link already holds source: the same data (hardlink), or a
    copy made from it (copy2 keeps size and modified time)."""
    if not (os.path.isfile(link) and os.path.isfile(source)):
        return False
    if os.path.samefile(link, source):
        return True
    a, b = os.stat(link), os.stat(source)
    return a.st_size == b.st_size and int(a.st_mtime) == int(b.st_mtime)


def _lock_publish_folder(maya_dir):
    """Make every file in the publish folder read-only again. Windows keeps
    read-only per piece of data, not per name, so removing a hardlink (which
    needs it writable) unlocks the version it pointed at too."""
    for dirpath, _, filenames in os.walk(publish_dir(maya_dir)):
        for name in filenames:
            path = os.path.join(dirpath, name)
            if os.access(path, os.W_OK):
                os.chmod(path, stat.S_IREAD)


def _drive_can_link(path):
    """True if path's drive is NTFS (hardlinks work). Only used to decide
    whether to turn an existing copy back into a link; os.link failing is
    what decides when making one."""
    if os.name != "nt":
        return True
    name = ctypes.create_unicode_buffer(32)
    drive = os.path.splitdrive(os.path.abspath(path))[0] + "\\"
    if not ctypes.windll.kernel32.GetVolumeInformationW(
            ctypes.c_wchar_p(drive), None, 0, None, None, None, name, len(name)):
        return False
    return name.value.upper() == "NTFS"


def _remove_name(path):
    if os.path.isfile(path):
        os.chmod(path, stat.S_IWRITE)
        os.remove(path)


def link_version(source, link, maya_dir):
    """Point the shot's fixed name at one version in the publish folder:
    a hardlink where the drive allows, else a read-only copy. Returns True
    if hardlinked."""
    if _is_current(link, source):
        if os.path.samefile(link, source):
            return True
        if not _drive_can_link(link):
            return False    # a copy is the best this drive can do
    try:
        _remove_name(link)
    except OSError as e:
        raise BuildError("Couldn't replace %s (%s). Is it open in another Maya?"
                         % (os.path.basename(link), e.strerror or e))
    finally:
        _lock_publish_folder(maya_dir)
    if not os.path.isdir(os.path.dirname(link)):
        os.makedirs(os.path.dirname(link))
    try:
        os.link(source, link)
        return True
    except OSError:
        shutil.copy2(source, link)
        os.chmod(link, stat.S_IREAD)
        return False


def link_state(shot_dir, entry):
    """LINKED, COPY (works, but uses its own disk), MISSING or STALE (holds
    something other than the version the manifest records, e.g. after the
    shot folder was copied from elsewhere). None for entries without a
    link. Build Shot fixes MISSING and STALE by building the asset again."""
    if not entry or not entry.get("link"):
        return None
    link, source = entry_path(shot_dir, entry), shared_path(shot_dir, entry)
    if not os.path.isfile(link):
        return MISSING
    if not os.path.isfile(source):
        return COPY     # version cleared from publish\: the shot still has the data
    if os.path.samefile(link, source):
        return LINKED
    return COPY if _is_current(link, source) else STALE


def _manifest_path(shot_dir):
    return os.path.join(shot_dir, "assets", MANIFEST_NAME)


def read_manifest(shot_dir):
    try:
        with open(_manifest_path(shot_dir), "r") as f:
            return json.load(f)
    except (IOError, OSError, ValueError):
        return {}


def _write_manifest(shot_dir, manifest):
    path = _manifest_path(shot_dir)
    if not os.path.isdir(os.path.dirname(path)):
        os.makedirs(os.path.dirname(path))
    with open(path, "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)


def manifest_key(asset_type, asset, code):
    return "%s/%s/%s" % (asset_type, asset, code)


# The shot's build lists on the H drive (user, 2026-10-23): shared by
# everyone building the shot, so a list comes back on any machine or scratch
# drive. One per department (user, 2026-10-30: "everyone on the same shot
# should see the same list"), so Lighting's list never carries Animation's
# picks, in the shot's data folder: <shot>\data\build\<department>.json.
# Just which assets (manifest keys): versions start at the latest and keys at
# the shot's latest keys. Saved on Build Shot and when "-" takes an asset off.
SHOT_LIST_FOLDER = ("data", "build")
# The one list per shot from before 2026-10-30. Read (never written) as the
# starting list for the departments that used it.
OLD_SHOT_LIST_NAME = "build_list.json"
OLD_SHOT_LIST_DEPARTMENTS = ("layout", "anim")


def build_list_path(folder, department):
    """A department's build list for a shot or asset folder on H. Assets
    have lists too since Build references into them like a shot (user,
    2026-10-30)."""
    return os.path.join(folder, *SHOT_LIST_FOLDER + ("%s.json" % department,))


def shot_list_path(h_root, film, seq, shot, department):
    return build_list_path(shot_folder(h_root, film, seq, shot), department)


def _read_list(path):
    try:
        with open(path, "r") as f:
            return list(json.load(f).get("assets", []))
    except (IOError, OSError, ValueError, AttributeError):
        return None


def read_build_list(folder, department):
    """The department's saved list of manifest keys for a shot or asset
    folder on H, or None if it has none yet."""
    keys = _read_list(build_list_path(folder, department))
    if keys is None and department in OLD_SHOT_LIST_DEPARTMENTS:
        keys = _read_list(os.path.join(folder, OLD_SHOT_LIST_NAME))
    return keys


def read_shot_list(h_root, film, seq, shot, department):
    return read_build_list(shot_folder(h_root, film, seq, shot), department)


def read_build_list_usd(folder, department):
    """The keys on the department's list that load as USD (spec §4h)."""
    try:
        with open(build_list_path(folder, department), "r") as f:
            return set(json.load(f).get("usd", []))
    except (IOError, OSError, ValueError, AttributeError):
        return set()


def write_build_list(folder, department, keys, usd=()):
    """Save the department's list (manifest keys, in list order) for a shot
    or asset folder on H. usd: the keys loaded as USD stages (spec §4h)."""
    path = build_list_path(folder, department)
    if not os.path.isdir(os.path.dirname(path)):
        os.makedirs(os.path.dirname(path))
    if os.path.exists(path):
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
    try:
        login = pub.who()
    except BuildError:
        login = ""
    with open(path, "w") as f:
        json.dump({"assets": list(keys), "usd": [k for k in keys if k in set(usd)],
                   "department": department, "saved_by": login,
                   "saved": datetime.now().isoformat(timespec="seconds")}, f, indent=2)


def write_shot_list(h_root, film, seq, shot, department, keys):
    write_build_list(shot_folder(h_root, film, seq, shot), department, keys)


def texture_folder_of(path):
    """The texture folder that goes with a published file (H drive or
    scratch publish folder): <asset>\\sourceimages\\<login>\\<file name
    without extension> beside <asset>\\scenes\\<dept>\\<login>\\<file> (spec
    §4g; scenes\\<login>\\ before 2026-11-23) (publishTool_textures,
    2026-10-20). It may not exist (nothing textured)."""
    login_dir = os.path.dirname(path)
    try:
        asset_dir = pub.project_of_publish(login_dir)
    except BuildError:
        # Not a scene publish (a cache in cache\alembic\...): no textures.
        # Callers only walk / copy what exists, so a folder that doesn't
        # exist is the answer, as before §4g.
        asset_dir = os.path.dirname(os.path.dirname(login_dir))
    return os.path.join(asset_dir, "sourceimages", os.path.basename(login_dir),
                        os.path.splitext(os.path.basename(path))[0])


# Files published beside a version under the same name: an environment's
# one-frame reference cache (spec §4c). Pulled and cleared with it.
SIDE_FILES = (".abc",)


def side_files(path):
    stem = os.path.splitext(path)[0]
    return [stem + ext for ext in SIDE_FILES if os.path.isfile(stem + ext)]


def version_files(path):
    """A pulled version in the publish folder plus its textures and side
    files: what clearing that version removes (spec "Clearing old
    versions": its textures go with it). A pulled USD (spec §4h): the .usd
    and the textures\\ folder beside it."""
    if path.lower().endswith(USD_EXTENSIONS):
        return [path] + _folder_files(os.path.join(os.path.dirname(path), USD_TEXTURES))
    found = [path] + side_files(path)
    for dirpath, _, filenames in os.walk(texture_folder_of(path)):
        found += [os.path.join(dirpath, n) for n in filenames]
    return found


def _copy_if_changed(source, dest):
    if os.path.isfile(dest) and os.path.getsize(dest) == os.path.getsize(source):
        return False
    if not os.path.isdir(os.path.dirname(dest)):
        os.makedirs(os.path.dirname(dest))
    if os.path.isfile(dest):
        os.chmod(dest, stat.S_IWRITE)
    shutil.copy2(source, dest)
    os.chmod(dest, stat.S_IREAD)
    return True


def copy_published(source, maya_dir):
    """Copy one published file from the H drive into the shared publish
    folder under the same path and name, unless an identical copy is
    already there, plus the textures published with it. Read-only, like
    the publish. Returns (dest, copied)."""
    dest = os.path.join(publish_dir(maya_dir), *_maya_rel(source).split("/"))
    textures = texture_folder_of(source)
    for dirpath, _, filenames in os.walk(textures):
        for name in filenames:
            src = os.path.join(dirpath, name)
            _copy_if_changed(src, os.path.join(texture_folder_of(dest),
                                               os.path.relpath(src, textures)))
    for side in side_files(source):
        _copy_if_changed(side, os.path.splitext(dest)[0] + os.path.splitext(side)[1])
    return dest, _copy_if_changed(source, dest)


def pull(shot_dir, published, vid, usd=False):
    """Make sure one published version (a version id, e.g. 'scout/v003')
    is in the shared publish folder and record that this shot uses it.
    Other shots' versions are untouched. usd: the version's USD export
    instead of its .ma (spec §4h). Returns the path in the publish
    folder."""
    if vid not in published["versions"]:
        raise BuildError("%s of %s %s isn't on the H drive."
                         % (vid, published["asset"], published["code"]))
    source = published["versions"][vid]
    if usd:
        source = usd_export(source)
        if not source:
            raise BuildError(no_usd_message(published, vid))
    maya_dir = maya_dir_of_shot(shot_dir)
    dest, _ = copy_usd(source, maya_dir) if usd else copy_published(source, maya_dir)

    info = published["info"][vid]
    key = manifest_key(published["asset_type"], published["asset"], published["code"])
    manifest = read_manifest(shot_dir)
    entry = {
        "version": info["version"],
        "login": info["login"],
        "shared": _maya_rel(source),
        "source": source,
        "pulled": datetime.now().isoformat(timespec="seconds"),
    }
    if published.get("from_shot"):         # another shot's cache (shot_items)
        entry["from_shot"] = list(published["from_shot"])
    if usd:
        entry["usd"] = True
    elif published["code"] in LINKED_CODES:
        entry["link"] = link_rel_path(published["asset_type"], published["asset"],
                                      published["code"], os.path.splitext(dest)[1])
        entry["hardlink"] = link_version(dest, entry_path(shot_dir, entry), maya_dir)
    manifest[key] = entry
    _write_manifest(shot_dir, manifest)
    return dest


def scene_references():
    """[(reference node, path as written, full path, resolved path)] for
    the open scene's top-level references, loaded or not, including ones
    whose file is missing. 'As written' is exactly what the scene stores
    (e.g. '$PIPE_SCRATCH/NWF_SHF/...'); 'full path' is that with the
    variable and any project-relative part filled in."""
    found = []
    for node in cmds.ls(type="reference") or []:
        if node == "sharedReferenceNode" or "_UNKNOWN_REF_NODE_" in node:
            continue
        try:
            if cmds.referenceQuery(node, parent=True, referenceNode=True):
                continue    # nested: it comes with its parent's file
            written = cmds.referenceQuery(node, filename=True, unresolvedName=True,
                                          withoutCopyNumber=True)
            resolved = cmds.referenceQuery(node, filename=True, withoutCopyNumber=True)
        except RuntimeError:
            continue
        found.append((node, written, _absolute(written), _absolute(resolved)))
    return found


def _absolute(path):
    """Fill in $PIPE_SCRATCH, and resolve project-relative reference paths
    (e.g. 'assets/prop/backpack/backpack.ma', as older builds wrote them)
    against the current Maya project."""
    path = os.path.expandvars(path) if path else path
    if path and not os.path.isabs(path):
        workspace = cmds.workspace(query=True, rootDirectory=True) or ""
        return os.path.normpath(os.path.join(workspace, path))
    return path


def referenced_nodes(path):
    """Reference nodes in the open scene that point at path."""
    target = os.path.normcase(os.path.normpath(path))
    return [node for node, _, full, resolved in scene_references()
            if target in (os.path.normcase(os.path.normpath(resolved)),
                          os.path.normcase(os.path.normpath(full)))]


def written_path(ref_node):
    """The reference's path exactly as the scene stores it."""
    return cmds.referenceQuery(ref_node, filename=True, unresolvedName=True,
                               withoutCopyNumber=True)


def repoint_reference(ref_node, path):
    """Swap a reference to another file ("Replace Reference"). Keys and
    other changes made on top of it carry over where node names match.
    path may use $PIPE_SCRATCH."""
    cmds.file(path, loadReference=ref_node)


def reload_references_to(path):
    """Reload any reference in the open scene that points at path, so an
    update shows up straight away. Returns the reference nodes reloaded."""
    nodes = referenced_nodes(path)
    for node in nodes:
        if cmds.referenceQuery(node, isLoaded=True):
            cmds.file(unloadReference=node)
        cmds.file(loadReference=node)
    return nodes


def namespace_for(asset, code):
    return asset if code == "model" else "%s_%s" % (asset, code)


def _old_paths(shot_dir, published, entry):
    """Files an existing reference to this asset might point at: the
    version the shot had, and the fixed-name copy Build Shot used to keep
    inside the shot (so old scenes get repointed too)."""
    paths = [entry_path(shot_dir, entry)] if entry else []
    for ext in (".ma", ".mb"):
        paths.append(os.path.join(shot_dir, *legacy_rel_path(
            published["asset_type"], published["asset"], published["code"], ext).split("/")))
    return paths


def any_version_references(shot_dir, published):
    """Reference nodes pointing at any version of this asset + department
    in the shot's publish folder, whatever the manifest says: old-style
    names (backpack_model_v003.ma) as well as personal ones
    (scenes\\<login>\\backpack_scout_model_v005.ma). Catches a scene whose
    reference the manifest no longer remembers, e.g. another scene in the
    same shot, or one saved before personal publishes."""
    folder = os.path.normcase(os.path.join(
        publish_dir(maya_dir_of_shot(shot_dir)), "assets",
        published["asset_type"], published["asset"], "scenes"))
    name = re.compile(r"^%s_(?:[^_]+_)?%s_v\d{3}\.(ma|mb)$"
                      % (re.escape(published["asset"]), re.escape(published["code"])),
                      re.IGNORECASE)
    found = []
    for node, _, full, resolved in scene_references():
        for path in (resolved, full):
            path = os.path.normcase(os.path.normpath(path or ""))
            if path.startswith(folder + os.sep) and name.match(os.path.basename(path)):
                found.append(node)
                break
    return found


def scene_version(shot_dir, published):
    """What the open scene has of this asset + department: its version id,
    '' if it's there at a version that can't be told (old names, old camera
    stamps), or None if it isn't in the scene. Build Shot leaves anything
    already in the scene alone unless the student picks another version
    (user, 2026-10-20: adding an asset must not rebuild the others)."""
    if published.get("kind") == "camera":
        node, vid = shot_camera((published.get("from_shot") or (None, published["asset"]))[1])
        return (vid or "") if node else None
    stage = stage_of(published)
    if stage:
        m = USD_RE.match(os.path.basename(_absolute(stage[2])))
        return version_id(m.group("login").lower(), int(m.group("version"))) if m else ""
    key = manifest_key(published["asset_type"], published["asset"], published["code"])
    entry = read_manifest(shot_dir).get(key)
    if entry and referenced_nodes(entry_path(shot_dir, entry)):
        return entry_version_id(entry)
    for node in any_version_references(shot_dir, published):
        m = PUBLISHED_RE.match(os.path.basename(_absolute(written_path(node))))
        return version_id(m.group("login").lower(), int(m.group("version"))) if m else ""
    if any(referenced_nodes(p) for p in _old_paths(shot_dir, published, entry)):
        return ""
    return None


# Files from a newer Maya (the move to 2027, 2026-10-28): Maya opens older
# scenes, not reliably newer ones, so while some machines are on 2025 and
# some on 2027 Build says when a publish was saved in a newer Maya. Read
# from the "requires maya" line every .ma carries, so it works for
# publishes made before this check.

_REQUIRES_MAYA = re.compile(r'^requires maya "(\d{4})')


def saved_in_maya(path):
    """The Maya version (e.g. 2027) a .ma was saved in, or None."""
    if not path.lower().endswith(".ma") or not os.path.isfile(path):
        return None
    try:
        with open(path, "r", errors="replace") as f:
            for i, line in enumerate(f):
                m = _REQUIRES_MAYA.match(line)
                if m:
                    return int(m.group(1))
                if i > 500 or line.startswith("createNode"):
                    break
    except (IOError, OSError):
        pass
    return None


def newer_maya_warning(path):
    """A warning if path was saved in a newer Maya than this one, else None."""
    made = saved_in_maya(path)
    this = int(cmds.about(majorVersion=True))
    if made and made > this:
        return ("published from Maya %d, newer than this Maya (%d): it may not load "
                "correctly here. Open this in Maya %d, or ask for it to be published "
                "from Maya %d." % (made, this, made, this))
    return None


def build_asset(shot_dir, published, vid, department=None, usd=False, replace=False):
    """Build one asset (see _build_asset), then point any MetaHuman DNA
    nodes it brought at their files on this drive (pipeEnv.fix_dna_paths:
    DNA nodes can't read $PIPE_SCRATCH). A cache also gets its look, picked
    by the department building (apply_look). usd: load a model's USD
    export as a USD stage instead (spec §4h); replace: allow switching an
    asset between a Maya reference and a USD stage (the other is removed)."""
    if usd:
        return _build_usd(shot_dir, published, vid, replace)
    done, warning, replaced = _build_asset(shot_dir, published, vid, replace)
    if published.get("kind") == "cache":
        look_done, look_warning = apply_look(shot_dir, published, vid, department)
        if look_done and done == ["already up to date"]:
            done = []
        done += look_done
        warning = " ".join(w for w in (warning, look_warning) if w) or None
    if published.get("kind") not in ("camera", "cache"):
        fixed = pipeEnv.fix_dna_paths()
        if fixed:
            if done == ["already up to date"]:
                done = []
            done.append("MetaHuman DNA pointed at this drive (%d)" % len(fixed))
    return done, warning, replaced


def _build_asset(shot_dir, published, vid, replace=False):
    """One click for one asset: make sure the chosen version (a version id,
    e.g. 'scout/v003') is in the shared publish folder, then make sure the
    open scene references it. A reference to another version (or to an old
    copy in the shot) is repointed, never referenced twice. Only this shot
    changes. The asset loaded as a USD stage instead (spec §4h): refused
    unless replace, which swaps the stage for the reference, keeping its
    placement.

    Returns (list of what was done, warning or None, replaced) where
    replaced is the path of a version this shot no longer uses, or None."""
    if published.get("kind") == "camera":
        done, warning = build_camera(shot_dir, published, vid)
        return done, warning, None
    key = manifest_key(published["asset_type"], published["asset"], published["code"])
    namespace = namespace_for(published["asset"], published["code"])
    entry = read_manifest(shot_dir).get(key)
    previous = shared_path(shot_dir, entry) if entry else None
    linked = published["code"] in LINKED_CODES
    label = version_label(published, vid, mark_latest=False)
    done = []
    stage = stage_of(published)
    placement = None
    if stage:
        if not replace:
            raise BuildError(switch_message(published, to_usd=False))
        placement = cmds.xform(stage[0], query=True, worldSpace=True, matrix=True)
        remove_stage(stage[0])
        done.append("USD stage %s removed" % stage[0].split("|")[-1])
        entry = None    # the stage's USD isn't a Maya reference to repoint
    # Leftover unassigned shaders holding the asset's name (e.g. from an
    # old import whose geometry was deleted) are cleared, not a clash.
    cleared = pub.unused_shading_nodes(namespace)
    if cleared:
        cmds.delete(cleared)
        done.append("removed unused shader leftovers %s" % ", ".join(cleared))

    same = bool(entry) and entry_version_id(entry) == vid
    restored = bool(same and entry.get("shared") and not os.path.isfile(previous))
    relinked = bool(same and not restored and link_state(shot_dir, entry) in (MISSING, STALE))
    dest = pull(shot_dir, published, vid)
    if not entry:
        done.append("pulled %s" % label)
    elif not same:
        done.append("%s -> %s" % (version_label(published, entry_version_id(entry), False)
                                  if entry_version_id(entry) in published["info"]
                                  else "v%03d" % entry["version"], label))
    elif restored:
        done.append("%s pulled again (it was missing)" % label)
    elif relinked:
        done.append("%s relinked in this shot (it was missing or out of date)" % label)
    replaced = previous if previous and not pub._same_path(previous, dest) else None

    # What the shot's scenes reference: the fixed name in the shot for rigs,
    # the version in the publish folder for everything else.
    new_entry = read_manifest(shot_dir)[key]
    target = entry_path(shot_dir, new_entry)
    warning = newer_maya_warning(dest)
    if linked and not new_entry.get("hardlink"):
        warning = " ".join(w for w in (warning, "this drive can't hardlink, so the rig is a "
                                       "full copy in this shot (works the same, uses more disk).")
                           if w)

    # References are written with $PIPE_SCRATCH so the shot opens from any
    # drive (spec "Reference paths that work on any drive"). Point the
    # variable at this shot's drive first.
    pipeEnv.set_from_path(shot_dir)
    ref_path = pipeEnv.to_var_path(target)

    nodes = referenced_nodes(target)
    if nodes:
        old_ns = use_clean_namespace(target, namespace)
        if old_ns:
            done.append("renamed %s: to %s:" % (old_ns, namespace))
        rewritten = False
        for node in nodes:
            if not pipeEnv.uses_var(written_path(node)) and pipeEnv.uses_var(ref_path):
                repoint_reference(node, ref_path)   # full D:\... path -> $PIPE_SCRATCH
                rewritten = True
        if rewritten:
            done.append("reference path made drive-independent")
        elif restored or relinked or (linked and not same):
            # Same path, new content: a reload is all a rig update needs.
            reload_references_to(target)
            done.append("reloaded in scene")
        if not done:
            done.append("already up to date")
        return done, warning, replaced

    for path in _old_paths(shot_dir, published, entry):
        nodes = referenced_nodes(path)
        if nodes:
            for node in nodes:
                repoint_reference(node, ref_path)
            use_clean_namespace(target, namespace)
            done.append("scene reference switched to %s" % label)
            return done, warning, replaced

    # Any other version of this asset already referenced (for rigs: a scene
    # from before the fixed name): switch it rather than referencing the
    # asset a second time.
    nodes = any_version_references(shot_dir, published)
    if nodes:
        for node in nodes:
            repoint_reference(node, ref_path)
        use_clean_namespace(target, namespace)
        done.append("scene reference switched to %s" % label)
        return done, warning, replaced

    if published.get("kind") == "cache":
        reference_cache(ref_path, namespace)
        done.append("cache referenced into scene (%s_GRP, display: Reference)" % namespace)
        return done, warning, replaced
    reference_into_scene(ref_path, namespace)
    done.append("referenced into scene")
    if placement:
        for top in reference_tops(target)[:1]:
            cmds.xform(placement_node(top), worldSpace=True, matrix=placement)
            done.append("placed where the USD stage was")
    return done, warning, replaced


def other_shots_using(shot_dir, published, vid):
    """Shot folders on the same scratch film, other than shot_dir, that have
    this linked asset + department on a version other than vid."""
    key = manifest_key(published["asset_type"], published["asset"], published["code"])
    film_dir = os.path.dirname(maya_dir_of_shot(shot_dir))
    found = []
    for seq, shot in list_shots(os.path.dirname(film_dir), os.path.basename(film_dir)):
        other = os.path.join(film_dir, "maya", "sequences", seq, shot)
        if pub._same_path(other, shot_dir):
            continue
        entry = read_manifest(other).get(key)
        if entry and entry.get("link") and entry_version_id(entry) != vid:
            found.append(other)
    return found


def update_shots(shot_dirs, published, vid):
    """Relink a rig in shots that aren't open (spec §4a: every shot follows
    an update by default). Their scenes load the new version the next time
    they're opened, since the path they reference doesn't change.
    Returns (updated shot names, replaced version paths)."""
    updated, replaced = [], []
    for shot_dir in shot_dirs:
        key = manifest_key(published["asset_type"], published["asset"], published["code"])
        entry = read_manifest(shot_dir).get(key)
        dest = pull(shot_dir, published, vid)
        updated.append(os.path.basename(shot_dir))
        if entry and not pub._same_path(shared_path(shot_dir, entry), dest):
            replaced.append(shared_path(shot_dir, entry))
    return updated, replaced


def shots_using(maya_dir):
    """{full path of a pulled version: [shot, ...]} from every shot's
    build manifest under one film's maya folder on scratch."""
    used = {}
    seq_dir = os.path.join(maya_dir, "sequences")
    if not os.path.isdir(seq_dir):
        return used
    for seq in os.listdir(seq_dir):
        for shot in os.listdir(os.path.join(seq_dir, seq)) if os.path.isdir(
                os.path.join(seq_dir, seq)) else []:
            shot_dir = os.path.join(seq_dir, seq, shot)
            for entry in read_manifest(shot_dir).values():
                if entry.get("shared"):
                    path = os.path.normcase(os.path.normpath(shared_path(shot_dir, entry)))
                    used.setdefault(path, []).append(shot)
    return used


def unused_versions(paths, maya_dir):
    """The paths (pulled versions in the publish folder) that no shot's
    manifest uses and the open scene doesn't reference (or load as a USD
    stage)."""
    used = shots_using(maya_dir)
    in_scene = set(os.path.normcase(os.path.normpath(r)) for _, _, _, r in scene_references())
    in_scene |= set(os.path.normcase(os.path.normpath(_absolute(w))) for _, _, w in usd_stages())
    result, seen = [], set()
    for path in paths:
        key = os.path.normcase(os.path.normpath(path))
        if key in seen:
            continue    # replaced by more than one shot
        seen.add(key)
        if os.path.isfile(path) and key not in used and key not in in_scene \
                and key.startswith(os.path.normcase(publish_dir(maya_dir)) + os.sep):
            result.append(path)
    return result


# ---------------------------------------------------------------------------
# Repair: pull back anything the open scene references that's missing
# ---------------------------------------------------------------------------

def repair_scene(h_root):
    """For every reference in the open scene whose file is missing: if it
    points into a publish folder on scratch, copy that exact version back
    from the H drive and load it. Old in-shot copies can't be repaired
    this way (their version isn't known): Build Shot repoints those.

    Returns (fixed, not_fixed) as lists of messages."""
    fixed, not_fixed = [], []
    for node, written, full, resolved in scene_references():
        path = resolved if os.path.isfile(resolved) else full
        if os.path.isfile(path):
            continue
        if pipeEnv.uses_var(written) and not pipeEnv.current():
            not_fixed.append("%s: %s isn't set, so this scene can't tell which drive to "
                             "look on. Is mpPipe installed? Reopen the scene after "
                             "installing." % (os.path.basename(written), pipeEnv.VAR))
            continue
        name = os.path.basename(path)
        try:
            root, rel = pub.find_film_folder(path)
        except BuildError:
            not_fixed.append("%s: not in a film folder, can't tell where it came from." % name)
            continue
        if len(rel) > 3 and rel[1] == "maya" and rel[2] == PUBLISH_FOLDER:
            source = os.path.join(h_root, rel[0], "maya", *rel[3:])
            if not os.path.isfile(source):
                not_fixed.append("%s: not on the H drive either (%s)." % (name, source))
                continue
            dest, _ = copy_published(source, os.path.join(root, rel[0], "maya"))
            # Keep the path as the scene wrote it ($PIPE_SCRATCH stays).
            cmds.file(written if pipeEnv.uses_var(written) else dest, loadReference=node)
            fixed.append("%s: pulled again from the H drive and loaded." % name)
        elif _linked_entry(root, rel, path):
            # A rig's fixed name in the shot: the manifest says which version.
            entry = _linked_entry(root, rel, path)
            source = os.path.join(h_root, rel[0], "maya", *entry["shared"].split("/"))
            if not os.path.isfile(source):
                not_fixed.append("%s: v%03d isn't on the H drive (%s)."
                                 % (name, entry["version"], source))
                continue
            maya_dir = os.path.join(root, rel[0], "maya")
            dest, _ = copy_published(source, maya_dir)
            link_version(dest, path, maya_dir)
            cmds.file(written if pipeEnv.uses_var(written) else path, loadReference=node)
            fixed.append("%s: relinked to v%03d (%s) and loaded."
                         % (name, entry["version"], entry.get("login", "?")))
        elif len(rel) > 5 and rel[1] == "maya" and rel[2] == "sequences" and rel[5] == "assets":
            not_fixed.append("%s: an old copy kept inside the shot. Add %s in Build Shot "
                             "and build to switch it to a published version."
                             % (name, rel[7] if len(rel) > 8 else os.path.splitext(name)[0]))
        else:
            not_fixed.append("%s: missing, and not a pulled publish (%s)." % (name, path))
    usd_fixed, usd_not = _repair_stages(h_root)
    fixed += usd_fixed
    not_fixed += usd_not
    fixed += _repair_textures(h_root)
    fixed += ["%s: MetaHuman DNA pointed at %s" % (node, os.path.basename(path))
              for node, path in pipeEnv.fix_dna_paths()]
    return fixed, not_fixed


def _repair_stages(h_root):
    """USD stages Build loaded (spec §4h) whose .usd is missing from the
    publish folder, e.g. after a scratch wipe: pull it (and its textures)
    again and reload the stage. Returns (fixed, not_fixed) messages."""
    fixed, not_fixed = [], []
    for transform, shape, written in usd_stages():
        path = _absolute(written)
        if written and os.path.isfile(path):
            if _repair_stage_layers(transform, shape, path):
                fixed.append("%s: its edit layers were missing; made again (edits not "
                             "saved before are gone)." % transform.split("|")[-1])
            continue
        if not written:
            continue
        name = os.path.basename(path)
        try:
            root, rel = pub.find_film_folder(path)
        except BuildError:
            not_fixed.append("%s: not in a film folder, can't tell where it came from." % name)
            continue
        if not (len(rel) > 3 and rel[1] == "maya" and rel[2] == PUBLISH_FOLDER):
            not_fixed.append("%s: missing, and not a pulled publish (%s)." % (name, path))
            continue
        source = os.path.join(h_root, rel[0], "maya", *rel[3:])
        if not os.path.isfile(source):
            not_fixed.append("%s: not on the H drive either (%s)." % (name, source))
            continue
        copy_usd(source, os.path.join(root, rel[0], "maya"))
        _repair_stage_layers(transform, shape, path)
        file_path = cmds.getAttr(shape + ".filePath")
        cmds.setAttr(shape + ".filePath", "", type="string")    # reload the stage
        cmds.setAttr(shape + ".filePath", file_path, type="string")
        fixed.append("%s: USD pulled again from the H drive and reloaded." % name)
    return fixed, not_fixed


def _repair_stage_layers(transform, shape, source):
    """A stage reading a shot layer (USD_SOURCE_ATTR) whose shot or edit
    layer file is gone (e.g. a scratch wipe): write them again over the
    publish source. True if anything was made."""
    if not (transform and cmds.attributeQuery(USD_SOURCE_ATTR, node=transform, exists=True)
            and cmds.attributeQuery(USD_KEY_ATTR, node=transform, exists=True)):
        return False
    shot_layer = _absolute(cmds.getAttr(shape + ".filePath") or "")
    asset_type, asset, code = cmds.getAttr(transform + "." + USD_KEY_ATTR).split("/")
    published = {"asset_type": asset_type, "asset": asset, "code": code}
    shot_dir = os.path.dirname(os.path.dirname(shot_layer))
    edit = asset_edit_layer_path(maya_dir_of_shot(shot_dir), asset_type, asset, code)
    if os.path.isfile(shot_layer) and os.path.isfile(edit):
        return False
    write_stage_layers(shot_dir, published, source)
    cmds.setAttr(shape + ".filePath", "", type="string")    # reload the stage
    cmds.setAttr(shape + ".filePath", pipeEnv.to_var_path(shot_layer), type="string")
    return True


def _repair_textures(h_root):
    """Pulled publishes the open scene references whose textures are
    missing on scratch (e.g. after a wipe, when a rig's link in the shot
    still had its data): pull them again. Returns messages."""
    fixed = []
    for node, written, full, resolved in scene_references():
        path = resolved if os.path.isfile(resolved) else full
        if not os.path.isfile(path):
            continue
        try:
            root, rel = pub.find_film_folder(path)
        except BuildError:
            continue
        maya_dir = os.path.join(root, rel[0], "maya")
        entry = _linked_entry(root, rel, path)
        if entry:
            local = os.path.join(publish_dir(maya_dir), *entry["shared"].split("/"))
            source = os.path.join(h_root, rel[0], "maya", *entry["shared"].split("/"))
        elif len(rel) > 3 and rel[1] == "maya" and rel[2] == PUBLISH_FOLDER:
            local, source = path, os.path.join(h_root, rel[0], "maya", *rel[3:])
        else:
            continue
        on_h, here = texture_folder_of(source), texture_folder_of(local)
        wanted = [os.path.relpath(os.path.join(d, n), on_h)
                  for d, _, names in os.walk(on_h) for n in names]
        if not os.path.isfile(source) or all(os.path.isfile(os.path.join(here, w))
                                             for w in wanted):
            continue
        copy_published(source, maya_dir)
        if entry:
            link_version(local, path, maya_dir)
        fixed.append("%s: textures pulled again from the H drive." % os.path.basename(path))
    return fixed


def _linked_entry(root, rel, path):
    """The shot's manifest entry whose fixed name is path, or None."""
    if not (len(rel) > 5 and rel[1] == "maya" and rel[2] == "sequences" and rel[5] == "assets"):
        return None
    shot_dir = os.path.join(root, *rel[:5])
    for entry in read_manifest(shot_dir).values():
        if entry.get("link") and pub._same_path(entry_path(shot_dir, entry), path):
            return entry
    return None


# ---------------------------------------------------------------------------
# Shot camera: imported live (not referenced) as camera1, keys connected
# and locked (spec §3i "Cameras": camera and keys are stored separately)
# ---------------------------------------------------------------------------

# Another shot's camera or caches, built into any shot or asset (user,
# 2026-11-12: "we need to be able to get any asset from any shot or
# department if we need it", e.g. a shot camera in an environment to check
# its layout). From Add to list's Shot side: Layout or Animation (whichever
# published the camera, user: "cameras can be published by layout or
# animation"), and Animation's Final caches. Entries carry 'from_shot':
# (sequence, shot). The camera arrives as camera1 in its <shot>_cam_GRP,
# like any shot camera (user, 2026-11-12: "we need to keep the camera name as
# camera1 other wise it breaks my camera viewport switching shortcut"), so
# whatever camera1 was there is renamed camera1_old: one camera1 at a time,
# the last one built. A cache arrives as <shot>_<item>, beside the scene's own.

OTHER_CAMERA_DIR = "assets/camera/shots"        # + /<shot>/cam.ma, camAnim.ma, camAnim.json
CACHE_DEPARTMENT = "anim"                       # caches are Final Animation's


def camera_files(published):
    """{part: path in the shot or asset} for a camera entry: the fixed
    names for the shot's own camera, a folder per shot for another's."""
    shot = (published.get("from_shot") or (None, None))[1]
    if not shot:
        return CAMERA_FILES
    return dict((part, "%s/%s/%s" % (OTHER_CAMERA_DIR, shot, rel.split("/")[-1]))
                for part, rel in CAMERA_FILES.items())


def _camera_published_from(map_path):
    """'layout' or 'anim': the department that published a camera."""
    mapping = _read_json(map_path) or {}
    return mapping.get("published_from") or "layout"


def shot_items(h_root, film, seq, shot, department):
    """What a shot has published for a department, to build into another
    shot or an asset: its camera, with only the versions that department
    published, and for Animation its Final caches (renamed <shot>_<item>
    so they sit beside the scene's own). [] for a department that publishes
    nothing for shots. department None: everything, every camera version
    (a list coming back with what was built)."""
    found = []
    for camera in list_shot_cameras(h_root, film, seq, shot):
        vids = [v for v, f in camera["files"].items()
                if department is None or _camera_published_from(f["map"]) == department]
        if vids:
            found.append(_finish(dict(
                camera, from_shot=(seq, shot),
                versions=dict((v, camera["versions"][v]) for v in vids),
                info=dict((v, camera["info"][v]) for v in vids),
                files=dict((v, camera["files"][v]) for v in vids))))
    if department in (CACHE_DEPARTMENT, None):
        for cache in list_shot_caches(h_root, film, seq, shot):
            found.append(dict(cache, asset="%s_%s" % (shot, cache["asset"]),
                              from_shot=(seq, shot)))
    return found


def _is_shot_dir(path):
    """True for a shot's folder (…\\maya\\sequences\\<seq>\\<shot>)."""
    try:
        _, rel = pub.find_film_folder(path)
    except Exception:
        return False
    return len(rel) >= 3 and rel[1:3] == ["maya", "sequences"]


def build_other_camera(shot_dir, published, vid):
    """Another shot's camera into this shot or asset: pulled into its own
    folder, imported as camera1 in its <shot>_cam_GRP, locked. Whatever
    camera1 the scene had (an asset's own, or the shot's camera) is renamed
    camera1_old first, as when a shot camera is rebuilt: one camera1 at a
    time. Into an asset the timeline takes that shot's range, so the move
    can be scrubbed; a shot keeps its own. Returns (done, warning)."""
    files = camera_files(published)
    shot = published["from_shot"][1]
    key = manifest_key(CAMERA_TYPE, published["asset"], CAMERA_CODE)
    entry = read_manifest(shot_dir).get(key)
    done = []
    files_there = all(os.path.isfile(os.path.join(shot_dir, *r.split("/")))
                      for r in files.values())
    label = version_label(published, vid, mark_latest=False)
    if not entry or entry_version_id(entry) != vid or not files_there:
        pull_camera(shot_dir, published, vid)
        done.append(("updated to %s" if entry else "pulled %s") % label)
    in_asset = not _is_shot_dir(shot_dir)
    current, current_vid = shot_camera(shot)
    if current and current_vid == vid:
        done.append("already up to date")
    else:
        for node in cmds.ls(CAMERA_NAME, long=True, type="transform") or []:
            done.append("existing camera1 renamed %s" % _move_out_of_the_way(node))
        info = published["info"][vid]
        import_camera(shot_dir, info["version"], info["login"], files)
        done.append("camera1 %s (from %s) imported and locked" % (label, shot))
    if in_asset:
        done += apply_camera_range(shot_dir, files)
    return done, None


def pull_camera(shot_dir, published, vid):
    """Copy one camera version's three files into the shot under fixed
    names (another shot's: in its own folder, camera_files) and record it
    in the manifest. Returns the camera file path."""
    if vid not in published["files"]:
        raise BuildError("Camera %s of %s isn't on the H drive."
                         % (vid, published["asset"]))
    files = camera_files(published)
    for part, rel in files.items():
        dest = os.path.join(shot_dir, *rel.split("/"))
        if not os.path.isdir(os.path.dirname(dest)):
            os.makedirs(os.path.dirname(dest))
        if os.path.isfile(dest):
            os.chmod(dest, stat.S_IWRITE)
        shutil.copy2(published["files"][vid][part], dest)
        os.chmod(dest, stat.S_IWRITE)

    key = manifest_key(CAMERA_TYPE, published["asset"], CAMERA_CODE)
    manifest = read_manifest(shot_dir)
    info = published["info"][vid]
    manifest[key] = {
        "version": info["version"],
        "login": info["login"],
        "file": files["camera"],
        "extra_files": [files["keys"], files["map"]],
        "source": published["files"][vid]["camera"],
        "pulled": datetime.now().isoformat(timespec="seconds"),
    }
    if published.get("from_shot"):
        manifest[key]["from_shot"] = list(published["from_shot"])
    _write_manifest(shot_dir, manifest)
    return os.path.join(shot_dir, *files["camera"].split("/"))


def _is_camera_group(node):
    """A published <shot>_cam_GRP: its pipe stamp says department cam."""
    return (cmds.attributeQuery(DEPT_STAMP, node=node, exists=True)
            and cmds.getAttr("%s.%s" % (node, DEPT_STAMP)) == CAMERA_CODE)


def shot_camera(shot=None):
    """The built shot camera in the open scene: (camera1 transform, version
    id) or (None, None). It's camera1 inside a top-level camera group; the
    group's stamp says who published which version. A camera from before
    the group (a top-level camera1) doesn't count, so a rebuild replaces it.
    shot: only that shot's camera (its <shot>_cam_GRP), since another
    shot's can be camera1 too (build_other_camera)."""
    for group in cmds.ls(assemblies=True, long=True) or []:
        camera = "%s|%s" % (group, CAMERA_NAME)
        if shot and group.split("|")[-1] != "%s_cam_GRP" % shot:
            continue
        if _is_camera_group(group) and cmds.objExists(camera):
            return camera, version_id(cmds.getAttr("%s.%s" % (group, BY_STAMP)),
                                      cmds.getAttr("%s.%s" % (group, VERSION_STAMP)))
    return None, None


def _camera_data(transform):
    """The data node(s) driving the camera (camera1_DATA)."""
    shape = cmds.listRelatives(transform, shapes=True, fullPath=True, type="camera") or []
    return sorted(set(n for n in cmds.listConnections([transform] + shape, source=True,
                                                      destination=False, type="transform") or []
                      if n.split("|")[-1].endswith("_DATA")))


def _camera_curves(transform):
    shape = cmds.listRelatives(transform, shapes=True, fullPath=True, type="camera") or []
    curves = set()
    for node in [transform] + shape + _camera_data(transform):
        curves.update(cmds.listConnections(node, source=True, destination=False,
                                           type="animCurve") or [])
    return sorted(curves)


def set_camera_locked(transform, locked):
    """Lock (or unlock) the camera so its keys can't be edited by accident:
    the channels of the camera, its data node and group, the curves' key
    data (so the Graph Editor can't move keys either) and the curve nodes
    themselves (so they can't be deleted)."""
    shape = cmds.listRelatives(transform, shapes=True, fullPath=True, type="camera")[0]
    curves = _camera_curves(transform)
    group = (cmds.listRelatives(transform, parent=True, fullPath=True) or [None])[0]
    nodes = [transform, shape] + _camera_data(transform)
    if group and _is_camera_group(group):
        nodes.append(group)
    for curve in curves:
        cmds.lockNode(curve, lock=False)
    for node in nodes:
        for attr in cmds.listAttr(node, keyable=True) or []:
            try:
                cmds.setAttr("%s.%s" % (node, attr), lock=locked)
            except RuntimeError:
                pass    # compound children etc.
    for curve in curves:
        for attr in CURVE_KEY_ATTRS:
            if cmds.attributeQuery(attr, node=curve, exists=True):
                cmds.setAttr("%s.%s" % (curve, attr), lock=locked)
        if locked:
            cmds.lockNode(curve, lock=True)


def _free_name(name):
    """name, or name1, name2, ... whichever no node in the scene uses. Maya
    allows the same short name under different parents (e.g. inside a
    camera group), but then names stop being unique."""
    candidate, i = name, 1
    while cmds.objExists(candidate):
        candidate, i = "%s%d" % (name, i), i + 1
    return candidate


def _move_out_of_the_way(node):
    """Rename an existing camera1 (and its shape, data node, camera group
    and our curves) to camera1_old, camera1_old1, ... Nothing is deleted.
    Returns the new name."""
    curves = _camera_curves(node)
    data = _camera_data(node)
    group = (cmds.listRelatives(node, parent=True, fullPath=True) or [None])[0]
    for curve in curves:
        cmds.lockNode(curve, lock=False)
    new = cmds.rename(node, _free_name(OLD_CAMERA_NAME))
    for shape in cmds.listRelatives(new, shapes=True, fullPath=True) or []:
        cmds.rename(shape, new.split("|")[-1] + "Shape")
    for d in data:
        cmds.rename(d, new.split("|")[-1] + "_DATA")
    if group and _is_camera_group(group):
        cmds.rename(group, _free_name(group.split("|")[-1] + "_old"))
    prefix = CAMERA_NAME + "_"
    for curve in curves:
        if curve.startswith(prefix):
            curve = cmds.rename(curve, new.split("|")[-1] + "_" + curve[len(prefix):])
        if cmds.getAttr(curve + ".ktv", lock=True):
            cmds.lockNode(curve, lock=True)     # it was protected; keep it so
    return new.split("|")[-1]


def _import_into_root(path, prefix):
    """Import a file through a temporary namespace (so its names can't
    clash with what's in the scene), then move everything to the root.
    Returns {name in the file: node now in the scene}."""
    ns = prefix
    i = 1
    while cmds.namespace(exists=":" + ns):
        ns, i = "%s%d" % (prefix, i), i + 1
    new = cmds.file(path, i=True, type="mayaAscii", namespace=ns,
                    returnNewNodes=True, preserveReferences=False) or []
    found = dict((n.split("|")[-1].split(":")[-1], n) for n in new if cmds.objExists(n))
    return ns, found


def _drop_namespace(ns):
    if cmds.namespace(exists=":" + ns):
        cmds.namespace(removeNamespace=":" + ns, mergeNamespaceWithRoot=True)


def import_camera(shot_dir, version, login, files=None):
    """Import the pulled camera group live (<shot>_cam_GRP > camera1 +
    camera1_DATA), connect its keys to the data node and lock it. The
    camera is driven 1:1 by the data node, so it behaves like a referenced
    camera with no reference path (user, 2026-10-20). The group's pipe
    stamp says which version it is. files: another shot's camera
    (camera_files). Returns camera1's transform."""
    files = files or CAMERA_FILES
    cam_path = os.path.join(shot_dir, *files["camera"].split("/"))
    keys_path = os.path.join(shot_dir, *files["keys"].split("/"))
    with open(os.path.join(shot_dir, *files["map"].split("/")), "r") as f:
        mapping = json.load(f)
    if mapping.get("format") != CAMERA_MAP_FORMAT:
        raise BuildError("This camera was published before cameras had a group. "
                         "Republish it from the layout scene.")
    group_name = mapping["group"]
    if cmds.objExists("|" + group_name):    # not our camera group, or one with no camera1
        cmds.rename("|" + group_name, _free_name(group_name + "_old"))

    ns, nodes = _import_into_root(cam_path, "buildCam")
    missing = [n for n in (group_name, mapping["camera"], mapping["data"]) if n not in nodes]
    if missing:
        raise BuildError("The camera file is missing %s: %s" % (", ".join(missing), cam_path))
    cmds.rename(nodes[mapping["data"]], ":" + DATA_NAME)
    transform = cmds.rename(nodes[mapping["camera"]], ":" + CAMERA_NAME)
    shape = cmds.listRelatives(transform, shapes=True, fullPath=True, type="camera")[0]
    cmds.rename(shape, ":" + CAMERA_NAME.replace("camera", "cameraShape"))
    group = cmds.rename(cmds.listRelatives(transform, parent=True, fullPath=True)[0],
                        ":" + group_name)
    _drop_namespace(ns)
    group = cmds.ls(group, long=True)[0]
    transform = "%s|%s" % (group, CAMERA_NAME)
    data = "%s|%s" % (group, DATA_NAME)

    ns, curves = _import_into_root(keys_path, "buildCamKeys")
    for curve, attr in mapping["curves"].items():
        if curve not in curves:
            raise BuildError("The keys file is missing curve %s." % curve)
        cmds.setAttr("%s.%s" % (data, attr), lock=False)
        cmds.connectAttr(curves[curve] + ".output", "%s.%s" % (data, attr), force=True)
        cmds.rename(curves[curve], ":%s_%s" % (DATA_NAME, attr))
    _drop_namespace(ns)
    set_camera_locked(transform, True)
    return transform


def build_camera(shot_dir, published, vid):
    """One click for the shot camera: pull (or update), then import it live
    as camera1 with its keys, locked. An existing camera1 is renamed
    camera1_old first. Another shot's camera: build_other_camera.
    Returns (done, warning)."""
    if published.get("from_shot"):
        return build_other_camera(shot_dir, published, vid)
    key = manifest_key(CAMERA_TYPE, published["asset"], CAMERA_CODE)
    entry = read_manifest(shot_dir).get(key)
    done = []
    files_there = all(os.path.isfile(os.path.join(shot_dir, *r.split("/")))
                      for r in CAMERA_FILES.values())
    label = version_label(published, vid, mark_latest=False)
    if not entry or entry_version_id(entry) != vid or not files_there:
        pull_camera(shot_dir, published, vid)
        done.append(("updated to %s" if entry else "pulled %s") % label)

    current, current_vid = shot_camera(published["asset"])
    if current and current_vid == vid:
        done.append("already up to date")
        done += apply_camera_range(shot_dir)
        return done, None

    # Cameras used to be referenced: turn an old reference into live nodes
    # so it can be moved aside like any other camera1.
    cam_path = os.path.join(shot_dir, *CAMERA_FILES["camera"].split("/"))
    for ref_node in referenced_nodes(cam_path):
        cams = [cmds.listRelatives(n, parent=True, fullPath=True)[0]
                for n in cmds.referenceQuery(ref_node, nodes=True, dagPath=True) or []
                if cmds.nodeType(n) == "camera"]
        cmds.file(cmds.referenceQuery(ref_node, filename=True), importReference=True)
        for node in cmds.ls(cams, long=True):
            done.append("old referenced camera %s made live and renamed %s"
                        % (node.split("|")[-1], _move_out_of_the_way(node)))
    # Any existing camera1 (an older build in its group, one from before
    # camera groups, or the student's own) is kept, renamed out of the way.
    for node in cmds.ls(CAMERA_NAME, long=True, type="transform") or []:
        done.append("existing camera1 renamed %s" % _move_out_of_the_way(node))
    info = published["info"][vid]
    import_camera(shot_dir, info["version"], info["login"])
    done.append("camera1 %s imported and locked" % label)
    done += apply_camera_range(shot_dir)
    return done, None


def apply_camera_range(shot_dir, files=None):
    """The shot's frame range is the one its camera was published with
    (the map's start/end): set the playback and animation range to it
    (user, 2026-10-26: SEQ010_160 built without its range). files: another
    shot's camera (camera_files). Returns what was done, as lines."""
    try:
        with open(os.path.join(shot_dir, *(files or CAMERA_FILES)["map"].split("/")), "r") as f:
            mapping = json.load(f)
        start, end = int(mapping["start"]), int(mapping["end"])
    except (IOError, OSError, ValueError, KeyError, TypeError):
        return []
    current = (cmds.playbackOptions(query=True, minTime=True),
               cmds.playbackOptions(query=True, maxTime=True),
               cmds.playbackOptions(query=True, animationStartTime=True),
               cmds.playbackOptions(query=True, animationEndTime=True))
    if current == (start, end, start, end):
        return []
    cmds.playbackOptions(minTime=start, maxTime=end,
                         animationStartTime=start, animationEndTime=end)
    return ["frame range set to %d-%d, from the camera publish" % (start, end)]


# ---------------------------------------------------------------------------
# Shot keys (spec §4 item 7 "Build Shot pulling animation back in", DECIDED
# 2026-10-23): a Layout or Animation publish writes each item's keys (a .ma
# of curves + a .json map) to the shot's scenes\<layout|anim>\<login>\ on
# the H drive (scenes\<login>\ before 2026-11-23).
# Build puts an asset's keys back on that same asset (Scout's keys on Scout
# only), from the Keys column on its row. Layout and anim keys are one list,
# newest by publish time; the rig version is picked separately, and keys
# made on another rig version go on anyway, with what didn't match listed.
# ---------------------------------------------------------------------------

KEY_CODES = ("layout", "anim")
KEYS_RE = re.compile(r"_(?P<code>layout|anim)_v(?P<version>\d{3})\.json$", re.IGNORECASE)
TIME_CURVES = ("animCurveTL", "animCurveTA", "animCurveTU", "animCurveTT")
KEYS_RECORD = "pipe_keys"       # fileInfo: which keys Build put on each asset
KEEP_KEYS = "keep"              # leave the scene's keys alone (e.g. keyed by hand)
NO_KEYS = "none"                # no keys: the asset at its default pose


def keys_id(shot, login, code, version):
    return "%s/%s/%s/v%03d" % (shot, login, code, version)


def parse_keys_id(kid):
    """(shot, login, code, version) from a keys id."""
    shot, login, code, version = kid.split("/")
    return shot, login, code, int(version[1:])


def list_shot_keys(h_root, film, seq, shot):
    """{asset's manifest key: {keys id: info}} for every asset keys publish
    in the shot on the H drive, everyone's. info: {shot, login, code,
    version, time, keys, map, made_on}, made_on being the asset version the
    keys were published from ({version, artistId}). Items made in the shot
    (no pipe stamp) and the camera are left out."""
    scenes = os.path.join(shot_folder(h_root, film, seq, shot), "scenes")
    found = {}
    for dirpath, filenames in _walk_shot_publishes(scenes):
        login = os.path.basename(dirpath).lower()
        for name in filenames:
            m = KEYS_RE.search(name)
            if not m or not name.lower().startswith(("%s_%s_" % (shot, login)).lower()):
                continue
            path = os.path.join(dirpath, name)
            keys = path[:-len(".json")] + ".ma"
            try:
                with open(path, "r") as f:
                    data = json.load(f)
            except (IOError, OSError, ValueError):
                continue
            asset = data.get("asset") or {}
            # Keys, or only unkeyed settings (an asset placed, never keyed).
            if not (((os.path.isfile(keys) and data.get("curves")) or data.get("settings"))
                    and asset.get("asset") and asset.get("assetType")
                    and asset.get("department")):
                continue
            code, version = m.group("code").lower(), int(m.group("version"))
            key = manifest_key(asset["assetType"], asset["asset"], asset["department"])
            found.setdefault(key, {})[keys_id(shot, login, code, version)] = {
                "shot": shot, "login": login, "code": code, "version": version,
                "time": publish_time(path), "keys": keys, "map": path,
                "made_on": {"version": asset.get("version"),
                            "artistId": asset.get("artistId")}}
    return found


def keys_label(kid, info=None, this_shot=None, latest=None):
    """'v005 anim (scout)', plus the shot when it isn't this one and
    '  (latest)' for the newest."""
    if kid == KEEP_KEYS:
        return "Keep scene's keys"
    if kid == NO_KEYS:
        return "None (no keys)"
    shot, login, code, version = parse_keys_id(kid)
    text = "v%03d %s (%s)" % (version, code, login)
    if this_shot and shot.lower() != this_shot.lower():
        text += "  from %s" % shot
    if latest and kid == latest:
        text += "  (latest)"
    return text


def sorted_keys(keys):
    """Keys ids of {kid: info}, newest publish first."""
    return sorted(keys, key=lambda k: keys[k]["time"], reverse=True)


def keys_record():
    """{asset's manifest key: keys id} that Build put on each asset in the
    open scene (saved with the scene)."""
    raw = cmds.fileInfo(KEYS_RECORD, query=True) or []
    record = {}
    for pair in (raw[0] if raw else "").split("|"):
        if "=" in pair:
            key, kid = pair.split("=", 1)
            record[key] = kid
    return record


def _set_keys_record(key, kid):
    record = keys_record()
    record[key] = kid
    cmds.fileInfo(KEYS_RECORD, "|".join("%s=%s" % kv for kv in sorted(record.items())))


def keys_in_scene(published):
    """The keys id Build last put on this asset in the open scene (or
    NO_KEYS), or None if Build hasn't put keys on it."""
    return keys_record().get(manifest_key(published["asset_type"], published["asset"],
                                          published["code"]))


def asset_namespace(shot_dir, published):
    """The namespace the asset is referenced under in the open scene, or
    None if it isn't there."""
    entry = read_manifest(shot_dir).get(manifest_key(
        published["asset_type"], published["asset"], published["code"]))
    nodes = referenced_nodes(entry_path(shot_dir, entry)) if entry else []
    nodes = nodes or any_version_references(shot_dir, published)
    if nodes:
        return cmds.referenceQuery(nodes[0], namespace=True).lstrip(":")
    namespace = namespace_for(published["asset"], published["code"])
    return namespace if cmds.namespace(exists=":" + namespace) else None


def _namespace_nodes(namespace):
    """{short name without namespaces: node} for everything in the
    namespace, nested namespaces included (the keys map keeps short names)."""
    nodes = cmds.namespaceInfo(":" + namespace, listOnlyDependencyNodes=True,
                               recurse=True, dagPath=True) or []
    found = {}
    for node in nodes:
        found.setdefault(node.split("|")[-1].split(":")[-1], node)
    return found


def _keys_on(namespace):
    """The animator's keys on the asset: time curves feeding its nodes
    straight in, not from the referenced file (driven keys belong to the rig)."""
    curves = set()
    for node in _namespace_nodes(namespace).values():
        for curve in cmds.listConnections(node, source=True, destination=False,
                                          type="animCurve") or []:
            if (cmds.nodeType(curve) in TIME_CURVES
                    and not cmds.referenceQuery(curve, isNodeReferenced=True)):
                curves.add(curve)
    return sorted(curves)


def clear_keys(namespace):
    """Delete the asset's keys. Returns how many curves went."""
    curves = _keys_on(namespace)
    for curve in curves:
        cmds.lockNode(curve, lock=False)
    if curves:
        cmds.delete(curves)
    return len(curves)


def apply_settings(targets, settings):
    """Set the published unkeyed settings ({node name: {attr: value}}) on
    the asset's nodes ({name: node}). A setting whose control or channel
    isn't on this rig, or can't be set (locked, driven, keyed), is left out.
    Returns (settings applied, [what didn't match])."""
    applied, unmatched = 0, []
    for node_name, attrs in sorted(settings.items()):
        node = targets.get(node_name)
        if not node:
            unmatched.append("%s (%d settings)" % (node_name, len(attrs)))
            continue
        for attr, value in sorted(attrs.items()):
            plug = "%s.%s" % (node, attr)
            try:
                if (cmds.connectionInfo(plug, isDestination=True)
                        or not cmds.getAttr(plug, settable=True)):
                    unmatched.append("%s.%s (locked or driven)" % (node_name, attr))
                    continue
                cmds.setAttr(plug, value)
            except (RuntimeError, ValueError, TypeError):
                unmatched.append("%s.%s" % (node_name, attr))
                continue
            applied += 1
    return applied, unmatched


def apply_keys(namespace, info):
    """Replace the asset's keys with a published set: import its curves,
    delete the keys already on the asset, then connect each curve to the
    same control and channel by name, on the frames it was published on,
    and set its unkeyed settings. Curves whose control or channel isn't on
    this rig (or is locked) are left out. Returns (curves applied,
    settings applied, [controls that didn't match])."""
    with open(info["map"], "r") as f:
        data = json.load(f)
    mapping = data.get("curves") or {}
    ns, curves = (_import_into_root(info["keys"], "buildKeys") if mapping
                  else (None, {}))
    applied, unmatched = 0, []
    try:
        clear_keys(namespace)
        targets = _namespace_nodes(namespace)
        for curve, (node_name, attr) in sorted(mapping.items()):
            new = curves.get(curve)
            if not new:
                unmatched.append("%s.%s (missing from the keys file)" % (node_name, attr))
                continue
            node = targets.get(node_name)
            plug = "%s.%s" % (node, attr)
            if not node or not cmds.attributeQuery(attr.split("[")[0], node=node, exists=True):
                unmatched.append("%s.%s" % (node_name, attr))
                cmds.delete(new)
                continue
            if cmds.getAttr(plug, lock=True):
                unmatched.append("%s.%s (locked)" % (node_name, attr))
                cmds.delete(new)
                continue
            cmds.connectAttr(new + ".output", plug, force=True)
            cmds.rename(new, ":%s_%s_%s" % (namespace.replace(":", "_"), node_name, attr))
            applied += 1
        set_count, set_unmatched = apply_settings(targets, data.get("settings") or {})
        unmatched += set_unmatched
    finally:
        if ns:
            _drop_namespace(ns)
    return applied, set_count, unmatched


def build_keys(shot_dir, published, kid, info=None):
    """Put the chosen keys on an asset that's in the open scene: kid a keys
    id (info from list_shot_keys) or NO_KEYS. Whatever keys the asset had
    are replaced (user, 2026-10-23). Returns (done, warning or None)."""
    namespace = asset_namespace(shot_dir, published)
    if not namespace:
        raise BuildError("%s isn't in this scene, so its keys have nowhere to go."
                         % published["asset"])
    key = manifest_key(published["asset_type"], published["asset"], published["code"])
    if kid == NO_KEYS:
        removed = clear_keys(namespace)
        _set_keys_record(key, NO_KEYS)
        return ["keys removed (%d curves)" % removed], None
    label = keys_label(kid, info, this_shot=os.path.basename(os.path.normpath(shot_dir)))
    applied, settings, unmatched = apply_keys(namespace, info)
    _set_keys_record(key, kid)
    done = ["keys %s on (%d curves%s)" % (
        label, applied, ", %d unkeyed settings" % settings if settings else "")]
    warning = None
    if unmatched:
        made_on = info.get("made_on") or {}
        entry = read_manifest(shot_dir).get(key)
        note = ""
        if entry and made_on.get("version") and (
                made_on.get("version"), (made_on.get("artistId") or "").lower()) != (
                entry["version"], (entry.get("login") or "").lower()):
            note = " (keys made on v%03d (%s), this shot has v%03d (%s))" % (
                made_on["version"], made_on.get("artistId") or "?",
                entry["version"], entry.get("login") or "?")
        shown = unmatched[:8] + (["..."] if len(unmatched) > 8 else [])
        warning = ("keys put on anyway, but %d didn't match this rig%s: %s"
                   % (len(unmatched), note, ", ".join(shown)))
    return done, warning


def free_namespace(namespace):
    """Make sure the clean namespace (e.g. backpack:) can be used. An empty
    leftover namespace is removed; one that still holds nodes is a real
    clash, explained rather than quietly becoming backpack1:."""
    if not cmds.namespace(exists=":" + namespace):
        return
    contents = cmds.namespaceInfo(":" + namespace, listNamespace=True, recurse=True) or []
    if contents:
        raise BuildError(
            "The name '%s:' is already used in this scene by %s.\n"
            "Rename or remove those first, then Build Shot again."
            % (namespace, ", ".join(sorted(contents)[:3]) + (" ..." if len(contents) > 3 else "")))
    cmds.namespace(removeNamespace=":" + namespace)


def use_clean_namespace(path, namespace):
    """If an existing reference to path has a different namespace (e.g.
    backpack1: from before this rule), move it to the clean one when that's
    free. Returns the old namespace if it was changed, else None."""
    for ref_node in referenced_nodes(path):
        current = cmds.referenceQuery(ref_node, namespace=True).lstrip(":")
        if current == namespace:
            continue
        try:
            free_namespace(namespace)
        except BuildError:
            return None     # something else uses the name; leave this one be
        cmds.file(cmds.referenceQuery(ref_node, filename=True), edit=True,
                  namespace=namespace)
        return current
    return None


def reference_into_scene(path, namespace):
    """Reference a pulled file into the open scene under its clean
    namespace. path is normally a $PIPE_SCRATCH path (see pipeEnv), since
    the shared publish folder is outside the shot project."""
    free_namespace(namespace)
    cmds.file(path, reference=True, namespace=namespace, mergeNamespacesOnClash=False)
    return path


def reference_cache(path, namespace):
    """Reference an animation cache (Alembic) into the open scene beside the
    live rig (user, 2026-10-28: Animation builds caches "occasionally to
    compare changes"): its own namespace (scout_cache:) and group
    (scout_cache_GRP), and display type Reference so it shows shaded but
    can't be selected or edited by accident."""
    if not cmds.pluginInfo("AbcImport", query=True, loaded=True):
        cmds.loadPlugin("AbcImport", quiet=True)
    free_namespace(namespace)
    group = namespace + "_GRP"
    cmds.file(path, reference=True, type="Alembic", namespace=namespace,
              mergeNamespacesOnClash=False, groupReference=True, groupName=group)
    group = cmds.ls(group, long=True) or cmds.ls("*:" + group, long=True)
    if group:
        cmds.setAttr(group[0] + ".overrideEnabled", 1)
        cmds.setAttr(group[0] + ".overrideDisplayType", 2)     # Reference
    return path


def placement_node(top):
    """What moves a referenced model: its top group, or, since a pipe group
    is locked at the origin (publishTool_api.finish_pipe_group), its geo
    group (the one artists move, e.g. grassB:geo in SEQ010_120), else its
    first child group."""
    if not cmds.getAttr(top + ".translateX", lock=True):
        return top
    children = cmds.listRelatives(top, children=True, type="transform", fullPath=True) or []
    geo = [c for c in children if c.split("|")[-1].split(":")[-1] == "geo"]
    return (geo or children or [top])[0]


def reference_tops(path):
    """The top-level DAG nodes (long names) a reference to path brought,
    e.g. |grassB:grassB_model_GRP."""
    tops = []
    for ref_node in referenced_nodes(path):
        for node in cmds.referenceQuery(ref_node, nodes=True, dagPath=True) or []:
            node = (cmds.ls(node, long=True) or [node])[0]
            # the pipe group is a dagContainer, a kind of transform
            if node.count("|") == 1 and cmds.objectType(node, isAType="transform"):
                tops.append(node)
    return tops


# ---------------------------------------------------------------------------
# Models as USD (spec §4h, user 2026-11-23: "I was hoping that publishing a
# model as USD would mean loading it as usd in another scene"). A Modeling
# publish with USD ticked writes <name>_exports\<name>.usd beside its .ma
# (publishTool_outputs). Build can load that instead of referencing the .ma:
# the .usd and its textures are pulled into scratch's publish\ (the .ma is
# not), and a USD stage (mayaUsdProxyShape) reads it by its $PIPE_SCRATCH
# path (spec §4f). One asset is either a Maya reference or a USD stage in a
# scene, never both; switching keeps the top group's placement only.
# ---------------------------------------------------------------------------

USD_PLUGIN = "mayaUsdPlugin"
USD_SHAPE = "mayaUsdProxyShape"
USD_CODES = ("model",)              # models and environments (Modeling publishes)
USD_EXTENSIONS = (".usd", ".usda", ".usdc")
USD_TEXTURES = "textures"           # beside the .usd (publishTool_outputs)
USD_STAGE_SUFFIX = "_USD"           # grassB -> grassB_USD (transform), grassB_USDShape
USD_KEY_ATTR = "pipe_buildKey"      # on the stage's transform: its manifest key
USD_GROUP_ATTR = "pipe_usdGroup"    # on the stage's <asset>_model_GRP (usd_group)
USD_RE = re.compile(r"^(?P<asset>.+)_(?P<login>[a-z0-9]+)_(?P<code>[A-Za-z]+)"
                    r"_v(?P<version>\d{3})\.usd[ac]?$", re.IGNORECASE)
EXPORTS_SUFFIX = "_exports"         # publishTool_outputs.FOLDER_SUFFIX


def can_load_usd(published):
    """True for a list entry that can be loaded as USD at all (a model or
    environment; not rigs, cameras or caches)."""
    return published.get("kind") is None and published.get("code") in USD_CODES


def usd_export(path):
    """The .usd a Modeling publish wrote beside path (H drive), or None if
    it was published without USD ticked."""
    if not path:
        return None
    stem = os.path.splitext(os.path.basename(path))[0]
    usd = os.path.join(os.path.dirname(path), stem + EXPORTS_SUFFIX, stem + ".usd")
    return usd if os.path.isfile(usd) else None


def has_usd(published, vid):
    return can_load_usd(published) and bool(usd_export(published["versions"].get(vid)))


def no_usd_message(published, vid):
    return ("%s of %s has no USD: it was published without USD ticked. Publish it "
            "again with USD ticked, or build it as a Maya reference."
            % (version_label(published, vid, mark_latest=False), published["asset"]))


def switch_message(published, to_usd):
    """Why Build stops before swapping an asset between a Maya reference
    and a USD stage, unless asked to (the UI asks first)."""
    if to_usd:
        return ("%s is in this scene as a Maya reference. Loading it as USD removes the "
                "reference (its file stays); the top group's placement is kept, changes "
                "made inside it are lost." % published["asset"])
    return ("%s is in this scene as a USD stage. Building it as a Maya reference "
            "removes the stage; its placement is kept." % published["asset"])


def _folder_files(folder):
    return [os.path.join(d, n) for d, _, names in os.walk(folder) for n in names]


def usd_files(usd):
    """The .usd plus everything it needs (spec §4f item 5: Build pulls the
    whole chain), found with UsdUtils.ComputeAllDependencies: (files,
    unresolved). Only files inside the .usd's own film folder count (§4f
    item 4); anything else is reported as unresolved."""
    load_usd_plugin()
    from pxr import Sdf, UsdUtils
    layers, assets, unresolved = UsdUtils.ComputeAllDependencies(
        Sdf.AssetPath(usd.replace("\\", "/")))
    try:
        root, rel = pub.find_film_folder(usd)
        film_root = os.path.join(root, rel[0])
    except BuildError:
        film_root = os.path.dirname(usd)
    files, missing = [usd], [str(p) for p in unresolved]
    for path in [layer.realPath for layer in layers] + [str(a) for a in assets]:
        path = os.path.normpath(path)
        if pub._same_path(path, usd) or path in files:
            continue
        if os.path.normcase(path).startswith(os.path.normcase(film_root) + os.sep):
            files.append(path)
        else:
            missing.append(path)
    return files, missing


def copy_usd(source, maya_dir):
    """Copy a published .usd and its dependencies (textures) from the H
    drive into the shared publish folder at the same paths, read-only, like
    copy_published. Returns (dest, copied)."""
    dest = os.path.join(publish_dir(maya_dir), *_maya_rel(source).split("/"))
    files, _ = usd_files(source)
    for path in files[1:]:
        _copy_if_changed(path, os.path.join(publish_dir(maya_dir), *_maya_rel(path).split("/")))
    return dest, _copy_if_changed(source, dest)


def load_usd_plugin():
    if not cmds.pluginInfo(USD_PLUGIN, query=True, loaded=True):
        cmds.loadPlugin(USD_PLUGIN, quiet=True)


# ---------------------------------------------------------------------------
# Edit layers (spec §4i, user 2026-11-24: "edit a shot or an asset and pass
# that from the shot back to the asset"). A stage doesn't read the
# published .usd directly: it reads the scene's own shot layer, which
# sublayers the asset's edit layer, which sits over the published file:
#
#   <scene's project>\usd\<asset>_<code>.usda              edits for this shot
#     sublayer  <maya>\assets\<type>\<asset>\usd\<asset>_<code>_edit.usda
#                                                          edits for the asset (every shot)
#     sublayer  <maya>\publish\...\<name>.usd              the publish, never edited
#
# Sublayers (not a reference) keep prim paths the same in all three, so the
# USD Edit tool (modelTool_usdEdit) only switches which layer is the edit
# target. Paths inside the layers are relative (spec §4f). All on scratch:
# unpublished work, the student's job (PIPE_RULES 7). The published .usd
# the stage uses is stamped on its transform (USD_SOURCE_ATTR).
# ---------------------------------------------------------------------------

USD_LAYER_FOLDER = "usd"
USD_EDIT_SUFFIX = "_edit"
USD_SOURCE_ATTR = "pipe_usdSource"      # on the stage's transform: the publish, as a var path
USD_LAYER_KEY = "pipe"                  # customLayerData key on the layers Build writes


def shot_layer_path(shot_dir, published):
    return os.path.join(shot_dir, USD_LAYER_FOLDER,
                        "%s_%s.usda" % (published["asset"], published["code"]))


def asset_edit_layer_path(maya_dir, asset_type, asset, code):
    return os.path.join(maya_dir, "assets", asset_type, asset, USD_LAYER_FOLDER,
                        "%s_%s%s.usda" % (asset, code, USD_EDIT_SUFFIX))


def _rel_layer_path(from_layer, to_file):
    rel = os.path.relpath(to_file, os.path.dirname(from_layer)).replace("\\", "/")
    return rel if rel.startswith(".") else "./" + rel


def _open_or_create_layer(path, role, **info):
    from pxr import Sdf
    layer = Sdf.Layer.FindOrOpen(path.replace("\\", "/"))
    if layer is None:
        folder = os.path.dirname(path)
        if not os.path.isdir(folder):
            os.makedirs(folder)
        layer = Sdf.Layer.CreateNew(path.replace("\\", "/"))
    data = dict(layer.customLayerData)
    stamp = dict(data.get(USD_LAYER_KEY) or {})
    stamp.update(dict(info, role=role))
    data[USD_LAYER_KEY] = stamp
    layer.customLayerData = data
    return layer


def write_stage_layers(shot_dir, published, source):
    """Make (or update) the shot layer and the asset's edit layer for a
    stage reading the pulled publish source. Edits already in either layer
    are kept; only the shot layer's sublayers change. Returns the shot
    layer's path."""
    load_usd_plugin()
    from pxr import Sdf
    maya_dir = maya_dir_of_shot(shot_dir)
    shot_path = shot_layer_path(shot_dir, published)
    edit_path = asset_edit_layer_path(maya_dir, published["asset_type"], published["asset"],
                                      published["code"])
    src = Sdf.Layer.FindOrOpen(source.replace("\\", "/"))
    default = src.defaultPrim if src else ""
    edit = _open_or_create_layer(edit_path, "asset", asset=published["asset"],
                                 code=published["code"])
    if default:
        edit.defaultPrim = default
    edit.Save()
    shot = _open_or_create_layer(shot_path, "shot", asset=published["asset"],
                                 code=published["code"])
    subs = [_rel_layer_path(shot_path, edit_path), _rel_layer_path(shot_path, source)]
    if list(shot.subLayerPaths) != subs:
        del shot.subLayerPaths[:]
        for sub in subs:
            shot.subLayerPaths.append(sub)
    if default:
        shot.defaultPrim = default
    shot.Save()
    return shot_path


def stage_layers(shape):
    """{'shot', 'asset', 'published'}: the Sdf layers of a stage Build
    loaded (None where it has no such layer, e.g. a stage loaded before
    edit layers, which reads the publish directly)."""
    import mayaUsd.ufe
    from pxr import Sdf
    stage = mayaUsd.ufe.getStage(cmds.ls(shape, long=True)[0])
    found = {"shot": None, "asset": None, "published": None}
    if stage is None:
        return found
    root = stage.GetRootLayer()
    role = (root.customLayerData.get(USD_LAYER_KEY) or {}).get("role")
    if role != "shot":
        found["published"] = root
        return found
    found["shot"] = root
    for sub in root.subLayerPaths:
        layer = Sdf.Layer.FindOrOpen(root.ComputeAbsolutePath(sub))
        if layer is None:
            continue
        if (layer.customLayerData.get(USD_LAYER_KEY) or {}).get("role") == "asset":
            found["asset"] = layer
        elif found["published"] is None:
            found["published"] = layer
    return found


def usd_stages():
    """[(transform, shape, published .usd as written)] for every USD stage
    in the open scene (long names). Written: the publish the stage reads,
    as the scene stores it (a $PIPE_SCRATCH path): its transform's
    USD_SOURCE_ATTR, or for a stage from before edit layers, its file."""
    if not cmds.pluginInfo(USD_PLUGIN, query=True, loaded=True):
        return []
    found = []
    for shape in cmds.ls(type=USD_SHAPE, long=True) or []:
        parent = (cmds.listRelatives(shape, parent=True, fullPath=True) or [None])[0]
        if parent and cmds.attributeQuery(USD_SOURCE_ATTR, node=parent, exists=True):
            written = cmds.getAttr(parent + "." + USD_SOURCE_ATTR) or ""
        else:
            written = cmds.getAttr(shape + ".filePath") or ""
        found.append((parent, shape, written))
    return found


def set_stage_source(transform, shape, shot_layer, source_var):
    """Point a stage at its shot layer and stamp the publish it reads."""
    if not cmds.attributeQuery(USD_SOURCE_ATTR, node=transform, exists=True):
        cmds.addAttr(transform, longName=USD_SOURCE_ATTR, dataType="string")
    cmds.setAttr(transform + "." + USD_SOURCE_ATTR, source_var, type="string")
    file_path = pipeEnv.to_var_path(shot_layer)
    if cmds.getAttr(shape + ".filePath") != file_path:
        cmds.setAttr(shape + ".filePath", file_path, type="string")


def stage_of(published):
    """(transform, shape, file path as written) of the USD stage Build
    loaded for this asset, or None."""
    if not can_load_usd(published):
        return None
    key = manifest_key(published["asset_type"], published["asset"], published["code"])
    for transform, shape, written in usd_stages():
        if (transform and cmds.attributeQuery(USD_KEY_ATTR, node=transform, exists=True)
                and cmds.getAttr(transform + "." + USD_KEY_ATTR) == key):
            return transform, shape, written
    return None


def make_stage(name, key, file_path, group_name):
    """A USD stage reading file_path: <name>_USD with its shape, driven by
    the scene's time, stamped with the asset's manifest key, in its pipe
    group (usd_group). Maya draws its proxy purpose (if the model has one)
    and renders the render purpose. Returns the stage's transform."""
    load_usd_plugin()
    transform = cmds.createNode("transform", name=name + USD_STAGE_SUFFIX)
    shape = cmds.createNode(USD_SHAPE, name=transform + "Shape", parent=transform)
    cmds.connectAttr("time1.outTime", shape + ".time")
    cmds.setAttr(shape + ".filePath", file_path, type="string")
    cmds.addAttr(transform, longName=USD_KEY_ATTR, dataType="string")
    cmds.setAttr(transform + "." + USD_KEY_ATTR, key, type="string")
    return usd_group(cmds.ls(transform, long=True)[0], group_name)


def usd_group(transform, group_name):
    """Put a stage in its pipe group, <asset>_model_GRP (user 2026-11-24):
    a dagContainer with the pipe icon, locked at the origin like a
    published model's top group, so the Outliner shows it came through the
    pipe. Presentation only: no pipe stamp, the stage under it stays a
    plain USD stage (it moves; the group doesn't). Stages loaded before
    this get their group the next time Build touches them. Returns the
    stage transform's new path."""
    parent = (cmds.listRelatives(transform, parent=True, fullPath=True) or [None])[0]
    if parent and cmds.attributeQuery(USD_GROUP_ATTR, node=parent, exists=True):
        return transform
    matrix = cmds.xform(transform, query=True, worldSpace=True, matrix=True)
    group = pub.make_pipe_group(group_name)
    cmds.addAttr(group, longName=USD_GROUP_ATTR, attributeType="bool", defaultValue=True)
    pub.finish_pipe_group(group)
    transform = cmds.parent(transform, group)[0]
    transform = cmds.ls(cmds.ls(transform, uuid=True)[0], long=True)[0]
    cmds.xform(transform, worldSpace=True, matrix=matrix)
    return transform


def remove_stage(transform):
    """Delete a stage and its pipe group (if nothing else was put in it)."""
    parent = (cmds.listRelatives(transform, parent=True, fullPath=True) or [None])[0]
    cmds.delete(transform)
    if parent and cmds.attributeQuery(USD_GROUP_ATTR, node=parent, exists=True) \
            and not cmds.listRelatives(parent, children=True):
        pub.delete_pipe_group(parent)


def _maya_references_of(shot_dir, published, entry):
    """Reference nodes in the open scene for this asset, whichever version
    or old path."""
    nodes = []
    paths = _old_paths(shot_dir, published, entry if entry and not entry.get("usd") else None)
    for node in [n for p in paths for n in referenced_nodes(p)] + \
            any_version_references(shot_dir, published):
        if node not in nodes:
            nodes.append(node)
    return nodes


def _build_usd(shot_dir, published, vid, replace=False):
    """Load the chosen version's USD export as a USD stage in the open
    scene (spec §4h): pulled into the publish folder, read by $PIPE_SCRATCH
    path. A stage Build loaded before is pointed at the new version. The
    asset referenced as a Maya file: refused unless replace, which removes
    the reference and puts the stage where its top group was.
    Returns (done, warning, replaced) like _build_asset."""
    if not can_load_usd(published):
        raise BuildError("Only models and environments can be loaded as USD.")
    if vid not in published["versions"]:
        raise BuildError("%s of %s %s isn't on the H drive."
                         % (vid, published["asset"], published["code"]))
    if not usd_export(published["versions"][vid]):
        raise BuildError(no_usd_message(published, vid))
    load_usd_plugin()
    key = manifest_key(published["asset_type"], published["asset"], published["code"])
    entry = read_manifest(shot_dir).get(key)
    refs = _maya_references_of(shot_dir, published, entry)
    if refs and not replace:
        raise BuildError(switch_message(published, to_usd=True))
    previous = shared_path(shot_dir, entry) if entry else None
    label = version_label(published, vid, mark_latest=False)
    stage = stage_of(published)
    dest = pull(shot_dir, published, vid, usd=True)
    pipeEnv.set_from_path(shot_dir)
    file_path = pipeEnv.to_var_path(dest)
    shot_layer = write_stage_layers(shot_dir, published, dest)
    done = []
    if stage:
        transform, shape, written = stage
        transform = usd_group(transform, pub.pipe_group_name(published["asset"],
                                                             published["code"]))
        shape = (cmds.listRelatives(transform, shapes=True, fullPath=True) or [shape])[0]
        set_stage_source(transform, shape, shot_layer, file_path)
        if written != file_path:
            m = USD_RE.match(os.path.basename(_absolute(written)))
            done.append("%s -> %s" % ("v%s" % m.group("version") if m else "USD", label))
        else:
            done.append("already up to date")
    else:
        placement = None
        if refs:
            tops = []
            for node in refs:
                path = _absolute(written_path(node))
                tops += reference_tops(path) if path else []
            if tops:
                placement = cmds.xform(placement_node(tops[0]), query=True, worldSpace=True,
                                       matrix=True)
            for node in refs:
                cmds.file(referenceNode=node, removeReference=True)
            done.append("Maya reference removed")
        transform = make_stage(namespace_for(published["asset"], published["code"]), key,
                               pipeEnv.to_var_path(shot_layer),
                               pub.pipe_group_name(published["asset"], published["code"]))
        set_stage_source(transform, cmds.listRelatives(transform, shapes=True, fullPath=True)[0],
                         shot_layer, file_path)
        if placement:
            cmds.xform(transform, worldSpace=True, matrix=placement)
        done.append("%s loaded as a USD stage (%s)" % (label, transform.split("|")[-1]))
    _, missing = usd_files(dest)
    warning = ("these files it needs weren't found: %s" % ", ".join(
        os.path.basename(m) for m in missing)) if missing else None
    replaced = previous if previous and not pub._same_path(previous, dest) else None
    return done, warning, replaced


# ---------------------------------------------------------------------------
# Shaders on caches (spec §4 "Shaders on caches, automatic", user
# 2026-10-28): an Alembic carries no shaders, so Build puts back the look
# of the asset version the cache came from (publishTool_look writes it with
# every rig and model publish). Which look depends on the department
# building: Layout and Animation get the rig's (or model's) look, what the
# animator saw; Lighting gets the asset's newest LookDev look, or the rig's
# if LookDev hasn't published one.
# ---------------------------------------------------------------------------

LOOK_SUFFIX = "_look"
LOOK_ATTR = "pipe_look"         # on the cache group: the look file it wears


def _published_source(h_root, film, stamp):
    """The H-drive publish an asset stamp names, or None."""
    login, version = stamp.get("artistId"), stamp.get("version")
    if not (stamp.get("assetType") and stamp.get("asset") and stamp.get("department")
            and login and version):
        return None
    scenes = os.path.join(asset_folder(h_root, film, stamp["assetType"], stamp["asset"]),
                          "scenes")
    # scenes\<dept>\<login>\ (spec §4g), then the old scenes\<login>\.
    folders = [os.path.join(scenes, stamp["department"], login), os.path.join(scenes, login)]
    for folder in folders:
        for ext in (".ma", ".mb"):
            path = os.path.join(folder, pub.published_name(stamp["asset"], login,
                                                           stamp["department"], version, ext))
            if os.path.isfile(path):
                return path
    return None


def _look_of(path):
    """(look .ma, look .json) of a published file, or None if it has none."""
    stem = os.path.splitext(path)[0] + LOOK_SUFFIX
    files = (stem + ".ma", stem + ".json")
    return files if all(os.path.isfile(f) for f in files) else None


def look_for_cache(h_root, film, info, department=None):
    """(look .ma, look .json, the publish it belongs to) for a cache's
    .json info, or None (made in the shot, or published without a look).
    Lighting: the asset's newest LookDev publish with a look first."""
    stamp = info.get("asset") or {}
    if department == "lighting" and stamp.get("asset"):
        lookdev = [p for p in list_published(h_root, film)
                   if (p["asset_type"], p["asset"], p["code"])
                   == (stamp.get("assetType"), stamp["asset"], "lookDev")]
        for p in lookdev:
            for vid in sorted_versions(p):
                look = _look_of(p["versions"][vid])
                if look:
                    return look + (p["versions"][vid],)
    source = _published_source(h_root, film, stamp)
    look = _look_of(source) if source else None
    return look + (source,) if look else None


def _pull_textures(source, maya_dir):
    """The textures published with source, into the shared publish folder
    (where the look's $PIPE_SCRATCH paths point), without the file itself."""
    dest = os.path.join(publish_dir(maya_dir), *_maya_rel(source).split("/"))
    textures = texture_folder_of(source)
    for dirpath, _, filenames in os.walk(textures):
        for name in filenames:
            src = os.path.join(dirpath, name)
            _copy_if_changed(src, os.path.join(texture_folder_of(dest),
                                               os.path.relpath(src, textures)))


def _parts(path):
    return [p.split(":")[-1] for p in path.split("|") if p]


def _match_meshes(group, paths):
    """{published path: cache transform} by name: the cache transform whose
    path below the cache group (namespaces off) ends the published path.
    The longest match wins, so two body_geo in different groups stay apart."""
    transforms = set()
    for shape in cmds.listRelatives(group, allDescendents=True, fullPath=True,
                                    type=pub.GEOMETRY_TYPES) or []:
        transforms.update(cmds.listRelatives(shape, parent=True, fullPath=True) or [])
    depth = len(_parts(group))
    found = {}
    for path in paths:
        want = _parts(path)
        best, best_len = None, 0
        for t in transforms:
            rel = _parts(t)[depth:]
            if rel and len(rel) > best_len and want[-len(rel):] == rel:
                best, best_len = t, len(rel)
        if best:
            found[path] = best
    return found


def apply_look(shot_dir, published, vid, department=None):
    """Put the look on a cache built into the open scene: import the look's
    materials (namespace <cache namespace>_look), make its shading groups
    again and assign them by mesh name. A cache already wearing this look
    is left alone. Returns (done lines, warning or None)."""
    info = (published.get("cache_info") or {}).get(vid) or {}
    namespace = namespace_for(published["asset"], published["code"])
    group = (cmds.ls(namespace + "_GRP", long=True) or [None])[0]
    if not group:
        return [], None
    h_root, rel = pub.find_film_folder(published["versions"][vid])
    look = look_for_cache(h_root, rel[0], info, department)
    if not look:
        if info.get("kind") in ("rig", "model"):
            return [], ("no look to put on the cache: %s v%03d was published without one "
                        "(republish it to get one)." % (info["kind"], (info.get("asset") or {})
                                                        .get("version") or 0))
        return [], None
    look_ma, look_json, source = look
    with open(look_json, "r") as f:
        data = json.load(f)
    worn = (cmds.getAttr(group + "." + LOOK_ATTR)
            if cmds.attributeQuery(LOOK_ATTR, node=group, exists=True) else None)
    look_ns = namespace + "_look"
    name = os.path.basename(look_ma)
    if worn == name and cmds.namespace(exists=":" + look_ns):
        return [], None

    maya_dir = maya_dir_of_shot(shot_dir)
    local, _ = copy_published(look_ma, maya_dir)
    _pull_textures(source, maya_dir)
    if cmds.namespace(exists=":" + look_ns):    # an older look: Build's own, replaced
        cmds.namespace(removeNamespace=":" + look_ns, deleteNamespaceContent=True)
    pipeEnv.set_from_path(shot_dir)
    cmds.file(local, i=True, type="mayaAscii", namespace=look_ns,
              mergeNamespacesOnClash=False, preserveReferences=False)

    matches = _match_meshes(group, [m["path"] for e in data["shading_groups"].values()
                                    for m in e["members"]])
    missed = []
    for sg_name, entry in sorted(data["shading_groups"].items()):
        sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True,
                       name="%s:%s" % (look_ns, sg_name))
        for attr, src in entry["inputs"].items():
            plug = "%s:%s" % (look_ns, src)
            if cmds.objExists(plug.split(".")[0]):
                cmds.connectAttr(plug, "%s.%s" % (sg, attr), force=True)
        for member in entry["members"]:
            target = matches.get(member["path"])
            if not target:
                missed.append(member["path"].split("|")[-1])
                continue
            cmds.sets(target + ("." + member["faces"] if member["faces"] else ""),
                      edit=True, forceElement=sg)
    if not cmds.attributeQuery(LOOK_ATTR, node=group, exists=True):
        cmds.addAttr(group, longName=LOOK_ATTR, dataType="string")
    cmds.setAttr(group + "." + LOOK_ATTR, name, type="string")
    what = "LookDev" if "_lookDev_" in name else data.get("department") or "asset"
    done = ["%s look v%03d put on (%d shader%s)" % (
        what, data.get("version") or 0, len(data["shading_groups"]),
        "" if len(data["shading_groups"]) == 1 else "s")]
    warning = ("no cache geometry for: %s" % ", ".join(sorted(set(missed)))) if missed else None
    return done, warning


# ---------------------------------------------------------------------------
# Asset development: a published asset pulled into an asset scene is
# imported, never referenced; referencing is for building shots (user,
# 2026-10-28). It arrives as published (its stamped pipe group, no
# namespace) and its textures and DNA become this asset's own, copied into
# its sourceimages.
# ---------------------------------------------------------------------------

def asset_of_scene(scene_path, scratch_root):
    """(film, asset_type, asset) if the scene is inside an asset on scratch, else None."""
    try:
        root, rel = pub.find_film_folder(scene_path)
    except BuildError:
        return None
    if (not pub._same_path(root, scratch_root) or len(rel) < 5
            or rel[1] != "maya" or rel[2] != "assets"):
        return None
    return rel[0], rel[3], rel[4]


def asset_folder(root, film, asset_type, asset):
    return os.path.join(root, film, "maya", "assets", asset_type, asset)


def _stamp(node, name):
    plug = "%s.%s" % (node, name)
    return cmds.getAttr(plug) if cmds.objExists(plug) else None


def _set_string(plug, value):
    locked = cmds.getAttr(plug, lock=True)
    if locked:
        cmds.setAttr(plug, lock=False)
    cmds.setAttr(plug, value, type="string")
    if locked:
        cmds.setAttr(plug, lock=True)


def own_files(nodes, pulled, asset_dir):
    """Copy the pulled version's texture folder (textures, DNA) into
    <asset>\\sourceimages\\<published file name>\\ and point the given
    nodes at the copies: texture and image-plane nodes, and each rig
    group's pipe_dna list (so the DNA nodes follow it when the scene
    opens, pipeEnv.fix_dna_paths). Returns the number of nodes repointed.
    Used by the mpModel shelf's Convert to Model (modelTool_convert), which
    makes a referenced publish the asset's own (user, 2026-10-30: Build
    always references; Convert makes it editable)."""
    import publishTool_textures as tex
    folder = texture_folder_of(pulled)
    if not os.path.isdir(folder):
        return 0
    own = os.path.join(asset_dir, tex.FOLDER, os.path.basename(folder))
    for dirpath, _, filenames in os.walk(folder):
        for name in filenames:
            dest = os.path.join(own, os.path.relpath(os.path.join(dirpath, name), folder))
            if not os.path.isfile(dest):
                if not os.path.isdir(os.path.dirname(dest)):
                    os.makedirs(os.path.dirname(dest))
                shutil.copyfile(os.path.join(dirpath, name), dest)     # writable: the asset's own
    key = os.path.normcase(os.path.normpath(folder)) + os.sep

    def owned(path):
        """The copy in this asset for a path inside the pulled folder, else None."""
        full = os.path.normcase(os.path.normpath(os.path.expandvars(path or "")))
        if not full.startswith(key):
            return None
        return os.path.join(own, os.path.normpath(os.path.expandvars(path))[len(key):]
                            ).replace("\\", "/")

    repointed = 0
    attrs = dict(tex.TEXTURE_NODES, **tex.IMAGE_PLANES)
    for node in set(cmds.ls(nodes, long=True) or []):
        attr = attrs.get(cmds.nodeType(node))
        if attr:
            path = owned(cmds.getAttr("%s.%s" % (node, attr)))
            if path:
                _set_string("%s.%s" % (node, attr), path)
                repointed += 1
        dna = _stamp(node, pipeEnv.DNA_STAMP)
        if dna:
            entries = json.loads(dna)
            for entry in entries:
                path = owned(entry.get("published"))
                if path:
                    entry["published"] = path
                    repointed += 1
            _set_string("%s.%s" % (node, pipeEnv.DNA_STAMP), json.dumps(entries))
    return repointed


def set_maya_project(shot_dir):
    pub.set_maya_project(shot_dir)


def ensure_maya_project(shot_dir):
    """Make the shot the Maya project if it isn't already (spec §3f: Build
    sets the project so students don't switch by hand). True if changed."""
    workspace = cmds.workspace(query=True, rootDirectory=True)
    if workspace and pub._same_path(workspace, shot_dir):
        return False
    set_maya_project(shot_dir)
    return True


# ---------------------------------------------------------------------------
# What's on my scratch
# ---------------------------------------------------------------------------

SAFE, CHANGED, UNPUBLISHED = "safe", "changed", "unpublished"


def _files(folder):
    found = []
    for dirpath, _, filenames in os.walk(folder):
        for name in filenames:
            if dirpath == folder and name in KEEP_FILES:
                continue
            found.append(os.path.join(dirpath, name))
    return sorted(found)


def scratch_items(scratch_root, h_root, film):
    """Everything on scratch that holds files, with how safe it is to remove.

    Each item: {kind ('asset'|'shot'), label, folder, files, size,
    status (SAFE/CHANGED/UNPUBLISHED), latest (text), risky: [files]}.
    """
    items = []
    published = list_published(h_root, film) if h_root and os.path.isdir(h_root) else []

    # Assets: safe if every file is a scene older than the newest publish.
    for asset_type, asset in pub.list_h_assets(scratch_root, film):
        folder = os.path.join(scratch_root, film, "maya", "assets", asset_type, asset)
        files = _files(folder)
        if not files:
            continue
        pubs = [p for p in published if p["asset_type"] == asset_type and p["asset"] == asset]
        newest = None
        latest_text = "never published"
        for p in pubs:
            path = p["versions"][p["latest"]]
            t = publish_time(path)
            if newest is None or t > newest[0]:
                newest = (t, p)
        if newest:
            t, p = newest
            latest_text = "%s %s, %s" % (DEPT_LABELS.get(p["code"], p["code"]),
                                          version_label(p, p["latest"], mark_latest=False),
                                          datetime.fromtimestamp(t).strftime("%d %b %H:%M"))
        scenes = os.path.normcase(os.path.join(folder, "scenes")) + os.sep
        risky = []
        for f in files:
            if newest is None or not os.path.normcase(f).startswith(scenes) \
                    or os.path.getmtime(f) > newest[0]:
                risky.append(f)
        status = SAFE if not risky else (UNPUBLISHED if newest is None else CHANGED)
        items.append(_item("asset", "%s  (%s)" % (asset, asset_type), folder,
                           files, status, latest_text, risky))

    # Shots: pulled copies can always be pulled again; anything else isn't
    # backed up anywhere yet (shot publishing isn't built).
    for seq, shot in list_shots(scratch_root, film):
        folder = shot_folder(scratch_root, film, seq, shot)
        files = _files(folder)
        if not files:
            continue
        manifest = read_manifest(folder)
        pulled = set(os.path.normcase(os.path.join(folder, *rel.split("/")))
                     for e in manifest.values()
                     for rel in ([e["file"]] if "file" in e else [])
                     + ([e["link"]] if "link" in e else []) + e.get("extra_files", []))
        pulled.add(os.path.normcase(_manifest_path(folder)))
        risky = [f for f in files if os.path.normcase(f) not in pulled]
        status = SAFE if not risky else UNPUBLISHED
        latest = "%d pulled asset(s)" % len(manifest) if manifest else "-"
        items.append(_item("shot", "%s / %s" % (seq, shot), folder,
                           files, status, latest, risky))
    return items


def _item(kind, label, folder, files, status, latest, risky):
    return {"kind": kind, "label": label, "folder": folder, "files": files,
            "size": sum(os.path.getsize(f) for f in files),
            "status": status, "latest": latest, "risky": risky}


def removal_check(folder, h_root, scratch_root):
    """Refuse anything that isn't an asset/shot folder on scratch."""
    h_root, scratch_root = pub.resolve_root(h_root), pub.resolve_root(scratch_root)
    pub.check_roots(h_root, scratch_root)
    root, rel = pub.find_film_folder(os.path.join(folder, "x"))
    is_asset = len(rel) == 6 and rel[1:3] == ["maya", "assets"]
    is_shot = len(rel) == 6 and rel[1:3] == ["maya", "sequences"]
    if not (is_asset or is_shot):
        raise BuildError("Not an asset or shot folder: %s" % folder)
    if not pub._same_path(root, scratch_root):
        raise BuildError("Refusing to remove anything outside the scratch drive (%s)."
                         % scratch_root)


def send_to_recycle_bin(paths):
    """Move files to the Recycle Bin (Windows), so a mistake can be undone.
    Returns True on success. Folders are left in place (1:1 mirror)."""
    if not paths:
        return True
    if os.name != "nt":
        raise BuildError("Recycle Bin removal is only set up for Windows.")
    # A rig's hardlink shares its read-only flag with the version in the
    # publish folder, so lock that folder again afterwards.
    relock = set()
    for p in paths:
        try:
            if os.stat(p).st_nlink > 1:
                root, rel = pub.find_film_folder(p)
                relock.add(os.path.join(root, rel[0], "maya"))
        except (OSError, BuildError):
            pass
        try:
            os.chmod(p, stat.S_IWRITE)
        except OSError:
            pass

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [("hwnd", ctypes.c_void_p), ("wFunc", ctypes.c_uint),
                    ("pFrom", ctypes.c_wchar_p), ("pTo", ctypes.c_wchar_p),
                    ("fFlags", ctypes.c_ushort), ("fAnyOperationsAborted", ctypes.c_int),
                    ("hNameMappings", ctypes.c_void_p),
                    ("lpszProgressTitle", ctypes.c_wchar_p)]

    FO_DELETE, FOF_SILENT, FOF_NOCONFIRMATION, FOF_ALLOWUNDO, FOF_NOERRORUI = \
        3, 0x4, 0x10, 0x40, 0x400
    op = SHFILEOPSTRUCTW()
    op.wFunc = FO_DELETE
    op.pFrom = "\0".join(os.path.abspath(p) for p in paths) + "\0\0"
    op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI
    result = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
    for maya_dir in relock:
        _lock_publish_folder(maya_dir)
    return result == 0 and not op.fAnyOperationsAborted


def format_size(n):
    for unit in ("bytes", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return ("%d %s" % (n, unit)) if unit == "bytes" else ("%.1f %s" % (n, unit))
        n /= 1024.0
