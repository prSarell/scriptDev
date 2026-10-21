"""
Studio Library in the pipe (spec §4b, DECIDED 2026-10-21). Plain file
work, so it can be tested under mayapy; Studio Library itself is only
imported by configure().

Two kinds of library, both kept on scratch (students can take them home on
a drive) and backed up to the H drive:

    show library   <film>\\maya\\studioLibrary\\        shared: anyone saves in it
                   (show\\ and sequences\\<SEQ>\\<SHOT>\\, one folder per
                   character, made by the desktop tool, h_sync.py)
    shot library   <shot project>\\data\\studioLibrary\\<login>\\
                   the student's own work for that shot, organised as they like

- back_up(): every publish, iterative or final, copies new and changed
  items from scratch to the H drive: the whole project's libraries.
- restore(): Set Project brings the show library and the student's own
  shot libraries down from the H drive (after a wipe, on a new machine, or
  to see what others shared).
- Both only add: nothing is ever deleted, and a newer copy is never
  written over with an older one. Removing an item for good is a staff job
  on the H drive (a deleted item comes back on the next restore).
- configure(): points the student's Studio Library at the show library
  and their shot library (the shot one opens by default).

Studio Library's own index of a library (.studiolibrary\\database.json in
the library's top folder) is never copied: it's a cache Studio Library
rebuilds, and everyone's copy differs.
"""

import os
import json
import shutil

FOLDER = "studioLibrary"
SHOT_FOLDER = ("data", FOLDER)
CACHE = (".studiolibrary", "database.json")
# Studio Library only looks this many folders down from a library's top for
# items. Its default (5) doesn't reach a show library item:
# sequences\SEQ\SHOT\<character>\keyframe\face\pose\<item> is 8 down.
SEARCH_DEPTH = 12
CONFIG_NAME = "mpPipe_studioLibrary_config.json"
TAG = "mpPipe_film"         # marks the Studio Library entries the pipe made
SLACK = 2                   # seconds: FAT/exFAT and some shares round file times
_TEMP = ".mpPipeTmp"


def show_library(root, film):
    return os.path.join(root, film, "maya", FOLDER)


def shot_library(shot_dir, login):
    return os.path.join(shot_dir, *(SHOT_FOLDER + (login,)))


def _shot_dirs(root, film):
    seq_dir = os.path.join(root, film, "maya", "sequences")
    found = []
    for seq in sorted(os.listdir(seq_dir)) if os.path.isdir(seq_dir) else []:
        for shot in sorted(os.listdir(os.path.join(seq_dir, seq))) \
                if os.path.isdir(os.path.join(seq_dir, seq)) else []:
            found.append(os.path.join(seq_dir, seq, shot))
    return found


def library_folders(root, film, login=None):
    """The film's library folders under root, relative to root: the show
    library plus every shot's data\\studioLibrary (or, with login, only that
    person's folder in each shot)."""
    found = [os.path.relpath(show_library(root, film), root)]
    for shot_dir in _shot_dirs(root, film):
        folder = os.path.join(shot_dir, *SHOT_FOLDER)
        if login:
            folder = os.path.join(folder, login)
        found.append(os.path.relpath(folder, root))
    return found


def _is_cache(path):
    parts = os.path.normpath(path).split(os.sep)
    return tuple(parts[-2:]) == CACHE


def _copy(src, dest):
    """Copy with times kept (so the next check sees them as the same), via a
    temporary name so nobody ever opens a half-written item."""
    tmp = dest + _TEMP
    shutil.copy2(src, tmp)
    if os.path.exists(dest):
        os.chmod(dest, 0o666)
    os.replace(tmp, dest)


