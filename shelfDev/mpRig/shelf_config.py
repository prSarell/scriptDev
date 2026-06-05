SHELF_NAME = "mpRig"
SHELF_VERSION = "1.0"

# Scripts deployed to ~/maya/scripts/ but with no shelf button.
EXTRA_SCRIPTS = []

# Scripts from rigDev/ — deployed flat to ~/maya/scripts/.
RIGTOOL_SCRIPTS = [
    "ps_spine.py",
]

# Each entry defines one shelf button.
BUTTONS = [
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
]
