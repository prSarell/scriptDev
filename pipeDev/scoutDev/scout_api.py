"""
Scout: every render in one place (user, 2026-11-20: "a render log tool
separate to renderSub that tracks all the renders, allows you to pause,
restart or kill a render ... from the one interface. The tool could point
to different projects and show all the renders just for that project and
down the track it would help students manage their renders on the render
farm"). Named after the film's character.

Three parts:

    scout_service.py   one per Maya version on each machine, in its own
                       mayapy. It owns the batch-render queue, so closing
                       Maya, or a shelf click reloading renderSub, can't lose
                       a render (2026-11-20: a night's queue was lost that
                       way). Runs one Render.exe at a time.
    scout_ui.py        the Scout window (plain mayapy + PySide6, no Maya
                       scene): a project's renders, with Pause, Resume,
                       Kill, Restart, Load in RV and Publish.
    scout_api.py       this: the shared pieces. Also renderSub's way in
                       (ScoutJob): renderSub hands its batch renders over.

What a render is stays in renderSub's files: render.json in the version
folder is the truth, and the film's ledger
(<scratch>/<film>/maya/data/renderSub/renders/<render id>.json) lists them
all. Scout's own state is per machine, in %LOCALAPPDATA%/scout (SCOUT_HOME
overrides it, for the tests):

    services/<maya>/service.json  the running service: pid, heartbeat
    services/<maya>/queue.json    its queue: running folder, waiting folders
    services/<maya>/inbox/        commands for it, one JSON file each
    services/<maya>/service.log   what it did
    settings.json                 the window's projects and choices

Decided with the user 2026-11-20: Pause/Resume/Kill/Restart for batch
renders on this machine; cloud (Flow) and in-Maya renders are shown, with
RV and Publish but no controls. Sims come later as another job kind
(KINDS), cached in the background.
"""

import os
import sys
import json
import glob
import time
import uuid
import shutil
import subprocess

import renderSub_api as rs

KINDS = ("render",)                 # later: "cache" (background sim caching)
HEARTBEAT_S = 2.0
STALE_S = 30.0                      # a heartbeat older than this: the service is gone
IDLE_EXIT_S = 15 * 60               # the service quits after this long with nothing to do
SERVICE_SCRIPT = "scout_service.py"
WORKER_SCRIPT = "scout_worker.py"

PAUSE, RESUME, KILL, RESTART, SUBMIT, QUIT = "pause", "resume", "kill", "restart", "submit", "quit"
RV, PUBLISH = "rv", "publish"
CONTROLS = (PAUSE, RESUME, KILL, RESTART)


class ScoutError(Exception):
    pass


# ---------------------------------------------------------------------------
# Where Scout keeps its state
# ---------------------------------------------------------------------------

def home():
    root = os.environ.get("SCOUT_HOME")
    if not root:
        if os.environ.get("LOCALAPPDATA"):
            base = os.environ["LOCALAPPDATA"]
        elif sys.platform == "darwin":
            base = os.path.expanduser("~/Library/Application Support")
        else:
            base = os.path.expanduser("~/.local/share")
        root = os.path.join(base, "scout")
    return root


def service_dir(maya):
    return os.path.join(home(), "services", str(maya))


