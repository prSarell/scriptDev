r"""Headless test: Publish puts the timeline sound into the ShotGrid movie.

    "C:\Program Files\Autodesk\Maya2025\bin\mayapy.exe" pipeDev/publishDev/test_publishAudio_mayapy.py

Throwaway files in %TEMP% only. Checks:
  - scene_audio() finds the sound and works out the offset in seconds;
  - upload_with_audio() passes audio to a shotgridConnect that supports it,
    and warns (never fails) with an older one that doesn't;
  - a real rvio encode, using the repo's shotgridConnect._encode_to_mp4,
    produces an H.264 mp4 that contains a sound track.
Spec: filmPipeline_spec.md §4 "Final publish movie for the edit".
Last run 2026-10-13: see the summary line printed at the end.
"""
import os, sys, struct, wave, shutil, tempfile

from PySide6 import QtWidgets, QtGui
app = QtWidgets.QApplication(sys.argv)
import maya.standalone
maya.standalone.initialize()
import maya.cmds as cmds

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path[:0] = [HERE, os.path.join(REPO, "shelfDev", "mpAnim", "tools")]
import publishTool_api as api
import shotgridConnect as sgc      # the repo's live copy (shelf-native)

base = tempfile.mkdtemp(prefix="pubaudio_")
results = []


def check(name, ok):
    results.append(bool(ok)); print(("PASS " if ok else "FAIL ") + name)


# A 2-second 440 Hz tone.
wav = os.path.join(base, "line.wav")
with wave.open(wav, "w") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(48000)
    import math
    w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(i * 2 * math.pi * 440 / 48000)))
                           for i in range(96000)))

cmds.file(new=True, force=True)
cmds.currentUnit(time="film")     # 24 fps
cmds.playbackOptions(minTime=1001, maxTime=1048)
check("no sound -> no audio", api.scene_audio(1001) == (None, 0.0))
cmds.sound(file=wav, offset=1001, name="dialogue")
path, offset = api.scene_audio(1001)
check("finds the sound node", path and os.path.normcase(path) == os.path.normcase(wav))
check("offset 0s when sound starts on the first frame", abs(offset) < 1e-6)
cmds.setAttr("dialogue.offset", 1013)
check("offset 0.5s when sound starts 12 frames in", abs(api.scene_audio(1001)[1] - 0.5) < 1e-6)
cmds.setAttr("dialogue.offset", 1001)


class NewSG(object):
    def upload_playblast(self, entity_type, entity_id, folder, files=None, notes=None, fps=None,
                         rvio_path=None, as_login=None, machine_diagnostic=None,
                         movie_path=None, thumbnail_path=None, audio_path=None,
                         audio_offset_seconds=0.0):
        return {"audio_path": audio_path, "audio_offset_seconds": audio_offset_seconds}


class OldSG(object):
    def upload_playblast(self, entity_type, entity_id, folder, files=None, notes=None, fps=None,
                         rvio_path=None, as_login=None, machine_diagnostic=None):
        return {"called": True}


plan = {}
r = api.upload_with_audio(NewSG(), plan, wav, 0.5, "Shot", 1, base, fps=24)
check("new shotgridConnect gets the audio", r["audio_path"] == wav and r["audio_offset_seconds"] == 0.5)
check("no warning with new shotgridConnect", not plan.get("warnings"))
plan = {}
r = api.upload_with_audio(OldSG(), plan, wav, 0.5, "Shot", 1, base, fps=24)
check("old shotgridConnect still uploads", r.get("called"))
check("old shotgridConnect -> 'no sound' warning", plan.get("warnings") and "no sound" in plan["warnings"][0])
plan = {}
api.upload_with_audio(OldSG(), plan, None, 0.0, "Shot", 1, base, fps=24)
check("no sound in scene -> no warning", not plan.get("warnings"))

# Real encode: 48 frames + the tone, through the same encoder Publish uses.
rvio = api.find_rvio()
if rvio:
    frames = os.path.join(base, "v001")
    os.makedirs(frames)
    for i in range(1001, 1049):
        img = QtGui.QImage(320, 180, QtGui.QImage.Format_RGB32)
        img.fill(QtGui.QColor((i * 5) % 255, 80, 120))
        img.save(os.path.join(frames, "shot.%04d.jpg" % i), "JPG")
    mp4 = sgc._encode_to_mp4(frames, 24, rvio, wav, 0.0)
    data = open(mp4, "rb").read() if mp4 else b""
    check("rvio made an mp4", bool(data))
    check("video is H.264 (avc1), which Premiere reads", b"avc1" in data)
    check("mp4 has a sound track", b"soun" in data)
else:
    print("SKIP rvio encode: rvio not found on this machine")

print("\n%d/%d passed" % (sum(results), len(results)))
shutil.rmtree(base, ignore_errors=True)
maya.standalone.uninitialize()
