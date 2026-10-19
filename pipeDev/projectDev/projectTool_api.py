"""
Project Tool — core (no UI, so it can be tested under mayapy)
Sets the Maya project to any asset or shot of a film the person is on in
ShotGrid, building the scratch folder structure when it isn't there yet,
and keeps that structure in step with the H drive.

Design: pipeDev/projectSwitcher_brief.md (DECIDED 2026-10-19), spec §3h
(scratch mirrors the H drive 1:1):
- Top level = the ShotGrid projects the person is on; each maps to its
  film folder on the H drive by <H>/<FILM>/pipeline.json's
  shotgrid_project_id.
- The whole film is listed (assets and shots); the person's own ShotGrid
  task assignments are highlighted, not used as a filter.
- Setting a project on a clean scratch drive lays down the film's full
  folder structure from the H drive (folders + workspace.mel, no files),
  plus scenes/<login>/ in that project, then sets the Maya project.
- When the H drive's structure changes the tool sees it and asks before
  updating. Things on scratch that are no longer on the H drive are listed,
  never deleted (they may hold work).
"""

import os
import shutil

import maya.cmds as cmds

import publishTool_api as pub
from publishTool_api import PublishError

WORKSPACE = "workspace.mel"
# Settings key: who to be in ShotGrid on a machine whose Windows login isn't
# an RMIT login (home testing). Same idea as publish_as, for ShotGrid only.
SHOTGRID_AS = "shotgrid_as"
# Made on scratch by the tools or Maya, never on the H drive: not "extra".
SCRATCH_ONLY = (("maya", "publish"),)


# ---------------------------------------------------------------------------
# Who, and which ShotGrid projects
# ---------------------------------------------------------------------------

def rmit_id():
    """The RMIT staff/student number to find the person by in ShotGrid
    (HumanUser.sg_rmit_id): the shotgrid_as setting, else the login."""
    return pub.clean_login(pub.load_config().get(SHOTGRID_AS, "")) or pub.who()


def shotgrid_user(sg=None):
    """The person's ShotGrid HumanUser, found by RMIT ID (sg_rmit_id),
    falling back to the student email login. None if ShotGrid doesn't know
    them."""
    sg = sg or pub._shotgrid().get_connection()
    number = rmit_id()
    fields = ["name", "login", "sg_rmit_id"]
    user = sg.find_one("HumanUser", [["sg_rmit_id", "is", number]], fields)
    if not user:
        user = sg.find_one("HumanUser", [["login", "is", "%s@student.rmit.edu.au" % number]],
                           fields)
    return user


def user_projects(user, sg=None):
    """[{"id", "name"}] of the ShotGrid projects the person is on."""
    sg = sg or pub._shotgrid().get_connection()
    projects = sg.find("Project", [["users", "in", [{"type": "HumanUser", "id": user["id"]}]]],
                       ["name"])
    return sorted(({"id": p["id"], "name": p["name"]} for p in projects),
                  key=lambda p: p["name"].lower())


def films_by_project(h_root):
    """{ShotGrid project id: film folder name} for every film on the H
    drive with a pipeline.json."""
    found = {}
    if not h_root or not os.path.isdir(h_root):
        return found
    for name in sorted(os.listdir(h_root)):
        if pub.FILM_FOLDER_RE.match(name) and os.path.isdir(os.path.join(h_root, name)):
            try:
                config = pub.load_film_config(h_root, name)
            except PublishError:
                continue
            if config.get("shotgrid_project_id"):
                found[config["shotgrid_project_id"]] = name
    return found


def assigned(user, project_id, sg=None):
    """{("Shot" | "Asset", code)} the person has a task on in this project."""
    sg = sg or pub._shotgrid().get_connection()
    tasks = sg.find("Task", [["project", "is", {"type": "Project", "id": project_id}],
                             ["task_assignees", "in", [{"type": "HumanUser", "id": user["id"]}]]],
                    ["entity"])
    return set((t["entity"]["type"], t["entity"]["name"]) for t in tasks if t.get("entity"))


