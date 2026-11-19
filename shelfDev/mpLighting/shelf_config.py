# mpLighting shelf — lighting and render tools for the film pipeline
# (user, 2026-11-13). Staff testing only for now: NOT part of mpToolSet or
# studio4AnimToolset. Installed with the mpPipe shelf by
# pipeDev/pipelineInstaller (its tools use the pipe's own modules).

SHELF_NAME = "mpLighting"

# Reloaded in import order on each click, so a reinstall takes effect
# without restarting Maya (see shelfDev/mpPipe/shelf_config.py).
RELOAD_ORDER = ("publishTool_api", "publishTool_camera", "pipeEnv",
                "renderSub_api", "renderSub_flow", "renderSub_ui",
                "renderPresets_api", "renderPresets_ui", "backdropCard")


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
    {
        "label": "Presets",
        "tooltip": "Render Presets: save this shot's Arnold settings, AOVs and lights (names, "
                   "world positions and every setting) as a named preset, then apply it in any "
                   "other shot of the film.",
        "icon": "iconRenderPresets.png",
        "command": _command("renderPresets_ui", "show"),
    },
    {
        "label": "Backdrop",
        "tooltip": "Backdrop Card: turn the selected free image plane(s) into a renderable "
                   "card with the same image, size and world position. Unlit, seen by the "
                   "camera only (no shadows, reflections or bounce light). The image plane "
                   "is hidden, not deleted; run it again to rebuild the card. An image from "
                   "another project is copied into this project's sourceimages/backdrops.",
        "icon": "iconBackdropCard.png",
        "command": _command("backdropCard", "convert"),
    },
]
