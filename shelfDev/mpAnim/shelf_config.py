SHELF_NAME = "mpAnim"
SHELF_VERSION = "1.0"

# Scripts from metahuman_facial_transfer/ — deployed flat to ~/maya/scripts/.
METAHUMAN_SCRIPTS = [
    "metahuman_facial_transfer_25.py",
    "metahuman_api_25.py",
]

# Scripts deployed to ~/maya/scripts/ but with no shelf button.
# Listed as filenames inside tools/ or multitool/.
EXTRA_SCRIPTS = [
    "mpAnimConfig.py",
    "shortCuts.py",
]

# Scripts from timeManagementDev/jiffyScheduleDev/ — deployed flat to ~/maya/scripts/.
JIFFYSCHEDULE_SCRIPTS = [
    "jiffySchedule.py",
]

# Scripts from timeManagementDev/jiffyPomoDev/ — all deployed flat to ~/maya/scripts/.
JIFFYPOMO_SCRIPTS = [
    "Jiffypomo.py",
    "jiffyUtils.py",
    "jiffyDialogs.py",
    "jiffyWidgets.py",
    "jiffyPromptsTab.py",
    "jiffyNotepadTab.py",
    "jiffyPomoTab.py",
    "jiffySummaryTab.py",
    "jiffySettingsTab.py",
]

# Scripts from animDev/multiTool/ — all deployed flat to ~/maya/scripts/.
MULTITOOL_SCRIPTS = [
    "multiTool.py",
    "mtSnap.py",
    "mtConstraints.py",
    "mtAimRig.py",
    "mtCycleKeys.py",
    "mtGravity.py",
    "mtBallistics.py",
    "mtRefPlane.py",
    "mtWSBake.py",
    "mtOSBake.py",
    "mtBakeDown.py",
    "mtTips.py",
    "mtPanic.py",
]

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
        "icon": "iconCamPreset.png",
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
        "command": (
            "import importlib\n"
            "import Jiffypomo\n"
            "importlib.reload(Jiffypomo)\n"
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
    {
        "label": "shortCuts",
        "tooltip": "Open shortCuts — manage and switch hotkey presets per workflow",
        "icon": "iconShortCuts.png",
        "script": "shortCuts.py",
        "command": (
            "import importlib\n"
            "import shortCuts\n"
            "importlib.reload(shortCuts)\n"
            "shortCuts.show()"
        ),
    },
]
