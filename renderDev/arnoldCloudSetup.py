"""
arnoldCloudSetup.py

Turns the selected mesh(es) into an Arnold volume cloud container
(Maya 2025+, MtoA). Follows the classic "sphere + aiStandardVolume + Cloud
texture" setup:

    mesh shape            aiStepSize          (Arnold > Volume Attributes)
    aiStandardVolume  --> shading group .volumeShader
    cloud (3D texture) --> aiStandardVolume.transparent
    place3dTexture        uniform, ~0.15 of the container's widest half-size
                          (bigger = bigger clouds)
    Render Settings       Ray Depth > Volume raised to 6 (bright, scattered clouds)

Usage (Script Editor, Python tab):
    import arnoldCloudSetup
    arnoldCloudSetup.build()                  # selected mesh(es), "character" preset
    arnoldCloudSetup.build("pSphere1")        # or name one
    arnoldCloudSetup.build(preset="small")    # the original fixed waveTest settings

Presets:
    character (default)  For scenes at real-world cm scale (1 unit = 1 cm,
                         characters ~180 units tall). Density and step size
                         are worked out from the container's size, so the
                         cloud looks the same whatever size the container is.
    small                The original look tuned in waveTest (2026-10-26):
                         density 0.1, step size 0.1 whatever the container
                         size. Good for small containers; a big container
                         renders solid white with it.

Both presets share the low contrast/amplitude Cloud texture and soft edge
thresholds from waveTest.

Why size matters: Arnold density is per unit of distance, so a ray through
a container 100x wider meets 100x more cloud. The character preset divides
density (and multiplies step size) by container width / REFERENCE_SIZE.

Tip: scale/flatten a sphere first - it's the container the clouds live in.
Build AFTER scaling it: the settings are worked out from its size when the
tool runs. Volumes are slow to render; test with a small render region.
"""
from maya import cmds

VOLUME_RAY_DEPTH = 6
DIFFUSION_BIAS = 0.0
DIFFUSION_ROUGHNESS = 0.378

# Cloud 3D texture
CLOUD_CONTRAST = 0.1
CLOUD_AMPLITUDE = 0.385
CLOUD_TRANSP_RANGE = 0.05
CLOUD_CENTER_THRESH = 0.091
CLOUD_EDGE_THRESH = 0.755

# placement size as a fraction of the container's widest half-size
PLACE_SCALE_RATIO = 0.15

# Container width (widest side, scene units) the waveTest look was tuned at.
# The character preset matches that look at any other width. If cm-scale
# clouds come out too thin, lower this; too thick, raise it.
REFERENCE_SIZE = 10.0

# density / step_size are the values at REFERENCE_SIZE; scale_with_size
# says whether they follow the container's width
PRESETS = {
    "character": {"density": 0.1, "step_size": 0.1, "scale_with_size": True},
    "small": {"density": 0.1, "step_size": 0.1, "scale_with_size": False},
}
DEFAULT_PRESET = "character"


def _get_meshes(geo=None):
    """Return a list of (transform, shape) for the given or selected meshes."""
    nodes = [geo] if geo else cmds.ls(selection=True, long=True)
    if not nodes:
        cmds.error("arnoldCloudSetup: select a mesh first.")
    # faces/verts still selected from modelling - use the object they belong to
    nodes = list(dict.fromkeys(node.split(".")[0] for node in nodes))
    result = []
    for node in nodes:
        if cmds.nodeType(node) == "mesh":
            result.append((cmds.listRelatives(node, parent=True, fullPath=True)[0], node))
            continue
        shapes = cmds.listRelatives(node, shapes=True, type="mesh",
                                    noIntermediate=True, fullPath=True)
        if shapes:
            result.append((node, shapes[0]))
    if not result:
        cmds.error("arnoldCloudSetup: nothing selected is a mesh.")
    return result


def _raise_volume_ray_depth():
    import mtoa.core
    mtoa.core.createOptions()
    attr = "defaultArnoldRenderOptions.GIVolumeDepth"
    if cmds.getAttr(attr) < VOLUME_RAY_DEPTH:
        cmds.setAttr(attr, VOLUME_RAY_DEPTH)
        print("arnoldCloudSetup: Render Settings > Ray Depth > Volume set to %d "
              "(brighter clouds, slower renders)." % VOLUME_RAY_DEPTH)


