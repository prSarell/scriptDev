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

### 3c. Publish (publish tool) — stage 2
**Iterative and final publish (RULE, user 2026-10-23; supersedes "after
approval only" below).** "The only thing we need the approval for is to
trigger the caches etc. That's all a final publish is. Same as an iterative
publish but with caches as defined by the rules we have been creating for
each department." So:
- **Iterative publish**: never blocked by approval. It's also how students
  move work between machines (§3h, "Wip between machines: CLOSED").
- **Final publish**: the same publish, plus that department's caches/outputs.
  It happens when the department's approval is in place (for shots, an
  Approved Version on the Final task, 2026-10-19).
- Approval gates nothing except those caches/outputs.

The original 2026-10 plan, kept for history: once the shot is approved, the
animator publishes with the **publish tool**:
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
- Reference paths work from any drive because of `$PIPE_SCRATCH`; students
  also need the versions their shot uses in that drive's `publish\` (§3i
  "Reference paths that work on any drive", 2026-10-13).

**Development / test setups:**

| Setup | Scratch | H drive |
|---|---|---|
| Home machine, 2026-10-12 | `D:` (Bean): `D:\NWF_SHF\` | `F:` (One Touch), **today only**: `F:\NWF_SHF\` |
| RMIT test install | lab scratch drive | lab H drive (setup may change) |
| **T7, from 2026-10-15** (home + RMIT test machine) | `G:\scratch\NWF_SHF\` (seeded from `D:\NWF_SHF`) | `G:\H\NWF_SHF\` (copied from the One Touch, dates and read-only locks kept) |

T7 setup checked 2026-10-15 (mayapy): Build lists backpack model
v001–v003 and the EAP_010_010 camera from `G:\H`; `shotSetup_003.ma`
opened from `G:\scratch` sets `PIPE_SCRATCH=G:/scratch` and loads the
backpack v003 reference and `camera1`. `build_manifest.json` still holds
`F:\` paths in `"source"`, which is a record only; the tools never read
it back. Installer: `G:\mpPipe\mpPipe.zip`.

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
  **Update 2026-10-20 (user):** every 3–4 weeks, unannounced; Maya prefs
  survive. Impacts in §4a.

**SUGGESTION (not agreed):** drive letters differ between these setups (and
will at RMIT), so the tools should never hard-code `D:\`/`H:\`. Each location
(H drive root, scratch root) would be a setting.

### 3i. Tools and build order — DECIDED (2026-10-12)

The tools are developed side by side:

- **Build tool**: pulls H drive → scratch (§3a, §3e). **Active, from 2026-10-12.**
- **Publish tool**: scratch → H drive; approval only triggers caches (§3c). **Active, from 2026-10-12.**
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

  **One shared publish folder on scratch (DECIDED 2026-10-13, replaces
  step 3 above):** "We should not be saving the rigs and the assets to each
  individual shot." Copying an asset into every shot that uses it adds up
  quickly. Instead, everything Build Shot pulls from the H drive (assets
  and their textures) goes into one folder on the student's scratch,
  `D:\NWF_SHF\maya\publish\`, shared by all their shots. Image sequences,
  caches and the like stay in each shot's own folder on scratch. Shots no
  longer keep assets in their own `assets\` folder.

  - **Changed for rigs 2026-10-20 (§4a, option C):** each shot references
    a fixed name hardlinked to a version here; every shot follows an
    update by default. Models still work as below.
  - **Each version is its own file (DECIDED 2026-10-13).** The shared folder
    keeps published versions side by side under their published names, e.g.
    `publish\assets\character\scout\scenes\scout_rig_v002.mb` and `..._v003.mb`.
    Each shot references the exact version it uses, and the shot's build
    manifest records it. The fixed-name overwrite in steps 3 and 4 is
    dropped for this reason: one file shared by every shot meant
    "versioning up breaks the animation in that shot" for every shot at
    once.
    - **Update** is per shot. Pull the new version if it isn't there yet,
      then repoint only that shot's reference ("Replace Reference"). Keys
      carry over when the control names match.
    - **Roll back** by picking the old version again. H drive publishes are
      never overwritten, so any version can be pulled again.
    - Textures sit with the model version they were published with.
    - Rule for riggers (SUGGESTION): don't rename or restructure controls in
      a rig update, because Maya matches keys by node name.
  - **Clearing old versions (DECIDED 2026-10-13).**
    - **My Scratch** lists every version in `publish\` that no shot's build
      manifest points to as "Not used by any shot". Its textures are listed
      with it and go with it.
    - Pulled copies that still match the H drive are *Safe to remove*. They
      go to the Recycle Bin, with the usual confirmation.
    - **Prompt after update:** once a shot is updated, Build Shot asks "scout
      rig v002 is no longer used by any of your shots. Remove it?" Nothing is
      ever removed without asking.
    - **Old saves, option (a):** the manifest only knows what each shot uses
      now, so an older save of a shot may still reference a removed version.
      That's accepted. Build Shot gets a **Repair** that finds missing
      references in the open scene and pulls those exact versions back from
      the H drive. Scene files are not scanned, because `.mb` files can't be
      read reliably.
  - OPEN: H drive versions are kept for the whole project, because rollback
    depends on them. Archiving at the end of term would be a staff job, not a
    student one, and is still to be decided.
  - **Layout (DECIDED 2026-10-13):** `publish\` mirrors the H drive layout
    exactly, so the path under `maya\` is the same on both drives:
    ```
    F:\NWF_SHF\maya\assets\prop\backpack\scenes\backpack_model_v002.mb          <- H drive
    D:\NWF_SHF\maya\publish\assets\prop\backpack\scenes\backpack_model_v002.mb  <- scratch
    ```
  - **Cameras stay in the shot (DECIDED 2026-10-13).** A shot camera
    belongs to one shot, so its pulled files stay in that shot's folder, as
    now.
  - **Shots already built (DECIDED 2026-10-13):** no migration. Old
    per-shot asset copies are deleted and rebuilt with Build Shot. Done on
    this machine for EAP_010_010; its camera files stay. The deleted
    `backpack.ma` went to the Recycle Bin, and the backpack entry was taken
    out of that shot's `build_manifest.json`. The H drive was not touched.
    Old scenes that still reference the in-shot copy (e.g.
    `shotSetup_001/002.ma`) are fixed by adding the asset in Build Shot and
    building, which repoints the reference.

  **Reference paths that work on any drive: `PIPE_SCRATCH` (DECIDED
  2026-10-13).**
  - **Problem.** `publish\` is outside the shot project, so a reference into
    it can't be project-relative. A full path (`D:/NWF_SHF/maya/publish/...`)
    is saved into the scene and breaks whenever the shot is opened from
    another drive. That happens to a student moving between classrooms, a
    portable copy of their work (§3h), or staff opening a student's shot.
  - **Tested 2026-10-13** (mayapy): a shot was built on one drive, the film
    folder copied to another, and the first drive removed.

    | How the path is written | Opens on the other drive? |
    |---|---|
    | full path `D:/...` | no, the reference is missing |
    | relative `../../../../publish/...` | yes, but only because Maya falls back to the scene file's own folder. It breaks if the scene is saved one folder deeper. Rejected as fragile. |
    | `$PIPE_SCRATCH/NWF_SHF/maya/publish/...` | yes, whatever the Maya project is |
  - **Decision.** References into `publish\` are written as
    `$PIPE_SCRATCH/<FILM>/maya/publish/...`. Maya fills in the variable each
    time it loads the reference.
  - **What the variable holds.** Only the folder that contains the film
    folders: `D:`, `E:` or `E:/MyWork`. The film's name stays in the path,
    so **one variable covers every film and every class**. Nothing changes
    per film, class or student. The name is generic (`PIPE_SCRATCH`, not
    `NWF_...`) on purpose.
  - **Who sets it, and when.**
    1. **Before every scene open.** A Maya "before open" callback sets it to
       the drive of the scene being opened, before Maya loads that scene's
       references. So a shot opened from `E:` loads `E:\...\publish`.
       Scenes opened from the H drive (published files) and paths outside a
       film folder leave it unchanged.
    2. **At Maya startup**, from the saved scratch drive setting, until a
       scene is opened.
    3. **By Build Shot**, from the shot it's building, just before it writes
       references.
    The callback is registered at startup by a marked block in the user's
    `scripts\userSetup.py`, added by the mpPipe installer (see
    Implementation).
  - **Several projects and classes at once.** This works, because Maya has
    one scene open at a time and the variable is reset on every open. A
    student can switch between film A on `D:` and film B on `E:`. Not
    supported: a scene referencing a different film's files on a different
    drive. The pipeline assumes each film uses only its own published
    assets, which is already how Publish and Build work.
  - **Existing full-path references** are rewritten to `$PIPE_SCRATCH`
    automatically the next time that shot is built.
  - **Limits.**
    - A machine without mpPipe installed doesn't set the variable, so the
      references show as missing there. Install mpPipe on any machine that
      opens student shots (staff included).
    - The shot only opens fully if the versions it uses are in that drive's
      `publish\` folder. A version in `publish\` never changes once pulled,
      so it is identical on every drive. A student who copies a shot to
      another drive also needs those versions: copy them across, or run
      Build Shot or Repair on that drive to pull them from the H drive.
  - Texture paths can use the same variable once texture publishing is
    designed (§4 Textures, which is waiting on a look at Substance Painter's
    export).

  **Scratch drive follows the work (DECIDED 2026-10-13).** "Students will
  be moving around and working on different scratch drives in different
  class rooms." A scratch setting saved on one machine can be wrong on the
  next, so the tools don't rely on it:
  1. **A scene is open.** Build and Publish take the scratch drive from
     where the open scene is, if it's inside a film folder that isn't on
     the H drive. The new drive is saved as the setting and the tool says
     so ("Scratch drive set to E:\, where the open scene is."). The Build
     tool checks when it opens and when Refresh is clicked; the Publish tool
     checks on each refresh.
  2. **No scene is open.** The saved setting is used.
  3. **The saved drive isn't on this machine.** The tool says so plainly and
     asks the student to Browse, or to open a scene from their scratch drive.
  The H drive stays a single saved setting. ANSWERED (2026-10-22): the H
  drive has the same letter in every classroom, and Maya prefs follow
  students between machines (they live on the H drive). So the saved
  scratch setting is whatever drive the student last used, in whichever
  room: it's often stale, which is why every tool (Build, Publish, Project
  Tool) follows the open scene.

  **Moving between rooms (reminder of the §3h decision, unchanged).** The
  H drive carries only publishes. A student's own working files (shot
  scenes, wip asset scenes, caches, image sequences) stay on the scratch
  drive they were made on. Students move those themselves (portable drive
  or cloud), and the tools don't manage it. On a new machine, Build Shot
  pulls whatever published versions are missing there. With students
  changing rooms often, this copying is a regular chore with a risk of
  copying old over new. Noted, not reopened.

  **Wip between machines: CLOSED (2026-10-23), the §3h answer stands.**
  Reopened 2026-10-22 and talked through 2026-10-23. The user: "I don't
  think we need to account for unpublished work. That's on the students.
  We have two types of publish. Iterative and final to cover that." So the
  pipe doesn't manage unpublished work. Wip scenes, wip texture paths,
  caches and image sequences stay the student's job. A student who wants
  work on another machine makes an **iterative publish**, which isn't
  blocked by approval (§3c, 2026-10-19), and Builds it there. Dropped: wip
  texture repointing on open, and a "save my wip to H" action.

  **Implementation (v0, 2026-10-13).**
  - `pipeDev/buildDev/buildTool_api.py`:
    - `copy_published` copies one H-drive file into `publish\` under the
      same path, read-only, and skips it if an identical-size copy is there.
    - `pull` uses `copy_published` and records `{"version", "shared":
      "<path under maya/publish>", "source", "pulled"}` in the shot's
      `assets\build_manifest.json`.
    - `entry_path` gives the full path for a manifest entry: shared for
      assets, in the shot for cameras.
    - `build_asset(shot_dir, published, version)` returns
      `(done, warning, replaced)`. It sets `PIPE_SCRATCH` from the shot,
      references with a `$PIPE_SCRATCH` path, repoints a reference to
      another version or to an old in-shot copy (`legacy_rel_path`, `.ma`
      or `.mb`, absolute or project-relative), and rewrites full-path
      references. It never references twice.
    - `scene_references()` gives `(node, as written, full, resolved)` for
      top-level references, including missing ones.
    - `shots_using` / `unused_versions` find versions that no shot's
      manifest uses and the open scene doesn't reference.
    - `repair_scene(h_root)` pulls missing `publish\` files back from the H
      drive and loads them (keeping `$PIPE_SCRATCH`). It explains old
      in-shot copies, and a missing variable.
  - `pipeDev/buildDev/pipeEnv.py`: the variable (`VAR = "PIPE_SCRATCH"`).
    - `set_from_path` (ignores the H drive), `to_var_path`, `uses_var`.
    - `install()` sets the starting value and registers the before-open
      callback. Its id is kept on `sys._pipeEnv_callback_id`, so a reinstall
      or reload replaces it instead of adding a second one.
  - `pipeDev/buildDev/buildTool_ui.py`: the prompt after update, the
    **Repair** button, and following the open scene (on open and Refresh).
  - `pipeDev/publishDev/publishTool_api.py`: `follow_open_scene(h_root,
    scratch_root)` and clearer `check_roots` messages. `publishTool_ui.py`
    calls it on each refresh.
  - `pipeDev/pipelineInstaller/install.py` writes this block at the end of
    `<maya>/scripts/userSetup.py`, replaced on reinstall, never duplicated,
    and leaving other lines (mpToolSet, mpInstaller) alone:
    ```
    # -- mpPipe BEGIN --
    try:
        import pipeEnv; pipeEnv.install()
    except Exception as _mpPipe_error:
        print('mpPipe: PIPE_SCRATCH not set up: %s' % _mpPipe_error)
    # -- mpPipe END --
    ```
    It also runs it immediately, so no restart is needed, and records
    `usersetup:<path>` in `mpPipe_manifest.txt`. `uninstall.py` removes
    only that block and the callback. `build_zip.py` and the shelf now
    include and reload `pipeEnv.py`.

  **Troubleshooting checklist.**
  - *Shot opens with a missing backpack/rig.* Script Editor:
    `import os; print(os.environ.get("PIPE_SCRATCH"))`.
    - Empty: mpPipe isn't installed or its startup block didn't run. Check
      `userSetup.py` for the `# -- mpPipe BEGIN --` block and the Script
      Editor for "mpPipe: PIPE_SCRATCH not set up".
    - Wrong drive: the scene was opened before mpPipe was installed. Reopen
      it.
    - Right drive, file missing: that version isn't in this drive's
      `publish\`. Click **Repair** in Build Shot.
  - *How is a reference written?* In the `.ma`, look for a line like
    `file -r ... "$PIPE_SCRATCH/NWF_SHF/maya/publish/..."`. A `D:/...` path
    means an older build; building the shot again rewrites it.
  - *Which version does a shot use?* `<shot>\assets\build_manifest.json`,
    key `<type>/<asset>/<dept>`, fields `version` and `shared`.
  - *Tool shows the wrong scratch drive.* Open a scene from the right drive
    and click Refresh, or Browse. The setting is in Maya prefs
    `pipeline_config.json` (`scratch_root`).

  **Tests.** `pipeDev/buildDev/test_buildTool_mayapy.py` (headless,
  mayapy) runs on throwaway folders and a throwaway settings file. It
  never touches the real drives or Maya prefs. 2026-10-13: 56/56 pass,
  covering:
  - per-shot versions, keys surviving an update, rollback, and the
    removal check;
  - Repair, and old in-shot references (absolute, and project-relative from
    a copy of the real `shotSetup_002.ma`);
  - `$PIPE_SCRATCH` writing, rewriting full paths, and the callback after
    moving the film to another drive (references and keys load);
  - H-drive opens leaving the variable alone;
  - scratch-follows-scene steps 1–3;
  - the userSetup block on install, reinstall and uninstall.

  **Not built yet:** My Scratch doesn't list `publish\` (versions not used
  by any shot); textures aren't pulled, because texture publishing isn't
  designed yet.

  **One click (DECIDED 2026-10-12):** the button is called **Build Shot**.
  The student picks an **Asset** + **Department** from the H drive and
  **adds it to the shot's list** (as many as the shot needs); Build Shot
  then, for every asset in the list, pulls it into the shot's `assets\`
  folder and **references it into the open scene**, setting the shot as the
  Maya project first. Already-built assets are updated if a different
  version is chosen (overwrite + reload), never referenced twice. The
  version dropdown starts at the version the shot already has, so updating
  is a deliberate choice, not automatic.

  Implementation (v0, 2026-10-12; the fixed-name copy in the shot is
  superseded 2026-10-13 by the shared publish folder above): the published list comes straight from
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
  - (2026-10-20: cameras now sit in a `<shot>_cam_GRP` with a
    `camera1_DATA` node driving them; see "Camera group (DECIDED + built
    2026-10-20)" in §4.)
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

- **Textures in a model publish (raised 2026-10-12, to discuss).** Today a
  publish copies/exports only the Maya scene; file texture nodes keep
  pointing at the asset's `sourceimages` on **scratch**. So a published,
  textured prop shows missing textures on other machines or in other
  students' shots, and breaks if that scratch copy is cleaned up (My
  Scratch).
  - **DECIDED (2026-10-12):** textures **live on the H drive**, are
    **published with the model**, and **Build Shot pulls them from the H
    drive** and loads them onto the right model in the shot.
  - **DECIDED (2026-10-12): there is no separate texture publish.** A
    texture update means a **new model publish**. Textures are versioned
    with the model: model v004 always means v004's textures.
  - **DECIDED for now (2026-10-12): every model version gets its own full
    copy of its textures.** It's the simplest and safest choice. Revisit
    once we know how students work and how much drive space they have:
    sharing unchanged textures between versions (each version recording
    which files it uses) stays on the table, as does everything else
    about storage.
  - SUGGESTION from the user (on hold): put textures in `sourceimages`, in
    a structure that mirrors the assets folder. Before choosing a folder
    layout, look closely at how Substance Painter exports shaders and
    textures (export presets, file naming, UDIMs, whether it writes
    shaders or just maps).
  - OPEN (for next session): the exact folder on
    the H drive (e.g. the asset's `sourceimages\`); how paths are written
    in the published file so they resolve from any drive (likely
    `$PIPE_SCRATCH`, as for references, §3i); where Build Shot
    puts them in the shot (e.g. beside the pulled model) and how it
    re-points the file nodes.
  - **Texture workflow through rigging (user, 2026-10-20; agreed in
    principle, not built):** "Rigger pulls the published model asset. The
    pipe saves the textures in the source images folder of the rig
    project. The rigger builds the rig and skins the live textured
    unreferenced model and publish the rig. The textures get saved with the
    rig publish in the source images folder. The animator builds the shot
    with the rig, the rig and textures are saved into the publish/ folder
    on the scratch drive."
    - What the pipe has to do: (1) model publish carries its textures (not
      built yet, comes first); (2) pulling a model for rigging copies that
      version's textures into the rig project's `sourceimages` and
      re-points the file nodes; (3) rig publish collects every file its
      file nodes use (incl. UDIM tiles, sequences, `.tx`), copies them to
      H with that rig version, rewrites paths to `$PIPE_SCRATCH` form, and
      stops on missing textures; (4) Build pulls them into scratch
      `publish\` with the rig (also covers Restore after a wipe).
  - **Two texture sets per model publish (DECIDED 2026-10-20).** The user:
    "we are not going to need heavy render ready textures for the rigs
    during animation. So I guess the models would hold a highres texture
    publish, but also need a low res publish for rigging. We need to build
    that into the model publish specs." So a model publish carries a
    full-res (render) set and a low-res (anim) set; pulling for rigging
    takes only the low-res set, so rigs and shots stay light.
    - SUGGESTION (not agreed): same file names in both, in sibling folders
      per version, e.g. `sourceimages\<login>\model_v004\render\` and
      `...\anim\`, so switching is a folder swap in the paths, not a
      rewire. Pulled textures go in their own subfolder of the rig
      project's `sourceimages` (e.g. `pulled\model_v004\`) so they never
      overwrite working textures.
    - Answers 2026-10-20: the artist exports the low-res set themselves
      (option b); the size is "up to the texture artist". (Then superseded
      the same day, below: the render set moves out of the model publish.)
    - Claude's folder-swap and "two shader sets in the model publish,
      paired `_render_MTL`/`_anim_MTL`" suggestions: dropped, superseded by
      the LookDev step below.
  - **LookDev is its own step and publish (DECIDED 2026-10-20, replaces
    the two texture sets above).** The user: "We need a lookdev stage or
    task as part of the modeling and a look dev publish would hold the
    renderable textures as a separate thing. So model publish would always
    be lowres placeholder textures for animation. lookdev publish would be
    the renderable textures."
    - **Model publish:** always low-res placeholder textures, made by the
      artist (size up to them). These are what rigs and shots carry.
    - **LookDev publish:** the render textures (and their shaders), a
      separate publish under the `lookDev` department code (already in
      the department list). Needs a LookDev task in ShotGrid (recorded in
      `shotgridTemplate_requirements.md`).
    - Unchanged: the texture workflow through rigging above (pull model
      -> textures into the rig project -> rig publish carries them ->
      Build pulls them into `publish\`), now with placeholder textures only.
  - **Rig publish carries its textures (built 2026-10-20, user: "can we
    add the texture handling to the rig publish process").**
    `pipeDev/publishDev/publishTool_textures.py` (shipped in the mpPipe
    zip):
    - Finds the texture nodes (`file`, `aiImage` when Arnold is loaded) on
      the shaders of what's published (selected objects and everything
      under them; whole scene = every one), not from references; every
      file each uses: UDIM tiles, image sequences, and an Arnold `.tx`
      beside a texture. Project-relative and `$VAR` paths resolved.
    - A missing texture stops the publish (with the other rig checks,
      before ShotGrid/playblast/H drive) and names the node; also checked
      when a Rigging row is added.
    - Copies them to H in a folder per version:
      `<asset>\sourceimages\<login>\<published file name>\`, e.g.
      `scout\sourceimages\scout\scout_scout_rig_v001\`. Files keep their
      names; a second source folder with a clashing name goes in its own
      numbered subfolder (whole folder, so tiles/sequences stay together).
      Read-only.
    - In the published file only, texture paths become
      `$PIPE_SCRATCH/<FILM>/maya/publish/<same path as on H>` (UDIM nodes
      keep their tile pattern); the working scene's paths are put back. A
      failed export removes the copied textures. A whole-scene rig with
      textures is exported, not copied. The ShotGrid note lists them.
    - Build: `copy_published()` also mirrors the version's texture folder
      into scratch `publish\` (so Build, Repair and Restore all bring
      them); clearing an unused version takes its textures with it
      (`version_files()`); Repair also re-pulls missing textures of
      anything the scene references (found in testing: after a wipe a
      rig's link still has its data, so only the textures were missing).
    - Test `pipeDev/publishDev/test_rigTextures_mayapy.py` 18/18; all
      other Publish/Build tests still pass.
    - Not yet: pulling a model's (placeholder) textures into the rig
      project (waits for model publishes to carry textures, same module
      can do it); opening a published rig straight from H shows textures
      missing unless that version is in scratch `publish\` (same as
      references).
    - OPEN: what a LookDev publish contains (shaders + render textures +
      which object gets which shader, no geometry? or a full textured
      model?); which model version it belongs to and what must match
      (object names, UVs); how lighting applies it (to the referenced rig,
      or to the Alembic caches from the shot publish, matched by object
      name); whether LookDev is a task on the Modeling step or its own
      step; who does it (same student or a texture artist); whether
      MetaHuman DNA files ride the rig's texture mechanism (pinned DNA
      question).
- **Could rigs be referenced straight from the H drive? (OPEN, test first.)**
  Maya reads a referenced file when the scene opens or the reference is
  reloaded. It doesn't keep reading it while you work. So a rig on the H
  drive probably costs time at open, not while animating. Things Maya
  reads again and again should stay local: textures (Arnold reads them at
  render time), Alembic and GPU caches (read every frame), and image-plane
  sequences.

  Before changing the scratch mirror, check these:
  - opening a scene with H-drive references vs scratch, timed at RMIT
    with a class working at once;
  - what happens when the H drive is missing (at home or offline);
  - drive letters differ between machines (F: here, H: at RMIT);
  - the rig's own textures and any nested references are also read from
    the H drive.
- **Personal work folders for group projects (raised 2026-10-13, OPEN).**
  The user, in their words: "the goal for this is to facilitate group
  projects. The idea is that multiple people/staff or students could build
  shots (if they are assigned to the project in shotgrid) work and publish
  their work. This would be handled in the file structure by adding folders
  in `D:\NWF_SHF\maya\assets\prop\backpack\scenes` and in
  `D:\NWF_SHF\maya\sequences\EAP_010\EAP_010_010\scenes` with a folder named
  after the student or staff # pulled from shotgrid."
  ```
  D:\NWF_SHF\maya\assets\prop\backpack\scenes\<person>\         <- that person's working files
  D:\NWF_SHF\maya\sequences\EAP_010\EAP_010_010\scenes\<person>\
  ```
  The intent is that the pipeline serves as both a teaching tool and a
  student production tool, for staff (with access to every class and
  project) and students alike.

  **Fact (from the user, 2026-10-13):** RMIT scratch drives are partitioned
  per login. "You can't work as another student or teacher on the scratch.
  Once you log on it knows it's you. You can't see anyone else's work on
  the machines." So personal folders are *not* needed to keep people apart
  on a shared machine; that was a wrong assumption on Claude's part. Their
  value is wherever work from several people meets, e.g. the H drive or
  anything copied between people. The Windows login also already
  identifies the person, which may answer how the tools know who's there.

  **On the H drive too (DECIDED 2026-10-13).** "Yes the multiple personal
  folders should exist on the H drive." Each asset's and shot's `scenes\`
  on the H drive holds one folder per person working on it, and scratch
  mirrors it 1:1, as everywhere else.

  **ASSUMPTION / dependency (2026-10-13):** "right now the H is
  partitioned, however I am working under the assumption that RMIT will
  change that." Today each login sees only its own H drive, so group work
  through a shared H drive can't happen yet. The whole group workflow
  (shared publishes, Build Shot pulling teammates' publishes, personal
  folders others can see) depends on RMIT giving a project group a shared
  H drive location. Until then, testing uses a single H drive (`F:` on the
  dev machine). If RMIT doesn't change it, this needs rethinking.

  **Strategy (from the user, 2026-10-15):** building the pipeline is meant
  to help shift RMIT to a less restrictive, shared server model. So the
  tools are designed for the shared-server target, not around today's
  per-login partitioning, and a working pipeline is part of the case for
  that change.
  - **Stand-in H drive (2026-10-15):** a Samsung T7 carried between home and
    the RMIT test machine plays the shared H drive: `<T7>\H\NWF_SHF\` (H
    drive setting `<T7>:\H`), with `<T7>\scratch\NWF_SHF\` as portable
    scratch and `<T7>\mpPipe\` for the installer. Any drive letter works,
    because references go through scratch `publish\` and `$PIPE_SCRATCH`,
    never the H drive. The two film folders must sit in separate
    top-level folders so the tools can tell H from scratch.
  - Swapping the T7 for a real server should be a settings change only.
    Keep any workaround for the partitioned setup out of the tools.

  Questions to settle:
  - **Who's at the machine (DECIDED 2026-10-13):** the RMIT Windows login
    matches the person's ShotGrid login ("yes the RMIT login matches their
    ShotGrid login"). The tools read the Windows login and look up the
    ShotGrid user with that login. Nobody picks themselves from a list.
    - **Folder name (DECIDED 2026-10-13):** the login itself, e.g.
      `scenes\s1234567\`.
    - **Not assigned = no access (DECIDED 2026-10-13):** "No fallback, if a
      student is not assigned to a project they have no access." The
      tools only work on films whose ShotGrid project lists the person.
      There is no "pick yourself" option.
    - **Exception (2026-10-13): "except with Mentors or ex-students no
      longer at RMIT."** Their ShotGrid login won't match an RMIT login,
      and they **can't reach the H drive**. PARKED (user, 2026-10-13):
      "Just keep them in mind for now… it may not be something we have to
      worry about." Don't design a route for them yet. Just avoid choices
      that would rule one out later.
    - OPEN: testing on the dev machine, whose Windows login (`scout`) isn't
      an RMIT/ShotGrid login. Under the rule above the tools would refuse.
    - **Staff problem (user, 2026-10-19):** "this is an issue for all
      staff". Staff have an RMIT ID like students, but their ShotGrid login
      is their email, which can't be worked out from the ID. Using the
      staff ID number would be "super helpful". Checked 2026-10-19: active
      ShotGrid users are 45 students on `s#######@student.rmit.edu.au`
      (derivable from the Windows login), 11 staff on `...@rmit.edu.au`
      emails, and 16 other logins (personal Gmail etc.). HumanUser has no
      ID field today.
      - **Direction agreed in principle (user, 2026-10-19):** add a field
        to ShotGrid's person (HumanUser) data that records **staff and
        student numbers**, and identify people by that **instead of their
        emails**. (Student emails contain the number; staff emails don't.)
        Tools find the person by `number == Windows login`. Not created
        yet.
      - SUGGESTION (not agreed): field name "RMIT ID" (`sg_rmit_id`),
        text; fill every student's from their email automatically, staff
        by hand once (later the Class Project Setup Tool). The dev
        machine's existing `publish_as` setting would then just hold an
        RMIT ID.
      - **Staff number format (user, 2026-10-19):** `e` + digits (e.g.
        `e123456`), vs. students' `s` + digits.
      - **Created 2026-10-19:** HumanUser text field **RMIT ID**
        (`sg_rmit_id`), site-wide. Filled for 46 people: every
        `s#######@student.rmit.edu.au` student (from the email) plus the
        user (`e` number). Staff and students on non-RMIT logins still need
        theirs entered. Tools don't read it yet.
      - ~~OPEN: go-ahead to create the field~~ (given 2026-10-19) (site-wide schema
        change, may need admin rights for the script user).
  - **How work reaches a personal folder on the H drive (DECIDED
    2026-10-13):** "the working files get into the personal folder on the
    H drive when a student publishes work from their scratch to the H
    drive." Publish is the only way in. There's no separate share step, and
    §1 still holds (nobody saves to the server by hand).
    - ~~OPEN: exactly what lands there~~ — **DECIDED 2026-10-15** (the
      user's answers):
      - **Publishes are personal.** The versioned publish goes in
        `scenes\<login>\` on the H drive, and the login is in the file
        name: `EAP_010_010_s1234567_anim_v003.ma`. The user: this is
        "mitigated by including the student number in the file name of
        the publish and by the student # inside the scenes folder". So
        **version numbers are per person**, and two people can't take the
        same `v###`. No separate concurrency guard is needed.
      - **Only the pipeline names published files.** "We are not locking
        students into a name convention on the scratch drive." Working
        files on scratch can be called anything and sit anywhere in the
        asset/shot project; Publish renames on the way to the H drive (as
        already decided in §3i).
      - **Alembic caches go in a per-person folder too:**
        `cache\alembic\<login>\`.
      - **Asset publishes follow the same rule, for now:** model, rig etc.
        go in `scenes\<login>\` with the login in the name. ("For now
        yes.")
      - **Latest = newest by time, across everyone (assets).** "Whoever's
        is the most recent published asset (not shot). Time stamp of the
        asset defines if it is the latest." Build Shot treats the most
        recently published file of an asset + department as the latest,
        whoever published it, and shows whose it is.
      - **Who's publishing, for testing:** the Windows login ("whatever is
        easiest for testing and moving between this machine and an RMIT
        lab machine"). See the OPEN item above about `scout`.
    - Is the working file copied alongside the publish? Not decided; the
      default is no.
    - **Built 2026-10-15** (asset and camera publishes; the shot publish
      will follow the same rule):
      - `publishTool_api.who()`: the Windows login, or `publish_as` in the
        machine's `pipeline_config.json` (for staff testing on a machine
        whose login isn't their RMIT one). Cleaned to lowercase letters and
        digits, since it sits between underscores in file names. The
        Publish window shows "Publishing as: <login>".
      - Assets: `<asset>\scenes\<login>\<asset>_<login>_<code>_v###.ma`.
        Cameras: `<shot>\scenes\<login>\<shot>_<login>_cam_v###.ma` +
        `_camAnim_v###.ma/.json`. Version numbers are counted in the
        person's own folder only.
      - Build lists every person's publishes. A version is identified as
        `<login>/v###` (e.g. `scout/v003`) and shown as "v003 (scout)".
        The latest is the newest by the H-drive file's creation time,
        whoever published it; the version menu lists newest first. A file
        only counts if it sits in the folder of the login in its name.
      - Each shot's `build_manifest.json` records `login` beside `version`.
        Entries from before (no login) match nothing on the H drive, so
        they show as "v003 (old)" with a newer version available, and
        building switches them over. camera1 gets a `pipeCameraBy` stamp
        beside `pipeCameraVersion`.
      - Old-style publishes (`backpack_model_v003.ma`, no login) are
        ignored by Build.
    - **Staff named by e-number (DECIDED + BUILT 2026-10-28):** "scout"
      (the dev machine's Windows login) read as the Scout character.
      `who()` is now `publish_as`, else `shotgrid_as` (the e-number the
      Project Tool already used for ShotGrid), else the Windows login. The
      dev machine publishes as `e131988`. The existing `scout` publishes on
      the T7 stay as they are (user: "going forward we will just publish
      on the pipe for future assets"): not renamed or migrated.
    - **Asset working folders (DECIDED + BUILT 2026-10-28):** every asset's
      `scenes\` has `model\`, `rig\` and `lookDev\` (named by department
      code), each with a folder per person: `scenes\rig\e131988\`. On the
      H drive and scratch, every asset type. h_sync adds them to new and
      existing assets; Set Project makes the person's own; Save Here uses
      the department's; Build skips them. Publishes still go in
      `scenes\<login>\`. Test: `projectDev/test_workFolders_mayapy.py`.
    - **Shot working folders (DECIDED + BUILT 2026-10-28):** the same for
      shots, so a shot can be built for rendering (caches, cameras,
      environment, everything a final render needs). The user proposed
      `scenes\Render\`, `Animation\`, `FX\` per shot with an `s`/`e`
      folder per person; agreed with these changes (user: "happy to go
      with your recommendations"): department codes, lowercase, plus
      `layout\` → every shot's `scenes\` has **`layout\`, `anim\`, `fx\`,
      `lighting\`**, each with a folder per person
      (`scenes\lighting\s1234567\`). **Lighting, not Render** (user,
      2026-10-28: "it's industry standard"): the department list's
      Render became Lighting (`lighting`), matching the Publish tool's
      coming-soon Lighting shot stage. **Previs dropped** from the
      department list the same day. h_sync adds them to new
      and existing shots; Set Project makes the person's own; Build's
      shot camera and keys lists skip them. Publishes still go in
      `scenes\<login>\`. `publishTool_api.SHOT_WORK_FOLDERS` (h_sync has
      its own copy). Tests: `projectDev/test_workFolders_mayapy.py`,
      `desktopDev/test_h_sync.py`.
      - **Animation caches per person (BUILT 2026-10-28):** the anim
        publish now writes caches to `cache\alembic\<login>\`, as decided
        2026-10-15 (it had been writing flat to `cache\alembic\`, where two
        people's `v003` would collide: versions are per person). Caches
        published before this (SEQ010_140's first final, 2026-10-28) stay
        where they are.
      - **Render output (DECIDED, not built):** `images\lighting\<login>\`,
        made when the render build exists.
    - **Build by department (DRAFT 2026-10-28, not built):** the user:
      the Build tool's Department dropdown should be the artist's
      department, "switching between the departments would define the
      types of data available through the build tool - it would basically
      filter out rigs for the lighting team etc." (today it mixes asset
      departments with Camera / Environment entries on the Shot side).
      Departments: Modeling, Rigging, Creature, LookDev, Layout,
      Animation, FX, Lighting. Draft of what each sees, from the user's
      corrections ("Modeling will need textures and lights too
      potentially", "Look dev will likely be doing lighting as well",
      "Rigging needs to see textures", "Creature needs rigs environments
      caches all assets really", "They will likely all need cameras"):

      | Department | Works in | Build offers |
      |---|---|---|
      | Modeling | asset | models, textures, lights, cameras |
      | Rigging | asset | models, textures, cameras |
      | Creature | asset and shot | everything |
      | LookDev | asset | models, textures, lookDev, lights, cameras |
      | Layout | shot | rigs, environment, camera |
      | Animation | shot | rigs, environment, camera, layout/anim keys |
      | FX | shot | animation caches, environment, camera |
      | Lighting | shot | animation caches, FX caches, full environment, camera, lookDev shaders, lights |

      - The department sets Asset vs Shot, except Creature (both).
      - OPEN: cameras in asset scenes: a shot's camera (pick the shot),
        a published turntable/lookDev camera, or both?
      - OPEN: lights aren't a publishable type yet (only lights inside an
        anim publish). A shared light rig publish for Modeling, LookDev
        and Lighting?
      - OPEN: "textures" for Modeling/Rigging: the ones that travel with
        the model/rig publish, or the render textures (lookDev)?
      - OPEN: FX gets rigs? Animation gets caches?
      - Not buildable yet: animation/FX caches, lookDev shaders on caches,
        lights.
    - **Build into an asset scene = import, never reference (DECIDED +
      BUILT 2026-10-28):** "if an artist pulls a published asset from the
      h drive it should not be referenced... a rule for all assets, so the
      referencing only really applies to the shot building." With an asset
      scene open, Build Shot becomes **Import into Asset**: any published
      asset/department of the film (not shot cameras) is pulled to scratch
      `publish\` and imported as published (stamped pipe group, no
      namespace). Its version texture folder (textures + DNA) is copied
      into `<asset>\sourceimages\<published file name>\` (writable, the
      asset's own) and the texture/image-plane nodes and the group's
      `pipe_dna` list point there. Already in the scene (by its stamp) =
      asks before importing again; nothing is deleted. No shot list, keys
      or manifest for assets. Test: `buildDev/test_assetImport_mayapy.py`.
      - Tests: `test_buildTool_mayapy.py` 76/76 (2026-10-15), including
        two people's series, latest by time, `publish_as`, and a camera
        published by Publish's own code and built by Build Shot.
  - **Overwriting (DECIDED 2026-10-13):** "People can overwrite their own
    work on the scratch drive but not on the H drive." The H drive is
    add-only: every publish is a new locked version, and nothing there is
    ever overwritten. That's already how Publish works (read-only,
    `_v###`, never reused).
  - Whether the tools only offer projects the person is assigned to in
    ShotGrid.
  - ~~SUGGESTION (Claude's): published files stay as they are
    (`scenes\<asset>_<dept>_v###`, one version series per asset, not per
    person).~~ Superseded 2026-10-15: publishes are personal (above).
  - Effects on what's built: Publish works out the asset or shot from the
    scene's folder, so it must accept `scenes\<person>\`. My Scratch's
    "safe to remove" check assumes scenes sit directly in `scenes\`.
    `PIPE_SCRATCH` and `publish\` are unaffected.
  - Linked: how staff review student shots, and the guard on "scratch
    follows the open scene" for files opened from shares (raised the same
    day).
- **Publish levels and formats for other software (raised 2026-10-13,
  OPEN).** The user, in their words: "This tool needs to be able to
  publish assets that can be used in other 3D software. I want to have
  levels of publish eg different types of approval trigger different types
  of publishes. So we don't clog up the H drive with caches and different
  file variations with every publish."
  - Formats: which software and formats (e.g. FBX, OBJ, Alembic, USD), per
    department.
  - Levels: what the levels are, and what triggers each one (e.g. a
    ShotGrid approval status).
  - When: approval usually comes *after* the publish, so do the extra
    formats get made later, from the locked file already on the H drive?
    By whom (staff, the student, automatically)?
  - Where the extra formats live on the H drive.
  - Linked: textures and Substance Painter (§4 Textures), which needs a
    mesh export from Maya.
  - Linked: the software folders beside `maya\` in the film folder (§3f):
    `afterEffects`, `blender`, `davinciResolve`, `dragonframe`, `houdini`,
    `photoshop`, `premiere`, `substancePainter`, `toonBoom`, `tvPaint`,
    `unreal`. OPEN: do exports for a piece of software land in its folder?
  - **Approach (DECIDED 2026-10-13):** "Let's start with a full publish and
    work backwards from there." First define everything a full publish
    produces; the lower levels are then subsets of it.
  - **Draft full publish for a model (2026-10-13, user: "That looks
    good"):**
    1. the locked `.ma` (as now);
    2. a ShotGrid Version with movie and notes (as now);
    3. FBX for Unreal and Blender;
    4. FBX/OBJ with UVs for Substance Painter;
    5. USD;
    6. an Alembic cache;
    7. textures (on hold);
    8. a turntable or stills.

    Where exports land is still OPEN.
  - **Alembic cache (DECIDED 2026-10-13):** "we would want a full cache of
    all the geometry not a single static frame (I am speaking about any
    asset with keyframes. Not a set or environment for example that would
    be a static frame.)"
    - An asset with keyframes gets a full cache of all its geometry, over
      the whole range.
    - A static asset (a set, an environment) gets a single frame.
    - OPEN: whether the tool decides this by itself (anything animated in
      what's published means full range), and what "the whole range" is
      for an asset publish. Shot publishes already always use the whole
      timeline.
  - **Where the processing runs (DECIDED 2026-10-13):** "right now this
    would need to be handled locally on the students machine. Processing
    the cache and sending it to the H drive, but down the track in the
    next 2 years we will be getting a render farm and that will be able to
    handle the caching etc publish process so keep that in mind as we
    design these tools."
    - Now: caches and exports are made on the student's machine and copied
      to the H drive.
    - Within about 2 years: a render farm takes over caching and the
      heavier publish steps.
    - Design rule (SUGGESTION, for review): build every export or cache
      step so it doesn't care where it runs. Each step:
      - works from the locked `.ma` already on the H drive, never from the
        student's open scene;
      - runs headless (mayapy), with no UI;
      - is described by a small job file (what to make, from which file,
        where it goes).
      Today the student's machine runs those jobs; later the farm runs the
      same jobs unchanged. It also means approval-triggered exports can be
      made any time after the publish, from the file on the H drive.
  - **Final publish movie for the edit (DECIDED 2026-10-13):** "The movie
    produced also gets saved with audio in the
    `D:\NWF_SHF\premiere\shotgridMovs` for updates in the edit." A final
    publish saves its movie, *with audio*, into the film's
    `premiere\shotgridMovs\` folder, so the edit picks up the update.
    - **Scratch only, replaced each time (DECIDED 2026-10-13):** "the movs
      do not need to be saved to the H drive as they will be on shotgrid.
      So maybe it's best to just write over existing ones?"
      - The movie goes only to the scratch drive's
        `premiere\shotgridMovs\`, never the H drive. ShotGrid keeps every
        version, so this is a working copy for the edit and is replaced on
        each final publish. That's allowed, because only the H drive is
        add-only.
      - Anyone else needing the movie gets it from ShotGrid.
      - SUGGESTION: name it exactly after the shot (`EAP_010_010.mp4`), so
        the replacement keeps the same name for Premiere. Shot-code names
        also sort into shot order for Automate to Sequence
        (`pipeDev/premiereBridge_research.md` §4).
    - **Premiere can read it (fact, 2026-10-13):** solved in shotSub. The
      user: "We had the movie not loading in premiere issue before, it is
      solved in the shotsub tool."
      - The live encoder `shelfDev/mpAnim/tools/shotgridConnect.py`
        `_encode_to_mp4` always passes `-codec libx264`, because rvio's
        default mp4 was Motion-JPEG/`mp4v`, which Premiere and Resolve on
        Windows can't import.
      - Audio comes from the Maya time slider's sound node, with its offset
        (`shotSub.get_scene_audio_for_encode`), muxed by rvio as
        `[ seq.#.jpg audio.wav -ao <secs> ]`. Audio stays rvio's default
        PCM, because `-audiocodec aac` fails in rvio.
    - **Sound in every publish movie (DECIDED and built 2026-10-13):** "We
      need sound to be working for the students dealing with lipsync." Not
      just the final publish: every ShotGrid movie from Publish (asset and
      camera) now carries the scene's sound, so lip sync can be reviewed in
      ShotGrid. ("Every publish" is Claude's reading of the request, for
      the user to confirm.)
      - `publishTool_api.scene_audio(start_frame)` uses the time slider's
        sound, with the same offset maths as shotSub. Headless (later, the
        farm), it uses the scene's only sound node.
      - `upload_with_audio(...)` passes the sound to `upload_playblast`.
        If the installed `shotgridConnect` is older than shotSub's audio
        support, it publishes without sound and warns ("Reinstall mpToolSet
        to fix") rather than failing.
      - Found 2026-10-13: the dev machine's *installed*
        `Documents\maya\scripts\shotgridConnect.py` is that older version.
        The repo copies (`shelfDev`, `mpToolSet`, `studio4AnimToolset`) have
        audio. Rerun the installer to get sound on this machine.
      - Test: `pipeDev/publishDev/test_publishAudio_mayapy.py` passes 12/12.
        A real rvio encode gives an H.264 (`avc1`) mp4 with a sound track.
    - Audio source: the sound on the shot's Maya timeline, as shotSub does.
    - OPEN: shots only, or assets too (e.g. a turntable)?
    - OPEN: does `davinciResolve\shotgridMovs` get a copy too?
    - Test in Premiere before relying on it: does replacing a same-named
      file show up in an open or reopened project, and does an open
      project lock the file so it can't be replaced?
  - **Iterative publish (raised 2026-10-13).** The user: "I think this
    just backs up the existing file, sends the required files to the
    appropriate folders on the h drive, produces a mov sends it to
    shotgrid and drops one in the aforementioned edit folder." So an
    iterative publish:
    1. backs up the student's existing file;
    2. sends the required files to the right folders on the H drive;
    3. makes a movie and sends it to ShotGrid (built, with sound);
    4. drops a copy of the movie in the edit folder
       (`premiere\shotgridMovs\` on scratch).

    The final publish is then this plus the chosen extra formats (the
    checkboxes).
    - **Step 1 is the publish itself (clarified 2026-10-13):** "I just mean
      the published file goes to the h drive so it's safe and can't be
      written over." There's no separate backup step. The locked versioned
      file on the H drive *is* the backup, which is what Publish already
      does.
    - **Step 2, "required files", depends on what each kind of publish
      contains (clarified 2026-10-13):** "required files refer to work we
      have not done yet defining what happens when we publish a shot for
      example. Keyframes would be part of that publish - even non official
      assets (things that just get made for the needs of that shot) might
      need to be published."
      - OPEN (next big design topic): the **shot publish**, meaning
        everything a shot publish hands on. That includes keyframes and
        **shot-only assets**: things made just for that shot, never
        published as assets in their own right. Linked to §3i "Animation
        publish" (hand on everything, plus a record of asset versions) and
        "Animated props in a shot".
      - The user (2026-10-13), on what the animation publish feeds: USD as
        well as lighting, FX, the edit and Unreal. The animation publish
        must produce USD. How depends on the user's own USD research.
      - Order agreed 2026-10-13: the animation publish is discussed before
        rigs, sets and textures. Rig requirements (e.g. what geometry gets
        cached) are noted as they come up.
      - **What an animation publish puts out (DECIDED 2026-10-13, the
        user's words):**
        1. "A cache of the animated object or rig."
        2. "The keyframes associated with the object or rig as a separate
           file that can be reapplied."
        3. "The animator may also publish a camera if they have made
           changes to the camera."
        4. "They might publish an effect or a cache or a rig they have
           created specifically for that shot", i.e. shot-only items.

        **Shot (animation) publish = iterative publish + these outputs
        (DECIDED 2026-10-13).** Details, all DECIDED 2026-10-13:
        - **Caches:** one cache file per character or prop.
          - **Rig requirement:** "The rigs will contain a geo set or group
            that will be created as part of the rigging process and will
            define what will be cached by the publish."
          - **Name (DECIDED 2026-10-13):** `cache_SET`. Every rig publish
            contains a `cache_SET` naming the geometry to cache, and
            Publish finds it inside each referenced rig (e.g.
            `scout:cache_SET`).
          - **Required (DECIDED 2026-10-13):** "It can't be published
            without the cache_SET. The rigger must create one manually as
            part of the rig publish." A Rigging publish is refused if the
            published content has no `cache_SET`. The tool never makes one
            automatically. No rigs have been published yet, so every
            pipeline rig will have one. OPEN (minor): a shot containing a
            rig from outside the pipeline (no `cache_SET`) needs a clear
            message at shot publish.
          - **Built 2026-10-13:**
            - `publishTool_api.check_cache_set(objects)` refuses, with
              how-to-fix messages, when:
              - there's no `cache_SET`, or more than one (referenced sets
                don't count);
              - it's empty, or has no geometry (mesh, nurbsSurface or
                subdiv, directly or under a group it lists);
              - for a selected-objects publish, it holds things outside
                what's being published.
            - `publish()` runs the check for Rigging (`RIG_CODE = "rig"`)
              before ShotGrid, the playblast or any H-drive write.
            - The Publish UI also checks when a Rigging row is added.
            - A selected-objects export adds the set itself (`noExpand`),
              so the published rig file contains `cache_SET` (namespace
              taken off).
            - Test: `pipeDev/publishDev/test_rigCacheSet_mayapy.py` passes
              15/15.
        - **Keys:** stored the camera way (keys file plus a map), and
          "re-applied by matching the control names". The publish records
          the rig version the keys were made on.
          - OPEN (later): animation layers. "I do want to talk later about
            animation layers and how we can integrate them, but for now
            your approach is fine."
        - **Camera:**
          - "The animator would manually unlock the camera and edit it or
            create a new one and publish that."
          - Publish only offers the camera when it has changed from the
            version that was built. The user's worry: "Will this be hard to
            track?"
          - SUGGESTION, how to track it: at build, stamp `camera1` with a
            fingerprint of its keys and settings, next to
            `pipeCameraVersion`. At publish, recompute it. If it's
            different, or the camera has no stamp (a new camera), offer it;
            if it's the same, skip it.
        - **Pipeline items vs things made in the shot (DECIDED
          2026-10-13):** "the exception for an animation/shot publish would
          be something created in the shot by the animator. So the tool
          knows the difference between a rig published via the pipe and a
          sphere with some keyframes."
          - The `cache_SET` rule applies only to rigs that came through the
            pipeline.
          - Things the animator made in the shot (e.g. a keyed sphere) need
            no `cache_SET` and are cached from their own geometry.
          - How the tool tells them apart (SUGGESTION):
            - a **pipeline item** is a reference Build Shot made: a file in
              `publish\`, listed in the shot's build manifest with its
              asset, department and version;
            - the **shot camera** is `camera1`, stamped by Build;
            - **made in the shot** is anything in the scene that didn't come
              from a reference (default cameras and `camera1_old*` aside);
            - a reference the animator added by hand, from outside the
              pipeline, is neither, so Publish warns and names it.
          - OPEN → DECIDED 2026-10-15, see "Shot (animation) publish v0"
            below.
        - **Lights in shot publishes (built 2026-10-20).** The user: "we
          need to be able to publish lights as part of the animation
          publish process if necessary - this won't be a usual thing but
          will happen sometimes when it's important for shot composition."
          A light (or group of lights, Maya's or Arnold's) made in the shot
          is a "light" item: written as `<shot>_<login>_<item>_<code>_v###
          _light.ma` (light, settings, keys) beside its keys, never cached
          (Alembic can't carry a light), even on Final. A group mixing
          lights and geometry stays "made in the shot" (cached; its lights
          only in the full file). Lights inside a referenced asset come
          with that asset. Build doesn't bring lights back yet (later,
          with Lighting). `publishTool_anim.is_light_item`; test
          `test_animLights_mayapy`.
        - **Publish movie burn-ins (built 2026-10-20).** The user:
          "published shotsubs are missing burn ins". The publish's own
          playblast had none; now shotSub's layout: fps top left, the
          published name top middle, frame top right, focal length bottom
          left (through a camera), "Name (login)" bottom right.
          `publishTool_api.burn_in`; skipped with a warning without a Qt
          app (headless). Test `test_burnIn_mayapy`.
        - **Shot (animation) publish v0 (DECIDED 2026-10-15).** The user
          confirmed the proposed defaults from 2026-10-13 and answered the
          remaining questions.
          - **Built 2026-10-19** (`publishTool_anim.py`, Publish window's
            **Animation** department in shot scenes; shotSub **Task** menu).
            The user OK'd the defaults: shotSub has a Task dropdown (from the
            linked shot's ShotGrid tasks, remembers the last one per shot in
            `shotgrid_link.json`) and sets `Version.sg_task`; keys files use
            the camera's `.ma` + `.json` map format, but hold the animator's
            own curves (not baked). Approval gate via
            `publishTool_api.approved_tasks()`; the camera publish now needs
            an approved Layout and links its Version to the Layout task.
            Playblast through `camera1`; movie copied to scratch
            `premiere\shotgridMovs\<SHOT>.mp4`. All-or-nothing H-drive write.
            `test_animPublish_mayapy.py` 25/25 (ShotGrid faked; real
            ShotGrid read checked separately).
            - **Shot publish UI (user, 2026-10-19):** no dropdown for *what*
              is published: the student selects everything and adds it in
              one click, and the tool sorts each thing by its id/type
              (built: Add Selected). But a dropdown **is** needed for which
              **stage** the publish is: **Layout** or **Animation**, with
              **Lighting** and **FX** to come later (shown as coming soon
              for now).
              - **Layout publish (DECIDED 2026-10-19):** "publishes the
                same thing as animation, just has no cache requirements":
                keys + the full file (and the camera), approved on the
                Layout task, never caches. Own version series
                (`<SHOT>_<login>_layout_v###`).
              - **Iterative vs for approval (user, 2026-10-19, later the
                same day): CHANGES "no pipe publish before approval".**
                "We need to not block iterative publishes like this ... the
                artist needs to define if the publish is iterative or for
                review. A simple check system box should do it with
                'iterative' and 'for approval'. Otherwise it's too hard to
                populate the pipe with assets. This new rule would not apply
                to a final publish where the cache is triggered." So: an
                iterative publish isn't blocked by approval; caches still
                need an approved Final.
                - **Settled the same day: no checkboxes.** "The lecturer
                  can mark a publish approved so the student can republish
                  and trigger the cache. This communication can just be
                  handled in the publish notes by the students. Please
                  approve for lighting etc." And: "every publish always
                  makes a shotgrid submission."
                - So: no shot publish (Layout, Animation, camera) is
                  blocked by approval. Every one makes a ShotGrid Version
                  for review: Layout publishes on the Layout task,
                  Animation publishes (and cameras from Animation) on the
                  Final task. Once a Version on the Final task is Approved,
                  the next Animation publish makes the caches. Approved
                  Blocking still doesn't cache; Layout never caches.
                - Built 2026-10-19 (`publish_stage()` replaces the gate);
                  `test_animPublish_mayapy.py` 32/32.
              - **Camera from Animation (DECIDED 2026-10-19):** allowed,
                but "we should know it came from animation": every camera
                publish is stamped like the model group, with
                `pipe_publishedFrom` (`layout` / `anim`) plus shot id, shot,
                department, version, artist, date and source scene, locked.
                ~~The stamp is on the camera node itself, not a group, because
                Build makes it the live `camera1` at the top of the scene;~~
                (superseded 2026-10-20: the stamp is on the camera group, see
                "Camera group" below) the keys map also records `published_from`.
              - **Camera group: edit frame range (built 2026-10-20).** The
                user: "the publish group we just created ... should also
                hold frame range data for the shot from the latest edl on
                shotgrid." An EDL on ShotGrid is a Cut with CutItems; the
                newest Cut (by date) holding the shot gives `cutIn`,
                `cutOut`, `cutDuration`, `editIn`, `editOut`, `cutOrder`,
                head/tail from the Shot (`sg_head_in`, `sg_tail_out`), plus
                `pipe_editSource` (cut/shot/none), `pipe_editCut`,
                `pipe_editCutId`, `pipe_editCutDate`. No Cut: the Shot's
                `sg_cut_*` fields (source "shot"). Nothing: source "none"
                and a warning, never a refusal. The baked range is stamped
                too (`pipe_frameStart`/`pipe_frameEnd`). A warning when the
                timeline's length differs from `cutDuration` (lengths only:
                EDL frames count from 0, Maya shots may start at 1001; how
                they map is OPEN). On 2026-10-20 ShotGrid had three SEQ010
                Cuts; EAP_010_010 is in none (EAP_010_140 is).
                `publishTool_camera.shot_edit_range`; test
                `test_cameraEditRange_mayapy`.
              - **Camera group (DECIDED + built 2026-10-20).** The user:
                (1) cameras parented under a publish group with the details
                the model publish has; (2) the camera's keyframes and any
                driven attribute stored separately on a node under that
                group; (3) the camera's attributes driven 1:1 by direct
                connections from that node, "this way the camera can behave
                like a referenced camera in the animators scenes but there
                are no reference paths for the pipe to manage"; (4) the
                publish records image sequences the camera uses (location,
                name etc.). Answers to Claude's questions: keep the keys in
                their own file (camera file + keys file + map, as before);
                image planes recorded only, not published or rebuilt (OPEN
                for later); old three-file publishes are dropped, republish
                them; names as below.
                ```
                EAP_010_010_cam_GRP     <shot>_cam_GRP, named from the shot (never fixed)
                  camera1               every animated attribute driven 1:1 by...
                  camera1_DATA          ...an attribute here (cam_translateX, camShape_focalLength, ...)
                ```
                - Published file: `<shot>_cam_GRP > shotCam + shotCam_DATA`,
                  data node already wired to the camera, no keys; group,
                  camera and data transforms locked. Group stamp:
                  `pipe_sgShotId`, `pipe_shot`, `pipe_department` (`cam`),
                  `pipe_version`, `pipe_publishedFrom`, `pipe_artistId`,
                  `pipe_artistName`, `pipe_published`, `pipe_sourceScene`,
                  `pipe_imagePlanes` (JSON: node, full path, folder, file
                  name, type, useFrameExtension, frameOffset, frameIn/Out,
                  frameCache, depth, fit, displayMode). Static settings
                  (film back etc.) stay on the camera shape.
                - Keys file: one baked curve per data attribute. Map
                  `format: 2`: `group`, `data`, `curves` (curve -> data
                  attribute), `attrs` (data attribute -> camera attribute),
                  `image_planes`. Data attributes use the camera
                  attribute's own type, so no unit-conversion nodes.
                - Build imports it live: the group keeps its name, the
                  camera becomes `camera1` (still the only `camera1`, so
                  playblast/shotSub by name still work), the data node
                  `camera1_DATA`, keys connected to the data node, then
                  everything locked (channels, curve key data, curve nodes,
                  group). The built version is read from the group's stamp
                  (replaces the old `pipeShot`/`pipeCameraVersion`/
                  `pipeCameraBy` stamps on camera1). An existing camera1
                  (older build, pre-group camera, or the student's own) is
                  kept as `camera1_old`, `camera1_old1`, ... with its data
                  node and group (`..._cam_GRP_old`); names are kept unique.
                - Publishing again from a built shot works (the scene's
                  group steps aside during export). In the Publish window,
                  selecting the group or `camera1_DATA` gives a Camera row;
                  an Animation publish refuses them.
                - Tests: `pipeDev/buildDev/test_cameraGroup_mayapy.py` 37/37
                  (two shots, so two group names); all other Build/Publish
                  tests still pass.
                - To do by hand: republish the EAP_010_010 camera from the
                  layout scene (v001/v002 on `G:\H` are the old format and
                  no longer listed), rebuild, check in Maya.
              - **Build in a blank scene = latest (DECIDED + built
                2026-10-19):** "if the student is building in a blank scene
                the build tool should always load the latest published
                assets." Blank = nothing referenced yet. In a scene that
                already has the shot's assets, rows still start at the
                version the shot has. `test_blankSceneLatest_mayapy.py` 2/2.
                (Same day the user had a successful build of a shot from a
                published animation.)
              - **Adding an asset builds only the new one (DECIDED + built
                2026-10-20).** Bug found by the user: adding scoutsHouse to
                the test shot also rebuilt the camera (existing camera1
                renamed camera1_old) and possibly touched the backpack.
                Cause: Build Shot ran every row and compared rows with the
                shot's manifest, not the open scene (here the manifest's
                camera had moved to v002 from another scene of the shot).
                The user: "If there are existing assets in the scene and new
                asset is added the tool needs to know to only add the new
                asset and not rebuild everything." Now each row records
                what the open scene has (`api.scene_version()`), starts at
                that version, and is skipped ("already in the scene, left
                as is") unless the student picks another version. A rig
                whose file in the shot is missing/out of date is still
                built (that's the fix). The table shows "Not in this scene:
                Build adds it" for shot assets the scene lacks.
                `test_addAssetOnly_mayapy.py` 9/9 (real tab, offscreen).
              - Built 2026-10-19: the **Publish for** dropdown (Layout,
                Animation; Lighting/FX coming soon) and Add Selected in shot
                scenes. `test_shotAddSelected_mayapy.py` 11/11 (real window,
                offscreen), `test_animPublish_mayapy.py` 33/33.
            - Known v0 limits: constraints, expressions and driven keys
              aren't in the keys file; Alembic names have no login
              (`<SHOT>_<item>_anim_v###.abc`, as decided), so two people's
              same-numbered finals would clash (the second is refused, not
              overwritten). ShotGrid Version codes used to repeat between
              people too: **FIXED 2026-10-28.** After the move to e-numbers
              restarted version numbers, e131988's shed env v001/v002 and
              SEQ010_140 anim v001 were uploaded into scout's existing
              Versions of the same name, replacing their movies. Versions
              are now named with the login, like the file on H
              (`Shed_e131988_env_v002`, `SEQ010_140_e131988_anim_v001`):
              the playblast folder is `<login>_<code>_v###`. The three
              older Versions were left holding the new movies.
            - **Maya 2027 (2026-10-28):** the whole pipe suite passes under
              2027's mayapy (Python 3.13, PySide6 6.8) except Studio
              Library, whose bundled `six` 1.12 fails on Python 3.12+. The
              pipe's settings now carry into a new version's prefs (copied
              from the newest other `maya\<ver>\prefs` the first time), and
              Build warns when a publish was saved in a newer Maya than the
              one running (read from the `.ma`'s `requires maya` line).
          1. **One version number per publish:** everything from one
             animation publish shares a `v###` ("anim v003 of
             EAP_010_010").
             **One movie per publish (DECIDED + BUILT 2026-10-28).** A
             camera and a character ticked together made two movies. The
             user: "We don't need a mov per asset in a publish. We should be
             able to publish many assets in a animation or layout from one
             maya file and only have one mov." The camera row now goes out
             inside the Layout/Animation publish of the same stage: one
             playblast through that camera, one review, one ShotGrid
             Version (its notes list the camera version). The camera keeps
             its own files and version series on H, so Build is unchanged;
             a failure removes the camera files with the rest. A camera
             ticked with no animation items still publishes on its own.
          2. *(Superseded 2026-10-19 by 6a: the list starts empty,
             select and add.)* **The animator chooses, everything ticked:** Publish scans
             the scene and lists every pipeline rig, made-in-shot item and
             changed camera, all ticked. The animator can untick items
             (e.g. a prop that didn't move).
          3. **Pipeline rigs** (references from `publish\` with a
             `cache_SET`): one Alembic per rig of its `cache_SET`, over the
             whole timeline, plus a keys file and map (the camera way) that
             record the rig version, so keys can be reapplied by control
             name.
          4. **Made in the shot:**
             - animated ones: their own Alembic over the whole timeline;
             - static ones: a **single-frame cache**, like a set (matches
               the Alembic rule: keyframed assets get the full range, static
               ones one frame);
             - named from the object's name in the scene:
               `<SHOT>_<object>_anim_v###.abc`, e.g.
               `EAP_010_010_bouncingBall_anim_v003.abc`. Renaming the
               object changes the file name.
          5. **Where files go on the H drive:** caches in the shot's
             `cache\alembic\`; keys files and maps in `scenes\`, next to
             the camera publishes.
          6. **ShotGrid and the edit:** a Version on the Shot with the movie
             (with sound), plus a copy in scratch
             `premiere\shotgridMovs\EAP_010_010.mp4`, replaced on each
             publish.
          6a. **Publish works out what each item is (DECIDED
             2026-10-19):** the animator only selects objects and adds
             them; there is no asset type or department to pick. Publish
             recognises "this is a camera", "this is a model with
             keyframes", "this is a rig" (and made-in-shot items) by itself.
             Came from testing on the T7: a keyframed reference of
             `backpack_scout_model_v003` couldn't be added because the shot
             scene only offered Camera.
             - **Made in the shot = not a published asset (DECIDED
               2026-10-19).** The test is "does this exist as a published
               asset?", not "is it none of the other kinds". Being animated
               is a separate question that applies to every kind: a
               made-in-shot item can have keys (item 4 already has animated
               and static made-in-shot items).
             - **A published asset has a ShotGrid id (DECIDED
               2026-10-19).** That is the cleanest definition: published =
               it carries a ShotGrid Asset id; no id = made in the shot.
               Today every asset publish already looks up its ShotGrid Asset
               (`find_shotgrid_asset`) but doesn't write the id into the
               published file.
             - **Stamping: DECIDED 2026-10-19, "we need it".** How it's
               stored was already decided in principle on 2026-10-12 (§3,
               "ShotGrid asset ID"): a `publishInfo` network node made at
               publish time, tested to survive selected and whole-scene
               exports and to read back through a reference, so **no
               top-group rule**. (On 2026-10-19 Claude wrongly proposed
               top-group attributes instead; that suggestion is withdrawn.)
             - **Model publish clean-up + pipe group (user proposal,
               2026-10-19, details OPEN):** when publishing a model (e.g.
               the backpack) the tool should **freeze transforms and delete
               history**, and "perhaps the pipe parents the model into a
               group with the appropriate name", the group storing the
               **ShotGrid id** and anything else needed, e.g. **date created
               and the artist** who created it.
               - **Never on a rig (user, 2026-10-20):** "There should be no
                 freeze transform clean up for the publish of the rig ...
                 and no delete history." The rig export never did either; a
                 rig went through Model because the Department picker
                 defaulted to Modeling. Fixed: Model rows/publishes refuse
                 joints, skinClusters, blendShapes, IK handles and
                 constraints (`publishTool_api.check_not_a_rig`), and the
                 picker starts on the department in the scene's file name
                 (`scout_rig_v002` -> Rigging). Test: `test_modelNotRig_mayapy`.
               - Changes the 2026-10-12 choice of a separate `publishInfo`
                 node with no top group: that "no top-group rule" was about
                 not making *students* build a group; here the **pipe**
                 makes it, so students still don't have to.
               - **DECIDED 2026-10-19** (user answered each):
                 1. The pipe group **replaces the `publishInfo` node**.
                 2. Clean-up happens in the **published file only**; the
                    working scene is untouched.
                 3. Freeze transforms + delete history: **models only**
                    (rigs keep history/deformers).
                 4. Group name **`<asset>_<department>_GRP`**, e.g.
                    `backpack_model_GRP`.
                 5. The group stores: ShotGrid Asset id, asset name and
                    type, department, version, the artist's RMIT ID and
                    name, the **date the publish was created**, and the
                    scene it was published from.
                 - The user is aware freezing zeroes translate/rotate in
                   the published file; ~~animators key the pipe group~~
                   (superseded 2026-10-20, below).
                 - **Pipe group look and lock (DECIDED + built
                   2026-10-20).** The user: the group should "display in
                   the outliner as the RMIT logo, so that we know it's
                   come from the pipe", and be "locked at world 000 with
                   all chanels hidden incase students accidentally move
                   it. This will be for all published assets." And: "All
                   the pipe needs to do is make the publish group and
                   parent the model/rig/camera under it. That's all. The
                   backpack model can be moved around without that group
                   via it's own transforms or connected to a locator in
                   the scene via a parent constraint." (Claude first
                   misread this as adding a place control; not built.)
                   - **Icon: pipe groups are now `dagContainer`s
                     (2026-10-20).** Tested in Maya by the user: the
                     Outliner ignores `iconName` on a plain group (even
                     Maya's own `sphere.png`) but shows it on a
                     `dagContainer` ("I can see the rmit logo in the
                     outliner!"). A container is Maya's own node (no
                     plug-in, unlike a custom MPxNode/MPxTransform type,
                     which the user asked about: rejected because every
                     published file would need the plug-in). It inherits
                     transform, so moving, parenting, referencing, keying
                     children, Alembic and every pipe check work unchanged
                     (mayapy tests). Children parented under it become
                     members and stop being when parented out;
                     `delete_pipe_group` clears members before deleting
                     so the rig publish never deletes the working rig.
                     Clicking a child selects the child while Maya's
                     container-centric selection pref is off (the
                     default). Adds one `hyperLayout` node per file.
                     `publishTool_api.make_pipe_group`. Older group-style
                     publishes keep working.
                   - `publishTool_api.finish_pipe_group()`: `iconName` =
                     `iconPipeOutliner.png` (file name only, found in the
                     prefs icons folder; missing icon = normal group
                     icon); translate/rotate/scale/visibility set to
                     0/0/1/on, locked, not keyable, hidden from the
                     Channel Box. Only the group; everything inside stays
                     free. Used by model publishes and the camera group;
                     rig publishes use it when the rig group is built.
                   - Icon: `shelfDev/mpPipe/icons/iconPipeOutliner.png`,
                     20x20, red RMIT mark on a navy circle (transparent
                     outside), drawn as a vector so it can be re-rendered.
                     Colours picked by eye (`#000054`, `#e61e2a`); swap
                     for official RMIT values if wanted. Copied to prefs
                     icons by the mpPipe installer (rebuild the zip).
                   - Fact found by test: in a shot scene, a student CAN
                     unlock the channels of a referenced pipe group, so
                     the lock stops accidents, not determined students.
                   - Tests: `test_modelGroup_mayapy.py` 26/26 (icon, lock,
                     hidden channels, model inside free, through a
                     reference, model moved by its own transform and by a
                     parent constraint to a locator);
                     `test_cameraGroup_mayapy.py` 38/38. The animation
                     publish tests now key the model, not the group.
                 - **Built 2026-10-19 for models**
                   (`publishTool_api.export_model_to_h_drive`): works on
                   duplicates, so the working scene ends exactly as it was;
                   attributes `pipe_sgAssetId`, `pipe_asset`,
                   `pipe_assetType`, `pipe_department`, `pipe_version`,
                   `pipe_artistId`, `pipe_artistName` (from ShotGrid),
                   `pipe_published`, `pipe_sourceScene`, all locked.
                   Whole-scene model publishes are now exported too (no
                   more plain file copy). Republishing from a file that
                   already has the group replaces it rather than nesting.
                   `test_modelGroup_mayapy.py` 13/13. Not built yet: the
                   group for rigs and other departments (a rig can't be
                   duplicated, so it needs a different approach).
             - **Rig publish, thought through from scratch (started
               2026-10-19).** The user: rigs are "a lot more complicated
               than the model, so let's think this through from scratch."
               Facts so far (user):
               - Rigs will in most cases be built on **clean published
                 models**.
               - **ngSkinTools is used at RMIT**, so the pipe must not rip
                 the plug-in out of students' scenes; but it's better to
                 publish **without the ngSkinTools node**. If it's present,
                 students could be **prompted to remove it before
                 publishing**.
                 - **DECIDED 2026-10-19:** if an ngSkinTools node is in the
                   rig, **Publish stops** and prompts the student to remove
                   it (Publish doesn't remove it for them).
               - Students rig with **mGear, Advanced Skeleton, Rapid Rig,
                 the user's own rigging tools, and possibly their own
                 setups**.
               - **mGear is installed only in the PC labs** (user). So an
                 mGear rig (it relies on mGear's own plug-in nodes) can only
                 be opened, and shots using it only animated, where mGear is
                 installed. The user: "for our purposes that is
                 everywhere" (the PC labs are where the work happens), but
                 then agreed the visibility ideas "all sound like good
                 ideas" (2026-10-19): **Publish records the plug-ins a rig
                 needs in its stamp; Build warns before pulling a rig onto
                 a machine that doesn't have them** ("This rig needs mGear,
                 which isn't installed here..."), so students find out at
                 Build, not when the shot opens with broken nodes.
               - **The model gets into the rig scene by import (user).**
                 "So building assets for the rigging shouldn't include
                 references": a rig scene (and its publish) holds no
                 references. OPEN: if a rig scene does have references at
                 publish time, refuse, or bring them into the published
                 file?
               - **mGear depends on its plug-in nodes (user)**: they must
                 never be stripped. SUGGESTION (not agreed): rig publishes
                 never delete anything; if a rig holds *unknown* plug-in
                 nodes (e.g. mGear's when mGear isn't loaded on that
                 machine) Publish stops and says which plug-in to load,
                 instead of the model publish's "leave unknown nodes out".
               - **What real rigs contain (scanned as data, never opened,
                 2026-10-19):** 8 of the user's/students' rigs (scoutPrevis,
                 ATKS, argus, dragonBird, KAT, Phyllis MH, wobbert, ATKS
                 volume block). All require `mgear_solvers`; 4 hold
                 ngSkinTools data; most require `mtoa`, `lookdevKit`,
                 `stereoCamera`; MetaHuman-based ones `embeddedRL4`. No
                 non-standard script nodes in the .ma files (the .mb ones
                 show 2 script-node chunks each, consistent with Maya's
                 standard two; .mb is read less reliably). No virus markers.
                 One (Phyllis) references a file on another drive
                 (`D:/ASSESSMENT/.../Hair_rig.mb`): the reference problem in
                 practice. Rig files are big: up to 276 MB (.ma).
               - **MetaHuman rigs (user, 2026-10-19):** "the tool needs to
                 recognise and track if there is a MetaHuman involved. It
                 will need to handle locating the DNA files, storing the
                 correct DNA file name and path for the publish in the top
                 node of the rig where we store the info, and save the DNA
                 files in an appropriate place in our assets folder, making
                 sure the paths hold up when the publish is built and
                 referenced for animating."
                 - Found in real rigs: each `embeddedNodeRL4` holds an
                   absolute `dnaFilePath` to wherever the rigger kept it;
                   3 of 5 checked don't exist on this machine (Phyllis,
                   KAT), and KAT's head node points at MAYHEM's body.dna.
                   `rigDev/mh_rig_assemble/mh_dna_repair.py` exists to fix
                   broken paths. Head DNA ~55 MB.
                 - SUGGESTION (not agreed): detect `embeddedNodeRL4`; stop
                   if a DNA file is missing (point to MH DNA Repair); copy
                   DNA to the H drive with the rig version; record node ->
                   DNA in the stamp; published path portable; Build pulls
                   DNA into the shared `publish\` folder with the rig
                   version (§3e, like textures), never into shots.
                 - OPEN (PINNED 2026-10-19, resume next session): where in
                   the asset folder (next to the rig in `scenes\<login>\`
                   vs a `data\dna\` folder; decide with the textures folder
                   question); per rig version vs per asset; missing DNA ->
                   stop?; head/body mismatch -> warn or stop?; technical
                   test: does `dnaFilePath` accept `$PIPE_SCRATCH`, or must
                   Build rewrite it?
                 - **Tested 2026-10-20: `dnaFilePath` does NOT accept
                   `$PIPE_SCRATCH`.** mayapy, `embeddedRL4` loaded, a new
                   `embeddedNodeRL4` with Scout's real `body.dna`: real
                   path -> "Initializing RigLogic - Done."; the same file
                   as `$PIPE_SCRATCH/...` -> "Failed to initialize rig
                   logic! Check DNA path or LOD value" (same as a broken
                   path). The node re-initialises every time the path is
                   set. Scout's DNA files exist on this machine (head 57
                   MB, body 4.5 MB). The user asked whether rig publish can
                   collect DNA from off-pipe locations like textures.
                 - SUGGESTION (not agreed): rig publish collects DNA like
                   textures (any location, stop if missing, copy to the
                   version's folder on H); the published file keeps the
                   portable `$PIPE_SCRATCH/...` path in a pipe attribute on
                   each DNA node (`pipe_dnaPath`), and the real path is
                   filled into `dnaFilePath` by Build and by an mpPipe
                   after-open hook (beside pipeEnv's before-open one), so
                   it follows the drive; Build/Repair pull DNA with the
                   rig. Suggested home: the same per-version folder as the
                   textures (`...\<published name>\dna\`); head/body
                   mismatch listed in the publish summary (warn only).
                 - **Rig publish group + DNA (DECIDED + built 2026-10-20).**
                   The user: "the names and paths of these files should
                   probably be stored on the publish node for the rigs";
                   on the rig now sitting one level down in shots
                   (`scout:scout_rig_GRP|...`): "that will all work fine.
                   As long as it's handled properly by the rigger."
                   - `publishTool_api.export_rig_to_h_drive()` (every rig
                     publish is now exported, never file-copied): for the
                     export only, the rig's top nodes are parented
                     (relative, values unchanged) under `<asset>_rig_GRP`
                     (pipe icon, locked at the origin, channels hidden;
                     everything inside free), then put back; a node
                     already called that steps aside meanwhile. Working
                     scene ends as it was, also after a failed export.
                   - Group stamp = the model group's fields plus
                     `pipe_textures` (node, original path, published path,
                     files), `pipe_dna` (node, attr, file name, original
                     path, portable `$PIPE_SCRATCH` path), `pipe_plugins`
                     (loaded plug-ins whose node types the scene uses, with
                     versions), `pipe_rigRulesVersion`,
                     `pipe_metahumanFaceControls`, `pipe_faceControlsAdded`.
                     JSON text, locked. Shot publishes recognise the rig
                     by its `pipe_sgAssetId` like other pipe groups.
                   - DNA (`publishTool_textures.collect_dna()`): every
                     MetaHuman DNA node's file, from wherever it is (dump
                     folders included); missing -> publish refused, names
                     the node and points at MH DNA Repair. Copied into the
                     version's folder `...\<published name>\dna\`, one
                     full copy per version, read-only; DNA nodes are always
                     exported. In the published file `dnaFilePath` = the
                     publisher's real scratch path; the summary lists
                     "node -> file" for a head/body check (warning only).
                     These four details are Claude's suggested defaults,
                     built after the user's go-ahead; not explicitly
                     confirmed one by one.
                   - Following the drive: `pipeEnv.fix_dna_paths()` reads
                     each rig group's `pipe_dna` and sets each DNA node (in
                     the group's namespace) to the file on this drive; run
                     by Build after building an asset, by Repair, and by a
                     new mpPipe **after-open** callback registered beside
                     the before-open one (`pipeEnv.install()`; the
                     uninstaller removes both). Build/Repair pull DNA with
                     the textures.
                   - Test `pipeDev/publishDev/test_rigGroup_mayapy.py`
                     21/21 (DNA from a Downloads dump folder, missing DNA,
                     stamp contents, working scene restored, whole-scene
                     publish with a clashing group name, failed export,
                     Build pulls DNA and points the node at it, film moved
                     to another drive -> after-open hook follows); DNA node
                     stood in by a `network` node. All other Publish/Build
                     tests still pass.
                   - Not yet: Build warning when a rig's `pipe_plugins`
                     aren't on this machine (decided 2026-10-19); the "a
                     rig update lost controls" warning; trying a real
                     MetaHuman rig publish end to end (Scout needs its
                     sets first).
               - Rig publish OPEN (pinned): rigs never strip anything /
                 stop on unknown plug-in nodes (suggestion); references in a
                 rig at publish: refuse or bring in?; ngSkinTools removal
                 wording for the prompt; stamp location for rigs.
               - Already built for rigs: `cache_SET` required (§ "Rig
                 requirement"), namespaces stripped, unassigned shaders left
                 out, script-node check. ~~Not yet: the pipe stamp~~ (built
                 2026-10-20: rig group + stamp, see "Rig publish group +
                 DNA" below); still no rig clean-up. Claude's earlier suggestions (wrap in
                 `<asset>_rig_GRP` at export, don't freeze/delete
                 history/remove hidden on rigs, import references) are NOT
                 agreed; set aside to start from scratch.
               - **Rig sets: controls and render geo (2026-10-20).**
                 - **Render geo = `cache_SET` (DECIDED).** The user: "we
                   need a way of flagging geo that is meant to be rendered
                   vs geo that is there to help the rig. Sets seems like a
                   good way ... leave it up to the rigger to define." Then:
                   "the non renderable geo doesn't need to be cached. So
                   maybe we just need one set that is cacheable renderable
                   geo." So the existing `cache_SET` now means **renderable
                   geo, and only that is cached**. Rig helpers (e.g. a
                   wing's NURBS surfaces with joints riveted to them, which
                   drive a skinned polygon membrane; collision geo) stay
                   out of it and aren't cached. No code change; the rule
                   goes in the spec and the Publish message (message
                   updated 2026-10-20).
                 - **Control sets (DECIDED).** The user: riggers make
                   control sets; mGear and Advanced Skeleton already have
                   their own, "if the pipe could recognise these that
                   would be great"; ideally separate body and face sets;
                   riggers may add custom sets.
                   1. A rig publish **is refused without the pipe's
                      control sets**.
                   2. **The rigger makes the pipe sets** by hand (Publish
                      doesn't make them).
                   3. **MetaHuman face controls count as face controls
                      automatically.**
                 - Found in real rigs (set names read from the .ma text):
                   Scout (`scoutPrevis_rig_006`, mGear) has `rig1_sets_grp`
                   > `rig1_controllers_grp`, `rig1_deformers_grp`,
                   `rig1_componentsRoots_grp`, `rig1_geo_grp` (prefix =
                   the mGear rig's name), plus a hand-made
                   `FacialControls`. mGear has one controls set, no
                   body/face split. KAT, wobbert, ATKS have no control
                   sets. Advanced Skeleton not seen yet (believed
                   `ControlSet`, `FaceControlSet`; check on a real AS rig).
                 - **CHANGED 2026-10-20 (user): `RMIT_publishSet`.** "The
                   rigger builds the body control cache and face sets the
                   pipe needs and the publish tool creates the
                   RMIT_publishSet and adds the pipe dependant sets."
                   Built: the rigger makes `cache_SET`, `body_controls_SET`
                   and (MetaHuman: required) `face_controls_SET` at any
                   level; `controls_SET` is no longer required. Publish
                   makes `RMIT_publishSet` holding those three in the
                   published file only (an existing one in the scene has
                   its members swapped for the export and put back).
                   `publishTool_api._PublishSet`. The older notes below
                   about `controls_SET` are superseded.
                 - **Names (DECIDED):** `controls_SET` >
                   `body_controls_SET`, `face_controls_SET`, plus any
                   custom sets the rigger adds inside `controls_SET`
                   ("fine as long as it doesn't clash with mgear advanced
                   skeleton or rapid rig"). No clash: mGear's sets end in
                   `_grp`; the Advanced Skeleton rig on Winston
                   (`E:\maya\projects\winston_PILOT\...\winston_RIG_v020.ma`,
                   Maya 2018) has only `Sets` > `AllSet` (804 members: every
                   rig node, not just controls) plus hand-made `cheeks`,
                   `mouthAll`, `mouthTop`; no `ControlSet` (so Claude's
                   belief about AS was wrong for that version). Rapid Rig
                   names not found; scan a real one when available.
                 - Sets can hold sets, so "recognising" mGear/AS sets means
                   the rigger drops e.g. `rig1_controllers_grp` into
                   `body_controls_SET`; Publish follows nested sets.
                 - **Which are required (DECIDED, user: "whatever keeps
                   things simple and flexible"):** `controls_SET` and
                   `body_controls_SET` (inside it, with controls) always;
                   `face_controls_SET` required for a MetaHuman rig (it may
                   be empty), optional otherwise but not empty if present.
                 - **MetaHuman face (DECIDED):** Publish adds the MetaHuman
                   face controls to `face_controls_SET` in the published
                   file only (the working scene ends as it was); controls
                   the rigger already put there stay, only missing ones are
                   added (user chose "a"). The two `lipsPressD` controls
                   the rigger had left out count (user: "in").
                 - **Updates (DECIDED):** the user: "we may need to account
                   for metahuman and mgear updates". The names Publish
                   relies on live in `pipeDev/publishDev/rig_rules.py`
                   (data only, `VERSION`): MetaHuman DNA node type, face GUI
                   group `headGui_grp`, prefix `CTRL_`, and six non-control
                   `CTRL_` nodes (`CTRL_faceGUI`, `CTRL_faceTweakersGUI`,
                   `CTRL_faceAndEyesAimFollowHeadGUI`, `CTRL_GUIswitch`,
                   `CTRL_rigLogic`, `CTRL_expressions`), plus known sets
                   of other tools named in messages. If MetaHuman DNA is
                   found but the rule finds no face controls, Publish stops
                   and says to fill the set by hand or update the rules.
                   Shipped with the mPipe installer (`build_zip.SCRIPTS`).
                 - **Built 2026-10-20:** `publishTool_api.check_control_sets()`
                   (beside `check_cache_set`, run by `publish()` before
                   ShotGrid/playblast/H drive and when a Rigging row is
                   added); refusal messages list the other tools' sets
                   found in the scene and where they go. Selected-object
                   exports now carry every set (`plan["set_uuids"]`:
                   `cache_SET` + the control set tree). A whole-scene rig
                   with MetaHuman controls to add is exported, not copied.
                   Test `test_rigControlSets_mayapy.py` 24/24 (Scout-like
                   mGear + MetaHuman layout; DNA node type swapped for
                   `network`). Checked on the real
                   `D:\projects\nwf_PREVIS\scenes\rig\scoutPrevis_rig_002.ma`
                   (opened headless, not saved): rule finds 175 face
                   controls = the 173 in `FacialControls` + the two
                   `lipsPressD`; the refusal names `FacialControls` and
                   `rig1_controllers_grp` and where each goes.
                 - Noticed: both DNA nodes in that rig are called
                   `body_rl4Embedded` / `body_rl4Embedded1` though one
                   points at head.dna; and both DNA paths are absolute into
                   an old project folder (pinned DNA question above).
                 - Not yet: recording rules version / face-control count in
                   the rig's group stamp, and the "a rig update lost
                   controls" warning (both wait for the rig group).
             - **Groups of models (user, 2026-10-19):** "if a model
               contains more than one individual model the student can
               select a group and the publish tool will perform a full clean
               ... but also delete any hidden geo etc." Found on the real
               `scoutsHouse.mb` (previs): its publish failed because the
               scene held 180 unknown plug-in nodes (editor bookmarks,
               Redshift settings, old ngSkinTools data), which stop Maya
               writing a .ma; and unparenting by hand broke world space.
               - Built: the model publish (still on copies; working scene
                 unchanged) leaves out anything hidden (itself, under a
                 hidden group, or on a hidden display layer) and empty
                 groups, runs Mesh Cleanup (`polyClean`) per mesh, leaves
                 unknown plug-in nodes out of the export (put back with
                 undo), and strips `requires` lines for plug-ins that
                 aren't loaded from a published .ma (Maya can't undo
                 removing them from the scene, so only the file is
                 changed; .mb keeps them). Publish lists what it left out.
               - Checked on the real house: .ma written, 8 hidden objects
                 + `group1` + 180 unknown nodes left out, all 99 visible
                 meshes in exactly the same world space, frozen, publish
                 opens with no warnings. `test_modelGroup_mayapy.py` 21/21.
             - **Unassigned shaders (DECIDED 2026-10-19):** "this rule will
               need to apply to all publishes": no published file carries
               unassigned shaders. Models are cleaned before rigging gets
               them; rigging publishes may need their own custom clean-up
               (OPEN).
               - Built: `publishTool_api.unused_shading_nodes()`, narrow
                 so it's safe for rigs (empty shading groups, materials
                 used only by those, textures/utilities feeding only those;
                 never DAG nodes, anim curves or referenced nodes). Model
                 publishes already left them out (export of the pipe group).
                 Whole-scene publishes of other departments now export
                 without them (deleted for the export, put back with undo).
                 **Build** deletes unassigned shaders sitting in the asset's
                 namespace instead of stopping (the `shotSetup_001`
                 `backpack:lambert7` case) and says so; real nodes there
                 still stop it. `test_unusedShading_mayapy.py` 14/14.
             - **Blocking and Final tasks created 2026-10-19** on all 75
               NWF shots (Animation step; `EAP_010_FULL_CUT` left out). The
               ShotGrid side is tracked in `shotgridTemplate_requirements.md`.
             - **Keyframed model reference (DECIDED 2026-10-19):** its keys
               are published separately from the model, plus a full version
               of the file.
             - **The list starts empty (DECIDED 2026-10-19).** The animator
               selects and adds; this replaces item 2's "scan the scene,
               everything ticked".
             - **Caches only on a final publish (DECIDED 2026-10-19).**
               Ordinary shot publishes put out keys + the full file, no
               Alembic. This changes items 3 and 4: their Alembics happen
               only on a final publish. A shot may have **more than one
               final**.
               - **How the tool knows (DECIDED 2026-10-19):** the shot is
                 marked final in ShotGrid. If it is published again after
                 that, the most recent final publish is the true source.
                 Related: "final publish checkboxes" in item 7.
               - **"Final" = Approved in ShotGrid, for now (DECIDED
                 2026-10-19):** the Version status `apr` (Approved) in
                 project 157. Not the Shot or Task `fin` status. Newest
                 final publish wins (confirmed).
               - **Final doesn't stick (DECIDED + BUILT 2026-10-28):** the
                 user: "Every new version to shotgrid is marked unviewed - I
                 have to manually mark it approved, so once a final publish
                 has occurred it's not an ongoing set state for that shot or
                 asset", and "It will help us reduce the number of caches."
                 A publish is Final only when the **newest** Version on the
                 Final task is Approved. Each publish makes a new Version
                 (Pending Review), so the next publish is iterative unless
                 that one is approved too. shotSub Versions (no task) and
                 other tasks' Versions don't count. Before this, any
                 Approved Version made every later publish Final.
                 `publishTool_api.approved_tasks`; test
                 `publishDev/test_finalNotSticky_mayapy.py`. Applies to
                 assets too (department Tasks, see "Publish thumbnail
                 borders").
               - **Publish thumbnail borders (DECIDED + BUILT 2026-10-28):**
                 ShotGrid thumbnails of pipe publishes get a border:
                 **dark blue = iterative**, **bright green = Final**.
                 Plain shotSub Versions: no border (shotSub unchanged).
                 The middle frame, bordered, replaces the thumbnail on the
                 Version and its Shot/Asset after the movie is uploaded
                 (`upload_bordered_thumbnail`, in `upload_with_audio`, so
                 asset, camera and anim publishes all get it). The movie
                 has no border. A failure is a warning. The Shot's
                 thumbnail shows whatever was uploaded last, so a later
                 shotSub replaces the green (user: "go with your
                 recommendation for now").
                 - **What's Final, per publish:** the newest Version on
                   the task the publish goes on is Approved
                   (`newest_approved`). Animation: Final task (caches).
                   Layout and camera: Layout/Final task, never caches.
                 - **Assets have Final publishes too** (no caches, "but
                   may trigger other things"). DECIDED (option A, user:
                   "go with your recommendation"): every asset gets a Task
                   per department, `publishTool_api.ASSET_TASKS`: Model,
                   Rig, Creature (characters), LookDev, Environment
                   (environments). Each asset publish links its Version to
                   its department's Task; Final when that Task's newest
                   Version is Approved. No Task: iterative, unlinked, with
                   a warning. `desktopDev/asset_tasks.py` makes the
                   missing Tasks (dry run; `--apply`), only adds. Dry run
                   on project 157 (2026-10-28): 61 Tasks to make, none for
                   the 3 Graphic assets and Farm Equipment (no type).
                   NOT APPLIED yet.
                 - Test: `publishDev/test_thumbnailBorder_mayapy.py`.
               - **The cache rule (DECIDED 2026-10-19):** approved
                 **Blocking** = no cache; approved **Final** = cache. Told
                 apart by the Version's task (Blocking / Final tasks on
                 every shot, created 2026-10-19). Earlier note, kept for
                 history: "final" has to be told apart from an
                 approved block, e.g. with tasks (Blocking vs. Final).
                 What project 157 had at the time (read 2026-10-19):
                 Animation step (id 106) exists; only two Shot tasks
                 ("blocking" and "Blocking", both Animation, wtg); 738
                 Versions, none linked to a Task (`sg_task` empty), 2
                 Approved; Version `sg_version_type` list field exists with
                 no values yet. Options put to the user: Blocking/Final
                 tasks per shot under Animation, Version linked to its
                 task (final = Approved Version on the Final task); or
                 Blocking/Final values on the Version Type field.
               - **Review then publish (DECIDED 2026-10-19):** the student
                 submits review versions with **shotSub** until the shot is
                 Approved (any number of rounds). Once it's flagged
                 Approved, the student **republishes the shot with the pipe
                 Publish tool**, and that publish makes the caches (if it's
                 the Final task). This settles the timing: the cache comes
                 from the next pipe publish, not from the approved review
                 Version itself.
                 - Implication: the review Versions come from shotSub, so
                   shotSub is what must link each Version to its Blocking
                   or Final task. Publish then checks "does this shot have
                   an Approved Version on its Final task?".
                 - **No pipe publish before approval (DECIDED
                   2026-10-19):** Publish refuses a shot that has no
                   Approved Version. Approved Blocking → publish keys + full
                   file, no cache; approved Final → keys + full file +
                   caches. The shot camera follows the same rule via a
                   **Layout** task (Layout step): Approved Layout → camera
                   publish. Layout tasks created on all 75 NWF shots
                   2026-10-19. Open details in
                   `shotgridTemplate_requirements.md`.
               - SUGGESTION (superseded by the line above, kept for
                 history): since approval lands on a Version
                 that was already published without caches, the *next*
                 publish of a shot with an Approved Version is the final
                 one (caches made then); any later publish is also final and
                 replaces it as the true source. This matches the
                 "post-approval publish" idea in the original design.
             - SUGGESTION (not agreed): the asset publish stamps the
               ShotGrid Asset id (plus department and version) onto the
               published file's top nodes. Then the id travels with the
               nodes, so an **imported** copy is still recognised, which
               closes the import question raised earlier the same day.
               Existing publishes (e.g. `backpack_scout_model_v001-v003`)
               have no stamp: republish them, or fall back to the
               reference's file name.
             - SUGGESTION (not agreed): camera = a camera shape under the
               transform; kind (`model`, `rig`, ...) from the stamped
               department; animated = keys on it or on anything in its
               reference.
             - OPEN: select-and-add here vs. item 2's "scan the scene, list
               everything ticked". Possibly both (list starts full, Add
               Selected for anything missed).
             - OPEN: how a keyframed **model** reference (no rig, no
               `cache_SET`) is cached. Options put to the user 2026-10-19:
               cache the whole reference / refuse ("animate a rig") / allow
               with a warning.
          7. **Not in v0:**
             - Build Shot pulling animation back in. **Design talked through
               2026-10-23 (not built):** this is how a student moves a shot
               to a new machine or scratch drive (§3h "Wip between machines:
               CLOSED"). A clean Build from the individual publishes plus the
               student's published keys, not a copy of the full file, so
               every path is made fresh on this drive. The user: "I want the
               build shot tool to know they are on a new machine and handle
               that for them." The full file on H stays the manual fallback.
               - **A Keys column on the asset row (DECIDED 2026-10-23).**
                 When a rig (character / prop / vehicle) is in the shot's
                 list, its row gets a **Keys** dropdown beside Version:
                 defaults to the latest keys, lists every earlier publish so
                 the student can **roll back**, plus None (default pose).
                 Scout's keys go on Scout only. Keys never come without their
                 asset, so "keys but no rig" can't happen. Environments and
                 models show "—"; the camera keeps its keys inside its own
                 version, unchanged. "In this shot" shows the keys version
                 currently on the asset, like the rig version.
               - **One list, newest first (DECIDED 2026-10-23).** "The pipe
                 labels them as layout and animation but they're all treated
                 as date stamped versions and the pipe offers up the latest
                 version." Layout and anim mixed (`v005 anim`, `v002
                 layout`), ordered by **publish time** (the two keep separate
                 version numbers). Whoever published them doesn't matter.
               - **Rig leads (DECIDED 2026-10-23):** the rig version and the
                 keys version are picked separately. Keys made on another rig
                 version are applied anyway; Status lists the controls that
                 didn't match.
               - **Rebuild replaces (DECIDED 2026-10-23):** building a
                 different keys version deletes the asset's existing keys and
                 puts the chosen ones on, on the frames they were published
                 on (no offset).
               - **Unkeyed settings go too (DECIDED + BUILT 2026-10-28).**
                 Found building SEQ010_140: the rig's master control was
                 placed but not keyed, so the clean build put the character
                 at the origin, out of camera. The user: "They shouldn't need
                 to key the master control ... this is important for things
                 like space switching which may not be default but also may
                 not be keyed ... settings for all controls that are not
                 keyed need to be stored so that the pipe can reapply them to
                 a clean build." The keys map now also lists `settings`:
                 every keyable or channel box value on the asset with no
                 keys, nothing driving it and not locked, changed or not.
                 Every published asset gets a map, keyed or not (no keys =
                 map only, no keys .ma), and Build lists it in the Keys
                 column. Build sets the settings after the curves; what isn't
                 on this rig, or is locked/driven on it, joins the "didn't
                 match" list. Publish's summary says how many were carried.
                 Not covered: constraints, hidden (non channel box)
                 attributes. "None" still only removes keys.
               - **Animation layers are baked (DECIDED + BUILT 2026-10-28,
                 option 1 of 3).** SEQ010_140 then lost Scout's clavicles and
                 FK arms: they were on AnimLayer1, driven through Maya's
                 layer blend nodes, which the keys export didn't see.
                 Publish now bakes every layered channel to one plain curve,
                 a key every frame over the timeline (stepping the timeline:
                 reading a layered channel at another time came back wrong),
                 and names the baked controls in the Publish window and the
                 ShotGrid notes. The animator's scene keeps its layers.
                 Rejected: refuse until layers are merged (option 2); bake
                 only on layer key times (option 3, in-betweens can drift).
                 The rebuilt scene has dense keys on those controls.
               - **Made in the shot (DECIDED 2026-10-23):** left out until a
                 "created in shot" publish is designed.
               - **PARKED: keys onto a different rig through the "Building
                 into shot" picker** (e.g. Scout's keys on another
                 character). "A feature that would be great but right now can
                 be handled using Studio Library." No Animation department in
                 the picker for now.
               - **Which shot's keys (DECIDED 2026-10-23):** only the shot
                 the "Building into shot" picker points at. "By default the
                 student would only see keys associated with the shot ...
                 they were working in. They would have to manually change
                 the Build into shot dropdowns to point to the keyframes in
                 another shot." So:
                 - picker on the Asset route (no shot in it): the Keys
                   dropdowns list the open scene's shot's publishes;
                 - picker on the Shot route, pointing at a shot: they list
                   that shot's publishes (still Scout's keys onto Scout);
                 - a keys choice from another shot stays on the row, shown
                   as `v003 anim — SEQ010_110`, when the picker moves on
                   (it never silently flips back to this shot's keys).
               - **Built 2026-10-23** (`buildTool_api` "Shot keys",
                 `buildTool_ui` Keys column). Details decided while
                 building:
                 - Keys are matched to a row by the asset's pipe stamp in the
                   keys map (asset type + asset + department), read straight
                   from the H drive (curves are imported, so nothing is
                   pulled to scratch).
                 - **Hand keys are never wiped unasked:** an asset already in
                   the scene whose keys Build didn't put there starts at
                   "Keep scene's keys". Only picking a keys version (or None)
                   replaces them.
                 - The scene records which keys Build put on each asset
                   (fileInfo `pipe_keys`), so a reopened scene's row starts
                   there, unticked, and "In this shot" shows it.
                 - Only the animator's time curves on the asset are replaced;
                   the rig's own driven keys stay.
                 - Tests: `test_shotKeys_mayapy.py` 21/21 (keys written by
                   Publish's own `export_keys`), `test_shotKeysUi_mayapy.py`
                   16/16 (the real Build tab offscreen); other Build tests
                   unchanged and passing.
                 - Not handled: animation layers, constraints, keys on
                   things made in the shot.
               - **The shot's build list on H (DECIDED + built
                 2026-10-23).** The user: "the pipe needs to remember that
                 list on a per shot basis so that when a student points the
                 tool to a shot that list will populate". Before this, the
                 list came only from the shot's manifest on scratch, so a new
                 machine started empty.
                 - **One list per shot**, shared by everyone building it:
                   `H\<film>\maya\sequences\<seq>\<shot>\build_list.json`.
                 - It stores **just which assets** (asset type, asset,
                   department). On a new drive each comes back at its latest
                   version, and each rig's Keys at the shot's latest keys.
                 - Saved on every Build Shot (even with nothing ticked) and
                   when **"-" takes an asset off**, which removes it from the
                   shot's list for good. The scene keeps it ("-" is list
                   only). A "+" counts once Build Shot is pressed.
                 - A shot with no saved list yet falls back to its scratch
                   manifest, as before, and gets one on its next build. The
                   shot's camera is always added when published, as before.
                 - Tests: `test_shotKeysUi_mayapy.py` 23/23 (new scratch
                   drive), `test_addAssetOnly_mayapy.py` 29/29.
             - the camera fingerprint;
             - USD;
             - final publish checkboxes;
             - renaming items.
          8. **Script-node check, for every publish (DECIDED 2026-10-15):**
             Publish refuses a scene containing any script node other than
             Maya's standard `uiConfigurationScriptNode` /
             `sceneConfigurationScriptNode` (namespaced copies included),
             names the node, and explains how to remove it. Applies to
             asset, camera and shot publishes, not just animation. Why: on
             2026-10-15 a student scene carried the `maya_secure_system`
             scene virus (Defender: `Trojan:Python/Multiverze`), which hides
             its code in script nodes. Publishing such a scene would spread
             it to the shared H drive and into every shot that builds from
             it.
             - **Built 2026-10-15:** `publishTool_api.check_script_nodes()`
               runs first in `publish()` and `publish_camera()`, and on
               every Publish window refresh (which disables Publish). It
               also refuses the two standard names when they hold Python,
               `exec`, `base64`, `scriptJob`, `userSetup` and similar, and
               it covers referenced files. Testing showed why that matters:
               referencing a file runs its script node straight away.
               `test_scriptNodeCheck_mayapy.py` 8/8, including 41 real
               scenes (repo, T7, `D:`) that pass with their 68 standard
               nodes.
        - **Shot-only items** (effects, caches, rigs made for one shot):
          - They belong to the shot (ID rule) and live in the shot's
            folder on the H drive, named
            `<SHOT>_<name>_<dept>_v###`, e.g.
            `EAP_010_010_dustCloud_fx_v001`.
          - Build Shot lists them for that shot automatically, like the
            camera.
    Questions to settle:
    - Step 4 for shots only, or assets too?
    - Are there only two levels (iterative and final), or anything in
      between?
  - **Students choose what a final publish makes (raised 2026-10-13).**
    The user: "if the students are doing a final publish do we give them
    some control over what gets made eg check boxes that only become active
    for the final publish… That might help minimize the number of files
    created."
    - **Checkboxes are formats, plus presets where software needs its own
      export (DECIDED 2026-10-13).** "The Unreal FBX will need to be its own
      separate export to handle the different XYZ axis position in Unreal
      vs a regular FBX going to blender. So maybe the choices are not
      software specific except for Unreal or Houdini (which requires a
      scale consideration). So the check boxes might look like Alembic FBX
      Obj Unreal Houdini for example."
      - Generic formats: **Alembic**, **FBX** (e.g. for Blender), **OBJ**.
      - Presets: **Unreal** (an FBX with Unreal's axis set-up) and
        **Houdini** (exports with Houdini's scale).
      - OPEN: the exact axis and scale settings for each preset, to be
        tested in each piece of software. Keep them as settings, not
        hard-coded, so staff can adjust them.
      - **Render checkbox (DECIDED 2026-10-13):** "It should trigger a
        render (if a lighting rig exists and is published), there's work to
        do around this but I would like a render check box as an option for
        the final publish."
        - A **Render** checkbox on the final publish starts a render.
        - It's only available when a lighting rig exists and has been
          published.
        - OPEN (to design): what a lighting rig publish is, and how the
          render finds it; renderer and settings (Arnold, per §3i
          Cameras); output location and format; whether it goes to
          ShotGrid or the edit; where it runs. Locally for now, but it's
          the heaviest job, so it's a prime candidate for the farm (see
          "Where the processing runs").
      - **USD is in (DECIDED 2026-10-13):** "100% in for USD I just don't
        know anything about working with it. So I need to do some
        research there." A **USD** checkbox joins the list. How the USD
        export is set up (and whether it later shapes more of the
        pipeline) waits on that research. The user: "we are going to
        include it and it will be key." The user is researching USD
        themselves; Claude shouldn't research or write it up unless asked.
        Design choices made now shouldn't close off a USD-centred
        pipeline later.
    - SUGGESTION (Claude's, not yet confirmed):
      - the film sets which boxes start ticked (`pipeline.json` on the H
        drive), because a teammate may need a format the publisher doesn't
        use;
      - unticking loses nothing, because any format can be made later from
        the locked file on the H drive.
- **Animated props in a shot (to discuss next).** How a prop's animation
  is published from a shot and handled downstream (see §3i "Animation
  publish", "Shot publishes always use the whole timeline", and the
  camera's keys/camera split).

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

### 4a. Rig reference paths, scratch wipes and the edit (2026-10-20)

Discussed 2026-10-20 and parked ("lets document this issue so we can come
back to it"); later that day the user chose to build option C for rigs
(below). The wipe and edit items are still parked.

**Facts from the user (DECIDED 2026-10-20):**
- Student scratch drives at RMIT are **wiped every 3–4 weeks**, "for any
  reason the IT department can think of" (unannounced). Replaces the
  "every couple of weeks" note in §3h.
- **Maya prefs survive the wipe.** Only work on scratch is lost, so the
  mpPipe `userSetup.py` block / `$PIPE_SCRATCH` and mpToolSet stay.
- **Students can publish any time** (not only after approval). The user:
  "as long as they can rebuild from the h drive (and have been publishing
  regularly) then this seems ok". So "publish at the end of every session"
  is the WIP backup; no separate "back up to H" action is needed. Closes
  the WIP backup item in §6.
- **No per-shot version pinning (user preference).** By default every shot
  follows the current rig. Reverses the per-shot update in §3i "Each
  version is its own file" (2026-10-13), not yet changed in code.
- **Shared scratch `publish\` folder stays** (user: "happy with it").
- **Rigs not referenced live from the H drive**, for now ("I might change
  my mind once we start testing"). The §4 H-drive referencing test stays
  open.

**The problem (user, 2026-10-20):** a reference path that changes on every
rig update "tends to break maya's referencing system". The user has worked
around this before with one fixed-name rig file that gets saved over. The
current build changes the path every update (`scout_rig_v002.mb` ->
`..._v003.mb`) and relies on Replace Reference. That keeps keys when used
correctly, but breaks when a student references the new version instead
(new namespace), clears an old version before repointing, or the format
flips `.ma`/`.mb`.

**Options compared:**

| Option | Path never changes | Default update | Roll back one shot | Disk |
|---|---|---|---|---|
| A. One fixed-name file in shared `publish\`, saved over | yes | every shot | no, a rollback hits every shot (user's objection) | 1 copy |
| B. Fixed-name copy inside each shot | yes | every shot | yes | 1 copy per shot |
| C. Fixed name per shot, **hardlinked** to a version file in `publish\` | yes | every shot | yes | 1 copy per version |
| Current build: version files + Replace Reference | no | per shot | yes | 1 copy per version |

**DECIDED 2026-10-20 (user): "we are going to build option C for the rigs
and test it."** Built the same day, rigs only (`LINKED_CODES = ("rig",)` in
`pipeDev/buildDev/buildTool_api.py`); models and cameras unchanged:
- `pull()` copies the version into `publish\` as before, then
  `link_version()` points the shot's `<asset>_rig.<ext>` at it (hardlink,
  else a read-only copy). Manifest entry gains `link` and `hardlink`.
- `build_asset()` references the fixed name. A version change in a scene
  that already has it is a **reload**, not a Replace Reference. Scenes
  from before (referencing a `publish\` version file directly) are
  repointed to the fixed name once.
- After a rig update or rollback, Build Shot asks **"Switch … in your
  other shots too?"** with *Every shot* as the default button and *Only
  this shot* for a rollback (`other_shots_using()`, `update_shots()`).
- Windows keeps the read-only flag per piece of data, not per name, so
  removing a link unlocks the version too; Build locks `publish\` again
  afterwards (`_lock_publish_folder()`), also after My Scratch removals.
- Repair relinks a missing rig link from the shot's manifest. The Build
  table shows "Rig file missing / out of date: Build to fix" and "Up to
  date (full copy, not linked)". Building turns a copy back into a link
  when the drive is NTFS.
- Test: `pipeDev/buildDev/test_rigLink_mayapy.py` 35/35 (path never
  changes on update/rollback, keys kept, one copy of the data, every shot
  follows, one-shot rollback, Maya can't save over the link, cleared
  version still opens, Repair, copied shot folder relinked, fallback
  copy). Existing `test_buildTool_mayapy.py` 76/76 and
  `test_blankSceneLatest_mayapy.py` 2/2 still pass.
- Checked on this machine: hardlinks work on D: and G: (T7, NTFS), fail on
  F: (exFAT) with WinError 1, which triggers the fallback.
- Still to test by hand: in Maya with the UI on the T7 (incl. the "other
  shots" question), and with an RMIT login on a lab machine. Not yet in
  the mpPipe staff zip (rebuild with `pipelineInstaller/build_zip.py`).

**Original suggestion: C with automatic fallback to B.**
```
publish\assets\character\scout\scenes\scout_rig_v003.mb                 <- real file, one per version
sequences\EAP_010\EAP_010_010\assets\character\scout\rig\scout_rig.mb  <- hardlink to v003
```
- Maya references the shot's fixed name (`$PIPE_SCRATCH/.../rig/scout_rig.mb`).
  A hardlink is a second name for the same data, so ten shots on v003 use
  the disk of one v003.
- **Update** (default, all shots): Build deletes each shot's name and
  re-links it to v004 (`os.link`). Path unchanged, no Replace Reference, no
  namespace change. **Roll back one shot:** re-link only that shot.
- Which version each link points at: the manifest, verified with
  `os.stat().st_ino` against the files in `publish\`.
- Hardlinks need NTFS on the same drive and no admin rights (symlinks need
  admin/Developer Mode, so not those). Here: D: and G: (T7) are NTFS, F:
  (One Touch) is exFAT. Not reliable on network shares or Dropbox/OneDrive.
- **Fallback:** if linking fails or the drive isn't NTFS, Build copies
  instead (B) and says so. Shot scenes see the same path either way, so a
  change in RMIT's setup never needs scene files fixed. It only costs disk.
- Quirks: links look like normal full-size files in Explorer; copying a
  shot folder elsewhere turns the link into a real copy (Update no longer
  reaches it until Build re-links); linked files should be read-only so a
  save through the link can't change the shared version.
- Build would need a link check/repair view in plain language ("shot 020:
  linked to v003", "shot 030: plain copy, Repair?"), so nobody has to use
  `fsutil hardlink list`.
- Rig publishes should keep one format (`.ma` or `.mb`), or the fixed name
  changes.
- Trade-off of every fixed-name option: a bad rig update reaches all shots
  at once. Softened by rollback, the "don't rename controls" rule (§3i),
  and maybe a rig Publish check that warns when controls disappear.
- **Test on the T7 before deciding:** two shots hardlinked to one rig,
  Update, roll back one shot, Maya save over a (read-only) link, copy a
  shot folder, delete a version from `publish\`, and try it with an RMIT
  login.
- OPEN: models, cameras and other published assets fixed-name too, or rigs
  only?

**What the wipe means for the design (OPEN):**
- **Rig version record must live on H.** `build_manifest.json` is on
  scratch and gets wiped. With fixed names the shot's reference path no
  longer says the version, so without a record a wipe silently resets
  every shot to the latest rig (and loses a one-shot rollback). The §3i
  suggestion of a version record saved with each shot publish on H
  (`EAP_010_010_..._anim_v004.json`) + Build's "Restore versions from…"
  becomes required if C is adopted.
- **One "restore my scratch" action in Build:** skeleton, `publish\`,
  links and shots back from H after a wipe; run Repair before students
  open shots, so nobody removes "missing" references in a panic.
- **Class-wide re-pull after each wipe:** slow, especially MetaHuman rigs.
  Time it with a class; useful evidence for IT.
- Hardlinks are recreated on restore like files, so the wipe hits A, B, C
  and the current build equally.

**The edit (OPEN, SUGGESTION not agreed):** the one thing that doesn't
rebuild from H. Two halves:
- **Shot movies** (`premiere\shotgridMovs\`): rebuildable. All on
  ShotGrid, named by shot code, so a "Restore edit media" re-downloads the
  latest Version per shot under the same names (the A3 editorial pull as a
  button).
- **The edit project** (`.prproj` / Resolve project): lost today.
  - The user: EDLs will be produced for ShotGrid. An EDL keeps the
    **picture cut** (shot order, in/out, simple transitions, shot-code reel
    names) but not extra video tracks, music/SFX/voice, the mix, titles,
    effects or colour. Premiere usually imports EDL clips offline (relink);
    Resolve matches by name better.
  - **Middle option (user: "sounds good"):** keep the EDL as the official
    record for ShotGrid, and copy the project file (`.prproj` or exported
    Resolve `.drp`) to H each time an EDL is produced, e.g.
    `premiere\cuts\<login>\NWF_SHF_s1234567_edit_v004.prproj` + the `.edl`.
  - **Where it lives (suggestion):** a small desktop tool beside
    `pipeDev/desktopDev/h_sync.py` (plain Python, Windows + Mac), not Maya
    (editors may never open it) and not a Premiere panel (CEP→UXP churn,
    lab install, Resolve would need a second plugin). Student exports the
    EDL by hand into `premiere\edl\`, saves the project, runs **Publish
    Edit** (version + copy both to H, EDL to ShotGrid as a Cut). **Restore
    Edit** re-downloads movies and pulls the project + EDL back.
  - Launcher could run it with **mayapy** (on every lab machine, ships
    `shotgun_api3` via mpToolSet), so IT installs nothing. Untested.
  - Resolve keeps projects in a database (likely in the profile, so may
    survive like Maya prefs; check at RMIT). Whether the free version can
    script the `.drp`/EDL export is untested; fallback is a manual export.
  - OPEN: music/SFX/voice/titles from outside ShotGrid need a home on H or
    they come back offline (ties to "Non-software material" above); one
    editor per group or everyone their own cut (`<login>` folders or one
    shared); Premiere, Resolve or both first; how often EDLs are made and
    whether they're saved on H as well as ShotGrid.

### 4c. Environment publishes and layout placement (started 2026-10-21)

**mpLayout shelf, "Env Sets" (DECIDED + built 2026-10-23).** The user:
"a tool to help publish layouts that auto builds the groups and sets for a
clean publish ... for environment publish only that just builds the sets and
groups with the correct names. It's up to the artist to add what they want
published to the groups and sets." One click makes `environment` >
`landscape` / `buildings` / `sky` and `environment_SET` > `landscape_SET` /
`building_SET` / `sky_SET`, each group in its role set, names taken from
`publishTool_env`. Whatever exists is reused; a role set the artist already
filled is left alone; one undo. Code: `pipeDev/layoutDev/layoutTool_env.py`
(test `test_layoutEnv_mayapy.py` 12/12, including the filled-in scene passing
`check_environment`). Shelf: `shelfDev/mpLayout/`, installed with the mpPipe
shelf by `pipeDev/pipelineInstaller` (staff testing, not in either student
toolset). Image planes in the landscape already publish (checked 2026-10-23:
kept in place, pictures copied, `$PIPE_SCRATCH` paths).

Raised by the user after the scoutsHouse publish test. The model rules
(freeze, delete history, leave out hidden/empty, Mesh Cleanup, pipe group
at the origin, §4 item 6a) stay for **props, vehicles and character
models** (the backpack's rules). Environments need different ones.

- USER DIRECTION (2026-10-21):
  1. scoutsHouse should be **modelled at 0,0,0 and positioned in the
     shot**; the pipe has no way to do that yet.
  2. **Environment creation is part of the layout workflow**, which the
     pipe doesn't consider yet: sketch a camera and a performance of
     Scout, build a terrain and position a (placeholder) building in it.
     An environment publish must **keep the position of everything**,
     since it matters relative to the camera and the world layout for
     continuity: the **landscape and placeholder buildings stay where they
     are** in the initial publish.
  3. scoutsHouse is modelled and published at 0,0,0, then **matched back
     to the position of its placeholder** from the initial layout publish.
- Note (Claude): freezing keeps geometry in place but zeroes the
  transform, which is exactly the placement the real asset has to match,
  so placeholders' transforms must survive an environment publish.
- USER DIRECTION (2026-10-21): **use sets, as the pipe already does**
  (rig `cache_SET` / control sets). In layout the artist makes a
  **landscape set** and a **building set**; Publish has rules for how
  each is treated differently. Set names and rules not decided yet.
  - DECIDED (user, 2026-10-21): **landscape set** = stays where it is in
    the world, cleaned up like a model (freeze, delete history, Mesh
    Cleanup; the geometry doesn't move).
  - DECIDED (user, 2026-10-21): **building set** = **transforms kept**
    (never frozen). Publish **creates a locator** for each building at
    its placement, and the locators are **published with the landscape**.
    A **single-frame cache of the buildings and the landscape** is made
    for **visual reference when a shot is rebuilt**. The real building
    (modelled and published at 0,0,0) is later matched to its locator.
  - DECIDED (user, 2026-10-21):
    1. Tools to **build and name the sets** come later, e.g. a building
       set and a landscape set **nested in an environment set**.
    2. A locator **takes its name from the top group of the building
       asset**, so **every model or collection of models** (e.g. Scout's
       House) must be **parented under one group**.
    3. **Students match real assets to the locators themselves** and make
       a new environment publish with the updated assets; Build doesn't
       place anything.
    4. **Buildings are published with the environment** for now.
  - DECIDED (user, 2026-10-21): a **sky set** too, holding **image planes
    and/or skydomes, possibly cloud models**, maybe linked to an **image
    sequence**. Sky assets **keep their transforms** but are **locked on
    publish**.
    - Notes (Claude, for the questions): a skydome is usually a light
      (Arnold `aiSkyDomeLight`), which model publishes never carry; image
      planes are normally attached to a camera rather than free in the
      world; sky images/sequences would need to travel with the publish
      the way rig textures do (`publishTool_textures`, which already
      handles image sequences and UDIMs).
  - DECIDED (user, 2026-10-21), sky details:
    1. For layout and animation a **skydome is just geometry** (e.g. a
       big textured sphere), not a light, so no light rules are needed.
    2. Image planes are **free-standing** in the world (not on a camera).
    3. Sky images and image sequences **travel with the publish** like rig
       textures (copied to H per version, pulled to scratch by Build).
  - Example scene (user, 2026-10-21):
    `D:\NWF_SHF\maya\sequences\SEQ010\SEQ010_140\scenes\environment_001.ma`:
    `environment` > `sky` (free image plane `imagePlanesky`), `landscape`
    (`ground`), `shed` (placeholder `pCube1` + `pPlane2`); `camera1` stays
    outside (camera publish). In it, `shed` sits at 0,0,0 and its pieces
    carry the placement (moved, rotated -9.7 deg).
  - DECIDED (user, 2026-10-21), after weighing groups vs sets (sets can
    overlap and don't move anything; Alembic carries neither sets nor
    shader assignments, so lookdev will need re-linking by name or a
    per-mesh tag later):
    1. **Sets + groups**: groups say where things are (placement), sets
       say what they are (the rules: landscape, building, sky now; water,
       vegetation, junk and look sets later).
    2. A **building's group holds its world-space placement** (move and
       rotate the group, pieces at zero inside). The **locator is still
       made**: it lets someone zero a building out, add a prop, and snap
       it back.
    3. Source images belong in the **asset's own Maya project**
       (`<asset>\sourceimages\`), not in folders outside the film (the
       example's sky image is in `D:\projects\nwf_PREVIS\sourceimages`).
  - **BUILT 2026-10-21** with the defaults proposed that day (user: "ok
    are you good to build it?"), mayapy-tested
    (`publishDev/test_envPublish_mayapy.py`), not yet tried in Maya:
    `publishDev/publishTool_env.py` + an **Environment** department
    (`env`). Sets `environment_SET` > `landscape_SET` / `building_SET` /
    `sky_SET`; group names free except each building's group is named
    after its asset (warned if no such asset on H); refused: no sets, one
    thing in two roles, a building that isn't a group, two buildings with
    one name. **Changed same day (user): "if there are no transforms on a
    building the pipe shouldn't reject it. It should just be able to cope
    with it if there are."** A building group with transforms gives its
    locator its placement; one with none (like `environment_001.ma`'s
    `shed`) gets its locator at the **bottom-centre of its pieces, turned
    like them if they share a rotation**, and the publish report says so.
    The building itself is published as it is. Publishes from a
    shot's layout scene ("Add Environment" in the Publish window) or an
    asset scene, to an environment asset. Published file:
    `<asset>_env_GRP` > `landscape` / `buildings` / `sky` / `locators`
    (`<group>_LOC` at each building's world placement) + the sets on the
    copies; sky images travel (image planes added to the texture
    collector, environments only); images outside an asset's
    `sourceimages` are warned about and copied anyway; one-frame `.abc`
    of landscape + buildings beside the publish, pulled by Build with it
    (`SIDE_FILES`) but **not put in the scene** (OPEN). Follow-ups:
    `pipeDev/pipelineFollowUps.md`.
  - DECIDED + BUILT (user, 2026-10-22), **room for more than one
    building**: `building_SET` holds **one group called `buildings`**,
    and **each group inside it is a building** (a group holding that
    building's geometry), **named however the student likes**. Each
    building still gets `<group>_LOC`. Refused: anything else in
    `building_SET`, an empty `buildings`, a loose mesh inside `buildings`
    (not in its own group). The H-drive asset-name warning is **dropped**
    (user: does the building need to match the H-drive asset? No: per
    decision 3 above students match assets to locators themselves; the
    locator name says which building it is). The published
    `building_SET` holds the published `buildings` group, so a published
    layout passes the same check and can be published again.
  - Suggested pipe answer to "students match real assets to locators"
    (Claude, 2026-10-21, not confirmed): published model groups are locked
    at 0,0,0, so the student parents `<asset>_model_GRP` under its
    locator; it stays locked, at the locator's placement.
  - OPEN: the set names (suggested `environment_SET` holding
    `landscape_SET` + `building_SET`) and the locator name
    (`<group>_LOC`?); props/vegetation placed the same way or not; where
    the environment publish goes (the environment's own asset, e.g.
    `scoutsHouseLandscape`); what Build brings into a shot (the
    environment file, the one-frame reference cache, or both).
- OPEN: questions below, being worked through with the user.
- **2026-10-26 changes (DECIDED + built):**
  - **Buildings and sky are optional.** "not all environments will always
    need buildings or a sky. not having every item in the groups shouldn't
    prevent a publish." An empty role set or empty role group is left out
    with a warning; only all three empty is refused.
  - **Environment isn't a department.** "it doesn't make a ton of sense"
    beside Modeling/Rigging. From an asset scene, Modeling on an
    environment asset with an `environment_SET` becomes an Environment
    publish by itself (replaces the "Publish as Environment?" question);
    from a shot scene, Environment sits on the Shot side beside Layout and
    lists environment assets. File names keep the `env` code.
  - **New asset, not on scratch yet (option B, chosen over an override).**
    fieldA was made in ShotGrid and on H, but with no scratch project there
    was nowhere to save the scene so Publish would take it. Now, from a
    scene outside any pipe project, "+" with an asset picked offers "Save
    Here": the asset is made on scratch as Set Project would, the scene is
    saved as `<asset>_###` in `scenes\<login>\` (the open file left as it
    was), and the row is added. The Publish window also re-reads H's
    assets/shots on every refresh, so an asset made while it's open shows
    up. An override for publishing elsewhere stays parked (§4d).

### 4b. Studio Library data (started 2026-10-21)

The film folder already has an empty `maya\studioLibrary\` placeholder
(§3f). Nothing in the pipe tools touches Studio Library yet; it's
installed separately from both toolsets.

- DECIDED (user, 2026-10-21): the pipe helps with **where libraries
  live**, **sharing them between students**, and **pointing each
  student's Studio Library at the right library** (not the install).
- DECIDED (user, 2026-10-21): the libraries are mainly **rig-level and
  shared**: a pose/clip library per character that every animator uses.
- DECIDED (user, 2026-10-21): **both** a live working library people save
  into directly (Studio Library's normal way of working) **and** some
  poses promoted/published through the pipe (versioned, read-only).
- Facts that bear on it (not decisions):
  - Studio Library stores poses by control name, so a pose lives as long
    as the rig keeps its control names (§3i "don't rename controls").
  - Build references rigs as `<asset>_rig:` and published rigs carry no
    namespace, so poses saved in a shot record `scout_rig:`; Studio
    Library can remap namespaces on load.
  - RMIT scratch is wiped every 3-4 weeks; Maya prefs (where Studio
    Library keeps its library path) survive (§4a).
  - H publishes are read-only; Studio Library edits its own folders, so a
    live library can't be locked like a publish.
  - RMIT H is partitioned per login today; the pipe is built for the
    shared-server target (T7 stands in).
- User's goals (2026-10-21): (1) the Project Tool sets where Studio
  Library saves; (2) the data is backed up on the server; (3) a global
  library per project, a private sandbox per student, and shot-by-shot
  work; mocap-specific libraries later.
- Studio Library 2.20.2 (bundled) facts: named libraries, each a root
  folder, set from code (`studiolibrary.setLibraries`), kept in
  `%APPDATA%\StudioLibrary\LibraryWidget.json`; a window can be locked
  with `superusers` (logins allowed to edit); each library root keeps a
  cache, `.studiolibrary/database.json`, that rebuilds itself.
- SUGGESTION (Claude, not agreed): layout `studioLibrary\global\<type>\
  <asset>\{pose,anim}\`, `sandbox\<login>\`, `shots\<SEQ>\<SHOT>\<login>\
  {pose,anim}\` (A3 pattern), `mocap\` later; library list in the film's
  `pipeline.json`; Project Tool registers Global (locked unless a lead),
  Sandbox and the current shot.
- USER DIRECTION (2026-10-21): the data lives in **both places**: on
  scratch, so students can take it home on a drive, and on H as the
  backup. Proposed: an **animation publish checks the student's Studio
  Library folders for new/changed items and copies them to H**.
  - Points raised by Claude, not decided: shot publishes only happen after
    shotSub approval, but scratch can be wiped every 3-4 weeks, so poses
    made before approval could be lost (backup on shotSub submit too, or a
    Back Up button?); copy only the student's own folders, add-only, never
    delete on H; skip the `.studiolibrary` cache; Global goes H -> scratch
    only; a pull back down (Project Tool Update Scratch) after a wipe or at
    home; the same student on two drives -> newest item wins?
  - DECIDED (user, 2026-10-21): the backup runs on **every** pipe
    publish, iterative or final (not just approved shot publishes): check
    the folders, update H. The whole project's `studioLibrary\` is checked
    each time (the data is small), not just the publisher's folders.
  - OPEN: whether a student's publish may update folders that aren't
    theirs on H (Global, other students' sandboxes/shot folders) when their
    scratch copy is newer.
  - USER DIRECTION (2026-10-21, "maybe" on the exact place): a student's
    shot-by-shot Studio Library work goes in a `<login>` folder (e.g.
    `s1234567\`) **inside the shot's own Maya project**, perhaps its
    `data\` folder. The **show-level `maya\studioLibrary\`** is where
    motion gets **shared**. This replaces the suggested
    `studioLibrary\shots\...` layout.
  - DECIDED (user, 2026-10-21):
    1. Shot work folder: `<shot project>\data\studioLibrary\<login>\`.
    2. No private sandbox for now.
    3. Any student can save straight into the show library (so the
       publish backup copies show-library changes up to H too).
    4. The show library **mirrors the shot structure**, with a **face**
       (motion + pose) and a **body** (motion + pose) folder **per
       character**. The same again for **motion capture**, shot-specific
       and show-specific. The folders are made by the **desktop tool**
       (staff setup, `desktopDev/h_sync.py`).
  - DECIDED tree (user, 2026-10-21): keyframe/mocap sit **inside**
    shot/character; **every character gets folders in every shot** ("any
    character could be in any shot at any time during a production"), so
    no Shot -> Asset links are needed. (The student's shot folder was
    first going to use the same split; changed, see below the tree.)
    ```
    maya\studioLibrary\
      show\<character>\{keyframe,mocap}\{face,body}\{pose,motion}\
      sequences\<SEQ>\<SHOT>\<character>\{keyframe,mocap}\{face,body}\{pose,motion}\
    <shot project>\data\studioLibrary\<login>\      <- plain folder, students organise it
    ```
    Changed same day (user, 2026-10-21, "I was being too prescriptive"):
    the student's shot folder is just `data\studioLibrary\<login>\`, made
    by the tool; students organise what's inside. Only the show library
    has the fixed character/keyframe/mocap/face/body/pose/motion folders.
    `<character>` = the film's ShotGrid Character assets, named like their
    `maya\assets\character\` folders. A new character added in ShotGrid
    gets its folders in every shot on the next desktop-tool sync (add
    only, like the rest of `h_sync.py`).
  - DECIDED (user, 2026-10-21): the desktop tool makes the show library
    (`show\` + `sequences\`); the Project Tool makes the student's own
    `data\studioLibrary\<login>\` when they set that shot as their
    project, so H doesn't get folders for every student in every shot.
  - **BUILT 2026-10-21** (mayapy-tested, not yet tried in Maya by the user):
    - `desktopDev/h_sync.py`: plans/builds the show library folders for
      every ShotGrid Character, show-wide and per worked-on shot; add only;
      a new character gets folders everywhere on the next sync.
    - `publishDev/pipeStudioLibrary.py`: `back_up()` (scratch -> H, the
      show library + every shot's `data\studioLibrary`), `restore()` (H ->
      scratch, the show library + the person's own shot folders),
      `configure()` (Studio Library settings), `use_config()` (startup).
      Sync rules: copy what's missing or newer, times kept, via a temp
      name; never delete; never write an older copy over a newer one (the
      student is told); skip `.studiolibrary\database.json` (per-item
      `.studiolibrary\metadata.json`, tags/colours, does travel).
    - Project Tool `set_project`: makes `data\studioLibrary\<login>` for a
      shot, restores, and registers "`<FILM>` Show" + "`<FILM>` `<SHOT>`
      (mine)" (the shot one opens by default; for an asset, the show one).
      The pipe's entries are tagged `mpPipe_film` and replaced on each
      switch; the person's own libraries are kept. Studio Library folders
      are left out of the 1:1 folder mirror and its banner (they'd nag
      every time someone shared a pose, and make empty shells of others'
      items); `restore()` brings them down with their files instead.
    - Publish UI: one backup after any successful publish; a backup
      problem is a line in the report, never a failed publish.
    - Studio Library only searches 5 folders deep by default; show
      library items sit 8 deep. `pipeEnv.install()` (startup) points
      `STUDIO_LIBRARY_CONFIG_PATH` at `<prefs>\mpPipe_studioLibrary_config.json`
      (`recursiveSearchDepth` 12) unless something else set it; the Project
      Tool also raises it in the running session.
    - Known limits: a deleted item comes back on the next restore
      (removing for good is a staff job on H); "reopen Studio Library if
      it's open" after switching project; restore walks the H show library
      on every Set Project (fine for NWF's ~3,600 folders; time it at
      RMIT).

### 4e. Open scene vs Maya project — DECIDED + BUILT (2026-10-28)

The user: "I keep changing the project expecting that to effect where the
build tool is building from and where the publish tool is publishing to and
I think that's why I keep sending stuff to the wrong place." Build and
Publish go by the open scene (it's what they build into and publish);
Set Project only changed the Maya project. Decided (both from options put
to the user):

- **Set Project offers to switch scene.** When the open scene is in another
  shot or asset (or is unsaved with changes), the Project Tool asks: Open
  <newest scene in the new project> / New Scene / Keep Current Scene, and
  Save / Don't Save / Cancel for unsaved changes before switching. Its old
  "Set the project anyway?" prompt is gone.
- **Mismatch: warn, let me carry on.** When the open scene and the Maya
  project are in different pipe shots/assets, Build and Publish show a red
  banner ("Your open scene is in shot SEQ010_140, but your Maya project is
  asset shed. Publish uses the open scene: shot SEQ010_140.") with a "Set
  Project to the scene's" button, and ask before building or publishing
  (Build Anyway / Publish Anyway / Cancel). Scenes or projects outside the
  pipe, and untitled scenes, don't count.
- With an unsaved scene, Publish's picker now starts on the Maya project's
  shot or asset, as Build already did.

### 4d. Things made in the shot, and reusing them in another shot — PARKED (2026-10-26)

Raised 2026-10-26; nothing built, nothing decided. The user: "lets record
this for now, put a pin in it and come back to it later." This would be the
"created in shot" publish that §4 item 7 leaves made-in-shot items out of
Build until it's designed.

1. **Where it started: reusing a shot's animation in another shot.** The
   user: "There will be times (although not often) when a student will want
   to publish something to a shot from a different project", clarified as
   "publish animation from one shot to another to reuse it? Shifting shot
   assets to an existing shot name." Today shot publishes take their shot
   from where the open scene is saved (`publishTool_camera.plan_camera`),
   and the Publish window refuses another film's assets.
   - SUGGESTION (Claude): a "Publish to another shot" checkbox in a shot
     scene, off by default, that unlocks the sequence/shot dropdowns; a
     confirm step naming from → to; the source shot recorded in the stamp.
   - OPEN: shift keys to the target shot's start frame (Claude: yes, offset
     shown in the confirm), or publish them unchanged? Animation only, or
     the camera too (Claude: animation only)? Same film only (avoids
     published shot files referencing another film's assets)? Is "shifting
     shot assets to an existing shot name" the same thing, or renumbering a
     shot in the edit (a separate tool)?
   - Note: Build can already take another shot's keys through the
     "Building into shot" picker (§4 item 7), which covers part of this for
     pipeline rigs.
2. **Proposed by the user: a shot group with role groups and sets, like the
   environment publish (§4c).** "A group that the artist can add the things
   to perhaps the groups would be rig model lights reference cache fx in a
   master group with an appropriate name. The groups would have
   corresponding sets."
   - SUGGESTION (Claude), not agreed:
     - Only for things **made in the shot**. Rigs/models/cameras that came
       in through Build already know what they are (the 2026-10-19 rule:
       the animator just selects, Publish works out what each thing is).
     - Master group + set, e.g. `shot_GRP` / `shot_SET` (name OPEN),
       holding `model`, `rig`, `lights`, `reference`, `cache`, `fx`, each
       with its own set; a button makes the structure (like the
       environment layout button). Empty groups are fine (the 2026-10-26
       environment fix).
     - The group decides the treatment: model → Alembic (whole timeline,
       or one frame if static); rig → its own `.ma` + keys by control name;
       lights → the existing light item; reference → image planes / guide
       geo, copied but never cached or rendered; cache → imported caches,
       their files travel as they are; fx → placeholder until FX.
     - Published with the shot's Layout/Animation stage, same version
       number; not a separate department.
     - Build puts them back into the same structure (the missing half
       today).
     - Made-in-shot things outside the groups: published as now, with a
       warning naming them; never refused.
     - Would also make reuse (1) cleaner: Build pulls another shot's shot
       items.
   - OPEN: what `reference` and `cache` mean (Claude's reading above);
     the master group name.
3. **A custom rig built for one shot.** The user asked "What if a student
   builds a custom rig for one shot?"
   - SUGGESTION (Claude): one shot only → the `rig` group: published as
     its own `.ma` with the shot's version, keys exported by control name,
     cached through a `cache_SET` inside it (the same rule as pipeline
     rigs); no ShotGrid asset or approval. Used in more than one shot →
     promote it to a real asset (Rigging publish from an asset scene);
     a "promote to asset" step later, carrying its shot keys over by
     control name. Rule of thumb: one shot = shot rig, two = asset.
   - OPEN: is the rig built inside the shot scene, or in its own scene and
     brought in? (Claude: if it's in its own scene, treat it as an asset
     from the start, since there's no place for a shot rig's working file.)

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
- **WIP backup:** (answered 2026-10-20, §4a: students can publish any time,
  so regular publishing is the backup.) Work in progress lives only on scratch until approval
  (possibly weeks). If scratch drives aren't reliable, consider a
  "back up to server" action that isn't a publish. The user's view so far is
  that the sandbox is disposable by design.
