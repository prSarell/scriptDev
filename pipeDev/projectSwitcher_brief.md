# Project switcher — brief

Working name only (no name chosen yet). A **new tool**, to develop
alongside the Publish/Build tools. Started 2026-10-19. A variation on Jiffy
Schedule (`timeManagementDev/jiffyScheduleDev/jiffySchedule.py`), which
also needs integrating into the pipe soon.

Private like the rest of the pipeline tools (see `filmPipeline_spec.md`):
not for the public toolsets until the user says so.

## Where it fits in the workflow (user, 2026-10-19)

1. **Staff set up the project.** A staff member creates a class or major
   project on ShotGrid using the desktop tool (not developed yet: the Class
   Project Setup Tool, tech notes
   `assetPipelineDev/rmit_pipeline_tech_dev.rtf` §14-15). When the ShotGrid
   project is created, the desktop tool:
   - builds the folder structure on the **H drive**;
   - assigns the students to the ShotGrid project.
2. **The student starts work.** The student opens Maya with an **empty
   scratch drive**. This tool:
   - sees **ShotGrid** (what the student is assigned to) and the **folder
     structure on the H drive**;
   - when the student selects something (e.g. the asset `backpack`) to set
     the project, **builds that project's folder structure on the scratch
     drive** and sets the Maya project, so the student can start work.

What it's for:
- **Starting a project when no assets exist yet**: nothing has to be on
  scratch, and nobody has to have published anything.
- **Switching easily** between shots, assets, etc., without opening Maya's
  Project window and clicking through folders.

## Jiffy Schedule today (for comparison)

- Jiffy Schedule **does not create projects.** Students manually add
  projects that **already exist**.
- It was looked at earlier as the way to set projects for this purpose, but
  that couldn't be done without ShotGrid up and running.
- It needs substantial reworking but is still useful. In the rework, the
  manual "add existing projects" is replaced by Jiffy seeing the projects
  the student is assigned to on ShotGrid.

## What already exists in the pipe

- Every asset and shot is its own Maya project (spec §3f), on H as
  `<H>\<FILM>\maya\assets\<type>\<asset>\` and
  `<H>\<FILM>\maya\sequences\<SEQ>\<SHOT>\`, each with `workspace.mel` and
  the standard Maya folders.
- **Build never creates scratch projects** (checked 2026-10-19): it only
  lists shots already on scratch, and its Set Project button
  (`buildTool_api.set_maya_project`) only works on those. The NWF scratch
  shots were made by one-off scripts. In the workflow above, Build's job is
  only pulling publishes into a project this tool has already made.
- Reusable code: `buildTool_api.list_films()` / `list_shots()` and
  `publishTool_api.list_h_assets()` read films, shots and assets from H;
  `shotSubDev/build_student_shot_projects.py` creates Maya projects (same
  `workspace.mel` and default folders as File > Project Window).

## DECIDED (2026-10-19)

- "Assigned to" comes from ShotGrid.
- The tool builds the project on scratch when it isn't there yet, for the
  pipe to populate.
- **Whole film, theirs highlighted.** The list shows every asset and shot
  in the film; the student's ShotGrid assignments are highlighted, not used
  as a filter. Any of them can be set as the project.
- **Builds the student's scenes folder too:** the empty Maya project
  (folders + `workspace.mel`) plus `scenes\<login>\`, ready to save into.
  Nobody's publishes are copied (that stays Build's job).
- **Why access to everything (user):** in most major projects one student
  makes a whole film on their own, so they see everything anyway. The pipe
  is what stops students saving over each other's work (personal folders,
  read-only publishes), so access to everything lets students work flexibly
  without a teacher having to over-manage assignments in ShotGrid.
  - Access is still per film: a student only sees films whose ShotGrid
    project they're on (spec §4, "Not assigned = no access").

- **Top level = the student's ShotGrid projects (user, 2026-10-19):** e.g.
  a student on a major project and on a class can choose between those two
  at the top of the tool, and sees all the Maya projects connected to the
  chosen one listed below.
  - Each ShotGrid project maps to its H-drive folder (for films via
    `<H>\<FILM>\pipeline.json` → `shotgrid_project_id`).

  - **Filtered by project:** e.g. a student on Chimera and
    3DcharacterPerformance sees both at the top, but only the contents of
    the one selected, never everything across all projects at once.
- **Class projects (user, 2026-10-19), e.g. 3DcharacterPerformance:**
  Sequences = assignments; Shots = each student's work on an assignment;
  Assets = published assets provided by lecturers (students don't create
  assets).
  - In ShotGrid today (project 190, read 2026-10-19): Sequences
    `Assignment1`, `Assignment2`, `Assignment_3_team_1..4`,
    `Assignment_3_FULL_CLASS`, `Assignment_3_facial_mocap`; shots named
    per student (`asgn1_tail_S4177501`, `poseToPose_main_<login>`,
    `NWF_EAP_010`...); one Animation task per shot (97); **no Assets** yet.
  - Same shape as a film (sequences / shots / assets), so the film layout on
    H (`maya\sequences\<SEQ>\<SHOT>`, `maya\assets\<type>\<asset>`) can
    serve classes as-is.

- **Separate tool (DECIDED 2026-10-19).** Its core (ShotGrid project
  list, H mapping, build-on-scratch) goes in its own module that the
  reworked Jiffy Schedule imports later. On the mpPipe shelf, private with
  the other pipeline tools.
- **Lecturer assets (DECIDED 2026-10-19):** lecturers create them as
  ShotGrid Assets in the class project and publish them to H with the
  Publish tool, like any asset (so they carry a ShotGrid id).

## OPEN

- Name of the tool.
- Shelf: mpPipe shelf?
