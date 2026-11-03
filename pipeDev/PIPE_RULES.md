# Pipe rules: read before changing the pipe

These are the standing rules for the film pipeline (`pipeDev/`, the
mpPipe / mpLayout / mpModel shelves). They apply to everyone, people and
Claude sessions alike. The **why** behind each one is in
`filmPipeline_spec.md`. The current review and Stage 2 direction are in
`pipelineReview_stage2.md`.

If a rule here gets in the way of a fix, **stop and ask the project lead**
(the repo owner). Don't work around it.

## Locked: change only with the project lead's explicit say-so

1. **The departments**, in this order: **Modeling, Rigging, Creature,
   LookDev, Layout, Animation, FX, Lighting**. They're defined once, in
   `publishDev/publishTool_api.py` `DEPARTMENTS`. Environment is **not** a
   department: environments are modelled, and an environment publish is a
   Modeling publish.
2. **Build's dropdowns** (Add to list, Build into, and what each
   department offers: `BUILD_FOR` in `buildDev/buildTool_api.py`). If
   something doesn't show up in Build, fix it where it was made (how it
   was published), or ask. Never widen or reshape the dropdowns to make it
   appear.

## Design rules (the pipe's backbone)

3. **H holds only publishes** and is the source of truth. Nothing saves to
   H except Publish.
4. **Build is the only way in, Publish is the only way out.**
5. **The ShotGrid entity defines the thing; the folder decides where it
   goes.** Working file names are free; Publish names the output.
6. **Iterative and Final are the same publish.** Approval only adds that
   department's caches and outputs.
7. **Unpublished work is the student's job.** An iterative publish is how
   work moves between machines.
8. **Paths work from any drive** via `$PIPE_SCRATCH`. Never hard-code a
   drive letter; H and scratch are settings.
9. **Refuse, don't warn, when a student goes off-pipe**, and give them a
   button that fixes it. (Exception, still OPEN: Publish's scene-vs-project
   check only warns.)
10. **Film-specific choices go in data** (`pipeline.json`, `rig_rules.py`),
    not in code.
11. **Build for the shared-server target.** H may be the T7 stand-in, a
    **SharePoint** library, or a **real server** (UNC path such as
    `\\server\share`). Swapping one for another must be a settings change
    only. See "Storage targets" below.
12. **Published files are clean**: no namespaces, no unused shaders, in a
    stamped pipe group, read-only.
13. **Publish refuses scenes with unknown script nodes**, so an infected
    student scene can't reach the shared H.

## Storage targets

The pipe must work with H on any of these. Code that touches files on H
must not assume one of them.

| Target | Path looks like | Watch out for |
|---|---|---|
| T7 stand-in (NTFS) | `G:\H` | the reference setup today |
| Server (SMB share) | `\\server\share\H` or a mapped letter | UNC paths have no drive letter; permissions set by IT, not by read-only flags; many students writing at once |
| SharePoint (OneDrive sync) | `C:\Users\<you>\<Org>\<Site> - Documents\H` | sync lag (two people taking the same `v###`); files-on-demand placeholders; read-only flags and creation times may not survive sync; path length limits; Studio Library's shared `database.json` |

Code that already depends on storage behaviour:
- hardlinks for rigs (`buildTool_api.link_version`). These are made on
  scratch, so they only matter if scratch itself is ever on a server;
  Build falls back to a copy;
- read-only locking (`_lock`, `_lock_publish_folder`);
- "latest" by creation time (`buildTool_api.publish_time`);
- version numbering (next free `v###`);
- Studio Library backup/restore (`pipeStudioLibrary`).

Hand tests for each target are in `handTests.md` section K.

## Working rules

- **Branch and pull request.** Never push to `main`; it's protected. One
  branch per task, e.g. `pipe/rollback-default` or `test/handtests-c`.
- **Run the tests before opening a PR**: `mayapy pipeDev/run_tests.py`.
  Say in the PR how many passed.
- **`mpToolSet/` and `studio4AnimToolset/` are student releases.** A
  change there is published to students when it's merged. Only touch them
  when the task is a release, and say so in the PR.
- **The pipe never goes into `mpToolSet/` or `studio4AnimToolset/`.**
- **Never commit credentials.** ShotGrid keys live in
  `shotSub_config.json` / `mpPipe_desktop.json`, which are gitignored.
  Send them privately.
- **Don't open student scene files you haven't checked.** Scan `.ma` / `.mb`
  for script nodes first (some carry the `maya_secure_system` and
  `vaccine` scene viruses).
- **Keep the docs honest.** New decisions go in `filmPipeline_spec.md`
  labelled DECIDED / OPEN / SUGGESTION, and to-dos go in GitHub Issues or
  `pipelineFollowUps.md`.
- **Use `maya.cmds` and PySide6 / shiboken6.** No pymel, no PySide2. Code
  must run in Maya 2025 and 2026.
