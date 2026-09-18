SHELF_NAME = "studio4Anim"
SHELF_VERSION = "1.0"

BUTTONS = [
    {
        "label": "multiTool",
        "tooltip": "Open multiTool — animation utilities: snap, constraints, bake, gravity, ballistics, and more",
        "icon": "iconMultiTool.png",
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
        "label": "Shot Submit",
        "tooltip": "Open shotSub — playblast + publish to ShotGrid for review",
        "icon": "playblast.png",
        "command": (
            "import importlib\n"
            "import shotSub\n"
            "importlib.reload(shotSub)\n"
            "shotSub.show_shotSub()"
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
    {
        "label": "SmoothTool",
        "tooltip": "Open Smooth Tool — smooth animation curves on NURBS controls with blend and aim-rig baking, plus a Face Smooth tab for MetaHuman-style board controls",
        "icon": "iconSmoothTool.png",
        "command": (
            "import importlib\n"
            "import smoothTool_api, smoothTool_ui\n"
            "importlib.reload(smoothTool_api)\n"
            "importlib.reload(smoothTool_ui)\n"
            "smoothTool_ui.show()"
        ),
    },
    {
        "label": "MH DNA Repair",
        "tooltip": "Repair a broken Metahuman DNA file path — finds the dnaFileNode, shows the current path, and lets you browse to the correct .dna file",
        "icon": "iconMhDnaRepair.png",
        "command": (
            "import importlib\n"
            "import mh_dna_repair\n"
            "importlib.reload(mh_dna_repair)\n"
            "mh_dna_repair.show()"
        ),
    },
    {
        "label": "MHTransfer",
        "tooltip": "Open Metahuman Facial Transfer — retarget Unreal facial animation to Maya",
        "icon": "iconMetahuman.png",
        "command": (
            "import importlib\n"
            "import metahuman_facial_transfer_25 as mh\n"
            "importlib.reload(mh)\n"
            "mh.UI()"
        ),
    },
]
