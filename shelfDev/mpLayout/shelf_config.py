# mpLayout shelf — layout tools for the film pipeline (user, 2026-10-23).
# Staff testing only for now: NOT part of mpToolSet or studio4AnimToolset.
# Installed with the mpPipe shelf by pipeDev/pipelineInstaller (its tools
# use the pipe's own modules, e.g. publishTool_env's set names).

SHELF_NAME = "mpLayout"

# Reloaded in import order on each click, so a reinstall takes effect
# without restarting Maya (see shelfDev/mpPipe/shelf_config.py).
RELOAD_ORDER = ("publishTool_api", "publishTool_textures", "publishTool_env",
                "layoutTool_env")


def _command(module, call):
    return ("import importlib\n"
            "for _n in %r: importlib.reload(importlib.import_module(_n))\n"
            "import %s\n"
            "%s.%s()" % (RELOAD_ORDER, module, module, call))


BUTTONS = [
    {
        "label": "Env Sets",
        "tooltip": "Environment Sets: make the empty environment groups and sets "
                   "(landscape, buildings, sky) with the names Publish checks. "
                   "Then put what you want published into the groups.",
        "icon": "iconLayoutEnvSets.png",
        "command": _command("layoutTool_env", "run"),
    },
]
