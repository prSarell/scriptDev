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
]
