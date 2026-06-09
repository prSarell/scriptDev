# Drag onto Maya viewport to install JiffySchedule on your personal machine.

import shutil, os

SRC_SCRIPT = r"C:\Users\patsa\OneDrive\Documents\maya\scriptDev\timeManagementDev\jiffyScheduleDev\jiffySchedule.py"
SRC_ICON   = r"C:\Users\patsa\OneDrive\Documents\maya\scriptDev\shelfDev\mpAnim\icons\iconJiffySchedule.png"
SHELF_NAME = "mpAnim"

BUTTON_CMD = (
    "import importlib, sys\n"
    "for mod in list(sys.modules.keys()):\n"
    "    if 'jiffySchedule' in mod:\n"
    "        del sys.modules[mod]\n"
    "import jiffySchedule\n"
    "importlib.reload(jiffySchedule)\n"
    "jiffySchedule.run_jiffyschedule()"
)


def _install():
    import maya.cmds as cmds
    import maya.mel as mel

    scripts_dir = os.path.join(cmds.internalVar(userAppDir=True), "scripts")
    icons_dir   = cmds.internalVar(userBitmapsDir=True)
    os.makedirs(scripts_dir, exist_ok=True)
    os.makedirs(icons_dir,   exist_ok=True)

    shutil.copy2(SRC_SCRIPT, os.path.join(scripts_dir, "jiffySchedule.py"))
    shutil.copy2(SRC_ICON,   os.path.join(icons_dir,   "iconJiffySchedule.png"))

    shelf_top = mel.eval("$tmpVar=$gShelfTopLevel")
    shelf     = f"{shelf_top}|{SHELF_NAME}"

    for btn in cmds.shelfLayout(shelf, query=True, childArray=True) or []:
        if cmds.shelfButton(btn, query=True, label=True) == "JiffySched":
            cmds.deleteUI(btn)

    cmds.shelfButton(
        parent=shelf,
        label="JiffySched",
        annotation="Open JiffySchedule — production schedule and asset tracker",
        image1="iconJiffySchedule.png",
        command=BUTTON_CMD,
        sourceType="python",
    )

    mel.eval("saveAllShelves $gShelfTopLevel")
    print("[install_jiffySchedule] done — button added to", SHELF_NAME)


def onMayaDroppedPythonFile(*args):
    _install()
