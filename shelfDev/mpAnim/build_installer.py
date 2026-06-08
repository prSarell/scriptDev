"""
build_installer.py — run this outside Maya to generate dist/mpAnim_installer.py.

Usage:
    mayapy build_installer.py

Bump SHELF_VERSION in shelf_config.py before each release so students
can see which version they are installing.

Output: dist/
    mpAnim_installer.py     <- drag this onto Maya viewport
    studiolibrary_src/      <- Studio Library packages (deployed at install time)
"""

import base64
import importlib.util
import os
import shutil
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS_DIR = os.path.join(HERE, "tools")
MULTITOOL_DIR = os.path.normpath(os.path.join(HERE, "..", "..", "animDev", "multiTool"))
JIFFYPOMO_DIR = os.path.normpath(os.path.join(HERE, "..", "..", "timeManagementDev", "jiffyPomoDev"))
ICONS_DIR = os.path.join(HERE, "icons")
DIST_DIR = os.path.join(HERE, "dist")
STUDIOLIB_SRC = os.path.normpath(
    os.path.join(HERE, "..", "..", "animDev", "studiolibrary-2.20.2", "src")
)

spec = importlib.util.spec_from_file_location(
    "shelf_config", os.path.join(HERE, "shelf_config.py")
)
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)


def _bundle_scripts():
    bundled = {}

    # tools/ scripts (EXTRA_SCRIPTS + button scripts)
    all_scripts = list(config.EXTRA_SCRIPTS)
    for btn in config.BUTTONS:
        name = btn.get("script", "")
        if name and name not in all_scripts:
            all_scripts.append(name)
    for name in all_scripts:
        path = os.path.join(TOOLS_DIR, name)
        if not os.path.exists(path):
            print(f"  WARNING: script not found — skipping: {path}")
            continue
        with open(path, "r", encoding="utf-8") as fh:
            bundled[name] = base64.b64encode(fh.read().encode("utf-8")).decode("ascii")

    # animDev/multiTool/ scripts
    for name in getattr(config, "MULTITOOL_SCRIPTS", []):
        path = os.path.join(MULTITOOL_DIR, name)
        if not os.path.exists(path):
            print(f"  WARNING: multiTool script not found — skipping: {path}")
            continue
        with open(path, "r", encoding="utf-8") as fh:
            bundled[name] = base64.b64encode(fh.read().encode("utf-8")).decode("ascii")

    # timeManagementDev/jiffyPomoDev/ scripts
    for name in getattr(config, "JIFFYPOMO_SCRIPTS", []):
        path = os.path.join(JIFFYPOMO_DIR, name)
        if not os.path.exists(path):
            print(f"  WARNING: jiffyPomo script not found — skipping: {path}")
            continue
        with open(path, "r", encoding="utf-8") as fh:
            bundled[name] = base64.b64encode(fh.read().encode("utf-8")).decode("ascii")

    return bundled


def _bundle_icons():
    bundled = {}
    for btn in config.BUTTONS:
        name = btn.get("icon", "")
        if not name:
            continue
        path = os.path.join(ICONS_DIR, name)
        if not os.path.exists(path):
            continue  # built-in Maya icon, nothing to bundle
        with open(path, "rb") as fh:
            bundled[name] = base64.b64encode(fh.read()).decode("ascii")
    return bundled


def _copy_studiolibrary():
    """Copy Studio Library src packages into dist/studiolibrary_src/."""
    if not os.path.exists(STUDIOLIB_SRC):
        print(f"  WARNING: Studio Library src not found at {STUDIOLIB_SRC} — skipping")
        return False
    dest = os.path.join(DIST_DIR, "studiolibrary_src")
    if os.path.exists(dest):
        shutil.rmtree(dest)
    shutil.copytree(STUDIOLIB_SRC, dest)
    return True


