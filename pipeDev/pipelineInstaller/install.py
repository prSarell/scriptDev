"""
mpPipe Installer (staff testing)
================================
Drag and drop this file onto the Maya viewport to install the film
pipeline tools (Publish, Build) and the mpPipe shelf.

Needs mpToolSet installed first: it supplies the ShotGrid connection
(shotgridConnect, shotgun_api3 and the connection settings). This package
never contains ShotGrid credentials.

To remove everything again, drag uninstall.py onto the viewport.
"""

import os
import shutil
import maya.cmds as cmds
import maya.mel as mel


_MANIFEST_NAME = "mpPipe_manifest.txt"
_TITLE = "mpPipe Installer"

# Startup block in the user's scripts/userSetup.py: sets up $PIPE_SCRATCH
# (pipeEnv.py) before any scene opens, so shot references load from
# whichever drive the shot is on (spec §3i "Reference paths that work on
# any drive"). Marked so it can be replaced on reinstall and removed by
# uninstall.py without touching anything else in the file (mpToolSet and
# mpInstaller keep their own lines there).
_US_START = "# -- mpPipe BEGIN --"
_US_END = "# -- mpPipe END --"
_US_BLOCK = (
    _US_START + "\n"
    "try:\n"
    "    import pipeEnv; pipeEnv.install()\n"
    "except Exception as _mpPipe_error:\n"
    "    print('mpPipe: PIPE_SCRATCH not set up: %s' % _mpPipe_error)\n"
    + _US_END + "\n")


def _scripts_dir():
    return os.path.join(cmds.internalVar(userAppDir=True), "scripts").replace("\\", "/")


def _prefs_dir():
    return cmds.internalVar(userPrefDir=True).replace("\\", "/")


def _icons_dir():
    return os.path.join(_prefs_dir(), "icons").replace("\\", "/")


def _shelves_dir():
    return os.path.join(_prefs_dir(), "shelves").replace("\\", "/")


def _copy_all(src_dir, dst_dir, ext):
    copied = []
    os.makedirs(dst_dir, exist_ok=True)
    for name in sorted(os.listdir(src_dir)):
        src = os.path.join(src_dir, name)
        if os.path.isfile(src) and name.lower().endswith(ext):
            dst = os.path.join(dst_dir, name).replace("\\", "/")
            shutil.copy2(src, dst)
            copied.append(dst)
    return copied


def _build_shelf(config_path):
    config = {}
    with open(config_path, "r", encoding="utf-8") as f:
        exec(f.read(), config)
    name = config["SHELF_NAME"]
    if cmds.shelfLayout(name, exists=True):
        cmds.deleteUI(name, layout=True)
    top = mel.eval("$tmpVar=$gShelfTopLevel")
    cmds.shelfLayout(name, parent=top)
    for btn in config["BUTTONS"]:
        icon = os.path.join(_icons_dir(), btn["icon"]).replace("\\", "/")
        cmds.shelfButton(parent=name, label=btn["label"], annotation=btn["tooltip"],
                         image1=icon if os.path.isfile(icon) else btn["icon"],
                         command=btn["command"], sourceType="python")
    cmds.saveAllShelves(top)
    return name, len(config["BUTTONS"])


def _patch_usersetup():
    """Add (or replace) the mpPipe block at the end of userSetup.py, then
    run it now so this session is set up without restarting Maya."""
    import re
    path = os.path.join(_scripts_dir(), "userSetup.py").replace("\\", "/")
    content = ""
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    content = re.sub(r"\n?" + re.escape(_US_START) + r".*?" + re.escape(_US_END) + r"\n?",
                     "\n", content, flags=re.DOTALL)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content.rstrip("\n") + ("\n\n" if content.strip() else "") + _US_BLOCK)
    import importlib
    import pipeEnv
    importlib.reload(pipeEnv)
    return path, pipeEnv.install()


def _check_dependencies():
    """What the tools need from mpToolSet / the machine. Returns warnings."""
    warnings = []
    try:
        import shotgridConnect                      # noqa: F401
    except ImportError:
        warnings.append("shotgridConnect not found: install mpToolSet first "
                        "(Publish needs it for ShotGrid).")
    try:
        import shotgun_api3                         # noqa: F401
    except ImportError:
        warnings.append("shotgun_api3 not found: install mpToolSet first.")
    if not os.path.isfile(os.path.join(_prefs_dir(), "shotSub_config.json")):
        warnings.append("No ShotGrid connection settings (shotSub_config.json): "
                        "install mpToolSet from its release zip.")
    rv = [p for p in ("C:/Program Files/Autodesk", "C:/Program Files/Shotgun",
                      "C:/Program Files/ShotGrid")
          if os.path.isdir(p) and any(n.startswith("RV-") for n in os.listdir(p))]
    if not rv and not shutil.which("rvio"):
        warnings.append("RV not found: publishes will reach ShotGrid with a "
                        "thumbnail but no playable movie.")
    return warnings


def _install(root):
    scripts = _copy_all(os.path.join(root, "scripts"), _scripts_dir(), ".py")
    icons = _copy_all(os.path.join(root, "icons"), _icons_dir(), ".png")
    shelf, buttons = _build_shelf(os.path.join(root, "shelf_config.py"))
    usersetup, scratch_var = _patch_usersetup()

    with open(os.path.join(_prefs_dir(), _MANIFEST_NAME), "w", encoding="utf-8") as f:
        f.write("shelf:%s\n" % shelf)
        f.write("usersetup:%s\n" % usersetup)
        for path in scripts + icons:
            f.write("file:%s\n" % path)

    version = ""
    version_file = os.path.join(root, "version.txt")
    if os.path.isfile(version_file):
        with open(version_file, "r", encoding="utf-8") as f:
            version = f.read().strip()

    warnings = _check_dependencies()
    summary = (
        "mpPipe installed%s\n\n"
        "  Scripts: %d -> %s\n"
        "  Icons:   %d -> %s\n"
        "  Shelf:   %s (%d buttons)\n"
        "  Startup: userSetup.py sets PIPE_SCRATCH (now: %s)\n"
        % (" (build %s)" % version if version else "", len(scripts), _scripts_dir(),
           len(icons), _icons_dir(), shelf, buttons,
           scratch_var or "set when you open a scene"))
    if warnings:
        summary += "\nCheck before publishing:\n" + "\n".join("  - " + w for w in warnings) + "\n"
    summary += ("\nFirst run: set the H drive and Scratch drive in the tool.\n"
                "To uninstall, drag uninstall.py onto the viewport.")
    print(summary)
    cmds.confirmDialog(title=_TITLE, message=summary, button=["OK"])


def onMayaDroppedPythonFile(_obj):
    """Called by Maya when this file is dragged onto the viewport."""
    root = os.path.dirname(os.path.abspath(__file__))
    try:
        _install(root)
    except Exception as e:
        import traceback
        print("mpPipe install FAILED:\n\n%s\n\n%s" % (e, traceback.format_exc()))
        cmds.confirmDialog(title=_TITLE + " — Error",
                           message="Install failed! See Script Editor for details.\n\n%s" % e,
                           button=["OK"])
