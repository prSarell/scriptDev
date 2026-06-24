SHELF_NAME = "studio4Anim"
SHELF_VERSION = "1.0"

BUTTONS = [
    {
        "label": "multiTool",
        "tooltip": "Open multiTool — animation utilities: snap, constraints, bake, gravity, ballistics, and more",
        "icon": "commandButton.png",
        "command": (
            "import importlib, sys\n"
            "for _m in [k for k in sys.modules if k.startswith('mt') or k == 'multiTool']:\n"
            "    del sys.modules[_m]\n"
            "import multiTool\n"
            "multiTool.show()"
        ),
    },
    {
        "label": "ps_spine",
        "tooltip": "Open ps_spine — build a ribbon spine rig from a drawn curve",
        "icon": "iconSpine.png",
        "command": (
            "import importlib\n"
            "import ps_spine\n"
            "importlib.reload(ps_spine)\n"
            "ps_spine.show()"
        ),
    },
    {
        "label": "Playblast",
        "tooltip": "Open the Playblast Manager — creates versioned JPEG sequences with burn-ins",
        "icon": "playblast.png",
        "command": (
            "import importlib\n"
            "import pbTool\n"
            "importlib.reload(pbTool)\n"
            "pbTool.show_pbTool()"
        ),
    },
    {
        "label": "CamPreset",
        "tooltip": "Open the Camera Preset Manager — save and apply named camera/render presets",
        "icon": "iconCamPreset.png",
        "command": (
            "import importlib\n"
            "import ps_cam_preset_simple as ps\n"
            "importlib.reload(ps)\n"
            "ps.show()"
        ),
    },
    {
        "label": "StudioLib",
        "tooltip": "Open Studio Library — animation pose and clip manager",
        "icon": "iconStudioLib.png",
        "command": (
            "import importlib\n"
            "import studiolibrary\n"
            "importlib.reload(studiolibrary)\n"
            "studiolibrary.main()"
        ),
    },
    {
        "label": "JiffyPomo",
        "tooltip": "Open JiffyPomo — Pomodoro timer and task tracker for Maya artists",
        "icon": "iconJiffy.png",
        "command": (
            "import sys\n"
            "for _m in [k for k in sys.modules if k.startswith('jiffy') or k == 'Jiffypomo']:\n"
            "    del sys.modules[_m]\n"
            "import Jiffypomo\n"
            "Jiffypomo.run_jiffypomo()"
        ),
    },
    {
        "label": "JiffySched",
        "tooltip": "Open JiffySchedule — production schedule and asset tracker for Maya artists",
        "icon": "iconJiffySchedule.png",
        "command": (
            "import importlib, sys\n"
            "for mod in list(sys.modules.keys()):\n"
            "    if 'jiffySchedule' in mod:\n"
            "        del sys.modules[mod]\n"
            "import jiffySchedule\n"
            "importlib.reload(jiffySchedule)\n"
            "jiffySchedule.run_jiffyschedule()"
        ),
    },
    {
        "label": "shortCuts",
        "tooltip": "Open shortCuts — manage and switch hotkey presets per workflow",
        "icon": "iconShortCuts.png",
        "command": (
            "import importlib\n"
            "import shortCuts\n"
            "importlib.reload(shortCuts)\n"
            "shortCuts.show()"
        ),
    },
]
