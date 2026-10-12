"""
Build Tool — core
Pulls published assets from the H drive into a shot on scratch, keeps
track of which version each shot has, and manages what's on scratch.
No UI, so it can be tested under mayapy.

Design: pipeDev/filmPipeline_spec.md §3e (Build owns scratch), §3h
(drives, 1:1 mirror) and §3i (Build Shot workflow, department codes,
scratch management).

    H drive  F:\\NWF_SHF\\maya\\assets\\prop\\backpack\\scenes\\backpack_model_v002.ma
    shot     D:\\NWF_SHF\\maya\\sequences\\EAP_010\\EAP_010_010\\assets\\prop\\backpack\\backpack.ma
    rig      ...\\assets\\prop\\backpack\\rig\\backpack.ma

Shares drive settings, department codes and film-folder helpers with the
Publish tool (pipeDev/publishDev/publishTool_api.py).
"""

import os
import re
import sys
import json
import stat
import ctypes
import shutil
from datetime import datetime

import maya.cmds as cmds

_PUBLISH_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "publishDev")
if os.path.isdir(_PUBLISH_DIR) and _PUBLISH_DIR not in sys.path:
    sys.path.append(_PUBLISH_DIR)

import publishTool_api as pub
from publishTool_api import PublishError as BuildError   # same "student can fix" error

MANIFEST_NAME = "build_manifest.json"   # in <shot>/assets/, records what was pulled
KEEP_FILES = ("workspace.mel",)          # never removed from scratch

PUBLISHED_RE = re.compile(r"^(?P<asset>.+)_(?P<code>[A-Za-z]+)_v(?P<version>\d{3})"
                          r"\.(?P<ext>ma|mb)$", re.IGNORECASE)
DEPT_CODES = [code for _, code in pub.DEPARTMENTS]
DEPT_LABELS = dict((code, label) for label, code in pub.DEPARTMENTS)
DEPT_LABELS["cam"] = "Camera"


# ---------------------------------------------------------------------------
# Films and shots
# ---------------------------------------------------------------------------

def list_films(root):
    """Film folders (<FILM>_<TYPE>) under a drive root."""
    if not root or not os.path.isdir(root):
        return []
    return sorted(n for n in os.listdir(root)
                  if pub.FILM_FOLDER_RE.match(n) and os.path.isdir(os.path.join(root, n)))


def list_shots(root, film):
    """[(sequence, shot), ...] from <root>/<film>/maya/sequences."""
    seq_dir = os.path.join(root, film, "maya", "sequences")
    shots = []
    if not os.path.isdir(seq_dir):
        return shots
    for seq in sorted(os.listdir(seq_dir)):
        seq_path = os.path.join(seq_dir, seq)
        if not os.path.isdir(seq_path):
            continue
        for shot in sorted(os.listdir(seq_path)):
            if os.path.isdir(os.path.join(seq_path, shot)):
                shots.append((seq, shot))
    return shots


def shot_folder(root, film, seq, shot):
    return os.path.join(root, film, "maya", "sequences", seq, shot)


def shot_of_scene(scene_path, scratch_root):
    """(film, seq, shot) if the scene is inside a shot on scratch, else None."""
    try:
        root, rel = pub.find_film_folder(scene_path)
    except BuildError:
        return None
    if (not pub._same_path(root, scratch_root) or len(rel) < 5
            or rel[1] != "maya" or rel[2] != "sequences"):
        return None
    return rel[0], rel[3], rel[4]


# ---------------------------------------------------------------------------
# Published assets on the H drive
# ---------------------------------------------------------------------------

def list_published(h_root, film):
    """Every published asset on the H drive, grouped by asset + department.

    Returns a list of dicts sorted by type/asset/department:
      {asset_type, asset, code, versions: {version: path}, latest}
    """
    assets_dir = os.path.join(h_root, film, "maya", "assets")
    groups = {}
    for asset_type, asset in pub.list_h_assets(h_root, film):
        scenes = os.path.join(assets_dir, asset_type, asset, "scenes")
        for dirpath, _, filenames in os.walk(scenes):
            for name in filenames:
                m = PUBLISHED_RE.match(name)
                if not m or m.group("asset").lower() != asset.lower():
                    continue
                code = m.group("code")
                key = (asset_type, asset, code)
                entry = groups.setdefault(key, {
                    "asset_type": asset_type, "asset": asset, "code": code,
                    "versions": {}})
                entry["versions"][int(m.group("version"))] = os.path.join(dirpath, name)
    result = []
    for key in sorted(groups, key=lambda k: (k[0], k[1].lower(),
                                             DEPT_CODES.index(k[2]) if k[2] in DEPT_CODES else 99)):
        entry = groups[key]
        entry["latest"] = max(entry["versions"])
        result.append(entry)
    return result


