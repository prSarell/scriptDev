r"""
Send to Gaffer (mpLighting shelf, user 2026-11-24)

Sends what's selected in Maya to Gaffer for lookdev and lighting: published
or not, whatever the student picks (user: "send whatever they want pipe
approved or not"). Geometry, cameras and lights go over the timeline range
as USD, with their Arnold shaders (mayaUSD's Arnold job context; the shaders
only come through in the Maya GUI, not mayapy).

Where things go: the one structure every hand-off between programs uses
(user 2026-11-24), in the film's gaffer folder:

    <film>\gaffer\assets\<type>\<asset>\<login>\              the student's Gaffer files
    <film>\gaffer\sequences\<seq>\<shot>\<login>\             (<name>_v###.gfr)
        fromMaya\<name>_v###.usd     every send, never overwritten
        fromMaya\<name>_latest.usda  points at the newest send

The Gaffer file reads <name>_latest.usda, so a new send carries on in the
student's Gaffer work (they press Reload); Start Again makes the next
<name>_v###.gfr and keeps the old one (user 2026-11-24). Paths in the Gaffer
file are ${PIPE_SCRATCH} paths; gafferPipeStartup sets the variable in
Gaffer from where the file is, so it opens from any drive (pipe rule 8).

Gaffer and the Arnold SDK aren't installed like Maya: they're folders (the
mpPipe bundle copies Gaffer to Documents\maya\gaffer). Their locations are
pipe settings (gaffer_root, arnold_root); the first send asks for any that
are missing. Each send rewrites <gaffer home>\gaffer_pipe.cmd (the launcher
the desktop shortcut and this tool use) and the startup stubs beside it.
"""

import os
import re
import shutil
import subprocess

import maya.cmds as cmds

import publishTool_api as pub
import pipeEnv
import fbxExport

TITLE = "Send to Gaffer"
APP_FOLDER = "gaffer"                   # <film>\gaffer, beside <film>\maya
APP_LABEL = "Gaffer"
GAFFER_ROOT = "gaffer_root"             # pipe settings (pipeline_config.json)
ARNOLD_ROOT = "arnold_root"
LAUNCHER = "gaffer_pipe.cmd"
STARTUP_FOLDER = "pipeStartup"
STARTUP_APPS = ("gui", "execute", "dispatch")
STARTUP_MODULE = "gafferPipeStartup.py"
LATEST = "%s_latest.usda"
USD_RE = r"^%s_v(\d{3,})\.usd$"
GFR_RE = r"^%s_v(\d{3,})\.gfr$"
# Maya's own Python, USD, MaterialX and Arnold paths must not leak into
# Gaffer: its Python 3.11 and USD 26.05 loaded Maya's USD 25.11 DLLs through
# PXR_USD_WINDOWS_DLL_PATH and failed (2026-11-24). Cleared by name in the
# launcher (for a desktop start from a shell Maya made) and by prefix too
# when the pipe starts Gaffer from Maya.
CLEARED_ENV = ("PYTHONPATH", "PYTHONHOME", "PXR_PLUGINPATH_NAME", "PXR_USD_WINDOWS_DLL_PATH",
               "PXR_MTLX_PLUGIN_SEARCH_PATHS", "PXR_MTLX_STDLIB_SEARCH_PATHS",
               "MAYA_PXR_PLUGINPATH_NAME", "USD_LOCATION", "ARNOLD_PLUGIN_PATH",
               "ARNOLD_MATERIALX_NODE_DEFINITIONS", "MATERIALX_SEARCH_PATH",
               "MATERIALX_OCIO_CONFIG_SEARCH_PATH", "MTOA_PATH", "MTOA_TEMPLATES_PATH",
               "MTOA_EXTENSIONS_PATH", "QT_PLUGIN_PATH")
CLEARED_PREFIXES = ("PXR_", "MAYAUSD", "MAYA_USD", "MTOA", "MATERIALX", "USD_", "QT_",
                    "PYSIDE", "PYTHON")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class SendError(Exception):
    pass


# ---------------------------------------------------------------------------
# Settings: where Gaffer and the Arnold SDK are
# ---------------------------------------------------------------------------

def gaffer_cmd(root):
    return os.path.join(root, "bin", "gaffer.cmd") if root else ""


