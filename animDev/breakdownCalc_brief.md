# Breakdown Calculator — Tool Brief

**Status:** Parked (2026-10-06) — design discussion in progress, not yet built.
**Ships to:** mpToolSet (mpAnim shelf) and studio4AnimToolset (studio4Anim shelf).

## Purpose

Teaching tool for working out the timing of breakdowns. A breakdown always sits exactly halfway between two neighbouring poses or contacts. Students drag-select a frame range, and the tool tells them which frames their breakdowns land on.

## Workflow

1. Student selects their controls.
2. Shift-drag selects a frame range in Maya's time slider.
3. Clicks **Calculate**.
4. Tool reads every key on the selected controls inside that range. **Every key in the range is assumed to be a pose or contact** — the student does not mark them manually.
5. Tool calculates the midpoint between each neighbouring pair of keys and displays the breakdown frames.

## Decided

- **Breakdown = exact midpoint** of two neighbouring poses/contacts. No favouring.
- **Sub-frames are fine.** Keys on 1 and 10 give a breakdown on 5.5 — report the true midpoint, no rounding.
- **Frame range comes from the time slider selection** (drag-select), not typed fields.
- **Keys in range = poses/contacts.** No separate pose list or Pose/Contact type in the UI.

## Draft UI (latest)

```
┌─ Breakdown Calculator ─────────────────────────────┐
│  Range: 1 – 49   (from time slider)   [Calculate]   │
├─────────────────────────────────────────────────────┤
│  1     7     13    19    25    31    37    43    49 │
│  ■─────◆─────■─────◆─────■─────◆─────■─────◆─────■  │
│  ■ Pose/Contact   ◆ Breakdown                       │
├─────────────────────────────────────────────────────┤
│  Breakdowns                                         │
│   7     (1 → 13)     [Go]                           │
│   19    (13 → 25)    [Go]                           │
│   31    (25 → 37)    [Go]                           │
│   43    (37 → 49)    [Go]                           │
├─────────────────────────────────────────────────────┤
│  [Add Timeline Bookmarks]                           │
└─────────────────────────────────────────────────────┘
```

- PySide6 window; visual strip drawn with QPainter.
- **Go** jumps the time slider to that breakdown frame.

## Open Questions (pick up here)

1. **Multiple controls with different key frames** — merge all keyed frames (union), or only frames where every selected control is keyed? Leaning: union.
2. **Existing breakdown keys** (Maya's green breakdown-flagged keys) — exclude them from the pose set so re-running doesn't treat breakdowns as poses? Leaning: yes, exclude.
3. **Output** — list + Go buttons + optional timeline bookmarks only, or also an option to set breakdown keys? Leaning: tell students where, don't key for them.
4. **Sub-frame note** — show a hint that sub-frame breakdowns need snapping off / sub-frame display to key?
5. **Inbetween level** — stop at breakdowns, or later add a second split (pose → breakdown midpoints)?
6. **Empty/invalid states** — friendly message when nothing selected or fewer than two keys in range.

## Technical Notes

- Time slider selection: `cmds.timeControl(mel.eval('$tmp=$gPlayBackSlider'), q=True, rangeArray=True)`. End value is exclusive (one past the visible end) — correct for it so keys on the last highlighted frame are included.
- Keys: `cmds.keyframe(ctrls, q=True, time=(start, end), timeChange=True)`; dedupe/sort.
- Breakdown-flagged keys: `cmds.keyframe(..., q=True, breakdown=True)` to identify and exclude.
- Bookmarks: Maya 2024+ timeline bookmarks (`timeSliderBookmark` plugin / `maya.plugin.timeSliderBookmark` API) — confirm availability in 2025/2026.
- `maya.cmds` only, no pymel. Dev-direct tool in `animDev/`, wired via `ANIMDEV_SCRIPTS` in both shelf configs. Icon 256×256 rounded PNG in `shelfDev/mpAnim/icons/`.
