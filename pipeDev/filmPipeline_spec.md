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
- Reference paths work from any drive because of `$PIPE_SCRATCH`; students
  also need the versions their shot uses in that drive's `publish\` (§3i
  "Reference paths that work on any drive", 2026-10-13).

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

  **One shared publish folder on scratch (DECIDED 2026-10-13, replaces
  step 3 above):** "We should not be saving the rigs and the assets to each
  individual shot." Copying an asset into every shot that uses it adds up
  quickly. Instead, everything Build Shot pulls from the H drive (assets
  and their textures) goes into one folder on the student's scratch,
  `D:\NWF_SHF\maya\publish\`, shared by all their shots. Image sequences,
  caches and the like stay in each shot's own folder on scratch. Shots no
  longer keep assets in their own `assets\` folder.

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
  The H drive stays a single saved setting. OPEN: confirm the H drive has the
  same letter in every classroom, and whether Maya prefs follow students
  between machines.

  **Moving between rooms (reminder of the §3h decision, unchanged).** The
  H drive carries only publishes. A student's own working files (shot
  scenes, wip asset scenes, caches, image sequences) stay on the scratch
  drive they were made on. Students move those themselves (portable drive
  or cloud), and the tools don't manage it. On a new machine, Build Shot
  pulls whatever published versions are missing there. With students
  changing rooms often, this copying is a regular chore with a risk of
  copying old over new. Noted, not reopened.

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
  - **How work reaches a personal folder on the H drive (DECIDED
    2026-10-13):** "the working files get into the personal folder on the
    H drive when a student publishes work from their scratch to the H
    drive." Publish is the only way in. There's no separate share step, and
    §1 still holds (nobody saves to the server by hand).
    - OPEN: exactly what lands there. Does the versioned publish itself go
      in `scenes\<login>\` (instead of `scenes\`)? Is the working file
      copied alongside it? Is version numbering per asset (shared by the
      group) or per person?
  - **Overwriting (DECIDED 2026-10-13):** "People can overwrite their own
    work on the scratch drive but not on the H drive." The H drive is
    add-only: every publish is a new locked version, and nothing there is
    ever overwritten. That's already how Publish works (read-only,
    `_v###`, never reused).
  - Whether the tools only offer projects the person is assigned to in
    ShotGrid.
  - SUGGESTION (Claude's, now in question given the publish decision
    below): published files stay as they are (`scenes\<asset>_<dept>_v###`,
    one version series per asset, not per person). ShotGrid already
    records who published each version.
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
          - OPEN: whether every animated made-in-the-shot thing is
            published automatically or the animator picks them; what each
            one is called; and what happens to static things made in the
            shot.
        - **NEXT SESSION: confirm these defaults before building the shot
          publish v0 (parked 2026-10-13, at the user's request: "ask me
          these questions next time").** Nothing is built yet; today only
          the shot camera can be published. Proposed v0 defaults:
          1. **One version number per publish:** everything from one
             animation publish shares a `v###` ("anim v003 of
             EAP_010_010").
          2. **Pipeline rigs** (references from `publish\` with a
             `cache_SET`): one Alembic per rig of the `cache_SET`, over the
             whole timeline, plus a keys file and map that record the rig
             version.
          3. **Made in the shot:** every animated one is published
             automatically, each as its own Alembic named after the object
             (`EAP_010_010_bouncingBall_anim_v003.abc`). Static ones are
             skipped in v0.
          4. **Where files go on the H drive:** caches in the shot's
             `cache\alembic\`; keys files and maps in `scenes\`, next to
             the camera publishes.
          5. **ShotGrid and the edit:** a Version on the Shot with the movie
             (with sound), plus a copy in scratch
             `premiere\shotgridMovs\EAP_010_010.mp4`.
          6. **Not in v0:**
             - Build Shot pulling animation back in;
             - the camera fingerprint;
             - USD;
             - final publish checkboxes;
             - renaming items.

          Also still to ask: all vs animator-chosen items, naming, and what
          happens to static things made in the shot (above).
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