# ---------------------------------------------------------------------------
# What's in a film
# ---------------------------------------------------------------------------

def film_projects(h_root, film):
    """Every Maya project (asset or shot) of the film on the H drive, as
    [{"kind": "asset" | "shot", "group", "name", "rel"}]. rel is the path
    below the drive root, e.g. ["NWF_SHF", "maya", "assets", "prop", "backpack"]."""
    found = []
    for asset_type, asset in pub.list_h_assets(h_root, film):
        found.append({"kind": "asset", "group": asset_type, "name": asset,
                      "rel": [film, "maya", "assets", asset_type, asset]})
    seq_dir = os.path.join(h_root, film, "maya", "sequences")
    if os.path.isdir(seq_dir):
        for seq in sorted(os.listdir(seq_dir)):
            if not os.path.isdir(os.path.join(seq_dir, seq)):
                continue
            for shot in sorted(os.listdir(os.path.join(seq_dir, seq))):
                if os.path.isdir(os.path.join(seq_dir, seq, shot)):
                    found.append({"kind": "shot", "group": seq, "name": shot,
                                  "rel": [film, "maya", "sequences", seq, shot]})
    return found


def is_assigned(project, mine):
    """Does a film project match one of the person's ShotGrid assignments?
    Shot folders use the ShotGrid code as is; asset folders are camelCase
    versions of the asset code (spec §3f), so compare loosely."""
    entity = "Shot" if project["kind"] == "shot" else "Asset"
    key = pub._match_key(project["name"])
    return any(t == entity and pub._match_key(code) == key for t, code in mine)


# ---------------------------------------------------------------------------
# Folder structure: H drive -> scratch, 1:1
# ---------------------------------------------------------------------------

def _dirs(root, film):
    """Every folder of the film below root, as relative path tuples
    (film first), plus the set of those holding a workspace.mel."""
    dirs, workspaces = set(), set()
    top = os.path.join(root, film)
    if not os.path.isdir(top):
        return dirs, workspaces
    for dirpath, dirnames, filenames in os.walk(top):
        rel = (film,) + tuple(p for p in os.path.relpath(dirpath, top).split(os.sep) if p != ".")
        dirs.add(rel)
        if WORKSPACE in filenames:
            workspaces.add(rel)
    return dirs, workspaces


def _scratch_only(rel):
    return any(rel[1:1 + len(p)] == p for p in SCRATCH_ONLY)


def structure_diff(h_root, scratch_root, film):
    """How the film's folders on scratch differ from the H drive:
    {"on_scratch": the film exists on scratch,
     "missing": folders on H not on scratch (sorted rel tuples),
     "workspaces": of those + existing ones, where workspace.mel is missing,
     "gone": asset/shot projects on scratch that the H drive no longer has}."""
    h_dirs, h_ws = _dirs(h_root, film)
    s_dirs, s_ws = _dirs(scratch_root, film)
    h_projects = set(tuple(p["rel"]) for p in film_projects(h_root, film))
    s_projects = set(tuple(p["rel"]) for p in film_projects(scratch_root, film)) \
        if s_dirs else set()
    return {
        "on_scratch": bool(s_dirs),
        "missing": sorted(h_dirs - s_dirs),
        "workspaces": sorted(h_ws - s_ws),
        "gone": sorted(r for r in s_projects - h_projects if not _scratch_only(r)),
    }


