# Smooth Tool — Future Development Notes

## Next session: multiple concurrent smooths in one scene

Requirement: the tool only ever processes one control at a time (no
multi-select batch mode needed), but the *scene* should be able to hold
several independent sets of live preview curves at once — e.g. Create
Curves on ControlA, leave it un-baked, open the tool again for ControlB
without ControlA's curves getting force-deleted.

Current blocker, found but not yet fixed: `smoothTool_ui.py`'s `show()`
uses a single-instance singleton —

```python
_instance = None

def show():
    global _instance
    if _instance is not None:
        try:
            _instance.close()
        except RuntimeError:
            pass
    _instance = SmoothToolUI()
    _instance.show()
    return _instance
```

`closeEvent` deletes that instance's live curves on close
(`smoothTool_ui.py`), so reopening the tool for a second control currently
closes the first window and wipes its curves — directly conflicting with
the "multiple smooths in the scene" requirement.

Planned fix (straightforward, scoped to `smoothTool_ui.py` only):
- Replace the `_instance` singleton with a persisted list (e.g.
  `_instances = []`) so `show()` always opens a **new independent window**
  instead of closing the previous one. Must keep a strong Python reference
  in that list or Qt/PySide will garbage-collect the widget almost
  immediately.
- On `closeEvent`, remove `self` from that list (keeps it from growing
  unbounded over a long Maya session) — the existing per-instance curve
  cleanup in `closeEvent` already only touches that instance's own
  `self._core`, so it doesn't need to change.
- Curve/anim-layer naming already collision-safe for concurrent sessions:
  `create_curves()` names curves from `self.bake_target`, and Maya
  auto-uniquifies + `cmds.curve()`'s return value is captured correctly if
  two sessions ever target the same control; `bake()` already has its own
  `while ... exists` collision loop for layer names.
- Nice-to-have while in there: reflect the current Bake Target in the
  window title (e.g. `Smooth Tool — pCube1`) once Create Curves is clicked,
  so multiple open windows are distinguishable at a glance. Revert to the
  plain title on Reset.

## Vision

Evolve Smooth Tool from a single-control jitter cleaner into a "human IK"
style solve: let an animator **pin** one or more controls in a rig (fixed in
space, or attached to a moving target/path) and have the tool work out
smooth, plausible motion for everything *between* the pins.

Worked example from the brief: pin a foot in place, pin the head to a path,
and have the tool solve smooth torso motion connecting the two — the pins
are hard constraints, the chain in between is where the "smooth" happens.

This is a substantially different problem from what the tool does today, so
treat it as a new capability layered on top of the existing engine, not a
tweak to it.

## Why this is a different problem, not an extension

The current `SmoothToolCore` (`smoothTool_api.py`) is fundamentally a
**single-control signal filter**:

1. Track 3 vertices on a mesh → per-frame world (or parent-local) positions.
2. Run each of the 9 position channels through a 1-D zero-phase Butterworth
   low-pass, independently, in time.
3. Reconstruct a rigid delta from the smoothed triangle and reapply it to
   one control's transform.
4. Bake to one control, on one anim layer.

Pinning + solving a chain is a **spatial constraint-satisfaction problem**,
not a temporal filtering problem:

- A pin changes the *shape* of the chain at every frame (kinematic), not
  just its *smoothness over time* (signal processing).
- Multiple controls have to agree with each other every frame (the torso
  has to actually reach from the pinned hip/root to the pinned head), which
  the current one-control-at-a-time architecture has no concept of.

So: keep `SmoothToolCore` as-is (it's a good, now well-tested building
block for cleaning up jitter), and build the pin/solve feature as a new
layer that can call into it, rather than bolting constraint logic onto it.

## Proposed building blocks

### 1. Pin definition
A pin needs at minimum:
- `control` — the transform being pinned.
- `mode` — `position`, `orientation`, or `both`. (Foot: probably both —
  planted feet shouldn't rotate either. Head-to-path: probably position
  only, let rotation stay driven by the original animation or aim-along-path.)
- `target` — a static point, a curve (path), or another moving object.

