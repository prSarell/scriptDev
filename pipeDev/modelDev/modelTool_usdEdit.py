"""
Model Tool — USD Edit (mpModel shelf, spec §4i, user 2026-11-24)

"Select a model on screen or in the outliner and hit the edit button, move
it to wherever, and save it", for this shot or for the asset (every shot).

Build loads a USD model as a stage reading the scene's shot layer, which
sits over the asset's edit layer, over the published .usd
(buildTool_api.write_stage_layers):

    shot layer   <scene's project>\\usd\\<asset>_<code>.usda       "this shot"
    asset layer  <maya>\\assets\\<type>\\<asset>\\usd\\<asset>_<code>_edit.usda   "the asset"
    published    <maya>\\publish\\...\\<name>.usd                  never edited

The same prim path in all three, so editing is only a matter of which layer
is the edit target: begin() points it at the shot or asset layer (and stops
the published layer taking edits), save() saves what changed and points it
back at the shot layer, discard() throws unsaved edits away.

The asset's edits reach the model through its Maya scene, like any model
change: apply_to_model() (in the asset's scene) moves the Maya nodes under
geo_USD to match the asset layer, then the student publishes as usual, so
the .ma and .usd stay in step and H only gets publishes (PIPE_RULES 3, 4).

One USD rule to know: a transform edit writes the object's whole op order,
so once a shot has moved an object, asset-level moves of that same object
don't show in that shot (the shot's placement wins).

No UI here (modelTool_usdEdit_ui), so it can be tested under mayapy.
"""

import os

import maya.cmds as cmds

import buildTool_api as build
import publishTool_api as pub
from publishTool_api import PublishError

SHOT, ASSET = "shot", "asset"
LABELS = {SHOT: "this shot", ASSET: "the asset (every shot)"}
XFORM_PREFIX = "xformOp"


# ---------------------------------------------------------------------------
# What's picked
# ---------------------------------------------------------------------------

def _shape_under(node):
    """The USD stage shape at or below a Maya node, or None."""
    node = (cmds.ls(node, long=True) or [None])[0]
    if not node:
        return None
    if cmds.nodeType(node) == build.USD_SHAPE:
        return node
    found = cmds.ls(cmds.listRelatives(node, allDescendents=True, fullPath=True) or [],
                    type=build.USD_SHAPE, long=True) or []
    return found[0] if len(found) == 1 else None


def picked():
    """(shape, prim path or None) for what's selected: a USD prim picked in
    the viewport or Outliner, or the stage's Maya node (or its pipe group).
    (None, None) if no single stage is picked."""
    if not cmds.pluginInfo(build.USD_PLUGIN, query=True, loaded=True):
        return None, None
    try:
        import ufe
        for item in ufe.GlobalSelection.get():
            path = item.path()
            if path.nbSegments() > 1:       # a USD prim: |maya|path,/usd/path
                shape = _shape_under(str(path.segments[0]).replace("|world", "", 1))
                if shape:
                    return shape, str(path.segments[1])
    except (ImportError, RuntimeError):
        pass
    for node in cmds.ls(selection=True, long=True) or []:
        shape = _shape_under(node)
        if shape:
            return shape, None
    return None, None


def asset_of(shape):
    """(asset type, asset, code) a Build stage loads, from its manifest key."""
    transform = cmds.listRelatives(shape, parent=True, fullPath=True)[0]
    if not cmds.attributeQuery(build.USD_KEY_ATTR, node=transform, exists=True):
        raise PublishError("%s wasn't loaded by Build, so it has no shot or asset layer. "
                           "Load it with Build (USD ticked)." % transform.split("|")[-1])
    return tuple(cmds.getAttr(transform + "." + build.USD_KEY_ATTR).split("/"))


# ---------------------------------------------------------------------------
# Layers
# ---------------------------------------------------------------------------

def layers(shape):
    """{'shot', 'asset', 'published'}: the stage's Sdf layers (see
    buildTool_api.stage_layers)."""
    return build.stage_layers(shape)


def needs_upgrade(shape):
    """True for a stage Build loaded before edit layers (it reads the
    publish directly): upgrade() gives it its layers."""
    found = layers(shape)
    return found["shot"] is None and found["published"] is not None


