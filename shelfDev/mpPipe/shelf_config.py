# mpPipe shelf — film pipeline tools (Publish, Build).
# Staff testing only for now: NOT part of mpToolSet or studio4AnimToolset.
# Packaged by pipeDev/pipelineInstaller/build_zip.py.

SHELF_NAME = "mpPipe"

# Each command reloads EVERY pipe module, so re-installing a newer build
# takes effect on the next click without restarting Maya. All of them, in
# import order (a module after the ones it imports): reloading only some
# leaves the others holding old classes, e.g. publishTool_env's old
# PublishError, which the reloaded UI's "except" no longer catches
# (2026-10-22: a shed environment publish failed that way).
RELOAD_ORDER = (
    "rig_rules", "pipeStudioLibrary", "pipePicker",
    "publishTool_api", "publishTool_textures", "publishTool_env",
    "publishTool_camera", "publishTool_anim",
    "pipeEnv", "buildTool_api", "projectTool_api",
    "publishTool_ui", "buildTool_ui", "projectTool_ui",
)


def _command(ui_module):
    return ("import importlib\n"
            "for _n in %r: importlib.reload(importlib.import_module(_n))\n"
            "import %s\n"
            "%s.show()" % (RELOAD_ORDER, ui_module, ui_module))


BUTTONS = [
    {
        "label": "Project",
        "tooltip": "Project Tool: set the Maya project to any asset or shot of your ShotGrid "
                   "projects, and keep your scratch folders in step with the H drive.",
        "icon": "iconPipeProject.png",
        "command": _command("projectTool_ui"),
    },
    {
        "label": "Publish",
        "tooltip": "Publish Tool: publish assets, and shot layout/animation, to the H drive and ShotGrid.",
        "icon": "iconPipePublish.png",
        "command": _command("publishTool_ui"),
    },
    {
        "label": "Build",
        "tooltip": "Build Tool: build shots from published assets, and manage your scratch drive.",
        "icon": "iconPipeBuild.png",
        "command": _command("buildTool_ui"),
    },
]
