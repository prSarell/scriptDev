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
                task with the movie, pointing at the frames on H

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

DEPARTMENT = "lighting"      # images\lighting\<login>\ (spec "Render output")
CODE = "render"
TASK = "Lighting"            # the ShotGrid Task on the Shot
IMAGE_FORMAT = "exr"
PADDING = 4
INFO_NAME = "render.json"
LOG_NAME = "render.log"
RESOLUTIONS = (100, 50, 25)  # percent of the render settings' size
FRAME_MODES = ("shot", "custom", "step", "list")
SEQUENCE, BATCH = "sequence", "batch"     # in this Maya / Render.exe (see render_in_maya)


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
        found.append({"name": os.path.basename(path), "path": path, "info": read_info(path)})
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
    """The frames to render. shot: the timeline; custom: start-end; step:
    every Nth frame from start, always ending on end (test renders across
    the shot); list: the typed frames."""
    if mode == "list":
        frames = parse_frame_list(text)
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
            "-seq", seq_string(info["frames"]),
            "-x", str(w), "-y", str(h),
            # Without an Arnold batch licence Arnold aborts; render with its
            # watermark instead and say so (see watermarked()).
            "-ai:alf", "false", "-ai:lve", "1",
            "-log", os.path.join(folder, LOG_NAME),
            info["scene"]]


def plan_render(ctx, scene_path, frames, camera, percent=100, how=BATCH):
    """Make the next version folder and its render.json. Nothing renders yet.
    how: SEQUENCE (in this Maya) or BATCH (Render.exe)."""
    if not cmds.objExists(camera):
        raise PublishError("The camera '%s' isn't in the scene." % camera)
    folder = next_version(ctx)
    os.makedirs(folder)
    info = {
        "shot": ctx["shot"], "seq": ctx["seq"], "film": ctx["film"], "login": ctx["login"],
        "version": os.path.basename(folder), "folder": folder,
        "prefix": image_prefix(ctx, folder),
        "scene": os.path.normpath(scene_path), "project": ctx["shot_project"],
        "camera": cmds.ls(camera)[0], "frames": sorted(set(frames)),
        "percent": percent, "size": list(render_size(percent)),
        "fps": pub._scene_fps(), "maya": cmds.about(version=True),
        "where": where(), "how": how, "status": "rendering", "started": _now(), "started_ts": time.time(),
    }
    write_info(folder, info)
    return info


# ---------------------------------------------------------------------------
# Render times: measured from when each frame's file was written, kept per
# shot, and used to predict the next render (user, 2026-11-13: "a predicted
# render time per frame based on where the render was being done eg locally
# or in the future on the render farm").
# ---------------------------------------------------------------------------

LOCAL, FARM = "local", "farm"
WHERE_LABELS = {LOCAL: "This computer", FARM: "Render farm"}
HISTORY_KEEP = 20


def where(kind=LOCAL):
    """Where a render runs: {"kind": "local"/"farm", "machine"}. Estimates
    only use renders from the same place (a farm node isn't a laptop)."""
    machine = os.environ.get("COMPUTERNAME") or platform.node() or "unknown"
    return {"kind": kind, "machine": machine}


def frame_files(info):
    """The frames on disk, in render order (Render.exe renders -seq in
    ascending order)."""
    paths = (frame_path(info["folder"], info["prefix"], f) for f in info["frames"])
    return [p for p in paths if os.path.isfile(p)]


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
    files = frame_files(info)
    done = files[:-1] if running else files
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
    t = timing(info)
    if not t or t["done"] < 1:
        return
    entry = {"version": info["version"], "login": info["login"], "at": _now(),
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
              BATCH: "In the background (batch render)"}


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
        self.saved = {}

    def __enter__(self):
        self.modified = cmds.file(query=True, modified=True)
        for attr, value in self.values.items():
            self.saved[attr] = cmds.getAttr(attr)
            _set(attr, value)
        return self

    def __exit__(self, *exc):
        for attr, value in self.saved.items():
            _set(attr, value)
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


def missing_frames(info):
    return [f for f in info["frames"]
            if not os.path.isfile(frame_path(info["folder"], info["prefix"], f))]


