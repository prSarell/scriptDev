# Backdrop Card (user, 2026-11-19): a free image plane becomes a renderable,
# camera-only card with the same image, size and place.
# The viewport match (card vs image plane, pixel for pixel) and the Arnold
# checks (true colours, unlit, no shadow/reflection) need a GUI and a render
# licence, so they were run by hand; this covers the rest.
# Run: mayapy test_backdropCard_mayapy.py
import sys, os, shutil, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import maya.standalone; maya.standalone.initialize()
import maya.cmds as cmds
import backdropCard as bc
ok = []
def check(label, cond): ok.append(bool(cond)); print("PASS" if cond else "FAIL", label)
def close(a, b, tol=1e-4): return all(abs(x - y) < tol for x, y in zip(a, b))

tmp = tempfile.mkdtemp(prefix="bdc_test_")
from PySide6 import QtGui
app = QtGui.QGuiApplication.instance() or QtGui.QGuiApplication([])
# a Maya project of its own (the tool copies images from other projects into it)
proj = os.path.join(tmp, "shotProj").replace("\\", "/")
os.makedirs(os.path.join(proj, "sourceimages"))
with open(os.path.join(proj, "workspace.mel"), "w") as f:
    f.write('workspace -fr "sourceImages" "sourceimages";\n')
cmds.workspace(proj, openWorkspace=True)
def make_image(path, colour):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img = QtGui.QImage(400, 200, QtGui.QImage.Format.Format_ARGB32); img.fill(QtGui.QColor(*colour))
    img.save(path); return path.replace("\\", "/")
sky = make_image(os.path.join(proj, "sourceimages", "sky.png"), (90, 140, 220))   # in the project
cmds.loadPlugin("mtoa", quiet=True)

# --- a plain free image plane, moved and stretched ----------------------------
cmds.file(new=True, force=True)
grp = cmds.group(empty=True, name="skyGrp"); cmds.xform(grp, t=(0, 2, -10), ro=(0, 15, 0))
xf, ip = cmds.imagePlane(fileName=sky)
xf = cmds.rename(cmds.parent(xf, grp)[0], "skyPlane")
ip = cmds.listRelatives(xf, shapes=True, fullPath=True)[0]
cmds.setAttr(ip + ".maintainRatio", 0); cmds.setAttr(ip + ".width", 30); cmds.setAttr(ip + ".height", 12)
cmds.setAttr(ip + ".colorSpace", "Raw", type="string")
cmds.setAttr(ip + ".colorGain", 0.9, 0.8, 0.7, type="double3")
cmds.setAttr(ip + ".coverageX", 300); cmds.setAttr(ip + ".coverageOriginX", 50)
cmds.xform(xf, t=(1, 0, 0), s=(1.2, 1.2, 1))
cmds.select(xf)
cmds.undoInfo(state=True, infinity=True)
cards = bc.convert()
check("one card made from the selection", len(cards) == 1)
card = cards[0]
shape = cmds.listRelatives(card, shapes=True, fullPath=True)[0]
check("the card sits under the image plane's transform (follows its animation and parents)",
      cmds.listRelatives(card, parent=True, fullPath=True)[0] == cmds.ls(xf, long=True)[0])
check("named after the image plane", card.endswith("|skyPlane_backdrop"))
bb = cmds.exactWorldBoundingBox(card)
check("one face, the image plane's size (30 x 12, x the transform's 1.2)",
      cmds.polyEvaluate(card, face=True) == 1
      and abs(cmds.getAttr(shape + ".boundingBoxSizeX") - 30) < 1e-3
      and abs(cmds.getAttr(shape + ".boundingBoxSizeY") - 12) < 1e-3)
check("centred on the image plane (Image Center 0)", close(cmds.getAttr(card + ".translate")[0], (0, 0, 0)))
cmds.setAttr(ip + ".width", 20)
check("width and height stay connected", abs(cmds.getAttr(shape + ".boundingBoxSizeX") - 20) < 1e-3)
cmds.setAttr(ip + ".width", 30)
check("the image plane is hidden, not deleted", cmds.objExists(ip) and not cmds.getAttr(ip + ".visibility"))

