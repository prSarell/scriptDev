# mpLighting shelf — lighting and render tools for the film pipeline
# (user, 2026-11-13). Staff testing only for now: NOT part of mpToolSet or
# studio4AnimToolset. Installed with the mpPipe shelf by
# pipeDev/pipelineInstaller (its tools use the pipe's own modules).

SHELF_NAME = "mpLighting"

# Reloaded in import order on each click, so a reinstall takes effect
# without restarting Maya (see shelfDev/mpPipe/shelf_config.py).
RELOAD_ORDER = ("publishTool_api", "publishTool_camera", "pipeEnv",
                "renderSub_api", "renderSub_ui")


def _command(module, call):
    return ("import importlib\n"
            "for _n in %r: importlib.reload(importlib.import_module(_n))\n"
            "import %s\n"
            "%s.%s()" % (RELOAD_ORDER, module, module, call))


BUTTONS = [
    {
        "label": "renderSub",
        "tooltip": "renderSub: render the shot in the background (whole shot, a range, every "
                   "Nth frame or a frame list), review it in RV, then publish the frames to "
                   "the H drive and the movie to ShotGrid.",
        "icon": "iconRenderSub.png",
        "command": _command("renderSub_ui", "show"),
    },
]
