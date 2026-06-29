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
import subprocess
import shutil
import sys
import maya.cmds as cmds
import maya.mel as mel


_MANIFEST_NAME = "mpToolSet_manifest.txt"
_BACKUPS_DIR = "mpToolSet_backups"


# -- paths -----------------------------------------------------------------

def _app_plugins_dir():
    import sys
    if sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("APPDATA", "")
    return os.path.join(base, "Autodesk", "ApplicationPlugins").replace("\\", "/")


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


def _backup_directory(src_path, backup_dir, category):
    """If src_path exists, copy the whole tree into backup_dir/category/name."""
    if not os.path.isdir(src_path):
        return
    dest_dir = os.path.join(backup_dir, category)
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, os.path.basename(src_path.rstrip("/")))
    if os.path.exists(dest):
        shutil.rmtree(dest)
    shutil.copytree(src_path, dest)


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


def _copy_tree(src_dir, dst_dir, backup_dir, category):
    _backup_directory(dst_dir, backup_dir, category)
    if os.path.exists(dst_dir):
        shutil.rmtree(dst_dir)
    shutil.copytree(src_dir, dst_dir)
    return dst_dir.replace("\\", "/")


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

def _write_manifest(files, dirs, shelves):
    path = _manifest_path()
    seen = set()
    with open(path, "w") as f:
        for shelf_name in shelves:
            f.write("shelf:{}\n".format(shelf_name))
        for d in dirs:
            f.write("dir:{}\n".format(d))
        for fp in files:
            if fp not in seen:
                f.write("file:{}\n".format(fp))
                seen.add(fp)


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

        copied = _copy_flat(
            os.path.join(shelf_path, "icons"), icons_dst,
            backup_dir, "icons", ext=".png",
        )
        all_files.extend(copied)

        studio_src = os.path.join(shelf_path, "studiolibrary")
        if os.path.isdir(studio_src):
            for name in os.listdir(studio_src):
                src = os.path.join(studio_src, name)
                if os.path.isdir(src):
                    dst = os.path.join(scripts_dst, name)
                    _backup_directory(dst, backup_dir, "dirs")
                    if os.path.exists(dst):
                        shutil.rmtree(dst)
                    shutil.copytree(src, dst)
                    all_dirs.append(dst.replace("\\", "/"))

        ngskin_src = os.path.join(shelf_path, "ngskintools2")
        if os.path.isdir(ngskin_src):
            plugins_dst = _app_plugins_dir()
            os.makedirs(plugins_dst, exist_ok=True)
            ngskin_dst = os.path.join(plugins_dst, "ngskintools2")
            _backup_directory(ngskin_dst, backup_dir, "app_plugins")
            if os.path.exists(ngskin_dst):
                shutil.rmtree(ngskin_dst)
            shutil.copytree(ngskin_src, ngskin_dst)
            if sys.platform == "darwin":
                subprocess.run(
                    ["xattr", "-dr", "com.apple.quarantine", ngskin_dst],
                    check=False,
                )
            all_dirs.append(ngskin_dst.replace("\\", "/"))

        config_file = os.path.join(shelf_path, "shelf_config.py")
        if os.path.isfile(config_file):
            name, btn_count = _build_shelf(config_file, backup_dir)
            shelves_built.append("{} ({} buttons)".format(name, btn_count))
            shelf_names.append(name)

    _write_manifest(all_files, all_dirs, shelf_names)

    backup_label = "v{:03d}".format(version)
    if version == 0:
        backup_label += " (original pre-install state)"

    ngskin_installed = any("ngskintools2" in d for d in all_dirs)

    restart_note = (
        "\n  ** Restart Maya for ngSkinTools2 to become available. **\n"
        if ngskin_installed else ""
    )

    summary = (
        "mpToolSet installed successfully!\n\n"
        "  Scripts: {} files -> {}\n"
        "  Icons:   {} files -> {}\n"
        "  Shelves: {}\n"
        "  ngSkinTools2: {}\n"
        "{}\n"
        "  Backup saved: {}\n\n"
        "To uninstall, drag uninstall.py onto the viewport."
    ).format(
        sum(1 for f in all_files if f.endswith(".py")), scripts_dst,
        sum(1 for f in all_files if f.endswith(".png")), icons_dst,
        ", ".join(shelves_built) if shelves_built else "none",
        "installed" if ngskin_installed else "not found",
        restart_note,
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
    _install(root)