def _read_json(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except (IOError, OSError, ValueError):
        return default


def _write_json(path, data):
    """Written to a temporary file then swapped in, so a reader never sees
    half a file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = "%s.%s.tmp" % (path, os.getpid())
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def read_settings():
    return _read_json(os.path.join(home(), "settings.json"), {}) or {}


def write_settings(settings):
    _write_json(os.path.join(home(), "settings.json"), settings)


# ---------------------------------------------------------------------------
# Processes: is it running, pause, resume, kill (with Render.exe's children)
# ---------------------------------------------------------------------------

alive = rs._alive


def _children_nt():
    """{parent pid: [child pids]} for every process (Toolhelp snapshot)."""
    import ctypes
    from ctypes import wintypes

    class ENTRY(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                    ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
                    ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long),
                    ("dwFlags", wintypes.DWORD), ("szExeFile", ctypes.c_wchar * 260)]

    kernel = ctypes.windll.kernel32
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    snap = kernel.CreateToolhelp32Snapshot(0x2, 0)          # TH32CS_SNAPPROCESS
    tree = {}
    if not snap or snap == wintypes.HANDLE(-1).value:
        return tree
    try:
        entry = ENTRY()
        entry.dwSize = ctypes.sizeof(ENTRY)
        ok = kernel.Process32FirstW(snap, ctypes.byref(entry))
        while ok:
            tree.setdefault(entry.th32ParentProcessID, []).append(entry.th32ProcessID)
            ok = kernel.Process32NextW(snap, ctypes.byref(entry))
    finally:
        kernel.CloseHandle(snap)
    return tree


def process_tree(pid):
    """pid and everything it started (Render.exe starts mayabatch), parent
    first."""
    if os.name != "nt":
        return [pid]
    tree, found, todo = _children_nt(), [], [int(pid)]
    while todo:
        p = todo.pop(0)
        if p not in found:
            found.append(p)
            todo.extend(c for c in tree.get(p, []) if c != p)
    return found


def _suspend(pids, resume=False):
    if os.name != "nt":
        import signal
        for p in pids:
            try:
                os.kill(p, signal.SIGCONT if resume else signal.SIGSTOP)
            except OSError:
                pass
        return
    import ctypes
    kernel, ntdll = ctypes.windll.kernel32, ctypes.windll.ntdll
    call = ntdll.NtResumeProcess if resume else ntdll.NtSuspendProcess
    for p in pids:
        handle = kernel.OpenProcess(0x0800, False, int(p))     # PROCESS_SUSPEND_RESUME
        if handle:
            try:
                call(handle)
            finally:
                kernel.CloseHandle(handle)


def pause_process(pid):
    _suspend(process_tree(pid))


def resume_process(pid):
    _suspend(list(reversed(process_tree(pid))), resume=True)


def kill_process(pid):
    """The process and its children. A paused one is resumed first, so it
    can be stopped cleanly."""
    pids = process_tree(pid)
    _suspend(pids, resume=True)
    if os.name == "nt":
        subprocess.call(["taskkill", "/T", "/F", "/PID", str(pid)],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        for p in reversed(pids):
            try:
                os.kill(p, 9)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# The service: is it running, start it, send it commands
# ---------------------------------------------------------------------------

def mayapy_for(maya):
    """This Maya version's mayapy, or "" when it isn't installed."""
    here = os.path.dirname(sys.executable)
    names = ("mayapy.exe", "mayapy") if os.name == "nt" else ("mayapy",)
    location = os.environ.get("MAYA_LOCATION") or os.path.dirname(here)
    if str(maya) in os.path.basename(os.path.normpath(location)):
        for n in names:
            if os.path.isfile(os.path.join(location, "bin", n)):
                return os.path.join(location, "bin", n)
    for pattern in (r"C:\Program Files\Autodesk\Maya%s\bin\mayapy.exe",
                    "/Applications/Autodesk/maya%s/Maya.app/Contents/bin/mayapy",
                    "/usr/autodesk/maya%s/bin/mayapy"):
        path = pattern % maya
        if os.path.isfile(path):
            return path
    return ""


def lock_path(maya):
    return os.path.join(service_dir(maya), "lock")


def lock_holder(maya):
    """The pid of the service holding this Maya version's lock (it may
    still be loading Maya), or None."""
    try:
        with open(lock_path(maya)) as f:
            pid = int(f.read().strip() or 0)
    except (IOError, OSError, ValueError):
        return None
    return pid if alive(pid) else None


def service_state(maya):
    """service.json for this Maya version's service when it's running, else
    None."""
    state = _read_json(os.path.join(service_dir(maya), "service.json"))
    if not state or not alive(state.get("pid")):
        return None
    if time.time() - state.get("heartbeat", 0) > STALE_S:
        return None
    return state


def services():
    """Every service running on this machine: [state]."""
    found = []
    for path in glob.glob(os.path.join(glob.escape(os.path.join(home(), "services")), "*")):
        state = service_state(os.path.basename(path))
        if state:
            found.append(state)
    return found


def _script(name):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), name)


def _detached():
    if os.name != "nt":
        return {"start_new_session": True}
    return {"creationflags": subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
            | 0x00000008}       # DETACHED_PROCESS: it outlives the Maya that started it


def start_service(maya):
    """Start this Maya version's service unless it's running. Returns its
    pid (the new one may still be loading Maya for a few seconds)."""
    state = service_state(maya)
    if state:
        return state["pid"]
    if lock_holder(maya):
        return lock_holder(maya)        # starting: still loading Maya
    mayapy = mayapy_for(maya)
    if not mayapy:
        raise ScoutError("Maya %s isn't installed on this machine (no mayapy), so Scout "
                         "can't render with it." % maya)
    os.makedirs(service_dir(maya), exist_ok=True)
    proc = subprocess.Popen([mayapy, _script(SERVICE_SCRIPT), "--maya", str(maya)],
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, close_fds=True, **_detached())
    return proc.pid


def send(maya, action, folder=None, start=True, **extra):
    """Leave a command in the service's inbox (starting the service if
    needed). The service acts on it within a couple of seconds. Returns the
    command's id."""
    if action not in CONTROLS + (SUBMIT, QUIT):
        raise ScoutError("Scout doesn't know how to %s." % action)
    command = dict(extra, id=uuid.uuid4().hex, action=action, folder=folder, sent=time.time(),
                   by=os.getpid())
    stamp = "%.6f" % time.time()
    _write_json(os.path.join(service_dir(maya), "inbox", "%s-%s.json" % (stamp, command["id"])),
                command)
    if start and action != QUIT:
        start_service(maya)
    return command["id"]


