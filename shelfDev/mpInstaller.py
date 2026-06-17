# mpInstaller.py
#
# Drag this file into a Maya viewport to install the mpAnim and mpRig shelves.
# Reads scripts and icons directly from the repo — no build step needed.
# Run again at any time to refresh all scripts and buttons.

import importlib.util
import os
import shutil


HERE              = os.path.dirname(os.path.abspath(__file__))
ANIM_DIR          = os.path.join(HERE, "mpAnim")
ANIM_TOOLS        = os.path.join(ANIM_DIR, "tools")
ANIM_ICONS        = os.path.join(ANIM_DIR, "icons")
RIG_DIR           = os.path.join(HERE, "mpRig")
RIG_TOOLS         = os.path.join(RIG_DIR, "tools")
RIG_ICONS         = os.path.join(RIG_DIR, "icons")
ANIMDEV_DIR       = os.path.normpath(os.path.join(HERE, "..", "animDev"))
MULTITOOL_DIR     = os.path.normpath(os.path.join(HERE, "..", "animDev", "multiTool"))
JIFFYPOMO_DIR     = os.path.normpath(os.path.join(HERE, "..", "timeManagementDev", "jiffyPomoDev"))
JIFFYSCHEDULE_DIR = os.path.normpath(os.path.join(HERE, "..", "timeManagementDev", "jiffyScheduleDev"))
METAHUMAN_DIR     = os.path.normpath(os.path.join(HERE, "..", "metahuman_facial_transfer"))
RIGDEV_DIR        = os.path.normpath(os.path.join(HERE, "..", "rigDev"))
SIMDEV_DIR        = os.path.normpath(os.path.join(HERE, "..", "simDev"))
STUDIOLIB_SRC     = os.path.normpath(
    os.path.join(HERE, "..", "animDev", "studiolibrary-2.20.2", "src")
)

_USERSETUP_MARKER = "# multiTool auto-load (mpAnim installer)"
_USERSETUP_LINE   = "import maya.utils; maya.utils.executeDeferred('import multiTool; multiTool.show()')"
_SHORTCUTS_MARKER = "# shortCuts auto-load (mpAnim installer)"
_SHORTCUTS_LINE   = "import maya.utils; maya.utils.executeDeferred('import shortCuts; shortCuts.init_hotkeys()')"


def _load_config(shelf_dir):
    spec = importlib.util.spec_from_file_location(
        "shelf_config_" + os.path.basename(shelf_dir),
        os.path.join(shelf_dir, "shelf_config.py")
    )
    cfg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cfg)
    return cfg


def _copy(src, dest_dir, dest_name=None):
    if not os.path.exists(src):
        print("[mpInstaller] WARNING: not found — {}".format(src))
        return
    shutil.copy2(src, os.path.join(dest_dir, dest_name or os.path.basename(src)))


