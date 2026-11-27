# Build: how work comes into a scene (brief, 2026-11-27)

**Status:** DECIDED by the project lead on 2026-11-27. Not built yet: the
Maya Build tool still has the old "Build into" row until this is done.

**Who this is for:** anyone building the film pipeline's tools, in Maya now
and in Houdini next (then Unreal, maybe Blender). It describes **what Build
must do**, not how Maya does it, so it can be built the same way in any
program. Maya details are marked *Maya today*. Houdini notes are
suggestions for the Houdini team to confirm or replace with how they work.

If you're using Claude to help build a tool for another program, give it
this file, `PIPE_RULES.md` and how your team builds tools in that program.
Ask it to follow this brief and to ask the project lead before changing any
decision in it.

---

## 1. The pipe in one page

You need these to read the rest.

**Two drives.**

| Drive | What it is | What goes there |
|---|---|---|
| **H** | The shared drive (server, SharePoint or a USB stand-in). The source of truth for the whole film. | **Only publishes.** Nothing is saved to H except by Publish. |
| **Scratch** | The student's own local drive: a sandbox. | Their working files, plus copies of the publishes they use. |

Scratch has the **same folder layout as H**, 1:1. Drive letters are never
hard-coded: H and scratch are settings, and paths inside scenes go through
an environment variable, **`$PIPE_SCRATCH`** (the scratch root), so a scene
opens from any drive.

**Two tools, one way in and one way out.**

- **Build** is the only way published work comes **into** a scene.
- **Publish** is the only way work goes **out** to H.

**Folder layout** (H and scratch the same):

```
<film>\<app>\assets\<type>\<asset>\scenes\<department>\<login>\
<film>\<app>\sequences\<SEQ>\<SHOT>\scenes\<department>\<login>\
```

For example, an animator's folder for shot SEQ010_120 is
`NWF_SHF\maya\sequences\SEQ010\SEQ010_120\scenes\anim\e131988\`.

- **Departments** (locked, in this order): Modeling, Rigging, Creature,
  LookDev, Layout, Animation, FX, Lighting. Folder codes: `model`, `rig`,
  `creature`, `lookDev`, `layout`, `anim`, `fx`, `lighting`.
- **Login** is the student's ID (e.g. `e131988`). Everyone has their own
  folder, so nobody overwrites anyone else.
- **Published names** are set by Publish:
  `<asset or shot>_<login>_<code>_v###`, e.g. `scout_e131988_rig_v003.ma`.
  Published files are read-only and never change after publishing. A fix
  means a new version.
