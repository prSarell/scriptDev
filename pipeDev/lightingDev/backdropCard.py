"""
backdropCard.py: turn a free image plane into a renderable backdrop card
(mpLighting shelf; user, 2026-11-19: "select an image plane and run this
tool and have the imagePlane converted to a single polygon plane with the
imageplane image as a texture ... renderable with Arnold, visible without
casting shadows or ambient occlusion ... exactly as the free imageplane
does but now it can show up in a render").

What a free image plane draws (checked in the Maya 2025 viewport): its
image stretched over width x height, facing the transform's +Z, both
sides. Coverage crops the image (origin from the bottom-left). Fit,
offset, rotate and squeeze do nothing on a free plane. A non-zero
imageCenter moves it, but not as a plain offset; the plane's bounding box
(filled in by the viewport) says where it really is.

The card:
    - a one-face polygon under the image plane's transform, so it follows
      the plane's animation and parenting. Width and height stay
      connected to the image plane; an image sequence's frame follows
      whatever drives the plane's frame. The image file, colour/alpha gain
      and centre are copied when the tool runs (Arnold misreads gains
      connected from an image plane): run it again after changing them.
    - an unlit surfaceShader fed by a file texture: what you see in the
      viewport is what Arnold renders, lights don't touch it. Transparent
      where the image has alpha (display mode RGBA).
    - visible to the camera only: no shadows, not in reflections,
      refractions, GI or volumes, so it can't change the shot's lighting.
The image plane is hidden, not deleted. Running the tool again on the
image plane (or its card) rebuilds the card.

An image from outside the Maya project the artist is working in (user,
2026-11-19: "if the image from the imageplane is from another project can
the tool copy a version of the file to the appropriate folder in the
project") is copied into the project's sourceimages\\backdrops\\ (every
frame of a sequence), and the image plane and card point at the copy.
A copy that's already there and identical is reused; a different file
with the same name gets _v002, _v003 ... so nothing is overwritten.

    import backdropCard; backdropCard.convert()
"""

import os
import re
import glob
import shutil
import filecmp

import maya.cmds as cmds

SUFFIX = "_backdrop"
LINK = "backdropCard"          # message attr on the image plane -> its card
MOVIE = 2                       # imagePlane.type: Image File, Texture, Movie
TEXTURE = 1
RGBA = 3                        # imagePlane.displayMode
# Maya and Arnold render flags on the card: camera rays only.
FLAGS = {"castsShadows": 0, "receiveShadows": 0, "motionBlur": 0, "primaryVisibility": 1,
         "visibleInReflections": 0, "visibleInRefractions": 0, "doubleSided": 1,
         "aiVisibleInDiffuseReflection": 0, "aiVisibleInSpecularReflection": 0,
         "aiVisibleInDiffuseTransmission": 0, "aiVisibleInSpecularTransmission": 0,
         "aiVisibleInVolume": 0, "aiSelfShadows": 0, "aiMatte": 0}
# Image plane attribute -> file texture attribute, copied. Not connected:
# Arnold misreads a file node's gain/offset when they come from an image
# plane (an opaque red rendered 27% too bright, an RGBA one 30% too dark).
FOLDER = "backdrops"            # under the project's sourceimages
FRAME = re.compile(r"^(.*?)(\d+)(\.[^.]+)$")      # name.0001.png -> name. 0001 .png
COPIED = (("imageName", "fileTextureName"), ("useFrameExtension", "useFrameExtension"),
          ("frameExtension", "frameExtension"), ("frameOffset", "frameOffset"),
          ("colorGain", "colorGain"), ("colorOffset", "colorOffset"), ("alphaGain", "alphaGain"))


class CardError(Exception):
    pass


def _image_plane(node):
    """The imagePlane shape for a selected image plane, its transform or
    its card; None for anything else."""
    if cmds.nodeType(node) == "imagePlane":
        return cmds.ls(node, long=True)[0]
    if cmds.objExists(node + ".backdropSource"):
        src = cmds.listConnections(node + ".backdropSource", source=True, destination=False,
                                   shapes=True) or []
        return cmds.ls(src[0], long=True)[0] if src else None
    shapes = cmds.listRelatives(node, shapes=True, type="imagePlane", fullPath=True) or []
    return shapes[0] if shapes else None


