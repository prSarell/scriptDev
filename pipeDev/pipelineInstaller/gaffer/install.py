"""
Gaffer for the film pipe: drag this onto the Maya viewport (user, 2026-11-24).

Gaffer isn't installed like Maya: it's a folder. This unzips the Gaffer
build that sits beside this file (gaffer-<version>-windows.zip) into
Documents\\maya\\gaffer\\, saves where it is in the pipe settings, and (with
mpPipe installed) writes the launcher and a "Gaffer" desktop shortcut.
Separate from mpPipe's own install.py, like Studio Library's: it's 1.6 GB
and only needed once per version. Run it again for a new Gaffer version.

The Arnold SDK isn't in the bundle (Autodesk's licence): Send to Gaffer asks
for it the first time.
"""

import glob
import json
import os
import shutil
import sys
import zipfile

import maya.cmds as cmds

TITLE = "Gaffer for mpPipe"
CONFIG_NAME = "pipeline_config.json"       # same as publishTool_api.CONFIG_NAME
GAFFER_ROOT = "gaffer_root"                # same as gafferSend.GAFFER_ROOT


def home():
    """Documents\\maya\\gaffer: per user, no admin rights needed."""
    return os.path.join(os.path.normpath(cmds.internalVar(userAppDir=True)), "gaffer")


def source_zip(here):
    found = sorted(glob.glob(os.path.join(here, "gaffer-*-windows.zip")))
    return found[-1] if found else None


def unzip(zip_path, dest):
    """Unzip with Maya's progress window; into a temporary folder first, so
    a cancelled or failed unzip never leaves half a Gaffer. Returns the
    build folder, or None if cancelled."""
    build = os.path.join(dest, os.path.basename(zip_path)[:-len(".zip")])
    temp = build + ".partial"
    if os.path.isdir(temp):
        shutil.rmtree(temp, ignore_errors=True)
    with zipfile.ZipFile(zip_path) as z:
        members = z.infolist()
        cmds.progressWindow(title=TITLE, progress=0, maxValue=len(members),
                            status="Unzipping Gaffer (about 1.6 GB)...", isInterruptable=True)
        try:
            for i, member in enumerate(members):
                if cmds.progressWindow(query=True, isCancelled=True):
                    shutil.rmtree(temp, ignore_errors=True)
                    return None
                z.extract(member, temp)
                if i % 250 == 0:
                    cmds.progressWindow(edit=True, progress=i)
        finally:
            cmds.progressWindow(endProgress=True)
    inner = os.path.join(temp, os.path.basename(build))     # the zip holds one top folder
    if os.path.isdir(build):
        shutil.rmtree(build)
    shutil.move(inner if os.path.isdir(inner) else temp, build)
    shutil.rmtree(temp, ignore_errors=True)
    return build


def save_setting(path):
    """gaffer_root in the pipe settings (through the pipe if it's installed,
    else straight into the same file)."""
    try:
        import publishTool_api as pub
        config = pub.load_config()
        config[GAFFER_ROOT] = path
        pub.save_config(config)
        return
    except ImportError:
        pass
    config_path = os.path.join(cmds.internalVar(userPrefDir=True), CONFIG_NAME)
    config = {}
    if os.path.isfile(config_path):
        with open(config_path) as f:
            config = json.load(f)
    config[GAFFER_ROOT] = path
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)


def install(here):
    zip_path = source_zip(here)
    if not zip_path:
        raise RuntimeError("No gaffer-<version>-windows.zip beside this install.py:\n  %s" % here)
    dest = home()
    build = os.path.join(dest, os.path.basename(zip_path)[:-len(".zip")])
    if os.path.isfile(os.path.join(build, "bin", "gaffer.cmd")):
        if cmds.confirmDialog(title=TITLE, message="%s is already installed:\n  %s\n\nUnzip "
                              "it again?" % (os.path.basename(build), build),
                              button=["Keep It", "Unzip Again"], defaultButton="Keep It",
                              cancelButton="Keep It", dismissString="Keep It") == "Keep It":
            return finish(build)
    if not os.path.isdir(dest):
        os.makedirs(dest)
    build = unzip(zip_path, dest)
    if not build:
        cmds.confirmDialog(title=TITLE, message="Cancelled: Gaffer wasn't installed.",
                           button=["OK"])
        return None
    return finish(build)


def finish(build):
    save_setting(os.path.normpath(build))
    lines = ["Gaffer is in:\n  %s" % build]
    try:
        import gafferSend
        gafferSend.write_launcher(build, gafferSend.settings()[1])
        link = gafferSend.make_shortcut(build)
        lines.append("Desktop shortcut: %s" % ("Gaffer" if link else "couldn't be made"))
    except ImportError:
        lines.append("Install mpPipe too: Send to Gaffer (mpLighting shelf) makes the "
                     "launcher and desktop shortcut.")
    lines.append("\nGaffer renders with the Arnold SDK (a free download with your Autodesk "
                 "education licence). Send to Gaffer asks where it is the first time.")
    cmds.confirmDialog(title=TITLE, message="\n".join(lines), button=["OK"])
    return build


def onMayaDroppedPythonFile(_obj):
    try:
        install(os.path.dirname(os.path.abspath(__file__)))
    except Exception as e:
        cmds.confirmDialog(title=TITLE, message="Gaffer wasn't installed:\n%s" % e,
                           button=["OK"])
        raise
