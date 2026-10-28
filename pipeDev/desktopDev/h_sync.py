"""
H drive sync — first piece of the staff desktop tool (Class Project Setup
Tool, tech notes §14). Plain Python 3, no Maya: runs on Windows and macOS.

DECIDED 2026-10-19 (pipeDev/projectSwitcher_brief.md): staff create assets
and shots in ShotGrid as normal; when the desktop tool is opened it sees
what's in ShotGrid without a folder on the H drive and builds those
folders. It ONLY ADDS: an existing asset/shot folder is never written over
(overwriting is the user's call only, to be designed later).

    Shot   EAP_010_010 (Sequence EAP_010)  -> <H>/<FILM>/maya/sequences/EAP_010/EAP_010_010/
    Asset  scoutsHouse_landscape (Environment)
                                           -> <H>/<FILM>/maya/assets/environment/scoutsHouseLandscape/

Each new folder gets the same Maya project layout as the film's existing
assets/shots (folders + workspace.mel, no files), copied from one of them.

It also builds the show's Studio Library folders (spec §4b, DECIDED
2026-10-21): every character gets keyframe/mocap x face/body x
pose/motion folders, show-wide and in every shot, because any character
can turn up in any shot.

    <H>/<FILM>/maya/studioLibrary/show/scout/keyframe/face/pose/
    <H>/<FILM>/maya/studioLibrary/sequences/EAP_010/EAP_010_010/scout/mocap/body/motion/

Run (dry run first; --apply to build):
    python h_sync.py --h-root "G:/H" --film NWF_SHF
    python h_sync.py --h-root "/Volumes/T7/H" --film NWF_SHF --apply

Needs: Python 3.7+ and shotgun_api3 (ships with mpToolSet; on its own:
pip install git+https://github.com/shotgunsoftware/python-api.git).
ShotGrid credentials: a JSON file with site_url, script_name, api_key (see
find_config()). Never printed.
"""

import os
import re
import sys
import json
import shutil
import argparse

WORKSPACE = "workspace.mel"
FILM_CONFIG = "pipeline.json"
CONFIG_NAMES = ("mpPipe_desktop.json", "shotSub_config.json")
# Shots that are cut references, not worked on (none get tasks either,
# shotgridTemplate_requirements.md): no folder.
REFERENCE_SHOT = re.compile(r"FULL_CUT$", re.IGNORECASE)
# ShotGrid asset types that have a folder under maya/assets (spec §3f).
# Graphic (boards, guides) has no home yet.
NO_FOLDER_TYPES = ("Graphic",)
# The show's Studio Library (spec §4b): <maya>/studioLibrary/{show,
# sequences/<SEQ>/<SHOT>}/<character>/<kind>/<part>/<item>.
LIBRARY = "studioLibrary"
LIBRARY_TYPE = "Character"
LIBRARY_KINDS = ("keyframe", "mocap")
LIBRARY_PARTS = ("face", "body")
LIBRARY_ITEMS = ("pose", "motion")
# Every asset's scenes\model\, scenes\rig\ and scenes\lookDev\ working
# folders (each holds a folder per person), new and existing assets alike
# (user, 2026-10-28). Same as publishTool_api.WORK_FOLDERS (this script
# runs without Maya).
WORK_FOLDERS = ("model", "rig", "lookDev")


# ---------------------------------------------------------------------------
# Names: ShotGrid code -> folder name (spec §3f)
# ---------------------------------------------------------------------------

def asset_folder_name(code):
    """camelCase folder name for a ShotGrid asset code, as the NWF folders
    were made: "Scout's House" -> scoutsHouse, "AT-KS" -> ATKS,
    "bakedBeans_Can" -> bakedBeansCan, "scoutsHouse_landscape" ->
    scoutsHouseLandscape. Words split on spaces, _ and -; other punctuation
    dropped; the first word keeps its case if it's all capitals, otherwise
    starts lower case; later words start with a capital."""
    words = [re.sub(r"[^A-Za-z0-9]", "", w) for w in re.split(r"[\s_\-]+", code.strip())]
    words = [w for w in words if w]
    if not words:
        return ""
    first = words[0] if words[0].isupper() else words[0][0].lower() + words[0][1:]
    return first + "".join(w[0].upper() + w[1:] for w in words[1:])


def type_folder_name(asset_type):
    return re.sub(r"[^A-Za-z0-9]", "", asset_type or "").lower()