def finish_render(info, returncode, cancelled=False):
    """Record how the render went; make the movie and thumbnail when every
    frame is there. Returns the updated info."""
    info["missing"] = missing_frames(info)
    info["finished"] = _now()
    info["returncode"] = returncode
    info["watermarked"] = watermarked(info)
    info["timing"] = timing(info)
    record_timing(info)         # cancelled and failed renders still timed their frames
    if cancelled:
        info["status"] = "cancelled"
    elif info["missing"]:
        info["status"] = "failed"
    else:
        info["status"] = "done"
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
    rvio (as shotSub). Returns None, or why there's no movie."""
    rvio = pub.find_rvio()
    if not rvio:
        return "RV's rvio wasn't found on this machine, so there's no review movie."
    frames = info["frames"]
    folder, prefix = info["folder"], info["prefix"]
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
    play one after another). [] when no frames are on disk."""
    frames = [f for f in info["frames"]
              if os.path.isfile(frame_path(info["folder"], info["prefix"], f))]
    if not frames:
        return []
    if frames == list(range(frames[0], frames[-1] + 1)):
        return [os.path.join(info["folder"], "%s.%d-%d#.%s"
                             % (info["prefix"], frames[0], frames[-1], IMAGE_FORMAT))]
    return [frame_path(info["folder"], info["prefix"], f) for f in frames]


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


def prune(ctx, keep):
    """Delete the oldest local versions beyond keep (None = keep all).
    Published ones are safe on H; returns the names of unpublished ones
    deleted, so the caller can say so."""
    if keep is None or keep < 0:
        return []
    lost = []
    for v in local_versions(ctx)[keep:]:
        if not v["info"].get("published"):
            lost.append(v["name"])
        shutil.rmtree(v["path"], ignore_errors=True)
    return lost


# ---------------------------------------------------------------------------
# Publish: H drive, then ShotGrid
# ---------------------------------------------------------------------------

def _published_files(folder):
    return sorted(n for n in os.listdir(folder)
                  if os.path.isfile(os.path.join(folder, n)) and n != LOG_NAME)


def copy_to_h(info, dest):
    """Copy the version's files to dest, check every one arrived whole,
    then make them read-only. A folder left by an earlier copy that broke
    off is finished, not duplicated."""
    os.makedirs(dest, exist_ok=True)
    for name in _published_files(info["folder"]):
        src, dst = os.path.join(info["folder"], name), os.path.join(dest, name)
        if os.path.isfile(dst) and os.path.getsize(dst) == os.path.getsize(src):
            continue
        if os.path.isfile(dst):
            os.chmod(dst, 0o666)
        shutil.copy2(src, dst)
    short = [n for n in _published_files(info["folder"])
             if not os.path.isfile(os.path.join(dest, n))
             or os.path.getsize(os.path.join(dest, n)) != os.path.getsize(os.path.join(info["folder"], n))]
    if short:
        raise PublishError("These files didn't copy to the H drive whole: %s\nPublish again "
                           "to finish the copy." % ", ".join(short[:5]))
    for name in os.listdir(dest):
        pub._lock(os.path.join(dest, name))


def find_shot_and_task(ctx):
    """The ShotGrid Shot matching the shot folder, and its Lighting Task
    (None if the shot has none yet)."""
    shot = cam_api.find_shotgrid_shot(ctx, ctx["h_root"])
    return shot, pub.task_on(shot, TASK)


def publish(ctx, folder, notes="", lookup=find_shot_and_task, shotgrid=None):
    """Publish one finished local version. Refuses a render that isn't
    complete. ShotGrid is looked up before H is written; if only the
    ShotGrid upload fails, the H copy stays and publishing again retries
    the upload. Returns {"dest", "sg_version", "sg_error", "warnings"}.

    lookup / shotgrid: stand-ins for the tests."""
    info = read_info(folder)
    info["folder"] = folder         # the drive may have changed since the render
    if info.get("status") != "done" or missing_frames(info):
        raise PublishError("%s isn't a finished render (%s). Only complete renders publish."
                           % (os.path.basename(folder), info.get("status", "no render.json")))
    if not os.path.isfile(movie_path(info)):
        raise PublishError("%s has no review movie. %s\nFix RV, then render again."
                           % (info["version"], info.get("movie_problem") or ""))
    sgc = shotgrid or pub._shotgrid()
    shot, task = lookup(ctx)
    result = {"dest": os.path.join(ctx["h"], info["version"]), "sg_version": None,
              "sg_error": None, "warnings": []}
    if not task:
        result["warnings"].append(
            "The ShotGrid shot %s has no %s task, so this Version isn't on a task "
            "(staff: add a %s task to the shot)." % (ctx["shot"], TASK, TASK))

    copy_to_h(info, result["dest"])
    info["published"] = {"at": _now(), "by": ctx["login"], "dest": result["dest"]}
    write_info(folder, info)

    note = "Render %s: %d frame(s) (%s), camera %s, %dx%d (%d%%)\nFrames on the H drive:\n%s\nScene: %s" % (
        info["version"], len(info["frames"]), seq_string(info["frames"]),
        info["camera"].split("|")[-1], info["size"][0], info["size"][1], info["percent"],
        result["dest"], os.path.basename(info["scene"]))
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
