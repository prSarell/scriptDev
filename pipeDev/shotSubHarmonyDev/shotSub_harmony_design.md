# shotSub for Toon Boom Harmony — Design

Companion tool to `pipeDev/shotSubDev/shotSub.py` (the Maya version), targeting
Toon Boom **Harmony** (not Storyboard Pro). This doc captures the design
worked out in discussion before any code was written, and should be kept in
sync with the actual implementation as it evolves.

## What's genuinely different from the Maya tool, and why

The Maya tool's job is mostly playblast management (capture, burn in,
version, review) with a ShotGrid publish step bolted on at the end. Harmony
does almost all of that natively, so this tool's job is much narrower:
**wire up the render, then hand off to ShotGrid** — not re-implement
playblasting, burn-ins, or local versioning.

- **No RV, no rvio encode step.** Harmony's Write node can output an
  H.264-in-`.mov` movie directly (`Movie` checkbox in its Output settings) —
  there's no separate encode pass the way the Maya tool needs rvio for.
- **No burn-in compositing code.** Harmony has a dedicated **Burn-In node**
  (separate from Write) that overlays frame number, timecode, and
  scene/environment/job metadata (`%s`/`%e`/`%j` codes) directly during
  render. It does not support arbitrary free text the way the Maya tool's
  Qt-based burn-in does (no student name/ID, no focal length) — accepted as
  a real capability gap, not something this tool tries to work around.
- **No "low-res preview" tier.** Confirmed a Harmony preview render costs the
  same as a full render, so there's no cheap playblast-equivalent to build
  around — the tool always triggers a real render.
- **No mirrored `scenes/` → `images/` folder structure.** Harmony standalone
  scenes are each self-contained (the `.xstage` plus its own subfolders),
  not subfolders of one shared project the way Maya's `cmds.workspace` gives
  the Maya tool for free. Render output lives relative to the scene itself.
- **No local version folders (`v001`, `v002`...).** Since there's no cheap
  preview tier and Harmony's Write node just produces one movie per render,
  the local artifact is a single file that gets overwritten each time the
  student re-renders (Movie Filename token `%s` = scene name, fixed). No
  publish log, no pruning, no local-version picker. ShotGrid *is* the
  history, from the first render the student decides to send.
- **Standalone scenes, not Harmony Server/Database.** Confirmed this class
  doesn't use Control Center / the Environment→Job→Scene database model —
  same reasoning as most studios and RMIT's own Maya pipeline: that's
  enterprise farm/check-in infrastructure this class doesn't need.

## What's reused as-is

`pipeDev/shotSubDev/shotgridConnect.py`'s actual ShotGrid logic — auth,
`list_visible_projects()`, `list_project_shots()`, `upload_playblast()`
(Version + Note + thumbnail creation, `sudo_as_login` impersonation) — has
**zero** Harmony-specific work to do; it's plain Python. The only thing that
ever coupled it to Maya was `cmds.internalVar(userPrefDir=True)`, used to
find the folder holding `shotSub_config.json`/`shotSub_student.json`. That's
now behind a `_prefs_dir()` helper that tries Maya first (unchanged
behaviour for already-configured student machines) and falls back to a
generic per-user config folder otherwise — **both fixed and verified** in
this session (`pipeDev/shotSubDev/shotgridConnect.py`, dual-copy mirrored
into this folder). This means a student's ShotGrid config and identity file
are **shared** across both tools on the same machine — set up once.

## Architecture: JS front-end + external Python bridge

Harmony's scripting is JavaScript. There's a newer Python interface
(`from ToonBoom import harmony`), but it requires an external Python 3.9.X
on PATH, is documented specifically under Harmony 22 Advanced, and it's
unconfirmed whether it supports a persistent custom tool UI the way JS does
(vs. just an interactive console). Given that uncertainty, **JS is the
front-end**, and it shells out to a small external Python "bridge" script
for the ShotGrid parts, reusing `shotgridConnect.py` unmodified. This is the
standard way studios bridge non-Python DCCs to ShotGrid.

Confirmed via Harmony's own scripting docs (Sources at the bottom):
- `node.type(path)` returns `"WRITE"` / `"COMPOSITE"` for the relevant node
  types; `node.numberOfSubNodes()`/`node.subNode()`/`node.isGroup()` let a
  script walk the whole node tree from `node.root()` to find them regardless
  of nesting or student-given names.