def find_gaffer(folder):
    """The Gaffer build folder (holding bin\\gaffer.cmd) at or just inside
    folder (e.g. Documents\\maya\\gaffer -> ...\\gaffer-1.7.7.0-windows,
    the newest if several), or None."""
    if not folder or not os.path.isdir(folder):
        return None
    if os.path.isfile(gaffer_cmd(folder)):
        return os.path.normpath(folder)
    inside = sorted(os.path.join(folder, n) for n in os.listdir(folder)
                    if os.path.isfile(gaffer_cmd(os.path.join(folder, n))))
    return os.path.normpath(inside[-1]) if inside else None


def is_arnold_sdk(folder):
    """A standalone Arnold SDK: Gaffer reads include\\ai_version.h to pick
    its Arnold module. MtoA's folder keeps it in include\\arnold\\, so it
    can't stand in (tested 2026-11-24)."""
    return bool(folder) and os.path.isfile(os.path.join(folder, "include", "ai_version.h"))


def arnold_version(folder):
    """'7.5.2.0' from an SDK's ai_version.h, or ''."""
    try:
        text = open(os.path.join(folder, "include", "ai_version.h")).read()
    except (OSError, TypeError):
        return ""
    parts = [re.search(r"#define\s+AI_VERSION_%s\s+\"?(\w+)" % k, text)
             for k in ("ARCH_NUM", "MAJOR_NUM", "MINOR_NUM", "FIX")]
    return ".".join(m.group(1) for m in parts if m)


def settings():
    """(gaffer build folder or None, Arnold SDK folder or None)."""
    config = pub.load_config()
    gaffer = find_gaffer(config.get(GAFFER_ROOT, ""))
    arnold = config.get(ARNOLD_ROOT, "")
    return gaffer, (arnold if is_arnold_sdk(arnold) else None)


def save_setting(key, value):
    config = pub.load_config()
    config[key] = os.path.normpath(value)
    pub.save_config(config)


# ---------------------------------------------------------------------------
# The launcher and Gaffer's startup stubs
# ---------------------------------------------------------------------------

def gaffer_home(gaffer):
    """The folder holding the Gaffer build: the launcher and stubs go here."""
    return os.path.dirname(os.path.normpath(gaffer))


def launcher_path(gaffer):
    return os.path.join(gaffer_home(gaffer), LAUNCHER)


def write_launcher(gaffer, arnold=None):
    """(Re)write <home>\\gaffer_pipe.cmd and <home>\\pipeStartup: a copy of
    gafferPipeStartup.py plus one stub per Gaffer app that installs it.
    Returns the launcher's path."""
    home = gaffer_home(gaffer)
    startup = os.path.join(home, STARTUP_FOLDER)
    python = os.path.join(startup, "python")
    if not os.path.isdir(python):
        os.makedirs(python)
    here = os.path.dirname(os.path.abspath(__file__))
    shutil.copy2(os.path.join(here, STARTUP_MODULE), os.path.join(python, STARTUP_MODULE))
    stub = ("# Written by the pipe's Send to Gaffer (gafferSend.py).\n"
            "import os, sys\n"
            "_python = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "
            "'python')\n"
            "if _python not in sys.path:\n"
            "    sys.path.insert(0, _python)\n"
            "import gafferPipeStartup\n"
            "gafferPipeStartup.install(application)\n")
    for app in STARTUP_APPS:
        folder = os.path.join(startup, app)
        if not os.path.isdir(folder):
            os.makedirs(folder)
        with open(os.path.join(folder, "pipe.py"), "w") as f:
            f.write(stub)
    lines = ["@echo off",
             "rem Starts Gaffer for the film pipe. Written by Send to Gaffer",
             "rem (gafferSend.py) on every send: edit the pipe settings, not this.",
             "setlocal"]
    lines += ["set %s=" % k for k in CLEARED_ENV]
    if arnold:
        lines.append('set "ARNOLD_ROOT=%s"' % os.path.normpath(arnold))
    lines += ['set "GAFFER_STARTUP_PATHS=%%~dp0%s"' % STARTUP_FOLDER,
              '"%s" %%*' % gaffer_cmd(gaffer),
              "endlocal"]
    path = launcher_path(gaffer)
    with open(path, "w") as f:
        f.write("\r\n".join(lines) + "\r\n")
    return path


