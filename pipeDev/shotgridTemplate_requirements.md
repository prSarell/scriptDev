# ShotGrid template requirements

What a film's ShotGrid project must have for the pipeline tools (Publish,
Build, shotSub) to work. The goal is a reusable project template, so every
new film starts ready for the pipe. Started 2026-10-19; reference project is
*Not Worth Fixing* (id 157). Design detail and history live in
`filmPipeline_spec.md`; this file is just the checklist.

The task itself (designing and building RMIT's ShotGrid Template Projects,
one per class archetype, with Andy) is planned in the tech notes,
`assetPipelineDev/rmit_pipeline_tech_dev.rtf` §14 "Class Project Setup
Tool" and §15 "Confirmed Phase 1 workflow". This file collects what those
templates must contain for the film pipeline.

Existing Template Projects on the site (read 2026-10-19): ShotGrid's stock
ones (Animation, Film VFX, Game, etc.) plus **MP Solo 3D Student Template**
(id 487), already made for major projects. Worth checking against this list
before building new ones.

Labels: **REQUIRED** (tools depend on it), **DECIDED** (agreed, tools not
built yet), **SUGGESTION** (not agreed), **OPEN**.

## Project

- **REQUIRED** One ShotGrid Project per film. Its id goes in
  `<H>\<FILM>\pipeline.json` (`shotgrid_project_id`), which is how the tools
  find it.
- **REQUIRED** Students are added to the project. Not on the project = no
  access to that film's tools; there's no fallback (spec §4, 2026-10-13).
- **REQUIRED** Each person's ShotGrid login matches their RMIT login, which
  is how the tools know who is publishing (spec §4, 2026-10-13).
- **Agreed in principle 2026-10-19 (site-wide, not per project):** a
  staff/student **number** field on every person (HumanUser), used to
  identify people instead of their emails. **Created 2026-10-19** as
  **RMIT ID** (`sg_rmit_id`, text); 46 filled (students from their emails,
  plus one staff member). Remaining staff and non-RMIT-login students need
  theirs entered. See spec §4 "Staff problem".
- **REQUIRED** A script user (API key) that can create Versions, upload
  movies, and act on behalf of the student (`sudo_as`). Set up per machine
  in `shotSub_config.json`, never in the template or the repo.

## Shots

- **REQUIRED** Sequences and Shots exist before work starts, named with the
  codes used for folders as-is (`EAP_010` / `EAP_010_010`). Tools match
  folders to ShotGrid by these codes.
- **DECIDED 2026-10-19** Every animated shot has two Animation-step tasks:
  **Blocking** and **Final**. Approved Blocking = no cache; approved
  Final = cache.
  - Done on NWF 2026-10-19: 75 shots × 2 tasks. `EAP_010_FULL_CUT` (the cut
    reference shot, not animated) was left out.
- **DECIDED 2026-10-19** Every animated shot also has a **Layout** task
  (Layout step), before Blocking. Approved Layout → shot camera publish.
  Created on NWF's 75 shots 2026-10-19, so each shot now has Layout,
  Blocking, Final.
  - OPEN: what layout publishes besides the camera; whether a camera
    change after layout needs re-approval; who does layout.
- **For the RMIT templates:** drop the **Roto** and **Online** steps
  (user, 2026-10-19). Steps are shared by the whole ShotGrid site, so in
  practice that means hiding them in the template project's settings
  rather than deleting them.
- OPEN: how a template tells "reference" shots like `*_FULL_CUT` apart from
  animated ones (naming convention today; could be the Shot `Type` field).
- OPEN: who is assigned to Blocking/Final, and whether it's always the same
  person for both.

## Assets

- **REQUIRED** Every pipeline asset exists in ShotGrid before it's
  published. Publish refuses an asset folder with no matching Asset.
- **REQUIRED** Asset codes are unique once turned into folder names
  (camelCase: `Scout's House` → `scoutsHouse`). Look-alikes make Publish
  refuse.
- **REQUIRED** Asset `Type` uses the values that match the asset folders:
  Character / Environment / Prop / Vehicle. OPEN: where `Graphic` assets go.
- **Class projects (DECIDED 2026-10-19):** Sequences = assignments, Shots =
  each student's work on an assignment, Assets = lecturer-provided, created
  in ShotGrid and published with the Publish tool. Students don't create
  assets in a class.
- **DECIDED 2026-10-20** Assets get a **LookDev** task alongside Modeling.
  The model publish carries only low-res placeholder textures (for rigging
  and animation); a separate **LookDev publish** carries the render
  textures and shaders (spec §4 "LookDev is its own step and publish").
  - OPEN: a task on the Modeling step or its own LookDev step (check
    whether the site already has a Look Dev / Surfacing step to reuse);
    which asset types get it (all, or only ones that are rendered); who is
    assigned.
- The Asset id is an asset's identity: stamped into every publish
  (`publishInfo` node, spec §3) and used by shot publishes to tell a
  published asset from something made in the shot.

## Versions

- **REQUIRED** Version status list includes **Approved** (`apr`). For now
  "approved" means final (2026-10-19).
- **DECIDED 2026-10-19** Shot Versions are linked to their Task
  (`sg_task`: Blocking or Final). Review Versions come from **shotSub**, so
  shotSub sets the task. Publish refuses a shot with no Approved Version
  (DECIDED 2026-10-19), and makes caches only for an Approved Version on the
  Final task. Not built: shotSub doesn't set it yet, and none of NWF's 738
  Versions has a task today.
- Versions are a record of publishes; the tools never look things up by
  Version (spec §3, "The ID rule").

## Not needed

- No Shot -> Character links or mocap flag for the Studio Library folders:
  every character gets keyframe + mocap folders in every shot (DECIDED
  2026-10-21, spec §4b). Only the film's Character assets are read.

- No new entities for cameras, caches or keyframes: they're identified by
  Shot/Asset id + department + version (spec §3, "The ID rule").
- Students never have to create anything in ShotGrid for the tools to work.
