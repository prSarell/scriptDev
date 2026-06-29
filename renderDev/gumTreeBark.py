"""
Australian Gum Tree (Eucalyptus) Bark Shader
Hybrid procedural + texture-ready shader network for Arnold (aiStandardSurface).

Run in Maya Script Editor (Python tab) to build the full shader network.
Optional file texture nodes are created but disconnected — connect them
in Hypershade to override any procedural channel with photo textures.
"""

import maya.cmds as cmds


def create_gum_bark_shader():
    """Build the full gum tree bark shader network and assign to selection."""

    # ------------------------------------------------------------------ #
    # 1. Core shader
    # ------------------------------------------------------------------ #
    shader = cmds.shadingNode("aiStandardSurface", asShader=True,
                              name="gumBark_mtl")
    sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True,
                   name="gumBark_mtlSG")
    cmds.connectAttr(f"{shader}.outColor", f"{sg}.surfaceShader")

    cmds.setAttr(f"{shader}.specular", 0.15)
    cmds.setAttr(f"{shader}.specularRoughness", 0.75)

    # ------------------------------------------------------------------ #
    # 2. Bark / Peel mask  (fractal + noise blend)
    #    White = rough bark patches, Black = smooth peeled surface
    # ------------------------------------------------------------------ #
    mask_fractal = cmds.shadingNode("fractal", asTexture=True,
                                    name="gumBark_maskFractal")
    cmds.setAttr(f"{mask_fractal}.amplitude", 1.0)
    cmds.setAttr(f"{mask_fractal}.threshold", 0.35)
    cmds.setAttr(f"{mask_fractal}.ratio", 0.65)
    cmds.setAttr(f"{mask_fractal}.frequencyRatio", 2.5)

    mask_noise = cmds.shadingNode("noise", asTexture=True,
                                  name="gumBark_maskNoise")
    cmds.setAttr(f"{mask_noise}.amplitude", 0.8)
    cmds.setAttr(f"{mask_noise}.frequency", 8.0)
    cmds.setAttr(f"{mask_noise}.noiseType", 4)  # Wispy

    mask_blend = cmds.shadingNode("blendColors", asUtility=True,
                                  name="gumBark_maskBlend")
    cmds.connectAttr(f"{mask_fractal}.outColor", f"{mask_blend}.color1")
    cmds.connectAttr(f"{mask_noise}.outColor", f"{mask_blend}.color2")
    cmds.setAttr(f"{mask_blend}.blender", 0.5)

    mask_ramp = cmds.shadingNode("ramp", asTexture=True,
                                 name="gumBark_maskContrast")
    cmds.setAttr(f"{mask_ramp}.interpolation", 4)  # Smooth
    cmds.removeMultiInstance(f"{mask_ramp}.colorEntryList[2]", b=True)
    cmds.setAttr(f"{mask_ramp}.colorEntryList[0].color", 0, 0, 0, type="double3")
    cmds.setAttr(f"{mask_ramp}.colorEntryList[0].position", 0.4)
    cmds.setAttr(f"{mask_ramp}.colorEntryList[1].color", 1, 1, 1, type="double3")
    cmds.setAttr(f"{mask_ramp}.colorEntryList[1].position", 0.6)
    cmds.setAttr(f"{mask_ramp}.type", 0)  # U Ramp — driven by input
    cmds.connectAttr(f"{mask_blend}.outputR", f"{mask_ramp}.uvCoord.uCoord")
    cmds.connectAttr(f"{mask_blend}.outputR", f"{mask_ramp}.uvCoord.vCoord")

    # ------------------------------------------------------------------ #
    # 3. Base color — two colour layers mixed by mask
    # ------------------------------------------------------------------ #
    # Smooth peeled layer: warm cream / pale pink tones
    col_smooth = cmds.shadingNode("noise", asTexture=True,
                                   name="gumBark_colSmooth")
    cmds.setAttr(f"{col_smooth}.colorGain", 0.82, 0.72, 0.58, type="double3")
    cmds.setAttr(f"{col_smooth}.colorOffset", 0.18, 0.14, 0.10, type="double3")
    cmds.setAttr(f"{col_smooth}.amplitude", 0.3)
    cmds.setAttr(f"{col_smooth}.frequency", 12.0)
    cmds.setAttr(f"{col_smooth}.noiseType", 3)  # Perlin

    # Rough bark layer: grey-brown tones
    col_bark = cmds.shadingNode("fractal", asTexture=True,
                                 name="gumBark_colBark")
    cmds.setAttr(f"{col_bark}.colorGain", 0.35, 0.30, 0.24, type="double3")
    cmds.setAttr(f"{col_bark}.colorOffset", 0.12, 0.10, 0.08, type="double3")
    cmds.setAttr(f"{col_bark}.amplitude", 0.6)
    cmds.setAttr(f"{col_bark}.ratio", 0.7)
    cmds.setAttr(f"{col_bark}.frequencyRatio", 2.2)

    col_blend = cmds.shadingNode("blendColors", asUtility=True,
                                  name="gumBark_colBlend")
    cmds.connectAttr(f"{col_bark}.outColor", f"{col_blend}.color1")
    cmds.connectAttr(f"{col_smooth}.outColor", f"{col_blend}.color2")
    cmds.connectAttr(f"{mask_ramp}.outColorR", f"{col_blend}.blender")

    cmds.connectAttr(f"{col_blend}.output", f"{shader}.baseColor")

    # ------------------------------------------------------------------ #
    # 4. Roughness — bark is rougher, peeled areas are smoother
    # ------------------------------------------------------------------ #
    rough_remap = cmds.shadingNode("remapValue", asUtility=True,
                                   name="gumBark_roughRemap")
    cmds.connectAttr(f"{mask_ramp}.outColorR", f"{rough_remap}.inputValue")
    cmds.setAttr(f"{rough_remap}.inputMin", 0)
    cmds.setAttr(f"{rough_remap}.inputMax", 1)
    cmds.setAttr(f"{rough_remap}.outputMin", 0.45)  # smooth peeled
    cmds.setAttr(f"{rough_remap}.outputMax", 0.9)   # rough bark
    cmds.connectAttr(f"{rough_remap}.outValue",
                     f"{shader}.specularRoughness", force=True)

    # ------------------------------------------------------------------ #
    # 5. Bump — layered procedural displacement
    # ------------------------------------------------------------------ #
    # Fine bark grain
    bump_fine = cmds.shadingNode("noise", asTexture=True,
                                 name="gumBark_bumpFine")
    cmds.setAttr(f"{bump_fine}.amplitude", 0.6)
    cmds.setAttr(f"{bump_fine}.frequency", 40.0)
    cmds.setAttr(f"{bump_fine}.noiseType", 4)  # Wispy

    # Broad undulation
    bump_broad = cmds.shadingNode("fractal", asTexture=True,
                                   name="gumBark_bumpBroad")
    cmds.setAttr(f"{bump_broad}.amplitude", 0.8)
    cmds.setAttr(f"{bump_broad}.ratio", 0.5)
    cmds.setAttr(f"{bump_broad}.frequencyRatio", 2.0)

    bump_blend = cmds.shadingNode("blendColors", asUtility=True,
                                   name="gumBark_bumpBlend")
    cmds.connectAttr(f"{bump_fine}.outColor", f"{bump_blend}.color1")
    cmds.connectAttr(f"{bump_broad}.outColor", f"{bump_blend}.color2")
    cmds.connectAttr(f"{mask_ramp}.outColorR", f"{bump_blend}.blender")

    bump2d = cmds.shadingNode("bump2d", asUtility=True,
                               name="gumBark_bump2d")
    cmds.setAttr(f"{bump2d}.bumpDepth", 0.15)
    cmds.connectAttr(f"{bump_blend}.outputR", f"{bump2d}.bumpValue")
    cmds.connectAttr(f"{bump2d}.outNormal", f"{shader}.normalCamera")

    # ------------------------------------------------------------------ #
    # 6. Optional file texture slots (disconnected — ready to override)
    # ------------------------------------------------------------------ #
    file_diffuse = cmds.shadingNode("file", asTexture=True,
                                     name="gumBark_fileDiffuse")
    p2d_diff = cmds.shadingNode("place2dTexture", asUtility=True,
                                 name="gumBark_p2d_diffuse")
    _connect_place2d(p2d_diff, file_diffuse)

    file_bump = cmds.shadingNode("file", asTexture=True,
                                  name="gumBark_fileBump")
    p2d_bump = cmds.shadingNode("place2dTexture", asUtility=True,
                                 name="gumBark_p2d_bump")
    _connect_place2d(p2d_bump, file_bump)

    file_rough = cmds.shadingNode("file", asTexture=True,
                                   name="gumBark_fileRoughness")
    cmds.setAttr(f"{file_rough}.colorSpace", "Raw", type="string")
    p2d_rough = cmds.shadingNode("place2dTexture", asUtility=True,
                                  name="gumBark_p2d_roughness")
    _connect_place2d(p2d_rough, file_rough)

    file_normal = cmds.shadingNode("file", asTexture=True,
                                    name="gumBark_fileNormal")
    cmds.setAttr(f"{file_normal}.colorSpace", "Raw", type="string")
    p2d_normal = cmds.shadingNode("place2dTexture", asUtility=True,
                                   name="gumBark_p2d_normal")
    _connect_place2d(p2d_normal, file_normal)

    normal_map = cmds.shadingNode("aiNormalMap", asUtility=True,
                                   name="gumBark_aiNormalMap")
    cmds.setAttr(f"{normal_map}.strength", 1.0)
    cmds.connectAttr(f"{file_normal}.outColor", f"{normal_map}.input")
    cmds.connectAttr(f"{normal_map}.outValue", f"{bump2d}.normalCamera")

    # ------------------------------------------------------------------ #
    # 7. Assign to selection
    # ------------------------------------------------------------------ #
    sel = cmds.ls(selection=True)
    if sel:
        cmds.sets(sel, edit=True, forceElement=sg)
        cmds.inViewMessage(
            amg="<hl>gumBark_mtl</hl> assigned to selection.",
            pos="topCenter", fade=True)
    else:
        cmds.inViewMessage(
            amg="<hl>gumBark_mtl</hl> created — select geometry and "
                "RMB-assign in Hypershade.",
            pos="topCenter", fade=True)

    cmds.select(shader, replace=True)
    print(f"[gumTreeBark] Shader network created: {shader}")
    print("[gumTreeBark] File texture nodes ready (disconnected):")
    print(f"  Diffuse : {file_diffuse}")
    print(f"  Bump    : {file_bump}")
    print(f"  Normal  : {file_normal}  ->  {normal_map}")
    print(f"  Rough   : {file_rough}")
    print("[gumTreeBark] To use photo textures, load images into the file")
    print("  nodes above and connect them in Hypershade to override the")
    print("  procedural channels.")

    return shader


def _connect_place2d(p2d, file_node):
    """Wire a place2dTexture to a file node."""
    pairs = [
        ("coverage", "coverage"),
        ("translateFrame", "translateFrame"),
        ("rotateFrame", "rotateFrame"),
        ("mirrorU", "mirrorU"),
        ("mirrorV", "mirrorV"),
        ("stagger", "stagger"),
        ("wrapU", "wrapU"),
        ("wrapV", "wrapV"),
        ("repeatUV", "repeatUV"),
        ("offset", "offset"),
        ("rotateUV", "rotateUV"),
        ("noiseUV", "noiseUV"),
        ("vertexUvOne", "vertexUvOne"),
        ("vertexUvTwo", "vertexUvTwo"),
        ("vertexUvThree", "vertexUvThree"),
        ("vertexCameraOne", "vertexCameraOne"),
        ("outUV", "uv"),
        ("outUvFilterSize", "uvFilterSize"),
    ]
    for src, dst in pairs:
        cmds.connectAttr(f"{p2d}.{src}", f"{file_node}.{dst}", force=True)


if __name__ == "__main__":
    create_gum_bark_shader()
