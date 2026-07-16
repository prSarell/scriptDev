"""
ngSkinTools2 Installer
=======================
Drag and drop this file onto the Maya viewport to install or update
ngSkinTools2. This is separate from the main mpToolSet install.py —
run it once, on its own, whenever you want to install or update
ngSkinTools2.

ngSkinTools2 is a third-party plugin, distributed here as an Autodesk
Application Plugin (PackageContents.xml). It installs into Maya's
ApplicationPlugins folder, where Maya discovers and loads it on
startup automatically — no userSetup.py changes needed.
"""

import os
import shutil
import subprocess
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


_SKIP = {"install.py", "uninstall.py", _MANIFEST_NAME, "__pycache__"}


def _install(root):
    src = root.replace("\\", "/")
    plugins_dst = _app_plugins_dir()
    os.makedirs(plugins_dst, exist_ok=True)
    dst = os.path.join(plugins_dst, _PLUGIN_NAME).replace("\\", "/")

    if os.path.exists(dst):
        try:
            if cmds.pluginInfo("ngSkinTools2", q=True, loaded=True):
                cmds.unloadPlugin("ngSkinTools2", force=True)
        except RuntimeError:
            pass
        try:
            shutil.rmtree(dst)
        except PermissionError:
            raise RuntimeError(
                "Could not update ngSkinTools2 — its plugin file is still "
                "locked by this Maya session. Restart Maya and run this "
                "installer again before opening any scene that uses "
                "ngSkinTools2."
            )

    shutil.copytree(src, dst, ignore=lambda _dir, names: _SKIP & set(names))

    if sys.platform == "darwin":
        subprocess.run(
            ["xattr", "-dr", "com.apple.quarantine", dst], check=False,
        )

    with open(_manifest_path(), "w") as f:
        f.write("dir:{}\n".format(dst))

    summary = (
        "ngSkinTools2 installed successfully!\n\n"
        "  Installed to: {}\n\n"
        "  ** Restart Maya for ngSkinTools2 to become available. **\n\n"
        "To uninstall, drag uninstall.py (in this same folder) onto "
        "the viewport."
    ).format(dst)
    print(summary)
    cmds.confirmDialog(
        title="ngSkinTools2 Installer",
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
        msg = "ngSkinTools2 install FAILED:\n\n{}\n\n{}".format(e, traceback.format_exc())
        print(msg)
        cmds.confirmDialog(
            title="ngSkinTools2 Installer — Error",
            message="Install failed! See Script Editor for details.\n\n{}".format(e),
            button=["OK"],
        )