- **Latest** means the newest version by time, across everyone.
- **Caches** live in the shot:
  `<shot>\cache\<alembic|usd|fbx>\<department>\<login>\`.

**Handing files between programs** (rule, 2026-11-24) uses the receiving
program's folder:

```
<film>\<receivingApp>\<assets\<type>\<asset> | sequences\<SEQ>\<SHOT>>\<login>\from<SourceApp>\<name>_v###.<ext>
```

---

## 2. What Build does

Build has **one list** and one button.

- **Add to list:** pick anything published (film, asset or shot, the
  department that **published** it, then the item) and press **+**. Press
  **−** to take rows off. The list is exactly what the student wants
  loaded.
- **Build** loads the ticked rows into the **open scene**.

There is **no "where am I building / which department am I" step.** That
was the old "Build into" row, now removed.

### The rules

1. **Build doesn't depend on the program's project setting.** It loads the
   list into the open scene whatever the project is, or with none set.
   The **student saves** the scene where it belongs. **Publish** uses the
   project to know where to publish. That's Publish's job, not Build's.
   *Why:* it leans on the program's own workflow and keeps students
   accountable for where they save.

2. **The shot (or asset) comes from where the open scene is saved.** A
   scene saved in `...\SEQ010_120\scenes\anim\e131988\` is in shot
   SEQ010_120. **An untitled scene has no shot.**

3. **Every department sees every asset, any time.** The department you
   pick in Add to list only says **which publish you mean**: scout's
   **rig** versus scout's **model**, or a shot's **camera** versus its
   **cache**. It never limits what you can load.

4. **One shared list per shot (or asset), the same for every
   department.** It's saved on H with the shot, so everyone who opens a
   new scene in that shot starts from the same list. + and − change it. An
   untitled scene starts with an empty list.
   *Stored at:* `<shot or asset>\data\build\build_list.json`, holding the
   list of items, each written `<type>/<asset>/<department code>`, e.g.
   `character/scout/rig`, `character/scoutrig/cache`,
   `camera/SEQ010_120/cam`. *Maya today* still has one list per
   department (`anim.json`, `lighting.json`...). These are merged into the
   shared list the first time a shot is opened, so nothing is lost.
   *OPEN:* this list is the one thing Build writes to H, which doesn't
   sit well with "H holds only publishes". To be settled before it's built.

5. **Publishes are copied to scratch before they're used, never read live
   off H.** H may be a slow network share. Build copies each version once
   into a film-wide mirror of H on scratch (`<film>\<app>\publish\...`,
   same sub-paths as H), and the scene reads it from there through
   `$PIPE_SCRATCH`.

6. **The shot keeps a record of what it uses.** When the scene is saved in
   a shot, Build notes in that shot what it pulled: which version, by
   whom, from where, and when. This drives "what's in this shot", "up to
   date / newer version available" and clearing versions no shot uses any
   more.
   *Stored at:* `<shot>\assets\build_manifest.json` on scratch.
   *Untitled scene:* nothing is recorded until it's saved into a shot and
   built again.

7. **Rigs in a shot go through one fixed name per shot.** In a scene saved
   in a shot, a rig is loaded through
   `<shot>\assets\<type>\<asset>\rig\<asset>_rig.<ext>`, a link (hardlink,
   or a read-only copy where links aren't possible) to the real version.
   Updating the rig re-points the link, so every scene in that shot gets
   the new rig, and one shot can be rolled back on its own. In an untitled
   scene the rig loads straight from the version file, and building again
   after saving into a shot switches it to the shot's link.

8. **Caches are imported, fully editable, in every department.** An
   animation cache (Alembic or FBX) is brought **into** the scene (not
   linked or referenced), in its own group and namespace, still reading
   its data from the scratch copy so the scene stays small. A newer
   version re-points the same nodes. USD caches load as a USD stage.
   *Why:* "the point of the cache is that they are editable".

9. **A cache wears the newest LookDev look.** If there's no LookDev look,
   it wears the look of the rig the cache was made from.

10. **Keys column: roll back animation from the scene's own shot.** Each
    rig row can load an older published animation version from the
    scene's shot. To use another shot's animation, add it from that shot
    with Add to list. If that brings in a second rig, move the keys across
    with Studio Library (or the program's own tool).

11. **Build never changes the project and never refuses over it.** The
    scene-vs-project check (a red banner) lives in Publish only.

---

## 3. In Houdini (suggestions for the Houdini team)

These map the rules onto Houdini terms. They are **not decided**: confirm
or replace them with how your team works, and take any change of rule to
the project lead.

| Rule | Maya today | Houdini, possibly |
|---|---|---|
| Scratch path in scenes | `$PIPE_SCRATCH` in reference / file paths | `$PIPE_SCRATCH` set in `houdini.env` or at startup; Houdini expands `$VAR` in file parameters natively |
| Project setting (rule 1) | Maya project (`workspace.mel`) | `$JOB`. Build ignores it; Publish uses it |
| Where the scene is saved (rule 2) | the open scene's path | `$HIP` / `$HIPFILE` |
| Loading a publish | file reference, in a namespace and a pipe group | a File / Alembic SOP, a USD sublayer or reference in LOPs, or an HDA. One node per row, named after the item |
| Imported cache (rule 8) | Alembic import, AlembicNode re-pointed for a new version | Alembic SOP or USD reference whose file parameter points at the `$PIPE_SCRATCH` path; a new version changes that path |
| Rig link (rule 7) | fixed-name reference | probably not needed (rigs rarely go into Houdini); character data arrives as caches |
| Program folder | `<film>\maya\...` | `<film>\houdini\...`, same layout below it |
| Departments, list, manifest | as above | the same files, shared with Maya: one list per shot, whatever program built it |

**Questions for the Houdini team to bring back:**

- Should Houdini read and write the **same** shot list and manifest as
  Maya (one list per shot across programs), or keep its own per program?
- What does a Houdini **publish** look like (geometry caches, HDAs, USD
  layers), and in which department folders?
- Does Houdini need anything from Maya beyond caches and cameras (the
  `from<SourceApp>` hand-off folders)?

---

## 4. Words used here

- **Publish:** a versioned, read-only file on H made by the Publish tool.
- **Pull:** copying a publish from H to scratch's publish mirror.
- **Build list:** the rows in Build. The shared list per shot is the saved
  starting point.
- **Manifest:** a shot's record of which versions it has pulled.
- **Look:** a published set of materials and assignments for an asset.
- **Iterative / Final:** two states of the same publish. Final also writes
  that department's caches and outputs.

Background and the history of each decision: `filmPipeline_spec.md`
(§4n for this brief). Standing rules: `PIPE_RULES.md`.
