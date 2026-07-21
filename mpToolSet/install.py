"""
mpToolSet Installer
===================
Drag and drop this file onto the Maya viewport to install both the
mpRig and mpAnim shelves with all their tools.

Before overwriting anything the installer snapshots every file it is
about to replace into a versioned backup folder:

    ~/maya/prefs/mpToolSet_backups/v000/   (pre-first-install)
    ~/maya/prefs/mpToolSet_backups/v001/   (pre-second-install)
    ...

The uninstaller reads these snapshots and offers the student a choice
of which version to roll back to.
"""

import os
import re
import shutil
import maya.cmds as cmds
import maya.mel as mel


_MANIFEST_NAME = "mpToolSet_manifest.txt"
_BACKUPS_DIR = "mpToolSet_backups"
_US_START = "# -- mpToolSet BEGIN --"
_US_END   = "# -- mpToolSet END --"


# -- paths -----------------------------------------------------------------

def _maya_scripts_dir():
    return os.path.join(
        cmds.internalVar(userAppDir=True), "scripts"
    ).replace("\\", "/")


def _maya_icons_dir():
    return os.path.join(
        cmds.internalVar(userPrefDir=True), "icons"
    ).replace("\\", "/")


def _maya_shelves_dir():
    return os.path.join(
        cmds.internalVar(userPrefDir=True), "shelves"
    ).replace("\\", "/")


def _manifest_path():
    return os.path.join(
        cmds.internalVar(userPrefDir=True), _MANIFEST_NAME
    ).replace("\\", "/")


def _backups_root():
    return os.path.join(
        cmds.internalVar(userPrefDir=True), _BACKUPS_DIR
    ).replace("\\", "/")


# -- versioned backups -----------------------------------------------------

def _next_backup_version():
    root = _backups_root()
    if not os.path.isdir(root):
        return 0
    versions = [
        int(d[1:]) for d in os.listdir(root)
        if d.startswith("v") and d[1:].isdigit()
    ]
    return (max(versions) + 1) if versions else 0


def _backup_file(src_path, backup_dir, category):
    """If src_path exists, copy it into backup_dir/category/.
    Skips if a backup already exists in this version — preserves the
    first snapshot (the student's actual pre-install state) when the
    same filename is deployed by both shelves."""
    if not os.path.isfile(src_path):
        return
    dest_dir = os.path.join(backup_dir, category)
    dest = os.path.join(dest_dir, os.path.basename(src_path))
    if os.path.isfile(dest):
        return
    os.makedirs(dest_dir, exist_ok=True)
    shutil.copy2(src_path, dest)


# -- copy helpers -----------------------------------------------------------

def _copy_flat(src_dir, dst_dir, backup_dir, category, ext=None):
    if not os.path.isdir(src_dir):
        return []
    copied = []
    for fname in os.listdir(src_dir):
        if ext and not fname.lower().endswith(ext):
            continue
        src = os.path.join(src_dir, fname)
        if os.path.isfile(src):
            dst = os.path.join(dst_dir, fname).replace("\\", "/")
            _backup_file(dst, backup_dir, category)
            shutil.copy2(src, dst)
            copied.append(dst)
    return copied


# -- shelf ------------------------------------------------------------------

def _build_shelf(shelf_config_path, backup_dir):
    config_ns = {}
    with open(shelf_config_path, "r") as f:
        exec(f.read(), config_ns)

    shelf_name = config_ns["SHELF_NAME"]
    buttons = config_ns["BUTTONS"]

    shelf_mel = os.path.join(
        _maya_shelves_dir(), "shelf_{}.mel".format(shelf_name)
    ).replace("\\", "/")
    _backup_file(shelf_mel, backup_dir, "shelves")

    if cmds.shelfLayout(shelf_name, exists=True):
        cmds.deleteUI(shelf_name, layout=True)

    top_shelf = mel.eval("$tmpVar=$gShelfTopLevel")
    cmds.shelfLayout(shelf_name, parent=top_shelf)

    icons_dir = _maya_icons_dir()

    for btn in buttons:
        icon_path = btn["icon"]
        full_icon = os.path.join(icons_dir, icon_path)
        if not os.path.isfile(full_icon):
            full_icon = icon_path

        cmds.shelfButton(
            parent=shelf_name,
            label=btn["label"],
            annotation=btn.get("tooltip", ""),
            image1=full_icon,
            command=btn["command"],
            sourceType="python",
        )

    cmds.saveAllShelves(top_shelf)
    return shelf_name, len(buttons)


# -- manifest ---------------------------------------------------------------

def _write_manifest(files, dirs, shelves, usersetups=None):
    path = _manifest_path()
    seen = set()
    with open(path, "w") as f:
        for shelf_name in shelves:
            f.write("shelf:{}\n".format(shelf_name))
        for d in dirs:
            f.write("dir:{}\n".format(d))
        for us in (usersetups or []):
            f.write("usersetup:{}\n".format(us))
        for fp in files:
            if fp not in seen:
                f.write("file:{}\n".format(fp))
                seen.add(fp)


