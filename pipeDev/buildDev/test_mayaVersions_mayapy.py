# Moving to Maya 2027 (user, 2026-10-28): the pipe's settings follow into a
# new Maya version's prefs, Build warns about files from a newer Maya, and
# ShotGrid Versions are named after the published file (with the login) so
# a new login's v001 never reuses someone else's Version. Throwaway
# folders only. Run: mayapy test_mayaVersions_mayapy.py
import sys, os, json, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), "publishDev")]
import maya.standalone; maya.standalone.initialize()
import maya.cmds as cmds
import buildTool_api as api
pub = api.pub

ok = []
def check(label, cond):
    ok.append(bool(cond)); print("PASS" if cond else "FAIL", label)

base = tempfile.mkdtemp(prefix="mayaver_")

# -- settings carried into a new version's prefs ------------------------------
maya_dir = os.path.join(base, "maya")
for v in ("2024", "2025", "2027"):
    os.makedirs(os.path.join(maya_dir, v, "prefs"))
old = os.path.join(maya_dir, "2024", "prefs", pub.CONFIG_NAME)
newest = os.path.join(maya_dir, "2025", "prefs", pub.CONFIG_NAME)
json.dump({pub.H_DRIVE: "X:\\old"}, open(old, "w"))
os.utime(old, (1000000000, 1000000000))
json.dump({pub.H_DRIVE: "G:\\H", "scratch_root": "D:\\", "shotgrid_as": "e131988"}, open(newest, "w"))
target = os.path.join(maya_dir, "2027", "prefs", pub.CONFIG_NAME)
pub._config_path = lambda: target
check("new Maya: settings copied from the newest other version",
      pub.load_config().get("shotgrid_as") == "e131988" and os.path.isfile(target))
json.dump({pub.H_DRIVE: "Q:\\mine"}, open(target, "w"))
check("... once: its own settings are kept after that", pub.get_root(pub.H_DRIVE) == "Q:\\mine")
loose = os.path.join(base, "elsewhere", pub.CONFIG_NAME)
pub._config_path = lambda: loose
check("not a Maya prefs folder: nothing copied", pub.load_config() == {} and not os.path.exists(loose))

# -- Build: a publish from a newer Maya --------------------------------------
def ma(name, version):
    path = os.path.join(base, name)
    with open(path, "w") as f:
        f.write('//Maya ASCII %s scene\nrequires maya "%sff03";\ncreateNode transform -n "a";\n'
                % (version, version))
    return path
this = int(cmds.about(majorVersion=True))
check("reads the Maya a .ma was saved in", api.saved_in_maya(ma("a.ma", 2025)) == 2025)
check("same or older Maya: no warning", api.newer_maya_warning(ma("b.ma", this)) is None
      and api.newer_maya_warning(ma("c.ma", this - 1)) is None)
warning = api.newer_maya_warning(ma("d.ma", this + 1))
check("newer Maya: Build warns, naming both versions",
      warning and ("Maya %d" % (this + 1)) in warning and ("(%d)" % this) in warning)
check("not a .ma: no warning", api.newer_maya_warning(os.path.join(base, "e.mb")) is None)

# -- ShotGrid Version name: the frames folder carries the login --------------
cmds.file(new=True, force=True)
cmds.playbackOptions(minTime=1, maxTime=2)
plan = {"code": "env", "version": 2, "asset": "shed", "asset_project": base, "login": "e131988"}
folder, files = pub.playblast_frames(plan, None)
check("frames folder (the Version name after the entity) has the login",
      os.path.basename(folder) == "e131988_env_v002" and len(files) == 2)
pub.remove_frames(folder, base)
print("%d/%d passed" % (sum(ok), len(ok)))
