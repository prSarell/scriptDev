# mpModel shelf — modelling tools for the film pipeline (user, 2026-10-30).
# Staff testing only for now: NOT part of mpToolSet or studio4AnimToolset.
# Installed with the mpPipe shelf by pipeDev/pipelineInstaller (its tools
# use the pipe's own modules, e.g. publishTool_api's pipe group).

SHELF_NAME = "mpModel"

# Reloaded in import order on each click, so a reinstall takes effect
# without restarting Maya (see shelfDev/mpPipe/shelf_config.py).
RELOAD_ORDER = ("publishTool_api", "publishTool_textures", "publishTool_env", "pipeEnv",
                "buildTool_api", "modelTool_convert", "modelTool_usd", "modelTool_usd_ui",
                "fbxExport")


def _command(module, call):
    return ("import importlib\n"
            "for _n in %r: importlib.reload(importlib.import_module(_n))\n"
            "import %s\n"
            "%s.%s()" % (RELOAD_ORDER, module, module, call))


BUTTONS = [
    {
        "label": "Convert",
        "tooltip": "Convert to Model: select a published model or environment brought in "
                   "from the pipe and click. It becomes a plain Maya model you can work on "
                   "and republish: imported, no pipe group, no namespace, nothing moved. "
                   "Asset scenes only.",
        "icon": "iconModelConvert.png",
        "command": _command("modelTool_convert", "run"),
    },
    {
        "label": "USD Hierarchy",
        "tooltip": "USD Hierarchy: builds geo_USD (red) > render / proxy for publishing the "
                   "model as USD (Publish puts it in <asset>_model_GRP, the USD's top prim). Moves "
                   "what's picked into render (the meshes that render) or proxy (a light "
                   "stand-in), where it is in the world.",
        "icon": "iconModelUsdHierarchy.png",
        "command": _command("modelTool_usd_ui", "show_hierarchy"),
    },
    {
        "label": "USD Names",
        "tooltip": "USD Names: name what's picked (<asset>_<part>_GEO, groups <part>_GRP) "
                   "and fix names that would clash or break the convention before a USD "
                   "publish: duplicates, namespaces, missing _GEO / _GRP, shape names.",
        "icon": "iconModelUsdNames.png",
        "command": _command("modelTool_usd_ui", "show_names"),
    },
]

# Not a pipe tool (user 2026-11-24): its source is the top-level modelDev\,
# it only reads the scene's path. Shipped in the mpPipe package with the shelf.
BUTTONS.append({
    "label": "FBX",
    "tooltip": "FBX Export: exports the selected geometry and cameras as FBX to this "
               "asset's or shot's Substance Painter folder, in your own folder "
               "(<film>/substancePainter/assets/<type>/<asset>/<login>/fromMaya, or "
               ".../sequences/<seq>/<shot>/<login>/fromMaya), as <name>_v001.fbx, "
               "v002, ... Camera animation is baked over the playback range.",
    "icon": "iconModelFbxExport.png",
    "command": _command("fbxExport", "run"),
})
