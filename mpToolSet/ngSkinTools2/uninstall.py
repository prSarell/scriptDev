"""
ngSkinTools2 Uninstaller
=========================
Drag and drop this file onto the Maya viewport to remove ngSkinTools2
(installed separately via install.py in this same folder).
"""

import os
import shutil
import sys
import maya.cmds as cmds


_PLUGIN_NAME = "ngSkinTools2"
_MANIFEST_NAME = "ngSkinTools2_manifest.txt"


def _app_plugins_dir():
    if sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("APPDATA", "")
    return os.path.join(base, "Autodesk", "ApplicationPlugins").replace("\\", "/")


def _manifest_path():
    return os.path.join(
        cmds.internalVar(userPrefDir=True), _MANIFEST_NAME
    ).replace("\\", "/")


def _uninstall():
    manifest = _manifest_path()
    dst = os.path.join(_app_plugins_dir(), _PLUGIN_NAME).replace("\\", "/")

    if not os.path.isfile(manifest) and not os.path.isdir(dst):
        cmds.confirmDialog(
            title="ngSkinTools2 Uninstaller",
            message="Nothing to uninstall — ngSkinTools2 does not appear "
                    "to be installed.",
            button=["OK"],
        )
        return

    choice = cmds.confirmDialog(
        title="ngSkinTools2 Uninstaller",
        message="This will remove ngSkinTools2 from Maya.\n\nContinue?",
        button=["Remove", "Cancel"],
        defaultButton="Cancel",
        cancelButton="Cancel",
        dismissString="Cancel",
    )
    if choice == "Cancel":
        return

    try:
        if cmds.pluginInfo("ngSkinTools2", q=True, loaded=True):
            cmds.unloadPlugin("ngSkinTools2", force=True)
    except RuntimeError:
        pass

    removed = False
    error = None
    if os.path.isdir(dst):
        try:
            shutil.rmtree(dst)
            removed = True
        except Exception as e:
            error = str(e)

    if os.path.isfile(manifest):
        os.remove(manifest)

    if error:
        summary = "ngSkinTools2 could not be fully removed:\n\n{}".format(error)
    elif removed:
        summary = "ngSkinTools2 removed."
    else:
        summary = "ngSkinTools2 was not found installed — nothing to remove."

    print(summary)
    cmds.confirmDialog(
        title="ngSkinTools2 Uninstaller",
        message=summary,
        button=["OK"],
    )


def onMayaDroppedPythonFile(_obj):
    """Called by Maya when this file is dragged onto the viewport."""
    _uninstall()