def describe_diff(diff):
    """Plain-language summary of new projects in a diff, e.g. 'new shots:
    EAP_010_110; new assets: willieWagtail'."""
    new = [r for r in diff["missing"] if len(r) == 5 and r[1] == "maya"
           and r[2] in ("sequences", "assets")]
    shots = sorted(r[4] for r in new if r[2] == "sequences")
    assets = sorted(r[4] for r in new if r[2] == "assets")
    parts = []
    if shots:
        parts.append("new shots: " + ", ".join(shots))
    if assets:
        parts.append("new assets: " + ", ".join(assets))
    # Someone's first publish makes their scenes\<login>\ folder on the H
    # drive (spec §4 "Personal work folders"): name whose, and where.
    people = sorted(set((r[6], r[4]) for r in diff["missing"] if len(r) == 7 and r[1] == "maya"
                        and r[2] in ("sequences", "assets") and r[5] == "scenes"
                        and r[:5] not in new))
    if people:
        parts.append("new people's folders: " + ", ".join("%s (in %s)" % p for p in people))
    # Folders inside a new shot/asset (scenes, images...) aren't news.
    others = len([r for r in diff["missing"] if r not in new
                  and not any(r[:5] == n for n in new)
                  and not (len(r) == 7 and r[5] == "scenes" and (r[6], r[4]) in people)
                  and not (len(r) == 4 and r[1] == "maya" and r[2] in ("sequences", "assets"))])
    if others:
        parts.append("%d other new folder(s)" % others)
    return "; ".join(parts)


def update_structure(h_root, scratch_root, film, diff=None, progress=None):
    """Bring scratch in line with the H drive: create every missing folder
    and copy in missing workspace.mel files. Never removes or overwrites
    anything. Returns (folders made, workspaces copied)."""
    diff = diff or structure_diff(h_root, scratch_root, film)
    total = len(diff["missing"])
    for i, rel in enumerate(diff["missing"]):
        os.makedirs(os.path.join(scratch_root, *rel), exist_ok=True)
        if progress and (i % 50 == 0 or i == total - 1):
            progress(i + 1, total)
    for rel in diff["workspaces"]:
        src = os.path.join(h_root, *(rel + (WORKSPACE,)))
        dest = os.path.join(scratch_root, *(rel + (WORKSPACE,)))
        if not os.path.exists(dest):
            shutil.copyfile(src, dest)      # a plain, writable copy
    return len(diff["missing"]), len(diff["workspaces"])


# ---------------------------------------------------------------------------
# Setting the project
# ---------------------------------------------------------------------------

def scratch_project(scratch_root, rel):
    return os.path.join(scratch_root, *rel)


def current_project():
    return os.path.normpath(cmds.workspace(query=True, rootDirectory=True) or "")


def set_project(h_root, scratch_root, rel, login=None, progress=None):
    """Make sure the project exists on scratch (laying down the film's full
    structure first on a clean scratch drive), make scenes/<login>/, and set
    it as the Maya project. Returns (project path, what was done)."""
    h_root, scratch_root = pub.resolve_root(h_root), pub.resolve_root(scratch_root)
    pub.check_roots(h_root, scratch_root)
    film = rel[0]
    done = []
    if not os.path.isdir(os.path.join(h_root, *rel)):
        raise PublishError("%s isn't on the H drive any more." % "\\".join(rel))
    project = scratch_project(scratch_root, rel)
    if not os.path.isdir(os.path.join(scratch_root, film)):
        # Clean scratch drive: the film's whole structure, 1:1.
        folders, _ = update_structure(h_root, scratch_root, film, progress=progress)
        done.append("built %s's folder structure on scratch (%d folders)" % (film, folders))
    elif not os.path.isfile(os.path.join(project, WORKSPACE)):
        # The film is there but this project is new on the H drive: build
        # just this one. The rest of any H-drive change waits for the
        # student to say yes to the update (they're asked separately).
        diff = structure_diff(h_root, scratch_root, film)
        inside = lambda r: r[:len(rel)] == tuple(rel)
        diff = {"missing": [r for r in diff["missing"] if inside(r)],
                "workspaces": [r for r in diff["workspaces"] if inside(r)]}
        folders, _ = update_structure(h_root, scratch_root, film, diff=diff)
        done.append("made %s on scratch (%d folders)" % (rel[-1], folders))
    login = login or pub.who()
    mine = os.path.join(project, "scenes", login)
    if not os.path.isdir(mine):
        os.makedirs(mine)
        done.append("made your scenes\\%s folder" % login)
    cmds.workspace(project, openWorkspace=True)
    done.append("Maya project set")
    return project, done