def make_shortcut(gaffer, desktop=None):
    """A 'Gaffer' shortcut to the launcher on the desktop (Windows only).
    Returns its path, or None if it couldn't be made."""
    if os.name != "nt":
        return None
    desktop = desktop or os.path.join(os.path.expanduser("~"), "Desktop")
    link = os.path.join(desktop, "Gaffer.lnk")
    icon = os.path.join(gaffer, "doc", "gaffer", "html", "_static", "favicon.ico")
    script = ("$s = (New-Object -ComObject WScript.Shell).CreateShortcut('%s'); "
              "$s.TargetPath = '%s'; $s.WorkingDirectory = '%s'; $s.WindowStyle = 7; "
              "$s.Description = 'Gaffer for the film pipe'; %s$s.Save()"
              % (link, launcher_path(gaffer), gaffer_home(gaffer),
                 ("$s.IconLocation = '%s'; " % icon) if os.path.isfile(icon) else ""))
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", script], check=True,
                       creationflags=NO_WINDOW, capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    return link if os.path.isfile(link) else None


def clean_env():
    """The environment to start Gaffer with, without Maya's Python/USD/MtoA:
    those variables cleared, and Maya's, MayaUSD's and MtoA's folders taken
    off PATH (Gaffer's USD loaded Maya's USD DLLs from it: "DLL load failed
    while importing _tf", 2026-11-24)."""
    env = dict((k, v) for k, v in os.environ.items()
               if k.upper() not in CLEARED_ENV
               and not k.upper().startswith(CLEARED_PREFIXES)
               and not (k.upper().startswith("ARNOLD_") and k.upper() != "ARNOLD_ROOT"))
    maya =os.path.normcase(os.environ.get("MAYA_LOCATION", "") or "\0")
    keep = [p for p in env.get("PATH", "").split(os.pathsep)
            if p and "\\autodesk\\" not in os.path.normcase(p) + "\\"
            and not os.path.normcase(p).startswith(maya)]
    env["PATH"] = os.pathsep.join(keep)
    return env


# ---------------------------------------------------------------------------
# Where a send goes
# ---------------------------------------------------------------------------

def target(scene=None):
    """(login folder, fromMaya folder, name) in the film's gaffer folder."""
    try:
        from_maya, name, _kind, _root = fbxExport.target(scene, app=APP_FOLDER, label=APP_LABEL)
    except fbxExport.ExportError as e:
        raise SendError(str(e))
    return os.path.dirname(from_maya), from_maya, name


def _versions(folder, pattern, name):
    regex = re.compile(pattern % re.escape(name), re.IGNORECASE)
    found = []
    for f in (os.listdir(folder) if os.path.isdir(folder) else []):
        m = regex.match(f)
        if m:
            found.append((int(m.group(1)), os.path.join(folder, f)))
    return sorted(found)


def next_usd(from_maya, name):
    taken = _versions(from_maya, USD_RE, name)
    return os.path.join(from_maya, "%s_v%03d.usd" % (name, (taken[-1][0] if taken else 0) + 1))


def latest_gfr(folder, name):
    found = _versions(folder, GFR_RE, name)
    return found[-1][1] if found else None


def next_gfr(folder, name):
    found = _versions(folder, GFR_RE, name)
    return os.path.join(folder, "%s_v%03d.gfr" % (name, (found[-1][0] if found else 0) + 1))


def var_path(path):
    """D:\\NWF_SHF\\gaffer\\... -> ${PIPE_SCRATCH}/NWF_SHF/gaffer/... (Gaffer
    expands it; gafferPipeStartup sets it from the open file)."""
    root = pipeEnv.root_of(path)
    norm = os.path.normpath(path).replace("\\", "/")
    if not root:
        return norm
    prefix = os.path.normpath(root).replace("\\", "/").rstrip("/") + "/"
    if not os.path.normcase(norm).startswith(os.path.normcase(prefix)):
        return norm
    return "${%s}/%s" % (pipeEnv.VAR, norm[len(prefix):])


# ---------------------------------------------------------------------------
# What goes
# ---------------------------------------------------------------------------

def _is_light(shape):
    return "light" in (cmds.getClassification(cmds.nodeType(shape)) or [""])[0].lower()


def stages_under(node):
    """The USD stages (mayaUsdProxyShape, long names) at or below node."""
    return [s for s in fbxExport._shapes_under(node) if cmds.nodeType(s) == "mayaUsdProxyShape"]