def take_inbox(maya):
    """The waiting commands, oldest first, removed from the inbox."""
    folder = os.path.join(service_dir(maya), "inbox")
    commands = []
    for path in sorted(glob.glob(os.path.join(glob.escape(folder), "*.json"))):
        command = _read_json(path)
        try:
            os.remove(path)
        except OSError:
            continue
        if command:
            commands.append(command)
    return commands


def read_queue(maya):
    return _read_json(os.path.join(service_dir(maya), "queue.json"), {}) or {}


def queued_folders():
    """Every version folder a service on this machine is rendering or
    holding."""
    found = []
    for state in services():
        q = read_queue(state["maya"])
        found += ([q["running"]] if q.get("running") else []) + list(q.get("waiting", []))
    return found


def last_results(maya):
    return (_read_json(os.path.join(service_dir(maya), "results.json"), {}) or {})


# ---------------------------------------------------------------------------
# renderSub's way in: hand a batch render to Scout
# ---------------------------------------------------------------------------

class ScoutJob(object):
    """A batch render Scout's service is running for renderSub. It looks
    like renderSub's RenderJob to the RenderQueue (poll, frames_done,
    cancel, finish) but reads how it stands from render.json, so the render
    carries on if Maya closes (carries_on) or renderSub reloads."""

    carries_on = True

    def __init__(self, info):
        self.info = info

    @classmethod
    def submit(cls, info):
        info["status"] = rs.QUEUED
        info["scout"] = {"maya": str(info.get("maya")), "sent": rs._now()}
        rs.write_info(info["folder"], info)
        send(info["maya"], SUBMIT, info["folder"])
        return cls(info)

    def _fresh(self):
        disk = rs.read_info(self.info["folder"])
        if disk:
            self.info.update(disk)
        return self.info

    def poll(self):
        return None if self._fresh().get("status") in rs.ACTIVE else 0

    def frames_done(self):
        return rs.frames_done(self.info, running=self.info.get("status") == rs.RENDERING)

    def cancel(self):
        send(self.info["maya"], KILL, self.info["folder"])
        return "Scout is stopping %s." % self.info["version"]

    def finish(self):
        return self._fresh()


def available():
    """True when Scout's service can run on this machine (its scripts are
    installed beside this one and this Maya's mayapy is there)."""
    return os.path.isfile(_script(SERVICE_SCRIPT))


# ---------------------------------------------------------------------------
# Projects and their renders (for the window)
# ---------------------------------------------------------------------------

def _drives():
    if os.name != "nt":
        return ["/Volumes/%s" % d for d in os.listdir("/Volumes")] if os.path.isdir("/Volumes") else []
    import ctypes
    found = []
    mask = ctypes.windll.kernel32.GetLogicalDrives()
    for n in range(26):
        if mask & (1 << n):
            root = "%s:\\" % chr(65 + n)
            if ctypes.windll.kernel32.GetDriveTypeW(root) == 3:       # fixed drives only
                found.append(root)
    return found


def ledger_of(film_folder):
    return os.path.join(film_folder, "maya", *rs.LEDGER)


