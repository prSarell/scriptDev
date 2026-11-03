# Film pipeline — Stage 2 review (2026-11-03)

A review of everything built for the group film pipeline so far (code,
spec, follow-ups, tech notes), written to chart the next stage. Stage 1
proved the design works in use. Stage 2 is about two things:

1. an **ecosystem**: each stage depends on the others, but it stays loose
   enough to support group work without limiting creativity;
2. the **most elegant, concise code** that keeps all the functionality, and
   that a trained coder could open, follow and edit.

How to read this:
- **FINDING**: something observed in the code or docs, with evidence.
- **SUGGESTION (not agreed)**: a proposal for you to accept, change or
  reject. Nothing here changes a DECIDED or LOCKED item in the spec.
- The department list and Build's dropdowns are **LOCKED** (2026-10-30).
  None of the suggestions below change what they show.

Sources reviewed: `filmPipeline_spec.md` (3,483 lines),
`pipelineFollowUps.md`, `assetPipelineDev/rmit_pipeline_tech_dev.rtf`,
`projectSwitcher_brief.md`, `shotgridTemplate_requirements.md`, every
module in `buildDev/`, `publishDev/`, `projectDev/`, `modelDev/`,
`layoutDev/`, `desktopDev/`, `pipelineInstaller/`, the mpPipe / mpLayout /
mpModel shelf configs, and the live film config on the T7
(`G:\H\NWF_SHF\pipeline.json`).

---

## 1. Where we are

### 1a. What exists

| Area | Modules | Lines (code) | Tests |
|---|---|---|---|
| Publish | `publishTool_api` (2,407), `_ui` (1,171), `_anim` (653), `_camera` (622), `_env` (447), `_textures` (301), `_outputs` (255), `_look` (161), `pipePicker` (258), `pipeStudioLibrary` (219), `rig_rules` (43) | ~6,500 | 25 scripts |
| Build | `buildTool_api` (2,171), `_ui` (1,317), `pipeEnv` (192) | ~3,700 | 12 scripts |
| Project Tool | `projectTool_api` (316), `_ui` (410) | ~730 | 3 scripts |
| Model / Layout shelves | `modelTool_convert` (262), `layoutTool_env` (122) | ~380 | 2 scripts |
| Desktop (no Maya) | `h_sync` (389), `asset_tasks` (100) | ~490 | 1 script |
| Installer | `install` (238), `uninstall` (105), `build_zip` (128) | ~470 | (inside build tests) |
| **Total** | 23 modules | **~12,300** | **46 mayapy scripts** |

Plus the review loop, which the pipe leans on but doesn't own: `shotSub`
and `shotgridConnect` (shipped in mpToolSet), and the class-setup scripts
in `shotSubDev/`.

106 commits touched `pipeDev/` or the mpPipe shelf since 2026-10-01: about
five weeks of fast, steady building.

### 1b. What works (built and passing mayapy tests)

