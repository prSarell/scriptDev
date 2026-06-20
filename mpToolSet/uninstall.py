"""
mpToolSet Uninstaller
=====================
Drag and drop this file onto the Maya viewport to remove all files
and shelves that were installed by install.py.

If versioned backups exist the student is offered a choice:

  - Restore to original  (v000 — before any mpToolSet install)
  - Restore to previous  (the most recent backup before current)
  - Just remove           (delete mpToolSet files, no restore)
"""

import os
import shutil
import maya.cmds as cmds
import maya.mel as mel


_MANIFEST_NAME = "mpToolSet_manifest.txt"
_BACKUPS_DIR = "mpToolSet_backups"


# -- paths -----------------------------------------------------------------

def _app_plugins_dir():
    return os.path.join(
        os.environ.get("APPDATA", ""),
        "Autodesk", "ApplicationPlugins"
    ).replace("\\", "/")


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


# -- backup discovery ------------------------------------------------------

def _available_versions():
    """Return sorted list of (version_int, dir_path) tuples."""
    root = _backups_root()
    if not os.path.isdir(root):
        return []
    versions = []
    for d in os.listdir(root):
        if d.startswith("v") and d[1:].isdigit():
            versions.append((int(d[1:]), os.path.join(root, d).replace("\\", "/")))
    versions.sort()
    return versions


# -- remove installed files -------------------------------------------------

def _clean_pyc(path):
    parent = os.path.dirname(path)
    base = os.path.splitext(os.path.basename(path))[0]
    cache_dir = os.path.join(parent, "__pycache__")
    if os.path.isdir(cache_dir):
        for cached in os.listdir(cache_dir):
            if cached.startswith(base + ".") and cached.endswith(".pyc"):
                try:
                    os.remove(os.path.join(cache_dir, cached))
                except Exception:
                    pass


def _remove_installed(lines):
    """Delete all files, dirs, and shelves listed in the manifest.
    Returns (files_removed, dirs_removed, shelves_removed, errors)."""
    files_removed = 0
    dirs_removed = 0
    shelves_removed = []
    errors = []

    top_shelf = mel.eval("$tmpVar=$gShelfTopLevel")

    for line in lines:
        if not line.strip():
            continue

        if line.startswith("shelf:"):
            name = line[len("shelf:"):]
            if cmds.shelfLayout(name, exists=True):
                cmds.deleteUI(name, layout=True)
                shelves_removed.append(name)
            shelf_mel = os.path.join(
                _maya_shelves_dir(), "shelf_{}.mel".format(name)
            ).replace("\\", "/")
            if os.path.isfile(shelf_mel):
                try:
                    os.remove(shelf_mel)
                except Exception as e:
                    errors.append("{}: {}".format(shelf_mel, e))

        elif line.startswith("dir:"):
            path = line[len("dir:"):]
            if os.path.isdir(path):
                try:
                    shutil.rmtree(path)
                    dirs_removed += 1
                except Exception as e:
                    errors.append("{}: {}".format(path, e))

        elif line.startswith("file:"):
            path = line[len("file:"):]
            if os.path.isfile(path):
                try:
                    os.remove(path)
                    files_removed += 1
                except Exception as e:
                    errors.append("{}: {}".format(path, e))
            if path.endswith(".py"):
                _clean_pyc(path)

    if shelves_removed:
        cmds.saveAllShelves(top_shelf)

    return files_removed, dirs_removed, shelves_removed, errors


# -- restore from backup ---------------------------------------------------

def _restore_from(backup_dir):
    """Copy everything in a backup snapshot back to the Maya folders.
    Returns (files_restored, dirs_restored)."""
    files_restored = 0
    dirs_restored = 0

    scripts_dst = _maya_scripts_dir()
    icons_dst = _maya_icons_dir()
    shelves_dst = _maya_shelves_dir()

    mapping = {
        "scripts": scripts_dst,
        "icons": icons_dst,
        "shelves": shelves_dst,
    }
    for category, dst in mapping.items():
        src = os.path.join(backup_dir, category)
        if not os.path.isdir(src):
            continue
        for fname in os.listdir(src):
            src_path = os.path.join(src, fname)
            dst_path = os.path.join(dst, fname)
            if os.path.isfile(src_path):
                shutil.copy2(src_path, dst_path)
                files_restored += 1

    dirs_src = os.path.join(backup_dir, "dirs")
    if os.path.isdir(dirs_src):
        for dname in os.listdir(dirs_src):
            src_path = os.path.join(dirs_src, dname)
            if os.path.isdir(src_path):
                dst_path = os.path.join(scripts_dst, dname)
                if os.path.exists(dst_path):
                    shutil.rmtree(dst_path)
                shutil.copytree(src_path, dst_path)
                dirs_restored += 1

    app_plugins_src = os.path.join(backup_dir, "app_plugins")
    if os.path.isdir(app_plugins_src):
        plugins_dst = _app_plugins_dir()
        for dname in os.listdir(app_plugins_src):
            src_path = os.path.join(app_plugins_src, dname)
            if os.path.isdir(src_path):
                dst_path = os.path.join(plugins_dst, dname)
                if os.path.exists(dst_path):
                    shutil.rmtree(dst_path)
                shutil.copytree(src_path, dst_path)
                dirs_restored += 1

    # Rebuild any restored shelves so they appear in the current session
    if os.path.isdir(os.path.join(backup_dir, "shelves")):
        top_shelf = mel.eval("$tmpVar=$gShelfTopLevel")
        for fname in os.listdir(os.path.join(backup_dir, "shelves")):
            if fname.startswith("shelf_") and fname.endswith(".mel"):
                shelf_name = fname[len("shelf_"):-len(".mel")]
                if cmds.shelfLayout(shelf_name, exists=True):
                    cmds.deleteUI(shelf_name, layout=True)
                mel_path = os.path.join(shelves_dst, fname).replace("\\", "/")
                try:
                    mel.eval('loadNewShelf "{}"'.format(mel_path))
                except Exception:
                    cmds.warning(
                        "mpToolSet: shelf file restored but could not "
                        "reload {} — restart Maya to see it.".format(shelf_name)
                    )

    return files_restored, dirs_restored