CAMERA_TYPE = "camera"              # asset_type used for a shot's camera
CAMERA_CODE = "cam"
CAMERA_NAME = "camera1"             # the shot camera is always live as camera1
OLD_CAMERA_NAME = "camera1_old"     # what an existing camera1 is renamed to
SHOT_ATTR = "pipeShot"              # stamped on camera1 at build
VERSION_ATTR = "pipeCameraVersion"
CURVE_KEY_ATTRS = ("ktv", "kix", "kiy", "kox", "koy", "kit", "kot", "kwl", "tan", "wgt")
CAMERA_FILES = {"camera": "assets/camera/cam.ma",
                "keys": "assets/camera/camAnim.ma",
                "map": "assets/camera/camAnim.json"}
CAMERA_RE = re.compile(r"^(?P<shot>.+)_(?P<code>cam|camAnim)_v(?P<version>\d{3})"
                       r"\.(?P<ext>ma|json)$", re.IGNORECASE)


def list_shot_cameras(h_root, film, seq, shot):
    """The shot's published cameras on the H drive, as a list with at most
    one entry shaped like list_published()'s, plus 'kind': 'camera' and
    'files': {version: {camera, keys, map}}. Only complete versions (all
    three files) count."""
    scenes = os.path.join(shot_folder(h_root, film, seq, shot), "scenes")
    found = {}
    if os.path.isdir(scenes):
        for name in os.listdir(scenes):
            m = CAMERA_RE.match(name)
            if not m or m.group("shot").lower() != shot.lower():
                continue
            part = ("camera" if m.group("code").lower() == "cam" else
                    "keys" if m.group("ext").lower() == "ma" else "map")
            found.setdefault(int(m.group("version")), {})[part] = os.path.join(scenes, name)
    files = dict((v, f) for v, f in found.items() if len(f) == 3)
    if not files:
        return []
    return [{"kind": "camera", "asset_type": CAMERA_TYPE, "asset": shot,
             "code": CAMERA_CODE, "files": files,
             "versions": dict((v, f["camera"]) for v, f in files.items()),
             "latest": max(files)}]


def publish_time(path):
    """When a file was published. copy2 keeps the source's modified time,
    so use the H-drive file's creation time (Windows) where available."""
    st = os.stat(path)
    return st.st_ctime if os.name == "nt" else st.st_mtime


# ---------------------------------------------------------------------------
# Pulling into a shot
# ---------------------------------------------------------------------------

def pulled_rel_path(asset_type, asset, code, ext):
    """Where a department's copy lives inside the shot project, relative to
    the shot root. Modeling sits at the asset folder root; every other
    department gets its own subfolder (§3i)."""
    parts = ["assets", asset_type, asset]
    if code != "model":
        parts.append(code)
    parts.append(asset + ext)
    return "/".join(parts)


def _manifest_path(shot_dir):
    return os.path.join(shot_dir, "assets", MANIFEST_NAME)


def read_manifest(shot_dir):
    try:
        with open(_manifest_path(shot_dir), "r") as f:
            return json.load(f)
    except (IOError, OSError, ValueError):
        return {}


