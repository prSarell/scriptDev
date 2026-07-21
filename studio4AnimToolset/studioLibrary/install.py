"""
Studio Library Installer
=========================
Drag and drop this file onto the Maya viewport to install or update
Studio Library. This is separate from the main studio4Anim install.py —
run it once, on its own, whenever you want to install or update
Studio Library.

Studio Library deploys as a set of top-level Python packages (mutils,
studiolibrary, studiolibrarymaya, studioqt, studiovendor) directly into
Maya's scripts folder, where the StudioLib shelf button's `import
studiolibrary` finds them.
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


def _install(root):
    src_root = root.replace("\\", "/")
    scripts_dst = _maya_scripts_dir()
    os.makedirs(scripts_dst, exist_ok=True)

    installed = []
    failed = []

    for pkg_name in _PACKAGES:
        pkg_src = os.path.join(src_root, pkg_name)
        if not os.path.isdir(pkg_src):
            continue
        pkg_dst = os.path.join(scripts_dst, pkg_name).replace("\\", "/")
        try:
            # Merge-copy, not rmtree-then-copy: deleting a live package
            # directory can fail with PermissionError on Windows if any of
            # its modules (or their __pycache__) are still loaded by the
            # running Maya session — e.g. Studio Library is currently open.
            shutil.copytree(pkg_src, pkg_dst, dirs_exist_ok=True)
            installed.append(pkg_dst)
        except Exception as e:
            failed.append("{} — {}".format(pkg_name, e))

    with open(_manifest_path(), "w") as f:
        for d in installed:
            f.write("dir:{}\n".format(d))

    summary = (
        "Studio Library installed successfully!\n\n"
        "  Packages: {}\n"
        "  Location: {}\n\n"
        "To uninstall, drag uninstall.py (in this same folder) onto "
        "the viewport."
    ).format(", ".join(_PACKAGES), scripts_dst)

    if failed:
        summary += (
            "\n\n  WARNING — some packages could not be updated:\n    "
            + "\n    ".join(failed)
            + "\n\n  If Studio Library is currently open, close it and run "
              "this installer again."
        )

    print(summary)
    cmds.confirmDialog(
        title="Studio Library Installer",
        message=summary,
        button=["OK"],
    )


def onMayaDroppedPythonFile(_obj):
    """Called by Maya when this file is dragged onto the viewport."""
    root = os.path.dirname(os.path.abspath(__file__))
    try:
        _install(root)
    except Exception as e:
        import traceback
        msg = "Studio Library install FAILED:\n\n{}\n\n{}".format(e, traceback.format_exc())
        print(msg)
        cmds.confirmDialog(
            title="Studio Library Installer — Error",
            message="Install failed! See Script Editor for details.\n\n{}".format(e),
            button=["OK"],
        )
