# Publish movies carry shotSub-style burn-ins (user 2026-10-20): fps, the
# published name, frame number, focal length, artist. Draws on a real
# playblast's JPEGs; headless Maya has no Qt app, so the test makes one
# (and checks that without one the publish carries on, burn-ins skipped).
# Run: mayapy test_burnIn_mayapy.py
import sys, os, shutil, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import maya.standalone; maya.standalone.initialize()
import maya.cmds as cmds
from PySide6 import QtGui
import publishTool_api as api
api.artist_name = lambda login: "Scout Test"        # no ShotGrid in the test
ok = []
def check(label, cond): ok.append(bool(cond)); print("PASS" if cond else "FAIL", label)

d = tempfile.mkdtemp(prefix="burnin_")
cmds.setAttr("defaultResolution.width", 640); cmds.setAttr("defaultResolution.height", 360)
cam = cmds.camera(focalLength=50)[0]
cmds.playbackOptions(minTime=1001, maxTime=1003)
plan = {"code": "anim", "version": 3, "asset": "EAP_010_010", "asset_project": d, "login": "scout",
        "dest": os.path.join(d, "EAP_010_010_scout_anim_v003.ma")}

text = api.burn_in_text(plan, cam)
check("text: fps, shot name (not the file name), focal length, artist (login)",
      text == {"top_left": "24 fps", "top_middle": "EAP_010_010",
               "bottom_left": "50mm", "bottom_right": "Scout Test (scout)"})
check("no camera: no focal length", api.burn_in_text(plan)["bottom_left"] == "")

# Without a Qt application the playblast still works, burn-ins skipped.
folder, files = api.playblast_frames(dict(plan), None)
check("no Qt app: frames still made (burn-ins skipped, not a failure)", len(files) == 3)
blank = QtGui.QImage(files[0])

app = QtGui.QGuiApplication.instance() or QtGui.QGuiApplication([])
api.burn_in(files, text)
img = QtGui.QImage(files[0])
w, h = img.width(), img.height()

def changed(x0, y0, x1, y1):
    """Pixels in this box that differ from the plain frame."""
    n = 0
    for y in range(int(y0), int(y1)):
        for x in range(int(x0), int(x1)):
            if abs(QtGui.QColor(img.pixel(x, y)).lightness() - QtGui.QColor(blank.pixel(x, y)).lightness()) > 40:
                n += 1
    return n

band = max(34, int(h * 0.055)); inset = max(28, int(h * 0.04))
check("top left drawn (fps)", changed(0, inset, w * 0.25, inset + band) > 10)
check("top middle drawn (published name)", changed(w * 0.25, inset, w * 0.75, inset + band) > 10)
check("top right drawn (frame number)", changed(w * 0.75, inset, w, inset + band) > 10)
check("bottom left drawn (focal length)", changed(0, h - inset - band, w * 0.25, h - inset) > 10)
check("bottom right drawn (artist)", changed(w * 0.5, h - inset - band, w, h - inset) > 10)
check("middle of the frame untouched", changed(w * 0.3, h * 0.4, w * 0.7, h * 0.6) == 0)

shutil.rmtree(d, ignore_errors=True)
print("\n%d/%d passed" % (sum(ok), len(ok)))
