# Film pipeline — follow-ups (from the 2026-10-21 reflection and review)

Collected from the morning check-in, the code review of the rig publish and
Build work, and everything built during the day. Details and decisions live in
`filmPipeline_spec.md` (section numbers below); this is the to-do list.

Status: **[ ]** to do · **[?]** needs your decision · **[x]** done

---

## 0. [x] How wip moves between machines — CLOSED 2026-10-23

Decided: unpublished work is the students' job; the pipe doesn't manage it.
To move work between machines, students make an iterative publish (not
blocked by approval) and Build it on the next machine. No wip texture
repointing, no "save my wip to H" action. Recorded in spec §3h (Build
section, "Wip between machines: CLOSED").

## 1. Hand tests in Maya (nothing here has been tried by hand yet)

Everything below passes its mayapy tests, but none of it has been tried by
hand. One T7 session could cover most of it.

- [ ] Publish and Build windows on the T7 (backlog from 2026-10-15).
- [ ] Shot publish v0 with a real Approved Version on EAP_010_010
      (Layout / Blocking / Final tasks), backpack v008+ with the stamp.
- [ ] Rig hardlinks: build Scout into two shots, update one, choose
      "Every shot" / "Only this shot", reopen both (spec §4a).
- [ ] Keys column (built 2026-10-23, spec §4 item 7): publish Animation on
      one machine/drive, then in a fresh scene on another drive add Scout's
      rig and Build: keys on, same frames. Roll back to a layout publish;
      point the picker at another shot and take its keys; reopen.
- [x] **New machine: the Build list starts empty.** Fixed 2026-10-23: each
      shot's list is saved on H (`build_list.json` in the shot folder) on
      Build Shot and on "-", one list per shot, and fills Build on any drive
      (spec §4 item 7, "The shot's build list on H").
- [ ] Hand test the shot list: build a shot on one drive, open a scene in
      that shot on another drive (T7 / D:), check the list comes back with
      the latest keys; "-" an asset, reopen, check it stays off.
- [ ] Publish failure popup (2026-10-28): make a publish fail in Maya and
      check the red PUBLISH FAILED window reads well on Maya's dark theme.
- [ ] Model/rig/lookDev folders (2026-10-28, spec "Asset working folders"):
      run h_sync on the T7 to add them to existing assets; Set Project an
      asset and check scenes\model|rig|lookDev\e131988 are made; Save Here a
      model scene; publish it and check it lands in scenes\e131988.
- [ ] Import into Asset (2026-10-28): open a scene in scout\scenes\rig\,
      Build: import the latest Scout model and a textured rig; check no
      reference, textures load from scout\sourceimages\<publish name>\, DNA
      works after reopening; import again and pick Skip.
- [?] MetaHuman model publish (2026-10-28): the plain model publish drags
      the original meshes in through the `*_pgcombined` face sets (Scout
      model v001 has the model twice) and those sets must be kept. Needs its
      own publish: how to detect it, what it keeps, where it goes next, name.