- `node.add(parentGroup, name, type, x, y, z)` creates nodes; `node.link()`
  connects them (exact parameter order not yet pinned down from docs alone
  — confirm against Harmony's own Script Editor before relying on it).
- `render.renderNodes(nodeNameList, fromFrame, toFrame)` renders through
  specific named nodes (not the whole scene), with a `renderFinished()`
  signal — this is what lets the tool trigger a render without the student
  ever touching File > Export > Render Write Nodes.
- `WriteNode.movieDir()`/`movieName()` (read-only accessors) let the tool
  find the rendered file after the fact, whichever node produced it.
- `scene.getStartFrame()`/`getStopFrame()` mirror Maya's
  `playbackOptions(minTime/maxTime)` — the natural default frame range.
- `Process2`/`System` classes launch external processes — confirmed
  mechanism for the JS→Python handoff below.

**Unverified / needs confirming against a real Harmony instance** (no
Harmony install available in this dev environment, unlike Maya where
mayapy let every mechanic get spike-tested headlessly before being relied
on): exact `node.link()` parameter order; whether `Process2` blocks until
the child process exits or is signal-based like `render`; whether the
Burn-In node's properties (see below) are actually scriptable via
`node.setTextAttr()`-style calls or only through its UI panel. The code
below is written against documented fragments and reasonable Harmony API
conventions, but should be treated as a first pass to debug against a real
session, not a finished, tested tool the way the Maya-side work in this
same session was.

## Workflow

1. Student launches the tool (Harmony panel/dialog).
2. Tool walks the node tree, lists every **Composite** node (by type, not
   name — students can and will rename them) in a dropdown/list.
3. Student picks the Composite node whose output is the shot.
4. Student can adjust the frame range, pre-filled from
   `scene.getStartFrame()`/`getStopFrame()`.
5. Student clicks **Create ShotSub**. The tool:
   - Deletes any previous tool-managed Write/Burn-In pair (by the fixed
     names below), so there's never more than one lying around.
   - Creates a Burn-In node and a Write node named `Write_playblast`
     (matching the naming the tool itself looks for/manages), links
     Composite → Burn-In → Write.
   - Configures the Write node per the settings supplied during design:
     Image Sequence **off**; Movie **on**, format `H.264/MPEG-4 (*.mov)`,
     filename token `%s` (scene name, one fixed file, overwritten on
     re-render) — output folder and Movie Options left at Harmony's
     defaults pending confirmation (open item, see below).
   - Calls `render.renderNodes(["Write_playblast"], fromFrame, toFrame)`.
6. On `renderFinished`, the tool reads back `movieDir()`/`movieName()` and
   loads the resulting `.mov` for in-tool preview.
7. If happy, student clicks **Publish ShotSub**:
   - Tool resolves the linked ShotGrid Shot/Asset (same `shotgrid_link.json`
     marker-file convention as the Maya tool, written by an equivalent
     "Link to ShotGrid" action — not detailed further here since it's a
     straight port of `link_to_shotgrid()`'s logic).
   - Writes a temp input JSON (`entity_type`, `entity_id`, movie path,
     notes, fps) and launches `shotgrid_bridge.py` via `Process2`, passing
     that file's path.
   - `shotgrid_bridge.py` imports the bundled `shotgridConnect.py` and
     `shotgun_api3` (see below on why these are vendored, not
     pip-installed) and calls the same publish logic the Maya tool uses,
     writing a result JSON (`success`/`sg_version_id`/`error`) before
     exiting.
   - Tool reads the result and shows success or surfaces the error, the
     same way the Maya tool's `cmds.warning()` does.
8. Tool-managed Write/Burn-In nodes are cleaned up on the *next* "Create
   ShotSub" click (delete-then-recreate) and as a safety net when the tool
   window closes — never left behind indefinitely, but also not deleted
   immediately after a single render, since a student iterating on a shot
   before publishing shouldn't have to pay the node-rebuild cost every time.

## Python bridge interpreter

Rather than depending on a lab machine happening to have Python on PATH
with `shotgun_api3` installed (fragile, and inconsistent with how the Maya
tool already vendors `shotgun_api3` straight into the repo instead of
pip-installing it), the bridge should run under a **bundled/portable Python
interpreter** shipped alongside this tool — set up once, no per-machine
Python-version dependency for the rest of the class's life. Not yet built
in this pass (a real embeddable-Python download/vendoring task, better done
deliberately by whoever owns the lab deployment than guessed at here); the
bridge script itself is written to need nothing beyond the stdlib and
`shotgun_api3`, so it'll run under whatever interpreter is pointed at it
once that's sorted.

## Implementation status

Built in this pass (all in this folder):
- `shotgrid_bridge.py` — the Python bridge. **Tested end-to-end** (input
  parsing, missing-movie handling, and the real `shotgridConnect` call path
  down to a clean "no config file" error) via mayapy as a stand-in Python
  interpreter, since there's no other working Python on this dev machine.
  Confirms the bridge protocol (temp-file JSON in, temp-file JSON out) and
  the `_prefs_dir()` DCC-agnostic fallback both work correctly.
- `shotgridConnect.py` (this folder's copy) + `shotgun_api3/` — dual-copy
  mirrored from `pipeDev/shotSubDev/`. The source copy was modified this
  session: `_prefs_dir()` added (Maya-first, generic-folder fallback,
  **verified both branches**), and `upload_playblast()` gained a
  `movie_path` parameter so a caller with an already-finished movie (this
  tool) skips the JPEG-sequence/thumbnail/rvio-encode path entirely and
  just uploads it directly — also propagated to every other deployed copy
  (`mpToolSet`, `shelfDev`, `studio4AnimToolset`) so the Maya tool keeps
  working unchanged.
- `shotSub_harmony.js` — the Harmony-side tool. **Not tested at all** — no
  Harmony instance was available in this environment, unlike Maya where
  mayapy let every mechanic get verified headlessly before being relied on.
  Every Harmony API call is written against documented scripting
  references (see Sources), but several specific calls are placeholders
  flagged `// VERIFY` inline rather than confirmed behaviour. Structural
  sanity only: brace/paren/bracket balance checked (no JS engine available
  to actually parse/run it).

## Open items (explicitly unresolved, flagged rather than guessed)

- **Write node attribute keywords** (Image Sequence on/off, Movie on/off +
  format, Movie Folder/Filename) — Toon Boom's docs don't enumerate
  WriteNode's settable attributes at all. `shotSub_harmony.js` ships
  `shotSub_dumpNodeAttributes()`, a discovery helper built on the
  high-confidence, generic `node.getAttrList()` call: manually build a
  Write node configured exactly like the design screenshot, run that
  helper against it, and read the real keywords back from the Message Log.
  `WRITE_NODE_ATTRS` at the top of the file currently holds placeholder
  guesses — replace them with what that helper reports before trusting
  `shotSub_configureWriteNode()`.
- **`node.link()` exact parameter order** — used with the commonly-cited
  Harmony convention (`outNode, outPort, inNode, inPort, replace, force`),
  not confirmed from docs.
- **`Process2` blocking vs. signal-based**, and its exact constructor/
  signal names — written assuming a `.finished` signal (parallel to
  `render.renderFinished`) so a slow ShotGrid upload can't freeze Harmony's
  UI thread if the assumption is wrong in the blocking direction; needs
  confirming.
- **Burn-In node's exact type string** (`"BURN_IN"` used as a placeholder)
  and whether its display fields are scriptable at all or only configurable
  through its own UI panel.
- **`scene.currentProjectPath()`** as "this scene's own folder" for a
  standalone (non-database) scene, and the exact calls for launching the
  OS default video player (`System.launch`) and platform detection
  (`about.isWindowsArch()`) — all placeholders pending a live session.
- **Movie Folder / Movie Options**: the screenshot showed Movie Folder as
  `frames` and Movie Options left at Harmony's defaults — not yet confirmed
  whether `frames` is meant literally or was just whatever Harmony defaulted
  to, and whether default H.264 compression settings are acceptable or need
  pinning (the way the Maya tool pins `quality=90`/`percent=100`).
- **Python bridge interpreter deployment** — the portable/embeddable Python
  bundling described above hasn't been built; `shotSub_resolvePythonExecutable()`
  currently falls back to a bare `python` on PATH plus an env-var override,
  a stopgap for local testing only.

## Next step

Everything Python-side is real, tested code. Everything Harmony-side needs
one hands-on pass in an actual Harmony session to work through the VERIFY
list above — expect to be debugging `shotSub_harmony.js` against the live
Script Editor console (checking return values, correcting attribute/signal
names) rather than finding it works on the first try, the same way any
first draft against an undocumented-in-places API would.

## Sources consulted

- [Harmony 21 Scripting Interface: node Class Reference](https://docs.toonboom.com/help/harmony-21/scripting/script/classnode.html)
- [Harmony 24 Scripting Interface: render Class Reference](http://docs.toonboom.com/help/harmony-24/scripting/script/classrender.html)
- [Harmony 20 Scripting Interface: WriteNode Class Reference](https://docs.toonboom.com/help/harmony-20/scripting/script/classWriteNode.html)
- [Harmony 21 Scripting Interface: scene Class Reference](https://docs.toonboom.com/help/harmony-21/scripting/script/classscene.html)
- [Harmony 22 Premium Documentation: Burn-In Node](https://docs.toonboom.com/help/harmony-22/premium/reference/node/generator/burn-in-node.html)
- [Harmony 22 Premium Documentation: About Scripting](https://docs.toonboom.com/help/harmony-22/premium/scripting/about-scripting.html)
- [Harmony 22 Advanced Documentation: Python Script Console View](https://docs.toonboom.com/help/harmony-22/advanced/reference/view/python-script-console-view.html)
