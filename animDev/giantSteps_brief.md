# Giant Steps — Tool Brief

## Purpose

Non-destructive stepped-key workflow. Students convert splined animation to stepped timing without touching the graph editor, and can toggle between splined and stepped freely.

## Workflow

1. Student selects controls and sets a frame range on the timeline.
2. Runs Giant Steps from the mpAnim shelf.
3. UI displays the selected frame range as a visual timeline.
4. Student clicks on the timeline to mark step frames (poses and in-betweens). Spacing can be variable — some on 2s, some on 3s, whatever the motion needs.
5. Student previews the stepped result via playback that only visits the marked frames.
6. When happy, student hits Bake. The tool creates an override animation layer with stepped keys at the marked frames.
7. The splined animation underneath is untouched. The override layer can be toggled off, deleted, or re-done at any time.

## UI

- PySide6 window.
- Custom timeline widget (QPainter) showing the selected frame range.
- Click to place step-frame markers, click again to remove.
- Preview button — plays back only the marked frames in sequence.
- Bake button — creates the override layer.
- Layer name field or auto-naming.

## Technical Approach

- Read selected frame range from the timeline.
- Collect all keyable attributes from selected controls.
- For preview: step through marked frames using `cmds.currentTime()` on a timer.
- For bake: create an override animation layer, key all attributes at each marked frame using values sampled from the splined curves, set all tangents to stepped.
- Works with existing animation layers — the splined animation can already be on multiple layers.

## Notes

- `cmds.playbackOptions(by=)` handles uniform step spacing natively but not variable spacing. Variable spacing needs manual frame-stepping for preview.
- Override layer approach means zero risk to the student's splined work.
