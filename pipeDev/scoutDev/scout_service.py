"""
Scout's render service: owns the batch-render queue on this machine, for
one Maya version, in its own mayapy (see scout_api.py). It renders one
version at a time with that Maya's Render.exe, and acts on the commands
left in its inbox: submit, pause, resume, kill, restart, quit.

Started by scout_api.start_service (renderSub hands a render over, or the
Scout window needs it); quits after IDLE_EXIT_S with nothing to do. If it
stops while a Render.exe runs (a crash, the machine restarting), the next
service picks that render up again from queue.json: Render.exe carries on
by itself, so it's watched until it ends.

    mayapy scout_service.py --maya 2027
"""

import os
import sys
import time
import argparse
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class AdoptedJob(object):
    """A Render.exe started by an earlier service (or renderSub) that is
    still running: watched by its pid, as there's no process handle."""

    def __init__(self, info):
        import scout_api as api
        self.api, self.info, self.cancelled = api, info, False
        self.pid = info.get("pid")

    def poll(self):
        return None if self.api.alive(self.pid) else 0

    def cancel(self):
        self.cancelled = True
        self.api.kill_process(self.pid)

    def finish(self):
        rs = self.api.rs
        if self.cancelled:
            return rs.finish_render(self.info, None, cancelled=True)
        if rs.log_completed(self.info) and not rs.missing_frames(self.info):
            return rs.finish_render(self.info, 0)
        return rs.finish_render(self.info, None, interrupted=True)