sg = cmds.listConnections(shape, type="shadingEngine")[0]
shader = cmds.listConnections(sg + ".surfaceShader")[0]
tex = cmds.listConnections(shader + ".outColor", source=True, destination=False)[0]
check("unlit: a surfaceShader fed by a file texture",
      cmds.nodeType(shader) == "surfaceShader" and cmds.nodeType(tex) == "file")
check("the texture shows the image plane's image and colour space",
      cmds.getAttr(tex + ".fileTextureName") == sky and cmds.getAttr(tex + ".colorSpace") == "Raw"
      and cmds.getAttr(tex + ".ignoreColorSpaceFileRules"))
check("colour gain is copied, not connected (Arnold misreads it from an image plane)",
      close(cmds.getAttr(tex + ".colorGain")[0], (0.9, 0.8, 0.7))
      and not cmds.listConnections(tex + ".colorGain", source=True, destination=False))
place = cmds.listConnections(tex + ".uvCoord", source=True, destination=False)[0]
check("coverage crops the image like the image plane does",
      abs(cmds.getAttr(place + ".repeatU") - 0.75) < 1e-6 and abs(cmds.getAttr(place + ".offsetU") - 0.125) < 1e-6
      and abs(cmds.getAttr(place + ".repeatV") - 1) < 1e-6)
flags = {a: cmds.getAttr("%s.%s" % (shape, a)) for a in bc.FLAGS if cmds.objExists("%s.%s" % (shape, a))}
check("camera only: no shadows, reflections, refractions, GI or volume",
      flags["castsShadows"] == 0 and flags["receiveShadows"] == 0 and flags["primaryVisibility"] == 1
      and flags["visibleInReflections"] == 0 and flags["visibleInRefractions"] == 0
      and flags.get("aiVisibleInDiffuseReflection", 0) == 0 and flags.get("aiVisibleInSpecularReflection", 0) == 0
      and flags.get("aiVisibleInDiffuseTransmission", 0) == 0 and flags.get("aiVisibleInVolume", 0) == 0)
check("RGBA display: transparent where the image is", cmds.isConnected(tex + ".outTransparency", shader + ".outTransparency")
      and not cmds.getAttr(shape + ".aiOpaque"))

# run again (the plane is hidden now), then from the card itself
again = bc.convert([xf])
check("running again rebuilds the card, no duplicates",
      len(cmds.ls("skyPlane_backdrop*", type="transform")) == 1 and len(cmds.ls(type="surfaceShader")) == 1
      and len(cmds.ls("skyPlane_backdrop_file*", type="file")) == 1)
from_card = bc.convert([again[0]])
check("selecting the card rebuilds it too", from_card and len(cmds.ls("skyPlane_backdrop*", type="transform")) == 1)
cmds.undo()
check("one undo takes back a whole run (one card and its network, as before)",
      len(cmds.ls("skyPlane_backdrop*", type="transform")) == 1
      and len(cmds.ls("skyPlane_backdrop_file*", type="file")) == 1 and len(cmds.ls(type="surfaceShader")) == 1)

# RGB display: opaque
cmds.setAttr(ip + ".displayMode", 2)
card = bc.convert([xf])[0]
shape = cmds.listRelatives(card, shapes=True, fullPath=True)[0]
shader = cmds.listConnections(cmds.listConnections(shape, type="shadingEngine")[0] + ".surfaceShader")[0]
check("RGB display: opaque", cmds.getAttr(shape + ".aiOpaque")
      and not cmds.listConnections(shader + ".outTransparency", source=True, destination=False))

# --- an image sequence: the card's frame follows the plane's driver ------------
cmds.setAttr(ip + ".useFrameExtension", 1)      # Maya adds its own frame expression
if not cmds.listConnections(ip + ".frameExtension", source=True, destination=False):
    cmds.expression(string="%s.frameExtension = frame;" % ip, object=ip)
