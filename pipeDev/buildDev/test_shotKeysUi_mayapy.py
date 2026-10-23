# The Keys column in the real Build tab, offscreen (spec §4 item 7, DECIDED
# 2026-10-23): a rig added to a fresh scene (e.g. on a new machine) comes
# with the shot's latest keys; picking older keys rolls back; pointing the
# picker at another shot lists that shot's keys and the choice stays when
# the picker moves on; a reopened scene shows what it has, unticked; an
# asset keyed by hand starts at "Keep scene's keys".
# Run: mayapy test_shotKeysUi_mayapy.py
import sys, os, time, shutil, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), "publishDev")]
from PySide6 import QtWidgets
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
import maya.standalone; maya.standalone.initialize()
import maya.cmds as cmds
import buildTool_api as api
import buildTool_ui as ui
import publishTool_anim as anim
import pipeEnv

ok = []
def check(label, cond):
    ok.append(bool(cond)); print("PASS" if cond else "FAIL", label)

base = tempfile.mkdtemp(prefix="keysui_")
H, SC = os.path.join(base, "H"), os.path.join(base, "scratch")
FILM, SEQ, SHOT, OTHER, LOGIN = "NWF_SHF", "SEQ010", "SEQ010_120", "SEQ010_110", "scout"
_cfg = os.path.join(base, "pipeline_config.json")
api.pub._config_path = lambda: _cfg
api.pub.set_root(api.pub.H_DRIVE, H)
api.pub.set_root(api.pub.SCRATCH, SC)
api.pub.save_config(dict(api.pub.load_config(), publish_as=LOGIN))
os.environ.pop(pipeEnv.VAR, None)


def save_as(path):
    if not os.path.isdir(os.path.dirname(path)):
        os.makedirs(os.path.dirname(path))
    cmds.file(rename=path); cmds.file(save=True, type="mayaAscii", force=True)


# Scout's rig v001 on the H drive, in its stamped pipe group.
rig = os.path.join(H, FILM, "maya", "assets", "character", "scout", "scenes", LOGIN,
                   "scout_%s_rig_v001.ma" % LOGIN)
cmds.file(new=True, force=True)
group = cmds.group(empty=True, name="scout_rig_GRP")
for name, value in (("sgAssetId", 7), ("asset", "scout"), ("assetType", "character"),
                    ("department", "rig"), ("version", 1), ("artistId", LOGIN)):
    if isinstance(value, int):
        cmds.addAttr(group, longName="pipe_" + name, attributeType="long")
        cmds.setAttr("%s.pipe_%s" % (group, name), value)
    else:
        cmds.addAttr(group, longName="pipe_" + name, dataType="string")
        cmds.setAttr("%s.pipe_%s" % (group, name), value, type="string")
cmds.parent(cmds.spaceLocator(name="ctrl")[0], group)
save_as(rig)


def publish_keys(shot, code, tx_at_10):
    cmds.file(new=True, force=True)
    cmds.file(rig, reference=True, namespace="scout_rig")
    cmds.setKeyframe("scout_rig:ctrl", attribute="translateX", time=1, value=0)
    cmds.setKeyframe("scout_rig:ctrl", attribute="translateX", time=10, value=tx_at_10)
    scene = os.path.join(base, "work", "%s_%s.ma" % (shot, code))
    save_as(scene)
    item = anim.classify(["scout_rig:ctrl"])[0]
    folder = os.path.join(H, FILM, "maya", "sequences", SEQ, shot, "scenes", LOGIN)
    if not os.path.isdir(folder):
        os.makedirs(folder)
    stem = os.path.join(folder, "%s_%s_%s_%s_v001" % (shot, LOGIN, item["name"], code))
    anim.export_keys(item, {"keys": stem + ".ma", "map": stem + ".json"},
                     {"shot": shot, "login": LOGIN, "version": 1, "stage": code}, 1, 10, scene)
    time.sleep(1.1)


publish_keys(SHOT, "layout", 2.0)
publish_keys(SHOT, "anim", 5.0)
publish_keys(OTHER, "anim", 9.0)
LAYOUT, ANIM = api.keys_id(SHOT, LOGIN, "layout", 1), api.keys_id(SHOT, LOGIN, "anim", 1)
OTHER_ANIM = api.keys_id(OTHER, LOGIN, "anim", 1)


def tx_at_10():
    cmds.currentTime(10)
    return round(cmds.getAttr("scout_rig:ctrl.tx"), 4)


def keys_combo(tab):
    return tab.table.cellWidget(0, 4)


