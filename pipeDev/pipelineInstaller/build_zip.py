"""
Build the mpPipe staff-testing zip.

    mayapy pipeDev/pipelineInstaller/build_zip.py

Collects the pipeline tools straight from their dev folders (they're
dev-direct tools, so there is no staged copy to drift), plus the mpPipe
shelf config and icons, into:

    pipeDev/pipelineInstaller/dist/mpPipe.zip      (dist/ and *.zip are gitignored)

Zip layout (unzip anywhere, drag install.py onto the Maya viewport):

    mpPipe/install.py, uninstall.py, shelf_config.py, version.txt
    mpPipe/scripts/*.py
    mpPipe/icons/*.png

Not for students: never copy this into mpToolSet/ or studio4AnimToolset/,
whose zips are published as public GitHub Releases.
"""

import os
import sys
import zipfile
import subprocess
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))

SCRIPTS = [
    ("pipeDev/publishDev", "publishTool_api.py"),
    ("pipeDev/publishDev", "publishTool_camera.py"),
    ("pipeDev/publishDev", "publishTool_ui.py"),
    ("pipeDev/buildDev", "buildTool_api.py"),
    ("pipeDev/buildDev", "buildTool_ui.py"),
]
SHELF_DIR = os.path.join(REPO, "shelfDev", "mpPipe")
TOP = "mpPipe"


def _git_hash():
    try:
        out = subprocess.check_output(["git", "-C", REPO, "rev-parse", "--short", "HEAD"],
                                      stderr=subprocess.DEVNULL)
        dirty = subprocess.check_output(["git", "-C", REPO, "status", "--porcelain",
                                         "pipeDev/publishDev", "pipeDev/buildDev",
                                         "pipeDev/pipelineInstaller", "shelfDev/mpPipe"],
                                        stderr=subprocess.DEVNULL)
        return out.decode().strip() + ("+local changes" if dirty.strip() else "")
    except (OSError, subprocess.CalledProcessError):
        return "no git"


def build():
    entries = [(os.path.join(HERE, n), "%s/%s" % (TOP, n))
               for n in ("install.py", "uninstall.py")]
    entries.append((os.path.join(SHELF_DIR, "shelf_config.py"), TOP + "/shelf_config.py"))
    for folder, name in SCRIPTS:
        entries.append((os.path.join(REPO, *folder.split("/"), name), "%s/scripts/%s" % (TOP, name)))
    icons = os.path.join(SHELF_DIR, "icons")
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
            z.write(src, arc)
        z.writestr(TOP + "/version.txt", version + "\n")
    print("Built %s\n  build %s\n  %d files" % (out, version, len(entries) + 1))
    return out


if __name__ == "__main__":
    build()
