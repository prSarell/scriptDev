"""
renderSub — render a shot on this machine, review it, then publish the
frames to the H drive and a review movie to ShotGrid. shotSub's sibling for
renders (user, 2026-11-13). Design: filmPipeline_spec.md "renderSub".

    render      Render.exe (Arnold) in the background, from the saved scene:
                <shot>\\images\\lighting\\<login>\\<login>_render_v###\\
                    <shot>_<login>_render_v###.####.exr
                    <shot>_<login>_render_v###.mp4        (rvio, for review)
                    <shot>_<login>_render_v###.thumb.jpg
                    render.json                           (what was rendered)
    review      play the mp4 in RV; delete or render again
    publish     copy the version to the same place on the H drive (checked,
                read-only), then a ShotGrid Version on the Shot's Lighting
                task with the movie, pointing at the frames on H. A render
                that stopped early (cancelled, failed, or interrupted by a
                crash or power cut) publishes the frames that finished.

Renders stay on scratch until published: H holds only publishes (PIPE_RULES
rule 3), and rendering straight to a server or SharePoint H is slow and can
leave half-written frames. The render is headless and described by
render.json, so a render farm can take it over later (spec "Where the
processing runs").

No UI here: renderSub_ui.py is the window; the tests drive this directly.
"""

import os
import re
import sys
import json
import glob
import time
import shutil
import platform
import subprocess
from datetime import datetime

import maya.cmds as cmds

import publishTool_api as pub
import publishTool_camera as cam_api
import pipeEnv

PublishError = pub.PublishError

DEPARTMENT = "lighting"      # images\lighting\<login>\ (spec "Render output"),
                             # whichever department the render comes from
# The department a render comes from: the artist picks it (user, 2026-11-14).
# It is recorded in render.json and on the ShotGrid Version only; the output
# folder and the Lighting task stay the same for every department.
DEPARTMENTS = pub.DEPARTMENTS
CODE = "render"
TASK = "Lighting"            # the ShotGrid Task on the Shot
IMAGE_FORMAT = "exr"
PADDING = 4
INFO_NAME = "render.json"
LOG_NAME = "render.log"
RESOLUTIONS = (100, 50, 25)  # percent of the render settings' size
FRAME_MODES = ("shot", "check", "custom", "step", "list")
CHECK_FRAMES = 5     # the lighting check: start, end, middle and halfway either side
SEQUENCE, BATCH = "sequence", "batch"     # in this Maya / Render.exe (see render_in_maya)
FLOW = "flow"        # Flow Render, Autodesk's cloud (renderSub_flow.py)
# render.json "status". INTERRUPTED: still "rendering" but nothing is
# rendering it any more (Maya crashed, the power went; user, 2026-11-13).
RENDERING, DONE, CANCELLED, FAILED, INTERRUPTED = (
    "rendering", "done", "cancelled", "failed", "interrupted")
STOPPED = (CANCELLED, FAILED, INTERRUPTED)
# QUEUED: a batch render waiting for the one before it (RenderQueue, or
# Scout's render service). PAUSED: Scout has suspended its Render.exe.
QUEUED, PAUSED = "queued", "paused"
ACTIVE = (RENDERING, QUEUED, PAUSED)
MAYA_CLOSED = "Maya was closed"


# ---------------------------------------------------------------------------
# Which shot, and where its renders go
# ---------------------------------------------------------------------------

def shot_of(scene_path, h_root):
    """The shot the saved scene is in, with this person's render folders:
    {"film", "seq", "shot", "shot_project", "login", "local", "h"}.
    Refuses a scene opened from the H drive: renders are made on scratch."""
    if not scene_path:
        raise PublishError("Save the scene first: renderSub renders the saved file.")
    ctx = cam_api.shot_context(scene_path)
    h_root = pub.resolve_root(h_root)
    if not h_root:
        raise PublishError("The H drive location isn't set yet. Set it in the Project or "
                           "Publish tool first.")
    if pub._same_path(ctx["root"], h_root):
        raise PublishError("This scene is open from the H drive. Build the shot onto your "
                           "scratch drive and render from there.")
    login = pub.who()
    rel = ["images", DEPARTMENT, login]
    ctx.update(login=login, h_root=h_root,
               local=os.path.join(ctx["shot_project"], *rel),
               h=os.path.join(h_root, ctx["film"], "maya", "sequences", ctx["seq"],
                              ctx["shot"], *rel))
    return ctx


def department_of(scene_path):
    """The department of the scene's scenes\\<dept>\\ folder, else Lighting.
    Only the dropdown's starting choice: the artist can change it."""
    parts = [p.lower() for p in os.path.normpath(scene_path or "").split(os.sep)]
    if "scenes" in parts[:-2]:
        folder = parts[len(parts) - parts[::-1].index("scenes")]     # the one after scenes
        for _, code in DEPARTMENTS:
            if code.lower() == folder:
                return code
    return DEPARTMENT


def department_label(code):
    return dict((c, label) for label, c in DEPARTMENTS).get(code, code or "?")


def version_name(ctx, number):
    return "%s_%s_v%03d" % (ctx["login"], CODE, number)


def image_prefix(ctx, folder):
    """<shot>_<login>_render_v### for the frames, movie and thumbnail."""
    return "%s_%s" % (ctx["shot"], os.path.basename(folder))


def version_numbers(folder, login):
    pattern = re.compile(r"^%s_%s_v(\d{3})$" % (re.escape(login), CODE))
    try:
        names = os.listdir(folder)
    except OSError:
        return []
    return sorted(int(m.group(1)) for m in map(pattern.match, names)
                  if m and os.path.isdir(os.path.join(folder, m.group(0))))


def next_version(ctx):
    """One series across scratch and H, so a local v004 publishes as v004
    and never lands on top of someone else's (versions are per person)."""
    used = version_numbers(ctx["local"], ctx["login"]) + version_numbers(ctx["h"], ctx["login"])
    return os.path.join(ctx["local"], version_name(ctx, max(used or [0]) + 1))


def local_versions(ctx):
    """[{"name", "path", "info"}], newest first."""
    found = []
    for n in reversed(version_numbers(ctx["local"], ctx["login"])):
        path = os.path.join(ctx["local"], version_name(ctx, n))
        info = ensure_render_id(path, read_info(path))
        found.append({"name": os.path.basename(path), "path": path, "info": info})
    return found


def read_info(folder):
    try:
        with open(os.path.join(folder, INFO_NAME)) as f:
            return json.load(f)
    except (IOError, OSError, ValueError):
        return {}


def write_info(folder, info):
    with open(os.path.join(folder, INFO_NAME), "w") as f:
        json.dump(info, f, indent=2)
    if info.get("render_id"):
        write_ledger(dict(info, folder=folder))


# ---------------------------------------------------------------------------
# Render IDs (user, 2026-11-19: "give every render a unique render id so we
# can find and track this stuff"; file names stay as they are). The ID is in
# render.json, the shot's history, the ShotGrid Version's note, and the
# header of every EXR the render writes (Arnold driver custom attribute), so
# a frame that turns up anywhere can be told whose it is. A small ledger on
# the scratch drive (one file per render) says where each one is; H isn't
# used for it (PIPE_RULES 3: nothing saves to H except Publish), and a
# published render's render.json on H carries its ID anyway.
# ---------------------------------------------------------------------------

ID_ATTR = "renderSub/render_id"      # the EXR header attribute
ID_INDEX = 900                       # driver.customAttributes[] slot renderSub uses
LEDGER = ("data", "renderSub", "renders")    # under <scratch>\<film>\maya\


def new_render_id(shot, when=None):
    """R20261119-171454-SEQ010_170-9f3a: when it was planned, the shot, and
    a random tag, so it is never reused (version numbers can be)."""
    when = when or datetime.now()
    return "R%s-%s-%s" % (when.strftime("%Y%m%d-%H%M%S"), shot, os.urandom(2).hex())