INSTALLER_TEMPLATE = '''\
# {shelf_name}_installer.py
# Version : {version}
# Built   : {build_date}
#
# Drag this file into a Maya viewport to install the {shelf_name} shelf.
# The studiolibrary_src/ folder must sit next to this file (it does if
# you downloaded the whole dist/ folder).
# Running it again will refresh all scripts and buttons.

import base64
import os

_SHELF_NAME = {shelf_name_r}
_SHELF_VERSION = {version_r}
_BUTTONS = {buttons_r}
_BUNDLED = {bundled_r}
_ICONS = {icons_r}

_USERSETUP_MARKER = "# multiTool auto-load (mpAnim installer)"
_USERSETUP_LINE = "import maya.utils; maya.utils.executeDeferred('import multiTool; multiTool.show()')"


def _install():
    import shutil
    import maya.cmds as cmds
    import maya.mel as mel

    # Deploy tool scripts
    scripts_dir = os.path.join(cmds.internalVar(userAppDir=True), "scripts")
    os.makedirs(scripts_dir, exist_ok=True)
    for filename, encoded in _BUNDLED.items():
        dest = os.path.join(scripts_dir, filename)
        with open(dest, "w", encoding="utf-8") as fh:
            fh.write(base64.b64decode(encoded.encode("ascii")).decode("utf-8"))

    # Deploy custom icons
    icons_dir = cmds.internalVar(userBitmapsDir=True)
    os.makedirs(icons_dir, exist_ok=True)
    for filename, encoded in _ICONS.items():
        dest = os.path.join(icons_dir, filename)
        with open(dest, "wb") as fh:
            fh.write(base64.b64decode(encoded.encode("ascii")))

    # Deploy Studio Library packages from the folder next to this installer
    installer_dir = os.path.dirname(os.path.abspath(__file__))
    studiolib_src = os.path.join(installer_dir, "studiolibrary_src")
    if os.path.exists(studiolib_src):
        for pkg_name in os.listdir(studiolib_src):
            src = os.path.join(studiolib_src, pkg_name)
            if os.path.isdir(src):
                dst = os.path.join(scripts_dir, pkg_name)
                if os.path.exists(dst):
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
        print("[mpAnim installer] deployed Studio Library packages")
    else:
        print("[mpAnim installer] WARNING: studiolibrary_src not found — Studio Library button may not work")

    # Patch userSetup.py so animMultiTool loads on every Maya start
    usersetup = os.path.join(scripts_dir, "userSetup.py")
    existing = ""
    if os.path.exists(usersetup):
        with open(usersetup, "r", encoding="utf-8") as fh:
            existing = fh.read()
    _OLD_MARKERS = [
        "# animMultiTool auto-load (mpAnim installer)",
        "import animMultiTool; animMultiTool.show()",
        "import maya.utils; maya.utils.executeDeferred('import animMultiTool; animMultiTool.show()')",
    ]
    for old in _OLD_MARKERS:
        if old in existing:
            existing = existing.replace(old, "")
    existing = "\\n".join(line for line in existing.splitlines() if line.strip())
    if _USERSETUP_MARKER not in existing:
        with open(usersetup, "a", encoding="utf-8") as fh:
            fh.write("\\n" + _USERSETUP_MARKER + "\\n" + _USERSETUP_LINE + "\\n")
        print("[mpAnim installer] patched userSetup.py for multiTool auto-load")
    else:
        print("[mpAnim installer] userSetup.py already patched")

    # Build / refresh shelf
    shelf_top = mel.eval("$tmpVar=$gShelfTopLevel")
    existing_tabs = cmds.shelfTabLayout(shelf_top, query=True, childArray=True) or []

    if _SHELF_NAME not in existing_tabs:
        mel.eval(f'addNewShelfTab "{{_SHELF_NAME}}"')
        print("[mpAnim installer] created new shelf tab")

    shelf = f"{{shelf_top}}|{{_SHELF_NAME}}"
    for old_btn in cmds.shelfLayout(shelf, query=True, childArray=True) or []:
        cmds.deleteUI(old_btn)

    for btn in _BUTTONS:
        try:
            cmds.shelfButton(
                parent=shelf,
                label=btn["label"],
                annotation=btn["tooltip"],
                image1=btn.get("icon", "commandButton.png"),
                command=btn["command"],
                sourceType="python",
            )
            print("[mpAnim installer] added button: " + btn["label"])
        except Exception as e:
            print("[mpAnim installer] ERROR adding " + btn["label"] + ": " + str(e))

    mel.eval("saveAllShelves $gShelfTopLevel")
    print("[mpAnim installer] done")

    cmds.evalDeferred("import multiTool; multiTool.show()")
    print("[mpAnim installer] multiTool queued for launch")

    # Prompt for save path on first install — silently skips if already configured
    cmds.evalDeferred("import mpAnimConfig; mpAnimConfig.get_save_path()")
    print("[mpAnim installer] mpAnimConfig path check queued")

    cmds.inViewMessage(
        amg=f"<b>{{_SHELF_NAME}} v{{_SHELF_VERSION}}</b> installed successfully.",
        pos="midCenter",
        fade=True,
    )


def onMayaDroppedPythonFile(*args):
    import sys
    import importlib
    mod = sys.modules.get(__name__)
    if mod is not None:
        importlib.reload(mod)
        sys.modules[__name__]._install()
    else:
        _install()
'''


def main():
    print(f"Building installer for {config.SHELF_NAME} v{config.SHELF_VERSION}...")

    bundled = _bundle_scripts()
    icons = _bundle_icons()

    os.makedirs(DIST_DIR, exist_ok=True)
    has_studiolib = _copy_studiolibrary()

    installer = INSTALLER_TEMPLATE.format(
        shelf_name=config.SHELF_NAME,
        shelf_name_r=repr(config.SHELF_NAME),
        version=config.SHELF_VERSION,
        version_r=repr(config.SHELF_VERSION),
        build_date=datetime.now().strftime("%Y-%m-%d %H:%M"),
        buttons_r=repr(config.BUTTONS),
        bundled_r=repr(bundled),
        icons_r=repr(icons),
    )

    out_path = os.path.join(DIST_DIR, f"{config.SHELF_NAME}_installer.py")
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(installer)

    print(f"  Output   : {out_path}")
    print(f"  Buttons  : {len(config.BUTTONS)}")
    print(f"  Scripts  : {list(bundled.keys()) or '(none)'}")
    print(f"  Icons    : {list(icons.keys()) or '(none)'}")
    print(f"  StudioLib: {'copied to dist/studiolibrary_src/' if has_studiolib else 'NOT FOUND'}")


if __name__ == "__main__":
    main()
