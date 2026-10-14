# Smooth Tool — Future Development Notes

## Face Smooth redesign + MetaHuman import timing (planned 2026-10-14)

Not started — design only. Needs a real test file before building (see
"What's needed to start" at the end).

### Where Face Smooth stands today

Checked headlessly in mayapy 2025:

- **Bake is correct.** Baked values exactly match the smoothed result in
  every mode: additive layer (default), override layer and base. Also
  with the control already on another layer, another layer selected,
  namespaced MetaHuman-style names, and non-unique names.
- **Performance** at 60 controls × 600 frames: sample 0.2s, Create Curves
  0.1s, **one slider tick 0.6s**, Bake 4.4s. Sliders recompute and redraw
  every curve on each `valueChanged`, so dragging lags on a full face
  board. On a real MetaHuman, sampling will be slower too (`currentTime`
  per frame evaluates the whole face rig).

### Why the current approach is wrong for face controls

1. **The viewport trajectory curves can't show the jitter.** Most face
   board controls are single-translate sliders. Their "trajectory" is one
   line drawn over itself many times, and the jitter is in the spacing of
   frames along that line, not the shape. Even on 2-axis controls it's
   mostly timing. Value over time is what matters, and the Graph Editor
   already shows that.
2. **The smoothing is weak and blunt.**
   - `_strength_to_cutoff` maps strength to a cutoff relative to Nyquist
     of the *sampled frames*, not to real time. The default (strength 1)
     is a cutoff of 0.46 × Nyquist. On 60fps capture that only removes
     motion faster than about 14Hz, and most of the jitter is slower.
   - The 2nd-order Butterworth (4th order effective with filtfilt) has a
     soft rolloff. Pushing it hard enough to kill jitter also rounds off
     peaks and accents (smile apexes, brow hits) before the noise is gone.
   - It treats everything as one signal. Jitter is small and fast; blinks,
     lip contacts and plosives are fast but large. A low-pass can't tell
     them apart.
3. **It samples on whole frames,** throwing away native-rate data (see the
   import section below), and **a base-layer bake leaves the subframe keys
   in place** between the new whole-frame keys. You don't see them at 24fps
   playback, but the jitter is still in the curve: it shows in the Graph
   Editor and in anything that evaluates between frames, like motion blur.

### Design goal

Strike a balance between keeping the **flow and overall character** of the
curves and pulling out jitter, so the feel of the performance survives.
It also needs to be **much more powerful** than the current smooth. Think
of the motion in three layers:

| Layer | What it is | Treatment |
|---|---|---|
| Flow | Overall shape and timing of the performance | Always kept |
| Character | Accents, holds, micro-expressions | Kept; optional softening |
| Jitter | Small, fast frame-to-frame noise | Removed |

### Proposed Face tab

1. **Drop the viewport curves. Preview on the rig through a temporary anim
   layer.**
   - Create Curves becomes Preview: it writes the result to a preview
     layer, so you judge the feel by watching the face.
   - **Blend = layer weight.** Instant, no recompute. This works for both
     additive (delta × w) and override (orig + w(s − orig)) layers.
   - Strength/Falloff recompute on slider release (or a short debounce
     timer), not on every tick.
   - Keys are written in bulk through `maya.api.OpenMaya` (`MFnAnimCurve`),
     not one `setKeyframe` per value.
   - A "Show original" toggle mutes the layer, and a button frames the
     controls in the Graph Editor for comparison.
   - Bake keeps or merges that layer, so there's no second pass.
2. **Jitter slider: an edge-preserving (temporal bilateral) filter.** It
   smooths small frame-to-frame wobble and leaves large, fast moves alone.
   The threshold is estimated per control from its own noise level (e.g. the
   median absolute deviation of its frame-to-frame second difference), so the
   default is sensible per control. This is where the extra power comes from:
   it can be aggressive on noise without touching accents.
3. **Flow slider: gentle overall softening.** Use a steeper low-pass (higher
   order Butterworth) set in **Hz**, from the scene/source frame rate, so it
   behaves the same at 24, 30 or 60fps. A steep filter removes what's above
   the cutoff without dulling what's below it.
