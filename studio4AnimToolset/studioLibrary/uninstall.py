"""
Studio Library Uninstaller
============================
Drag and drop this file onto the Maya viewport to remove Studio Library
(installed separately via install.py in this same folder).
"""

import os
import shutil
import maya.cmds as cmds


_PACKAGES = ["mutils", "studiolibrary", "studiolibrarymaya", "studioqt", "studiovendor"]
_MANIFEST_NAME = "studioLibrary_manifest.txt"


def _maya_scripts_dir():
    return os.path.join(
        cmds.internalVar(userAppDir=True), "scripts"
    ).replace("\\", "/")


def _manifest_path():
    return os.path.join(
        cmds.internalVar(userPrefDir=True), _MANIFEST_NAME
    ).replace("\\", "/")


def _uninstall():
    manifest = _manifest_path()
    scripts_dst = _maya_scripts_dir()
    targets = [os.path.join(scripts_dst, pkg).replace("\\", "/") for pkg in _PACKAGES]
    existing = [t for t in targets if os.path.isdir(t)]

    if not os.path.isfile(manifest) and not existing:
        cmds.confirmDialog(
            title="Studio Library Uninstaller",
            message="Nothing to uninstall — Studio Library does not appear "
                    "to be installed.",
            button=["OK"],
        )
        return

    choice = cmds.confirmDialog(
        title="Studio Library Uninstaller",
        message="This will remove Studio Library from Maya.\n\nContinue?",
        button=["Remove", "Cancel"],
        defaultButton="Cancel",
        cancelButton="Cancel",
        dismissString="Cancel",
    )
    if choice == "Cancel":
        return

    removed = 0
    errors = []
    for path in existing:
        try:
            shutil.rmtree(path)
            removed += 1
        except Exception as e:
            errors.append("{}: {}".format(path, e))

    if os.path.isfile(manifest):
        os.remove(manifest)

    if errors:
        summary = "Studio Library could not be fully removed:\n\n" + "\n".join(errors)
    elif removed:
        summary = "Studio Library removed ({} package folder(s)).".format(removed)
    else:
        summary = "Studio Library was not found installed — nothing to remove."

    print(summary)
    cmds.confirmDialog(
        title="Studio Library Uninstaller",
        message=summary,
        button=["OK"],
    )


def onMayaDroppedPythonFile(_obj):
    """Called by Maya when this file is dragged onto the viewport."""
    _uninstall()