def sync(src_root, dest_root, rel_folders):
    """Copy what's new or newer from src_root to dest_root for each folder
    (paths relative to both roots), folders included. Never deletes; never
    writes over a newer file. Returns {"copied": [rel paths], "kept":
    [rel paths where dest was newer], "folders": n made}."""
    result = {"copied": [], "kept": [], "folders": 0}
    for rel in rel_folders:
        top = os.path.join(src_root, rel)
        if not os.path.isdir(top):
            continue
        for dirpath, dirnames, filenames in os.walk(top):
            dest_dir = os.path.join(dest_root, os.path.relpath(dirpath, src_root))
            if not os.path.isdir(dest_dir):
                os.makedirs(dest_dir)
                result["folders"] += 1
            for name in filenames:
                src = os.path.join(dirpath, name)
                if name.endswith(_TEMP) or _is_cache(src):
                    continue
                dest = os.path.join(dest_dir, name)
                file_rel = os.path.relpath(src, src_root)
                if os.path.isfile(dest):
                    s, d = os.stat(src), os.stat(dest)
                    if d.st_mtime > s.st_mtime + SLACK:
                        if d.st_size != s.st_size:
                            result["kept"].append(file_rel)
                        continue
                    if s.st_mtime <= d.st_mtime + SLACK and s.st_size == d.st_size:
                        continue
                _copy(src, dest)
                result["copied"].append(file_rel)
    return result


def back_up(scratch_root, h_root, film):
    """Every publish: the film's libraries on scratch -> the H drive (the
    show library and every shot's data\\studioLibrary)."""
    return sync(scratch_root, h_root, library_folders(scratch_root, film))


def restore(h_root, scratch_root, film, login):
    """Set Project: the show library and this person's own shot libraries,
    H drive -> scratch."""
    return sync(h_root, scratch_root, library_folders(h_root, film, login))


def describe(result, where):
    """'Studio Library: 3 file(s) backed up to the H drive' (or '' if
    nothing happened), plus a note for items left alone because the other
    side had a newer copy."""
    text = ""
    if result["copied"]:
        text = "Studio Library: %d file(s) %s" % (len(result["copied"]), where)
    if result["kept"]:
        text += ("; " if text else "Studio Library: ") + (
            "%d file(s) not copied because the other copy is newer (someone changed it "
            "since): %s" % (len(result["kept"]), ", ".join(
                os.path.basename(p) for p in result["kept"][:5])))
    return text


# ---------------------------------------------------------------------------
# Studio Library's own settings
# ---------------------------------------------------------------------------

def config_file(folder):
    """Write (if needed) a Studio Library config that lets it look deep
    enough for the show library's items. Returns its path."""
    path = os.path.join(folder, CONFIG_NAME)
    data = {"recursiveSearchDepth": SEARCH_DEPTH}
    try:
        with open(path, "r") as f:
            if json.load(f) == data:
                return path
    except (IOError, OSError, ValueError):
        pass
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    return path


def use_config(folder):
    """At Maya startup (pipeEnv.install): point Studio Library at that
    config, unless something else already set STUDIO_LIBRARY_CONFIG_PATH."""
    if not os.environ.get("STUDIO_LIBRARY_CONFIG_PATH"):
        os.environ["STUDIO_LIBRARY_CONFIG_PATH"] = config_file(folder)
    return os.environ["STUDIO_LIBRARY_CONFIG_PATH"]


def library_names(film, shot=None):
    """(show library name, shot library name or None) as Studio Library
    lists them."""
    return "%s Show" % film, ("%s %s (mine)" % (film, shot) if shot else None)


def configure(film, show_path, shot_path=None, shot=None):
    """Point the person's Studio Library at the film's show library and,
    for a shot, their own shot library (opened by default). The pipe's
    entries for this film from other shots are replaced; anything the
    person added themselves is kept. Returns the names set, or None if
    Studio Library isn't installed."""
    try:
        import studiolibrary
    except ImportError:
        return None
    if (studiolibrary.config.get("recursiveSearchDepth") or 0) < SEARCH_DEPTH:
        studiolibrary.config.set("recursiveSearchDepth", SEARCH_DEPTH)
    show_name, shot_name = library_names(film, shot if shot_path else None)
    settings = studiolibrary.readSettings() or {}
    for name in list(settings):
        entry = settings[name]
        if isinstance(entry, dict) and entry.get(TAG) == film and name not in (show_name, shot_name):
            del settings[name]
    for name, path, default in ((show_name, show_path, not shot_name),
                                (shot_name, shot_path, True)):
        if not name:
            continue
        entry = settings.setdefault(name, {})
        entry.update({"path": os.path.normpath(path).replace("\\", "/"), TAG: film})
        if default:
            for other in settings.values():
                if isinstance(other, dict):
                    other.pop("default", None)
            entry["default"] = True
    studiolibrary.saveSettings(settings)
    return [n for n in (show_name, shot_name) if n]
