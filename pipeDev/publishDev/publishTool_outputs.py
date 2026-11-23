"""
Publish Tool — output files for other software (user, 2026-10-30)

A Modeling publish (any modelled asset, environments included) can also
write ABC, USD, FBX and OBJ, ticked per row in the publish list. They are
made from exactly what goes in the .ma (the clean copy in its pipe group,
no namespaces) and go in one folder beside it, so the folder can be handed
to another program (e.g. Unreal) on its own:

    <asset>\\scenes\\model\\<login>\\<published name>_exports\\   (spec §4g)
        <published name>.abc        geometry, one frame, world space, UVs
        <published name>.usd        USD with UsdPreviewSurface materials,
                                    textures in textures\\ beside it
                                    (relative paths); the top prim is the
                                    default prim, kind component, and
                                    geo|render / geo|proxy get their USD
                                    purpose when there is a proxy (user,
                                    2026-11-20 / 11-23; see modelTool_usd)
        <published name>.usdz       the same, textures packed inside
        <published name>.fbx        textures embedded
        <published name>.obj/.mtl   + textures\\ (copies, .mtl points there).
                                    OBJ only carries Maya's basic shaders
                                    (Lambert, Blinn, Phong).

The textures come from the version's published copies on the H drive. Each
asset remembers its ticks (user: "always remembers"), on the H drive in
<asset>\\data\\publish\\outputs.json. A failed export fails the publish.
No UI, so it can be tested under mayapy.
"""

import os
import re
import json
import shutil
from datetime import datetime

import maya.cmds as cmds
import maya.mel as mel

import publishTool_api as api
from publishTool_api import PublishError
import publishTool_textures as tex

# (label, key): the publish list's columns, in order.
FORMATS = [("ABC", "abc"), ("USD", "usd"), ("FBX", "fbx"), ("OBJ", "obj")]
FORMAT_KEYS = [key for _, key in FORMATS]
LABELS = dict((key, label) for label, key in FORMATS)
PLUGINS = {"abc": "AbcExport", "usd": "mayaUsdPlugin", "fbx": "fbxmaya", "obj": "objExport"}
EXTENSIONS = {"abc": ".abc", "usd": ".usd", "fbx": ".fbx", "obj": ".obj"}   # USD: + .usdz
FOLDER_SUFFIX = "_exports"
REMEMBER = ("data", "publish", "outputs.json")


# ---------------------------------------------------------------------------
# What each asset remembers
# ---------------------------------------------------------------------------

def remembered_path(h_root, film, asset_type, asset):
    return os.path.join(h_root, film, "maya", "assets", asset_type, asset, *REMEMBER)


def remembered(h_root, film, asset_type, asset):
    """The formats this asset was last published with ([] if none yet)."""
    try:
        with open(remembered_path(h_root, film, asset_type, asset), "r") as f:
            return [k for k in json.load(f).get("formats", []) if k in FORMAT_KEYS]
    except (IOError, OSError, ValueError, AttributeError):
        return []


def remember(h_root, film, asset_type, asset, formats):
    path = remembered_path(h_root, film, asset_type, asset)
    if not os.path.isdir(os.path.dirname(path)):
        os.makedirs(os.path.dirname(path))
    try:
        login = api.who()
    except PublishError:
        login = ""
    with open(path, "w") as f:
        json.dump({"formats": [k for k in FORMAT_KEYS if k in formats], "saved_by": login,
                   "saved": datetime.now().isoformat(timespec="seconds")}, f, indent=2)


# ---------------------------------------------------------------------------
# Writing them
# ---------------------------------------------------------------------------

def check(formats):
    """Load the exporters needed, before anything is published: one that
    won't load stops the publish here."""
    missing = []
    for key in formats:
        try:
            cmds.loadPlugin(PLUGINS[key], quiet=True)
        except RuntimeError:
            missing.append("%s (%s)" % (LABELS[key], PLUGINS[key]))
    if missing:
        raise PublishError("These exporters won't load in this Maya, so nothing was "
                           "published: %s\nUntick them, or ask your teacher." % ", ".join(missing))


def folder_of(dest):
    return os.path.splitext(dest)[0] + FOLDER_SUFFIX