# -- main -------------------------------------------------------------------

def _uninstall():
    manifest = _manifest_path()
    if not os.path.isfile(manifest):
        cmds.confirmDialog(
            title="mpToolSet Uninstaller",
            message="Nothing to uninstall — no manifest found.\n\n"
                    "mpToolSet does not appear to be installed.",
            button=["OK"],
        )
        return

    with open(manifest, "r") as f:
        lines = f.read().splitlines()

    versions = _available_versions()

    # -- ask the student what to do ----------------------------------------

    restore_version = None

    if len(versions) >= 2:
        latest = versions[-1]
        original = versions[0]
        choice = cmds.confirmDialog(
            title="mpToolSet Uninstaller",
            message=(
                "How would you like to uninstall?\n\n"
                "Restore to original:\n"
                "  Roll back to your setup before any mpToolSet install\n"
                "  (backup v{:03d})\n\n"
                "Restore to previous:\n"
                "  Roll back to the previous mpToolSet version\n"
                "  (backup v{:03d})\n\n"
                "Just remove:\n"
                "  Delete mpToolSet files without restoring anything"
            ).format(original[0], latest[0]),
            button=["Restore to original", "Restore to previous", "Just remove", "Cancel"],
            defaultButton="Restore to original",
            cancelButton="Cancel",
            dismissString="Cancel",
        )
        if choice == "Cancel":
            return
        if choice == "Restore to original":
            restore_version = original
        elif choice == "Restore to previous":
            restore_version = latest

    elif len(versions) == 1:
        choice = cmds.confirmDialog(
            title="mpToolSet Uninstaller",
            message=(
                "How would you like to uninstall?\n\n"
                "Restore to original:\n"
                "  Roll back to your setup before mpToolSet was installed\n"
                "  (backup v{:03d})\n\n"
                "Just remove:\n"
                "  Delete mpToolSet files without restoring anything"
            ).format(versions[0][0]),
            button=["Restore to original", "Just remove", "Cancel"],
            defaultButton="Restore to original",
            cancelButton="Cancel",
            dismissString="Cancel",
        )
        if choice == "Cancel":
            return
        if choice == "Restore to original":
            restore_version = versions[0]

    else:
        choice = cmds.confirmDialog(
            title="mpToolSet Uninstaller",
            message="This will remove all mpToolSet scripts, icons, and shelves.\n\n"
                    "No backups were found — nothing to restore.\n\n"
                    "Continue?",
            button=["Remove", "Cancel"],
            defaultButton="Cancel",
            cancelButton="Cancel",
            dismissString="Cancel",
        )
        if choice == "Cancel":
            return

    # -- do the work -------------------------------------------------------

    files_removed, dirs_removed, shelves_removed, errors = _remove_installed(lines)

    files_restored = 0
    dirs_restored = 0
    if restore_version is not None:
        files_restored, dirs_restored = _restore_from(restore_version[1])

    os.remove(manifest)

    # Only clean up backups if we restored — if the student chose
    # "Just remove", keep backups so originals can still be recovered
    # manually from ~/maya/prefs/mpToolSet_backups/v000/.
    if restore_version is not None:
        backups_root = _backups_root()
        if os.path.isdir(backups_root):
            shutil.rmtree(backups_root)

    # -- report ------------------------------------------------------------

    summary = (
        "mpToolSet uninstalled.\n\n"
        "  Files removed:    {}\n"
        "  Folders removed:  {}\n"
        "  Shelves removed:  {}"
    ).format(
        files_removed,
        dirs_removed,
        ", ".join(shelves_removed) if shelves_removed else "none",
    )
    if files_restored or dirs_restored:
        summary += (
            "\n\n  Restored from backup v{:03d}:\n"
            "    {} file(s), {} folder(s)"
        ).format(restore_version[0], files_restored, dirs_restored)
    if errors:
        summary += "\n\n  Errors:\n    " + "\n    ".join(errors)

    print(summary)
    cmds.confirmDialog(
        title="mpToolSet Uninstaller",
        message=summary,
        button=["OK"],
    )


def onMayaDroppedPythonFile(obj):
    """Called by Maya when this file is dragged onto the viewport."""
    _uninstall()