def ensure_render_id(folder, info):
    """Give a version made before render IDs one (from when it started), and
    save it. Returns the info."""
    if info and not info.get("render_id") and info.get("shot"):
        try:
            when = datetime.fromisoformat(info.get("started") or "")
        except ValueError:
            when = None
        info["render_id"] = new_render_id(info["shot"], when)
        try:
            write_info(folder, info)
        except (IOError, OSError):
            pass
    return info


def ledger_dir(info):
    """<scratch>\\<film>\\maya\\data\\renderSub\\renders\\ for the render's
    film (scratch root from the scene), else beside the shot."""
    root = pipeEnv.root_of(info.get("scene") or "") if info.get("scene") else None
    if root and info.get("film"):
        return os.path.join(root, info["film"], "maya", *LEDGER)
    return os.path.join(info.get("project") or info["folder"], *LEDGER)


LEDGER_KEYS = ("render_id", "shot", "seq", "film", "login", "version", "folder", "scene",
               "department", "camera", "size", "how", "where", "status", "started", "finished",
               "missing")


def write_ledger(info):
    """The render's line in the ledger: what it is, where its folder is and
    how it stands. Never fails a render."""
    entry = dict((k, info.get(k)) for k in LEDGER_KEYS)
    entry["frames"] = len(info.get("frames") or [])
    entry["range"] = seq_string(info["frames"]) if info.get("frames") else ""
    entry["published"] = info.get("published")
    entry["flow"] = info.get("flow")
    entry["updated"] = _now()
    try:
        folder = ledger_dir(info)
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, info["render_id"] + ".json"), "w") as f:
            json.dump(entry, f, indent=2)
    except (IOError, OSError, KeyError):
        pass


def ledger_folders(roots=None):
    """Every film's ledger folder on the given scratch roots (default: the
    open scene's scratch root and the pipe's $PIPE_SCRATCH)."""
    if not roots:
        roots = [pipeEnv.root_of(cmds.file(query=True, sceneName=True) or ""), pipeEnv.current()]
    found = []
    for root in [r for r in roots if r]:
        for path in glob.glob(os.path.join(glob.escape(root), "*", "maya", *LEDGER)):
            if os.path.isdir(path) and not any(_same(path, f) for f in found):
                found.append(path)
    return found


def read_ledger(roots=None):
    """[entry], newest first, from every ledger on the roots."""
    entries = []
    for folder in ledger_folders(roots):
        for path in glob.glob(os.path.join(glob.escape(folder), "R*.json")):
            try:
                with open(path) as f:
                    entries.append(json.load(f))
            except (IOError, OSError, ValueError):
                pass
    return sorted(entries, key=lambda e: e.get("render_id") or "", reverse=True)


def find_render(render_id, roots=None):
    """The ledger entry for an ID (a unique start of one is enough), with
    "frames_found" counted from its folder, or None."""
    render_id = render_id.strip()
    hits = [e for e in read_ledger(roots) if (e.get("render_id") or "").startswith(render_id)]
    if len(hits) != 1:
        return None
    entry = hits[0]
    info = read_info(entry.get("folder") or "")
    entry["frames_found"] = len(frame_files(dict(info, folder=entry["folder"]))) if info else 0
    return entry


def describe_render(entry):
    """Lines for the artist about a ledger entry or published render.json."""
    total = entry.get("frames")
    total = len(total) if isinstance(total, list) else total
    lines = ["Render %s" % entry.get("render_id"),
             "%s %s, %s, from %s" % (entry.get("shot"), entry.get("version"),
                                     entry.get("login"), department_label(entry.get("department"))),
             "Status: %s (%s, %s)" % (entry.get("status"), HOW_LABELS.get(entry.get("how"),
                                                                          entry.get("how")),
                                      (entry.get("where") or {}).get("machine", "?")),
             "Started %s%s" % (entry.get("started"), ", finished %s" % entry["finished"]
                               if entry.get("finished") else "")]
    if "frames_found" in entry:
        lines.append("%s of %s frame(s) in its folder" % (entry["frames_found"], total))
    lines.append(("On the H drive: " if entry.get("on_h") else "Folder: ") + (entry.get("folder") or "?"))
    pub_ = entry.get("published")
    if pub_:
        lines.append("Published %s to %s%s" % (
            pub_.get("at"), pub_.get("dest"),
            " (ShotGrid Version %s)" % pub_["sg_version_id"] if pub_.get("sg_version_id") else ""))
    elif not entry.get("on_h"):
        lines.append("Not published yet.")
    return "\n".join(lines)


def find_published(render_id, h_root):
    """A published render on H with this ID (a unique start is enough):
    {"render_id", "shot", "version", "folder", "published", ...} from its
    render.json, or None. Only reads H."""
    render_id = render_id.strip()
    pattern = os.path.join(glob.escape(h_root), "*", "maya", "sequences", "*", "*", "images",
                           DEPARTMENT, "*", "*", INFO_NAME)
    hits = []
    for path in glob.glob(pattern):
        info = read_info(os.path.dirname(path))
        if (info.get("render_id") or "").startswith(render_id):
            hits.append(dict(info, folder=os.path.dirname(path), on_h=True))
    return hits[0] if len(hits) == 1 else None


def exr_attribute(path, name=ID_ATTR):
    """A string attribute from an EXR's (first) header, or None. Reads only
    the header, so it's quick on big frames."""
    try:
        with open(path, "rb") as f:
            if f.read(4) != b"\x76\x2f\x31\x01":
                return None
            f.read(4)                                   # version and flags
            for _ in range(200):
                attr = _cstring(f)
                if not attr:
                    return None
                kind = _cstring(f)
                size = int.from_bytes(f.read(4), "little")
                value = f.read(size)
                if attr == name:
                    return value.split(b"\0")[0].decode("utf-8", "replace") if kind == "string" else None
    except (IOError, OSError):
        return None
    return None


def _cstring(f, limit=256):
    out = b""
    while len(out) < limit:
        c = f.read(1)
        if not c or c == b"\0":
            break
        out += c
    return out.decode("ascii", "replace")


_VERSION_DIR = re.compile(r"_%s_v\d{3}$" % CODE)


def frames_with_id(render_id, folders, depth=4):
    """EXRs under the folders whose header carries this render ID. Version
    folders are skipped (their frames are theirs), which keeps a search of
    a shot's images\\ quick."""
    found = []
    for top in folders:
        if not os.path.isdir(top):
            continue
        for root, dirs, names in os.walk(top):
            dirs[:] = [d for d in dirs if not _VERSION_DIR.search(d)]
            if os.path.relpath(root, top).count(os.sep) >= depth:
                dirs[:] = []
            for n in names:
                if n.lower().endswith(".exr"):
                    path = os.path.join(root, n)
                    if exr_attribute(path) == render_id:
                        found.append(path)
    return sorted(found)


def id_mel(render_id):
    """MEL that stamps the render ID into every Arnold driver's EXR header
    (Render.exe -preRender: the batch render's scene copy)."""
    return ('for ($d in `ls -type aiAOVDriver`) setAttr -type "string" '
            '($d + ".customAttributes[%d]") "STRING %s %s";' % (ID_INDEX, ID_ATTR, render_id))


# ---------------------------------------------------------------------------
# Which frames
# ---------------------------------------------------------------------------

def shot_range():
    return (int(round(cmds.playbackOptions(query=True, minTime=True))),
            int(round(cmds.playbackOptions(query=True, maxTime=True))))