def _install():
    import maya.cmds as cmds
    import maya.mel as mel

    scripts_dir = os.path.join(cmds.internalVar(userAppDir=True), "scripts")
    icons_dir   = cmds.internalVar(userBitmapsDir=True)
    os.makedirs(scripts_dir, exist_ok=True)
    os.makedirs(icons_dir, exist_ok=True)

    anim_cfg = _load_config(ANIM_DIR)
    rig_cfg  = _load_config(RIG_DIR)

    # --- Scripts ---

    # mpAnim tools/ (EXTRA_SCRIPTS + button scripts)
    anim_scripts = list(anim_cfg.EXTRA_SCRIPTS)
    for btn in anim_cfg.BUTTONS:
        name = btn.get("script", "")
        if name and name not in anim_scripts:
            anim_scripts.append(name)
    for name in anim_scripts:
        _copy(os.path.join(ANIM_TOOLS, name), scripts_dir)

    for name in getattr(anim_cfg, "ANIMDEV_SCRIPTS", []):
        _copy(os.path.join(ANIMDEV_DIR, name), scripts_dir)

    for name in getattr(anim_cfg, "MULTITOOL_SCRIPTS", []):
        _copy(os.path.join(MULTITOOL_DIR, name), scripts_dir)

    for name in getattr(anim_cfg, "JIFFYPOMO_SCRIPTS", []):
        _copy(os.path.join(JIFFYPOMO_DIR, name), scripts_dir)

    for name in getattr(anim_cfg, "JIFFYSCHEDULE_SCRIPTS", []):
        _copy(os.path.join(JIFFYSCHEDULE_DIR, name), scripts_dir)

    for name in getattr(anim_cfg, "METAHUMAN_SCRIPTS", []):
        _copy(os.path.join(METAHUMAN_DIR, name), scripts_dir)

    for name in getattr(anim_cfg, "SIMTOOL_SCRIPTS", []):
        _copy(os.path.join(SIMDEV_DIR, name), scripts_dir, os.path.basename(name))

    # mpRig tools/ (EXTRA_SCRIPTS + button scripts)
    rig_scripts = list(rig_cfg.EXTRA_SCRIPTS)
    for btn in rig_cfg.BUTTONS:
        name = btn.get("script", "")
        if name and name not in rig_scripts:
            rig_scripts.append(name)
    for name in rig_scripts:
        _copy(os.path.join(RIG_TOOLS, name), scripts_dir)

    for name in getattr(rig_cfg, "RIGTOOL_SCRIPTS", []):
        _copy(os.path.join(RIGDEV_DIR, name), scripts_dir, os.path.basename(name))

    # --- Icons ---
    # Generate any icons that have a gen_icon*.py script alongside them.
    for src_icons_dir in (ANIM_ICONS, RIG_ICONS):
        if not os.path.isdir(src_icons_dir):
            continue
        for fname in sorted(os.listdir(src_icons_dir)):
            if fname.startswith("gen_icon") and fname.endswith(".py"):
                script_path = os.path.join(src_icons_dir, fname)
                try:
                    with open(script_path, "r", encoding="utf-8") as fh:
                        code = fh.read()
                    exec(compile(code, script_path, "exec"), {"__file__": script_path})
                except Exception as e:
                    print("[mpInstaller] WARNING: icon gen failed for {}: {}".format(fname, e))

    for btn in anim_cfg.BUTTONS:
        name = btn.get("icon", "")
        if name:
            _copy(os.path.join(ANIM_ICONS, name), icons_dir)

    for btn in rig_cfg.BUTTONS:
        name = btn.get("icon", "")
        if name:
            _copy(os.path.join(RIG_ICONS, name), icons_dir)

    # --- Studio Library ---
    if os.path.exists(STUDIOLIB_SRC):
        for pkg_name in os.listdir(STUDIOLIB_SRC):
            src = os.path.join(STUDIOLIB_SRC, pkg_name)
            if os.path.isdir(src):
                dst = os.path.join(scripts_dir, pkg_name)
                if os.path.exists(dst):
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
        print("[mpInstaller] deployed Studio Library")
    else:
        print("[mpInstaller] WARNING: Studio Library not found — StudioLib button may not work")

    # --- userSetup.py ---
    usersetup = os.path.join(scripts_dir, "userSetup.py")
    existing = ""
    if os.path.exists(usersetup):
        with open(usersetup, "r", encoding="utf-8") as fh:
            existing = fh.read()
    for old in [
        "# animMultiTool auto-load (mpAnim installer)",
        "import animMultiTool; animMultiTool.show()",
        "import maya.utils; maya.utils.executeDeferred('import animMultiTool; animMultiTool.show()')",
    ]:
        existing = existing.replace(old, "")
    existing = "\n".join(line for line in existing.splitlines() if line.strip())
    if _USERSETUP_MARKER not in existing:
        with open(usersetup, "a", encoding="utf-8") as fh:
            fh.write("\n" + _USERSETUP_MARKER + "\n" + _USERSETUP_LINE + "\n")
        print("[mpInstaller] patched userSetup.py")
    if _SHORTCUTS_MARKER not in existing:
        with open(usersetup, "a", encoding="utf-8") as fh:
            fh.write("\n" + _SHORTCUTS_MARKER + "\n" + _SHORTCUTS_LINE + "\n")
        print("[mpInstaller] patched userSetup.py (shortCuts)")

    # --- Shelves ---
    shelf_top    = mel.eval("$tmpVar=$gShelfTopLevel")
    existing_tabs = cmds.shelfTabLayout(shelf_top, query=True, childArray=True) or []

    for cfg in (anim_cfg, rig_cfg):
        shelf_name = cfg.SHELF_NAME
        if shelf_name not in existing_tabs:
            mel.eval('addNewShelfTab "{}"'.format(shelf_name))

        shelf = "{}|{}".format(shelf_top, shelf_name)
        for old_btn in cmds.shelfLayout(shelf, query=True, childArray=True) or []:
            cmds.deleteUI(old_btn)

        for btn in cfg.BUTTONS:
            try:
                cmds.shelfButton(
                    parent=shelf,
                    label=btn["label"],
                    annotation=btn["tooltip"],
                    image1=btn.get("icon", "commandButton.png"),
                    command=btn["command"],
                    sourceType="python",
                )
            except Exception as e:
                print("[mpInstaller] ERROR adding {}: {}".format(btn["label"], e))

    mel.eval("saveAllShelves $gShelfTopLevel")

    cmds.evalDeferred("import multiTool; multiTool.show()")
    cmds.evalDeferred("import mpAnimConfig; mpAnimConfig.get_save_path()")
    cmds.evalDeferred("import shortCuts; shortCuts.init_hotkeys()")

    cmds.inViewMessage(
        amg="<b>mpAnim v{} + mpRig v{}</b> installed.".format(
            anim_cfg.SHELF_VERSION, rig_cfg.SHELF_VERSION
        ),
        pos="midCenter", fade=True,
    )
    print("[mpInstaller] done — mpAnim v{} + mpRig v{}".format(
        anim_cfg.SHELF_VERSION, rig_cfg.SHELF_VERSION
    ))


def onMayaDroppedPythonFile(*args):
    _install()
