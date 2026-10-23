# mpLayout "Environment Sets" (user, 2026-10-23): one click makes the empty
# environment groups and sets with the names Publish checks; the artist
# fills them. Filled the way an artist would, the scene passes the
# environment publish's own check. Running again duplicates nothing; names
# used elsewhere don't get numbers; sets the artist already filled are kept.
# Run: mayapy test_layoutEnv_mayapy.py
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), "publishDev")]
import maya.standalone; maya.standalone.initialize()
import maya.cmds as cmds
import publishTool_env as env
import layoutTool_env as lay

ok = []
def check(label, cond):
    ok.append(bool(cond)); print("PASS" if cond else "FAIL", label)

members = lambda s: sorted(m.split("|")[-1] for m in cmds.sets(s, query=True) or [])

# A fresh scene.
cmds.file(new=True, force=True)
made, kept = lay.make_environment_structure()
check("groups made", all(cmds.objExists("|environment|" + g)
                         for g in ("landscape", "buildings", "sky")))
check("environment_SET holds the three role sets",
      members("environment_SET") == ["building_SET", "landscape_SET", "sky_SET"])
check("each role set holds its group", (members("landscape_SET"), members("building_SET"),
                                        members("sky_SET")) == (["landscape"], ["buildings"], ["sky"]))
check("nothing reported as already there", not kept)

# Running again: nothing new.
before = sorted(cmds.ls())
made, kept = lay.make_environment_structure()
check("second run makes nothing", not made and sorted(cmds.ls()) == before)

# Filled the way an artist would: the publish's own check passes.
cmds.parent(cmds.polyPlane(name="ground")[0], "|environment|landscape")
shed = cmds.group(empty=True, name="shed", parent="|environment|buildings")
cmds.parent(cmds.polyCube(name="shedBox")[0], shed)
cmds.parent(cmds.imagePlane(name="skyPlane")[0], "|environment|sky")
found = env.check_environment()
check("filled in: passes the environment publish check",
      [n.split("|")[-1] for n in found[env.BUILDINGS]] == ["shed"]
      and [n.split("|")[-1] for n in found[env.LANDSCAPE]] == ["landscape"]
      and [n.split("|")[-1] for n in found[env.SKY]] == ["sky"])

# Names already used elsewhere: still made with the exact names.
cmds.file(new=True, force=True)
cmds.group(empty=True, name="landscape")
cmds.group(empty=True, name="sky")
lay.make_environment_structure()
check("exact names even when used elsewhere", cmds.objExists("|environment|landscape")
      and cmds.objExists("|environment|sky"))

# Partly set up by the artist: what they made is kept.
cmds.file(new=True, force=True)
top = cmds.group(empty=True, name="environment")
cmds.group(empty=True, name="buildings", parent=top)
cmds.parent(cmds.polyPlane(name="ground")[0], top)
cmds.sets("|environment|ground", name="landscape_SET")
made, kept = lay.make_environment_structure()
check("existing buildings group reused", len(cmds.ls("buildings", long=True)) == 1)
check("artist's landscape_SET kept as made", members("landscape_SET") == ["ground"])
check("...and reported", any("landscape_SET" in k for k in kept))
check("missing pieces still made", members("building_SET") == ["buildings"]
      and cmds.sets("landscape_SET", isMember="environment_SET"))

# A non-set node with a set's name: refused, explained.
cmds.file(new=True, force=True)
cmds.group(empty=True, name="environment_SET")
try:
    lay.make_environment_structure()
    check("non-set environment_SET refused", False)
except RuntimeError as e:
    check("non-set environment_SET refused", "isn't a set" in str(e))

print("%d/%d passed" % (sum(ok), len(ok)))
maya.standalone.uninitialize()
os._exit(0 if all(ok) else 1)