card = bc.convert([xf])[0]
tex = cmds.listConnections(card + ".backdropFile")[0]
cmds.currentTime(7)
check("an image sequence stays in step with the image plane",
      cmds.getAttr(tex + ".useFrameExtension") and cmds.getAttr(tex + ".frameExtension") == 7
      and cmds.getAttr(ip + ".frameExtension") == 7)

# --- an image from another project is copied into this one ---------------------
backdrops = os.path.join(proj, "sourceimages", bc.FOLDER)
other = make_image(os.path.join(tmp, "layoutProj", "sourceimages", "dusk.png"), (200, 90, 40))
cmds.file(new=True, force=True)
xf, ip = cmds.imagePlane(fileName=other)
card = bc.convert([xf])[0]
tex = cmds.listConnections(card + ".backdropFile")[0]
copied = os.path.join(backdrops, "dusk.png").replace("\\", "/")
check("an image from another project is copied to this project's sourceimages/backdrops",
      os.path.isfile(copied) and cmds.getAttr(tex + ".fileTextureName") == copied
      and cmds.getAttr(ip + ".imageName") == copied and os.path.isfile(other))
xf2, ip2 = cmds.imagePlane(fileName=other)
bc.convert([xf2])
check("the same image again reuses the copy (no _v002)",
      cmds.getAttr(ip2 + ".imageName") == copied and os.listdir(backdrops) == ["dusk.png"])
make_image(other, (20, 200, 60))                      # same name, different picture
xf3, ip3 = cmds.imagePlane(fileName=other)
bc.convert([xf3])
check("a different image with the same name gets _v002, nothing overwritten",
      cmds.getAttr(ip3 + ".imageName").endswith("/backdrops/dusk_v002.png")
      and sorted(os.listdir(backdrops)) == ["dusk.png", "dusk_v002.png"])
xf4, ip4 = cmds.imagePlane(fileName=sky)
bc.convert([xf4])
check("an image already in the project is left where it is", cmds.getAttr(ip4 + ".imageName") == sky)
seq = [make_image(os.path.join(tmp, "layoutProj", "sourceimages", "clouds", "clouds.%04d.png" % i),
                  (i * 20, 120, 200)) for i in (1, 2, 3)]
xf5, ip5 = cmds.imagePlane(fileName=seq[0])
cmds.setAttr(ip5 + ".useFrameExtension", 1)
card = bc.convert([xf5])[0]
check("an image sequence: every frame is copied, numbers kept",
      sorted(f for f in os.listdir(backdrops) if f.startswith("clouds"))
      == ["clouds.0001.png", "clouds.0002.png", "clouds.0003.png"]
      and cmds.getAttr(cmds.listConnections(card + ".backdropFile")[0] + ".fileTextureName")
      .endswith("/backdrops/clouds.0001.png"))
xf6, ip6 = cmds.imagePlane(fileName=other)
cmds.setAttr(ip6 + ".imageName", os.path.join(tmp, "gone", "missing.png"), type="string")
check("a missing image from another project is refused, not linked to nothing",
      bc.convert([xf6]) == [] and not cmds.listRelatives(xf6, children=True, type="transform"))

# --- refusals -----------------------------------------------------------------
cam = cmds.camera()[1]
cxf, cip = cmds.imagePlane(fileName=sky, camera=cam)
check("a camera's image plane is left alone", bc.convert([cxf]) == [])
mxf, mip = cmds.imagePlane(fileName=sky)
cmds.setAttr(mip + ".type", bc.MOVIE)
check("a movie image plane is refused (a texture can't read movies)", bc.convert([mxf]) == [])
oxf, oip = cmds.imagePlane(fileName=sky)
cmds.setAttr(oip + ".imageCenter", 1, 0, 0, type="double3")
check("a moved Image Center with no viewport to measure it is refused, not guessed",
      bc.convert([oxf]) == [] and not cmds.listRelatives(oxf, children=True, type="transform"))
check("nothing selected: nothing made", bc.convert([]) == [])

shutil.rmtree(tmp, ignore_errors=True)
print("\n%d/%d passed" % (sum(ok), len(ok)))