class _RealTextures(object):
    """While inside, texture and image-plane nodes under roots point at the
    version's real texture copies on the H drive instead of their
    $PIPE_SCRATCH paths (which only resolve once Build has pulled them), so
    the exporters can embed and copy them."""

    def __init__(self, roots, h_root):
        self.roots, self.h_root, self.changed = roots, h_root, []
        self.files = {}         # file name -> real path, of every texture used

    def __enter__(self):
        prefix = "$%s/" % tex.VAR
        attrs = dict(tex.TEXTURE_NODES, **tex.IMAGE_PLANES)
        # Everything under the roots (image planes are in the hierarchy),
        # and the whole shading network of every shading group they use.
        dag = cmds.ls(self.roots, long=True) or []
        dag += cmds.listRelatives(dag, allDescendents=True, fullPath=True) or []
        groups = set(cmds.listConnections(cmds.ls(dag, shapes=True) or [],
                                          type="shadingEngine") or [])
        network = dag + (cmds.listHistory(list(groups)) if groups else [])
        # By each node's type: ls(type=...) finds nothing at all if one of
        # the types isn't loaded (aiImage without Arnold).
        for node in set(n for n in network if cmds.objExists(n)
                        and cmds.nodeType(n) in attrs):
            attr = attrs[cmds.nodeType(node)]
            plug = "%s.%s" % (node, attr)
            path = cmds.getAttr(plug) or ""
            if not path.startswith(prefix):
                self.files.setdefault(os.path.basename(path), os.path.expandvars(path))
                continue
            parts = path[len(prefix):].split("/")
            # <film>/maya/publish/<below maya> -> <h_root>\<film>\maya\<below maya>
            if len(parts) < 4 or parts[1] != "maya" or parts[2] != "publish":
                continue
            real = os.path.join(self.h_root, parts[0], "maya", *parts[3:]).replace("\\", "/")
            locked = cmds.getAttr(plug, lock=True)
            if locked:
                cmds.setAttr(plug, lock=False)
            cmds.setAttr(plug, real, type="string")
            self.changed.append((plug, path, locked))
            self.files[os.path.basename(real)] = real
        return self

    def __exit__(self, *exc):
        for plug, path, locked in reversed(self.changed):
            if cmds.objExists(plug.split(".")[0]):
                cmds.setAttr(plug, path, type="string")
                if locked:
                    cmds.setAttr(plug, lock=True)
        return False


def _abc(roots, path, textures):
    frame = int(cmds.currentTime(query=True))
    cmds.AbcExport(j="-frameRange %d %d -uvWrite -worldSpace -writeVisibility "
                     "-dataFormat ogawa %s -file %s" % (
                         frame, frame, " ".join("-root %s" % r for r in roots),
                         path.replace("\\", "/")))


def _usd(roots, path, textures):
    """A plain .usd with its textures copied to textures\\ beside it, and
    the same packed as one .usdz (user, 2026-11-20: ".usd + .usdz")."""
    cmds.select(roots, replace=True)
    cmds.mayaUSDExport(file=path.replace("\\", "/"), selection=True,
                       shadingMode="useRegistry", convertMaterialsTo=["UsdPreviewSurface"])
    finish_usd(path, textures)
    from pxr import Sdf, UsdUtils
    usdz = os.path.splitext(path)[0] + ".usdz"
    if not UsdUtils.CreateNewUsdzPackage(Sdf.AssetPath(path.replace("\\", "/")),
                                         usdz.replace("\\", "/")) or not os.path.isfile(usdz):
        raise PublishError("the .usdz package wasn't made")
    return [usdz]


# The model's USD layout (user, 2026-11-20; modelTool_usd builds it):
#   <asset>_model_GRP   default prim, kind component
#     geo
#       render          purpose render: the meshes that render
#       proxy           purpose proxy: an optional light stand-in
#   Purposes are set only when proxy has geometry (render's proxyPrim
#   points at it); with no proxy, render is left untagged so it shows
#   everywhere, Maya's USD stage included (user 2026-11-23).
#     mtl               materials (the exporter writes them)
USD_PURPOSES = (("geo", "render", "render"), ("geo", "proxy", "proxy"))


def finish_usd(path, textures):
    """What mayaUSDExport leaves out: the top prim as the default prim and a
    component (what USD tools expect of an asset), render/proxy purposes
    (only when proxy has geometry),
    and texture paths relative to the file (textures\\<name>, copied from
    textures, file name -> real path) so the folder works anywhere."""
    from pxr import Usd, UsdGeom, Kind, Sdf
    stage = Usd.Stage.Open(path.replace("\\", "/"))
    tops = list(stage.GetPseudoRoot().GetChildren())
    if tops:
        stage.SetDefaultPrim(tops[0])
        if len(tops) == 1:
            Usd.ModelAPI(tops[0]).SetKind(Kind.Tokens.component)
    for top in tops:
        geo = top.GetChild("geo")
        parts = dict((child, geo.GetChild(child) if geo else None)
                     for _, child, _ in USD_PURPOSES)
        # Purposes only when there's a proxy to stand in (user 2026-11-23):
        # Maya's USD stage draws proxy, not render, by default, so a model
        # with render tagged and no proxy would show nothing there.
        proxy = parts["proxy"]
        if not (proxy and any(p.IsA(UsdGeom.Gprim) for p in Usd.PrimRange(proxy))):
            continue
        for group, child, purpose in USD_PURPOSES:
            prim = parts[child]
            if prim and prim.IsA(UsdGeom.Imageable):
                UsdGeom.Imageable(prim).CreatePurposeAttr().Set(purpose)
        if parts["render"]:
            UsdGeom.Imageable(parts["render"]).SetProxyPrim(proxy)
    folder = os.path.join(os.path.dirname(path), "textures")
    for prim in stage.Traverse():
        for attr in prim.GetAttributes():
            if attr.GetTypeName() != Sdf.ValueTypeNames.Asset:
                continue
            value = attr.Get()
            if not value or not value.path:
                continue
            name = os.path.basename(value.path.replace("\\", "/"))
            src = textures.get(name) or value.resolvedPath or value.path
            if not src or not os.path.isfile(src):
                continue
            if not os.path.isdir(folder):
                os.makedirs(folder)
            target = os.path.join(folder, name)
            if not os.path.isfile(target):
                shutil.copy2(src, target)
            attr.Set(Sdf.AssetPath("./textures/" + name))
    stage.GetRootLayer().Save()