def parse_frame_list(text):
    """'1001, 1050 1100-1105' -> [1001, 1050, 1100, ..., 1105]. Ranges as
    a-b or a..b."""
    frames = set()
    for token in re.split(r"[,\s]+", (text or "").strip()):
        if not token:
            continue
        m = re.match(r"^(\d+)(?:(?:-|\.\.)(\d+))?$", token)
        if not m:
            raise PublishError("'%s' isn't a frame number or a range like 1001-1010." % token)
        a, b = int(m.group(1)), int(m.group(2) or m.group(1))
        frames.update(range(min(a, b), max(a, b) + 1))
    return sorted(frames)


def frames_for(mode, start=None, end=None, step=1, text=""):
    """The frames to render. shot: the timeline; check: a lighting check
    across the timeline (check_frames); custom: start-end; step: every Nth
    frame from start, always ending on end; list: the typed frames."""
    if mode == "list":
        frames = parse_frame_list(text)
    elif mode == "check":
        frames = check_frames(*shot_range())
    else:
        if mode == "shot":
            start, end = shot_range()
        if start is None or end is None or end < start:
            raise PublishError("The end frame is before the start frame.")
        step = max(1, int(step)) if mode == "step" else 1
        frames = list(range(start, end + 1, step))
        if frames[-1] != end:
            frames.append(end)
    if not frames:
        raise PublishError("No frames to render.")
    return frames


def check_frames(start, end, count=CHECK_FRAMES):
    """A lighting check across the shot without rendering all of it (user,
    2026-11-13, after seeing a 5-frame test of SEQ010_140): the start, the
    end, the middle and the frames halfway between the middle and each
    end, evenly spread whatever the shot's length. 1001-1118 ->
    1001, 1030, 1060, 1089, 1118. A shot shorter than that renders every
    frame once."""
    if end < start:
        raise PublishError("The end frame is before the start frame.")
    return sorted({int(round(start + i * (end - start) / float(count - 1)))
                   for i in range(count)})


def seq_string(frames):
    """Render.exe's -seq: runs compressed, '1001..1010 1050'."""
    runs, frames = [], sorted(set(frames))
    start = prev = frames[0]
    for f in frames[1:] + [None]:
        if f is not None and f == prev + 1:
            prev = f
            continue
        runs.append(str(start) if start == prev else "%d..%d" % (start, prev))
        start = prev = f
    return " ".join(runs)


# ---------------------------------------------------------------------------
# Camera and size
# ---------------------------------------------------------------------------

def cameras():
    """Camera transforms to offer, the shot camera first: a camera in a
    published camera group, then renderable cameras, then the rest.
    Maya's top/front/side are left out."""
    found = []
    for shape in cmds.ls(type="camera", long=True) or []:
        transform = cmds.listRelatives(shape, parent=True, fullPath=True)[0]
        if cmds.camera(shape, query=True, startupCamera=True) and \
                not transform.endswith("|persp"):
            continue
        rank = 0 if cam_api.camera_in_group(transform) else (
            1 if cmds.getAttr(shape + ".renderable") else 2)
        if transform.endswith("|persp"):
            rank = 3
        found.append((rank, transform))
    return [t for _, t in sorted(found)]