def picked(selection=None):
    """(roots, skipped): the picked transforms holding geometry, a camera, a
    light or a USD stage (a component or shape counts as its transform), and
    what's left out with why."""
    selection = cmds.ls(selection if selection is not None else cmds.ls(selection=True),
                        long=True, objectsOnly=True) or []
    nodes = []
    for node in selection:
        if not cmds.objectType(node, isAType="transform"):
            node = (cmds.listRelatives(node, parent=True, fullPath=True) or [None])[0]
        if node and node not in nodes:
            nodes.append(node)
    nodes = [n for n in nodes if not any(n.startswith(o + "|") for o in nodes if o != n)]
    roots, skipped = [], []
    for node in nodes:
        shapes = fbxExport._shapes_under(node)
        # surfaceShape: meshes and NURBS (a locator is a geometryShape too).
        # A USD stage goes as a reference to its own .usd (add_stages).
        if any((cmds.objectType(s, isAType="surfaceShape") or cmds.nodeType(s) == "camera"
                or _is_light(s) or cmds.nodeType(s) == "mayaUsdProxyShape")
               and not cmds.getAttr(s + ".intermediateObject")
               for s in shapes):
            roots.append(node)
        else:
            skipped.append((node, "no geometry, camera or light"))
    return roots, skipped


# ---------------------------------------------------------------------------
# The send
# ---------------------------------------------------------------------------

def export(roots, path, start, end):
    """USD of roots over start..end, with Arnold shaders and lights."""
    for plugin in ("mayaUsdPlugin", "mtoa"):
        if not cmds.pluginInfo(plugin, query=True, loaded=True):
            try:
                cmds.loadPlugin(plugin, quiet=True)
            except RuntimeError:
                if plugin == "mayaUsdPlugin":
                    raise SendError("Maya's USD plug-in (mayaUsdPlugin) won't load.")
    folder = os.path.dirname(path)
    if not os.path.isdir(folder):
        os.makedirs(folder)
    before = cmds.ls(selection=True, long=True) or []
    # nurbsCurve left out: a rig's controls came through as curves (Scout,
    # 2026-11-24) and they're never rendered.
    options = dict(file=path.replace("\\", "/"), selection=True, frameRange=(start, end),
                   defaultUSDFormat="usdc", filterTypes=["nurbsCurve"])
    if cmds.pluginInfo("mtoa", query=True, loaded=True):
        options["jobContext"] = ["Arnold"]
    try:
        cmds.select(roots, replace=True)
        cmds.mayaUSDExport(**options)
    finally:
        cmds.select(before, replace=True) if before else cmds.select(clear=True)
    if not os.path.isfile(path):
        raise SendError("The USD wasn't written:\n  %s" % path)
    return path


def _stage_file(proxy):
    """(the stage's root layer file, unsaved edits?) for a proxy shape: the
    layer the stage really has open (a USD Edit layer if there is one), else
    its filePath with $PIPE_SCRATCH filled in."""
    try:
        import mayaUsd.ufe
        stage = mayaUsd.ufe.getStage(proxy)
    except Exception:
        stage = None
    if stage is not None and stage.GetRootLayer().realPath:
        root = stage.GetRootLayer()
        session = stage.GetSessionLayer()
        unsaved = root.dirty or any(l.dirty for l in stage.GetLayerStack(includeSessionLayers=False)) \
            or bool(session.rootPrims)
        return os.path.normpath(root.realPath), unsaved
    path = cmds.getAttr(proxy + ".filePath") or ""
    return os.path.normpath(os.path.expandvars(path)) if path else None, False


def _usd_path(node):
    """The prim path mayaUSD writes a Maya node at: |a|b:c -> /a/b_c."""
    return "/" + "/".join(p.replace(":", "_") for p in node.strip("|").split("|"))


def _relative(source, layer_path):
    """source as a path relative to the layer (works from any drive), or
    absolute with forward slashes if they're on different drives."""
    try:
        ref = os.path.relpath(source, os.path.dirname(layer_path)).replace("\\", "/")
        return ref if ref.startswith(".") else "./" + ref
    except ValueError:
        return source.replace("\\", "/")


