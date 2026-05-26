"""
build_installer.py — run this outside Maya to generate dist/mpAnim_installer.py.

Usage:
    python build_installer.py

Bump SHELF_VERSION in shelf_config.py before each release so students
can see which version they are installing.
"""

import base64
import importlib.util
import os
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS_DIR = os.path.join(HERE, "tools")
DIST_DIR = os.path.join(HERE, "dist")

spec = importlib.util.spec_from_file_location(
    "shelf_config", os.path.join(HERE, "shelf_config.py")
)
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)


def _bundle_scripts():
    bundled = {}
    for btn in config.BUTTONS:
        name = btn["script"]
        path = os.path.join(TOOLS_DIR, name)
        if not os.path.exists(path):
            print(f"  WARNING: script not found — skipping: {path}")
            continue
        with open(path, "r", encoding="utf-8") as fh:
            bundled[name] = base64.b64encode(fh.read().encode("utf-8")).decode("ascii")
    return bundled


INSTALLER_TEMPLATE = '''\
# {shelf_name}_installer.py
# Version : {version}
# Built   : {build_date}
#
# Drag this file into a Maya viewport to install the {shelf_name} shelf.
# Running it again will remove the old shelf and install a fresh copy.

import base64
import os

_SHELF_NAME = {shelf_name_r}
_SHELF_VERSION = {version_r}
_BUTTONS = {buttons_r}
_BUNDLED = {bundled_r}


def _install():
    import maya.cmds as cmds
    import maya.mel as mel

    scripts_dir = os.path.join(cmds.internalVar(userAppDir=True), "scripts")
    os.makedirs(scripts_dir, exist_ok=True)
    for filename, encoded in _BUNDLED.items():
        dest = os.path.join(scripts_dir, filename)
        with open(dest, "w", encoding="utf-8") as fh:
            fh.write(base64.b64decode(encoded.encode("ascii")).decode("utf-8"))

    shelf_top = mel.eval("$tmpVar=$gShelfTopLevel")
    existing = cmds.shelfTabLayout(shelf_top, query=True, childArray=True) or []
    if _SHELF_NAME in existing:
        cmds.deleteUI(f"{{shelf_top}}|{{_SHELF_NAME}}")

    cmds.setParent(shelf_top)
    shelf = cmds.shelfLayout(_SHELF_NAME)
    for btn in _BUTTONS:
        cmds.shelfButton(
            parent=shelf,
            label=btn["label"],
            annotation=btn["tooltip"],
            image1=btn.get("icon", "commandButton.png"),
            command=btn["command"],
            sourceType="python",
        )

    mel.eval("saveAllShelves $gShelfTopLevel")

    cmds.confirmDialog(
        title=f"{{_SHELF_NAME}} Installed",
        message=(
            f"{{_SHELF_NAME}} v{{_SHELF_VERSION}} installed successfully!\\n\\n"
            f"Scripts copied to:\\n{{scripts_dir}}"
        ),
        button=["OK"],
    )


def onMayaDroppedPythonFile(*args):
    _install()
'''


def main():
    print(f"Building installer for {config.SHELF_NAME} v{config.SHELF_VERSION}...")

    bundled = _bundle_scripts()

    installer = INSTALLER_TEMPLATE.format(
        shelf_name=config.SHELF_NAME,
        shelf_name_r=repr(config.SHELF_NAME),
        version=config.SHELF_VERSION,
        version_r=repr(config.SHELF_VERSION),
        build_date=datetime.now().strftime("%Y-%m-%d %H:%M"),
        buttons_r=repr(config.BUTTONS),
        bundled_r=repr(bundled),
    )

    os.makedirs(DIST_DIR, exist_ok=True)
    out_path = os.path.join(DIST_DIR, f"{config.SHELF_NAME}_installer.py")
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(installer)

    print(f"  Output : {out_path}")
    print(f"  Buttons: {len(config.BUTTONS)}")
    print(f"  Scripts: {list(bundled.keys()) or '(none yet)'}")


if __name__ == "__main__":
    main()
