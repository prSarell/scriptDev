"""
arnoldSnowSetup.py

Slope-based landscape shading for Arnold (Maya 2025+, MtoA): Maya's Snow
3D texture drives the base colour of an aiStandardSurface, so upward-facing
faces get the "snow" colour and steep slopes get the "surface" colour.

    snow (3D texture) --> aiStandardSurface.baseColor
    place3dTexture       default (world up = Y)

Snow texture controls:
    threshold   - how steep a face can be and still catch snow
    depthDecay  - how sharply snow fades towards the slopes
    thickness   - how much snow there is overall

Usage (Script Editor, Python tab):
    import arnoldSnowSetup
    arnoldSnowSetup.build()                    # white snow on red rock
    arnoldSnowSetup.build(preset="desert")     # pale sand on red-orange rock
    arnoldSnowSetup.build("pPlane1_bossOcean") # or name one

Works on a BOSS Ocean graph too - select the bifrost graph, not the hidden plane.
"""
from maya import cmds

PRESETS = {
    # snow colour (flat faces), surface colour (slopes), roughness, diffuse roughness
    "snow": ((1.0, 1.0, 1.0), (0.5, 0.0, 0.0), 0.5, 0.2),
    "desert": ((0.85, 0.62, 0.42), (0.55, 0.2, 0.08), 0.7, 0.5),
}


def _get_shapes(geo=None):
    """Return the renderable shapes for the given or selected objects."""
    nodes = [geo] if geo else cmds.ls(selection=True, long=True)
    if not nodes:
        cmds.error("arnoldSnowSetup: select a landscape mesh first.")
    # listRelatives rejects the whole call if a type isn't registered, so only
    # look for Bifrost graphs when the bifrostGraph plug-in is loaded
    types = ["mesh"]
    if cmds.pluginInfo("bifrostGraph", query=True, loaded=True):
        types.append("bifrostGraphShape")
    shapes = []
    for node in nodes:
        if cmds.nodeType(node) in types:
            shapes.append(node)
            continue
        shapes += cmds.listRelatives(node, shapes=True, noIntermediate=True,
                                     fullPath=True, type=types) or []
    if not shapes:
        cmds.error("arnoldSnowSetup: nothing selected is a mesh or Bifrost graph.")
    return shapes


def build(geo=None, preset="snow"):
    """Assign a slope-based snow shader to a landscape. Returns the snow texture."""
    if preset not in PRESETS:
        cmds.error("arnoldSnowSetup: preset must be one of %s." % ", ".join(PRESETS))
    cmds.loadPlugin("mtoa", quiet=True)
    shapes = _get_shapes(geo)
    snow_rgb, surface_rgb, roughness, diffuse_roughness = PRESETS[preset]

    cmds.undoInfo(openChunk=True, chunkName="arnoldSnowSetup")
    try:
        surface = cmds.shadingNode("aiStandardSurface", asShader=True, name="%sLand_mtl" % preset)
        cmds.setAttr(surface + ".specularRoughness", roughness)
        cmds.setAttr(surface + ".diffuseRoughness", diffuse_roughness)

        engine = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name="%sLand_SG" % preset)
        cmds.connectAttr(surface + ".outColor", engine + ".surfaceShader")

        snow = cmds.shadingNode("snow", asTexture=True, name="%sLand_snowTex" % preset)
        place = cmds.shadingNode("place3dTexture", asUtility=True, name="%sLand_snowPlace" % preset)
        cmds.connectAttr(place + ".worldInverseMatrix[0]", snow + ".placementMatrix")
        cmds.setAttr(snow + ".snowColor", *snow_rgb, type="double3")
        cmds.setAttr(snow + ".surfaceColor", *surface_rgb, type="double3")
        cmds.connectAttr(snow + ".outColor", surface + ".baseColor")

        for shape in shapes:
            cmds.sets(shape, edit=True, forceElement=engine)
    finally:
        cmds.undoInfo(closeChunk=True)

    cmds.select(snow)
    print("arnoldSnowSetup: assigned %s to %d object(s). The Snow texture is selected - "
          "tweak Threshold / Depth Decay / Thickness in the Attribute Editor."
          % (surface, len(shapes)))
    return snow