def _write_manifest(shot_dir, manifest):
    path = _manifest_path(shot_dir)
    if not os.path.isdir(os.path.dirname(path)):
        os.makedirs(os.path.dirname(path))
    with open(path, "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)


def manifest_key(asset_type, asset, code):
    return "%s/%s/%s" % (asset_type, asset, code)


def pull(shot_dir, published, version):
    """Copy one published version into the shot under its fixed name,
    overwriting what's there (that's how an update works). Records it in
    the shot's manifest. Returns (dest_path, warning or None)."""
    if version not in published["versions"]:
        raise BuildError("v%03d of %s %s isn't on the H drive."
                         % (version, published["asset"], published["code"]))
    source = published["versions"][version]
    ext = os.path.splitext(source)[1].lower()
    rel = pulled_rel_path(published["asset_type"], published["asset"], published["code"], ext)
    dest = os.path.join(shot_dir, *rel.split("/"))
    if not os.path.isdir(os.path.dirname(dest)):
        os.makedirs(os.path.dirname(dest))

    key = manifest_key(published["asset_type"], published["asset"], published["code"])
    manifest = read_manifest(shot_dir)
    warning = None
    previous = manifest.get(key)
    if previous and previous.get("file") != rel:
        # e.g. v001 was .mb, v002 is .ma: the fixed name changes, so any
        # reference to the old file won't pick this version up.
        warning = ("The file type changed (%s -> %s), so scenes referencing "
                   "the old file need re-pointing." % (previous.get("file"), rel))
        old = os.path.join(shot_dir, *previous["file"].split("/"))
        if os.path.isfile(old):
            os.chmod(old, stat.S_IWRITE)
            os.remove(old)

    if os.path.isfile(dest):
        os.chmod(dest, stat.S_IWRITE)
    shutil.copy2(source, dest)
    os.chmod(dest, stat.S_IWRITE)   # a working copy on scratch, not a locked publish

    manifest[key] = {
        "version": version,
        "file": rel,
        "source": source,
        "pulled": datetime.now().isoformat(timespec="seconds"),
    }
    _write_manifest(shot_dir, manifest)
    return dest, warning


def referenced_nodes(path):
    """Reference nodes in the open scene that point at path."""
    target = os.path.normcase(os.path.normpath(path))
    nodes = []
    for ref_file in cmds.file(query=True, reference=True) or []:
        resolved = cmds.referenceQuery(ref_file, filename=True, withoutCopyNumber=True)
        if os.path.normcase(os.path.normpath(resolved)) == target:
            nodes.append(cmds.referenceQuery(ref_file, referenceNode=True))
    return nodes


def reload_references_to(path):
    """Reload any reference in the open scene that points at path, so an
    update shows up straight away. Returns the reference nodes reloaded."""
    nodes = referenced_nodes(path)
    for node in nodes:
        if cmds.referenceQuery(node, isLoaded=True):
            cmds.file(unloadReference=node)
        cmds.file(loadReference=node)
    return nodes


def namespace_for(asset, code):
    return asset if code == "model" else "%s_%s" % (asset, code)


def build_asset(shot_dir, published, version):
    """One click for one asset: pull it into the shot if it isn't there (or
    a different version is wanted), then make sure the open scene references
    it, reloading if the file was just updated. Never references twice.
    Returns (list of what was done, warning or None)."""
    if published.get("kind") == "camera":
        return build_camera(shot_dir, published, version)
    key = manifest_key(published["asset_type"], published["asset"], published["code"])
    entry = read_manifest(shot_dir).get(key)
    current = os.path.join(shot_dir, *entry["file"].split("/")) if entry else None
    done, warning = [], None

    if not entry or entry["version"] != version or not os.path.isfile(current):
        dest, warning = pull(shot_dir, published, version)
        done.append(("updated to v%03d" if entry else "pulled v%03d") % version)
        pulled = True
    else:
        dest, pulled = current, False

    if referenced_nodes(dest):
        old_ns = use_clean_namespace(dest, namespace_for(published["asset"], published["code"]))
        if old_ns:
            done.append("renamed %s: to %s:" % (old_ns, namespace_for(published["asset"],
                                                                     published["code"])))
        if pulled:
            reload_references_to(dest)
            done.append("reloaded in scene")
        elif not old_ns:
            done.append("already up to date")
    else:
        rel = read_manifest(shot_dir)[key]["file"]
        reference_into_scene(shot_dir, rel, namespace_for(published["asset"], published["code"]))
        done.append("referenced into scene")
    return done, warning


# ---------------------------------------------------------------------------
# Shot camera: imported live (not referenced) as camera1, keys connected
# and locked (spec §3i "Cameras": camera and keys are stored separately)
# ---------------------------------------------------------------------------

def pull_camera(shot_dir, published, version):
    """Copy one camera version's three files into the shot under fixed
    names and record it in the manifest. Returns the camera file path."""
    if version not in published["files"]:
        raise BuildError("Camera v%03d of %s isn't on the H drive."
                         % (version, published["asset"]))
    for part, rel in CAMERA_FILES.items():
        dest = os.path.join(shot_dir, *rel.split("/"))
        if not os.path.isdir(os.path.dirname(dest)):
            os.makedirs(os.path.dirname(dest))
        if os.path.isfile(dest):
            os.chmod(dest, stat.S_IWRITE)
        shutil.copy2(published["files"][version][part], dest)
        os.chmod(dest, stat.S_IWRITE)

    key = manifest_key(CAMERA_TYPE, published["asset"], CAMERA_CODE)
    manifest = read_manifest(shot_dir)
    manifest[key] = {
        "version": version,
        "file": CAMERA_FILES["camera"],
        "extra_files": [CAMERA_FILES["keys"], CAMERA_FILES["map"]],
        "source": published["files"][version]["camera"],
        "pulled": datetime.now().isoformat(timespec="seconds"),
    }
    _write_manifest(shot_dir, manifest)
    return os.path.join(shot_dir, *CAMERA_FILES["camera"].split("/"))


def shot_camera():
    """The built shot camera in the open scene: (transform, version) or
    (None, None). It's the top-level camera1 carrying the build stamp."""
    for node in cmds.ls(CAMERA_NAME, long=True, type="transform") or []:
        if node == "|" + CAMERA_NAME and cmds.attributeQuery(VERSION_ATTR, node=node, exists=True):
            return node, cmds.getAttr("%s.%s" % (node, VERSION_ATTR))
    return None, None


def _camera_curves(transform):
    shape = cmds.listRelatives(transform, shapes=True, fullPath=True, type="camera") or []
    curves = set()
    for node in [transform] + shape:
        curves.update(cmds.listConnections(node, source=True, destination=False,
                                           type="animCurve") or [])
    return sorted(curves)


def set_camera_locked(transform, locked):
    """Lock (or unlock) the camera so its keys can't be edited by accident:
    the channels, the curves' key data (so the Graph Editor can't move keys
    either) and the curve nodes themselves (so they can't be deleted)."""
    shape = cmds.listRelatives(transform, shapes=True, fullPath=True, type="camera")[0]
    curves = _camera_curves(transform)
    for curve in curves:
        cmds.lockNode(curve, lock=False)
    for node in (transform, shape):
        for attr in cmds.listAttr(node, keyable=True) or []:
            try:
                cmds.setAttr("%s.%s" % (node, attr), lock=locked)
            except RuntimeError:
                pass    # compound children etc.
    for curve in curves:
        for attr in CURVE_KEY_ATTRS:
            if cmds.attributeQuery(attr, node=curve, exists=True):
                cmds.setAttr("%s.%s" % (curve, attr), lock=locked)
        if locked:
            cmds.lockNode(curve, lock=True)


def _move_out_of_the_way(node):
    """Rename an existing camera1 (and its shape and our curves) to
    camera1_old, camera1_old1, ... Nothing is deleted. Returns the new name."""
    curves = _camera_curves(node)
    for curve in curves:
        cmds.lockNode(curve, lock=False)
    new = cmds.rename(node, OLD_CAMERA_NAME)
    for shape in cmds.listRelatives(new, shapes=True, fullPath=True) or []:
        cmds.rename(shape, new.split("|")[-1] + "Shape")
    prefix = CAMERA_NAME + "_"
    for curve in curves:
        if curve.startswith(prefix):
            curve = cmds.rename(curve, new.split("|")[-1] + "_" + curve[len(prefix):])
        if cmds.getAttr(curve + ".ktv", lock=True):
            cmds.lockNode(curve, lock=True)     # it was protected; keep it so
    return new.split("|")[-1]


def _import_into_root(path, prefix):
    """Import a file through a temporary namespace (so its names can't
    clash with what's in the scene), then move everything to the root.
    Returns {name in the file: node now in the scene}."""
    ns = prefix
    i = 1
    while cmds.namespace(exists=":" + ns):
        ns, i = "%s%d" % (prefix, i), i + 1
    new = cmds.file(path, i=True, type="mayaAscii", namespace=ns,
                    returnNewNodes=True, preserveReferences=False) or []
    found = dict((n.split("|")[-1].split(":")[-1], n) for n in new if cmds.objExists(n))
    return ns, found


def _drop_namespace(ns):
    if cmds.namespace(exists=":" + ns):
        cmds.namespace(removeNamespace=":" + ns, mergeNamespaceWithRoot=True)


def import_camera(shot_dir, version):
    """Import the pulled camera as a live camera1, connect its keys, stamp
    and lock it. Returns the transform."""
    cam_path = os.path.join(shot_dir, *CAMERA_FILES["camera"].split("/"))
    keys_path = os.path.join(shot_dir, *CAMERA_FILES["keys"].split("/"))
    with open(os.path.join(shot_dir, *CAMERA_FILES["map"].split("/")), "r") as f:
        mapping = json.load(f)

    ns, nodes = _import_into_root(cam_path, "buildCam")
    transform = nodes.get(mapping.get("camera", "shotCam"))
    if not transform or cmds.nodeType(transform) != "transform":
        raise BuildError("The camera file has no %s camera: %s"
                         % (mapping.get("camera", "shotCam"), cam_path))
    transform = cmds.rename(transform, ":" + CAMERA_NAME)
    shape = cmds.listRelatives(transform, shapes=True, fullPath=True, type="camera")[0]
    cmds.rename(shape, ":" + CAMERA_NAME.replace("camera", "cameraShape"))
    _drop_namespace(ns)
    transform = cmds.ls("|" + CAMERA_NAME, long=True)[0]
    shape = cmds.listRelatives(transform, shapes=True, fullPath=True, type="camera")[0]

    ns, curves = _import_into_root(keys_path, "buildCamKeys")
    for curve, (where, attr) in mapping["curves"].items():
        if curve not in curves:
            raise BuildError("The keys file is missing curve %s." % curve)
        node = shape if where == "shape" else transform
        cmds.setAttr("%s.%s" % (node, attr), lock=False)
        cmds.connectAttr(curves[curve] + ".output", "%s.%s" % (node, attr), force=True)
        cmds.rename(curves[curve], ":%s_%s%s" % (CAMERA_NAME, "shape_" if where == "shape" else "", attr))
    _drop_namespace(ns)

    # Stamp: which shot and version this camera is (how a rebuild knows).
    for attr, value in ((SHOT_ATTR, mapping.get("shot", "")), (VERSION_ATTR, version)):
        if not cmds.attributeQuery(attr, node=transform, exists=True):
            if attr == VERSION_ATTR:
                cmds.addAttr(transform, longName=attr, attributeType="long")
            else:
                cmds.addAttr(transform, longName=attr, dataType="string")
        if attr == VERSION_ATTR:
            cmds.setAttr("%s.%s" % (transform, attr), value)
        else:
            cmds.setAttr("%s.%s" % (transform, attr), value, type="string")
        cmds.setAttr("%s.%s" % (transform, attr), lock=True)
    set_camera_locked(transform, True)
    return transform


def build_camera(shot_dir, published, version):
    """One click for the shot camera: pull (or update), then import it live
    as camera1 with its keys, locked. An existing camera1 is renamed
    camera1_old first. Returns (done, warning)."""
    key = manifest_key(CAMERA_TYPE, published["asset"], CAMERA_CODE)
    entry = read_manifest(shot_dir).get(key)
    done = []
    files_there = all(os.path.isfile(os.path.join(shot_dir, *r.split("/")))
                      for r in CAMERA_FILES.values())
    if not entry or entry["version"] != version or not files_there:
        pull_camera(shot_dir, published, version)
        done.append(("updated to v%03d" if entry else "pulled v%03d") % version)

    current, current_version = shot_camera()
    if current and current_version == version:
        done.append("already up to date")
        return done, None

    # Cameras used to be referenced: turn an old reference into live nodes
    # so it can be moved aside like any other camera1.
    cam_path = os.path.join(shot_dir, *CAMERA_FILES["camera"].split("/"))
    for ref_node in referenced_nodes(cam_path):
        cams = [cmds.listRelatives(n, parent=True, fullPath=True)[0]
                for n in cmds.referenceQuery(ref_node, nodes=True, dagPath=True) or []
                if cmds.nodeType(n) == "camera"]
        cmds.file(cmds.referenceQuery(ref_node, filename=True), importReference=True)
        for node in cmds.ls(cams, long=True):
            done.append("old referenced camera %s made live and renamed %s"
                        % (node.split("|")[-1], _move_out_of_the_way(node)))
    for node in cmds.ls(CAMERA_NAME, long=True, type="transform") or []:
        if node == "|" + CAMERA_NAME:
            done.append("existing camera1 renamed %s" % _move_out_of_the_way(node))
    import_camera(shot_dir, version)
    done.append("camera1 v%03d imported and locked" % version)
    return done, None


def free_namespace(namespace):
    """Make sure the clean namespace (e.g. backpack:) can be used. An empty
    leftover namespace is removed; one that still holds nodes is a real
    clash, explained rather than quietly becoming backpack1:."""
    if not cmds.namespace(exists=":" + namespace):
        return
    contents = cmds.namespaceInfo(":" + namespace, listNamespace=True, recurse=True) or []
    if contents:
        raise BuildError(
            "The name '%s:' is already used in this scene by %s.\n"
            "Rename or remove those first, then Build Shot again."
            % (namespace, ", ".join(sorted(contents)[:3]) + (" ..." if len(contents) > 3 else "")))
    cmds.namespace(removeNamespace=":" + namespace)


def use_clean_namespace(path, namespace):
    """If an existing reference to path has a different namespace (e.g.
    backpack1: from before this rule), move it to the clean one when that's
    free. Returns the old namespace if it was changed, else None."""
    for ref_node in referenced_nodes(path):
        current = cmds.referenceQuery(ref_node, namespace=True).lstrip(":")
        if current == namespace:
            continue
        try:
            free_namespace(namespace)
        except BuildError:
            return None     # something else uses the name; leave this one be
        cmds.file(cmds.referenceQuery(ref_node, filename=True), edit=True,
                  namespace=namespace)
        return current
    return None


def reference_into_scene(shot_dir, rel, namespace):
    """Reference a pulled file into the open scene under its clean
    namespace. Uses the project-relative path when the shot is the current
    Maya project (§3g rule 2), so the reference resolves wherever the shot
    project is."""
    free_namespace(namespace)
    workspace = cmds.workspace(query=True, rootDirectory=True)
    if workspace and pub._same_path(workspace, shot_dir):
        path = rel
    else:
        path = os.path.join(shot_dir, *rel.split("/"))
    cmds.file(path, reference=True, namespace=namespace, mergeNamespacesOnClash=False)
    return path


def set_maya_project(shot_dir):
    cmds.workspace(shot_dir, openWorkspace=True)


def ensure_maya_project(shot_dir):
    """Make the shot the Maya project if it isn't already (spec §3f: Build
    sets the project so students don't switch by hand). True if changed."""
    workspace = cmds.workspace(query=True, rootDirectory=True)
    if workspace and pub._same_path(workspace, shot_dir):
        return False
    set_maya_project(shot_dir)
    return True


# ---------------------------------------------------------------------------
# What's on my scratch
# ---------------------------------------------------------------------------

SAFE, CHANGED, UNPUBLISHED = "safe", "changed", "unpublished"


def _files(folder):
    found = []
    for dirpath, _, filenames in os.walk(folder):
        for name in filenames:
            if dirpath == folder and name in KEEP_FILES:
                continue
            found.append(os.path.join(dirpath, name))
    return sorted(found)


def scratch_items(scratch_root, h_root, film):
    """Everything on scratch that holds files, with how safe it is to remove.

    Each item: {kind ('asset'|'shot'), label, folder, files, size,
    status (SAFE/CHANGED/UNPUBLISHED), latest (text), risky: [files]}.
    """
    items = []
    published = list_published(h_root, film) if h_root and os.path.isdir(h_root) else []

    # Assets: safe if every file is a scene older than the newest publish.
    for asset_type, asset in pub.list_h_assets(scratch_root, film):
        folder = os.path.join(scratch_root, film, "maya", "assets", asset_type, asset)
        files = _files(folder)
        if not files:
            continue
        pubs = [p for p in published if p["asset_type"] == asset_type and p["asset"] == asset]
        newest = None
        latest_text = "never published"
        for p in pubs:
            path = p["versions"][p["latest"]]
            t = publish_time(path)
            if newest is None or t > newest[0]:
                newest = (t, p)
        if newest:
            t, p = newest
            latest_text = "%s v%03d, %s" % (DEPT_LABELS.get(p["code"], p["code"]),
                                             p["latest"],
                                             datetime.fromtimestamp(t).strftime("%d %b %H:%M"))
        scenes = os.path.normcase(os.path.join(folder, "scenes")) + os.sep
        risky = []
        for f in files:
            if newest is None or not os.path.normcase(f).startswith(scenes) \
                    or os.path.getmtime(f) > newest[0]:
                risky.append(f)
        status = SAFE if not risky else (UNPUBLISHED if newest is None else CHANGED)
        items.append(_item("asset", "%s  (%s)" % (asset, asset_type), folder,
                           files, status, latest_text, risky))

    # Shots: pulled copies can always be pulled again; anything else isn't
    # backed up anywhere yet (shot publishing isn't built).
    for seq, shot in list_shots(scratch_root, film):
        folder = shot_folder(scratch_root, film, seq, shot)
        files = _files(folder)
        if not files:
            continue
        manifest = read_manifest(folder)
        pulled = set(os.path.normcase(os.path.join(folder, *rel.split("/")))
                     for e in manifest.values()
                     for rel in [e["file"]] + e.get("extra_files", []))
        pulled.add(os.path.normcase(_manifest_path(folder)))
        risky = [f for f in files if os.path.normcase(f) not in pulled]
        status = SAFE if not risky else UNPUBLISHED
        latest = "%d pulled asset(s)" % len(manifest) if manifest else "-"
        items.append(_item("shot", "%s / %s" % (seq, shot), folder,
                           files, status, latest, risky))
    return items


def _item(kind, label, folder, files, status, latest, risky):
    return {"kind": kind, "label": label, "folder": folder, "files": files,
            "size": sum(os.path.getsize(f) for f in files),
            "status": status, "latest": latest, "risky": risky}


def removal_check(folder, h_root, scratch_root):
    """Refuse anything that isn't an asset/shot folder on scratch."""
    h_root, scratch_root = pub.resolve_root(h_root), pub.resolve_root(scratch_root)
    pub.check_roots(h_root, scratch_root)
    root, rel = pub.find_film_folder(os.path.join(folder, "x"))
    is_asset = len(rel) == 6 and rel[1:3] == ["maya", "assets"]
    is_shot = len(rel) == 6 and rel[1:3] == ["maya", "sequences"]
    if not (is_asset or is_shot):
        raise BuildError("Not an asset or shot folder: %s" % folder)
    if not pub._same_path(root, scratch_root):
        raise BuildError("Refusing to remove anything outside the scratch drive (%s)."
                         % scratch_root)


def send_to_recycle_bin(paths):
    """Move files to the Recycle Bin (Windows), so a mistake can be undone.
    Returns True on success. Folders are left in place (1:1 mirror)."""
    if not paths:
        return True
    if os.name != "nt":
        raise BuildError("Recycle Bin removal is only set up for Windows.")
    for p in paths:
        try:
            os.chmod(p, stat.S_IWRITE)
        except OSError:
            pass

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [("hwnd", ctypes.c_void_p), ("wFunc", ctypes.c_uint),
                    ("pFrom", ctypes.c_wchar_p), ("pTo", ctypes.c_wchar_p),
                    ("fFlags", ctypes.c_ushort), ("fAnyOperationsAborted", ctypes.c_int),
                    ("hNameMappings", ctypes.c_void_p),
                    ("lpszProgressTitle", ctypes.c_wchar_p)]

    FO_DELETE, FOF_SILENT, FOF_NOCONFIRMATION, FOF_ALLOWUNDO, FOF_NOERRORUI = \
        3, 0x4, 0x10, 0x40, 0x400
    op = SHFILEOPSTRUCTW()
    op.wFunc = FO_DELETE
    op.pFrom = "\0".join(os.path.abspath(p) for p in paths) + "\0\0"
    op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI
    result = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
    return result == 0 and not op.fAnyOperationsAborted


def format_size(n):
    for unit in ("bytes", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return ("%d %s" % (n, unit)) if unit == "bytes" else ("%.1f %s" % (n, unit))
        n /= 1024.0