def _check(ip):
    """Refuse an image plane the card can't stand in for."""
    name = ip.split("|")[-1]
    cam = (cmds.imagePlane(ip, q=True, camera=True) or [""])[0]
    if cam:
        raise CardError("%s is attached to camera %s. Backdrop cards are made from free "
                        "image planes only." % (name, cam))
    if cmds.getAttr(ip + ".type") == MOVIE:
        raise CardError("%s shows a movie file, which a texture can't read. Use an image "
                        "sequence on the image plane instead, then convert it." % name)
    if cmds.getAttr(ip + ".type") != TEXTURE and not cmds.getAttr(ip + ".imageName"):
        raise CardError("%s has no image." % name)


def _drawn_centre(ip):
    """Where the viewport draws the image plane's centre, in its transform's
    space. A non-zero imageCenter isn't a plain offset (the transform's own
    rotation and scale bend it), but the plane's bounding box holds the
    drawn result. The box is only filled in by a viewport draw, so the plane
    is shown and the viewport refreshed first. Baked, not connected: a batch
    render has no viewport to fill the box."""
    centre = cmds.getAttr(ip + ".imageCenter")[0]
    if not any(abs(v) > 1e-6 for v in centre):
        return (0.0, 0.0, 0.0)
    hidden = not cmds.getAttr(ip + ".visibility")
    if hidden:
        cmds.setAttr(ip + ".visibility", 1)
    try:
        cmds.refresh(force=True)
    except RuntimeError:
        pass
    lo, hi = cmds.getAttr(ip + ".boundingBoxMin")[0], cmds.getAttr(ip + ".boundingBoxMax")[0]
    if hidden:
        cmds.setAttr(ip + ".visibility", 0)
    if not any(abs(a - b) > 1e-6 for a, b in zip(lo, hi)):
        raise CardError("%s has its Image Center moved, and Maya only says where that puts "
                        "the plane once a viewport draws it. Run this in interactive Maya (not "
                        "batch), or set Image Center to 0 and move the image plane "
                        "itself." % ip.split("|")[-1])
    return tuple((a + b) / 2.0 for a, b in zip(lo, hi))


def _norm(path):
    return os.path.normcase(os.path.normpath(os.path.abspath(path)))


def _frames(path, sequence):
    """The files to copy: the image, or every frame of its sequence."""
    m = FRAME.match(os.path.basename(path)) if sequence else None
    if not m:
        return [path]
    pre, digits, ext = m.groups()
    pattern = os.path.join(glob.escape(os.path.dirname(path)), glob.escape(pre) + "[0-9]" * len(digits)
                           + glob.escape(ext))
    return sorted(glob.glob(pattern)) or [path]


def _same(files, dest_dir, rename):
    """True when every file is already in dest_dir (renamed) and identical."""
    return all(os.path.isfile(os.path.join(dest_dir, rename(f)))
               and filecmp.cmp(f, os.path.join(dest_dir, rename(f)), shallow=False)
               for f in files)


def _project_image(ip):
    """The image plane's image inside the current Maya project: unchanged if
    it is already in the project, else a copy in sourceimages\\backdrops\\
    (all frames of a sequence) that the image plane is pointed at. Returns
    the path the texture should use."""
    name = cmds.getAttr(ip + ".imageName")
    if cmds.getAttr(ip + ".type") == TEXTURE or not name:
        return name
    root = cmds.workspace(query=True, rootDirectory=True) or ""
    path = cmds.workspace(expandName=name) if not os.path.isabs(name) else name
    if not root or _norm(path).startswith(_norm(root).rstrip("\\/") + os.sep):
        return name                                   # already in the project
    if not os.path.isfile(path):
        raise CardError("%s's image wasn't found, so it couldn't be copied into this project: "
                        "%s" % (ip.split("|")[-1], path))
    files = _frames(path, cmds.getAttr(ip + ".useFrameExtension"))
    rule = cmds.workspace(fileRuleEntry="sourceImages") or "sourceimages"
    dest_dir = os.path.join(root, rule, FOLDER)

    m = FRAME.match(os.path.basename(path)) if len(files) > 1 else None
    stem, ext = (m.group(1), None) if m else os.path.splitext(os.path.basename(path))
    version = 1
    while True:
        tag = "" if version == 1 else "_v%03d" % version
        if m:      # sky.0001.png -> sky_v002.0001.png (keep the frame numbers)
            pre = stem.rstrip("._")
            sep = stem[len(pre):]
            rename = lambda f, t=tag: pre + t + sep + os.path.basename(f)[len(stem):]
        else:
            rename = lambda f, t=tag: stem + t + ext
        clash = [f for f in files if os.path.exists(os.path.join(dest_dir, rename(f)))]
        if not clash or _same(files, dest_dir, rename):
            break
        version += 1
    if not os.path.isdir(dest_dir):
        os.makedirs(dest_dir)
    made = 0
    for f in files:
        dest = os.path.join(dest_dir, rename(f))
        if not os.path.isfile(dest):
            shutil.copy2(f, dest)
            made += 1
    new = os.path.join(dest_dir, rename(path)).replace("\\", "/")
    cmds.setAttr(ip + ".imageName", new, type="string")
    print("Backdrop Card: %s's image was outside this project; %s %s"
          % (ip.split("|")[-1], "copied %d file(s) to" % made if made else "using the copy already in",
             dest_dir.replace("\\", "/")))
    return new


