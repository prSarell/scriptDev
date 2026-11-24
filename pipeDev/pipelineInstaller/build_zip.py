"""
Build the mpPipe staff-testing zip.

    mayapy pipeDev/pipelineInstaller/build_zip.py

Collects the pipeline tools straight from their dev folders (they're
dev-direct tools, so there is no staged copy to drift), plus the mpPipe
shelf config and icons, into:

    pipeDev/pipelineInstaller/dist/mpPipe.zip      (dist/ and *.zip are gitignored)
    ~/Dropbox/mpPipe/mpPipe.zip                    (copy, for other machines)

Zip layout (unzip anywhere, drag install.py onto the Maya viewport):

    mpPipe/install.py, uninstall.py, shelf_config.py, version.txt
    mpPipe/scripts/*.py
    mpPipe/icons/*.png
    mpPipe/gaffer/install.py, uninstall.py, gaffer-<version>-windows.zip

gaffer/ is Gaffer itself (user 2026-11-24: "part of the pipeline bundle ...
like studio library ... not handled by the drag and drop"): the Gaffer
release zip as downloaded (BSD licence, so it can be passed on), never
committed to git, with its own install/uninstall that students drag in
separately. Found in MPPIPE_GAFFER_ZIP, else the newest
gaffer-*-windows.zip in Documents\\maya or Downloads. --no-gaffer leaves it
out (a quick build: Gaffer adds ~470 MB). The Arnold SDK is never bundled
(Autodesk's licence).

Not for students: never copy this into mpToolSet/ or studio4AnimToolset/,
whose zips are published as public GitHub Releases.
"""

import os
import sys
import shutil
import zipfile
import subprocess
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))

SCRIPTS = [
    ("pipeDev/publishDev", "publishTool_api.py"),
    ("pipeDev/publishDev", "publishTool_camera.py"),
    ("pipeDev/publishDev", "publishTool_anim.py"),
    ("pipeDev/publishDev", "publishTool_ui.py"),
    ("pipeDev/publishDev", "pipePicker.py"),
    ("pipeDev/publishDev", "rig_rules.py"),
    ("pipeDev/publishDev", "publishTool_textures.py"),
    ("pipeDev/publishDev", "publishTool_outputs.py"),
    ("pipeDev/publishDev", "publishTool_look.py"),
    ("pipeDev/publishDev", "pipeStudioLibrary.py"),
    ("pipeDev/publishDev", "publishTool_env.py"),
    ("pipeDev/buildDev", "pipeEnv.py"),
    ("pipeDev/buildDev", "buildTool_api.py"),
    ("pipeDev/buildDev", "buildTool_ui.py"),
    ("pipeDev/projectDev", "projectTool_api.py"),
    ("pipeDev/projectDev", "projectTool_ui.py"),
    ("pipeDev/layoutDev", "layoutTool_env.py"),
    ("pipeDev/modelDev", "modelTool_convert.py"),
    ("pipeDev/modelDev", "modelTool_usd.py"),
    ("pipeDev/modelDev", "modelTool_usd_ui.py"),
    ("pipeDev/modelDev", "modelTool_usdEdit.py"),
    ("pipeDev/modelDev", "modelTool_usdEdit_ui.py"),
    ("modelDev", "fbxExport.py"),            # not a pipe tool, on the mpModel shelf
    ("pipeDev/lightingDev", "renderSub_api.py"),
    ("pipeDev/lightingDev", "renderSub_ui.py"),
    ("pipeDev/lightingDev", "renderSub_flow.py"),
    ("pipeDev/lightingDev", "renderPresets_api.py"),
    ("pipeDev/lightingDev", "renderPresets_ui.py"),
    ("pipeDev/lightingDev", "backdropCard.py"),
    ("pipeDev/lightingDev", "gafferSend.py"),
    ("pipeDev/lightingDev", "gafferPipeStartup.py"),   # runs in Gaffer, copied there by gafferSend
    ("pipeDev/scoutDev", "scout_api.py"),
    ("pipeDev/scoutDev", "scout_service.py"),
    ("pipeDev/scoutDev", "scout_worker.py"),
    ("pipeDev/scoutDev", "scout_ui.py"),
]
SHELF_DIR = os.path.join(REPO, "shelfDev", "mpPipe")
# Every shelf the package installs (2026-10-23: mpLayout added; 2026-10-30:
# mpModel; 2026-11-13: mpLighting). The first
# goes in the zip as shelf_config.py, the others as shelf_config_<shelf>.py.
SHELF_DIRS = [SHELF_DIR, os.path.join(REPO, "shelfDev", "mpLayout"),
              os.path.join(REPO, "shelfDev", "mpModel"),
              os.path.join(REPO, "shelfDev", "mpLighting")]
TOP = "mpPipe"