def _fbx(roots, path, textures):
    cmds.select(roots, replace=True)
    mel.eval("FBXResetExport")
    mel.eval("FBXExportEmbeddedTextures -v true")
    mel.eval("FBXExportAnimationOnly -v false")
    mel.eval('FBXExport -f "%s" -s' % path.replace("\\", "/"))


MAP_RE = re.compile(r"^(\s*(?:map_\w+|bump|disp|decal|refl)\b.*?\s)(\S+)\s*$")


def _obj(roots, path, textures):
    cmds.select(roots, replace=True)
    cmds.file(path, exportSelected=True, type="OBJexport", force=True,
              options="groups=1;ptgroups=1;materials=1;smoothing=1;normals=1")
    # The .mtl names each texture by file name only: copy them beside it
    # (from textures, file name -> real path) and point there, so the
    # folder works on its own.
    mtl = os.path.splitext(path)[0] + ".mtl"
    if not os.path.isfile(mtl):
        return
    folder = os.path.join(os.path.dirname(path), "textures")
    lines = []
    with open(mtl, "r") as f:
        for line in f:
            match = MAP_RE.match(line.rstrip("\n"))
            name = match and os.path.basename(match.group(2).replace("\\", "/"))
            src = textures.get(name) if name else None
            if src and os.path.isfile(src):
                if not os.path.isdir(folder):
                    os.makedirs(folder)
                target = os.path.join(folder, os.path.basename(src))
                if not os.path.isfile(target):      # the USD may have copied it (read-only)
                    shutil.copy2(src, target)
                line = "%stextures/%s\n" % (match.group(1), os.path.basename(src))
            lines.append(line)
    with open(mtl, "w") as f:
        f.writelines(lines)


WRITERS = {"abc": _abc, "usd": _usd, "fbx": _fbx, "obj": _obj}


def write(plan, roots):
    """Write the ticked formats (plan['outputs']) for roots, the published
    copy's top nodes, while they're in the scene. Records what was written
    in plan['outputs_written']. Any failure removes the folder and raises."""
    formats = [k for k in FORMAT_KEYS if k in (plan.get("outputs") or [])]
    plan["outputs_written"] = []
    if not formats:
        return []
    check(formats)
    folder = folder_of(plan["dest"])
    if os.path.exists(folder):
        raise PublishError("%s already exists — try again." % folder)
    os.makedirs(folder)
    stem = os.path.splitext(os.path.basename(plan["dest"]))[0]
    h_root = api.find_film_folder(plan["dest"])[0]
    selection = cmds.ls(selection=True)
    try:
        with _RealTextures(roots, h_root) as real:
            for key in formats:
                path = os.path.join(folder, stem + EXTENSIONS[key])
                try:
                    extra = WRITERS[key](roots, path, real.files) or []
                except Exception as e:
                    raise PublishError("The %s export failed, so nothing was published: %s"
                                       % (LABELS[key], e))
                if not os.path.isfile(path):
                    raise PublishError("The %s export wrote nothing, so nothing was "
                                       "published." % LABELS[key])
                plan["outputs_written"] += [path] + list(extra)
        for dirpath, _, names in os.walk(folder):
            for name in names:
                api._lock(os.path.join(dirpath, name))
    except Exception:
        remove(folder)
        plan["outputs_written"] = []
        raise
    finally:
        cmds.select(selection, replace=True) if selection else cmds.select(clear=True)
    return plan["outputs_written"]


def remove(folder):
    """Remove an outputs folder (its files are read-only)."""
    if not os.path.isdir(folder):
        return
    for dirpath, _, names in os.walk(folder):
        for name in names:
            os.chmod(os.path.join(dirpath, name), 0o666)
    shutil.rmtree(folder, ignore_errors=True)