def _relink(spec, layer_path):
    """mayaUSD exports a stage as `over "<defaultPrim>"` under its transform,
    referencing the stage's file by an ABSOLUTE path (breaks on another
    drive). Rewrite those to relative paths. Returns how many it changed."""
    from pxr import Sdf
    changed = 0
    for child in [spec] + list(spec.nameChildren):
        op = child.GetInfo("references") if child.HasInfo("references") else None
        if op is None:
            continue
        items = list(op.prependedItems)
        # Build sets stages to $PIPE_SCRATCH/... paths; USD can't expand those.
        full = [os.path.expandvars(r.assetPath) if r.assetPath else r.assetPath for r in items]
        fixed = [Sdf.Reference(_relative(f, layer_path), r.primPath, r.layerOffset, r.customData)
                 if f and os.path.isabs(f) else r for r, f in zip(items, full)]
        if fixed != items:
            new = Sdf.ReferenceListOp()
            new.prependedItems = fixed
            child.SetInfo("references", new)
            changed += sum(1 for a, b in zip(items, fixed) if a != b)
    return changed


def add_stages(path, stages):
    """USD stages go as references to the stage's own .usd, never copied.
    mayaUSD already writes each one (its transform, plus an `over` that
    references the stage's file, 2026-11-24) but by an absolute path: those
    are made relative to the send, so they work from any drive. A stage
    mayaUSD didn't write gets a reference added here. Returns notes: what
    went, and stages with unsaved USD edits (those aren't sent)."""
    if not stages:
        return []
    from pxr import Sdf
    layer = Sdf.Layer.FindOrOpen(path)
    notes = []
    for proxy in stages:
        transform = cmds.listRelatives(proxy, parent=True, fullPath=True)[0]
        short = transform.split("|")[-1]
        source, unsaved = _stage_file(proxy)
        if not source or not os.path.isfile(source):
            notes.append("%s: its USD file wasn't found (%s), not sent" % (short, source))
            continue
        prim_path = Sdf.Path(_usd_path(transform))
        spec = layer.GetPrimAtPath(prim_path)
        if spec is not None and _relink(spec, path):
            notes.append("%s: references %s" % (short, os.path.basename(source)))
            if unsaved:
                notes.append("%s has unsaved USD edits: they aren't in Gaffer until you save "
                             "them (USD layer editor)" % short)
            continue
        if spec is None:
            # Not written by mayaUSD (e.g. under a group that wasn't sent):
            # place it at the top, where it is in the world.
            prim_path = Sdf.Path("/" + short.replace(":", "_"))
            spec = Sdf.CreatePrimInLayer(layer, prim_path)
            spec.specifier, spec.typeName = Sdf.SpecifierDef, "Xform"
            matrix = cmds.xform(transform, query=True, matrix=True, worldSpace=True)
            from pxr import Gf
            attr = Sdf.AttributeSpec(spec, "xformOp:transform", Sdf.ValueTypeNames.Matrix4d)
            attr.default = Gf.Matrix4d(*matrix)
            order = Sdf.AttributeSpec(spec, "xformOpOrder", Sdf.ValueTypeNames.TokenArray,
                                      variability=Sdf.VariabilityUniform)
            order.default = ["xformOp:transform"]
        ref = _relative(source, path)
        inside = cmds.getAttr(proxy + ".primPath") or ""
        target = Sdf.Path(inside) if inside not in ("", "/") else Sdf.Path()
        spec.referenceList.Prepend(Sdf.Reference(ref, target))
        notes.append("%s: references %s" % (short, os.path.basename(source)))
        if unsaved:
            notes.append("%s has unsaved USD edits: they aren't in Gaffer until you save "
                         "them (USD layer editor)" % short)
    layer.Save()
    return notes


def write_latest(from_maya, name, usd):
    """<name>_latest.usda: a small layer that sublayers the newest send (a
    relative path, so it works from any drive) and carries its frame range
    and units. Gaffer never holds a .usda open, so it can be rewritten."""
    from pxr import Sdf
    sent = Sdf.Layer.FindOrOpen(usd)
    path = os.path.join(from_maya, LATEST % name)
    layer = Sdf.Layer.FindOrOpen(path) or Sdf.Layer.CreateNew(path)
    layer.Clear()
    layer.subLayerPaths.append("./" + os.path.basename(usd))
    if sent.HasStartTimeCode():
        layer.startTimeCode = sent.startTimeCode
    if sent.HasEndTimeCode():
        layer.endTimeCode = sent.endTimeCode
    if sent.HasTimeCodesPerSecond():
        layer.timeCodesPerSecond = sent.timeCodesPerSecond
    if sent.HasFramesPerSecond():
        layer.framesPerSecond = sent.framesPerSecond
    for key in ("metersPerUnit", "upAxis"):
        if key in sent.pseudoRoot.GetMetaDataInfoKeys():
            layer.pseudoRoot.SetInfo(key, sent.pseudoRoot.GetInfo(key))
    if sent.defaultPrim:
        layer.defaultPrim = sent.defaultPrim
    layer.Save()
    return path


