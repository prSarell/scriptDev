# mpModel shelf — modelling tools for the film pipeline (user, 2026-10-30).
# Staff testing only for now: NOT part of mpToolSet or studio4AnimToolset.
# Installed with the mpPipe shelf by pipeDev/pipelineInstaller (its tools
# use the pipe's own modules, e.g. publishTool_api's pipe group).

SHELF_NAME = "mpModel"

# Reloaded in import order on each click, so a reinstall takes effect
# without restarting Maya (see shelfDev/mpPipe/shelf_config.py).
RELOAD_ORDER = ("publishTool_api", "publishTool_textures", "publishTool_env",
                "modelTool_convert")


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
]
