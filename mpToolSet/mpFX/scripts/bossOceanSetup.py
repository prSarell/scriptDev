"""
bossOceanSetup.py

Builds a Bifrost BOSS spectral-wave ocean on the selected mesh (Maya 2025+,
Bifrost 2.9+). Replaces the old Maya 2020 Bifrost > Boss menu workflow.

Graph built:
    input mesh --> displace_by_wave.geometry
               --> create_spectral_waves.bounds_geometry  (ocean sized to the mesh)
    create_spectral_waves.out_wave --> displace_by_wave.waves
    displace_by_wave.out_geometry --> output

Usage (Script Editor, Python tab):
    import bossOceanSetup
    bossOceanSetup.build()            # uses the selected mesh
    bossOceanSetup.build("pPlane1")   # or name one

The source mesh is hidden; the Bifrost graph shows the displaced result.
Give the mesh plenty of subdivisions - the waves can only move existing points.

Freeze a frame as a static Maya mesh (e.g. to use as terrain):
    bossOceanSetup.freeze()           # selected ocean graph, current frame
"""
from maya import cmds

WAVES_NODE = "BifrostGraph,Simulation::BOSS,create_spectral_waves"
DISPLACE_NODE = "BifrostGraph,Simulation::BOSS,displace_by_wave"
BOUNDS_FROM_GEOMETRY = "2"  # Simulation::BOSS::BoundsMethod enum


def _get_mesh(geo=None):
    """Return (transform, shape) for the given or selected mesh."""
    if geo is None:
        sel = cmds.ls(selection=True, long=True)
        if not sel:
            cmds.error("bossOceanSetup: select a mesh first.")
        geo = sel[0]
    if cmds.nodeType(geo) == "mesh":
        shape = geo
        geo = cmds.listRelatives(shape, parent=True, fullPath=True)[0]
    else:
        shapes = cmds.listRelatives(geo, shapes=True, type="mesh",
                                    noIntermediate=True, fullPath=True)
        if not shapes:
            cmds.error("bossOceanSetup: %s is not a mesh." % geo)
        shape = shapes[0]
    return geo, shape


def build(geo=None):
    """Build the BOSS ocean graph on a mesh. Returns the bifrostGraphShape."""
    cmds.loadPlugin("bifrostGraph", quiet=True)
    geo, shape = _get_mesh(geo)
    short = geo.split("|")[-1]

    cmds.undoInfo(openChunk=True, chunkName="bossOceanSetup")
    try:
        graph = cmds.createNode("bifrostGraphShape", name="%s_bossOceanShape" % short)
        cmds.rename(cmds.listRelatives(graph, parent=True)[0], "%s_bossOcean" % short)

        # Maya mesh into the graph
        cmds.vnnNode(graph, "/input", createOutputPort=("inMesh", "Object"))
        cmds.connectAttr(shape + ".worldMesh[0]", graph + ".inMesh")

        waves = cmds.vnnCompound(graph, "/", addNode=WAVES_NODE)[0]
        displace = cmds.vnnCompound(graph, "/", addNode=DISPLACE_NODE)[0]

        # size the ocean patch to the mesh
        cmds.vnnNode(graph, "/" + waves, setPortDefaultValues=("bounds_method", BOUNDS_FROM_GEOMETRY))
        cmds.vnnConnect(graph, "/input.inMesh", "/%s.bounds_geometry" % waves)

        cmds.vnnConnect(graph, "/input.inMesh", "/%s.geometry" % displace)

        # waves is a fan-in port: its sub-port has to exist before connecting
        cmds.vnnNode(graph, "/" + displace, createInputPort=("waves.out_wave", "array<Object>"))
        cmds.vnnConnect(graph, "/%s.out_wave" % waves, "/%s.waves.out_wave" % displace)

        cmds.vnnNode(graph, "/output", createInputPort=("outMesh", "Object"))
        cmds.vnnConnect(graph, "/%s.out_geometry" % displace, "/output.outMesh")

        # carry the source material over, then hide the source
        engines = cmds.listConnections(shape, type="shadingEngine") or ["initialShadingGroup"]
        cmds.sets(graph, edit=True, forceElement=engines[0])
        cmds.setAttr(geo + ".visibility", 0)
    finally:
        cmds.undoInfo(closeChunk=True)

    cmds.select(graph)
    print("bossOceanSetup: built %s on %s - open the Bifrost Graph Editor to "
          "tweak Wind / wave_height on create_spectral_waves." % (graph, short))
    return graph


def _get_graph(graph=None):
    """Return the bifrostGraphShape for the given or selected ocean."""
    nodes = [graph] if graph else cmds.ls(selection=True, long=True)
    for node in nodes:
        if cmds.nodeType(node) == "bifrostGraphShape":
            return node
        shapes = cmds.listRelatives(node, shapes=True, type="bifrostGraphShape", fullPath=True)
        if shapes:
            return shapes[0]
    cmds.error("bossOceanSetup: select a BOSS Ocean (the bifrost graph) first.")


def freeze(graph=None):
    """Copy the ocean at the current frame into a static Maya mesh. Returns its transform."""
    graph = _get_graph(graph)
    if not cmds.attributeQuery("outMesh", node=graph, exists=True):
        cmds.error("bossOceanSetup: %s has no outMesh - was it built with this tool?" % graph)
    frame = int(round(cmds.currentTime(query=True)))
    short = cmds.listRelatives(graph, parent=True)[0].replace("_bossOcean", "")

    cmds.undoInfo(openChunk=True, chunkName="bossOceanFreeze")
    try:
        # Bifrost geometry needs converting before a Maya mesh can take it
        convert = cmds.createNode("bifrostGeoToMaya")
        cmds.connectAttr(graph + ".outMesh", convert + ".bifrostGeo")
        live = cmds.createNode("mesh")
        cmds.connectAttr(convert + ".mayaMesh[0]", live + ".inMesh")
        live_xform = cmds.listRelatives(live, parent=True)[0]

        # a duplicate has no incoming connections, so it stays at this frame
        frozen = cmds.duplicate(live_xform, name="%s_frozen_f%d" % (short, frame))[0]
        cmds.delete(live_xform, convert)

        engines = cmds.listConnections(graph, type="shadingEngine") or ["initialShadingGroup"]
        cmds.sets(frozen, edit=True, forceElement=engines[0])
    finally:
        cmds.undoInfo(closeChunk=True)

    cmds.select(frozen)
    print("bossOceanSetup: froze frame %d of %s as %s. Hide the ocean graph to see it."
          % (frame, graph, frozen))
    return frozen