# ---------------------------------------------------------------------------
# ShotGrid
# ---------------------------------------------------------------------------

def find_config(explicit=None):
    """The credentials file: --config, else mpPipe_desktop.json next to this
    script or in ~/.mpPipe/, else Maya's shotSub_config.json (Windows/macOS
    prefs) for staff machines that already have shotSub set up."""
    candidates = [explicit] if explicit else []
    here = os.path.dirname(os.path.abspath(__file__))
    home = os.path.expanduser("~")
    candidates += [os.path.join(here, CONFIG_NAMES[0]),
                   os.path.join(home, ".mpPipe", CONFIG_NAMES[0])]
    for maya_dir in (os.path.join(home, "Documents", "maya"),                      # Windows
                     os.path.join(home, "Library", "Preferences", "Autodesk", "maya")):  # macOS
        for version in ("2026", "2025", "2027"):
            candidates.append(os.path.join(maya_dir, version, "prefs", CONFIG_NAMES[1]))
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    raise SystemExit("No ShotGrid settings file found. Put %s (site_url, script_name, "
                     "api_key) next to h_sync.py or in ~/.mpPipe/." % CONFIG_NAMES[0])


def _find_shotgun_api3():
    """Make shotgun_api3 importable: a copy next to this script, else the
    one mpToolSet installs into Maya's scripts folder (Windows / macOS)."""
    home = os.path.expanduser("~")
    for folder in (os.path.dirname(os.path.abspath(__file__)),
                   os.path.join(home, "Documents", "maya", "scripts"),
                   os.path.join(home, "Library", "Preferences", "Autodesk", "maya", "scripts")):
        if os.path.isdir(os.path.join(folder, "shotgun_api3")) and folder not in sys.path:
            sys.path.append(folder)


def connect(config_path=None):
    _find_shotgun_api3()
    try:
        import shotgun_api3
    except ImportError:
        raise SystemExit("shotgun_api3 isn't available. Put the shotgun_api3 folder next to "
                         "h_sync.py, or pip install it (see the top of this file).")
    with open(find_config(config_path), "r") as f:
        config = json.load(f)
    return shotgun_api3.Shotgun(config["site_url"], script_name=config["script_name"],
                                api_key=config["api_key"])


def shotgrid_contents(sg, project_id):
    """What ShotGrid says the film has: (shots, assets), as lists of dicts
    with "code" and "sequence" / "type"."""
    project = {"type": "Project", "id": project_id}
    shots = sg.find("Shot", [["project", "is", project]], ["code", "sg_sequence"])
    assets = sg.find("Asset", [["project", "is", project]], ["code", "sg_asset_type"])
    return ([{"code": s["code"], "sequence": (s.get("sg_sequence") or {}).get("name")} for s in shots],
            [{"code": a["code"], "type": a.get("sg_asset_type")} for a in assets])


# ---------------------------------------------------------------------------
# The plan: what to build, what to leave
# ---------------------------------------------------------------------------

def _key(path):
    """Compare paths ignoring case and slash style. os.path.normcase only
    does that on Windows; macOS drives (APFS, SMB shares) are usually
    case-insensitive too, so do it explicitly."""
    return os.path.normpath(path).replace("\\", "/").lower()


def film_project_id(h_root, film):
    path = os.path.join(h_root, film, FILM_CONFIG)
    with open(path, "r") as f:
        return json.load(f)["shotgrid_project_id"]


def library_folders(maya_dir, shots, characters):
    """Every Studio Library end folder the show should have: for each
    character (folder name), show-wide and per (sequence, shot)."""
    places = [("show",)] + [("sequences", seq, shot) for seq, shot in shots]
    return [os.path.join(maya_dir, LIBRARY, *(place + (character, kind, part, item)))
            for place in places for character in characters
            for kind in LIBRARY_KINDS for part in LIBRARY_PARTS for item in LIBRARY_ITEMS]


