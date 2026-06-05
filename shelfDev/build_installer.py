"""
build_installer.py — run this outside Maya to generate dist/mpInstaller.py.

Usage:
    mayapy build_installer.py

This master build script combines the mpAnim and mpRig shelf configs into a
single drag-and-drop installer for students.

Bump SHELF_VERSION in each shelf's shelf_config.py before each release.

Output: dist/
    mpInstaller.py          <- drag this onto Maya viewport
    studiolibrary_src/      <- Studio Library packages (deployed at install time)
"""

import base64
import importlib.util
import os
import shutil
from datetime import datetime

HERE        = os.path.dirname(os.path.abspath(__file__))
DIST_DIR    = os.path.join(HERE, "dist")

ANIM_DIR      = os.path.join(HERE, "mpAnim")
ANIM_TOOLS    = os.path.join(ANIM_DIR, "tools")
ANIM_ICONS    = os.path.join(ANIM_DIR, "icons")
MULTITOOL_DIR = os.path.normpath(os.path.join(HERE, "..", "animDev", "multiTool"))
STUDIOLIB_SRC = os.path.normpath(
    os.path.join(HERE, "..", "animDev", "studiolibrary-2.20.2", "src")
)

RIG_DIR    = os.path.join(HERE, "mpRig")
RIG_TOOLS  = os.path.join(RIG_DIR, "tools")
RIG_ICONS  = os.path.join(RIG_DIR, "icons")
RIGDEV_DIR = os.path.normpath(os.path.join(HERE, "..", "rigDev"))


def _load_config(shelf_dir):
    spec = importlib.util.spec_from_file_location(
        "shelf_config", os.path.join(shelf_dir, "shelf_config.py")
    )
    cfg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cfg)
    return cfg


anim_cfg = _load_config(ANIM_DIR)
rig_cfg  = _load_config(RIG_DIR)


def _bundle_scripts():
    bundled = {}

    def _read(path, name):
        if not os.path.exists(path):
            print(f"  WARNING: script not found — skipping: {name}")
            return
        with open(path, "r", encoding="utf-8") as fh:
            bundled[name] = base64.b64encode(fh.read().encode("utf-8")).decode("ascii")

    # mpAnim extra scripts + button scripts
    anim_scripts = list(anim_cfg.EXTRA_SCRIPTS)
    for btn in anim_cfg.BUTTONS:
        name = btn.get("script", "")
        if name and name not in anim_scripts:
            anim_scripts.append(name)
    for name in anim_scripts:
        _read(os.path.join(ANIM_TOOLS, name), name)

    # multiTool scripts
    for name in getattr(anim_cfg, "MULTITOOL_SCRIPTS", []):
        _read(os.path.join(MULTITOOL_DIR, name), name)

    # mpRig extra scripts + button scripts
    rig_scripts = list(rig_cfg.EXTRA_SCRIPTS)
    for btn in rig_cfg.BUTTONS:
        name = btn.get("script", "")
        if name and name not in rig_scripts:
            rig_scripts.append(name)
    for name in rig_scripts:
        _read(os.path.join(RIG_TOOLS, name), name)

    # rigDev scripts
    for name in getattr(rig_cfg, "RIGTOOL_SCRIPTS", []):
        _read(os.path.join(RIGDEV_DIR, name), name)

    return bundled


def _bundle_icons():
    bundled = {}

    def _read(icons_dir, name):
        path = os.path.join(icons_dir, name)
        if not os.path.exists(path):
            return  # built-in Maya icon
        with open(path, "rb") as fh:
            bundled[name] = base64.b64encode(fh.read()).decode("ascii")

    for btn in anim_cfg.BUTTONS:
        name = btn.get("icon", "")
        if name:
            _read(ANIM_ICONS, name)

    for btn in rig_cfg.BUTTONS:
        name = btn.get("icon", "")
        if name:
            _read(RIG_ICONS, name)

    return bundled


def _copy_studiolibrary():
    if not os.path.exists(STUDIOLIB_SRC):
        print(f"  WARNING: Studio Library src not found at {STUDIOLIB_SRC} — skipping")
        return False
    dest = os.path.join(DIST_DIR, "studiolibrary_src")
    if os.path.exists(dest):
        shutil.rmtree(dest)
    shutil.copytree(STUDIOLIB_SRC, dest)
    return True