def render_size(percent=100):
    """(width, height) at percent of the render settings, rounded down to
    even numbers (the H.264 review movie needs them even)."""
    w = cmds.getAttr("defaultResolution.width") * percent / 100.0
    h = cmds.getAttr("defaultResolution.height") * percent / 100.0
    return max(2, int(w) // 2 * 2), max(2, int(h) // 2 * 2)


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------

def ensure_arnold():
    """Arnold's render options must be in the saved scene, or Render.exe
    fails ("No object matches name: defaultArnoldDriver.aiTranslator") in
    a scene that never had Arnold set up. Makes them if missing; returns
    True when the scene changed (so it needs saving)."""
    if not cmds.pluginInfo("mtoa", query=True, loaded=True):
        try:
            cmds.loadPlugin("mtoa", quiet=True)
        except RuntimeError:
            raise PublishError("Arnold (mtoa) won't load on this machine, so it can't render.")
    if cmds.objExists("defaultArnoldDriver") and cmds.objExists("defaultArnoldRenderOptions"):
        return False
    import mtoa.core
    mtoa.core.createOptions()
    return True


def render_exe():
    name = "Render.exe" if os.name == "nt" else "Render"
    location = os.environ.get("MAYA_LOCATION") or os.path.dirname(os.path.dirname(sys.executable))
    path = os.path.join(location, "bin", name)
    if not os.path.isfile(path):
        raise PublishError("Maya's batch renderer wasn't found at %s." % path)
    return path


def frame_path(folder, prefix, frame):
    return os.path.join(folder, "%s.%0*d.%s" % (prefix, PADDING, frame, IMAGE_FORMAT))


BEAUTY = "beauty"


def frames_folder(info):
    """Where a version's beauty frames are. A scene with AOVs (e.g. Arnold's
    denoising AOVs) makes Arnold write each AOV to its own subfolder, the
    beauty included: <version>\\beauty\\, <version>\\N_noice\\, ... (SEQ010_140
    rendered all 118 frames that way 2026-11-16 and was marked failed because
    only the version folder was checked)."""
    sub = os.path.join(info["folder"], BEAUTY)
    return sub if os.path.isdir(sub) else info["folder"]


def beauty_path(info, frame):
    """A frame's beauty EXR, wherever Arnold put it (see frames_folder)."""
    return frame_path(frames_folder(info), info["prefix"], frame)


def render_command(info):
    folder = info["folder"]
    w, h = info["size"]
    # -cam must come first: MtoA's -cam handler sets the options string
    # ($opt="-cam ...") instead of adding to it, so an earlier -seq is lost
    # and Render.exe falls back to the scene's own frame range (found
    # 2026-11-13, Maya 2025 / MtoA 5.4, with Render.exe -test).
    return [render_exe(), "-r", "arnold", "-cam", info["camera"],
            "-proj", info["project"],
            "-rd", folder, "-im", info["prefix"],
            "-of", IMAGE_FORMAT, "-fnc", "name.#.ext", "-pad", str(PADDING),
            # render_frames: what's left when Scout restarts a stopped render.
            "-seq", seq_string(info.get("render_frames") or info["frames"]),
            "-x", str(w), "-y", str(h),
            # Without an Arnold batch licence Arnold aborts; render with its
            # watermark instead and say so (see watermarked()).
            "-ai:alf", "false", "-ai:lve", "1",
            "-log", os.path.join(folder, LOG_NAME)] + (
            ["-preRender", id_mel(info["render_id"])] if info.get("render_id") else []) + [
            scene_to_render(info)]


# ---------------------------------------------------------------------------
# The scene: versioned up, and a copy rendered (user, 2026-11-19: "render
# saves a copy for sure"; "save and version up the file it is rendering from
# and not just save over")
# ---------------------------------------------------------------------------

_NUMBERED = re.compile(r"^(.*?)(\d+)$")


def version_up_path(path):
    """The next free version of a working file: NFW_SEQ010_170_001.ma ->
    NFW_SEQ010_170_002.ma (past any number already in the folder); a name
    with no number gets _001."""
    folder, name = os.path.split(path)
    stem, ext = os.path.splitext(name)
    m = _NUMBERED.match(stem)
    base, width = (m.group(1), len(m.group(2))) if m else (stem + "_", 3)
    pattern = re.compile(r"^%s(\d+)%s$" % (re.escape(base), re.escape(ext)), re.IGNORECASE)
    try:
        used = [int(p.group(1)) for p in map(pattern.match, os.listdir(folder or ".")) if p]
    except OSError:
        used = []
    number = max(used + [int(m.group(2)) if m else 0]) + 1
    return os.path.join(folder, "%s%0*d%s" % (base, width, number, ext))


def save_version_up():
    """Save the open scene as its next version and carry on in that one.
    Returns the new path."""
    scene = cmds.file(query=True, sceneName=True)
    if not scene:
        raise PublishError("Save the scene first: renderSub renders the saved file.")
    path = version_up_path(os.path.normpath(scene))
    kind = "mayaBinary" if path.lower().endswith(".mb") else "mayaAscii"
    cmds.file(rename=path.replace("\\", "/"))
    cmds.file(save=True, type=kind)
    return os.path.normpath(cmds.file(query=True, sceneName=True))


def copy_scene(info):
    """Copy the saved scene into the version folder: the copy is what
    renders (Render.exe) and what's published with the frames, so later
    saves of the working file don't change the render."""
    name = os.path.basename(info["scene"])
    shutil.copy2(info["scene"], os.path.join(info["folder"], name))
    info["scene_copy"] = name
    write_info(info["folder"], info)
    return info


def scene_to_render(info):
    """The version's own copy of the scene, else (older versions) the
    working file."""
    copy = info.get("scene_copy")
    path = os.path.join(info["folder"], copy) if copy else ""
    return path if copy and os.path.isfile(path) else info["scene"]


def plan_render(ctx, scene_path, frames, camera, percent=100, how=BATCH, department=None):
    """Make the next version folder and its render.json. Nothing renders yet.
    how: SEQUENCE (in this Maya), BATCH (Render.exe) or FLOW (the cloud).
    department: the code the render comes from (default: the scene's folder)."""
    if not cmds.objExists(camera):
        raise PublishError("The camera '%s' isn't in the scene." % camera)
    folder = next_version(ctx)
    os.makedirs(folder)
    info = {
        "render_id": new_render_id(ctx["shot"]),
        "shot": ctx["shot"], "seq": ctx["seq"], "film": ctx["film"], "login": ctx["login"],
        "department": department or department_of(scene_path),
        "version": os.path.basename(folder), "folder": folder,
        "prefix": image_prefix(ctx, folder),
        "scene": os.path.normpath(scene_path), "project": ctx["shot_project"],
        "camera": cmds.ls(camera)[0], "frames": sorted(set(frames)),
        "percent": percent, "size": list(render_size(percent)),
        "fps": pub._scene_fps(), "maya": cmds.about(version=True),
        "where": where(CLOUD if how == FLOW else LOCAL), "how": how, "status": RENDERING, "started": _now(), "started_ts": time.time(),
        # The process doing the render (this Maya; RenderJob swaps in
        # Render.exe), so a render nobody is running any more can be told
        # from one still going (see settle).
        "pid": os.getpid(),
    }
    write_info(folder, info)
    return info


# ---------------------------------------------------------------------------
# Render times: measured from when each frame's file was written, kept per
# shot, and used to predict the next render (user, 2026-11-13: "a predicted
# render time per frame based on where the render was being done eg locally
# or in the future on the render farm").
# ---------------------------------------------------------------------------

LOCAL, FARM, CLOUD = "local", "farm", "cloud"
WHERE_LABELS = {LOCAL: "This computer", FARM: "Render farm", CLOUD: "Flow Render (cloud)"}
CLOUD_MACHINE = "Flow Render"
HISTORY_KEEP = 20


def where(kind=LOCAL):
    """Where a render runs: {"kind": "local"/"farm"/"cloud", "machine"}.
    Estimates only use renders from the same place (a farm node isn't a
    laptop)."""
    if kind == CLOUD:
        return {"kind": kind, "machine": CLOUD_MACHINE}
    machine = os.environ.get("COMPUTERNAME") or platform.node() or "unknown"
    return {"kind": kind, "machine": machine}


def cloud_timing(info):
    """A cloud render's frames all arrive together when it's downloaded, so
    file times say nothing. Its time is the turnaround instead: submit to
    download, spread over the frames (what an artist waits for)."""
    frames = finished_frames(info)
    if not frames or not info.get("started_ts"):
        return None
    elapsed = max(0.0, time.time() - info["started_ts"])
    return {"done": len(frames), "per_frame": elapsed / len(frames), "startup": 0.0}


def frame_files(info):
    """The frames on disk, in render order (Render.exe renders -seq in
    ascending order)."""
    paths = (beauty_path(info, f) for f in info["frames"])
    return [p for p in paths if os.path.isfile(p)]


def finished_frames(info):
    """The frames that rendered whole, in render order. A render that
    stopped early (STOPPED) may have left its last frame half-written:
    Arnold makes the EXR when the frame starts (a power cut left a 4 KB
    file, 2026-11-13). That last file counts if it's at least half the
    usual size of the others; with nothing to compare it to, only an
    in-Maya cancel (which stops between frames) keeps it."""
    present = [(f, beauty_path(info, f)) for f in info["frames"]]
    present = [(f, p) for f, p in present if os.path.isfile(p)]
    if not present or info.get("status") not in STOPPED:
        return [f for f, _ in present]
    rest, (last, path) = present[:-1], present[-1]
    if rest:
        sizes = sorted(os.path.getsize(p) for _, p in rest)
        whole = os.path.getsize(path) >= sizes[len(sizes) // 2] * 0.5
    else:
        whole = info["status"] == CANCELLED and info.get("how") == SEQUENCE
    return [f for f, _ in rest] + ([last] if whole else [])


def partial(info):
    """True when a stopped render has only some of its frames."""
    return info.get("status") != DONE and finished_frames(info) != list(info["frames"])


def _alive(pid):
    """True while the process is running (PIDs are reused, so this can be
    fooled, but only into keeping a version marked rendering)."""
    if not pid:
        return False
    if os.name == "nt":
        import ctypes
        kernel = ctypes.windll.kernel32
        handle = kernel.OpenProcess(0x1000, False, int(pid))    # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        code = ctypes.c_ulong()
        ok = kernel.GetExitCodeProcess(handle, ctypes.byref(code))
        kernel.CloseHandle(handle)
        return bool(ok) and code.value == 259                   # STILL_ACTIVE
    try:
        os.kill(int(pid), 0)
    except OSError:
        return False
    return True


def _same(a, b):
    return os.path.normcase(os.path.normpath(a)) == os.path.normcase(os.path.normpath(b))


def settle(info, running_folder=None):
    """A version still marked rendering (or queued) that nothing is
    rendering any more (this machine's render process is gone, it was
    rendered on another machine, or the queue holding it went with Maya) is
    marked interrupted, and its finished frames timed, so it can be
    published. running_folder: the version(s) this session is rendering or
    has queued (a folder or a list). Returns the info, updated or not."""
    if info.get("status") not in ACTIVE or not info.get("folder"):
        return info
    running = [running_folder] if isinstance(running_folder, str) else (running_folder or [])
    if any(_same(r, info["folder"]) for r in running):
        return info
    if in_cloud(info):
        return info         # in the cloud: it carries on with Maya closed (renderSub_flow)
    here = (info.get("where") or {}).get("machine") == where()["machine"]
    if here and info.get("pid") not in (None, os.getpid()) and _alive(info["pid"]):
        return info         # another Maya (its queue) or Render.exe on this machine has it
    if info.get("status") == RENDERING and info.get("how") == BATCH \
            and log_completed(info) and not missing_frames(info):
        return finish_render(info, 0)   # Render.exe finished with nothing watching it
    return finish_render(info, None, interrupted=True)


def log_completed(info):
    """True when the render log says Maya's batch render reached the end
    ("Scene <path> completed.")."""
    try:
        with open(os.path.join(info["folder"], LOG_NAME), errors="replace") as f:
            return any(line.startswith("Scene ") and line.rstrip().endswith(" completed.")
                       for line in f)
    except (IOError, OSError):
        return False


def in_cloud(info):
    """True for a cloud render the cloud has taken, its frames still to come
    back (renderSub_flow: they download into the version folder). One still
    uploading when Maya closed never got there, and settles as interrupted."""
    return (info.get("how") == FLOW and info.get("status") == RENDERING
            and (info.get("flow") or {}).get("state") == "in the cloud")


def frames_done(info, running=False):
    """Finished frames. Arnold creates a frame's EXR when it starts the frame
    and writes into it as it renders (seen 2026-11-13), so while the render
    runs the newest file is the frame in progress."""
    n = len(frame_files(info))
    return max(0, n - 1) if running else n


def _created(path):
    """When a file was created (Windows, macOS), or None where the system
    doesn't keep it."""
    st = os.stat(path)
    birth = getattr(st, "st_birthtime", None)
    return birth if birth else (st.st_ctime if os.name == "nt" else None)


def timing(info, running=False):
    """{"done", "per_frame", "startup"} in seconds from the finished frames,
    or None before the first one finishes. A frame finishes at its file's
    last write. per_frame = the gap between finished frames (it includes
    Maya's per-frame work, not just Arnold's); with only one finished, that
    frame's own time (last write minus creation). startup = loading Maya
    and the scene before the first frame started."""
    if running:
        done = frame_files(info)[:-1]
    else:
        done = [beauty_path(info, f) for f in finished_frames(info)]
    if not done or not info.get("started_ts"):
        return None
    ends = [os.path.getmtime(p) for p in done]
    created = _created(done[0])
    if len(ends) > 1:
        per_frame = (ends[-1] - ends[0]) / (len(ends) - 1)
    else:
        per_frame = ends[0] - (created or info["started_ts"])
    startup = created - info["started_ts"] if created else ends[0] - info["started_ts"] - per_frame
    return {"done": len(done), "per_frame": max(0.0, per_frame), "startup": max(0.0, startup)}


def time_left(info, running=True):
    """Seconds until the render finishes, or None until a frame is done."""
    t = timing(info, running)
    return None if not t else (len(info["frames"]) - t["done"]) * t["per_frame"]


def history_path(shot_project):
    return os.path.join(shot_project, "data", "renderSub", "history.json")


def read_history(shot_project):
    try:
        with open(history_path(shot_project)) as f:
            return json.load(f)
    except (IOError, OSError, ValueError):
        return []


def record_timing(info):
    """Add a finished render's timing to the shot's history (kept apart from
    the version folders, so pruning old renders keeps their times)."""
    t = info.get("timing") if "timing" in info else timing(info)
    if not t or t["done"] < 1:
        return
    entry = {"render_id": info.get("render_id"),
             "version": info["version"], "login": info["login"], "at": _now(),
             "where": info.get("where") or where(), "how": info.get("how", BATCH),
             "size": info["size"],
             "frames": t["done"], "per_frame": round(t["per_frame"], 2),
             "startup": round(t["startup"], 2)}
    history = (read_history(info["project"]) + [entry])[-HISTORY_KEEP:]
    path = history_path(info["project"])
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(history, f, indent=2)
    except (IOError, OSError):
        pass        # an estimate is a nicety; never fail a render over it


def predict(shot_project, frame_count, size, kind=LOCAL, machine=None, how=None):
    """Estimate a render from this shot's earlier renders in the same place:
    {"per_frame", "startup", "total", "based_on", "this_machine"} or None.
    Render time is taken as proportional to the pixel count, so a 25% test
    predicts a full-size render (16x the pixels). This machine's renders
    are preferred; other machines of the same kind are the fallback.
    how (SEQUENCE/BATCH): prefer renders made the same way; a sequence
    render has no start-up (Maya already has the scene loaded)."""
    machine = machine or where(kind)["machine"]
    same_kind = [e for e in read_history(shot_project)
                 if (e.get("where") or {}).get("kind") == kind and e.get("per_frame")]
    if how:
        same_kind = [e for e in same_kind if e.get("how", BATCH) == how] or same_kind
    mine = [e for e in same_kind if e["where"].get("machine") == machine]
    entries = (mine or same_kind)[-5:]
    if not entries:
        return None
    pixels = float(size[0] * size[1])
    per = sorted(e["per_frame"] * pixels / (e["size"][0] * e["size"][1]) for e in entries)
    startup = sorted(e["startup"] for e in entries)
    per_frame, startup = per[len(per) // 2], startup[len(startup) // 2]
    if how == SEQUENCE:
        startup = 0.0
    return {"per_frame": per_frame, "startup": startup,
            "total": startup + per_frame * frame_count,
            "based_on": len(entries), "this_machine": bool(mine)}


def duration(seconds):
    """42 -> '42 s', 400 -> '6 min 40 s', 7300 -> '2 h 1 min'."""
    seconds = int(round(seconds))
    if seconds < 60:
        return "%d s" % seconds
    if seconds < 3600:
        m, s = divmod(seconds, 60)
        return "%d min %d s" % (m, s) if s and m < 10 else "%d min" % m
    h, m = divmod(seconds // 60, 60)
    return "%d h %d min" % (h, m) if m else "%d h" % h


# ---------------------------------------------------------------------------
# Two ways to render (user, 2026-11-13: "a check box for a sequence render and
# a batch render ... the default needs to be sequence. I am not sure the
# students have batch render available at RMIT right now"):
#   sequence  inside this Maya, like Render > Render Sequence. Maya's own
#             licence covers it (no watermark); Maya is busy until it's done.
#   batch     Render.exe in the background (RenderJob below). Maya stays
#             free, but Arnold needs a batch licence or watermarks.
# ---------------------------------------------------------------------------

HOW_LABELS = {SEQUENCE: "In Maya (Render Sequence)",
              BATCH: "In the background (batch render)",
              FLOW: "Flow Render (cloud)"}


class _SequenceSettings(object):
    """Point the scene's render output at the version folder for an in-Maya
    render, then put every setting back, and the scene's saved/unsaved state
    with them, so the artist's render settings are left as they were."""

    def __init__(self, info):
        self.values = {
            "defaultRenderGlobals.imageFilePrefix": os.path.join(info["folder"], info["prefix"]).replace("\\", "/"),
            "defaultRenderGlobals.animation": 1,
            "defaultRenderGlobals.outFormatControl": 0,
            "defaultRenderGlobals.putFrameBeforeExt": 1,
            "defaultRenderGlobals.periodInExt": 1,
            "defaultRenderGlobals.extensionPadding": PADDING,
            "defaultArnoldDriver.aiTranslator": IMAGE_FORMAT,
            # Arnold in Maya renders at the render settings' size, whatever
            # size it's asked for.
            "defaultResolution.width": info["size"][0],
            "defaultResolution.height": info["size"][1],
        }
        # Only the chosen camera renderable, as Render.exe's -cam does
        # (arnoldMakeCameraRenderable).
        chosen = set(cmds.listRelatives(info["camera"], shapes=True, fullPath=True, type="camera") or [])
        for shape in cmds.ls(type="camera", long=True) or []:
            self.values[shape + ".renderable"] = int(shape in chosen)
        # The render ID in every frame's EXR header (see Render IDs).
        self.stamps = {}
        if info.get("render_id"):
            for driver in cmds.ls(type="aiAOVDriver") or []:
                self.stamps["%s.customAttributes[%d]" % (driver, ID_INDEX)] = "STRING %s %s" % (
                    ID_ATTR, info["render_id"])
        self.saved = {}

    def __enter__(self):
        self.modified = cmds.file(query=True, modified=True)
        for attr, value in self.values.items():
            self.saved[attr] = cmds.getAttr(attr)
            _set(attr, value)
        self.saved_stamps = {}
        for plug, value in self.stamps.items():
            node = plug.split(".")[0]
            had = ID_INDEX in (cmds.getAttr(node + ".customAttributes", multiIndices=True) or [])
            self.saved_stamps[plug] = cmds.getAttr(plug) if had else None
            cmds.setAttr(plug, value, type="string")
        return self

    def __exit__(self, *exc):
        for attr, value in self.saved.items():
            _set(attr, value)
        for plug, value in self.saved_stamps.items():
            if value is None:
                cmds.removeMultiInstance(plug, b=True)
            else:
                cmds.setAttr(plug, value, type="string")
        cmds.file(modified=self.modified)
        return False


def _set(attr, value):
    """setAttr by the attribute's own type: an unset string (an empty image
    prefix reads back as None) is put back as ""."""
    if cmds.getAttr(attr, type=True) == "string":
        cmds.setAttr(attr, value or "", type="string")
    else:
        cmds.setAttr(attr, value)


def render_in_maya(info, progress=None):
    """Render the version's frames in this Maya session, one frame at a
    time. progress(done, total) is called before each frame and after the
    last; returning False stops the render (Esc in the progress bar).
    Returns the finished info, as RenderJob.finish() does.

    arnoldRender's batch flag writes the frame to the render settings' file
    name (the interactive call, Render Sequence's, added "_1" to it), and in
    a Maya with its UI it's still covered by Maya's licence: no watermark
    (both checked 2026-11-13, Maya 2025, no Arnold batch licence)."""
    total, cancelled = len(info["frames"]), False
    with _SequenceSettings(info):
        for i, frame in enumerate(info["frames"]):
            if progress and progress(i, total) is False:
                cancelled = True
                break
            cmds.currentTime(frame)
            cmds.arnoldRender(batch=True, seq=str(frame), cam=info["camera"])
        if progress and not cancelled:
            progress(total, total)
    return finish_render(info, 0, cancelled)


class RenderJob(object):
    """A background Render.exe for one version. poll() is None while it
    runs; then finish() makes the review movie and records the result."""

    def __init__(self, info):
        self.info = info
        self.cancelled = False
        env = dict(os.environ)
        # References are written as $PIPE_SCRATCH/<film>/... by Build.
        root = pipeEnv.root_of(info["scene"])
        if root:
            env[pipeEnv.VAR] = pipeEnv._clean(root)
        flags = 0
        if os.name == "nt":
            # Below normal priority keeps the artist's Maya responsive.
            flags = subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS
        self.process = subprocess.Popen(
            render_command(info), env=env, cwd=info["folder"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
        # Render.exe keeps going if Maya closes, so it's the one to watch.
        info["pid"] = self.process.pid
        write_info(info["folder"], info)

    def frames_done(self):
        return frames_done(self.info, running=self.poll() is None)

    def poll(self):
        return self.process.poll()

    def cancel(self):
        self.cancelled = True
        if self.poll() is None:
            if os.name == "nt":     # Render.exe starts mayabatch: stop the whole tree
                subprocess.call(["taskkill", "/T", "/F", "/PID", str(self.process.pid)],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                self.process.kill()
        self.process.wait()

    def finish(self):
        return finish_render(self.info, self.process.returncode, self.cancelled)


class RenderQueue(object):
    """Every render this Maya is running or holding, from any shot (user,
    2026-11-19: "kick of a cloud render, work in another shot and either
    cue another cloud render or do a batch render locally or a que of batch
    renders"). Batch renders run one at a time, the rest wait (QUEUED);
    cloud renders are Flow Render's to queue (it uploads one at a time) and
    don't hold up a batch render. step() moves it on; the window calls it
    on a timer. start_batch: a stand-in for RenderJob in the tests."""

    def __init__(self, start_batch=None):
        self.jobs = []          # running: RenderJob / renderSub_flow.FlowJob
        self.waiting = []       # queued batch renders' infos, in order
        self._start_batch = start_batch or RenderJob

    def batch_running(self):
        return any(j.info.get("how") == BATCH and j.poll() is None for j in self.jobs)

    def add_batch(self, info):
        """Start a planned batch render, or queue it behind the running one.
        Returns its RenderJob, or None when it's queued."""
        if self.batch_running() or self.waiting:
            info["status"] = QUEUED
            write_info(info["folder"], info)
            self.waiting.append(info)
            return None
        return self._start(info)

    def add(self, job):
        """A job that's already running (a cloud render)."""
        self.jobs.append(job)
        return job

    def _start(self, info):
        info.update(status=RENDERING, started=_now(), started_ts=time.time())
        write_info(info["folder"], info)
        return self.add(self._start_batch(info))

    def step(self):
        """Finish the jobs that are done and start the next batch render.
        Returns the finished versions' infos."""
        finished = []
        for job in list(self.jobs):
            if job.poll() is not None:
                self.jobs.remove(job)
                finished.append(job.finish())
        if self.waiting and not self.batch_running():
            self._start(self.waiting.pop(0))
        return finished

    def folders(self):
        return [j.info["folder"] for j in self.jobs] + [i["folder"] for i in self.waiting]

    def busy(self):
        return bool(self.jobs or self.waiting)

    def place(self, folder):
        """1 for the next batch render to start, 2 after it...; None when
        it isn't waiting."""
        for n, info in enumerate(self.waiting, 1):
            if _same(info["folder"], folder):
                return n
        return None

    def job(self, folder):
        return next((j for j in self.jobs if _same(j.info["folder"], folder)), None)

    def cancel(self, folder):
        """Cancel a running or waiting render. Returns a note for the artist,
        or None. A running one is finished on the next step()."""
        for info in self.waiting:
            if _same(info["folder"], folder):
                self.waiting.remove(info)
                finish_render(info, None, cancelled=True)
                return None
        job = self.job(folder)
        return job.cancel() if job else None

    def stop_for_quit(self):
        """Maya is closing (user, 2026-11-19: cloud renders carry on, batch
        renders don't). Stops the batch renders, marks the waiting ones and
        any cloud render still uploading interrupted, and returns a line per
        render stopped, to warn about next time Maya starts."""
        lines = []
        for job in list(self.jobs):
            info = job.info
            if info.get("how") == FLOW and in_cloud(info):
                continue            # the cloud has it; its frames still come back
            if getattr(job, "carries_on", False):
                continue            # Scout's render service has it, not this Maya
            if info.get("how") == BATCH and job.poll() is None:
                job.cancel()
            info["stopped_why"] = MAYA_CLOSED
            finish_render(info, None, interrupted=True)
            lines.append(_stopped_line(info))
            self.jobs.remove(job)
        for info in self.waiting:
            info["stopped_why"] = MAYA_CLOSED
            finish_render(info, None, interrupted=True)
            lines.append(_stopped_line(info))
        self.waiting = []
        return lines

    def cloud_folders(self):
        return [j.info["folder"] for j in self.jobs if in_cloud(j.info)]


def _stopped_line(info):
    done = len(finished_frames(info))
    if info.get("how") == FLOW:
        what = "the cloud render was still uploading, so it never reached the cloud"
    elif done:
        what = "%d of %d frame(s) had finished: publish them from Local Versions, or render again" % (
            done, len(info["frames"]))
    else:
        what = "no frames had finished: render it again"
    return "%s %s was stopped when Maya was closed; %s." % (info["shot"], info["version"], what)


# What a closed Maya leaves for the next one: renders it stopped (warned at
# startup) and cloud renders still to come back (watched again). Kept in
# Maya's prefs, so per person and machine.
JOBS_FILE = "renderSub_jobs.json"


def _jobs_path():
    return os.path.join(cmds.internalVar(userPrefDir=True), JOBS_FILE)


def read_jobs():
    try:
        with open(_jobs_path()) as f:
            saved = json.load(f)
    except (IOError, OSError, ValueError):
        saved = {}
    return {"stopped": saved.get("stopped") or [], "cloud": saved.get("cloud") or []}


def write_jobs(stopped=None, cloud=None):
    saved = read_jobs()
    if stopped is not None:
        saved["stopped"] = stopped
    if cloud is not None:
        saved["cloud"] = cloud
    try:
        with open(_jobs_path(), "w") as f:
            json.dump(saved, f, indent=2)
    except (IOError, OSError):
        pass


def warn_stopped_renders():
    """At Maya startup (pipeEnv.install): say which renders were stopped
    when Maya last closed, in the Script Editor, then forget them."""
    lines = read_jobs()["stopped"]
    for line in lines:
        cmds.warning("renderSub: " + line)
    if lines:
        write_jobs(stopped=[])
    return lines


def missing_frames(info):
    return [f for f in info["frames"] if not os.path.isfile(beauty_path(info, f))]


def finish_render(info, returncode, cancelled=False, interrupted=False):
    """Record how the render went; make the movie and thumbnail when every
    frame is there (a stopped render's movie is made when it's published).
    interrupted: nothing was left running it (see settle). Returns the
    updated info."""
    if interrupted:
        info["status"] = INTERRUPTED
    elif cancelled:
        info["status"] = CANCELLED
    elif missing_frames(info):
        info["status"] = FAILED
    else:
        info["status"] = DONE
    finished = finished_frames(info)
    info["missing"] = [f for f in info["frames"] if f not in finished]
    info["finished"] = _now()
    info["returncode"] = returncode
    info["watermarked"] = watermarked(info)
    info["timing"] = cloud_timing(info) if info.get("how") == FLOW else timing(info)
    record_timing(info)         # stopped renders still timed their frames
    if info["status"] == DONE:
        info["movie_problem"] = make_review_media(info)
    write_info(info["folder"], info)
    return info


WATERMARK_TEXT = "rendering with watermarks"
NO_LICENCE_HELP = (
    "Arnold had no batch-render licence on this machine, so these frames carry "
    "Arnold's watermark. Maya's own licence covers rendering inside Maya, not "
    "background renders. Fine for checking lighting; for final frames render on a "
    "machine with an Arnold licence.")


def watermarked(info):
    """True when the render log says Arnold had no licence (frames carry
    its watermark)."""
    try:
        with open(os.path.join(info["folder"], LOG_NAME), errors="replace") as f:
            return any(WATERMARK_TEXT in line for line in f)
    except (IOError, OSError):
        return False


def log_tail(info, lines=15):
    """The end of the render log, to show why a render failed."""
    try:
        with open(os.path.join(info["folder"], LOG_NAME), errors="replace") as f:
            return "".join(f.readlines()[-lines:])
    except (IOError, OSError):
        return ""


# ---------------------------------------------------------------------------
# Review movie
# ---------------------------------------------------------------------------

def movie_path(info):
    return os.path.join(info["folder"], info["prefix"] + ".mp4")


def thumbnail_path(info):
    return os.path.join(info["folder"], info["prefix"] + ".thumb.jpg")


def _rvio(args):
    return subprocess.run(args, capture_output=True, text=True,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def make_review_media(info):
    """EXRs -> an sRGB H.264 mp4 and a middle-frame thumbnail, with RV's
    rvio (as shotSub), from the frames that finished. Records which frames
    the movie holds in info["movie_frames"] (the caller writes render.json).
    Returns None, or why there's no movie."""
    rvio = pub.find_rvio()
    if not rvio:
        return "RV's rvio wasn't found on this machine, so there's no review movie."
    frames = finished_frames(info)
    if not frames:
        return "No frames finished rendering."
    info["movie_frames"] = frames
    folder, prefix = frames_folder(info), info["prefix"]
    contiguous = frames == list(range(frames[0], frames[-1] + 1))
    # A gap-free range is one sequence; step and list renders are
    # separate frames played one after another.
    sources = ([os.path.join(folder, "%s.%d-%d#.%s" % (prefix, frames[0], frames[-1], IMAGE_FORMAT))]
               if contiguous else [frame_path(folder, prefix, f) for f in frames])
    w, h = info["size"]
    result = _rvio([rvio] + sources + ["-outsrgb", "-outres", str(w), str(h),
                                       "-o", movie_path(info), "-codec", "libx264",
                                       "-fps", str(info["fps"])])
    _rvio([rvio, frame_path(folder, prefix, frames[len(frames) // 2]), "-outsrgb",
           "-o", thumbnail_path(info)])
    if result.returncode or not os.path.isfile(movie_path(info)):
        output = (result.stdout or "") + (result.stderr or "")
        sgc = _quiet_shotgrid()
        return ((sgc.rvio_problem(output) if sgc and hasattr(sgc, "rvio_problem") else None)
                or "RV couldn't make the review movie:\n" + output.strip()[-400:])
    return None


RV_TAG = "renderSub"


def rv_media(info):
    """What RV loads to show a version's frames (full-quality EXRs): one
    sequence for a gap-free range, else each frame (step and list renders
    play one after another). [] when no frames are on disk. A stopped
    render's half-written last frame is left out."""
    frames = finished_frames(info)
    if not frames:
        return []
    if frames == list(range(frames[0], frames[-1] + 1)):
        return [os.path.join(frames_folder(info), "%s.%d-%d#.%s"
                             % (info["prefix"], frames[0], frames[-1], IMAGE_FORMAT))]
    return [beauty_path(info, f) for f in frames]


def find_rvpush():
    rvio = pub.find_rvio()
    path = os.path.join(os.path.dirname(rvio), "rvpush.exe" if os.name == "nt" else "rvpush") \
        if rvio else ""
    return path if path and os.path.isfile(path) else ""


def push_to_rv(media, tries=20):
    """Show media in renderSub's own RV window (rvpush, tag "renderSub"),
    starting RV if it isn't open; the same window is reused next time.
    Blocks while a new RV starts, so call it off Maya's main thread.
    Returns None, or why it failed.

    As shotSub found: when no tagged RV is running, rvpush starts one but
    may not hand it the media (exit 15), so retry until the new RV listens,
    with spawning switched off so only one RV ever starts.

    The first call (the one that may start RV) doesn't capture rvpush's
    output: the RV it starts inherits those pipes and holds them open until
    it quits, so reading them would wait for RV to close (found 2026-11-13:
    Play in RV hung with no error)."""
    rvpush = find_rvpush()
    if not rvpush:
        return "RV (rvpush) wasn't found on this machine."
    command = [rvpush, "-tag", RV_TAG, "set"] + list(media)
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    no_spawn = dict(os.environ, RVPUSH_RV_EXECUTABLE_PATH="none")
    for attempt in range(tries):
        if attempt == 0:
            code = subprocess.call(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, creationflags=flags)
            output = ""
        else:
            result = subprocess.run(command, capture_output=True, text=True, env=no_spawn,
                                    stdin=subprocess.DEVNULL, creationflags=flags)
            code, output = result.returncode, (result.stderr or result.stdout or "").strip()
        if code == 0:
            return None
        if code == 15 or (code == 11 and attempt > 0):
            time.sleep(1)
            continue
        return "RV didn't take the frames (rvpush exit %d)%s" % (code, ": " + output if output else ".")
    return "RV started but didn't take the frames in %d s." % tries


def _quiet_shotgrid():
    try:
        import shotgridConnect
        return shotgridConnect
    except ImportError:
        return None


# ---------------------------------------------------------------------------
# Local versions: delete, prune
# ---------------------------------------------------------------------------

def delete_version(folder):
    shutil.rmtree(folder)


def prune(ctx, keep, running=None):
    """Delete the oldest local versions beyond keep (None = keep all).
    Published ones are safe on H; returns the names of unpublished ones
    deleted, so the caller can say so. running: the versions this Maya is
    rendering or has queued (see settle); they, and any still rendering
    elsewhere or in the cloud, are kept."""
    if keep is None or keep < 0:
        return []
    lost = []
    for v in local_versions(ctx)[keep:]:
        info = settle(dict(v["info"], folder=v["path"]), running)
        if in_cloud(info) or info.get("status") in ACTIVE:
            continue        # rendering, queued, or in the cloud (its frames come back here)
        if not info.get("published"):
            lost.append(v["name"])
        shutil.rmtree(v["path"], ignore_errors=True)
    return lost


# ---------------------------------------------------------------------------
# Publish: H drive, then ShotGrid
# ---------------------------------------------------------------------------

def _published_files(info):
    """Everything in the version folder but the log and any frame that
    didn't finish (a stopped render's half-written last frame), as paths
    relative to it. AOV subfolders (beauty\\, N_noice\\, ...; see
    frames_folder) go too, holding only the finished frames: anything else
    in a subfolder (anything renderSub didn't make) stays on scratch."""
    folder = info["folder"]
    frames = {os.path.basename(frame_path(folder, info["prefix"], f)) for f in info["frames"]}
    whole = {os.path.basename(frame_path(folder, info["prefix"], f)) for f in finished_frames(info)}
    files = []
    for n in os.listdir(folder):
        path = os.path.join(folder, n)
        if os.path.isfile(path):
            if n != LOG_NAME and (n not in frames or n in whole):
                files.append(n)
        elif os.path.isdir(path):
            files += [os.path.join(n, f) for f in os.listdir(path)
                      if f in whole and os.path.isfile(os.path.join(path, f))]
    return sorted(files)


def copy_to_h(info, dest):
    """Copy the version's files (and AOV subfolders) to dest, check every
    one arrived whole, then make them read-only. A folder left by an
    earlier copy that broke off is finished, not duplicated."""
    os.makedirs(dest, exist_ok=True)
    names = _published_files(info)
    for name in names:
        src, dst = os.path.join(info["folder"], name), os.path.join(dest, name)
        if os.path.isfile(dst) and os.path.getsize(dst) == os.path.getsize(src):
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.isfile(dst):
            os.chmod(dst, 0o666)
        shutil.copy2(src, dst)
    short = [n for n in names
             if not os.path.isfile(os.path.join(dest, n))
             or os.path.getsize(os.path.join(dest, n)) != os.path.getsize(os.path.join(info["folder"], n))]
    if short:
        raise PublishError("These files didn't copy to the H drive whole: %s\nPublish again "
                           "to finish the copy." % ", ".join(short[:5]))
    for root, _, files in os.walk(dest):
        for name in files:
            pub._lock(os.path.join(root, name))


def find_shot_and_task(ctx):
    """The ShotGrid Shot matching the shot folder, and its Lighting Task
    (None if the shot has none yet)."""
    shot = cam_api.find_shotgrid_shot(ctx, ctx["h_root"])
    return shot, pub.task_on(shot, TASK)


def version_ctx(info, ctx=None):
    """The shot a version was rendered in, which isn't always the open
    scene's: a background render can finish after the artist has opened
    another shot (2026-11-19: Publish would have sent it to that shot's H
    folder and ShotGrid Shot). ctx is used when it is the same shot."""
    ctx = ctx or {}
    if (ctx.get("film"), ctx.get("shot")) == (info.get("film"), info.get("shot")):
        return ctx
    if not info.get("scene"):
        raise PublishError("%s doesn't say which shot it was rendered in (render.json "
                           "has no scene), so it can't be published."
                           % info.get("version", os.path.basename(info.get("folder", ""))))
    return shot_of(info["scene"], ctx.get("h_root") or pub.get_root(pub.H_DRIVE))


def scene_note(info, dest):
    """The ShotGrid note's lines naming the scene the frames came from
    (user, 2026-11-19: "the file the shot was rendered from should be
    listed"): its copy on H, published with the frames, and the working
    file it was saved as."""
    working = os.path.basename(info["scene"])
    if info.get("scene_copy"):
        return "Rendered from (on the H drive):\n%s\nWorking file: %s" % (
            os.path.join(dest, info["scene_copy"]), working)
    return "Scene: %s" % working


def publish(ctx, folder, notes="", lookup=find_shot_and_task, shotgrid=None, running=None):
    """Publish one local version: all of it, or for a render that stopped
    early (cancelled, failed, interrupted) the frames that finished (user,
    2026-11-13: "There are to many times when a render might not finish for
    whatever reason. This shouldn't mean the existing rendered frames can't
    be published"). Refuses one still rendering or with no finished frames.
    ShotGrid is looked up before H is written; if only the ShotGrid upload
    fails, the H copy stays and publishing again retries the upload.
    Returns {"dest", "sg_version", "sg_error", "warnings", "partial"}.

    running: the versions this Maya is rendering or has queued (see settle).
    lookup / shotgrid: stand-ins for the tests."""
    info = read_info(folder)
    if not info:
        raise PublishError("%s has no render.json, so it can't be published."
                           % os.path.basename(folder))
    info["folder"] = folder         # the drive may have changed since the render
    ctx = version_ctx(info, ctx)
    info = settle(info, running)
    if info["status"] in ACTIVE:
        raise PublishError("%s is still %s. Wait for it, or cancel it."
                           % (info["version"], info["status"]))
    frames = finished_frames(info)
    if not frames:
        raise PublishError("%s has no finished frames to publish (%s)."
                           % (info["version"], info["status"]))
    is_partial = partial(info)
    if not os.path.isfile(movie_path(info)) or info.get("movie_frames", frames) != frames:
        # A stopped render's movie is made now, from the frames it has.
        info["movie_problem"] = make_review_media(info)
        write_info(folder, info)
    if info.get("movie_problem") or not os.path.isfile(movie_path(info)):
        raise PublishError("%s has no review movie. %s\nFix RV, then publish again."
                           % (info["version"], info.get("movie_problem") or ""))
    sgc = shotgrid or pub._shotgrid()
    shot, task = lookup(ctx)
    result = {"dest": os.path.join(ctx["h"], info["version"]), "sg_version": None,
              "sg_error": None, "warnings": [], "partial": is_partial}
    if not task:
        result["warnings"].append(
            "The ShotGrid shot %s has no %s task, so this Version isn't on a task "
            "(staff: add a %s task to the shot)." % (ctx["shot"], TASK, TASK))

    copy_to_h(info, result["dest"])
    info["published"] = {"at": _now(), "by": ctx["login"], "dest": result["dest"], "frames": frames}
    write_info(folder, info)

    note = ("Render %s from %s: %d frame(s) (%s), camera %s, %dx%d (%d%%)\n"
            "Frames on the H drive:\n%s\n%s") % (
        "%s (render ID %s)" % (info["version"], info["render_id"]) if info.get("render_id")
        else info["version"], department_label(info.get("department")), len(frames), seq_string(frames),
        info["camera"].split("|")[-1], info["size"][0], info["size"][1], info["percent"],
        result["dest"], scene_note(info, result["dest"]))
    if is_partial:
        note = "Partial render (%s): %d of %d frame(s) finished; %s was asked for.\n%s" % (
            info["status"], len(frames), len(info["frames"]), seq_string(info["frames"]), note)
    if notes.strip():
        note = notes.strip() + "\n\n---\n" + note
    try:
        version = sgc.upload_playblast(
            "Shot", shot["id"], result["dest"], files=[],
            movie_path=os.path.join(result["dest"], os.path.basename(movie_path(info))),
            thumbnail_path=os.path.join(result["dest"], os.path.basename(thumbnail_path(info))),
            notes=note, fps=info["fps"], task_id=task["id"] if task else None)
    except Exception as e:
        result["sg_error"] = str(e)
    else:
        result["sg_version"] = version
        info["published"]["sg_version_id"] = (version or {}).get("id")
        write_info(folder, info)
    return result


def _now():
    return datetime.now().isoformat(timespec="seconds")