def new_gaffer_file(gaffer, gfr, latest, folder, name, start, end):
    """Make the student's Gaffer file with Gaffer's own Python."""
    module = os.path.join(gaffer_home(gaffer), STARTUP_FOLDER, "python", STARTUP_MODULE)
    fps = mel_fps()
    cmd = [launcher_path(gaffer), "python", module, "-arguments", "new", gfr,
           var_path(latest), var_path(folder), name, str(int(start)), str(int(end)), str(fps)]
    result = subprocess.run(cmd, env=clean_env(), creationflags=NO_WINDOW,
                            capture_output=True, text=True, timeout=600)
    if not os.path.isfile(gfr):
        raise SendError("Gaffer couldn't make the Gaffer file:\n  %s\n\n%s"
                        % (gfr, (result.stderr or result.stdout or "").strip()[-1500:]))
    return gfr


def mel_fps():
    unit = cmds.currentUnit(query=True, time=True)
    named = {"game": 15, "film": 24, "pal": 25, "ntsc": 30, "show": 48, "palf": 50, "ntscf": 60}
    if unit in named:
        return named[unit]
    m = re.match(r"([\d.]+)fps", unit)
    return float(m.group(1)) if m else 24


def is_open(gfr):
    """True if a Gaffer on this computer has gfr open (its command line)."""
    if os.name != "nt":
        return False
    script = ("Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
              "ForEach-Object { $_.CommandLine }")
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", script],
                             creationflags=NO_WINDOW, capture_output=True, text=True,
                             timeout=30).stdout or ""
    except (OSError, subprocess.SubprocessError):
        return False
    want = os.path.normcase(os.path.normpath(gfr))
    return any(want in os.path.normcase(line.replace("/", "\\")) for line in out.splitlines()
               if "gaffer" in line.lower())


def launch(gaffer, gfr):
    """Open gfr in Gaffer, on its own (closing Maya leaves it open)."""
    flags = NO_WINDOW | getattr(subprocess, "DETACHED_PROCESS", 0) | \
        getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen([launcher_path(gaffer), "gui", gfr], env=clean_env(),
                     creationflags=flags, close_fds=True)


def send(roots, start_again=False, scene=None, start=None, end=None, open_gaffer=True):
    """Export roots and open (or update) the student's Gaffer file. Returns
    a dict: usd, latest, gfr, made (a new Gaffer file), opened, already_open."""
    gaffer, arnold = settings()
    if not gaffer:
        raise SendError("Gaffer isn't set up on this computer.")
    folder, from_maya, name = target(scene)
    start = cmds.playbackOptions(query=True, minTime=True) if start is None else start
    end = cmds.playbackOptions(query=True, maxTime=True) if end is None else end
    write_launcher(gaffer, arnold)
    usd = export(roots, next_usd(from_maya, name), start, end)
    stage_notes = add_stages(usd, [s for r in roots for s in stages_under(r)])
    latest = write_latest(from_maya, name, usd)
    gfr = None if start_again else latest_gfr(folder, name)
    made = gfr is None
    if made:
        gfr = new_gaffer_file(gaffer, next_gfr(folder, name), latest, folder, name, start, end)
    already = (not made) and is_open(gfr)
    if open_gaffer and not already:
        launch(gaffer, gfr)
    return {"usd": usd, "latest": latest, "gfr": gfr, "made": made,
            "opened": open_gaffer and not already, "already_open": already,
            "stages": stage_notes}


# ---------------------------------------------------------------------------
# The shelf button
# ---------------------------------------------------------------------------

def _ask(message, buttons, default=None):
    return cmds.confirmDialog(title=TITLE, message=message, button=buttons,
                              defaultButton=default or buttons[0], cancelButton=buttons[-1],
                              dismissString=buttons[-1])


def _locate(what, check, hint):
    """Ask for a folder until check(folder) passes; None if cancelled."""
    while True:
        picked_dir = cmds.fileDialog2(fileMode=3, caption="Locate %s" % what,
                                      okCaption="Use This Folder")
        if not picked_dir:
            return None
        found = check(picked_dir[0])
        if found:
            return found
        if _ask("That folder isn't %s:\n  %s\n\n%s" % (what, picked_dir[0], hint),
                ["Try Again", "Cancel"]) != "Try Again":
            return None