def _remove_card(ip):
    """Delete the card (and its shading network) a previous run made."""
    if not cmds.objExists(ip + "." + LINK):
        return
    for card in cmds.listConnections(ip + "." + LINK, source=False, destination=True) or []:
        shading = []
        for attr in ("backdropShader", "backdropFile", "backdropPlace", "backdropSG"):
            if cmds.objExists("%s.%s" % (card, attr)):
                shading += cmds.listConnections("%s.%s" % (card, attr), source=True,
                                                destination=False) or []
        cmds.delete([card] + [n for n in shading if cmds.objExists(n)])


def _tag(node, attr, target):
    """Record target on node with a message connection (to find it again)."""
    if not cmds.objExists("%s.%s" % (node, attr)):
        cmds.addAttr(node, longName=attr, attributeType="message")
    cmds.connectAttr(target + ".message", "%s.%s" % (node, attr), force=True)


def _shading(ip, base):
    """surfaceShader <- file (or the image plane's texture). Returns (shading
    group, shader, file, place2d); file and place2d are None for a texture."""
    shader = cmds.shadingNode("surfaceShader", asShader=True, name=base + "_SS")
    sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=base + "_SG")
    cmds.connectAttr(shader + ".outColor", sg + ".surfaceShader")
    alpha = cmds.getAttr(ip + ".displayMode") == RGBA
    if cmds.getAttr(ip + ".type") == TEXTURE:
        src = cmds.listConnections(ip + ".sourceTexture", source=True, destination=False) or []
        if not src:
            raise CardError("%s is set to Texture but has no texture connected."
                            % ip.split("|")[-1])
        cmds.connectAttr(src[0] + ".outColor", shader + ".outColor")
        if alpha and cmds.objExists(src[0] + ".outTransparency"):
            cmds.connectAttr(src[0] + ".outTransparency", shader + ".outTransparency")
        return sg, shader, None, None

    tex = cmds.shadingNode("file", asTexture=True, isColorManaged=True, name=base + "_file")
    place = cmds.shadingNode("place2dTexture", asUtility=True, name=base + "_place2d")
    cmds.connectAttr(place + ".outUV", tex + ".uvCoord")
    cmds.connectAttr(place + ".outUvFilterSize", tex + ".uvFilterSize")
    for src, dst in COPIED:
        value = cmds.getAttr("%s.%s" % (ip, src))
        if isinstance(value, list):                  # a colour: [(r, g, b)]
            cmds.setAttr("%s.%s" % (tex, dst), *value[0], type="double3")
        elif isinstance(value, str):
            cmds.setAttr("%s.%s" % (tex, dst), value, type="string")
        else:
            cmds.setAttr("%s.%s" % (tex, dst), value)
    # An image sequence: drive the texture's frame from whatever drives the
    # image plane's (its expression or keys), so they stay in step.
    driver = cmds.listConnections(ip + ".frameExtension", source=True, destination=False,
                                  plugs=True, skipConversionNodes=True) or []
    if driver:
        cmds.connectAttr(driver[0], tex + ".frameExtension", force=True)
    cmds.setAttr(tex + ".colorSpace", cmds.getAttr(ip + ".colorSpace"), type="string")
    cmds.setAttr(tex + ".ignoreColorSpaceFileRules", 1)
    cmds.setAttr(tex + ".filterType", 0)        # no blur: a backdrop should stay sharp

    # Coverage crops the image; its origin counts from the bottom-left.
    w, h = cmds.getAttr(ip + ".outputImageWidth"), cmds.getAttr(ip + ".outputImageHeight")
    if w and h:
        cx, cy = cmds.getAttr(ip + ".coverageX"), cmds.getAttr(ip + ".coverageY")
        ox, oy = cmds.getAttr(ip + ".coverageOriginX"), cmds.getAttr(ip + ".coverageOriginY")
        if (cx, cy) != (w, h) and cx > 0 and cy > 0:
            cmds.setAttr(place + ".repeatU", float(cx) / w)
            cmds.setAttr(place + ".repeatV", float(cy) / h)
            cmds.setAttr(place + ".offsetU", float(ox) / w)
            cmds.setAttr(place + ".offsetV", float(oy) / h)

    cmds.connectAttr(tex + ".outColor", shader + ".outColor")
    if alpha:
        cmds.connectAttr(tex + ".outTransparency", shader + ".outTransparency")
    return sg, shader, tex, place