- **Storage model**: H = published source of truth, scratch = sandbox
  mirroring H 1:1, a shared `maya\publish\` folder on scratch, personal
  `scenes\<login>\` folders on H.
- **Publish**: model, rig (top group, cache/control sets, textures,
  MetaHuman DNA, look files), environment (sets, locators, sky), camera
  (baked, split camera + keys, locked), layout/animation (keys, unkeyed
  settings, layered bake, caches on Final, lights), output formats
  (ABC/USD/FBX/OBJ), iterative vs Final, thumbnail borders, review in RV
  before publishing, failure / warning dialogs.
- **Build**: per-department build lists on H, versions per shot, rig
  hardlinks (option C), cameras, keys from any shot, caches wearing the
  rig's look, Repair, My Scratch, `$PIPE_SCRATCH` reference paths that
  survive a drive change, refusing when off-pipe.
- **Project Tool**: ShotGrid assignment gating, structure diff and update,
  Set Project, Studio Library show/shot libraries.
- **Desktop**: `h_sync` lays down and updates the H skeleton from ShotGrid;
  `asset_tasks` makes department Tasks.
- **Installer**: staff zip, userSetup block, three shelves.

### 1c. What hasn't been proved yet

FINDING: `pipelineFollowUps.md` has **55 open items** and **9 decisions
waiting on you**. Most of the open items are **hand tests in Maya**:
section 1 opens with "Everything below passes its mayapy tests, but none of
it has been tried by hand." Several are core to the ecosystem (a class-sized
login that isn't `scout`, a drive change with a MetaHuman face, a scratch
wipe, rig rollback across shots).

This matters for Stage 2: a refactor is safest on behaviour that has been
confirmed by hand. Refactoring behaviour that later turns out to be wrong
is wasted effort.

---

## 2. The design principles that have emerged

These are the rules the code already follows. They read well as the
**backbone of the new brief**, because they are what makes the pipe an
ecosystem rather than a set of tools. (All DECIDED in the spec; collected
here, not changed.)

1. **H is the source of truth and holds only publishes.** Students never
   save to H by hand (§1, §3d).
2. **Build is the only way in, Publish is the only way out** (§3e, §3i).
3. **The ShotGrid entity defines the thing; the folder decides where it
   goes.** Working file names don't matter; Publish renames (§3i).
4. **Two IDs only**: Asset ID and Shot ID, combined with department code
   and version (§3i "The ID rule").
5. **Iterative and Final are the same publish**; approval only adds the
   department's caches/outputs (§3c, 2026-10-23).
6. **Unpublished work is the student's job**; an iterative publish is how
   work moves between machines (§3h, CLOSED 2026-10-23).
7. **Paths work from any drive** through `$PIPE_SCRATCH`; the scratch drive
   follows the open scene (§3i).
8. **Published files are clean**: no namespaces, no unused shaders, in a
   stamped pipe group, read-only (§3i, §4).
9. **Refuse, with a fix button, when a student goes off-pipe** (2026-10-28).
10. **Film-specific choices live in data, not code** (server strategy;
    `pipeline.json`, `rig_rules.py`).
11. **Built for the shared-server target**; drive locations are settings,
    and swapping the T7 for a real server should be a settings change only.
12. **The department list is locked** (2026-10-30).

SUGGESTION (not agreed): principle 13, for Stage 2: **one place for each
fact.** Every department, naming rule, path rule and ShotGrid lookup is
defined once and used everywhere. Most of the code findings below come back
to this.

---

## 3. Code findings

Overall: the code is careful and well tested, and its docstrings explain
*why*, which is rare and valuable. The problems are structural. They come
from building fast and feature-first, which was the right call for Stage 1.

### 3a. `publishTool_api.py` has become the pipe's core, under a tool's name

FINDING: `publishTool_api.py` (2,407 lines) holds much more than Publish:

- machine settings (`load_config`, `get_root`, `set_root`), who's logged in
  (`who`, `clean_login`);
- film/shot/asset path rules (`find_film_folder`, `pipe_place`,
  `asset_context`, `list_films`, `list_shots`, `personal_folder`);
- the department list, `PublishError` (which Build re-exports as
  `BuildError`);
- ShotGrid access (`_shotgrid`, `find_shotgrid_asset`, tasks, approval,
  uploads, thumbnails);
- playblast, burn-in, audio, RV/rvio discovery;
- model and rig export, cache/control-set rules, pipe groups, stamps,
  namespace stripping, script-node security check.

Every other module imports it: Build, the Project Tool, `pipeEnv`, the
model and layout shelves. So the dependency graph looks like this:

```
             publishTool_api  (core + Publish + ShotGrid + playblast)
            /    |      |     \           \
  buildTool_api  pipeEnv  projectTool_api  publishTool_* (anim, camera, env...)
       |            ^
  modelTool_convert |
       (buildDev/pipeEnv.py lives in Build's folder but is used by everyone)
```

A coder opening the repo would look for "where are paths defined?" or
"where's the ShotGrid code?" and find it inside the Publish tool.
`buildTool_api.py` also adds `publishDev/` to `sys.path` to reach it.

### 3b. The publish sequence is written out three times

FINDING: `api.publish`, `camera.publish_camera` and `anim.publish_anim` each
spell out the same ~80-line sequence:

```
script-node check -> plan -> ShotGrid entity -> task + Final? -> check RV
-> playblast -> audio -> review in RV -> write to H (clean up on failure)
-> build the note -> find rvio -> upload with audio -> link task
-> remove frames
```

The steps that differ per department are only **plan**, **checks** and
**write**. A fix to the shared steps (e.g. the rvio warning, the task
link) has to be made in three places. The rvio warning text is already
copied word for word three times.

### 3c. Department knowledge is spread across many files

FINDING: what a department *is* (code, label, what it publishes, what Build
pulls, its ShotGrid task, its working folder) is spread out:

- `DEPARTMENTS` in `publishTool_api`; `DEPT_LABELS` built in
  `buildTool_api` and then changed four more times in that file
  (lines 52, 53, 91, 114), and built again differently in
  `publishTool_ui` (line 53).
- `ENV_CODE` defined in three modules; `env` is still a code although
  environments are now Modeling publishes.
- `ASSET_TASKS` (publish), `TASKS_BY_TYPE` (`asset_tasks.py`),
  `PUBLISH_FOR` (anim), `BUILD_FOR` (build), `LIVE_DEPARTMENTS` /
  `SHOT_DEPARTMENTS` / `PICKER_DEPARTMENTS` (publish UI),
  `WORK_FOLDERS` / `SHOT_WORK_FOLDERS` (in `publishTool_api` and copied
  into `h_sync`).
- The UI decides which function to call with `if code == cam...elif code
  == anim...else` (`publishTool_ui._publish_saved`), and `api.publish`
  branches on `ENV_CODE` / `MODEL_CODE` / `RIG_CODE` inside itself.

Adding a department, or changing what one does, means finding all of
these. That is the opposite of "flexible and malleable".

### 3d. The naming contract lives in two places

FINDING: how a published file is named is written once in Publish
(`published_name`, `published_versions`) and read back with separate
regexes in Build (`PUBLISHED_RE`, `CAMERA_RE`, `CACHE_RE`, `KEYS_RE`). The
two sides only agree because they were written carefully. This is the
contract the whole ecosystem depends on (Publish writes it, Build reads it,
Studio Library, h_sync and future tools rely on it), so it should be one
module both sides use.

### 3e. The `plan` dictionary is an unwritten interface

FINDING: Publish passes a `plan` dict between ~20 functions in 6 modules.
It has **49 distinct keys** (`plan["sg_shot"]`, `plan["frames_folder"]`,
`plan["camera_plan"]`...), added and changed along the way. Nothing lists
them, so a coder can't tell what a function expects without tracing every
caller.

### 3f. Repeated small helpers and UI parts

FINDING:
- `_short(node)` in 4 modules, `_stamp` in 3, `_clean` in 3, `_under`,
  `_namespace`, `_namespace_nodes` in 2 each; `TIME_CURVES` twice.
- `GEOMETRY_TYPES` is defined twice **with different values** (`publishTool_api`
  without `nurbsCurve`, `publishTool_anim` with it). Probably intended, but
  the same name meaning two things is a trap.
- The Build and Publish windows each have their own `StatusLabel`,
  `_maya_main_window`, H/scratch root fields with Browse, `_render_table`,
  `_remove_rows`, `_items_for`, `_match_project`, `changeEvent`. The
  Project Tool has a third copy of some of these. `pipePicker.py` already
  shows the right pattern (one shared widget); it lives in `publishDev/`
  though it's used by Build too.
- The UIs carry real logic: `_publish_saved` groups rows into jobs and
  joins animation + camera publishes; `_build_shot` is ~100 lines. That
  logic is untested headless unless a test drives the UI.

### 3g. Comments carry the conversation history

FINDING: roughly 100 dated decision notes sit in the four largest files
(e.g. `# (user, 2026-10-28: "We don't need a mov per asset in a
publish")`). They were useful while the design moved daily, and they
explain *why*. But a coder needs the rule as it stands now; the history of
how it was reached belongs in the spec. Some comments describe superseded
behaviour next to the current code.

### 3h. Compatibility layers are piling up

FINDING: the code keeps several older forms working: `build_manifest.json`
next to the per-department build lists on H, the old `build_list.json`
read as a starting list, in-shot asset copies (`legacy_rel_path`), the
referenced `cam:shotCam` camera, camera map formats, carried-forward
settings files, `_env_` publish names. Each is small, but together they
roughly double the paths through Build. NWF is the only film using the
pipe, so most of them could be retired with a one-off migration of NWF's
data.

### 3i. ShotGrid: decided, not yet built

FINDING:
- The ID rule (spec §3i, DECIDED 2026-10-12: `asset.json` / `shot.json`
  holding ShotGrid IDs) isn't built. Every publish fetches **all** assets
  in the project and matches the folder name
  (`find_shotgrid_asset`, `find_shotgrid_shot`). Fragile on renames, and a
  class-sized load concern (26 students publishing at once, tech notes §5).
- The pipe depends on `shotgridConnect` from **mpToolSet** (the student
  toolset), and on shotSub having been opened once to set the identity.
  `install.py` warns if it's missing. So the staff package isn't
  self-contained, and a change to shotSub's connection module can break
  Publish.
- The artist's name is looked up twice per publish (follow-ups §3).

### 3j. Packaging and imports

FINDING:
- All modules install flat into Maya's `scripts\` folder, with generic
  names (`pipeEnv`, `pipePicker`, `rig_rules`) beside every other tool's.
  Each UI module begins with `sys.path` changes so it works from the repo
  as well.
- Naming styles mix: `publishTool_api`, `pipePicker`, `rig_rules`,
  `h_sync`, `layoutTool_env`.
- `build_zip.py` lists every file by hand; a new module that's forgotten
  there works in dev and breaks on the T7.
- Python 2 idioms remain (`class X(object)`, `dict((a, b) for ...)`,
  `%` formatting). Maya 2025+ is Python 3 only, so these can go.

### 3k. Tests

FINDING: coverage is a real strength: 46 headless scripts on throwaway
folders, never touching real drives or prefs. But:
- each script repeats the same bootstrap (sys.path, Qt offscreen,
  `maya.standalone`, its own `check()` function, its own fake film tree);
- there's no single "run everything" command, so it's easy to miss a
  regression in a module you didn't touch;
- one test is known stale (`test_projectMatch_mayapy.py` still expects
  Build to ask instead of refuse).

### 3l. The spec

FINDING: `filmPipeline_spec.md` is 3,483 lines (224 KB). It's a faithful
record, which is valuable, but current rules, history, superseded
decisions (some struck through, some marked "superseded" in place),
implementation notes and test results are interleaved. One section
("Publish levels and formats", §4) runs to ~1,300 lines. Answering "what
is the rule now for X?" means reading the whole history of X. The 3
labels (DECIDED / OPEN / SUGGESTION) are still followed and still work.

---

## 4. Ecosystem findings (design, not code)

### 4a. The stages already depend on each other, through files on H

The pipe's stages talk only through files and folders on H:

| Producer | File / folder on H | Consumers |
|---|---|---|
| h_sync / Setup | film skeleton, `pipeline.json` | everything |
| Publish | `scenes\<login>\<asset>_<login>_<code>_v###.ma` + `_look`, `_exports\`, `sourceimages\<login>\` | Build, Convert to Model |
| Publish (camera) | `_cam_`, `_camAnim_` `.ma` + `.json` | Build |
| Publish (anim) | keys `.json`, caches `.abc`, cache info | Build (keys, caches) |
| Build | `data\build\<department>.json` | Build on another drive |
| Publish | `data\publish\outputs.json` | Publish (ticks remembered) |
| Publish / Project Tool | `studioLibrary\` | Studio Library |

That's a good, simple ecosystem shape: the **file layout and names on H
are the API between stages**. Nothing calls across tools at runtime except
through `publishTool_api`'s helpers.

SUGGESTION (not agreed): write this table up as **the contract** in the
new brief, and have one code module own each row (the naming module in
3d). Then a new stage (FX, Lighting, Unreal, another program) joins the
ecosystem by reading and writing those files, without touching the
others' code. This is also what tech notes §11 asks for ("Maya is simply
the first adapter").

### 4b. Flexibility for group work

What already keeps it flexible: build from any published asset (no
per-shot ShotGrid list), keys from any shot, personal version series,
iterative publishes at any time, working file names are free.

Where it's tight, and worth a deliberate look in the brief (OPEN, your
call):
- **Things made in the shot** (spec §4d, PARKED): one-shot rigs, props,
  reusing animation in another shot. This is the main creative-freedom
  gap: today something that isn't a published asset can't travel.
- **Build by department** (DRAFT): what each department pulls.
- **Rollback default** (decision waiting): the "Every shot" default can
  undo another shot's rollback.
- **Skeleton goes stale** (§3h, OPEN): renames on H aren't followed on
  scratch without the Project Tool's structure update.
- **Rig version record on H** (follow-ups §6): a scratch wipe silently
  resets every shot to the latest rig.
- The tech notes' three class archetypes (§10) and solo mode (§3g,
  DEFERRED): the code assumes a group film throughout. Worth stating in
  the brief whether Stage 2 keeps that assumption.

### 4c. Reconciling the spec and the tech notes

The tech notes (Aug–Oct) and the spec agree on the big shape and differ in
places (you've said there are no winners or losers). Where they differ
today, as built:

| Topic | Tech notes | Built (spec) |
|---|---|---|
| H structure | working + published structures | published only; working stays on scratch |
| Publish tiers | "to H" then "for review" | review (shotSub) and publish separate; iterative / Final |
| Per-student nesting | `<asset>/<StudentID>/<project>` | one project per asset/shot, `scenes\<login>\` inside |
| Setup | Class Project Setup Tool, templates, rosters | `h_sync` + `asset_tasks`, hand-written `pipeline.json` |
| Load | staggered pulls/publishes for 26 students | not addressed yet |
| Render farm | locked published structure | not addressed yet |

Worth settling in the new brief which of the not-yet-addressed rows (load,
render farm, setup tool, archetypes) are Stage 2 scope.

---

## 5. A possible shape for Stage 2 code (SUGGESTION, not agreed)

Offered as a starting point for the brief, not a plan to execute. The aim
is fewer lines, one place per fact, and a layout a coder can navigate by
folder names alone. Behaviour stays exactly as it is.

### 5a. One package, three layers

```
pipeDev/mpPipe/                  <- installs as one package: import mpPipe
  core/                          <- no UI; most of it no Maya either
    config.py        machine settings, roots, who's logged in
    places.py        Film / Asset / Shot: parse a path, build a path
    naming.py        published names: write AND read (3d)
    departments.py   the locked list + what each department does (5b)
    shotgrid.py      connection, IDs (asset.json / shot.json), tasks, uploads
    review.py        playblast, burn-in, audio, RV
    scene.py         Maya helpers: short names, namespaces, stamps, pipe groups
    errors.py        PipeError (student can fix), Cancelled
    env.py           $PIPE_SCRATCH (today's pipeEnv)
  publish/
    pipeline.py      the one publish sequence (5c)
    model.py rig.py environment.py camera.py anim.py look.py textures.py outputs.py
  build/
    pull.py          copy / link / manifest
    references.py    reference, repoint, repair
    camera.py keys.py caches.py scratch.py
  ui/
    widgets.py       StatusLabel, roots row, picker, banner, dialogs
    publish_window.py build_window.py project_window.py
  tools/             small shelf tools: convert_to_model.py, environment_structure.py
  desktop/           h_sync.py, asset_tasks.py (no Maya; reuse core/naming + places)
  tests/
    run_all.py       one command, one summary
    harness.py       mayapy bootstrap, check(), fake film tree, fake ShotGrid
```

Nothing here changes where files go on H or scratch, or what any window
shows.

### 5b. Departments as data

One entry per department in `core/departments.py`, holding what is now
spread over 3c: code, label, ShotGrid task name, working folder, asset or
shot, what Publish writes, what Build pulls. The locked order stays the
list order. Publish and Build ask the registry instead of branching on
codes, so changing what a department does is one edit, and the dropdowns
can't drift from each other.

### 5c. One publish sequence

`publish/pipeline.py` runs the shared steps (3b) once. Each department
module supplies only `plan`, `check` and `write` (and optionally extra
note lines and outputs). Animation + camera in one movie becomes "a
publish with two writers" rather than a special case in the UI.

### 5d. A written-down publish record

Replace the open `plan` dict with a small dataclass (`PublishPlan`) whose
fields are listed in one place, with a docstring each. Same data, but
readable and checked.

### 5e. Smaller steps that pay off on their own

Each of these is useful even without the restructure:
1. A test runner + shared harness (3k), and fix the stale test. Do this
   first: it protects everything after it.
2. `naming.py` used by both Publish and Build (3d).
3. Build the ShotGrid ID files (`asset.json` / `shot.json`, already
   DECIDED) and look up by ID (3i).
4. Retire the compatibility layers after migrating NWF's data (3h).
5. Move dated decision quotes from code comments to the spec, leaving a
   one-line "why" and a spec section reference (3g).
6. Make `build_zip.py` collect the package folder instead of a hand list
   (3j).
7. Bring the ShotGrid connection into the pipe package, so it doesn't
   depend on mpToolSet (3i).

### 5f. Docs

SUGGESTION (not agreed): split the docs by job, keeping the current spec
whole as the archive:

| Doc | Job | Size |
|---|---|---|
| **Stage 2 brief** (new) | goals, principles (section 2), scope, what's in and out | a few pages |
| **Pipe rules** (new) | the current rule for each topic, no history; links to the spec for why | grows slowly |
| **The H contract** (new, or part of the rules) | section 4a's table, file names and formats | one page |
| `filmPipeline_spec.md` | decision log and history, unchanged | as is |
| `pipelineFollowUps.md` | to-do list, unchanged | as is |

### 5g. Order and risk

A suggested order, so the pipe stays usable throughout:
1. Hand-test pass on the T7 (section 1c), so we refactor confirmed
   behaviour.
2. Test runner and harness.
3. New brief + rules doc agreed.
4. Core extraction (`config`, `places`, `naming`, `departments`,
   `errors`), with old module names kept as thin re-exports for one
   release so nothing breaks mid-term.
5. One publish sequence, then the Build split, then the shared UI widgets.
6. Retire compatibility layers; tidy comments.
7. Measure: lines of code before/after, test count, publish and build
   timings (also useful evidence for IT).

A rough sense of the gain: the three publish flows, the duplicated UI
parts, the department tables and the compatibility paths together are a
large share of today's ~12,300 lines. A reduction of 20–30% with no loss
of function seems realistic, but that's an estimate, not a measurement.

---

## Answers so far (user, 2026-11-03)

- Suggestions in section 5 accepted in principle. The user's concern: they
  must make the work easier, not just the code tidier for Claude.
- Stage 2 = **tidying and adding new features** ("still lots of work to do").
- **Hand tests first**: list at `pipeDev/handTests.md`.
- **Package**: yes, as **one downloadable zip on GitHub, separate from the
  mpToolSet download**. (The repo is public, so a release there is public;
  to confirm before setting it up.)
- **Move NWF data**: yes. A **new ShotGrid site** is coming, with everything
  migrated over the next two weeks (from 2026-11-03); old-layout code can
  be retired as part of that move.

- **Storage targets** (user, 2026-11-03): "we also need to assume we are
  building a test for SharePoint and a server." H may be the T7, a
  SharePoint library (OneDrive sync) or a server share (UNC). Code that
  assumes storage behaviour: rig hardlinks, read-only locking, "latest" by
  creation time (`publish_time`), next free `v###` (sync lag can give two
  people the same number), Studio Library's shared `database.json`.
  Rules: `PIPE_RULES.md` "Storage targets"; tests: `handTests.md` section
  K. Stage 2 should put all H file operations behind one small storage
  module so a target's quirks are handled in one place.
- **Contributors** (2026-11-03): about seven people joining, coding and/or
  testing, using Claude. Git setup: protected `main`, PRs, CODEOWNERS,
  `.github/CONTRIBUTING.md`, issue templates, `pipeDev/run_tests.py`.
  The pipe stays public.

## 6. Questions to chart the brief

1. **Scope of Stage 2**: is it consolidation only (same features, better
   code), or consolidation plus new stages (Lighting build, FX, §4d things
   made in the shot)? Or consolidation first, then features?
2. **Hand tests first?** Are you happy to do the T7 hand-test pass before
   any restructure?
3. **Package restructure**: is a single `mpPipe` package (5a) the
   direction, or would you rather keep the per-tool `*Dev` folders and
   just extract a shared core?
4. **Retiring old forms (3h)**: OK to migrate NWF's data once and drop the
   compatibility code?
5. **ShotGrid connection**: should the pipe carry its own copy of the
   connection module (self-contained staff package), or keep sharing
   shotSub's?
6. **Archetypes and solo mode**: does Stage 2 stay group-film only?
7. **Load and render farm** (tech notes §5, §12): Stage 2 or later?
8. **Docs**: happy with the brief / rules / contract split (5f), with the
   spec kept as the history?
9. **The waiting decisions** (rollback default, MetaHuman model publish,
   DNA defaults, Build copying the env `.abc`, what decides the latest
   shot publish): settle before the restructure, or carry them into it?
