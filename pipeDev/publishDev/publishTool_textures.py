"""
Publish Tool — textures
A rig publish carries the textures its shaders use (user, 2026-10-20): they
are copied to the H drive in a folder for that version, and the published
file points at them through $PIPE_SCRATCH, so a shot that pulls the rig
into scratch publish\\ finds them on any drive. No UI, so it can be tested
under mayapy.

Design: pipeDev/filmPipeline_spec.md §4 "Textures in a model publish",
"Texture workflow through rigging".

    working scene   D:\\NWF_SHF\\maya\\assets\\character\\scout\\sourceimages\\skin.png
    H drive         G:\\H\\NWF_SHF\\maya\\assets\\character\\scout\\sourceimages\\s1234567\\
                      scout_s1234567_rig_v003\\skin.png
    published file  $PIPE_SCRATCH/NWF_SHF/maya/publish/assets/character/scout/
                      sourceimages/s1234567/scout_s1234567_rig_v003/skin.png
    shot (Build)    D:\\NWF_SHF\\maya\\publish\\assets\\character\\scout\\sourceimages\\...

Every version gets its own full copy (DECIDED 2026-10-12, "for now"). UDIM
tiles, image sequences and Arnold .tx files beside a texture all travel.
"""

import os
import stat
import shutil

import maya.cmds as cmds

import publishTool_api as api
from publishTool_api import PublishError

FOLDER = "sourceimages"
# Node type -> the attribute holding its file path.
TEXTURE_NODES = {"file": "fileTextureName", "aiImage": "filename"}
# Free-standing image planes (an environment's sky, spec §4c) carry their
# picture too, but only when asked: a rig's or model's camera reference
# planes never travel.
IMAGE_PLANES = {"imagePlane": "imageName"}
VAR = "PIPE_SCRATCH"            # same variable as references (pipeEnv)


def _attr(node):
    node_type = cmds.nodeType(node)
    return TEXTURE_NODES.get(node_type) or IMAGE_PLANES[node_type]


# ---------------------------------------------------------------------------
# What the publish uses
# ---------------------------------------------------------------------------

def texture_nodes(objects):
    """File-texture nodes the publish carries: the shaders on the given
    objects (and everything under them), or every one in the scene when
    objects is empty. Nodes from references don't count."""
    # Only types Maya knows right now: with Arnold not loaded, asking for
    # aiImage makes ls return nothing at all.
    known = set(cmds.allNodeTypes() or [])
    types = [t for t in TEXTURE_NODES if t in known]
    if not objects:
        nodes = cmds.ls(type=types, long=True) or []
    else:
        shapes = cmds.listRelatives(objects, allDescendents=True, fullPath=True,
                                    type="shape") or []
        shapes += cmds.ls(objects, type="shape", long=True) or []
        engines = set(cmds.listConnections(shapes, type="shadingEngine") or [])
        nodes = set()
        for engine in engines:
            nodes.update(cmds.ls(cmds.listHistory(engine) or [], type=types, long=True) or [])
    return sorted(n for n in nodes if not cmds.referenceQuery(n, isNodeReferenced=True))


def image_plane_nodes(objects):
    """Image plane shapes in (or under) the given objects."""
    nodes = cmds.listRelatives(objects, allDescendents=True, fullPath=True,
                               type="imagePlane") or []
    nodes += cmds.ls(objects, type="imagePlane", long=True) or []
    return sorted(set(n for n in nodes if not cmds.referenceQuery(n, isNodeReferenced=True)))


def _short(node):
    """Name without path or namespace: what the node is called in the
    published file (Publish takes namespaces off)."""
    return node.split("|")[-1].split(":")[-1]


def _resolve(path):
    """$VARS filled in; a project-relative path made absolute."""
    path = os.path.expandvars(path)
    if not os.path.isabs(path):
        path = cmds.workspace(expandName=path)
    return os.path.normpath(path)