def convert_one(ip):
    """Make (or remake) the backdrop card for one free imagePlane shape.
    Returns the card's transform."""
    _check(ip)
    centre = _drawn_centre(ip)            # can refuse: before anything is made
    _project_image(ip)                    # an image from another project: copy it in
    xf = cmds.listRelatives(ip, parent=True, fullPath=True)[0]
    base = xf.split("|")[-1].split(":")[-1] + SUFFIX
    _remove_card(ip)

    card, poly = cmds.polyPlane(name=base, axis=(0, 0, 1), subdivisionsX=1, subdivisionsY=1,
                                width=cmds.getAttr(ip + ".width"),
                                height=cmds.getAttr(ip + ".height"))
    card = cmds.parent(card, xf, relative=True)[0]
    card = cmds.ls(card, long=True)[0]
    shape = cmds.listRelatives(card, shapes=True, fullPath=True)[0]
    # follow the image plane's size; sit where the viewport draws it
    cmds.connectAttr(ip + ".width", poly + ".width")
    cmds.connectAttr(ip + ".height", poly + ".height")
    cmds.setAttr(card + ".translate", *centre, type="double3")
    poly = cmds.rename(poly, base + "_shape")

    sg, shader, tex, place = _shading(ip, base)
    cmds.sets(shape, edit=True, forceElement=sg)
    alpha = cmds.getAttr(ip + ".displayMode") == RGBA
    for a, v in dict(FLAGS, aiOpaque=0 if alpha else 1).items():
        if cmds.objExists("%s.%s" % (shape, a)):
            try:
                cmds.setAttr("%s.%s" % (shape, a), v)
            except RuntimeError:
                pass

    _tag(card, "backdropSource", ip)
    _tag(card, "backdropSG", sg)
    _tag(card, "backdropShader", shader)
    for attr, node in (("backdropFile", tex), ("backdropPlace", place)):
        if node:
            _tag(card, attr, node)
    if not cmds.objExists(ip + "." + LINK):
        cmds.addAttr(ip, longName=LINK, attributeType="message")
    cmds.addAttr(card, longName="backdropOf", attributeType="message")
    cmds.connectAttr(ip + "." + LINK, card + ".backdropOf")
    cmds.setAttr(ip + ".visibility", 0)         # the card replaces it on screen
    return card


def _load_arnold():
    if not cmds.pluginInfo("mtoa", q=True, loaded=True):
        try:
            cmds.loadPlugin("mtoa", quiet=True)
        except RuntimeError:
            pass        # the card still works; only the Arnold flags are skipped


def convert(nodes=None):
    """Convert the selected (or given) free image planes. Returns the cards.
    One undo."""
    nodes = cmds.ls(selection=True, long=True) if nodes is None else nodes
    planes = []
    for n in nodes or []:
        ip = _image_plane(n)
        if ip and ip not in planes:
            planes.append(ip)
    if not planes:
        cmds.warning("Backdrop Card: select a free image plane first.")
        return []
    _load_arnold()
    cards, problems = [], []
    cmds.undoInfo(openChunk=True, chunkName="Backdrop Card")
    try:
        for ip in planes:
            try:
                cards.append(convert_one(ip))
            except CardError as e:
                problems.append(str(e))
    finally:
        cmds.undoInfo(closeChunk=True)
    if cards:
        cmds.select(cards)
        print("Backdrop Card: made %s. The image plane is hidden; unhide its shape to get "
              "it back." % ", ".join(c.split("|")[-1] for c in cards))
    for p in problems:
        cmds.warning("Backdrop Card: " + p)
    return cards
