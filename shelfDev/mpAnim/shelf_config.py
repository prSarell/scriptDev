SHELF_NAME = "mpAnim"
SHELF_VERSION = "1.0"

# Each entry defines one shelf button.
# Fields:
#   label   : short text under the button (keep under ~10 chars)
#   tooltip : text shown on hover
#   icon    : Maya built-in icon filename (e.g. "commandButton.png", "render.png")
#   script  : filename inside tools/ — will be copied to ~/maya/scripts/
#   command : Python string executed when the button is clicked
BUTTONS = [
    {
        "label": "Playblast",
        "tooltip": "Open the Playblast Manager — creates versioned JPEG sequences with burn-ins",
        "icon": "playblast.png",
        "script": "pbTool.py",
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
        "icon": "camera.png",
        "script": "ps_cam_preset_simple.py",
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
        "script": "tlmClothChain.py",
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
        "script": "Jiffypomo.py",
        "command": (
            "import importlib\n"
            "import Jiffypomo\n"
            "importlib.reload(Jiffypomo)\n"
            "Jiffypomo.run_jiffypomo()"
        ),
    },
]