### 2. Chain resolution
Given two or more pinned controls, find the ordered list of controls
between them to solve. Two ways to get this, worth prototyping both:
- **Hierarchy walk** — pins are ancestors/descendants of each other in the
  DAG (e.g. foot up through hip, spine, chest, neck, to head); walk
  `listRelatives`/`listRelatives -parent` between them.
- **Explicit user-defined chain** — user selects/orders the controls
  in-between manually (needed for rigs where the "chain" isn't a clean DAG
  path — e.g. two IK legs both needing to reconcile with a pinned COG).

### 3. Solving the pinned pose per frame
Don't reinvent an IK solver if the rig already has one. Two tiers:

- **Tier 1 (reuse the rig's own solvers)** — temporarily constrain
  (`pointConstraint`/`orientConstraint`/`parentConstraint`) the pinned
  controls to locators driven by the pin target (static point, motion path
  on the target curve, or the other object), let the *rig's existing
  IK/FK/spline setup* propagate the result naturally frame by frame, bake,
  then remove the temp constraints/locators. This is the pragmatic default
  — most character rigs (see `boxPerson_003.mb`'s `leg_L_003_IK_CTRL`,
  `poleVectorConstraint` setup, etc.) already have a solver for exactly
  this kind of reach problem.
- **Tier 2 (custom chain solver)** — only needed for chains without a
  usable existing rig solver (e.g. a freeform spine with no spline IK). If
  needed, look at CCD or FABRIK for a lightweight multi-joint solver, or
  temporarily rig a spline IK across the chain, drive its end CVs from the
  pin targets, bake, discard the temp rig. Don't build this until Tier 1
  is proven insufficient for a real case.

### 4. Distributing motion across the chain ("the smooth part")
Once the two ends are pinned/solved, the *shape* of the chain is
determined by the rig, but there may still be jitter/noise to clean up
along the intermediate controls, and/or a need to blend the pinned solve
against the character's original performance so the pin doesn't look like
a hard clamp.

- Reuse `compute_falloff_weights` as a starting point for a **spatial**
  (not temporal) blend weight along the chain — 0 at one pin, 1 at the
  other, adjustable bias/ease — analogous to how `falloff` already tapers
  the temporal blend at the start/end of a frame range.
- Reuse `smooth_channel`/`_filtfilt` per intermediate control to clean up
  any resulting jitter, exactly like today's tool does for a single
  control — this is where the existing engine plugs back in as a
  polish pass after the constraint solve, not before it.

## Open questions to resolve before implementation

- **Position vs. orientation pinning per case** — needs to be a per-pin
  choice (see mode above), not a global setting.
- **Path attachment for a pin** — literal motion path (arc-length
  parameterized, needs a U value driven by time or by the character's
  original head speed?) vs. just "closest point on curve" per frame.
- **What happens to the pinned control's own original animation?** Fully
  replaced by the pin target, or blended (a `blend` slider, same idea as
  today's Strength/Blend, but applied to "how much of the original
  performance survives under the pin")?
- **Multi-pin conflicts** — three or more pins on the same chain (e.g. both
  feet + head) needs a real solve order / weighting strategy, not just a
  pairwise blend.
- **UI shape** — this is a big enough capability that it probably wants its
  own panel/mode rather than being squeezed into the current sliders-and-
  three-buttons layout. Chain selection, per-pin target assignment, and
  per-pin mode are all list-like data, not single values.

## Suggested phased approach

1. **Prototype headless first** (mayapy, like this session's debugging) —
   prove the constrain → let-rig-solve → bake → cleanup pipeline on one
   simple two-pin case (e.g. `boxPerson_003.mb`'s leg) before touching UI.
2. **Single chain, two pins, position-only** — smallest useful version of
   the feature.
3. **Orientation pinning + path targets.**
4. **Multi-pin / multi-chain, and the UI to support authoring pins.**

Keep `smoothTool_api.py`/`smoothTool_ui.py` as the jitter-cleanup engine
throughout; the pin/solve feature should be a new module (e.g.
`smoothTool_pin.py` or a `humanIK/` subfolder under `animDev/smoothTool/`)
that orchestrates constraints + the rig's own solvers + calls back into
`SmoothToolCore` for the cleanup pass, rather than growing
`SmoothToolCore` itself into something it isn't.