def find_projects(extra=()):
    """Film folders with renders: <drive>/<film>/ on this machine's fixed
    drives, plus the folders added in the window. [path], sorted by name."""
    found = []
    for root in list(_drives()) + list(extra):
        candidates = [root] if os.path.isdir(ledger_of(root)) else \
            [os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(p))))
             for p in glob.glob(os.path.join(glob.escape(root), "*", "maya", *rs.LEDGER))]
        for c in candidates:
            if os.path.isdir(ledger_of(c)) and not any(rs._same(c, f) for f in found):
                found.append(os.path.normpath(c))
    return sorted(found, key=lambda p: os.path.basename(p).lower())


def project_renders(film_folder):
    """Every render in a project, newest first: the ledger entry with
    render.json's live state over it ("info"), "frames_done", "exists"
    (its folder is still on scratch) and the actions it offers."""
    rows, entries = [], []
    for path in glob.glob(os.path.join(glob.escape(ledger_of(film_folder)), "R*.json")):
        entry = _read_json(path)
        if entry and entry.get("folder"):
            entries.append(entry)
    # Renders made before render IDs (2026-11-19) aren't in the ledger: found
    # in the shots' folders, given an ID (which adds them to the ledger).
    pattern = os.path.join(glob.escape(film_folder), "maya", "sequences", "*", "*", "images",
                           "*", "*", "*", rs.INFO_NAME)
    for path in glob.glob(pattern):
        folder = os.path.dirname(path)
        if any(rs._same(folder, e["folder"]) for e in entries):
            continue
        info = rs.read_info(folder)
        if not info or not info.get("shot"):
            continue
        info = rs.ensure_render_id(folder, dict(info, folder=folder))
        entries.append(dict((k, info.get(k)) for k in rs.LEDGER_KEYS))
    for entry in entries:
        info = rs.read_info(entry["folder"]) or {}
        if info:
            info["folder"] = entry["folder"]
        row = dict(entry, info=info, exists=bool(info))
        row["status"] = info.get("status") or entry.get("status") or "?"
        row["frames_done"] = len(rs.finished_frames(info)) if info and "frames" in info else 0
        row["total"] = len(info.get("frames") or []) or entry.get("frames") or 0
        row["actions"] = actions(info) if info else []
        rows.append(row)
    return sorted(rows, key=lambda r: r.get("render_id") or "", reverse=True)


# ---------------------------------------------------------------------------
# Removing unwanted renders (user, 2026-11-20)
# ---------------------------------------------------------------------------

def why_not_delete(row):
    """None when the render can go, else why not (it's still rendering,
    waiting, paused, or its frames are still coming back from the cloud)."""
    info = row.get("info") or {}
    if not row.get("exists"):
        return None
    if info.get("status") in rs.ACTIVE and not stale(row):
        if rs.in_cloud(info):
            return "%s is rendering in the cloud: its frames are still coming back." % row["version"]
        return "%s is still %s: Kill it first." % (row["version"], info["status"])
    return None


def delete_render(film_folder, row):
    """Delete a render's folder from scratch (its frames, movie and scene
    copy) and take it off the list. Anything published stays on H and
    ShotGrid. Raises ScoutError when it can't go."""
    why = why_not_delete(row)
    if why:
        raise ScoutError(why)
    folder = row.get("folder")
    if row.get("exists") and folder and os.path.isdir(folder):
        try:
            shutil.rmtree(folder)
        except OSError as e:
            raise ScoutError("Couldn't delete %s (a file in it is open, e.g. in RV?):\n%s"
                             % (row["version"], e))
    forget(film_folder, row)


def forget(film_folder, row):
    """Take a render off the list (its ledger entry), leaving any files."""
    if row.get("render_id"):
        try:
            os.remove(os.path.join(ledger_of(film_folder), row["render_id"] + ".json"))
        except OSError:
            pass


def _here(info):
    return (info.get("where") or {}).get("machine") == rs.where()["machine"]


def stale(row):
    """A render on this machine still marked running that nothing runs any
    more (Maya closed, the queue was lost: SEQ010_170 v007, 2026-11-20)."""
    info = row.get("info") or {}
    return bool(row.get("exists") and info.get("status") in rs.ACTIVE and _here(info)
                and not rs.in_cloud(info) and not alive(info.get("pid")))


