# mpPipe shelf — film pipeline tools (Publish, Build).
# Staff testing only for now: NOT part of mpToolSet or studio4AnimToolset.
# Packaged by pipeDev/pipelineInstaller/build_zip.py.

SHELF_NAME = "mpPipe"

# Each command reloads its modules, so re-installing a newer build takes
# effect on the next click without restarting Maya.
BUTTONS = [
    {
        "label": "Publish",
        "tooltip": "Publish Tool: publish assets and shot cameras to the H drive and ShotGrid.",
        "icon": "iconPipePublish.png",
        "command": (
            "import importlib, publishTool_api, publishTool_camera, publishTool_ui\n"
            "for _m in (publishTool_api, publishTool_camera, publishTool_ui): importlib.reload(_m)\n"
            "publishTool_ui.show()"
        ),
    },
    {
        "label": "Build",
        "tooltip": "Build Tool: build shots from published assets, and manage your scratch drive.",
        "icon": "iconPipeBuild.png",
        "command": (
            "import importlib, publishTool_api, publishTool_camera, buildTool_api, buildTool_ui\n"
            "for _m in (publishTool_api, publishTool_camera, buildTool_api, buildTool_ui): importlib.reload(_m)\n"
            "buildTool_ui.show()"
        ),
    },
]