4. **Clamp to each control's translate limits.** Bilateral filters can
   overshoot, which would push a 0–1 board slider past its range.
5. Later: per-region strength (eyes vs mouth usually want different
   amounts).

Keep the existing Smooth and FK Chain tabs as they are.

### Tuning method

Prototype the filters headlessly on real capture, and compare them with
numbers before building UI: jitter removed (high-band energy), and peak
height and timing kept on accents, blinks and lip contacts. Build the tab
around whichever approach holds the character best.

### Frame rate: 60fps capture into 24fps scenes

The iPhone/MetaHuman capture is 60fps, but the shots are 24fps. 60/24 = 2.5,
so the subframe keys seen after import (0, 2.5, 5, 7.5…) are the original
60fps samples sitting at their real times. Nothing has been lost at that
point.

Converting badly is what causes the problems:

- **Nearest-frame picking** alternates 2- and 3-capture-frame gaps. That's
  ±1/120s of timing error every other frame, which shows up as a
  frame-to-frame spacing zigzag on moving sections. It's created by the
  conversion, and it's worst where the face moves most.
- **Sampling on whole frames without filtering first** folds 12–30Hz noise
  down into slower wobble that looks like real motion. No 24fps smoothing
  can cleanly separate that from the performance afterwards.
- **Lip sync timing is not off.** Subframe keys sit at their true times, so
  every 24fps frame shows the mouth exactly where it was at that moment.
  The real risk is **contacts**: 24fps frames are about 42ms apart, and a
  B/P/M closure can last 17–33ms (1–2 capture frames). If it falls
  between frames, no rendered frame shows the lips fully closed, which
  *feels* like bad sync. (Separately, if a performance feels uniformly early
  or late, check start frame/timecode alignment with the audio. That's a
  constant offset, not a frame-rate issue.)

**Decision: the 60 → 24 conversion belongs in the import tool, not in Face
Smooth.** Face Smooth then works on clean 24fps data and only has to
handle jitter vs character.

### Import tool changes (`metahuman_facial_transfer/metahuman_api_25.py`)

The importer works from `metahuman_facial_transfer/` (dev-direct; synced to
`mpToolSet/mpAnim/scripts/` and `studio4AnimToolset/studio4Anim/scripts/`).
Current timing behaviour in `retarget_metahuman_animation_sequence`:

1. Imports with `FBXImportSetMayaFrameRate False`, then sets the scene to
   `timeunit='ntsc'`, which is **30fps**, not 24. Maya keeps keys at their
   real times through unit changes, so after switching to 24 the 60fps keys
   land 2.5 frames apart.
2. **Controls are handled inconsistently:**
   - Single-expression controls are copied with `copyKey`/`pasteKey`, so they
     **keep native 60fps subframe keys**.
   - Multi-expression controls (combined through `blendWeighted`, e.g.
     bidirectional sliders) are baked with `bakeResults(sampleBy=1)` on
     whole frames, **with no filtering first**. That's the bad conversion
     described above.

Planned "Convert to scene rate" step at the end of the transfer:

- A **target frame rate** option, defaulting to 24 for classes, replacing the
  hard-coded `ntsc`.
- **Bake the multi-expression controls at native rate** (sample at the
  source key spacing, or evaluate the curves at the native key times), so
  every control starts from true 60fps data.
- For every face control: read native key times/values, **detect the source
  rate** from the key spacing, **filter out what 24fps can't represent** (low-pass
  below the target Nyquist), then sample on whole frames with **contact
  protection**: find the real extremes in the mouth/jaw channels (closures,
  peaks) and make sure each lands on a whole frame. Write whole-frame keys and
  **remove the subframe keys**.
- Make it runnable on its own on keys already in a scene, so shots that
  have already been imported can be fixed without re-importing.

### What's needed to start

- An Unreal FBX export (Animation Sequence route), ideally with dialogue,
  blinks and a stretch of bad jitter.
- The Maya MetaHuman file it imports into, or at least the face board
  controls. A 60fps original as well as a 24fps result is ideal for
  comparison.

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
