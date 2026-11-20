"""
Model Tool — USD hierarchy and names (mpModel shelf, user 2026-11-20)

Gets a model ready to publish as USD. The layout and names are the user's
(2026-11-20):

    <asset>_model_GRP       added by Publish: the USD's default prim, kind
    |                       component (publishTool_outputs.finish_usd)
    +- geo
       +- render            the meshes that render     (USD purpose render)
       |  +- chair_seat_GEO
       |  +- legs_GRP
       |     +- chair_legL_GEO
       +- proxy             an optional light stand-in (USD purpose proxy)
          +- chair_proxy_GEO

    meshes  <asset>_<part>_GEO      groups  <part>_GRP

Hierarchy (the USD Hierarchy button): build() makes geo|render|proxy at the
world root; add() moves what's picked into render or proxy, where it was
in the world. left_out() is the geometry still outside geo.

Names (the USD Names button): name() names what's picked from a part name
(chair_seat_GEO; several get 01, 02, ...); problems() finds the names that
would clash or break the convention and fix() mends them: two nodes with
the same name, a namespace, a missing _GEO / _GRP or asset prefix, shape
nodes not named after their transform. A Maya default name (pCube1,
group3) is listed but left for the artist to name.

Asset scenes only (the asset's name comes from the scene's folder). No UI
here (modelTool_usd_ui), so it can be tested under mayapy.
"""

import re

import maya.cmds as cmds

import publishTool_api as api
from publishTool_api import PublishError

GEO, RENDER, PROXY = "geo", "render", "proxy"
STRUCTURE = (GEO, RENDER, PROXY)
GEO_SUFFIX, GRP_SUFFIX = "_GEO", "_GRP"
# Maya's own names for new things: listed for the artist to name.
DEFAULT_NAME = re.compile(
    r"^(p(Cube|Sphere|Cylinder|Cone|Plane|Torus|Prism|Pyramid|Pipe|Helix|SolidSphere|"
    r"Disc|Platonic|SuperShape|Gear)|polySurface|polyMesh|mesh|transform|group|null|"
    r"curve|nurbs\w*|subdiv\w*)\d*$")
SKIP_TYPES = ("camera", "light")


# ---------------------------------------------------------------------------
# The scene
# ---------------------------------------------------------------------------

def asset_name(scene=None):
    """The asset's name, from the scene's folder (assets\\<type>\\<asset>\\)."""
    scene = scene or cmds.file(query=True, sceneName=True)
    if not scene:
        raise PublishError("Save the scene in its asset's scenes folder first: the names "
                           "start with the asset's name.")
    return api.asset_context(scene)["asset"]


def _short(node):
    return node.split("|")[-1]


def _bare(name):
    return name.split(":")[-1]


def _uuid(node):
    return cmds.ls(node, uuid=True)[0]


def _path(uuid):
    found = cmds.ls(uuid, long=True)
    return found[0] if found else None


def _shapes(node):
    return cmds.listRelatives(node, shapes=True, fullPath=True, noIntermediate=True) or []


def _kind(node):
    """'geo' (a transform with geometry), 'group' (a transform holding
    others), or None (a camera, light, shape or anything else)."""
    if cmds.nodeType(node) != "transform":
        return None
    shapes = _shapes(node)
    if any(cmds.nodeType(s) in SKIP_TYPES or cmds.objectType(s, isAType="light")
           for s in shapes):
        return None
    if shapes:
        return "geo"
    return "group"


def _default_camera(node):
    return cmds.camera(node, query=True, startupCamera=True) if _shapes(node) and \
        cmds.nodeType(_shapes(node)[0]) == "camera" else False


# ---------------------------------------------------------------------------
# The hierarchy
# ---------------------------------------------------------------------------

def structure():
    """{'geo', 'render', 'proxy'}: each one's path, or None if it isn't
    there yet."""
    found = {}
    for key, path in ((GEO, "|geo"), (RENDER, "|geo|render"), (PROXY, "|geo|proxy")):
        found[key] = path if cmds.objExists(path) and cmds.nodeType(path) == "transform" \
            else None
    return found


def _in_the_way():
    """Nodes already called geo / render / proxy somewhere else: the
    hierarchy needs those names to itself."""
    where = {GEO: "|geo", RENDER: "|geo|render", PROXY: "|geo|proxy"}
    clash = []
    for key in STRUCTURE:
        for node in cmds.ls(key, long=True) or []:
            if node != where[key]:
                clash.append(node)
    return clash


