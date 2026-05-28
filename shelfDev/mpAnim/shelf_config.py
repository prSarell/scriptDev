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
        "label": "StudioLib",
        "tooltip": "Open Studio Library — animation pose and clip manager",
        "icon": "iconStudioLib.png",
        "command": (
            "try:\n"
            "    import studiolibrary\n"
            "    studiolibrary.main()\n"
            "except ImportError:\n"
            "    import maya.cmds as cmds\n"
            "    cmds.confirmDialog(\n"
            "        title='Studio Library Not Found',\n"
            "        message='Studio Library is not installed.\\n\\nDrag the install.py file from\\nanimDev/studiolibrary-2.20.2/ onto the Maya viewport, then try again.',\n"
            "        button=['OK']\n"
            "    )"
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
