# ------------------------------------------------------------
# build_class_playlist.py
#
# One-off admin utility: builds a dated ShotGrid Playlist of everything
# published to a Project since the last class, ready to open straight in
# Screening Room for presenting student work on the big screen.
#
# Cutoff logic:
#   - explicit since_date (YYYY-MM-DD) argument, if given, always wins.
#   - otherwise, finds this Project's most recently-created Playlist and
#     uses its created_at as the cutoff -- so a plain re-run each class
#     naturally picks up "everything since last time" with no bookkeeping
#     on your end.
#   - if this Project has no Playlist yet, falls back to the start of
#     today (local time).
#
# Does NOT create an empty Playlist if nothing new was published --
# re-running this script twice in a row (or before any new work has come
# in) just reports "nothing new" and exits, so it's safe to re-run without
# leaving clutter behind.
#
# Flags any included Version that has no uploaded movie (see shotSub's
# "no review movie" Note fix) so you know before hitting Play in front of
# the class that one of them won't have anything to scrub through.
#
# Uses the same ShotGrid connection as shotSub (shotgridConnect.py,
# colocated in this same folder) -- reads shotSub_config.json, connects as
# the instructor's own login (current_login()), same permission tier as
# doing this by hand in ShotGrid's web UI.
#
# Run via mayapy from this folder:
#   mayapy build_class_playlist.py <project_name> [since_date_YYYY-MM-DD]
#
# Example:
#   mayapy build_class_playlist.py "3DcharacterPerformance"
#   mayapy build_class_playlist.py "3DcharacterPerformance" 2026-08-01
# ------------------------------------------------------------
import sys
import os
from datetime import datetime

_DEV_DIR = os.path.dirname(os.path.abspath(__file__))
if _DEV_DIR not in sys.path:
    sys.path.insert(0, _DEV_DIR)

try:
    import maya.standalone
    maya.standalone.initialize(name="python")
except Exception:
    pass  # already running inside an interactive Maya session

import shotgridConnect


def _find_project(sg, project_name):
    project = sg.find_one("Project", [["name", "is", project_name]], ["id", "name"])
    if not project:
        raise RuntimeError(
            "build_class_playlist: no ShotGrid Project named '{0}'".format(project_name)
        )
    return project


def _resolve_cutoff(sg, project, since_date):
    """Returns (cutoff_datetime, source_description) -- see module
    docstring for the priority order (explicit arg > last Playlist >
    start of today)."""
    if since_date:
        try:
            return datetime.strptime(since_date, "%Y-%m-%d"), "explicit --since {0}".format(since_date)
        except ValueError:
            raise RuntimeError(
                "build_class_playlist: since_date '{0}' isn't YYYY-MM-DD".format(since_date)
            )

    last_playlist = sg.find(
        "Playlist", [["project", "is", project]], ["id", "code", "created_at"],
        order=[{"field_name": "created_at", "direction": "desc"}],
    )
    if last_playlist:
        playlist = last_playlist[0]
        return playlist["created_at"], "last Playlist '{0}' (created {1})".format(
            playlist["code"], playlist["created_at"])

    start_of_today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return start_of_today, "no previous Playlist found — defaulting to start of today"


def build_class_playlist(project_name, since_date=None, playlist_name=None):
    sg = shotgridConnect.get_connection()
    project = _find_project(sg, project_name)

    cutoff, cutoff_source = _resolve_cutoff(sg, project, since_date)
    print("build_class_playlist: cutoff = {0} ({1})".format(cutoff, cutoff_source))

    versions = sg.find(
        "Version",
        [["project", "is", project], ["created_at", "greater_than", cutoff]],
        ["id", "code", "entity", "created_at", "sg_uploaded_movie"],
        order=[{"field_name": "created_at", "direction": "asc"}],
    )

    if not versions:
        print("build_class_playlist: nothing published to '{0}' since the cutoff — "
              "nothing to do.".format(project_name))
        return None

    missing_movie = [v for v in versions if not v.get("sg_uploaded_movie")]

    name = playlist_name or "{0} - {1}".format(project_name, datetime.now().strftime("%Y-%m-%d"))
    playlist = sg.create("Playlist", {
        "project": project,
        "code": name,
        "versions": [{"type": "Version", "id": v["id"]} for v in versions],
    })

    print("build_class_playlist: created Playlist '{0}' (id {1}) with {2} version(s)".format(
        name, playlist["id"], len(versions)))
    for v in versions:
        entity_code = (v.get("entity") or {}).get("name", "")
        flag = "  [NO MOVIE]" if not v.get("sg_uploaded_movie") else ""
        print("  {0}  ({1}){2}".format(v["code"], entity_code, flag))

    if missing_movie:
        print("")
        print("build_class_playlist: heads up -- {0}/{1} included version(s) have no "
              "review movie and won't play back in Screening Room:".format(
                  len(missing_movie), len(versions)))
        for v in missing_movie:
            print("  {0}".format(v["code"]))

    return playlist


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        print(__doc__)
        sys.exit("Usage: mayapy build_class_playlist.py <project_name> [since_date_YYYY-MM-DD]")
    since_arg = sys.argv[2] if len(sys.argv) == 3 else None
    build_class_playlist(sys.argv[1], since_date=since_arg)
