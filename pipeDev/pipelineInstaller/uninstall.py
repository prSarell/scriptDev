"""
mpPipe Uninstaller (staff testing)
==================================
Drag and drop this file onto the Maya viewport to remove the files and
the mpPipe and mpLayout shelves that install.py put in place.

Also takes the mpPipe startup block (PIPE_SCRATCH) out of userSetup.py.
Left alone: the drive settings (pipeline_config.json in Maya prefs),
mpToolSet and its ShotGrid connection, and anything on the scratch and
H drives.
"""

import os
import re
import sys
import maya.cmds as cmds


_MANIFEST_NAME = "mpPipe_manifest.txt"
_TITLE = "mpPipe Uninstaller"
_US_START = "# -- mpPipe BEGIN --"     # must match install.py
_US_END = "# -- mpPipe END --"


def _prefs_dir():
    return cmds.internalVar(userPrefDir=True).replace("\\", "/")


def _strip_usersetup(path):
    """Take the mpPipe startup block (PIPE_SCRATCH) out of userSetup.py,
    leaving everything else in the file, and stop it in this session."""
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        new = re.sub(r"\n?" + re.escape(_US_START) + r".*?" + re.escape(_US_END) + r"\n?",
                     "\n", content, flags=re.DOTALL)
        if new != content:
            with open(path, "w", encoding="utf-8") as f:
                f.write(new.rstrip("\n") + "\n" if new.strip() else "")
    for attr in ("_pipeEnv_callback_id", "_pipeEnv_after_open_id"):
        callback = getattr(sys, attr, None)
        if callback is not None:
            try:
                import maya.api.OpenMaya as om
                om.MMessage.removeCallback(callback)
            except Exception:
                pass
            delattr(sys, attr)


def _uninstall():
    manifest = os.path.join(_prefs_dir(), _MANIFEST_NAME)
    if not os.path.isfile(manifest):
        cmds.confirmDialog(title=_TITLE, message="mpPipe doesn't seem to be installed.",
                           button=["OK"])
        return
    if cmds.confirmDialog(title=_TITLE, message="Remove the mpPipe tools and shelf?",
                          button=["Remove", "Cancel"], defaultButton="Cancel",
                          cancelButton="Cancel", dismissString="Cancel") != "Remove":
        return

    with open(manifest, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
    removed = 0
    for line in lines:
        kind, _, value = line.partition(":")
        if kind == "file" and os.path.isfile(value):
            os.remove(value)
            removed += 1
            cache = os.path.join(os.path.dirname(value), "__pycache__")
            stem = os.path.splitext(os.path.basename(value))[0] + "."
            if os.path.isdir(cache):
                for name in os.listdir(cache):
                    if name.startswith(stem):
                        os.remove(os.path.join(cache, name))
        elif kind == "usersetup":
            _strip_usersetup(value)
        elif kind == "shelf":
            if cmds.shelfLayout(value, exists=True):
                cmds.deleteUI(value, layout=True)
            shelf_file = os.path.join(_prefs_dir(), "shelves", "shelf_%s.mel" % value)
            if os.path.isfile(shelf_file):
                os.remove(shelf_file)
    os.remove(manifest)

    summary = ("mpPipe removed: %d files and the shelves.\n\n"
               "Your H drive / Scratch drive settings were kept." % removed)
    print(summary)
    cmds.confirmDialog(title=_TITLE, message=summary, button=["OK"])


def onMayaDroppedPythonFile(_obj):
    """Called by Maya when this file is dragged onto the viewport."""
    try:
        _uninstall()
    except Exception as e:
        import traceback
        print("mpPipe uninstall FAILED:\n\n%s\n\n%s" % (e, traceback.format_exc()))
        cmds.confirmDialog(title=_TITLE + " — Error",
                           message="Uninstall failed! See Script Editor for details.\n\n%s" % e,
                           button=["OK"])
    finally:
        # Same as install.py: don't let a later drop of another uninstall.py
        # this session run this one instead.
        sys.modules.pop(__name__, None)