def plan_sync(h_root, film, shots, assets):
    """{"build": [(kind, label, folder)], "skipped": [(label, why)],
        "not_in_shotgrid": [folder], "library": [folder],
        "characters": [name], "work": [folder]}. Only folders that don't
    exist yet are ever in "build", "library" or "work"."""
    maya_dir = os.path.join(h_root, film, "maya")
    build, skipped, expected = [], [], set()
    work = []           # scenes\model, scenes\rig of every asset that has/gets a folder
    worked_on = []      # (sequence, shot) of every shot that has/gets a folder
    for shot in sorted(shots, key=lambda s: s["code"]):
        if REFERENCE_SHOT.search(shot["code"]):
            skipped.append((shot["code"], "cut reference shot, not worked on"))
            continue
        if not shot["sequence"]:
            skipped.append((shot["code"], "not in a sequence in ShotGrid"))
            continue
        worked_on.append((shot["sequence"], shot["code"]))
        folder = os.path.join(maya_dir, "sequences", shot["sequence"], shot["code"])
        expected.add(_key(folder))
        if not os.path.isdir(folder):
            build.append(("shot", shot["code"], folder))
    for asset in sorted(assets, key=lambda a: a["code"].lower()):
        if not asset["type"]:
            # Can't tell which type folder it belongs in, so nothing is
            # built; but a folder of that name under any type is its own.
            name = asset_folder_name(asset["code"])
            assets_dir = os.path.join(maya_dir, "assets")
            existing = [os.path.join(assets_dir, t, name) for t in
                        (os.listdir(assets_dir) if os.path.isdir(assets_dir) else [])
                        if os.path.isdir(os.path.join(assets_dir, t, name))]
            expected.update(_key(p) for p in existing)
            skipped.append((asset["code"], "no asset type in ShotGrid" +
                            (" (has a folder: %s)" % ", ".join(existing) if existing
                             else ", so no folder can be made")))
            continue
        if asset["type"] in NO_FOLDER_TYPES:
            skipped.append((asset["code"], "%s assets have no folder yet" % asset["type"]))
            continue
        name = asset_folder_name(asset["code"])
        folder = os.path.join(maya_dir, "assets", type_folder_name(asset["type"]), name)
        expected.add(_key(folder))
        if not os.path.isdir(folder):
            build.append(("asset", "%s (%s)" % (asset["code"], asset["type"]), folder))
        work += [os.path.join(folder, "scenes", w) for w in WORK_FOLDERS
                 if not os.path.isdir(os.path.join(folder, "scenes", w))]
    # Folders on the H drive that ShotGrid doesn't have (renamed/removed, or
    # made by hand): reported, never touched.
    not_in_shotgrid = []
    for kind, depth in (("sequences", 2), ("assets", 2)):
        top = os.path.join(maya_dir, kind)
        if not os.path.isdir(top):
            continue
        for group in sorted(os.listdir(top)):
            gdir = os.path.join(top, group)
            if not os.path.isdir(gdir):
                continue
            for name in sorted(os.listdir(gdir)):
                path = os.path.join(gdir, name)
                if os.path.isdir(path) and _key(path) not in expected:
                    not_in_shotgrid.append(path)
    characters = sorted(set(asset_folder_name(a["code"]) for a in assets
                            if (a["type"] or "").lower() == LIBRARY_TYPE.lower()), key=str.lower)
    library = [f for f in library_folders(maya_dir, worked_on, characters)
               if not os.path.isdir(f)]
    return {"build": build, "skipped": skipped, "not_in_shotgrid": not_in_shotgrid,
            "library": library, "characters": characters, "work": work}


# ---------------------------------------------------------------------------
# Building
# ---------------------------------------------------------------------------

def template_project(h_root, film, kind):
    """An existing asset (or shot) project to copy the layout from."""
    top = os.path.join(h_root, film, "maya", "assets" if kind == "asset" else "sequences")
    if os.path.isdir(top):
        for group in sorted(os.listdir(top)):
            for name in sorted(os.listdir(os.path.join(top, group))
                               if os.path.isdir(os.path.join(top, group)) else []):
                path = os.path.join(top, group, name)
                if os.path.isfile(os.path.join(path, WORKSPACE)):
                    return path
    return None


def build_project(template, folder):
    """Make folder with the template's Maya project layout: its folders and
    workspace.mel only (no files, no one's personal scenes/<login>/).
    Refuses if folder exists: nothing is ever written over."""
    if os.path.exists(folder):
        raise RuntimeError("%s already exists: not touched." % folder)
    made = 0
    for dirpath, dirnames, filenames in os.walk(template):
        rel = os.path.relpath(dirpath, template)
        parts = [] if rel == "." else rel.split(os.sep)
        if len(parts) >= 2 and parts[0] == "scenes":
            continue
        os.makedirs(os.path.join(folder, *parts))
        made += 1
    shutil.copyfile(os.path.join(template, WORKSPACE), os.path.join(folder, WORKSPACE))
    return made


