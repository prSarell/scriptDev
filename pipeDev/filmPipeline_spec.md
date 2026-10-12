# Group film pipeline — working spec (started 2026-10-05)

Design notes for how students work in groups on a short film with ShotGrid,
without overwriting each other's work. Captured from a design conversation;
this is a living spec, not a finished design. Sections are marked
**DECIDED** (user's stated design), **OPEN** (unanswered), or
**SUGGESTION** (raised during discussion, not agreed).

Pilot/test bed: *Not Worth Fixing* (NWF) — see the MegaGrant proposal site
(`github.com/prSarell/mega-grant-proposal-site`), which describes NWF as the
test bed for Maya→ShotGrid publish/review and network asset publishing.

---

## 1. Core storage model — DECIDED

- **Server ("H drive")** holds everything for the whole film. It's the source
  of truth.
- **Students work locally on a scratch drive**, which acts as a **sandbox**.
  They pull down only what they need to work on a given asset or shot.
- Work goes back to the server **only via the publish tool** (not yet built).
  Students don't save to the server by hand, and don't reference files live
  off the server while working.
- Students **build shot scenes locally** by referencing pulled assets. They do
  not pull a pre-assembled, already-referenced scene as their starting point.
- **Every asset is its own separately published entity, including keyframe
  data.**

## 2. Scenarios differ by department — DECIDED

Animation, rigging, modelling and FX each have their own scenario (different
things pulled, different things published). Animation is written up in full below. Per the user (2026-10-05), the same
pull → sandbox → publish workflow covers the other departments too; only
what each one pulls and publishes differs.

## 3. Animation scenario — DECIDED

### 3a. Build the shot
- The animator runs the **Build Shot tool** (not yet built — nothing in the
  repo does this; `pipeDev/shotSubDev/build_student_shot_projects.py` only
  makes folders).
- ~~Build Shot knows what the shot contains from a **shot asset list on
  ShotGrid**~~ — **superseded 2026-10-12:** Build Shot lists **all published
  assets for the project** and the student picks what the shot needs (see
  §3i). Why: any shot might need any asset at any time as the film develops,
  and a per-shot list on ShotGrid is extra data entry and management for no
  real gain.
- Example shot: 1 character, 2 props, 1 set, a camera and some lights. Each
  of those is a published asset, pulled from the server onto the animator's
  scratch drive. **Camera and lights are pulled assets** like everything else.

### 3b. Review loop (shotSub) — stage 1
- While animating, the animator uses **shotSub** (existing tool,
  `shelfDev/mpAnim/tools/shotSub.py`) to check their own work and send
  versions to ShotGrid, for the cut and for review.
- This loop repeats until the shot is **approved**.

### 3c. Publish (publish tool) — stage 2, after approval only
Once the shot is approved, the animator publishes with the **publish tool**
(not yet built):
1. The animator **selects assets from their shot** to publish (e.g. the
   animated character + props).
2. On Publish, the tool:
   - sends a shotSub-style version to ShotGrid, with a **.mov of the
     published shot**;
   - **writes out keyframes** per selected asset and sends them back to the
     server;
   - builds a **replica of the shot scene on the server, in a locked folder
     that can't be written over**;
   - lists the **location of that replica** on the ShotGrid version.
3. That gives **two ways back into a shot**:
   - **Rebuild** it from the published assets + published keyframes, or
   - **Open the backed-up replica** and save it to the scratch drive.

Review (shotSub) and publish are **two separate stages**.

### 3d. Server holds published versions only — DECIDED
- **Only published versions of assets and shots live on the server.** The
  locked shot replica does **not** carry its own copies of assets; it uses
  the server's published asset versions.
- Duplicated asset copies only ever exist on the **student's scratch drive**
  (pulled into each shot's sandbox), so disk-space cost lands on scratch,
  not the server.

### 3e. Build tool is the only way assets reach scratch — DECIDED
- Assets get onto the scratch drive **only via the Build tool** (not yet
  built). That includes reopening a shot from its locked server replica:
  the Build tool pulls the asset versions that replica uses back to scratch.
- The Build tool **can only pull published assets** from the server.
- Implication: the Build tool owns reference paths. It pulls assets into the
  shot sandbox and points references at those local copies, so students
  never edit paths by hand. (The alternative — a path variable that
  resolves to server or scratch — is not needed.)

### 3f. Film folder structure, v1 — DECIDED (2026-10-06)

First version of the folder structure. Build on it from here.

**Layout rule:** the **film folder** is at the top, with **one folder per
software** below it. Inside each software folder is that software's own
structure. Neither the film folder nor the software folders are Maya
projects.

**Why:** this layout drives the pipeline, and it brings all the software
for a film together in one place. Everything for the film, from every
program, sits under a single folder. Each program keeps the structure it
expects, and ShotGrid's sequence, shot and asset names tie the programs
together.

**Film folder naming:** `<FILM>_<TYPE>`, where TYPE is a three-letter
production-type code:

| Code | Meaning |
|------|---------|
| `SHF` | short film |
| `GSF` | group short film |
| `CLA` | class assignment |

More codes will be added as needed. Example: `NWF_SHF` = *Not Worth Fixing*,
short film.

**Naming style:** folder names are camelCase (`davinciResolve`,
`shotgridMovs`). Shot and sequence folders use the ShotGrid codes as they
are (`EAP_010_010`) so tools can match folders to ShotGrid. Asset folders
are camelCase versions of the ShotGrid asset codes (`Scout's House` ->
`scoutsHouse`, `AT-KS` -> `ATKS`). Rename an asset in ShotGrid and on disk
together, so the two stay in step (e.g. `willyWagTail` -> `willieWagtail`,
2026-10-06).

```
NWF_SHF\                                 <- film folder (organising only)
  afterEffects\                          <- empty, structure TBD
  blender\                               <- empty, structure TBD
  davinciResolve\
    cuts\                                <- edit projects / cuts
    edl\                                 <- edit decision lists
    shotgridMovs\                        <- review movies pulled from ShotGrid Versions
  dragonframe\                           <- empty, structure TBD
  houdini\                               <- empty, structure TBD
  maya\
    assets\
      character\<asset>\                 <- one Maya project per asset
      environment\<asset>\
      prop\<asset>\
      vehicle\<asset>\
    sequences\
      <SEQ>\                             <- one folder per ShotGrid Sequence
        <SHOT>\                          <- one Maya project per shot
    studioLibrary\                       <- shared Studio Library library; empty, structure TBD
  photoshop\                             <- empty, structure TBD
  premiere\
    cuts\
    edl\
    shotgridMovs\
  substancePainter\                      <- empty, structure TBD
  toonBoom\                              <- empty, structure TBD
  tvPaint\                               <- empty, structure TBD
  unreal\                                <- empty, structure TBD
```

**Maya:** each **shot and asset is its own Maya project**, with its own
`workspace.mel` and Maya's default project folders. They're created with
Maya's File > Project Window > New logic (`sp_createAndSetDefaultProject`
in `setProject.mel`, run from mayapy, as in
`pipeDev/shotSubDev/build_student_shot_projects.py`). `assets\`,
`sequences\`, the asset-type folders and the per-sequence folders are plain
grouping folders, not projects.

- **`sequences\`, not `shots\` or `scenes\`:** every shot project already
  has Maya's own `scenes\` inside it, so a top-level `scenes\` would read
  as `maya\scenes\EAP_010\EAP_010_010\scenes\`.
- **Asset type folders** match ShotGrid's `sg_asset_type` values
  (Character / Environment / Prop / Vehicle). ShotGrid `Graphic` assets
  (style guides, character design, storyboards) don't get a Maya project.

**First build — `C:\Users\scout\Dropbox\NWF_SHF\` (2026-10-06):**
- 75 shot projects from ShotGrid project *Not Worth Fixing* (id 157):
  sequences `EAP_010`, `SEQ010` and `SEQ020`, shots `_010` to `_250` in
  each. `EAP_020` has no shots and was skipped. `EAP_010_FULL_CUT` is a
  reference shot and was skipped too.
- 19 asset projects: character (`scout`, `ATKS`, `willieWagtail`,
  `welcomeSwallow`, `scoutGrownUp`, `scoutsChild`), environment
  (`scoutsHouse`, `riverAndScrub`, `sandyRiver`, `cliffTop`,
  `farmBuildings`, `sugarcaneFields`), prop (`backpack`, `battery`,
  `stick`, `bananaLounge`, `bakedBeansCan`, `spoon`, `farmEquipment`).
  `vehicle\` is empty. `Farm Equipment` has no asset type in ShotGrid and
  was put under `prop` for now.
- The build used one-off mayapy scripts; there's no reusable build script in
  the repo yet.

**Server vs scratch:** the server ("H drive") holds the whole film folder.
A student's scratch drive mirrors the same path for whatever they've pulled
(2026-10-12: superseded, scratch is now a full 1:1 folder mirror, see §3h):

```
H:\NWF_SHF\maya\sequences\SEQ010\SEQ010_010\             <- shot project on server (published keyframes + locked replica)

<scratch>\NWF_SHF\maya\sequences\SEQ010\SEQ010_010\      <- same shot project, pulled to sandbox
  workspace.mel
  scenes\        <- animator's working scenes
  assets\        <- pulled copies of this shot's assets
  images\        <- shotSub playblasts
```

Why per-shot/per-asset rather than one project per film: students pull only
what one shot/asset needs, and shots move between scratch and server as a
unit (publish replica, "open backup → save to scratch"). shotSub already
works with per-shot projects (as in Assignment 3). Build Shot should set the
Maya project automatically so students don't have to switch by hand.

### 3g. Solo students / single film-wide project — DEFERRED (decided 2026-10-05)

Build **per-shot / per-asset projects only** for now. A simplified mode where
a solo student uses one Maya project for the whole film is deferred to later.

It was confirmed feasible: the server, publish and ShotGrid side is identical
either way; only the local scratch layout differs. To keep that door open
without a redesign, the first build must follow two rules:

1. **Pulled assets keep their version in the folder path**
   (`assets\character\scout\rig\v003\`), so several versions can coexist in one
   project (shot 10 on rig v3, shot 20 on v4).
2. **References are stored relative to the project root**
   (`assets/character/scout/rig/v003/scout_rig.ma`), so the same path resolves in
   a per-shot project and in a film-wide project.

With those in place, adding the solo mode later is just one setting in the
Build tool ("pull into this shot's project" vs "pull into my film project").
The publish tool and shotSub need no changes.

### 3h. Drives and locations — DECIDED (2026-10-12)

RMIT has **no definite server structure** to code against yet, and the
H-drive setup there may change soon. The pipeline has to stay flexible about
where each location physically lives.

**First working form: three locations.**

| Location | Role | Who moves work there |
|---|---|---|
| **H drive** (server) | Source of truth, as in §1 / §3d | Publish tool |
| **Scratch drive** | Student's local sandbox, as in §1 / §3e | Build tool (pull from H) |
| **Portable drive / cloud** (external drive, Dropbox, etc.) | **Portable scratch**: the student takes work home and keeps working on it there | The student, by hand |

- Students **plan what they're working on**, pull the needed assets from the
  H drive to scratch, then copy from scratch to their portable drive/cloud.
- Only **scratch work** is copied to the portable location, not the whole
  project.
- The tools **don't manage** the portable/cloud copy. Students copy it
  themselves.
- Because it acts as portable scratch, it has the same layout as scratch.

**Development / test setups:**

| Setup | Scratch | H drive |
|---|---|---|
| Home machine, 2026-10-12 | `D:` (Bean): `D:\NWF_SHF\` | `F:` (One Touch), **today only**: `F:\NWF_SHF\` |
| RMIT test install | lab scratch drive | lab H drive (setup may change) |

Both `D:\NWF_SHF\` and `F:\NWF_SHF\` were seeded 2026-10-12 as exact copies
of the full v1 skeleton (2,849 folders, 94 `workspace.mel`), so scratch and
H drive start with a matching structure. `C:\Users\scout\Dropbox\NWF_SHF\`
stays as the reference copy.

**Scratch mirrors the H drive 1:1 — DECIDED (2026-10-12).** "We have to
start somewhere": revisit if it causes problems in practice.
Scratch holds the **whole film folder structure**, a 1:1 copy of the H
drive's folders, but only holds **content** (assets, scenes) for what's
being worked on. E.g. working on `EAP_010_010` → every shot/asset folder
exists on scratch, but only `EAP_010_010` and its assets have files in them.

- **Why:** keeps the code simpler and the system easier to manage. Paths are
  identical everywhere, and tools never need to work out which folders to
  create.
- **Slow first build is fine.** Laying down the skeleton (~2,850 folders) is
  slow on a USB drive (4.5 min to One Touch), but it only happens once, on
  the first build.
- **Empty folders look like real work.** A student could open or save into a
  shot they haven't pulled. Accepted for now: students carry some
  responsibility here.
- **OPEN — skeleton goes stale.** When shots/assets are added or renamed on
  the H drive (e.g. `willyWagTail` -> `willieWagtail`), each scratch copy
  falls out of step. Undecided how to handle this.
- Note: tech notes §6 says lab scratch drives are wiped every couple of
  weeks, so at RMIT the "first build" may repeat after each wipe.

**SUGGESTION (not agreed):** drive letters differ between these setups (and
will at RMIT), so the tools should never hard-code `D:\`/`H:\`. Each location
(H drive root, scratch root) would be a setting.

### 3i. Tools and build order — DECIDED (2026-10-12)

The tools are developed side by side:

- **Build tool**: pulls H drive → scratch (§3a, §3e). **Active, from 2026-10-12.**
- **Publish tool**: scratch → H drive, after approval (§3c). **Active, from 2026-10-12.**
  **Build Shot workflow (DECIDED 2026-10-12, as described by the user):**
  1. The tool holds a **list of all published assets for the project**
     (replaces the ShotGrid shot asset list in §3a: no per-shot list to
     maintain).
  2. The student picks an asset and **chooses which published version** to
     pull.
  3. The tool saves it into the **shot project's own `assets\` folder**,
     mirroring the asset type/name, under a **fixed, unversioned name**:
     ```
     F:\NWF_SHF\maya\assets\prop\backpack\scenes\backpack_model_v001.mb   <- published (H drive)
     D:\NWF_SHF\maya\sequences\EAP_010\EAP_010_010\assets\prop\backpack\backpack.mb  <- pulled into shot (scratch)
     ```
  4. When a new version is published (`backpack_model_v002.mb` on the H
     drive), the student selects the asset in Build Shot and **updates** it:
     the tool **overwrites `backpack.mb`** on scratch with the new version.
  5. So Build Shot **needs to know when a publish has been updated**.

  **Other departments in the shot (DECIDED 2026-10-12):** the model sits at
  the asset folder's root; a rig publish of the same asset goes in a `rig\`
  subfolder:
  ```
  ...\EAP_010_010\assets\prop\backpack\
    backpack.mb          <- latest Modeling publish
    rig\
      backpack.mb        <- latest Rigging publish
  ```
  **Department codes (DECIDED 2026-10-12):** each department has one short
  code, used everywhere: published filename (`<asset>_<code>_v###`) and the
  department subfolder in the shot. The tab shows the full label only.
  Chosen because it will make more sense to students: the same word
  everywhere.

  | Tab label | Code |
  |---|---|
  | Modeling | `model` (exception: sits at the asset folder root in the shot, no `model\` folder) |
  | Rigging | `rig` |
  | Previs | `previs` |
  | Anim | `anim` |
  | Creature | `creature` |
  | LookDev | `lookDev` |
  | FX | `fx` |
  | Render | `render` |

  e.g. `backpack_model_v001.mb`, `backpack_rig_v001.mb` → shot `rig\backpack.mb`.

  Note: the fixed name means the shot scene's reference path never changes
  on update. This differs from §3g rule 1 (version in the pulled path), so
  §3g's solo-mode plan needs revisiting.
- **shotSub**: already exists; the review loop between build and publish (§3b).
  **Shape (DECIDED 2026-10-12):** one Publish tool (one shelf button, one
  window) with a **tab per production stage** (modelling, rigging,
  animation, ...). Each tab has **its own Publish button** for that
  department, not one shared button. This replaces the
  shelf-per-department studio model, which is too much overhead for
  generalist students. First tab: **modelling**, tested by publishing the
  `Backpack` prop (ShotGrid Asset id 1577). Tab list/order (starting
  set, 2026-10-12): **Modeling, Rigging, Previs, Anim, Creature, LookDev,
  FX, Render**.

  **Where publishes land (DECIDED 2026-10-12):** in the **same folder on
  the H drive** that the work was done in on scratch. There is no separate
  `publish\` folder. Scratch holds all the working variations; the H drive
  holds only published milestones. Version and department go in the
  filename instead, `<asset>_<department>_v###.<ext>`:

  ```
  D:\NWF_SHF\maya\assets\prop\backpack\scenes\backPack_wip_012.mb       <- scratch: working
  F:\NWF_SHF\maya\assets\prop\backpack\scenes\backpack_model_v001.mb <- H drive: published
  ```

  Note for §3g rule 1: versions still coexist (several `v###` files side
  by side), just by filename rather than by `v###` folder.
- **Setup tool**: **keep in mind, not built yet.** Lays down the film
  folder structure and links it to ShotGrid (the reusable version of the
  hand-built v1 skeleton; cf. tech notes §14 Class Project Setup Tool).
  Build and publish must stay compatible with the structure it will create.

---

## 4. Open questions

- ~~Replica references~~ — resolved, see §3e.
- **Locking:** is the replica folder locked by IT/Windows permissions on the
  server, or only by convention (the tool never writes there again)?
- **Asset versions in Build Shot:** always pull the latest published version
  of each asset, or can the shot asset list pin specific versions?
- **Review vs publish in ShotGrid:** both stages create Versions on the same
  Shot — how is the published one marked (a status, or a separate
  PublishedFile entity) so the cut and Build Shot know which is final?
- **Keyframe data format:** not discussed yet. Candidates: Studio Library's
  `mutils` anim format (already shipped to students), Maya ATOM. Alembic/FBX
  are baked and not editable, but may be needed downstream (lighting/Unreal).
- ~~Maya project folder structure~~ — decided, see §3f.
- **Cross-software assets:** an asset that exists in several programs (e.g.
  `scout` in Maya and Unreal) — do asset/shot names and grouping match
  across software folders so tools can find "the same asset" in each?
- **Non-software material:** editorial is now covered by the
  `premiere\` / `davinciResolve\` folders (§3f). Audio, reference,
  scripts/boards and ShotGrid `Graphic` assets still need a home: a
  shared folder at film level (e.g. `NWF_SHF\reference\`) alongside the
  software folders, or somewhere else?
- **Inner structure of the other software folders:** `afterEffects`,
  `blender`, `dragonframe`, `houdini`, `photoshop`, `substancePainter`, `toonBoom`, `tvPaint`, `unreal` and `maya\studioLibrary` are
  empty placeholders in v1.
- **Reusable build script:** v1 was built with one-off scripts. A
  `pipeDev` tool that builds a film folder from a ShotGrid project (any
  `<FILM>_<TYPE>`) would make this repeatable.
- **Per-department detail:** what exactly rigging, modelling and FX pull and
  publish (same workflow as animation, details not yet written up).

## 5. Context: what the existing tools assume

The repo currently contains two conflicting Maya project models:

- **One Maya project per film** — `shotSub.py` assumes this. A shot is a
  subfolder under `scenes/`, and shotSub works out the shot from where the
  open scene sits. It writes `shotgrid_link.json` + `shotgrid_publish_log.json`
  into that scene folder, and puts playblasts in the mirrored `images/` folder.
- **One Maya project per shot** — `build_student_shot_projects.py` (used for
  Assignment 3, `D:\assignment_3\NWF_EAP_XXX\`) builds a project per shot
  with `scenes/<studentID>/` inside. The paused JiffySG also assumed a Maya
  project per shot/asset.

Because shotSub keys its link file, publish log and `v###` numbering off the
scene's folder, two people saving into the same folder would share and clash
over them (auto-prune could delete the other person's playblasts). Today
nothing in the repo versions or protects `.ma` scene files themselves.

## 6. Suggestions raised, not agreed

- **Two-way paths:** if the sandbox mirrors the server's folder layout and
  references are stored relative to the project root, the same file resolves
  on scratch and on the server without repathing. The user questioned an
  earlier, more prescriptive version of this; revisit once the scenarios are
  fully described.
- **Rig version stamped on keyframe publishes**, so animation made on an
  older rig can be flagged.
- **Publish permission tied to the ShotGrid Task assignee**, so two people
  can't both publish the same asset/shot.
- **Stale-version check** on pull or scene open ("newer version available").
- **WIP backup:** work in progress lives only on scratch until approval
  (possibly weeks). If scratch drives aren't reliable, consider a
  "back up to server" action that isn't a publish. The user's view so far is
  that the sandbox is disposable by design.
