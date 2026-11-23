"""Edge To Curve - build a NURBS curve from selected polygon edges.

Select a run of connected edges on a mesh (e.g. an edge path down a
character's back) and run. One curve is made per connected run of edges,
with one CV snapped to each vertex on the run, in order along the edges.

- Open runs start at the end with the lower world Y, so a spine curve
  runs bottom to top.
- Closed loops make a closed (periodic) curve.
- Curves are cubic; runs with fewer than 4 vertices drop to the highest
  degree they can support (2 vertices -> linear).

Shelf usage:
    import edgeToCurve
    edgeToCurve.run()
"""
import maya.cmds as cmds

DEFAULT_DEGREE = 3


def _edge_vertex_pairs(edges):
    """Return {(mesh, edgeIndex): (vtxA, vtxB)} for the given edge components."""
    pairs = []
    for edge in cmds.ls(edges, flatten=True):
        verts = cmds.ls(cmds.polyListComponentConversion(edge, fromEdge=True,
                                                         toVertex=True),
                        flatten=True)
        if len(verts) == 2:
            pairs.append((verts[0], verts[1]))
    return pairs


def _ordered_chains(pairs):
    """Group edge vertex pairs into ordered chains.

    Returns a list of (vertex_list, is_closed). Raises if a run branches
    (a vertex joined to more than two selected edges).
    """
    neighbours = {}
    for a, b in pairs:
        neighbours.setdefault(a, set()).add(b)
        neighbours.setdefault(b, set()).add(a)

    branched = [v for v, n in neighbours.items() if len(n) > 2]
    if branched:
        raise RuntimeError(
            'The selected edges branch at %s. Select a single path of edges '
            '(no forks) for each curve.' % branched[0])

    chains = []
    unvisited = set(neighbours)
    while unvisited:
        # Collect this connected run.
        seed = next(iter(unvisited))
        run, stack = set(), [seed]
        while stack:
            v = stack.pop()
            if v in run:
                continue
            run.add(v)
            stack.extend(neighbours[v] - run)
        unvisited -= run

        ends = [v for v in run if len(neighbours[v]) == 1]
        closed = not ends
        start = ends[0] if ends else min(run)

        ordered, prev, cur = [start], None, start
        while True:
            nxt = [n for n in neighbours[cur] if n != prev and n not in ordered]
            if not nxt:
                break
            prev, cur = cur, nxt[0]
            ordered.append(cur)
        chains.append((ordered, closed))
    return chains


def _make_curve(points, closed, name, degree=DEFAULT_DEGREE):
    count = len(points)
    if closed:
        # A periodic curve needs at least degree + 1 unique CVs.
        degree = max(1, min(degree, count - 1))
        if count < 3:
            raise RuntimeError('A closed loop needs at least 3 vertices.')
        cvs = points + points[:degree]
        knots = list(range(-(degree - 1), count + degree))
        return cmds.curve(name=name, degree=degree, periodic=True,
                          point=cvs, knot=knots)

    degree = max(1, min(degree, count - 1))
    return cmds.curve(name=name, degree=degree, point=points)


def edges_to_curve(edges=None, degree=DEFAULT_DEGREE):
    """Build one curve per connected run of edges. Returns the curve names.

    edges: edge components (e.g. ['body.e[12]', ...]). Defaults to the
    current selection.
    """
    if edges is None:
        edges = cmds.filterExpand(selectionMask=32, expand=True) or []
    if not edges:
        raise RuntimeError('Select one or more polygon edges first.')

    pairs = _edge_vertex_pairs(edges)
    curves = []
    for verts, closed in _ordered_chains(pairs):
        points = [tuple(cmds.pointPosition(v, world=True)) for v in verts]
        if not closed and points[-1][1] < points[0][1]:
            points.reverse()  # run bottom to top
        mesh = verts[0].split('.')[0].split('|')[-1].split(':')[-1]
        curve = _make_curve(points, closed, mesh + 'Curve#', degree)
        curves.append(curve)
    return curves


def run():
    """Shelf entry point: curve(s) from the selected edges, then select them."""
    cmds.undoInfo(openChunk=True, chunkName='edgeToCurve')
    try:
        curves = edges_to_curve()
    except RuntimeError as exc:
        cmds.warning(str(exc))
        return []
    finally:
        cmds.undoInfo(closeChunk=True)
    cmds.select(curves, replace=True)
    print('Edge To Curve: built %s' % ', '.join(curves))
    return curves