def apply_sync(h_root, film, plan, log=print):
    templates = {}
    built = []
    for kind, label, folder in plan["build"]:
        if kind not in templates:
            templates[kind] = template_project(h_root, film, kind)
        if not templates[kind]:
            log("  can't build %s: no existing %s project on the H drive to copy the "
                "layout from" % (label, kind))
            continue
        try:
            build_project(templates[kind], folder)
            built.append(folder)
            log("  built  %s  ->  %s" % (label, folder))
        except (RuntimeError, OSError) as e:
            log("  skipped %s: %s" % (label, e))
    made = 0
    for folder in plan.get("library") or []:
        try:
            os.makedirs(folder, exist_ok=True)      # only adds; nothing inside is touched
            made += 1
        except OSError as e:
            log("  skipped Studio Library folder %s: %s" % (folder, e))
    if made:
        log("  built  %d Studio Library folder(s)" % made)
    made = 0
    for folder in plan.get("work") or []:
        # After the asset itself is built; skipped if it couldn't be.
        if not os.path.isdir(os.path.dirname(os.path.dirname(folder))):
            continue
        try:
            os.makedirs(folder, exist_ok=True)
            made += 1
        except OSError as e:
            log("  skipped %s: %s" % (folder, e))
    if made:
        log("  built  %d model/rig/lookDev working folder(s)" % made)
    return built


def report(plan, log=print):
    log("New in ShotGrid, no folder on the H drive yet (%d):" % len(plan["build"]))
    for kind, label, folder in plan["build"]:
        log("  %-5s %s  ->  %s" % (kind, label, folder))
    if plan["skipped"]:
        log("Not given a folder (%d):" % len(plan["skipped"]))
        for label, why in plan["skipped"]:
            log("  %s: %s" % (label, why))
    if plan["not_in_shotgrid"]:
        log("On the H drive but not in ShotGrid (left alone) (%d):" % len(plan["not_in_shotgrid"]))
        for path in plan["not_in_shotgrid"]:
            log("  %s" % path)
    if plan.get("library"):
        log("Studio Library folders to add (%d), for characters: %s"
            % (len(plan["library"]), ", ".join(plan["characters"])))
    if plan.get("work"):
        log("Asset working folders to add (%d): scenes\\%s"
            % (len(plan["work"]), ", scenes\\".join(WORK_FOLDERS)))


def films_on(h_root):
    """Film folders on the H drive that know their ShotGrid project."""
    return sorted(n for n in os.listdir(h_root)
                  if os.path.isfile(os.path.join(h_root, n, FILM_CONFIG)))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build H-drive folders for new ShotGrid "
                                                 "assets and shots. Never overwrites.")
    parser.add_argument("--h-root", required=True, help="folder holding the film folders")
    parser.add_argument("--film", help="film folder, e.g. NWF_SHF (default: every film)")
    parser.add_argument("--config", help="ShotGrid settings JSON")
    parser.add_argument("--apply", action="store_true", help="build them (default: just list)")
    parser.add_argument("--ask", action="store_true",
                        help="list, then ask whether to build (for the double-click launchers)")
    args = parser.parse_args(argv)
    if not os.path.isdir(args.h_root):
        raise SystemExit("Can't find the H drive at %s. Is it connected?" % args.h_root)
    films = [args.film] if args.film else films_on(args.h_root)
    if not films:
        raise SystemExit("No film folders with a %s in %s." % (FILM_CONFIG, args.h_root))
    sg = connect(args.config)
    plans = []
    for film in films:
        print("\n=== %s ===" % film)
        shots, assets = shotgrid_contents(sg, film_project_id(args.h_root, film))
        plan = plan_sync(args.h_root, film, shots, assets)
        report(plan)
        plans.append((film, plan))
    total = sum(len(p["build"]) + len(p.get("library") or []) + len(p.get("work") or [])
                for _, p in plans)
    print("")
    if not total:
        print("Nothing new: the H drive already has a folder for everything in ShotGrid.")
        return
    build = args.apply
    if args.ask and not build:
        build = input("Build these %d folder(s) now? (y/n) " % total).strip().lower() in ("y", "yes")
    if build:
        print("Building...")
        for film, plan in plans:
            apply_sync(args.h_root, film, plan)
        print("Done.")
    else:
        print("Nothing built." if args.ask else "(Dry run: nothing built. Add --apply to build.)")


if __name__ == "__main__":
    main()