def node_files(node):
    """(path as the node stores it, [files on disk]) for one texture node.
    UDIM tiles and image sequences give every matching file; an Arnold .tx
    beside a texture comes with it. [] = missing."""
    node_type = cmds.nodeType(node)
    written = cmds.getAttr("%s.%s" % (node, _attr(node))) or ""
    if not written.strip():
        return written, None            # no texture set: nothing to carry
    path = _resolve(written)
    files = []
    if node_type in ("file", "imagePlane"):
        tiling = cmds.getAttr(node + ".uvTilingMode") if node_type == "file" else 0
        frames = cmds.getAttr(node + ".useFrameExtension")
        if tiling or frames:
            from maya.app.general import fileTexturePathResolver as ftr
            pattern = ftr.getFilePatternString(path, frames, tiling)
            files = [os.path.normpath(f) for f in ftr.findAllFilesForPattern(pattern, None)]
    if not files and os.path.isfile(path):
        files = [path]
    for f in list(files):
        tx = os.path.splitext(f)[0] + ".tx"
        if tx != f and os.path.isfile(tx) and tx not in files:
            files.append(tx)
    return written, files


def collect(objects, image_planes=False):
    """[{uuid, node, attr, written, files}] for the publish's textures
    (plus image planes' pictures if image_planes). Raises PublishError
    listing any that are missing on disk."""
    entries, missing = [], []
    nodes = texture_nodes(objects) + (image_plane_nodes(objects) if image_planes and objects
                                      else [])
    for node in nodes:
        written, files = node_files(node)
        if files is None:
            continue
        if not files:
            missing.append("%s: %s" % (node.split("|")[-1], written))
            continue
        entries.append({"uuid": cmds.ls(node, uuid=True)[0], "node": node,
                        "attr": _attr(node), "written": written, "files": files})
    if missing:
        raise PublishError(
            "These textures are missing, so the publish would show them broken "
            "everywhere:\n  %s\n\nFind the files (File > File Path Editor helps), "
            "point the nodes at them, save, and publish again." % "\n  ".join(missing))
    return entries


def collect_dna():
    """[{uuid, node, attr, written, files}] for the rig's MetaHuman DNA
    files (rig_rules.METAHUMAN), wherever they are on disk. Raises
    PublishError listing any that are missing. [] for a rig without
    MetaHuman (or with the plug-in not loaded)."""
    import rig_rules
    rules = rig_rules.METAHUMAN
    if rules["dna_node_type"] not in set(cmds.allNodeTypes() or []):
        return []
    entries, missing = [], []
    for node in cmds.ls(type=rules["dna_node_type"]) or []:
        if cmds.referenceQuery(node, isNodeReferenced=True):
            continue
        attr = rules["dna_path_attr"]
        written = cmds.getAttr("%s.%s" % (node, attr)) or ""
        path = _resolve(written) if written.strip() else ""
        if not path or not os.path.isfile(path):
            missing.append("%s: %s" % (node, written or "(no DNA file set)"))
            continue
        entries.append({"uuid": cmds.ls(node, uuid=True)[0], "node": node, "attr": attr,
                        "written": written, "files": [path]})
    if missing:
        raise PublishError(
            "These MetaHuman DNA files are missing, so the face (or body) rig "
            "wouldn't work anywhere else:\n  %s\n\nPoint the DNA nodes at the "
            "files (MH DNA Repair on the mpRig shelf can help), save, and publish "
            "again." % "\n  ".join(missing))
    return entries


# ---------------------------------------------------------------------------
# Where they go
# ---------------------------------------------------------------------------

def texture_folder(plan):
    """The version's texture folder on the H drive:
    <asset>\\sourceimages\\<login>\\<published file name without extension>."""
    asset_dir = os.path.dirname(os.path.dirname(plan["h_folder"]))   # <asset>\scenes\<login>
    stem = os.path.splitext(os.path.basename(plan["dest"]))[0]
    return os.path.join(asset_dir, FOLDER, plan["login"], stem)


def published_path(folder, name):
    """The $PIPE_SCRATCH path a published file uses for a texture in folder
    (the H drive's layout below <film>\\maya, seen through scratch publish\\)."""
    root, rel = api.find_film_folder(os.path.join(folder, name))
    return "$%s/%s/maya/publish/%s" % (VAR, rel[0], "/".join(rel[2:]))


def _layout(entries):
    """{source file: name in the version folder}. Files keep their names;
    a second source folder with a clashing name goes in its own subfolder
    (whole folder, so UDIM tiles and sequences stay together)."""
    names, by_dir, taken = {}, {}, {}
    for entry in entries:
        for f in entry["files"]:
            by_dir.setdefault(os.path.dirname(f), []).append(f)
    for i, (src_dir, files) in enumerate(sorted(by_dir.items())):
        clash = any(taken.get(os.path.basename(f).lower(), f) != f for f in files)
        sub = ("%d/" % i) if clash else ""
        for f in files:
            names[f] = sub + os.path.basename(f)
            if not sub:
                taken[os.path.basename(f).lower()] = f
    return names


