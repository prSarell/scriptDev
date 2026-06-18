SHELF_NAME = "mpRig"
SHELF_VERSION = "2.1"

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
    {
        "label": "MH Body Clean",
        "tooltip": "Open MH Body Clean — delete LODs, Unreal lights, and assign base colour textures to a Metahuman body scene",
        "icon": "iconMhBodyClean.png",
        "command": (
            "import importlib\n"
            "import mh_body_clean_api, mh_body_clean_ui\n"
            "importlib.reload(mh_body_clean_api)\n"
            "importlib.reload(mh_body_clean_ui)\n"
            "mh_body_clean_ui.show()"
        ),
    },
    {
        "label": "VP Shader",
        "tooltip": "Open VP Shader Assign — auto-assign colour-coded shaders to Virtual Pancakes selection sets so joint-critical edge loops are visible before sculpting",
        "icon": "iconVpShader.png",
        "command": (
            "import importlib\n"
            "import vp_shader_api, vp_shader_ui\n"
            "importlib.reload(vp_shader_api)\n"
            "importlib.reload(vp_shader_ui)\n"
            "vp_shader_ui.show()"
        ),
    },
    {
        "label": "DoubleSkin",
        "tooltip": "Open Double Skin Face Rig — add fine surface-joint control to an existing face rig mid-production",
        "icon": "iconDsfr.png",
        "command": (
            "import importlib\n"
            "import pose_capture, dsfr_api, dsfr_ui\n"
            "importlib.reload(pose_capture)\n"
            "importlib.reload(dsfr_api)\n"
            "importlib.reload(dsfr_ui)\n"
            "dsfr_ui.show()"
        ),
    },
    {
        "label": "NS Strip",
        "tooltip": "Open Namespace Stripper — strip namespaces, add prefix/suffix, and revert names on selected transforms and joints",
        "icon": "iconNsStrip.png",
        "command": (
            "import importlib\n"
            "import ps_namespace_stripper\n"
            "importlib.reload(ps_namespace_stripper)\n"
            "ps_namespace_stripper.show()"
        ),
    },
    {
        "label": "ngSkinTools",
        "tooltip": "Open ngSkinTools2 — layer-based skin weight painting and editing",
        "icon": "iconNgSkin.png",
        "command": (
            "import ngSkinTools2\n"
            "ngSkinTools2.open_ui()"
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
]