INSTALLER_TEMPLATE = '''\
# mpInstaller.py
# mpAnim  v{anim_version}
# mpRig   v{rig_version}
# Built   : {build_date}
#
# Drag this file into a Maya viewport to install the mpAnim and mpRig shelves.
# The studiolibrary_src/ folder must sit next to this file.
# Running it again will refresh all scripts and buttons.

import base64
import os

_SHELVES = {shelves_r}
_BUNDLED = {bundled_r}
_ICONS   = {icons_r}

_USERSETUP_MARKER = "# multiTool auto-load (mpAnim installer)"
_USERSETUP_LINE   = "import maya.utils; maya.utils.executeDeferred(\'import multiTool; multiTool.show()\')"


def _install():
    import shutil
    import maya.cmds as cmds
    import maya.mel as mel

    # Deploy all scripts
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

    # Deploy Studio Library
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
        print("[mpInstaller] deployed Studio Library")
    else:
        print("[mpInstaller] WARNING: studiolibrary_src not found")

    # Patch userSetup.py
    usersetup = os.path.join(scripts_dir, "userSetup.py")
    existing = ""
    if os.path.exists(usersetup):
        with open(usersetup, "r", encoding="utf-8") as fh:
            existing = fh.read()
    _OLD_MARKERS = [
        "# animMultiTool auto-load (mpAnim installer)",
        "import animMultiTool; animMultiTool.show()",
        "import maya.utils; maya.utils.executeDeferred(\'import animMultiTool; animMultiTool.show()\')",
    ]
    for old in _OLD_MARKERS:
        if old in existing:
            existing = existing.replace(old, "")
    existing = "\\n".join(line for line in existing.splitlines() if line.strip())
    if _USERSETUP_MARKER not in existing:
        with open(usersetup, "a", encoding="utf-8") as fh:
            fh.write("\\n" + _USERSETUP_MARKER + "\\n" + _USERSETUP_LINE + "\\n")
        print("[mpInstaller] patched userSetup.py")
    else:
        print("[mpInstaller] userSetup.py already patched")

    # Build / refresh shelves
    shelf_top = mel.eval("$tmpVar=$gShelfTopLevel")
    existing_tabs = cmds.shelfTabLayout(shelf_top, query=True, childArray=True) or []

    for shelf_name, buttons in _SHELVES.items():
        if shelf_name not in existing_tabs:
            mel.eval(f\'addNewShelfTab "{{shelf_name}}"\')\n            print(f"[mpInstaller] created shelf tab: {{shelf_name}}")

        shelf = f"{{shelf_top}}|{{shelf_name}}"
        for old_btn in cmds.shelfLayout(shelf, query=True, childArray=True) or []:
            cmds.deleteUI(old_btn)

        for btn in buttons:
            try:
                cmds.shelfButton(
                    parent=shelf,
                    label=btn["label"],
                    annotation=btn["tooltip"],
                    image1=btn.get("icon", "commandButton.png"),
                    command=btn["command"],
                    sourceType="python",
                )
                print(f"[mpInstaller] added button: {{shelf_name}} / {{btn[\'label\']}}")
            except Exception as e:
                print(f"[mpInstaller] ERROR adding {{btn[\'label\']}}: {{e}}")

    mel.eval("saveAllShelves $gShelfTopLevel")
    print("[mpInstaller] done")

    cmds.evalDeferred("import multiTool; multiTool.show()")
    cmds.evalDeferred("import mpAnimConfig; mpAnimConfig.get_save_path()")

    cmds.inViewMessage(
        amg="<b>mpAnim + mpRig</b> installed successfully.",
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
    print(f"Building combined installer (mpAnim v{anim_cfg.SHELF_VERSION} + mpRig v{rig_cfg.SHELF_VERSION})...")

    bundled = _bundle_scripts()
    icons   = _bundle_icons()

    shelves = {
        anim_cfg.SHELF_NAME: anim_cfg.BUTTONS,
        rig_cfg.SHELF_NAME:  rig_cfg.BUTTONS,
    }

    os.makedirs(DIST_DIR, exist_ok=True)
    has_studiolib = _copy_studiolibrary()

    installer = INSTALLER_TEMPLATE.format(
        anim_version=anim_cfg.SHELF_VERSION,
        rig_version=rig_cfg.SHELF_VERSION,
        build_date=datetime.now().strftime("%Y-%m-%d %H:%M"),
        shelves_r=repr(shelves),
        bundled_r=repr(bundled),
        icons_r=repr(icons),
    )

    out_path = os.path.join(DIST_DIR, "mpInstaller.py")
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(installer)

    print(f"  Output    : {out_path}")
    print(f"  Shelves   : {list(shelves.keys())}")
    print(f"  Scripts   : {list(bundled.keys()) or '(none)'}")
    print(f"  Icons     : {list(icons.keys()) or '(none)'}")
    print(f"  StudioLib : {'copied to dist/studiolibrary_src/' if has_studiolib else 'NOT FOUND'}")


if __name__ == "__main__":
    main()