def build():
    """Make geo|render|proxy at the world root (only the parts missing).
    Returns structure()."""
    clash = _in_the_way()
    if clash:
        raise PublishError("The USD hierarchy needs the names geo, render and proxy, and "
                           "these already have one:\n  %s\nRename them first (USD Names)."
                           % "\n  ".join(clash))
    if not cmds.objExists("|geo"):
        cmds.group(empty=True, world=True, name=GEO)
    for key in (RENDER, PROXY):
        if not cmds.objExists("|geo|" + key):
            cmds.group(empty=True, parent="|geo", name=key)
    return structure()


def _topmost(nodes):
    """The picked transforms, each once, without any that sit under another
    picked one (a shape counts as its transform)."""
    picked = []
    for node in cmds.ls(nodes, long=True) or []:
        if cmds.nodeType(node) != "transform":
            node = (cmds.listRelatives(node, parent=True, fullPath=True) or [None])[0]
        if node and node not in picked:
            picked.append(node)
    return [n for n in picked if not any(n.startswith(o + "|") for o in picked if o != n)]


def add(nodes, purpose=RENDER):
    """Move nodes into geo|render (or geo|proxy), where they are in the
    world. Builds the hierarchy first if it's missing. Returns the new
    paths of what moved."""
    if purpose not in (RENDER, PROXY):
        raise ValueError(purpose)
    target = build()[purpose]
    moved = []
    for node in _topmost(nodes):
        if node in ("|geo", "|geo|render", "|geo|proxy"):
            continue
        if target.startswith(node + "|"):
            continue                    # can't go inside itself
        if (cmds.listRelatives(node, parent=True, fullPath=True) or [None])[0] == target:
            continue                    # already there
        if _kind(node) is None:
            continue                    # cameras, lights
        moved += cmds.parent(node, target) or []
    return [cmds.ls(m, long=True)[0] for m in moved]


def left_out():
    """Top-level geometry outside geo (cameras and lights don't count)."""
    out = []
    for node in cmds.ls(assemblies=True, long=True) or []:
        if node == "|geo" or _default_camera(node):
            continue
        if _kind(node) == "geo" or (_kind(node) == "group" and _has_geometry(node)):
            out.append(node)
    return out


def _has_geometry(node):
    return any(_kind(n) == "geo" for n in
               cmds.listRelatives(node, allDescendents=True, fullPath=True, type="transform") or [])


# ---------------------------------------------------------------------------
# Names
# ---------------------------------------------------------------------------

def clean_part(text, asset=None):
    """A part name made fit for USD and the convention: letters, digits and
    _ only, no leading digit, without the asset's name or a _GEO / _GRP the
    artist typed."""
    text = re.sub(r"[^A-Za-z0-9_]+", "_", (text or "").strip())
    text = re.sub(r"_+", "_", text).strip("_")
    if asset and text.lower().startswith(asset.lower() + "_"):
        text = text[len(asset) + 1:]
    text = re.sub(r"_(GEO|GRP|geo|grp|Geo|Grp)$", "", text)
    return re.sub(r"^[0-9_]+", "", text)


def wanted(node, asset, part):
    """What node is called with this part name."""
    return ("%s_%s%s" % (asset, part, GEO_SUFFIX)) if _kind(node) == "geo" \
        else part + GRP_SUFFIX


def _numbered(name, n, width=2):
    """chair_leg_GEO, 3 -> chair_leg03_GEO."""
    for suffix in (GEO_SUFFIX, GRP_SUFFIX):
        if name.endswith(suffix):
            return "%s%0*d%s" % (name[:-len(suffix)], width, n, suffix)
    return "%s%0*d" % (name, width, n)


def _taken(ignore=()):
    """Every DAG node's short name in the scene (but those being renamed)."""
    ignore = set(ignore)
    names = set()
    for node in cmds.ls(dag=True, long=True) or []:
        if node not in ignore:
            names.add(_bare(_short(node)))
    return names


def _free(name, taken):
    """name, or the first numbered version of it no one has."""
    if name not in taken:
        return name
    n = 1
    while _numbered(name, n) in taken:
        n += 1
    return _numbered(name, n)


def _rename(uuid, new):
    """Rename a node (by UUID: paths change as parents are renamed) and its
    shapes after it (<name>Shape, as Maya does)."""
    node = _path(uuid)
    if _short(node) != new:
        cmds.rename(node, ":" + new)    # into the root namespace
        node = _path(uuid)
    shapes = _shapes(node)
    for n, shape in enumerate(shapes):
        want = "%sShape%s" % (new, n + 1 if len(shapes) > 1 and n else "")
        if _short(shape) != want and not cmds.referenceQuery(shape, isNodeReferenced=True):
            cmds.rename(shape, ":" + want)
    return _path(uuid)


