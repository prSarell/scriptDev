SHELF_NAME = "mpRig"
SHELF_VERSION = "1.5"

# Scripts deployed to ~/maya/scripts/ but with no shelf button.
EXTRA_SCRIPTS = []

# Scripts from rigDev/ — deployed flat to ~/maya/scripts/.
# Subdirectory paths (e.g. "mh_bs_bake/mh_bs_bake_api.py") are supported;
# they are deployed using just the basename.
RIGTOOL_SCRIPTS = [
    "ps_spine.py",
    "follicleRig_api.py",
    "follicleRig_ui.py",
    "../metahuman_facial_transfer/metahuman_api_25.py",
    "mh_bs_bake/mh_bs_bake_api.py",
    "mh_bs_bake/mh_bs_bake_ui.py",
    "mh_rig_assemble/mh_recycle_api.py",
    "mh_rig_assemble/mh_recycle_ui.py",
    "mh_rig_assemble/mh_dna_repair.py",
    "correctiveBSToolDev/tlmCorrectiveBS_api.py",
    "correctiveBSToolDev/tlmCorrectiveBS_ui.py",
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
    {
        "label": "Follicle Rig",
        "tooltip": "Open Follicle Rig Tools — scatter follicles across NURBS or poly surfaces",
        "icon": "iconFollicleRig.png",
        "command": (
            "import importlib\n"
            "import follicleRig_api, follicleRig_ui\n"
            "importlib.reload(follicleRig_api)\n"
            "importlib.reload(follicleRig_ui)\n"
            "follicleRig_ui.show()"
        ),
    },
    {
        "label": "MH BS Bake",
        "tooltip": "Open MH Blendshape Baker — bake Metahuman RigLogic face rig into a portable blendshape rig",
        "icon": "iconMhBsBake.png",
        "command": (
            "import importlib\n"
            "import mh_bs_bake_api, mh_bs_bake_ui\n"
            "importlib.reload(mh_bs_bake_api)\n"
            "importlib.reload(mh_bs_bake_ui)\n"
            "mh_bs_bake_ui.show()"
        ),
    },
    {
        "label": "Corrective BS",
        "tooltip": "Open Corrective Blendshape Editor — add corrective shapes to fix deformation errors",
        "icon": "iconCorrectiveBS.png",
        "command": (
            "import importlib\n"
            "import tlmCorrectiveBS_api, tlmCorrectiveBS_ui\n"
            "importlib.reload(tlmCorrectiveBS_api)\n"
            "importlib.reload(tlmCorrectiveBS_ui)\n"
            "tlmCorrectiveBS_ui.show()"
        ),
    },
    {
        "label": "MH Recycle",
        "tooltip": "Open MH Rig Recycle — strip Metahuman plugin dependency and export a standalone blendshape face rig",
        "icon": "iconMhRecycle.png",
        "command": (
            "import importlib\n"
            "import mh_recycle_api, mh_recycle_ui\n"
            "importlib.reload(mh_recycle_api)\n"
            "importlib.reload(mh_recycle_ui)\n"
            "mh_recycle_ui.show()"
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
]
