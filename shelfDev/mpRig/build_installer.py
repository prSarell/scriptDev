"""
build_installer.py — run this outside Maya to generate dist/mpRig_installer.py.

Usage:
    mayapy build_installer.py

Bump SHELF_VERSION in shelf_config.py before each release.

Output: dist/
    mpRig_installer.py  <- drag this onto Maya viewport
"""

import base64
import importlib.util
import os
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS_DIR = os.path.join(HERE, "tools")
RIGTOOL_DIR = os.path.normpath(os.path.join(HERE, "..", "..", "rigDev"))
ICONS_DIR = os.path.join(HERE, "icons")
DIST_DIR = os.path.join(HERE, "dist")

spec = importlib.util.spec_from_file_location(
    "shelf_config", os.path.join(HERE, "shelf_config.py")
)
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)


def _bundle_scripts():
    bundled = {}

    all_scripts = list(config.EXTRA_SCRIPTS)
    for btn in config.BUTTONS:
        name = btn.get("script", "")
        if name and name not in all_scripts:
            all_scripts.append(name)
    for name in all_scripts:
        path = os.path.join(TOOLS_DIR, name)
        if not os.path.exists(path):
            print(f"  WARNING: script not found in tools/ — skipping: {name}")
            continue
        with open(path, "r", encoding="utf-8") as fh:
            bundled[name] = base64.b64encode(fh.read().encode("utf-8")).decode("ascii")

    for name in getattr(config, "RIGTOOL_SCRIPTS", []):
        path = os.path.join(RIGTOOL_DIR, name)
        if not os.path.exists(path):
            print(f"  WARNING: rigDev script not found — skipping: {name}")
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


INSTALLER_TEMPLATE = '''\
# {shelf_name}_installer.py
# Version : {version}
# Built   : {build_date}
#
# Drag this file into a Maya viewport to install the {shelf_name} shelf.
# Running it again will refresh all scripts and buttons.

import base64
import os

_SHELF_NAME = {shelf_name_r}
_SHELF_VERSION = {version_r}
_BUTTONS = {buttons_r}
_BUNDLED = {bundled_r}
_ICONS = {icons_r}


def _install():
    import maya.cmds as cmds
    import maya.mel as mel

    scripts_dir = os.path.join(cmds.internalVar(userAppDir=True), "scripts")
    os.makedirs(scripts_dir, exist_ok=True)
    for filename, encoded in _BUNDLED.items():
        dest = os.path.join(scripts_dir, filename)
        with open(dest, "w", encoding="utf-8") as fh:
            fh.write(base64.b64decode(encoded.encode("ascii")).decode("utf-8"))

    icons_dir = cmds.internalVar(userBitmapsDir=True)
    os.makedirs(icons_dir, exist_ok=True)
    for filename, encoded in _ICONS.items():
        dest = os.path.join(icons_dir, filename)
        with open(dest, "wb") as fh:
            fh.write(base64.b64decode(encoded.encode("ascii")))

    shelf_top = mel.eval("$tmpVar=$gShelfTopLevel")
    existing_tabs = cmds.shelfTabLayout(shelf_top, query=True, childArray=True) or []

    if _SHELF_NAME not in existing_tabs:
        mel.eval(f\'addNewShelfTab "{{_SHELF_NAME}}"\')\n        print("[{shelf_name} installer] created new shelf tab")

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
            print("[{shelf_name} installer] added button: " + btn["label"])
        except Exception as e:
            print("[{shelf_name} installer] ERROR adding " + btn["label"] + ": " + str(e))

    mel.eval("saveAllShelves $gShelfTopLevel")
    print("[{shelf_name} installer] done")

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

    print(f"  Output  : {out_path}")
    print(f"  Buttons : {len(config.BUTTONS)}")
    print(f"  Scripts : {list(bundled.keys()) or '(none)'}")
    print(f"  Icons   : {list(icons.keys()) or '(none)'}")


if __name__ == "__main__":
    main()
