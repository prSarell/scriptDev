"""
arnoldCloudSetup.py

Turns the selected mesh(es) into an Arnold volume cloud container
(Maya 2025+, MtoA). Follows the classic "sphere + aiStandardVolume + Cloud
texture" setup:

    mesh shape            aiStepSize 0.1      (Arnold > Volume Attributes)
    aiStandardVolume  --> shading group .volumeShader
    cloud (3D texture) --> aiStandardVolume.transparent
    place3dTexture        uniform, ~0.15 of the container's widest half-size
                          (bigger = bigger clouds)
    Render Settings       Ray Depth > Volume raised to 6 (bright, scattered clouds)

Usage (Script Editor, Python tab):
    import arnoldCloudSetup
    arnoldCloudSetup.build()              # uses the selected mesh(es)
    arnoldCloudSetup.build("pSphere1")    # or name one

Defaults are the look tuned in waveTest (2026-10-26): density 0.1, low
contrast/amplitude Cloud texture, soft edge thresholds.

Tip: scale/flatten a sphere first - it's the container the clouds live in.
Scene scale matters a lot: a bigger container gives much better clouds.
Volumes are slow to render; test with a small render region.
"""
from maya import cmds

STEP_SIZE = 0.1
VOLUME_RAY_DEPTH = 6
DENSITY = 0.1
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


def _build_one(geo, shape):
    short = geo.split("|")[-1]

    # mesh renders as a volume once step size is non-zero
    cmds.setAttr(shape + ".aiStepSize", STEP_SIZE)

    volume = cmds.shadingNode("aiStandardVolume", asShader=True, name="%s_cloudVolume" % short)
    cmds.setAttr(volume + ".density", DENSITY)
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
    bb = cmds.exactWorldBoundingBox(geo)
    cmds.xform(place, worldSpace=True, translation=(
        (bb[0] + bb[3]) / 2.0, (bb[1] + bb[4]) / 2.0, (bb[2] + bb[5]) / 2.0))
    size = max(bb[3] - bb[0], bb[4] - bb[1], bb[5] - bb[2]) / 2.0 * PLACE_SCALE_RATIO
    cmds.xform(place, scale=(size, size, size))

    cmds.setAttr(geo + ".visibility", 1)
    return volume, cloud, place


def build(geo=None):
    """Set up Arnold volume clouds on a mesh. Returns the aiStandardVolume nodes."""
    cmds.loadPlugin("mtoa", quiet=True)
    meshes = _get_meshes(geo)

    cmds.undoInfo(openChunk=True, chunkName="arnoldCloudSetup")
    try:
        volumes = []
        places = []
        for geo_, shape in meshes:
            volume, _, place = _build_one(geo_, shape)
            volumes.append(volume)
            places.append(place)
        _raise_volume_ray_depth()
    finally:
        cmds.undoInfo(closeChunk=True)

    cmds.select(places)
    print("arnoldCloudSetup: built %s. The cloud placement is selected - scale it "
          "to change cloud size; lower Density on the volume for wispier clouds."
          % ", ".join(volumes))
    return volumes