def ensure_setup():
    """Ask for Gaffer and the Arnold SDK if the settings don't have them
    (refuse with a fix, pipe rule 9). False if the student cancelled."""
    gaffer, arnold = settings()
    if not gaffer:
        if _ask("Gaffer isn't set up on this computer.\n\nInstall it from the mpPipe bundle "
                "(gaffer\\install.py), or show me where it is.",
                ["Locate Gaffer...", "Cancel"]) != "Locate Gaffer...":
            return False
        gaffer = _locate("a Gaffer folder", find_gaffer,
                         "Pick the folder that holds bin\\gaffer.cmd (or the folder it's in).")
        if not gaffer:
            return False
        save_setting(GAFFER_ROOT, gaffer)
        make_shortcut(gaffer)
    if not arnold:
        answer = _ask("Gaffer renders with the Arnold SDK, a separate free download with your "
                      "Autodesk education licence (the same Arnold version as Maya's: %s).\n\n"
                      "Show me where you unzipped it, or send without Arnold for now."
                      % (_mtoa_arnold() or "7.5"),
                      ["Locate Arnold...", "Send Without Arnold", "Cancel"])
        if answer == "Cancel":
            return False
        if answer == "Locate Arnold...":
            arnold = _locate("an Arnold SDK folder", lambda f: f if is_arnold_sdk(f) else None,
                             "Pick the folder that holds bin, include and plugins "
                             "(e.g. Arnold-7.5.2.0-windows). Maya's own Arnold (MtoA) "
                             "can't be used: Gaffer needs the SDK.")
            if not arnold:
                return False
            save_setting(ARNOLD_ROOT, arnold)
    return True


def _mtoa_arnold():
    try:
        return cmds.arnoldPlugins(getVersion=True) if hasattr(cmds, "arnoldPlugins") else ""
    except Exception:
        return ""


def run():
    """The shelf button."""
    try:
        target()            # refuse before asking anything if the scene is off-pipe
        roots, skipped = picked()
        if not roots:
            why = "".join("\n  %s: %s" % (n.split("|")[-1], r) for n, r in skipped)
            raise SendError("Select what to send to Gaffer: geometry, cameras and lights."
                            + ("\nLeft out:" + why if why else ""))
        if not ensure_setup():
            return None
        folder, _from_maya, name = target()
        current = latest_gfr(folder, name)
        start_again = False
        if current:
            answer = _ask("Send %d item(s) to Gaffer?\n\nCarry On keeps your Gaffer work in %s "
                          "and updates what it reads from Maya. Start Again makes a new Gaffer "
                          "file (the old one is kept)." % (len(roots), os.path.basename(current)),
                          ["Carry On", "Start Again", "Cancel"])
            if answer == "Cancel":
                return None
            start_again = answer == "Start Again"
        result = send(roots, start_again=start_again)
    except (SendError, pub.PublishError, OSError, RuntimeError,
            subprocess.SubprocessError) as e:
        cmds.confirmDialog(title=TITLE, message=str(e), button=["OK"])
        return None
    lines = ["Sent to Gaffer: %s" % os.path.basename(result["usd"]),
             "Gaffer file: %s%s" % (result["gfr"], " (new)" if result["made"] else "")]
    if result["already_open"]:
        lines.append("It's already open in Gaffer: press Reload on the fromMaya node "
                     "(the refresh button by File Name) to see this send.")
    if result["stages"]:
        lines.append("USD stages:" + "".join("\n  " + n for n in result["stages"]))
    if skipped:
        lines.append("Left out:" + "".join("\n  %s: %s" % (n.split("|")[-1], r)
                                            for n, r in skipped))
    print("Send to Gaffer:\n" + "\n".join(lines))
    cmds.inViewMessage(amg="Send to Gaffer: <hl>%s</hl>%s" % (
        os.path.basename(result["usd"]),
        "; press Reload in Gaffer" if result["already_open"] else "; opening Gaffer"),
        pos="topCenter", fade=True)
    if skipped or any("unsaved" in n or "wasn't found" in n for n in result["stages"]):
        cmds.confirmDialog(title=TITLE, message="\n".join(lines), button=["OK"])
    return result