def _patch_usersetup(scripts_dir, backup_dir, extra_syspaths=None):
    """Append (or replace) the mpToolSet startup hook in userSetup.py."""
    path = os.path.join(scripts_dir, "userSetup.py").replace("\\", "/")
    _backup_file(path, backup_dir, "scripts")

    content = ""
    if os.path.isfile(path):
        with open(path, "r") as f:
            content = f.read()

    content = re.sub(
        r"\n?" + re.escape(_US_START) + r".*?" + re.escape(_US_END) + r"\n?",
        "", content, flags=re.DOTALL,
    )

    syspath_lines = ""
    for p in (extra_syspaths or []):
        syspath_lines += (
            "import sys as _sys\n"
            "if {p!r} not in _sys.path:\n"
            "    _sys.path.insert(0, {p!r})\n"
        ).format(p=p)

    block = (
        "\n{start}\n"
        "{syspaths}"
        "try:\n"
        "    import shortCuts; shortCuts.init_hotkeys()\n"
        "except Exception:\n"
        "    pass\n"
        "{end}\n"
    ).format(start=_US_START, end=_US_END, syspaths=syspath_lines)

    with open(path, "w") as f:
        f.write(content.rstrip("\n") + block)

    return path


# -- install ----------------------------------------------------------------

def _install(root):
    root = root.replace("\\", "/")
    scripts_dst = _maya_scripts_dir()
    icons_dst = _maya_icons_dir()

    os.makedirs(scripts_dst, exist_ok=True)
    os.makedirs(icons_dst, exist_ok=True)

    version = _next_backup_version()
    backup_dir = os.path.join(_backups_root(), "v{:03d}".format(version))
    os.makedirs(backup_dir, exist_ok=True)

    all_files = []
    all_dirs = []
    shelves_built = []
    shelf_names = []

    for shelf_dir_name in ("mpRig", "mpAnim"):
        shelf_path = os.path.join(root, shelf_dir_name)
        if not os.path.isdir(shelf_path):
            cmds.warning(
                "mpToolSet: skipping {} — folder not found.".format(shelf_dir_name)
            )
            continue

        copied = _copy_flat(
            os.path.join(shelf_path, "scripts"), scripts_dst,
            backup_dir, "scripts", ext=".py",
        )
        all_files.extend(copied)

        staff_src = os.path.join(shelf_path, "scripts", "staff_shortcuts")
        if os.path.isdir(staff_src):
            staff_dst = os.path.join(scripts_dst, "staff_shortcuts")
            os.makedirs(staff_dst, exist_ok=True)
            copied = _copy_flat(staff_src, staff_dst, backup_dir, "staff_shortcuts", ext=".json")
            all_files.extend(copied)

        copied = _copy_flat(
            os.path.join(shelf_path, "icons"), icons_dst,
            backup_dir, "icons", ext=".png",
        )
        all_files.extend(copied)

        config_file = os.path.join(shelf_path, "shelf_config.py")
        if os.path.isfile(config_file):
            name, btn_count = _build_shelf(config_file, backup_dir)
            shelves_built.append("{} ({} buttons)".format(name, btn_count))
            shelf_names.append(name)

    usersetup_path = _patch_usersetup(scripts_dst, backup_dir)
    _write_manifest(all_files, all_dirs, shelf_names, usersetups=[usersetup_path])

    backup_label = "v{:03d}".format(version)
    if version == 0:
        backup_label += " (original pre-install state)"

    summary = (
        "mpToolSet installed successfully!\n\n"
        "  Scripts: {} files -> {}\n"
        "  Icons:   {} files -> {}\n"
        "  Shelves: {}\n"
        "  Startup hook: userSetup.py updated\n"
        "  Backup saved: {}\n\n"
        "  ngSkinTools2 installs separately — drag ngSkinTools2/install.py\n"
        "  (in this same folder) onto the viewport if you need it.\n\n"
        "  Studio Library installs separately too — drag\n"
        "  studioLibrary/install.py (in this same folder) onto the\n"
        "  viewport if you need it.\n\n"
        "To uninstall, drag uninstall.py onto the viewport."
    ).format(
        sum(1 for f in all_files if f.endswith(".py")), scripts_dst,
        sum(1 for f in all_files if f.endswith(".png")), icons_dst,
        ", ".join(shelves_built) if shelves_built else "none",
        backup_label,
    )
    print(summary)
    cmds.confirmDialog(
        title="mpToolSet Installer",
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
        msg = "mpToolSet install FAILED:\n\n{}\n\n{}".format(e, traceback.format_exc())
        print(msg)
        cmds.confirmDialog(
            title="mpToolSet Installer — Error",
            message="Install failed! See Script Editor for details.\n\n{}".format(e),
            button=["OK"],
        )
