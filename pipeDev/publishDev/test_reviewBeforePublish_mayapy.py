# Watch before publishing (2026-10-21): the movie is made straight after
# the playblast and shown (the UI opens RV); Cancel leaves nothing on H or
# scratch, Publish uploads that same movie instead of encoding again.
# ShotGrid, rvio and the playblast are stubbed.
# Run: mayapy test_reviewBeforePublish_mayapy.py
import sys, os, stat, shutil, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE]
import maya.standalone; maya.standalone.initialize()
import maya.cmds as cmds
import publishTool_api as api

ok = []
def check(label, cond):
    ok.append(bool(cond)); print("PASS" if cond else "FAIL", label)

base = tempfile.mkdtemp(prefix="review_")
H, SC = os.path.join(base, "H"), os.path.join(base, "scratch")
FILM = "NWF_SHF"
h_scenes = os.path.join(H, FILM, "maya", "assets", "prop", "spoon", "scenes")
os.makedirs(h_scenes)
sc_scenes = os.path.join(SC, FILM, "maya", "assets", "prop", "spoon", "scenes")
os.makedirs(sc_scenes)

api.who = lambda: "scout"
api.artist_name = lambda login: "Test Person"
api.check_rv = lambda: None
api.find_rvio = lambda: "rvio.exe"
api.find_shotgrid_asset = lambda plan, h_root: {"id": 4242, "code": plan["asset"]}
frames = os.path.join(SC, FILM, "maya", "assets", "prop", "spoon", "images", "spoon_v001")
def fake_playblast(plan, count, objects=None, camera=None):
    os.makedirs(frames, exist_ok=True)
    open(os.path.join(frames, "spoon_v001.0001.jpg"), "w").close()
    return frames, [os.path.join(frames, "spoon_v001.0001.jpg")]
api.playblast_frames = fake_playblast
uploads, encodes = [], []
class FakeSG(object):
    last_encode_problem = None
    def _encode_to_mp4(self, folder, fps, rvio, audio_path=None, audio_offset_seconds=0.0):
        encodes.append(folder)
        movie = os.path.join(folder, "spoon_v001.mp4")
        open(movie, "w").close()
        return movie
    def upload_playblast(self, entity_type, entity_id, folder, files=None, notes=None, fps=None,
                         rvio_path=None, as_login=None, machine_diagnostic=None,
                         movie_path=None, thumbnail_path=None, audio_path=None,
                         audio_offset_seconds=0.0, task_id=None):
        uploads.append(movie_path)
        return {"id": 1, "type": "Version"}
    def get_connection(self): raise RuntimeError("no ShotGrid in the test")
sg = FakeSG()
api._shotgrid = lambda: sg

cmds.file(new=True, force=True)
cmds.polyCube(name="spoon_geo")
scene = os.path.join(sc_scenes, "spoon_model_001.ma")
cmds.file(rename=scene); cmds.file(save=True, type="mayaAscii")

shown = []
def watch(answer):
    def review(movie, plan):
        shown.append((movie, os.path.isfile(movie or ""), os.listdir(h_scenes)))
        return answer
    return review

# -- Cancel ----------------------------------------------------------------------
try:
    api.publish(scene, H, SC, "model", objects=["spoon_geo"], review=watch(False))
    cancelled = False
except api.PublishCancelled:
    cancelled = True
check("Cancel raises PublishCancelled", cancelled)
check("the movie was made before the question, with nothing on H yet",
      shown[-1][1] and not shown[-1][2])
check("cancelled: nothing on the H drive", not os.listdir(h_scenes))
check("cancelled: the frames and movie are gone from scratch", not os.path.exists(frames))
check("cancelled: nothing uploaded", not uploads)

# -- Publish ---------------------------------------------------------------------
plan = api.publish(scene, H, SC, "model", objects=["spoon_geo"], review=watch(True))
check("Publish: written to H as v001 (the cancel didn't use up a version)",
      plan["version"] == 1 and os.path.isfile(plan["dest"]))
check("the reviewed movie is the one uploaded", uploads == [shown[-1][0]])
check("encoded once per attempt", len(encodes) == 2)

# -- Headless (no review): still publishes ----------------------------------------
plan = api.publish(scene, H, SC, "model", objects=["spoon_geo"])
check("no review given: publishes straight through", plan["version"] == 2)

print("%d/%d passed" % (sum(ok), len(ok)))
for root, dirs, files in os.walk(base):
    for f in files:
        os.chmod(os.path.join(root, f), stat.S_IWRITE)
shutil.rmtree(base, ignore_errors=True)