def upgrade(shape):
    """Give a stage from before edit layers its shot and asset layers
    (the fix button for needs_upgrade). The scene's project is the shot."""
    asset_type, asset, code = asset_of(shape)
    transform = cmds.listRelatives(shape, parent=True, fullPath=True)[0]
    written = cmds.getAttr(shape + ".filePath")
    source = build._absolute(written)
    shot_dir = os.path.normpath(cmds.workspace(query=True, rootDirectory=True))
    shot_layer = build.write_stage_layers(
        shot_dir, {"asset_type": asset_type, "asset": asset, "code": code}, source)
    build.set_stage_source(transform, shape, shot_layer, written)


def _usd_stage(shape):
    import mayaUsd.ufe
    return mayaUsd.ufe.getStage(cmds.ls(shape, long=True)[0])


def editing(shape):
    """SHOT, ASSET or None: which of the stage's layers is the edit target."""
    stage = _usd_stage(shape)
    found = layers(shape)
    target = stage.GetEditTarget().GetLayer() if stage else None
    for role in (ASSET, SHOT):
        if target is not None and found[role] is not None and target == found[role]:
            return role
    return None


def _set_target(shape, layer):
    cmds.mayaUsdEditTarget(cmds.ls(shape, long=True)[0], edit=True,
                           editTarget=layer.identifier)


def begin(shape, role):
    """Point the stage's edits at the shot or asset layer. The published
    layer is set not to take edits. Returns the layer's file."""
    if role not in (SHOT, ASSET):
        raise ValueError(role)
    if needs_upgrade(shape):
        raise PublishError("This stage was loaded before USD Edit and has no edit layers. "
                           "Click Update Stage (or build it again in Build).")
    found = layers(shape)
    if found[role] is None:
        raise PublishError("This stage has no %s layer. Build it again in Build." % role)
    if found["published"] is not None:
        found["published"].SetPermissionToEdit(False)
    _set_target(shape, found[role])
    return found[role].realPath


def dirty(shape):
    """The roles whose layer has unsaved edits."""
    found = layers(shape)
    return [r for r in (SHOT, ASSET) if found[r] is not None and found[r].dirty]


def save(shape):
    """Save the shot and asset layers' edits and point edits back at the
    shot layer. Returns the roles saved."""
    found = layers(shape)
    if found[ASSET] is not None and found[ASSET].dirty:
        record_base(shape)
    saved = []
    for role in (SHOT, ASSET):
        layer = found[role]
        if layer is not None and layer.dirty:
            layer.Save()
            saved.append(role)
    if found[SHOT] is not None:
        _set_target(shape, found[SHOT])
    return saved


def discard(shape):
    """Throw away unsaved edits in the shot and asset layers. Returns the
    roles reverted."""
    found = layers(shape)
    reverted = []
    for role in (SHOT, ASSET):
        layer = found[role]
        if layer is not None and layer.dirty:
            layer.Reload(True)
            reverted.append(role)
    if found[SHOT] is not None:
        _set_target(shape, found[SHOT])
    return reverted


def edited_prims(layer):
    """Prim paths that have attribute opinions in a layer, sorted."""
    paths = []

    def visit(spec):
        if spec.attributes or spec.properties:
            paths.append(str(spec.path))
        for child in spec.nameChildren:
            visit(child)

    for root in layer.rootPrims:
        visit(root)
    return sorted(paths)


# ---------------------------------------------------------------------------
# The asset's edits into its Maya model
# ---------------------------------------------------------------------------

def _model_scene():
    """(maya dir, asset type, asset) for the open asset scene."""
    scene = cmds.file(query=True, sceneName=True)
    if not scene:
        raise PublishError("Open (or save) the asset's scene first.")
    context = pub.asset_context(scene)
    root, rel = pub.find_film_folder(scene)
    return os.path.join(root, rel[0], "maya"), context["asset_type"], context["asset"]


def asset_layer_file(code="model"):
    """The open asset scene's asset edit layer file (it may not exist)."""
    maya_dir, asset_type, asset = _model_scene()
    return build.asset_edit_layer_path(maya_dir, asset_type, asset, code)


