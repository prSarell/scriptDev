SHELF_NAME = "teamHope"
SHELF_VERSION = "1.0"

BUTTONS = [
    {
        "label": "JiffySG",
        "tooltip": "Open Jiffy SG — ShotGrid-integrated production schedule and asset tracker",
        "icon": "iconJiffySchedule.png",
        "command": (
            "import importlib, sys\n"
            "for mod in list(sys.modules.keys()):\n"
            "    if 'jiffySG' in mod or mod == 'shotgun_api3':\n"
            "        del sys.modules[mod]\n"
            "import jiffySG\n"
            "importlib.reload(jiffySG)\n"
            "jiffySG.run_jiffySG()"
        ),
    },
    {
        "label": "shotSub",
        "tooltip": "Open shotSub — Shot Submission Tool, playblast + ShotGrid publish",
        "icon": "playblast.png",
        "command": (
            "import importlib, sys\n"
            "for mod in list(sys.modules.keys()):\n"
            "    if mod == 'shotSub':\n"
            "        del sys.modules[mod]\n"
            "import shotSub\n"
            "importlib.reload(shotSub)\n"
            "shotSub.show_shotSub()"
        ),
    },
]
