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
  **One click publishes (DECIDED 2026-10-12):** for each row in the Publish
  list, the Publish button (1) makes a **shotSub of the asset**: 2 frames by default, with the
  option to playblast more; (2) copies the scene to the H drive; (3) sends
  the shotSub to ShotGrid as a Version on the asset.
  - The **ShotGrid asset defines the asset**. The asset project folder the
    student works in (named from the ShotGrid asset, §3f) decides where
    the publish goes. What the student calls their working files doesn't
    matter; the tool renames the publish to fit the convention.
  - Implementation (v0): the folder is matched to the ShotGrid Asset
    ignoring case/spaces/punctuation (`bakedBeansCan` = `bakedBeans_Can`).
    The film folder's ShotGrid project comes from `<H>\<FILM>\pipeline.json`
    (hand-written for NWF_SHF on 2026-10-12; the Setup tool would write it
    later).

  **ShotGrid asset ID (DECIDED in principle 2026-10-12, not built):**
  matching folder names to ShotGrid codes on every publish is fragile
  (renames, look-alike names), so the stable ShotGrid ID goes in two places:
  1. **In the asset's folder on the H drive:** e.g.
     `<H>\NWF_SHF\maya\assets\prop\backpack\asset.json` holding the
     ShotGrid ID, code and type. Tools read the ID instead of matching
     names. The Setup tool would write these when it creates the folders.
  2. **In the published asset itself:** a small `publishInfo` node (ShotGrid
     ID, department, version, source scene...) stamped into every publish.
     It travels into shots by reference (`backpack:publishInfo`), so a shot
     knows exactly which asset/version each reference is (needed later
     for shot publish §3c, and the "rig version on keyframe publishes"
     idea in §6).
     - Tested 2026-10-12: a `network` node made in the working scene just
       for the publish, then deleted, survives both selected-objects and
       whole-scene exports (.ma and .mb), and reads back through a
       reference. **No top-group rule needed.** Maya's `fileInfo` was
       tried first but is dropped by selected-objects exports.
     - Implies whole-scene publishes become an export of everything
       instead of a plain file copy.
  - Not chosen for now: stamping the ID in the *working* scene (so Add to
    List could pick the asset automatically). That would need a top-group
    rule.

  **The ID rule (DECIDED 2026-10-12):** only **two kinds of ShotGrid ID**
  are needed, and both already exist on ShotGrid: **Asset IDs** (one per
  asset; NWF has 19) and **Shot IDs** (one per shot; NWF has 76, e.g.
  `EAP_010_010` = 2560). Everything else is identified by combining an ID
  with the department code and version number. No new ShotGrid entities
  are needed for cameras, caches or keys, and students never create
  anything on ShotGrid for the tools to work.

  | Thing | Identified by |
  |---|---|
  | Backpack model v002 | Asset 1577 + `model` + v002 |
  | Shot camera v001 | Shot 2560 + `cam` + v001 |
  | Scout's anim cache in a shot | Shot 2560 + Scout's Asset ID + `anim` + v004 |

  - **Each thing keeps its own ID.** An asset referenced into a shot still
    carries its own Asset ID; the shot doesn't re-label it. That's how the
    same asset can be in many shots, and how the version record (anim
    publish) knows what each reference is.
  - **A camera has one ID: its shot's.** It belongs to the shot, so the
    Shot ID is its identity. No ShotGrid asset for cameras.
  - **Models and rigs have one ID: their own Asset ID.**
  - **Anything published from a shot carries two:** the Shot ID (where it
    goes: the shot folder, and the Version on that Shot) and the Asset ID
    (what it is, e.g. which character a cache belongs to).
  - Where IDs live on disk: `asset.json` in each asset folder, `shot.json`
    in each shot folder (Shot ID, code, sequence). Written once; later the
    Setup tool's job. The ShotGrid Version made on each publish is a record
    of the publish, not something the tools look up by.

  **Local publish frames:** once ShotGrid has the Version, the frames/movie
  made for it are deleted from scratch (kept if the upload failed).

  **Clearing scratch — moved to the Build tool (DECIDED 2026-10-12).** A
  "Clean Up Scratch" button in the Publish tool was tried and felt too
  scary: permanent deletion, one click under Publish. Since Build owns what's
  on scratch (§3e), it also handles taking things off. Build tool has a
  **My Scratch** tab:
  - Lists every asset/shot on scratch that holds files, with **size**,
    **latest publish** and a **status**: *Safe to remove* (nothing changed
    since the last publish, or only re-pullable copies), *Changed since last
    publish*, or *Not backed up* (never published; for shots, anything
    that isn't a pulled asset, since shot publishing isn't built yet).
  - Removal sends files to the **Recycle Bin** (undoable); folders and
    `workspace.mel` stay (1:1 mirror). Never touches the H drive.
  - **Safe:** a normal "Are you sure?" with what goes. **Risky:** lists the
    files at risk and the student must **type the asset/shot name**.
  - v0 rule: an asset is only "safe" if every file is a scene in `scenes\`
    older than its newest publish. Textures etc. aren't published yet, so
    they always count as at risk. Publish time = the H-drive file's
    creation time.

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

  **One click (DECIDED 2026-10-12):** the button is called **Build Shot**.
  The student picks an **Asset** + **Department** from the H drive and
  **adds it to the shot's list** (as many as the shot needs); Build Shot
  then, for every asset in the list, pulls it into the shot's `assets\`
  folder and **references it into the open scene**, setting the shot as the
  Maya project first. Already-built assets are updated if a different
  version is chosen (overwrite + reload), never referenced twice. The
  version dropdown starts at the version the shot already has, so updating
  is a deliberate choice, not automatic.

  Implementation (v0, 2026-10-12): the published list comes straight from
  the H drive's `<asset>_<code>_v###` files (no ShotGrid). Each shot keeps
  `assets\build_manifest.json` recording the version pulled per
  asset/department; comparing it with the H drive gives "v002 available".
  Updating overwrites the fixed-name file and reloads any reference to it in
  the open scene. "Reference into Open Scene" stores the project-relative
  path when the shot is the current Maya project (§3g rule 2). Known gap:
  if a department switches `.mb` ↔ `.ma` between versions, the fixed name
  changes and references need re-pointing (the tool warns).

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
  department subfolder in the shot. The tools' Department menus show the full label only.
  Chosen because it will make more sense to students: the same word
  everywhere.

  | Label | Code |
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
  window), replacing the shelf-per-department studio model, which is too
  much overhead for generalist students. Department list/order:
  **Modeling, Rigging, Previs, Anim, Creature, LookDev, FX, Render**.
  - ~~A tab per department, each with its own Publish button~~ —
    superseded the same day: the Publish tool now uses the **Build tool's
    layout** as its template. Pick an **Asset** + **Department**, **add it
    to a list**; each row is one publish with its own objects (empty =
    whole scene). **Add to List takes whatever is selected in Maya** as
    that row's objects (nothing selected = whole scene). One **Publish** click publishes every row, one ShotGrid
    Version each, so several assets can come out of one scene.
  - Live departments (v0): Modeling, Rigging, Creature, LookDev (all
    publish an asset scene the same way). Previs, Anim, FX, Render are
    shot work, shown "coming soon" until shot publishing exists.
  - First test: the `Backpack` prop (ShotGrid Asset id 1577).

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

  **Namespaces (DECIDED 2026-10-12)**: names were stacking up, e.g.
  `backpack1:backpack:backPack_previs_001`: `backpack1:` from Build Shot
  (a clash) and `backpack:` baked into v002 because the working scene had
  it. Rules:
  - **Published files never carry a namespace.** Publish takes them off
    in the published file only: namespaced nodes are renamed for the
    moment of export, then every name is put back by node UUID, so the
    working scene ends unchanged. Nothing is deleted or merged. The status
    line says which namespaces were taken off. A whole-scene publish with
    namespaces is exported; a clean one is still copied. Name clashes
    while stripping get Maya's usual number (`lambert7` → `lambert8`).
  - **Build Shot always uses the clean namespace** (`backpack:`). An empty
    leftover namespace is removed first. One still holding nodes is
    explained ("already used in this scene by ..."), never turned into
    `backpack1:`. An existing reference under another namespace (shots
    built before this rule) is moved to the clean one when it's free;
    keys on it survive, including save + reopen.

  **Shot publishes always use the whole timeline (DECIDED 2026-10-12):**
  anything published under a shot (cameras, characters' animation, props
  moving in the shot, ...) bakes and sends to ShotGrid the **whole
  playback range**. The ShotSub frames setting (default 2) applies to
  asset publishes only. In the Publish tool, a row whose target is a shot
  always gets the whole range.

  **Cameras (started 2026-10-12)**
  - **DECIDED:** a camera **belongs to a shot**, not to the asset library.
    First test: shot `EAP_010_010` (ShotGrid Shot id 2560, Sequence
    `EAP_010`).
  - **DECIDED: camera and keys are stored separately.** Two files per
    camera publish: the camera (all its settings, no keys) and its keys
    (baked curves plus a small map of which curve drives which attribute).
    Build Shot references the camera, then imports the keys and connects
    them, in one click.
  - **DECIDED: keys are baked before publishing** (a key every frame) so
    the curve shape survives whatever made it: rig parents, constraints,
    tangents, expressions. Every animated or driven attribute on the camera
    shape is found automatically and baked, not from a hand-made list (e.g.
    focal length, film offset, locator scale).
  - **DECIDED: all camera data is captured**: film back, film fit,
    overscan, gates, display options, clip planes, etc. These travel in the
    camera file because they belong to the camera node.
  - **DECIDED: no scale on cameras.** The published camera is always scale
    1 with no scale keys, and the scale channels are locked, because camera
    scale breaks Arnold renders. Rig parent scale is not carried over;
    position and rotation are baked in world space.
  - Prototype test (2026-10-12, mayapy, not in the tools yet): a camera
    under a ×2-scaled, rotating rig, aim-constrained, with spline keys,
    keyed focal length / film offsets / locator scale, an expression on
    camera scale, and non-default film back and display settings. It was
    baked, split into `EAP_010_010_cam_v001.ma` +
    `EAP_010_010_camAnim_v001.ma`/`.json`, and rebuilt in a fresh scene.
    World position and rotation plus 148 shape attributes matched on all
    48 frames; scale was 1 and locked.
  - **v0 built (2026-10-12)**: `publishDev/publishTool_camera.py` + Publish
    UI + Build tool. Choices made to get it testable (not yet agreed):
    department **Camera**, code `cam`, offered only when the open scene is
    a shot scene; keys baked over the playback range (the ShotSub frames
    setting only affects ShotGrid); both files always `.ma`; one version
    number covers camera + keys; ~~in the shot the camera is
    `assets\camera\cam.ma` referenced as `cam:shotCam`~~ (superseded, see
    below); ShotGrid Version on the Shot by name match (until
    `shot.json`). Checks: a Camera row takes exactly one camera (not
    persp/top/front/side); an asset row refuses anything containing a
    camera. Camera Scale ≠ 1 gives a warning, not a change. Image planes
    and anything parented under the camera are left out.
    Tested end to end on throwaway drives (ShotGrid stubbed), 28 checks:
    v001 + v002 published; Build Shot matches the layout camera every
    frame, survives save + reopen, no double reference on rebuild, roll
    back to v001 works with no leftover curves.
  - **DECIDED: in the shot the camera is live, not referenced.** Build
    Shot imports it, always named **`camera1`** (shape `cameraShape1`),
    and connects its keys. An existing `camera1` is renamed
    **`camera1_old`** first (then `camera1_old1`, ...); nothing is
    deleted. A camera from before this change (referenced `cam:shotCam`)
    is made live and renamed the same way.
  - **DECIDED: the camera is locked** so an animator can't edit its keys by
    accident. Tested 2026-10-12: locking only the channels is NOT enough,
    because the Graph Editor can still move keys. So the build locks
    three things: every keyable channel on camera1 and its shape, the
    curves' key data, and the curve nodes. All accidental edits were
    blocked (Graph Editor move, set key, delete keys, delete curve, typing
    a value), the camera still plays, and the locks survive save + reopen.
    camera1 is stamped `pipeShot` / `pipeCameraVersion`, which is how a
    rebuild knows it's already up to date.
  - Tested end to end (44 checks, throwaway drives): including a student's
    own camera1 moved to camera1_old with its keys, rollback keeping the
    previous camera as camera1_old1 (still protected), and an old
    referenced camera converted.
  - OPEN: image planes (frame offset); whether a hand-edited key in the
    shot should be overwritten or warned about when keys are updated; the
    shape's `cameraScale` attribute (different from transform scale).
  - OPEN: which scene it's published from (previs/layout shot scene?);
    file format (`.ma` now, Alembic/FBX later?); department/code (`cam`?
    `previs`?). If it's
    published from a shot scene, the Publish tool needs to learn shot
    scenes, and the ShotGrid Version goes on the Shot, not an Asset.
  - SUGGESTION: it lands in the shot's own `scenes\` on the H drive, e.g.
    `F:\NWF_SHF\maya\sequences\EAP_010\EAP_010_010\scenes\EAP_010_010_cam_v001.ma`,
    following "same folder as the work" above. Not agreed yet.
  **Animation publish (started 2026-10-12)**
  - **DECIDED: an anim publish hands on everything:** baked keys per
    character/prop, Alembic caches per character/prop, the camera keys,
    and the whole animation scene.
  - **DECIDED: every anim publish records the exact version of every asset
    used in the shot** (rigs, props, sets, camera), so that if an update
    breaks something, the shot can be rolled back.
  - SUGGESTION (not agreed): the tool knows what each thing in the scene
    is from where it came from. Everything arrived by Build Shot as a
    stamped reference (`publishInfo`), so a **Scan Scene** fills the
    publish list automatically: rig → that character's anim in this shot;
    camera → the shot camera keys; anything unstamped is flagged
    "Unknown, not from Build Shot" for the student to decide. Destination
    is always the shot.
  - SUGGESTION (not agreed): the version record is read from the stamps
    actually in the scene (the truth), cross-checked against
    `build_manifest.json`, and saved next to the publish on the H drive
    (e.g. `EAP_010_010_anim_v004.json`) and in the ShotGrid Version's
    notes. Build Shot gets a "Restore versions from…" option that re-pulls
    exactly those versions. This only works if published versions on the
    H drive are never deleted or overwritten (already read-only).

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
