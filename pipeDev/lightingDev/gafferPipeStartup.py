r"""
Gaffer side of the pipe (user, 2026-11-24). Runs inside Gaffer's own Python
(3.11 in Gaffer 1.7), never in Maya: no maya imports here.

Two jobs:

1. install(application): Gaffer's startup stubs call this (gafferSend writes
   them into <gaffer home>\pipeStartup\<app>\pipe.py). Whenever a script is
   opened, PIPE_SCRATCH is set from where the .gfr lives, the way pipeEnv
   does for Maya scenes, so paths written as ${PIPE_SCRATCH}/<film>/... work
   from any drive (pipe rule 8).

2. new_script(...): run through `gaffer python gafferPipeStartup.py
   -arguments new ...` by gafferSend to make a student's first Gaffer file:
   a SceneReader on the Maya sends (<name>_latest.usda), Arnold options and a
   batch beauty output in the student's own folder.
"""

import os
import sys

FILM_SUBFOLDERS = ("maya", "gaffer")     # <film>\maya\..., <film>\gaffer\...
KINDS = ("assets", "sequences", "publish")
VAR = "PIPE_SCRATCH"


def scratch_root(path):
    """The folder holding the film folder for a path inside it
    ('D:' for D:/NWF_SHF/gaffer/assets/...), or None."""
    if not path:
        return None
    parts = os.path.normpath(path).replace("\\", "/").split("/")
    lowered = [p.lower() for p in parts]
    for i in range(len(parts) - 2, 0, -1):
        if lowered[i] in FILM_SUBFOLDERS and lowered[i + 1] in KINDS:
            root = "/".join(parts[:i - 1])
            return root or "/"
    return None


def set_from_script(script):
    """Set PIPE_SCRATCH for this script: as a variable on the script's own
    context (what Gaffer's ${...} substitution reads first; changing
    os.environ from Python doesn't reach Gaffer's C++ side, 2026-11-24, and
    the context isn't saved into the file) and in os.environ for Python."""
    root = scratch_root(script["fileName"].getValue())
    if root:
        os.environ[VAR] = root
        script.context()[VAR] = root
    return root


def install(application):
    """Called from the startup stubs, for each Gaffer app (gui, execute,
    dispatch)."""
    scripts = application.root()["scripts"]

    def added(parent, child):
        try:
            set_from_script(child)
        except Exception as e:      # never stop Gaffer opening a script
            sys.stderr.write("pipe: couldn't set %s: %s\n" % (VAR, e))

    scripts.childAddedSignal().connect(added, scoped=False)
    for script in scripts.children():
        added(scripts, script)


# ---------------------------------------------------------------------------
# A student's first Gaffer file
# ---------------------------------------------------------------------------

def new_script(gfr, scene_file, project_dir, project_name, start, end, fps):
    """Write gfr: SceneReader (scene_file, a ${PIPE_SCRATCH} path) ->
    StandardOptions -> ArnoldOptions -> Outputs (batch beauty under
    project_dir/renders) -> ArnoldRender. project_dir is a ${PIPE_SCRATCH}
    path to the student's own Gaffer folder."""
    import imath
    import IECore
    import IECoreScene
    import Gaffer
    import GafferScene

    script = Gaffer.ScriptNode()
    script["frameRange"]["start"].setValue(int(start))
    script["frameRange"]["end"].setValue(int(end))
    script["framesPerSecond"].setValue(float(fps))
    script["variables"].addChild(Gaffer.NameValuePlug(
        "project:name", IECore.StringData(project_name), "projectName",
        flags=Gaffer.Plug.Flags.Default | Gaffer.Plug.Flags.Dynamic))
    script["variables"].addChild(Gaffer.NameValuePlug(
        "project:rootDirectory", IECore.StringData(project_dir), "projectRootDirectory",
        flags=Gaffer.Plug.Flags.Default | Gaffer.Plug.Flags.Dynamic))

    nodes = []

    def add(name, node, above=None):
        script[name] = node
        if above is not None:
            node["in"].setInput(above["out"])
        Gaffer.Metadata.registerValue(node, "__uiPosition", imath.V2f(0, -8 * len(nodes)))
        nodes.append(node)
        return node

    reader = add("fromMaya", GafferScene.SceneReader())
    reader["fileName"].setValue(scene_file)
    Gaffer.Metadata.registerValue(reader, "description",
                                  "What you sent from Maya (Send to Gaffer). After a new "
                                  "send, press Reload (the refresh button on File Name).")
    options = add("StandardOptions", GafferScene.StandardOptions(), reader)
    try:
        import GafferArnold
    except ImportError:
        GafferArnold = None     # Arnold isn't set up: the file still opens
    last = options
    if GafferArnold is not None:
        last = add("ArnoldOptions", GafferArnold.ArnoldOptions(), options)
    outputs = add("Outputs", GafferScene.Outputs(), last)
    outputs.addOutput("beauty", IECoreScene.Output(
        "${project:rootDirectory}/renders/${script:name}/beauty/beauty.####.exr",
        "exr", "rgba", {"quantize": IECore.IntVectorData([0, 0, 0, 0])}))
    if GafferArnold is not None:
        add("ArnoldRender", GafferArnold.ArnoldRender(), outputs)

    folder = os.path.dirname(gfr)
    if folder and not os.path.isdir(folder):
        os.makedirs(folder)
    script["fileName"].setValue(gfr.replace("\\", "/"))
    script.save()
    return gfr


if __name__ == "__main__" or "argv" in globals():
    # `gaffer python gafferPipeStartup.py -arguments new <gfr> <usd> <dir> <name> <start> <end> <fps>`
    _args = list(globals().get("argv") or sys.argv[1:])
    if _args and _args[0] == "new":
        print("pipe: made %s" % new_script(*_args[1:8]))