# Each build is also copied here, so the latest is ready to download on
# another machine (e.g. RMIT) from dropbox.com. Private unless shared.
# Skipped on machines without Dropbox.
DROPBOX = os.path.join(os.path.expanduser("~"), "Dropbox")
COPY_TO = os.path.join(DROPBOX, "mpPipe")


def _git_hash():
    try:
        out = subprocess.check_output(["git", "-C", REPO, "rev-parse", "--short", "HEAD"],
                                      stderr=subprocess.DEVNULL)
        dirty = subprocess.check_output(["git", "-C", REPO, "status", "--porcelain",
                                         "pipeDev/publishDev", "pipeDev/buildDev",
                                         "pipeDev/pipelineInstaller", "shelfDev/mpPipe",
                                         "pipeDev/layoutDev", "shelfDev/mpLayout",
                                         "pipeDev/modelDev", "shelfDev/mpModel", "modelDev",
                                         "pipeDev/lightingDev", "shelfDev/mpLighting"],
                                        stderr=subprocess.DEVNULL)
        return out.decode().strip() + ("+local changes" if dirty.strip() else "")
    except (OSError, subprocess.CalledProcessError):
        return "no git"


def config_name(index, shelf_dir):
    """A shelf's config file name in the zip."""
    return ("shelf_config.py" if index == 0 else
            "shelf_config_%s.py" % os.path.basename(shelf_dir))


def gaffer_zip():
    """The Gaffer release zip to bundle, or None."""
    import glob
    named = os.environ.get("MPPIPE_GAFFER_ZIP")
    if named:
        return named if os.path.isfile(named) else None
    home = os.path.expanduser("~")
    found = []
    for folder in (os.path.join(home, "Documents", "maya"), os.path.join(home, "Downloads")):
        found += glob.glob(os.path.join(folder, "gaffer-*-windows.zip"))
    return sorted(found, key=os.path.basename)[-1] if found else None


def build(with_gaffer=True):
    entries = [(os.path.join(HERE, n), "%s/%s" % (TOP, n))
               for n in ("install.py", "uninstall.py")]
    gaffer = gaffer_zip() if with_gaffer else None
    if with_gaffer and not gaffer:
        sys.exit("No Gaffer zip found (MPPIPE_GAFFER_ZIP, or gaffer-*-windows.zip in "
                 "Documents\\maya or Downloads). Use --no-gaffer to build without it.")
    if gaffer:
        entries += [(os.path.join(HERE, "gaffer", n), "%s/gaffer/%s" % (TOP, n))
                    for n in ("install.py", "uninstall.py")]
        entries.append((gaffer, "%s/gaffer/%s" % (TOP, os.path.basename(gaffer))))
    for i, shelf_dir in enumerate(SHELF_DIRS):
        entries.append((os.path.join(shelf_dir, "shelf_config.py"),
                        "%s/%s" % (TOP, config_name(i, shelf_dir))))
    for folder, name in SCRIPTS:
        entries.append((os.path.join(REPO, *folder.split("/"), name), "%s/scripts/%s" % (TOP, name)))
    for icons in [os.path.join(d, "icons") for d in SHELF_DIRS]:
        for name in sorted(os.listdir(icons)):
            if name.lower().endswith(".png"):
                entries.append((os.path.join(icons, name), "%s/icons/%s" % (TOP, name)))

    missing = [src for src, _ in entries if not os.path.isfile(src)]
    if missing:
        sys.exit("Missing files:\n  " + "\n  ".join(missing))

    version = "%s (%s)" % (datetime.now().strftime("%Y-%m-%d %H:%M"), _git_hash())
    dist = os.path.join(HERE, "dist")
    os.makedirs(dist, exist_ok=True)
    out = os.path.join(dist, "mpPipe.zip")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for src, arc in entries:
            # The Gaffer zip is already compressed: store it as it is.
            z.write(src, arc, compress_type=zipfile.ZIP_STORED if src == gaffer else None)
        z.writestr(TOP + "/version.txt", version + "\n")
    print("Built %s\n  build %s\n  %d files%s" % (
        out, version, len(entries) + 1,
        "\n  Gaffer: %s" % os.path.basename(gaffer) if gaffer else "\n  without Gaffer"))

    if os.path.isdir(DROPBOX):
        os.makedirs(COPY_TO, exist_ok=True)
        shutil.copy2(out, os.path.join(COPY_TO, "mpPipe.zip"))
        with open(os.path.join(COPY_TO, "mpPipe_build.txt"), "w") as f:
            f.write("mpPipe build %s\n" % version)
        print("Copied to %s" % os.path.join(COPY_TO, "mpPipe.zip"))
    else:
        print("No Dropbox folder on this machine; not copied.")
    return out


if __name__ == "__main__":
    build(with_gaffer="--no-gaffer" not in sys.argv[1:])
