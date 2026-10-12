"""
mpPipe Uninstaller (staff testing)
==================================
Drag and drop this file onto the Maya viewport to remove the files and
the mpPipe shelf that install.py put in place.

Left alone: the drive settings (pipeline_config.json in Maya prefs),
mpToolSet and its ShotGrid connection, and anything on the scratch and
H drives.
"""

import os
import maya.cmds as cmds


_MANIFEST_NAME = "mpPipe_manifest.txt"
_TITLE = "mpPipe Uninstaller"


def _prefs_dir():
    return cmds.internalVar(userPrefDir=True).replace("\\", "/")


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
        elif kind == "shelf":
            if cmds.shelfLayout(value, exists=True):
                cmds.deleteUI(value, layout=True)
            shelf_file = os.path.join(_prefs_dir(), "shelves", "shelf_%s.mel" % value)
            if os.path.isfile(shelf_file):
                os.remove(shelf_file)
    os.remove(manifest)

    summary = ("mpPipe removed: %d files and the shelf.\n\n"
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
