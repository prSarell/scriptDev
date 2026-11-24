"""
Remove Gaffer for the film pipe: drag this onto the Maya viewport.

Deletes Documents\\maya\\gaffer\\ (every Gaffer build there, the launcher and
the pipe's startup stubs), the "Gaffer" desktop shortcut, and the
gaffer_root pipe setting. The student's Gaffer files and sends in the film
folders are never touched. The Arnold SDK isn't touched either.
"""

import json
import os
import shutil

import maya.cmds as cmds

TITLE = "Gaffer for mpPipe"
CONFIG_NAME = "pipeline_config.json"
GAFFER_ROOT = "gaffer_root"


def uninstall():
    home = os.path.join(os.path.normpath(cmds.internalVar(userAppDir=True)), "gaffer")
    if cmds.confirmDialog(title=TITLE, message="Remove Gaffer from this computer?\n  %s\n\n"
                          "Your Gaffer files in the film folders are kept." % home,
                          button=["Remove", "Cancel"], defaultButton="Cancel",
                          cancelButton="Cancel", dismissString="Cancel") != "Remove":
        return False
    if os.path.isdir(home):
        shutil.rmtree(home, ignore_errors=True)
    link = os.path.join(os.path.expanduser("~"), "Desktop", "Gaffer.lnk")
    if os.path.isfile(link):
        os.remove(link)
    config_path = os.path.join(cmds.internalVar(userPrefDir=True), CONFIG_NAME)
    if os.path.isfile(config_path):
        with open(config_path) as f:
            config = json.load(f)
        if config.pop(GAFFER_ROOT, None) is not None:
            with open(config_path, "w") as f:
                json.dump(config, f, indent=2)
    left = os.path.isdir(home)
    cmds.confirmDialog(title=TITLE, button=["OK"], message=(
        "Gaffer removed." if not left else
        "Some files couldn't be removed (is Gaffer still open?):\n  %s" % home))
    return not left


def onMayaDroppedPythonFile(_obj):
    uninstall()