- [ ] Scout v004 in a shot: can animators click-select controls inside
      the dagContainer group? Try it once with
      `selectPref -containerCentricSelection` on as well (review #9).
- [ ] MetaHuman face after a **drive change**: open a Scout shot from a
      different drive letter and check the face moves. The DNA path is only
      fixed after the scene opens (review #5). If it fails, fix the path
      *before* open instead.
- [ ] Everything with a real **RMIT login** (not `scout`).
- [ ] **Picker row redesign** (2026-10-22), Publish and Build: Film |
      Asset or Shot | Department | Type or Sequence | Asset or Shot, then
      - / +, and ticks on the list. Used for the shed environment publish
      and build (2026-10-22). Still to check: Build follows a newly opened
      scene when the window is clicked, and a new scene builds into the
      Project Tool's shot.
- [ ] **Set Project** in the Project Tool (Build's button was removed
      2026-10-22; Build still sets it): File > Open starts in
      the new project, it shows in Recent Projects, and it's remembered next
      session (fixed 2026-10-21; the Maya-UI part can't run headless).
- [ ] Build tab: **Remove from List** and the new **Show:** department
      filter (2026-10-21).
- [ ] **Studio Library** (spec §4b): Set Project on a shot → two libraries
      appear ("NWF_SHF Show", "NWF_SHF <shot> (mine)"), the shot one opens
      by default, show-library poses are found 8 folders deep; a publish
      backs up; a wiped scratch comes back on Set Project.
- [ ] **Watch before publishing** (2026-10-21, simplified 2026-10-22): Publish
      opens the movie in RV as a reminder; Publish / Cancel work straight
      away, and closing RV brings that window to the front. Check it does
      come to the front over Maya, and that Cancel leaves nothing on H,
      ShotGrid or scratch.
- [x] **Environment publish** (spec §4c): DONE by hand 2026-10-22 —
      `shed` environment published from SEQ010_140 (`shed_scout_env_v001`,
      cache + sky image on H) and built back into a shot, with the new
      picker row and the `buildings` group. Still worth a look: does the
      sky image plane show its picture in the built shot (through
      `$PIPE_SCRATCH`)?
- [ ] **Scratch on a different drive** (spec §3i, 2026-10-22): copy a built
      shot's scratch film folder (shot + `maya\publish\`) to another drive
      letter, e.g. a USB stick as `E:\`. With the saved scratch setting
      still pointing at the old drive, open the shot from `E:\` and check:
      references, rig textures, MetaHuman DNA (rig logic runs) and the sky
      image plane all load from `E:\`; Build, Publish and the Project Tool
      each say "Scratch drive set to E:\". Then delete `E:\...\maya\publish\`
      and check Build/Repair pulls the shot's versions back from H.
- [?] **Unpublished textures on another drive**: a wip asset scene carried
      to a different scratch drive keeps full `D:\...\sourceimages\` paths,
      so its textures go missing. Warn about it, fix paths to this drive on
      open, or leave it to students?

## 2. Decisions waiting on you

- [?] **Rollback undone by the default button** (review #4). Shot A is
      rolled back with "Only this shot", then updating shot B offers
      "Every shot" as the default (Enter) and re-updates A. Either make
      "Only this shot" the default, or remember rolled-back shots in the
      manifest and leave them unticked.
- [?] **Whole-scene rig publish** (review #6) puts *every* top-level node
      (stray lights, extra cameras, stand-ins) into `<asset>_rig_GRP`.
      Require a selection for rigs, list what was included, or keep as is?
- [?] **Environment cache in shots** (spec §4c): Build pulls the
      one-frame `.abc` with the environment but doesn't put it in the scene
      (both at once would overlap). Should it replace the environment file
      in shots (light stand-in), be referenced unloaded, or stay a file?
- [?] **Four MetaHuman DNA defaults**: folder, refuse if missing, warn on
      mismatch, full copy per version. These were my suggestions and were
      never confirmed one by one.
- [?] **Shot publish "not in v0" list**: explained 2026-10-15 but never
      explicitly confirmed.
- [?] **What decides the latest shot publish**: still open, doesn't block
      v0.

## 3. Bugs and risks found in the review

- [x] Build lost its "Nothing has been published" message (#1), fixed.
- [x] Shapes in `cache_SET` made shots cache the whole rig (#2), fixed.
- [x] A group and a mesh inside it in `cache_SET` broke the Alembic (#3),
      now refused at rig publish.
- [ ] **Namespace clash on publish** (#7): stripping namespaces can make
      Maya silently rename a node (`head_geo` → `head_geo1`). If that hits
      a DNA node the face fails with no error. Refuse clashes instead.
- [ ] **MetaHuman face controls in a selection publish** (#8): if
      `headGui_grp` isn't under the selection, the auto-added face controls
      point at nodes that aren't exported, so `face_controls_SET` comes out
      short without a warning.
- [ ] **macOS** (#10): the T7 is NTFS, which a Mac can only read, so the
      desktop tool can't write to the stand-in H from a Mac. On macOS,
      Build's "latest" uses modified time, so a copied publish can sort
      wrong; use the creation time (`st_birthtime`) there.
- [ ] Minor: the artist's name is looked up in ShotGrid twice per publish;
      the plug-ins stamp lists every plug-in in the scene, not just the
      selection's; each relink re-locks the whole `publish\` folder (slow
      as textures pile up).

## 4. Environments (spec §4c, built 2026-10-21)

- [ ] Get `D:\NWF_SHF\maya\sequences\SEQ010\SEQ010_140\scenes\environment_001.ma`
      ready to publish:
  - `shed` sits at 0,0,0 with its pieces placed. That's fine now: its
    locator goes at the bottom-centre of the pieces, turned -9.7° like them
    (checked on a copy). Check that's where you'd want a 0,0,0-modelled
    shed to snap to.
  - Add the sets: `environment_SET` holding `landscape_SET` (ground),
    `building_SET` (shed) and `sky_SET` (imagePlanesky).
  - Move the sky image from `D:\projects\nwf_PREVIS\sourceimages\` into
    the environment asset's own `sourceimages\`. Publish only warns about
    it and copies the image anyway.
- [ ] **Tools to build and name the sets** (and groups) for students.
- [ ] More sets later: **props, vegetation, water, junk**. Water may need a
      full-range cache; vegetation shouldn't be frozen; junk is placed
      like buildings.
- [ ] **Lookdev re-linking**: Alembic carries neither sets nor shader
      assignments, so lookdev must be re-linked to cached meshes by name
      or by a per-mesh tag attribute (e.g. `pipe_look`) that Alembic does
      carry.
- [ ] Confirm the **house-on-locator** workflow: parent the published
      `<asset>_model_GRP` under its `_LOC` (it stays locked, at the
      locator's placement). Tested headless.

## 5. Studio Library (spec §4b, built 2026-10-21)

- [ ] **Deleting a pose for good** is a staff job on H: a pose deleted on
      scratch comes back on the next Set Project, because the sync only adds.
- [ ] After switching project, Studio Library must be **reopened** if it
      was open.
- [ ] **Time the restore at RMIT**: it walks the H show library on every
      Set Project (fine for NWF's ~3,600 folders locally).
- [ ] **Load test with a class**: Studio Library's own index
      (`.studiolibrary\database.json`) in the shared show library is
      written by everyone at once; it rebuilds itself, but check it holds up.
- [ ] Run the desktop tool for real on the T7 to create NWF's show library
      folders (6 characters × 75 shots).

## 6. Open threads (not started)

- [?] **PARKED 2026-10-26: things made in the shot + reusing them in
      another shot** (spec §4d). Your idea of a shot group with
      rig / model / lights / reference / cache / fx groups and sets, a
      custom one-shot rig, and publishing animation to another shot.
      Open questions are listed in §4d; come back to it later.

- [ ] **Build warning** when a rig's `pipe_plugins` aren't loaded.
- [ ] Scan a newer **Advanced Skeleton** rig and a **Rapid Rig** rig for
      their set names (`rig_rules.py`).
- [ ] **Rig version record on H**: the scratch manifest gets wiped, and with
      fixed rig names a wipe silently resets every shot to the latest rig
      and loses rollbacks. Also a "restore my scratch" action (spec §4a).
- [ ] **The edit**: EDL + project file to H via the desktop tool (parked,
      spec §4a).
- [ ] **Class Project Setup Tool** (desktop, Windows and macOS) beyond
      `h_sync.py`.
- [ ] **Jiffy Schedule** integration with the pipe / Project Tool.
- [ ] Offered earlier, not done: a self-unload line in every
      `install.py`/`uninstall.py` (Maya caches a dropped `install` module),
      and the repo mpPipe installer running from source.

## 7. Housekeeping

- [x] **Commit today's work**: committed locally 2026-10-21 (`8c02061`),
      not pushed.
- [x] **Pipeline tools backed up to git**: the user is fine with the public
      scriptDev repo (2026-10-21); everything pushed (`e74fb3f`). Pushes of
      `pipeDev/` never trigger a student release; only changes under
      `mpToolSet/` or `studio4AnimToolset/` do, so check those before pushing.
- [ ] **Rebuild the staff zip** (`mayapy pipeDev/pipelineInstaller/build_zip.py`)
      once you want to test on the T7; it now includes `pipeStudioLibrary.py`
      and `publishTool_env.py`.
- [ ] **Evidence for IT**: class-sized load, pull/publish timings, the
      permissions needed (shared server case).
- [ ] This machine's mayapy prints a traceback from
      `FabPlugins\...\userSetup.py` ("initialize_plugin is not defined") on
      every start. It's harmless for the tests, but worth fixing or removing.