class Service(object):
    """job_class: renderSub's RenderJob (Render.exe), or a stand-in in the
    tests. step() does one round; run() loops until quit or idle."""

    def __init__(self, maya, job_class=None, idle_exit=None):
        import scout_api as api
        self.api, self.rs = api, api.rs
        self.maya = str(maya)
        self.dir = api.service_dir(self.maya)
        self.job_class = job_class or self.rs.RenderJob
        self.idle_exit = api.IDLE_EXIT_S if idle_exit is None else idle_exit
        self.job = None
        self.waiting = []
        self.quit = False
        self.started = time.time()
        self.idle_since = time.time()
        os.makedirs(os.path.join(self.dir, "inbox"), exist_ok=True)
        self._load()

    # ------------------------------------------------------------------ state
    def log(self, text):
        line = "%s  %s" % (self.rs._now(), text)
        try:
            with open(os.path.join(self.dir, "service.log"), "a") as f:
                f.write(line + "\n")
        except OSError:
            pass

    def _info(self, folder):
        info = self.rs.read_info(folder or "")
        if info:
            info["folder"] = folder
        return info

    def _load(self):
        """Carry on from the last service's queue.json."""
        q = self.api.read_queue(self.maya)
        running = q.get("running")
        if running:
            info = self._info(running)
            if info and info.get("status") in (self.rs.RENDERING, self.rs.PAUSED) \
                    and self.api.alive(info.get("pid")):
                self.job = AdoptedJob(info)
                self.log("watching %s again (Render.exe %s still running)" % (info["version"], info["pid"]))
            elif info and info.get("status") in self.rs.ACTIVE:
                self.job = AdoptedJob(info)         # gone: finished on the first step
        for folder in q.get("waiting", []):
            info = self._info(folder)
            if info and info.get("status") == self.rs.QUEUED:
                info["pid"] = os.getpid()
                self.rs.write_info(folder, info)
                self.waiting.append(folder)

    def save(self):
        self.api._write_json(os.path.join(self.dir, "queue.json"), {
            "running": self.job.info["folder"] if self.job else None,
            "waiting": list(self.waiting), "updated": self.rs._now()})

    def heartbeat(self):
        self.api._write_json(os.path.join(self.dir, "service.json"), {
            "pid": os.getpid(), "maya": self.maya, "machine": self.rs.where()["machine"],
            "started": self.started, "heartbeat": time.time()})

    def _running(self, folder):
        return self.job is not None and self.rs._same(self.job.info["folder"], folder)

    def _job_pid(self):
        proc = getattr(self.job, "process", None)
        return proc.pid if proc is not None else getattr(self.job, "pid", None)

    # ------------------------------------------------------------------ commands
    def handle(self, command):
        action, folder = command.get("action"), command.get("folder")
        rs = self.rs
        info = self._info(folder) if folder else None
        if action == self.api.QUIT:
            self.quit = True
            return "quitting"
        if not info:
            return "no render.json in %s" % folder
        name = info.get("version")
        if action == self.api.SUBMIT:
            if self._running(folder) or any(rs._same(folder, w) for w in self.waiting):
                return "%s is already in the queue" % name
            info.update(status=rs.QUEUED, pid=os.getpid())
            rs.write_info(folder, info)
            self.waiting.append(folder)
            return "queued %s" % name
        if action == self.api.KILL:
            if self._running(folder):
                self.api.resume_process(self._job_pid())
                self.job.cancel()
                return "killing %s" % name
            for w in list(self.waiting):
                if rs._same(w, folder):
                    self.waiting.remove(w)
                    rs.finish_render(info, None, cancelled=True)
                    return "took %s out of the queue" % name
            if info.get("status") in rs.ACTIVE and self.api.alive(info.get("pid")) \
                    and info.get("pid") != os.getpid():
                self.api.kill_process(info["pid"])      # renderSub's own Render.exe
                return "killed %s's Render.exe (%s)" % (name, info["pid"])
            return "%s isn't rendering" % name
        if action in (self.api.PAUSE, self.api.RESUME):
            pause = action == self.api.PAUSE
            want, now = (rs.RENDERING, rs.PAUSED) if pause else (rs.PAUSED, rs.RENDERING)
            if info.get("status") != want:
                return "%s isn't %s" % (name, want)
            pid = self._job_pid() if self._running(folder) else info.get("pid")
            if not self.api.alive(pid):
                return "%s's Render.exe isn't running" % name
            (self.api.pause_process if pause else self.api.resume_process)(pid)
            info["status"] = now
            if pause:
                info["paused_at"] = time.time()
            else:
                # Paused time isn't render time (timing, time left).
                info["paused_s"] = info.get("paused_s", 0) + time.time() - info.pop("paused_at", time.time())
            rs.write_info(folder, info)
            if self._running(folder):
                self.job.info.update(info)
            return "%s %s" % ("paused" if pause else "resumed", name)
        if action == self.api.RESTART:
            if info.get("status") not in rs.STOPPED:
                return "%s is %s, not stopped" % (name, info.get("status"))
            finished = rs.finished_frames(info)
            left = [f for f in info["frames"] if f not in finished]
            if not left:
                return "%s has every frame" % name
            for key in ("finished", "returncode", "missing", "timing", "movie_problem", "stopped_why"):
                info.pop(key, None)
            info.update(status=rs.QUEUED, pid=os.getpid(), render_frames=left,
                        restarts=info.get("restarts", 0) + 1)
            rs.write_info(folder, info)
            self.waiting.append(folder)
            return "restarting %s: %d frame(s) left (%s)" % (name, len(left), rs.seq_string(left))
        return "unknown command %s" % action

    # ------------------------------------------------------------------ the loop
    def step(self):
        for command in self.api.take_inbox(self.maya):
            try:
                self.log("%s %s: %s" % (command.get("action"), command.get("folder") or "",
                                        self.handle(command)))
            except Exception:
                self.log("%s failed:\n%s" % (command.get("action"), traceback.format_exc()))
        if self.job and self.job.poll() is not None:
            try:
                info = self.job.finish()
                info.pop("render_frames", None)
                self.rs.write_info(info["folder"], info)
                self.log("%s %s (%d of %d frame(s))" % (info["version"], info["status"],
                                                       len(self.rs.finished_frames(info)),
                                                       len(info["frames"])))
            except Exception:
                self.log("finishing a render failed:\n%s" % traceback.format_exc())
            self.job = None
        while not self.job and self.waiting:
            folder = self.waiting.pop(0)
            info = self._info(folder)
            if not info or info.get("status") != self.rs.QUEUED:
                continue
            info.update(status=self.rs.RENDERING, started=self.rs._now(), started_ts=time.time())
            self.rs.write_info(folder, info)
            try:
                self.job = self.job_class(info)
                self.log("rendering %s %s" % (info["shot"], info["version"]))
            except Exception as e:
                self.rs.finish_render(info, 1)
                self.log("couldn't start %s: %s" % (info["version"], e))
        self.save()
        self.heartbeat()
        if self.job or self.waiting:
            self.idle_since = time.time()
        elif time.time() - self.idle_since > self.idle_exit:
            self.log("nothing to do for %d min: quitting" % (self.idle_exit // 60))
            self.quit = True

    def run(self, tick=1.0):
        self.log("service started (Maya %s, pid %d)" % (self.maya, os.getpid()))
        while not self.quit:
            try:
                self.step()
            except Exception:
                self.log("step failed:\n%s" % traceback.format_exc())
            time.sleep(tick)
        self.save()
        for name in ("service.json", "lock"):
            try:
                os.remove(os.path.join(self.dir, name))
            except OSError:
                pass
        self.log("service stopped")


def _only_one(maya):
    """Take this Maya version's lock: True when no other service has it."""
    import scout_api as api
    lock = api.lock_path(maya)
    os.makedirs(os.path.dirname(lock), exist_ok=True)
    for _ in range(2):
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            holder = api.lock_holder(maya)
            if holder and holder != os.getpid():
                return False
            try:
                os.remove(lock)         # left by a service that died
            except OSError:
                return False
            continue
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return True
    return False


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--maya", required=True)
    parser.add_argument("--no-maya", action="store_true",
                        help="don't load Maya (the tests' stand-in renders don't need it)")
    parser.add_argument("--idle", type=float, default=None)
    args = parser.parse_args(argv)
    if not _only_one(args.maya):
        return 0
    if not args.no_maya:
        import maya.standalone
        maya.standalone.initialize()
    Service(args.maya, idle_exit=args.idle).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