def _maya_node(prim_path, asset):
    """The Maya node in the work scene for a model prim path:
    /<asset>_model_GRP/geo/a/b -> |geo_USD|a|b (or |geo|a|b in a scene
    from before geo_USD)."""
    parts = prim_path.strip("/").split("/")
    if len(parts) < 2 or parts[0] != pub.pipe_group_name(asset, "model") \
            or parts[1] != pub.USD_TOP:
        return None
    for top in (pub.USD_WORK_TOP, pub.USD_TOP):
        node = "|" + "|".join([top] + parts[2:])
        if cmds.objExists(node):
            return node
    return None


def pending():
    """What apply_to_model() would do in the open asset scene:
    (moves [(prim path, Maya node)], not found [prim path],
    other edits [prim path.attribute])."""
    path = asset_layer_file()
    if not os.path.isfile(path):
        return [], [], []
    build.load_usd_plugin()
    from pxr import Sdf
    layer = Sdf.Layer.FindOrOpen(path.replace("\\", "/"))
    _, _, asset = _model_scene()
    moves, missing, other = [], [], []
    for prim_path in edited_prims(layer):
        spec = layer.GetPrimAtPath(prim_path)
        names = [a.name for a in spec.attributes]
        xform = [n for n in names if n.startswith(XFORM_PREFIX)]
        other += ["%s.%s" % (prim_path, n) for n in names if not n.startswith(XFORM_PREFIX)]
        if not xform:
            continue
        node = _maya_node(prim_path, asset)
        if node:
            moves.append((prim_path, node))
        else:
            missing.append(prim_path)
    return moves, missing, other


def _composed_stage(layer):
    """The asset layer over the publish it was made on (the shot layer's
    sublayer it sat beside when saved), so a transform reads whole."""
    from pxr import Sdf, Usd
    base = (layer.customLayerData.get(build.USD_LAYER_KEY) or {}).get("base")
    root = Sdf.Layer.CreateAnonymous(".usda")
    root.subLayerPaths.append(layer.identifier)
    if base:
        base_path = layer.ComputeAbsolutePath(base)
        if os.path.isfile(base_path):
            root.subLayerPaths.append(base_path)
    return Usd.Stage.Open(root)


def apply_to_model():
    """In the asset's own scene: move each Maya node under geo_USD to the
    local transform the asset layer gives its prim. Undoable in one step.
    Returns (moved nodes, not found prim paths, other edits skipped)."""
    moves, missing, other = pending()
    if not moves:
        return [], missing, other
    from pxr import Sdf, Usd, UsdGeom
    layer = Sdf.Layer.FindOrOpen(asset_layer_file().replace("\\", "/"))
    stage = _composed_stage(layer)
    moved = []
    cmds.undoInfo(openChunk=True, chunkName="USD Edit: apply asset edits")
    try:
        for prim_path, node in moves:
            prim = stage.GetPrimAtPath(prim_path)
            if not prim:
                missing.append(prim_path)
                continue
            matrix = UsdGeom.Xformable(prim).GetLocalTransformation(Usd.TimeCode.Default())
            cmds.xform(node, objectSpace=True, matrix=[matrix[r][c] for r in range(4)
                                                       for c in range(4)])
            moved.append(node)
    finally:
        cmds.undoInfo(closeChunk=True)
    return moved, missing, other


def record_base(shape):
    """Note on the asset layer which publish its edits were made over, so
    apply_to_model() can read a transform whole."""
    found = layers(shape)
    if found[ASSET] is None or found["published"] is None:
        return
    rel = build._rel_layer_path(found[ASSET].realPath, found["published"].realPath)
    data = dict(found[ASSET].customLayerData)
    stamp = dict(data.get(build.USD_LAYER_KEY) or {})
    if stamp.get("base") != rel:
        stamp["base"] = rel
        data[build.USD_LAYER_KEY] = stamp
        found[ASSET].customLayerData = data


def clear_asset_edits():
    """Empty the open asset scene's asset layer (after its edits are in the
    model and published). Every shot on this scratch drive stops getting
    them. Returns how many prims had edits."""
    path = asset_layer_file()
    if not os.path.isfile(path):
        return 0
    build.load_usd_plugin()
    from pxr import Sdf
    layer = Sdf.Layer.FindOrOpen(path.replace("\\", "/"))
    count = len(edited_prims(layer))
    for prim in list(layer.rootPrims):
        del layer.rootPrims[prim.name]
    layer.Save()
    return count