def settle_row(row):
    """Record how a stale render ended (renderSub's settle: done when its log
    says it completed with every frame, else interrupted, its finished frames
    ready to publish). Makes the movie for a done one, so it takes a while."""
    return rs.settle(dict(row["info"]))


def controllable(info):
    """Scout can pause, kill and restart local batch renders on this
    machine."""
    return info.get("how") == rs.BATCH and (info.get("where") or {}).get("kind") == rs.LOCAL \
        and _here(info)


def actions(info):
    """What can be done to a render now."""
    status, done = info.get("status"), rs.finished_frames(info) if "frames" in info else []
    found = []
    if controllable(info):
        if status == rs.RENDERING:
            found += [PAUSE, KILL]
        elif status == rs.PAUSED:
            found += [RESUME, KILL]
        elif status == rs.QUEUED:
            found += [KILL]
        elif status in rs.STOPPED and len(done) < len(info.get("frames") or []):
            found += [RESTART]
    if done:
        found.append(RV)
        if status not in rs.ACTIVE and not info.get("published"):
            found.append(PUBLISH)
    return found


def describe(row):
    """A render's state in a few words, for the window."""
    info, status = row.get("info") or {}, row["status"]
    done, total = row["frames_done"], row["total"]
    if not row["exists"]:
        return "deleted from scratch" + (" (published)" if row.get("published") else "")
    if info.get("how") == rs.FLOW and rs.in_cloud(info):
        return "in the cloud, %d of %d frame(s) back" % (len(rs.frame_files(info)), total)
    if status == rs.RENDERING and info.get("how") == rs.BATCH:
        running = rs.frames_done(info, running=True)
        text = "rendering, %d of %d frame(s)" % (running, total)
        if rs.timing(info, running=True):
            text += ", about %s left" % rs.duration(rs.time_left(info))
        return text
    if status == rs.PAUSED:
        return "paused, %d of %d frame(s)" % (rs.frames_done(info, running=True), total)
    if status in rs.STOPPED:
        return "%s, %d of %d frame(s)" % (status, done, total)
    if status == rs.DONE and info.get("published"):
        return "published"
    return status


# ---------------------------------------------------------------------------
# The window
# ---------------------------------------------------------------------------

def _this_maya():
    try:
        import maya.cmds as cmds
        return cmds.about(version=True)
    except Exception:
        return None


def launch_window(maya=None):
    """Open the Scout window in its own mayapy (the mpLighting shelf's
    Scout button), so it stays open when Maya closes. Returns its pid."""
    maya = maya or _this_maya()
    mayapy = mayapy_for(maya) if maya else ""
    if not mayapy:
        installed = sorted(glob.glob(r"C:\Program Files\Autodesk\Maya20*\bin\mayapy.exe"))
        mayapy = installed[-1] if installed else ""
    if not mayapy:
        raise ScoutError("No Maya (mayapy) found to run Scout with.")
    proc = subprocess.Popen([mayapy, _script("scout_ui.py")], stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            close_fds=True, **_detached())
    return proc.pid


# ---------------------------------------------------------------------------
# Publish and RV, from outside Maya
# ---------------------------------------------------------------------------

def start_worker(maya, action, folder, notes=""):
    """Publish runs in its own mayapy (it needs Maya's settings), so the
    window stays free. Returns (process, result path); the result file is
    JSON {"ok", "message", ...} once it has finished."""
    mayapy = mayapy_for(maya)
    if not mayapy:
        raise ScoutError("Maya %s isn't installed on this machine." % maya)
    folder_out = os.path.join(home(), "work")
    os.makedirs(folder_out, exist_ok=True)
    result = os.path.join(folder_out, "%s.json" % uuid.uuid4().hex)
    request = result[:-5] + ".request.json"
    _write_json(request, {"action": action, "folder": folder, "notes": notes, "result": result})
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    proc = subprocess.Popen([mayapy, _script(WORKER_SCRIPT), request],
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, creationflags=flags)
    return proc, result


def read_result(path):
    return _read_json(path)


def load_in_rv(info):
    """Show a render's finished frames in renderSub's RV window. Blocks
    while RV starts. Returns None or why it failed."""
    media = rs.rv_media(info)
    if not media:
        return "%s has no finished frames yet." % info.get("version")
    return rs.push_to_rv(media)