class PublishedTextures(object):
    """For the length of the export: copy the textures (and MetaHuman DNA,
    into dna\\) into the version's folder on the H drive and point the nodes
    at them, so the published file carries the new paths. Textures get the
    $PIPE_SCRATCH path; DNA nodes can't read the variable, so they get the
    publisher's real scratch path, and the portable one goes in the rig
    group's pipe_dna list (stamp_dna) for pipeEnv.fix_dna_paths(). The
    working scene's paths are put back afterwards; if the export fails, the
    copied files are removed again. stamp_textures / stamp_dna: what each
    node used and where it now points, for the rig's publish group."""

    def __init__(self, entries, plan, dna=None):
        self.entries, self.dna, self.plan = list(entries or []), list(dna or []), plan
        self.folder, self.changed = None, []
        self.stamp_textures, self.stamp_dna = [], []

    def __enter__(self):
        if not (self.entries or self.dna):
            return self
        self.folder = texture_folder(self.plan)
        if os.path.exists(self.folder):
            raise PublishError("%s already exists — try again." % self.folder)
        names = _layout(self.entries)
        dna_names = dict((src, "dna/" + name) for src, name in _layout(self.dna).items())
        os.makedirs(self.folder)
        try:
            for src, name in sorted(list(names.items()) + list(dna_names.items())):
                dest = os.path.join(self.folder, *name.split("/"))
                if not os.path.isdir(os.path.dirname(dest)):
                    os.makedirs(os.path.dirname(dest))
                shutil.copy2(src, dest)
                api._lock(dest)
            for entry in self.entries:
                # The node's own path (a UDIM/frame pattern stays a pattern),
                # now inside the version folder.
                sub = os.path.dirname(names[entry["files"][0]])
                name = (sub + "/" if sub else "") + os.path.basename(_resolve(entry["written"]))
                new = published_path(self.folder, name)
                self._set(entry, new)
                self.stamp_textures.append({
                    "node": _short(entry["node"]), "original": entry["written"],
                    "published": new, "files": sorted(names[f] for f in entry["files"])})
            # The publisher's own scratch drive (where the scene is), not
            # whatever the variable last pointed at.
            scratch = os.path.normpath(self.plan["root"]).rstrip("\\/")
            for entry in self.dna:
                new = published_path(self.folder, dna_names[entry["files"][0]])
                real = os.path.normpath(new.replace("$" + VAR, scratch)).replace("\\", "/")
                self._set(entry, real)
                self.stamp_dna.append({
                    "node": _short(entry["node"]), "attr": entry["attr"],
                    "file": os.path.basename(entry["files"][0]),
                    "original": entry["written"], "published": new})
            self.plan["textures"] = {"folder": self.folder, "files": len(names),
                                     "dna": len(dna_names)}
        except Exception:
            self._restore()
            self._remove()
            raise
        return self

    def _set(self, entry, value):
        node = cmds.ls(entry["uuid"], long=True)[0]
        plug = "%s.%s" % (node, entry["attr"])
        locked = cmds.getAttr(plug, lock=True)
        cmds.setAttr(plug, lock=False)
        cmds.setAttr(plug, value, type="string")
        self.changed.append((entry["uuid"], entry["attr"], entry["written"], locked))

    def _restore(self):
        for uuid, attr, written, locked in reversed(self.changed):
            nodes = cmds.ls(uuid, long=True)
            if nodes:
                plug = "%s.%s" % (nodes[0], attr)
                cmds.setAttr(plug, written, type="string")
                cmds.setAttr(plug, lock=locked)
        self.changed = []

    def _remove(self):
        if self.folder and os.path.isdir(self.folder):
            for dirpath, _, filenames in os.walk(self.folder):
                for name in filenames:
                    os.chmod(os.path.join(dirpath, name), stat.S_IWRITE)
            shutil.rmtree(self.folder, ignore_errors=True)
        self.plan.pop("textures", None)

    def __exit__(self, exc_type, *exc):
        self._restore()
        if exc_type is not None:
            self._remove()      # nothing was published: no textures left behind
        return False