def _preset_values(preset, width):
    """Return (density, step_size) for a preset and container width."""
    settings = PRESETS[preset]
    density, step_size = settings["density"], settings["step_size"]
    if settings["scale_with_size"] and width > 0:
        factor = width / REFERENCE_SIZE
        density /= factor
        step_size *= factor
    return density, step_size


def _build_one(geo, shape, preset):
    short = geo.split("|")[-1]
    bb = cmds.exactWorldBoundingBox(geo)
    width = max(bb[3] - bb[0], bb[4] - bb[1], bb[5] - bb[2])
    density, step_size = _preset_values(preset, width)

    # mesh renders as a volume once step size is non-zero
    cmds.setAttr(shape + ".aiStepSize", step_size)

    volume = cmds.shadingNode("aiStandardVolume", asShader=True, name="%s_cloudVolume" % short)
    cmds.setAttr(volume + ".density", density)
    cmds.setAttr(volume + ".scatterColor", 1, 1, 1, type="double3")
    # scatter diffusion only exists from Arnold 7.3.3 (MtoA 5.4.5) - older
    # Maya 2025 installs don't have it, so skip it there rather than fail
    if cmds.attributeQuery("scatterDiffusionBias", node=volume, exists=True):
        cmds.setAttr(volume + ".scatterDiffusionBias", DIFFUSION_BIAS)
        cmds.setAttr(volume + ".scatterDiffusionRoughness", DIFFUSION_ROUGHNESS)
    else:
        print("arnoldCloudSetup: this Arnold has no Scatter Diffusion settings "
              "(needs MtoA 5.4.5+) - skipped; clouds will render a little darker.")

    engine = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name="%s_cloudSG" % short)
    cmds.connectAttr(volume + ".outColor", engine + ".volumeShader")
    cmds.sets(geo, edit=True, forceElement=engine)

    # Maya's Cloud 3D texture erodes the container into cloud shapes
    cloud = cmds.shadingNode("cloud", asTexture=True, name="%s_cloudTex" % short)
    cmds.setAttr(cloud + ".contrast", CLOUD_CONTRAST)
    cmds.setAttr(cloud + ".amplitude", CLOUD_AMPLITUDE)
    cmds.setAttr(cloud + ".transpRange", CLOUD_TRANSP_RANGE)
    cmds.setAttr(cloud + ".centerThresh", CLOUD_CENTER_THRESH)
    cmds.setAttr(cloud + ".edgeThresh", CLOUD_EDGE_THRESH)
    place = cmds.shadingNode("place3dTexture", asUtility=True, name="%s_cloudPlace" % short)
    cmds.connectAttr(place + ".worldInverseMatrix[0]", cloud + ".placementMatrix")
    cmds.connectAttr(cloud + ".outColor", volume + ".transparent")

    # centre the placement on the container, uniform scale relative to its
    # widest side - scale it up for bigger clouds
    cmds.xform(place, worldSpace=True, translation=(
        (bb[0] + bb[3]) / 2.0, (bb[1] + bb[4]) / 2.0, (bb[2] + bb[5]) / 2.0))
    size = width / 2.0 * PLACE_SCALE_RATIO
    cmds.xform(place, scale=(size, size, size))

    cmds.setAttr(geo + ".visibility", 1)
    return volume, cloud, place


def build(geo=None, preset=DEFAULT_PRESET):
    """Set up Arnold volume clouds on a mesh. Returns the aiStandardVolume nodes.

    preset: "character" (default, sized to the container) or "small"
    (the original fixed waveTest settings).
    """
    if preset not in PRESETS:
        cmds.error("arnoldCloudSetup: unknown preset %r - use one of: %s."
                   % (preset, ", ".join(sorted(PRESETS))))
    cmds.loadPlugin("mtoa", quiet=True)
    meshes = _get_meshes(geo)

    cmds.undoInfo(openChunk=True, chunkName="arnoldCloudSetup")
    try:
        volumes = []
        places = []
        for geo_, shape in meshes:
            volume, _, place = _build_one(geo_, shape, preset)
            volumes.append(volume)
            places.append(place)
        _raise_volume_ray_depth()
    finally:
        cmds.undoInfo(closeChunk=True)

    cmds.select(places)
    print("arnoldCloudSetup: built %s (%s preset). The cloud placement is selected - "
          "scale it to change cloud size; lower Density on the volume for wispier clouds."
          % (", ".join(volumes), preset))
    return volumes
