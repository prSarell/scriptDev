SHELF_NAME = "mpAnim"
SHELF_VERSION = "1.1"

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
        "label": "ClothChain",
        "tooltip": "Open the Cloth Chain Sim tool — build and control nCloth chain rigs",
        "icon": "iconClothChain.png",
        "command": (
            "import importlib\n"
            "import tlmClothChain\n"
            "importlib.reload(tlmClothChain)\n"
            "import maya.cmds as cmds\n"
            "run = tlmClothChain.SimClothRig()\n"
            "cmds.evalDeferred(run.UI)"
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
        "label": "PbTempo",
        "tooltip": "Open Playback Tempo Tool — keyframe variable playback speed across a shot and bake the result into rig animation",
        "icon": "iconPbTempo.png",
        "command": (
            "import importlib\n"
            "import PlaybackTempoTool\n"
            "importlib.reload(PlaybackTempoTool)\n"
            "PlaybackTempoTool.show()"
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
