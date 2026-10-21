"""
Pipe Env — the PIPE_SCRATCH path variable
Lets a shot open from any scratch drive without its references breaking.

Design and reasons: pipeDev/filmPipeline_spec.md §3i "Reference paths that
work on any drive (PIPE_SCRATCH)".

Build Shot writes references into the shared publish folder as

    $PIPE_SCRATCH/NWF_SHF/maya/publish/assets/prop/backpack/scenes/backpack_model_v002.ma

and Maya fills in $PIPE_SCRATCH when it loads them. The variable holds only
the folder that contains the film folders (e.g. "D:" or "E:/MyWork"); the
film's name stays in the path, so one variable covers every film and class.

It's set:
  - every time a scene is opened, from where that scene is, before Maya
    loads its references (a "before open" callback, installed at Maya
    startup by the mpPipe installer's userSetup.py block, see install());
  - at startup, from the saved scratch drive setting, until a scene opens;
  - by Build Shot, from the shot it's building.

If mpPipe isn't installed (e.g. on a machine without it), the variable
isn't set and these references show as missing.
"""

import os
import sys

import publishTool_api as pub

VAR = "PIPE_SCRATCH"
_CALLBACK_ATTR = "_pipeEnv_callback_id"     # kept on sys so a reload doesn't add a second one


def root_of(path):
    """The folder holding the film folder a path is in ('D:/' for
    D:\\NWF_SHF\\maya\\...), or None if the path isn't in a film folder."""
    if not path:
        return None
    try:
        root, _ = pub.find_film_folder(path)
    except pub.PublishError:
        return None
    return root


def _clean(root):
    """'D:\\' -> 'D:', 'E:\\MyWork\\' -> 'E:/MyWork' (so '$VAR/NWF_SHF' joins cleanly)."""
    return os.path.normpath(root).replace("\\", "/").rstrip("/")


def current():
    return os.environ.get(VAR, "")


def set_root(root):
    """Point the variable at a drive root. Returns the value set."""
    value = _clean(root)
    os.environ[VAR] = value
    return value


def set_from_path(path):
    """Point the variable at the root of the film folder a scene is in.
    Ignored for scenes on the H drive (published files) and for paths
    outside a film folder. Returns the value set, or None."""
    root = root_of(path)
    if not root:
        return None
    h_root = pub.get_root(pub.H_DRIVE)
    if h_root and pub._same_path(root, h_root):
        return None
    return set_root(root)


def to_var_path(path):
    """'D:\\NWF_SHF\\maya\\publish\\...' -> '$PIPE_SCRATCH/NWF_SHF/maya/publish/...'
    when the path is under the variable's current root; otherwise the path
    unchanged (forward slashes)."""
    value = current()
    norm = os.path.normpath(path).replace("\\", "/")
    if value:
        prefix = value + "/"
        if os.path.normcase(norm).startswith(os.path.normcase(prefix)):
            return "$%s/%s" % (VAR, norm[len(prefix):])
    return norm


def uses_var(path):
    return path.replace("\\", "/").startswith("$%s/" % VAR) or \
        path.startswith("${%s}" % VAR)


def _before_open(file_object, client_data=None):
    """Before Maya opens a scene: point the variable at that scene's drive,
    so its $PIPE_SCRATCH references load from the same drive."""
    try:
        path = file_object.resolvedFullName() or file_object.rawFullName()
        set_from_path(path)
    except Exception as e:      # never block a file from opening
        print("mpPipe: couldn't set %s: %s" % (VAR, e))
    return True


# ---------------------------------------------------------------------------
# MetaHuman DNA paths. The DNA node can't read $PIPE_SCRATCH (tested
# 2026-10-20: "Failed to initialize rig logic"), so a rig's publish group
# lists each DNA node with its portable path (pipe_dna, written by Publish)
# and the real path for this drive is filled in after a scene opens, and by
# Build when it builds a rig.
# ---------------------------------------------------------------------------

DNA_STAMP = "pipe_dna"
_AFTER_OPEN_ATTR = "_pipeEnv_after_open_id"


def fix_dna_paths():
    """For every rig publish group in the scene with a pipe_dna list, point
    each DNA node (same namespace as the group) at its file on this drive.
    Skips files that aren't there (Build/Repair pulls them). Returns
    [(node, path)] for the nodes changed."""
    import json
    import maya.cmds as cmds
    changed = []
    for group in cmds.ls("*." + DNA_STAMP, objectsOnly=True, recursive=True) or []:
        try:
            entries = json.loads(cmds.getAttr("%s.%s" % (group, DNA_STAMP)) or "[]")
        except ValueError:
            continue
        ns = group.split("|")[-1].rpartition(":")[0]
        for entry in entries:
            node = (ns + ":" if ns else "") + entry["node"]
            path = os.path.expandvars(entry["published"])
            if not cmds.objExists(node) or "$" in path or not os.path.isfile(path):
                continue
            path = os.path.normpath(path).replace("\\", "/")
            plug = "%s.%s" % (node, entry.get("attr", "dnaFilePath"))
            now = cmds.getAttr(plug) or ""
            if os.path.normcase(os.path.normpath(now)) == os.path.normcase(os.path.normpath(path)):
                continue
            if cmds.getAttr(plug, lock=True):
                cmds.setAttr(plug, lock=False)
            cmds.setAttr(plug, path, type="string")
            changed.append((node, path))
    return changed


def _after_open(client_data=None):
    try:
        fix_dna_paths()
    except Exception as e:      # never break opening a scene
        print("mpPipe: couldn't set MetaHuman DNA paths: %s" % e)


def install():
    """Called once at Maya startup (userSetup.py). Sets a starting value
    from the saved scratch drive and registers the before-open callback
    (the variable) and the after-open one (MetaHuman DNA paths). Safe to
    call again: old callbacks are replaced, not doubled."""
    import maya.api.OpenMaya as om
    if not current():
        saved = pub.get_root(pub.SCRATCH)
        if saved:
            set_root(saved)
    for attr in (_CALLBACK_ATTR, _AFTER_OPEN_ATTR):
        old = getattr(sys, attr, None)
        if old is not None:
            try:
                om.MMessage.removeCallback(old)
            except RuntimeError:
                pass
    setattr(sys, _CALLBACK_ATTR, om.MSceneMessage.addCheckFileCallback(
        om.MSceneMessage.kBeforeOpenCheck, _before_open))
    setattr(sys, _AFTER_OPEN_ATTR, om.MSceneMessage.addCallback(
        om.MSceneMessage.kAfterOpen, _after_open))
    try:
        # Studio Library must look deep enough to find show library items
        # (spec §4b); its config is read the first time it's opened.
        import maya.cmds as cmds
        import pipeStudioLibrary
        pipeStudioLibrary.use_config(cmds.internalVar(userPrefDir=True))
    except Exception as e:      # never break Maya starting up
        print("mpPipe: couldn't set up Studio Library's search depth: %s" % e)
    return current()