# A fresh scene on a new scratch drive: add Scout, Build.
shot = api.shot_folder(SC, FILM, SEQ, SHOT)
cmds.file(new=True, force=True)
save_as(os.path.join(shot, "scenes", "%s_001.ma" % SHOT))
parent = QtWidgets.QWidget()
tab = ui.BuildShotTab(lambda: (H, SC), parent)
tab.refresh()
tab.picker.set_current(film=FILM, code="rig", group="character", name="scout")
tab._add_asset()
row = tab._rows[0]
check("new rig row starts at the shot's latest keys", row["keys_chosen"] == ANIM)
combo = keys_combo(tab)
items = [combo.itemData(i) for i in range(combo.count())] if combo else []
check("Keys dropdown: newest first, then None", items == [ANIM, LAYOUT, api.NO_KEYS])
check("latest marked", combo and "(latest)" in combo.itemText(0))
tab._build_shot()
print("   ", tab.status._text.replace("\n", " | "))
check("keys on after Build", tx_at_10() == 5.0)
check("row unticked after Build", not row["checked"])

# Roll back to the layout keys.
combo = keys_combo(tab)
combo.setCurrentIndex(combo.findData(LAYOUT))
check("picking other keys ticks the row", row["checked"])
combo.setCurrentIndex(combo.findData(ANIM))
check("picking back what the scene has unticks it", not row["checked"])
combo.setCurrentIndex(combo.findData(LAYOUT))
tab._build_shot()
check("rolled back to layout keys", tx_at_10() == 2.0)

# Point the picker at another shot: its keys are listed; pick them.
tab.picker.set_current(code="cam", group=SEQ, name=OTHER)
tab._on_keys_source_changed()
combo = keys_combo(tab)
items = [combo.itemData(i) for i in range(combo.count())]
check("picker on another shot lists that shot's keys (plus the current choice)",
      items[0] == OTHER_ANIM and LAYOUT in items and ANIM not in items)
check("other shot shown in the label", OTHER in combo.itemText(0))
combo.setCurrentIndex(combo.findData(OTHER_ANIM))
tab.picker.set_current(film=FILM, code="rig", group="character", name="scout")
tab._on_keys_source_changed()
combo = keys_combo(tab)
check("choice from another shot stays when the picker moves on",
      combo.currentData() == OTHER_ANIM and row["keys_chosen"] == OTHER_ANIM)
tab._build_shot()
check("keys from another shot on", tx_at_10() == 9.0)

# Reopen: the row shows what the scene has, unticked.
cmds.file(save=True, force=True)
cmds.file(cmds.file(query=True, sceneName=True), open=True, force=True)
tab.refresh()
row = tab._rows[0]
check("reopened: row starts at the keys the scene has, unticked",
      row["keys_start"] == OTHER_ANIM and not row["checked"])
check("In this shot shows the keys", "keys v001 anim" in tab.table.item(0, 5).text())

# Keyed by hand, no record: starts at Keep, unticked, nothing wiped.
cmds.file(new=True, force=True)
save_as(os.path.join(shot, "scenes", "%s_002.ma" % SHOT))
api.build_asset(shot, tab._rows[0], tab._rows[0]["chosen"])
cmds.setKeyframe("scout_rig:ctrl", attribute="translateX", time=10, value=7)
tab.refresh()
row = tab._rows[0]
check("hand-keyed asset starts at Keep, unticked",
      row["keys_chosen"] == api.KEEP_KEYS and not row["checked"])
tab._build_shot()
check("hand keys untouched", tx_at_10() == 7.0)

# The shot's list is saved on the H drive (user, 2026-10-23).
saved = api.read_shot_list(H, FILM, SEQ, SHOT)
check("shot's list saved on the H drive", saved == [api.manifest_key("character", "scout", "rig")])

# Another machine: a new scratch drive with nothing on it. The list comes
# back from H, at the latest version and the latest keys, ready to build.
SC2 = os.path.join(base, "scratch2")
shot2 = api.shot_folder(SC2, FILM, SEQ, SHOT)
cmds.file(new=True, force=True)
save_as(os.path.join(shot2, "scenes", "%s_001.ma" % SHOT))
tab2 = ui.BuildShotTab(lambda: (H, SC2), parent)
tab2.refresh()
rows = dict((r["asset"], r) for r in tab2._rows)
check("new drive: list comes back from the H drive", "scout" in rows)
check("new drive: latest version, latest keys, ticked",
      rows["scout"]["chosen"] == rows["scout"]["latest"]
      and rows["scout"]["keys_chosen"] == ANIM and rows["scout"]["checked"])
tab2._build_shot()
check("new drive: built with the latest keys", tx_at_10() == 5.0)

# "-" takes it off the shot's list for good.
tab2.table.selectRow(0)
tab2._remove_rows()
check("'-' removes it from the saved list", api.read_shot_list(H, FILM, SEQ, SHOT) == [])
tab2.refresh()
check("...and it doesn't come back", not [r for r in tab2._rows if r["asset"] == "scout"])
check("still in the scene ('-' is list only)", cmds.ls("scout_rig:ctrl"))

shutil.rmtree(base, ignore_errors=True)
print("\n%d/%d passed" % (sum(ok), len(ok)))
maya.standalone.uninitialize()
os._exit(0 if all(ok) else 1)