def name(nodes, part, asset=None):
    """Name what's picked from a part name: meshes <asset>_<part>_GEO,
    groups <part>_GRP; several of a kind numbered 01, 02, ... Never takes a
    name something else has. Returns [(old short name, new)]."""
    asset = asset or asset_name()
    part = clean_part(part, asset)
    if not part:
        raise PublishError("Type a part name (e.g. seat, legL, wheelFront).")
    picked = [n for n in cmds.ls(nodes, long=True, type="transform") or []
              if n not in ("|geo", "|geo|render", "|geo|proxy") and _kind(n)]
    if not picked:
        raise PublishError("Pick the meshes or groups to name.")
    taken = _taken(ignore=picked)
    kinds = [(_uuid(n), _kind(n)) for n in picked]     # paths change as they're renamed
    done = []
    for kind in ("geo", "group"):
        group = [u for u, k in kinds if k == kind]
        base = wanted(_path(group[0]), asset, part) if group else None
        for n, uuid in enumerate(group, 1):
            new = base if len(group) == 1 else _numbered(base, n)
            new = _free(new, taken)
            taken.add(new)
            old = _short(_path(uuid))
            _rename(uuid, new)
            done.append((old, new))
    return done


def _scope():
    """The nodes names are checked on: everything under geo, or (no
    hierarchy yet) every transform with geometry below the world root."""
    roots = ["|geo"] if cmds.objExists("|geo") else left_out()
    nodes = []
    for root in roots:
        nodes.append(root)
        nodes += cmds.listRelatives(root, allDescendents=True, fullPath=True,
                                    type="transform") or []
    return [n for n in sorted(set(nodes), key=lambda p: (p.count("|"), p))
            if n not in ("|geo", "|geo|render", "|geo|proxy") and _kind(n)
            and not cmds.referenceQuery(n, isNodeReferenced=True)]


def proper(node, asset):
    """The name node should have by the convention, or None if only the
    artist can say (a Maya default name like pCube1)."""
    short = _bare(_short(node))
    kind = _kind(node)
    stem = re.sub(r"_(GEO|GRP)$", "", short, flags=re.IGNORECASE)
    if kind == "geo":
        stem = re.sub(r"^%s_" % re.escape(asset), "", stem, flags=re.IGNORECASE)
    if DEFAULT_NAME.match(stem):
        return None
    if kind == "geo":
        return "%s_%s%s" % (asset, stem, GEO_SUFFIX)
    return stem + GRP_SUFFIX


def problems(asset=None):
    """The names to fix before a USD publish, in the order fix() mends
    them. Each: {node, uuid, name, why, fix} (fix None: name it yourself)."""
    asset = asset or asset_name()
    found = []
    nodes = _scope()
    counts = {}
    for node in cmds.ls(dag=True, long=True) or []:
        counts.setdefault(_bare(_short(node)), []).append(node)
    for node in nodes:
        short = _short(node)
        whys = []
        if ":" in short:
            whys.append("has a namespace")
        want = proper(node, asset)
        if want is None:
            whys.append("Maya's default name: give it a real one (Name Selected)")
        elif want != _bare(short):
            kind = _kind(node)
            if kind == "geo" and not _bare(short).lower().startswith(asset.lower() + "_"):
                whys.append("doesn't start with %s_" % asset)
            if not _bare(short).endswith(GEO_SUFFIX if kind == "geo" else GRP_SUFFIX):
                whys.append("doesn't end in %s" % (GEO_SUFFIX if kind == "geo" else GRP_SUFFIX))
            if not whys:
                whys.append("should be %s" % want)
        if len(counts.get(_bare(short), [])) > 1:
            whys.append("%d nodes are called %s" % (len(counts[_bare(short)]), _bare(short)))
        shapes = _shapes(node)
        if shapes and not _short(shapes[0]).startswith(_bare(short)):
            whys.append("its shape is called %s" % _short(shapes[0]))
        if whys:
            found.append({"node": node, "uuid": _uuid(node), "name": short,
                          "why": "; ".join(whys), "fix": want})
    return found


def fix(asset=None, found=None):
    """Mend every problem that has a fix: the convention's name, made unique
    (a number before the suffix) when it's taken. Two nodes with one name:
    the first keeps it. Returns [(old, new)]."""
    asset = asset or asset_name()
    found = problems(asset) if found is None else found
    moving = [f["node"] for f in found]
    taken = _taken(ignore=moving)
    done = []
    for f in found:
        node = _path(f["uuid"])
        if not node:
            continue
        target = f["fix"] or _bare(_short(node))
        new = _free(target, taken)
        taken.add(new)
        old = _short(node)
        _rename(f["uuid"], new)
        if old != new:
            done.append((old, new))
    return done
