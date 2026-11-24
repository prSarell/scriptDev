# Film pipeline — follow-ups (from the 2026-10-21 reflection and review)

Collected from the morning check-in, the code review of the rig publish and
Build work, and everything built during the day. Details and decisions live in
`filmPipeline_spec.md` (section numbers below); this is the to-do list.

Status: **[ ]** to do · **[?]** needs your decision · **[x]** done

---

## PICK UP HERE: left 2026-11-03

Stage 2 started: tidy up and add features, with contributors joining. Read
`pipelineReview_stage2.md` (the review, plus your answers so far).

**GitHub: protect the repo before anyone joins**
- [ ] Review and merge the PR for branch `setup/contributors`:
      github.com/prSarell/scriptDev/pull/new/setup/contributors
      (CODEOWNERS, CONTRIBUTING, issue forms, PR check, `PIPE_RULES.md`,
      `run_tests.py`, `handTests.md`, the review). Tag `stage1` = the
      pipe before this, a permanent restore point.
- [ ] Settings → Rules → Rulesets: on `main`, require a PR with 1 approval
      and review from Code Owners; block force pushes and deletion; add
      yourself to the bypass list.
- [ ] Settings → Environments: create `student-release` with you as
      required reviewer. Move the 3 `SHOTGRID_*` secrets into it, then
      **delete the repository-level copies**.
- [ ] Settings → Collaborators: invite the contributors with the **Write**
      role (needs their GitHub usernames).
- [ ] Tell Claude who codes, who tests, and who does both, so it can make one
      issue per hand-test section for testers to pick up.

**ShotGrid: new site `dsc-sod-animation.shotgrid.autodesk.com`**
- [ ] Log in. Is anything already migrated, or is it empty?
- [ ] Ask Autodesk support whether they can migrate or clone the old site's
      (`nfw`) data. If not, Claude scripts it through the API: dry run first,
      then one project, keeping an old → new ID table.
- [?] Move everything (class projects too) or only NWF? Does the new site
      replace the old one, or will both run for a while?
- [ ] Admin → Scripts: make a new script (e.g. `mpPipe`) with limited
      permissions, and a **new key** (the old key is inside the public
      mpToolSet zip). Put the key in your local `shotSub_config.json` and
      the GitHub `student-release` secrets. Never in chat or the repo.
- [ ] Then Claude updates `pipeline.json` (project ID) and the connection,
      checks names still match H, reruns `asset_tasks.py`, and you run
      hand tests S1–S4.
- [ ] shotSub link files (and probably Jiffy's) store the old project and
      shot IDs: relink by hand, or Claude writes a script to rewrite them
      from the ID table.

**SharePoint and server**
- [ ] When SharePoint is set up: send Claude the path to the synced H
      folder, then run `handTests.md` section K there, and again on the
      server.

**Hand tests**
- [ ] Work through `handTests.md` A–J on the T7 (report each result in a
      GitHub issue, or tell Claude the ID and what you saw).

**Claude to check**
- [ ] The first full run of `mayapy pipeDev/run_tests.py` was started
      2026-11-03 and hadn't finished when we stopped. Rerun it and look at
      the summary (`test_projectMatch_mayapy.py` is known stale).

**renderSub (built 2026-11-13, spec "renderSub")**
- [ ] Hand test the window in Maya (mpLighting shelf, after reinstalling
      mpPipe): render each frame mode, Cancel mid-render, close and reopen
      the window during a render, Play in RV, Delete, Publish. The engine
      was tested headless and on SEQ010_140 (published as
      `SEQ010_140_e131988_render_v001`, ShotGrid Version 13643); the
      window itself hasn't been clicked yet.
- [x] Hand test **partial publish** (built 2026-11-13 after a power cut; PASSED by the user 2026-11-13):
      reopen renderSub on SEQ010_160; `e131988_render_v003` should list as
      "39 of 181 frame(s) interrupted". Play in RV (1001-1039), then
      Publish Selected: H gets 1001-1039 (not the 1040 stub), ShotGrid
      note says partial. Also Cancel a batch render mid-frame and publish.
- [?] **Resume** a stopped render into the same version (render only the
      missing frames)? Not built; ask the user.
- [?] Add a **Lighting** task to the NWF shots (none have one), so render
      Versions sit on it. Claude can script it, as `asset_tasks.py` does for
      assets.
- [?] Arnold **batch** licences: this machine has none, so background
      renders carry Arnold's watermark. Do RMIT lab machines have them? If
      not, finals need a licensed machine, the farm, or an in-Maya render
      option.
- [ ] **Flow Render (Autodesk cloud rendering), researched 2026-11-13.**
      The user: "this might be a great option for students to handle test
      render submissions during animation without locking them out of
      machines." Planned as renderSub's **Render on: Flow Render (cloud)**
      (the greyed "Render farm" slot).
      - What it is: Arnold's cloud render service (tech preview since Arnold
        7.5.1, March 2026), not part of Flow Production Tracking. 40 h
        (2,400 min) free render time per user per month; CPU only; no
        end date or price announced; 7.5.4 added custom OCIO, UDIM tokens,
        a per-frame time limit. Sources: cgchannel.com Arnold 7.5.1 / 7.5.3
        / 7.5.4 articles; blogs.autodesk.com 2026-04-27 "Cloud Rendering
        with Autodesk Flow Render".
      - Scriptable (read on this machine, Maya 2027's Arnold):
        `C:\Program Files\Autodesk\Arnold\Maya2027\scripts\flow_render\`.
        `ExportQueueManager.instance().createNewJob()` then
        `flow_render.cmds.submitFlowRender.submitFlowRender(cameras, width,
        height, startFrame, endFrame, frameStep, ...` (CORRECTED 2026-11-13: `frameSampling` is
        motion-blur sub-frames, not a frame list; Flow renders start..end by
        step only), `
        autoDownload=True, autoDownloadLocation=<version folder>,
        jobId=job.job_id ...)`. Status: `cmds.flowRenderQuery(jobStatus=<id>)`
        -> (status, percent); local id -> cloud id with
        `flowRenderQuery(fgeIdFromJobId=...)` (see
        `cmds/waitForFlowRenderJob.py`). Plug-in: `flowRender.mll`.
      - How it uploads: saves a temp copy of the scene beside it, converts to
        USD in a background mayabatch (Maya stays free), uploads, renders in
        the cloud, downloads frames. Needs the scene saved.
      - Blockers: (1) needs Arnold for Maya 5.6.1+: in Maya 2027 here, NOT
        in Maya 2025's Arnold (the pipe's target); depends on RMIT lab
        versions. (2) Unknown if RMIT education logins get the free hours.
        (3) Preview: an extra option only, never a pipe dependency.
        (4) Untested: do Build's `$PIPE_SCRATCH` references and Alembic
        caches survive the USD export + upload? Does the export need an
        Arnold batch licence (probably not)?
      - [x] **BUILT 2026-11-13 as a trial** (user: "lets get it running so I
        can test it. If it turns out to be to difficult to manage we will
        ditch it."): `lightingDev/renderSub_flow.py` (all Flow calls; ditch =
        delete it + the Render on menu item), test
        `test_renderSubFlow_mayapy.py` (cloud stood in). Render on > Flow
        Render (cloud); greyed with the reason where Flow isn't in the Maya.
        Flow renders ranges only: Lighting check -> 5 evenly spaced frames
        (can be a frame off the end), Every Nth drops renderSub's added end
        frame, frame lists refused unless evenly spaced. (Tracking and
        download below SUPERSEDED 2026-11-18: see "simpler Flow flow".) Downloads go to
        `<version>\flow_download\` and are renamed into the version; leftovers
        (AOVs, anything unexpected) stay there, listed in render.json
        `flow.unused_downloads`. The cloud id is saved in render.json, so the
        window picks the job up after Maya restarts. Cancel after upload
        can't stop the cloud job (no API): it opens Flow's Job Monitor.
      - [ ] **User hand test:** Maya 2027, reinstall mpPipe, SEQ010_160,
        renderSub > Render on: Flow Render (cloud) > Lighting check at 25% >
        Render. Report: quota line (education hours?), upload/queued/running
        status, frames back in the version folder and correct (references,
        caches, textures), what's left in `flow_download\`, close Maya
        mid-render and reopen renderSub (does it pick it up and download?).
        Unverified until then: `flowRenderSubmit -download` behaviour and
        Flow's download folder layout.
- [ ] **Flow Render first real job, 2026-11-13** (end of day): SEQ010_160
      `e131988_render_v004`, whole shot 1001-1181. Scene export to USD done
      (~16 min, 553 MB); upload was in progress, no cloud id in render.json
      yet; quota 0 of 2400 min used, resets 2026-12-01. Next session: check
      v004 (queued/running/downloaded?), frames correct, minutes used per
      frame, what's left in `flow_download\`, and whether Maya was signed in
      with the RMIT education account. Log:
      `%TEMP%\setUP_v009_defaultRenderLayer_17388__1.log`.
      Seen in the export log: sky dome `light_shader.outputs:color` type
      mismatch (may light wrong); background export ran with
      `-proj ...assets\prop\backpack\` (wrong project: set the shot's
      project before submitting).
- [ ] **v004 cloud job FAILED (found 2026-11-13 17:00).** From
      `%LOCALAPPDATA%\Autodesk\Logs\FlowRenderMaya.log`: upload ok (one
      `403 Forbidden` at 16:12, retried with renewed URLs: likely the
      "lost connection" popup the user saw), cloud job
      `39e6ac5b-170f-49c7-bcfa-56ba23e6bbbf` (181 tasks) started 16:14:04,
      failed 16:15:50: "Task failed: Rendering failed, see log for more
      information". 0 min of quota used. `flowRenderSubmit -download` on it
      ran but found 0 outputs (no log comes down). Next: user opens Arnold >
      Flow Render > Job Monitor, clicks the failed job, reads a task log.
      Suspects: assets on D:\ / `$PIPE_SCRATCH` not uploaded (caches,
      textures), wrong `-proj` (backpack asset), sky dome type mismatch.
      Retry with a 1-frame, 25% test.
- [ ] **renderSub bug: cloud id never found.** `flowRenderQuery
      -fgeIdFromJobId` wants the plug-in's own submission id (log: "Job
      85d1ed75... submission finished"), not ExportQueueManager's job_id
      (207964c2...), so v004 sat at "uploading". Fix: get the id another way
      (try `flowRenderQuery -sceneActiveJobList`, or the submission
      callback) and test against a real job. Also check why ID_WAIT (300 s)
      didn't fail it. Leftover: `scenes\anim\e131988\setUP_v009__17388__1.mb`
      (394 MB) Flow didn't delete.
- [ ] **Flow hand tests 2026-11-18: cloud renders WORK; only renderSub's
      tracking is broken.** SEQ010_130 v002 (11 fr) and SEQ010_120 v001
      (101 fr, 1920x1080) both SUCCEEDED in the cloud, but renderSub marked
      them failed (no cloud id, even after ID_WAIT was raised to 30 min).
      `%LOCALAPPDATA%\Autodesk\Logs\FlowRenderMaya.log` shows the facts:
      - Flow AUTO-DOWNLOADS even with `job.autoDownload = False` (Arnold
        only passes the flag when True; the plug-in default is on) into
        `<shot project>\flow_render_images\<aov>\<prefix>.####.exr`, e.g.
        `beauty\SEQ010_120_e131988_render_v001.1001.exr`: renderSub's own
        names (its prefix is in the uploaded copy), AOVs in subfolders.
      - Speed: Maya's download ~4 MB/s (12 GB in ~50 min); the Job
        Monitor's zip download ~0.2-0.5 MB/s (unusable for full shots).
      - Size: 5 files a frame (beauty + denoise_albedo_noice, N_noice,
        variance, Z_noice), ~24 MB each: the noice AOVs are 80% of it.
      - CORRECTED 2026-11-18 (I first blamed Maya closing): the
        `pathmap.json` "Missing path mapping file" failure is Flow's
        **10-minute upload-link expiry**. SEQ010_120 v002 (101 fr): the
        354 MB USD took 12 min at ~0.5 MB/s, pathmap.json (uploaded last)
        got 403, Flow's retry wrongly said "already uploaded" and submitted
        without it. A Flow plug-in bug (it should renew the link): report
        to Autodesk. Workaround: keep uploads under ~250 MB (fewer frames;
        the USD grows with animated frames) or a faster connection.
      - [x] **BUILT 2026-11-18, the simpler Flow flow** (user: "Maybe all
        renderSub needs to do is send the render to the cloud"):
        `job.autoDownload = True`, `autoDownloadLocation` = the version
        folder; no cloud id, no status polling, no own download. States:
        uploading (until Arnold's queue lets the job go) -> "in the cloud"
        (waits for every beauty frame, untouched 15 s). `catch_up()` finishes
        a Flow version whenever its frames turn up later (Maya closed,
        Cancel, a Job Monitor zip saved into the version folder: unzipped,
        zip removed; frames in `<project>\flow_render_images\`: moved in).
        Warns when the export USD is over 250 MB. `api.cloud_job_id` ->
        `api.in_cloud`. Test 26/26. Old records with an `fge` id settle as
        interrupted, then catch_up picks their frames up.
      - [ ] **User hand test** of the above: a ~10-frame Flow render; frames
        should land straight in `<version>\beauty\` etc. and the version
        finish by itself. Check Flow honours `autoDownloadLocation` (if it
        still uses `flow_render_images\`, catch_up moves them anyway).
      - [?] Not done: a cloud job that fails in the cloud just never sends
        frames (renderSub can't see it; the status line points at the Job
        Monitor). A waiting cloud job blocks the next render until Cancel.
        Consider dropping the noice AOVs on cloud tests (1/5 the download).
- [?] Flow follow-ups offered, not yet agreed: delete Flow's temp .mb/.usd
      (~1 GB) when a cloud render is interrupted before upload; warn on Maya
      quit while a cloud job is still uploading; set the shot's project
      before submit. Also still open: Resume a stopped local render.
- [x] **BUILT 2026-11-19, render queue** (spec "Render queue"): renders from
      any shot at once (`api.RenderQueue`, the window's Render Queue list +
      Cancel Selected); batch renders one at a time, cloud uploads queued
      by Arnold; every Render saves the scene as its next version
      (`..._002.ma`) and renders a copy in the version folder, published to
      H and named in the ShotGrid note; Maya closing stops batch renders
      (and uploads still going) and the next Maya warns in the Script Editor
      (`renderSub_jobs.json` in Maya prefs, via `pipeEnv.install`); cloud
      renders sent before closing are watched again from any shot. Tests
      105/105 + Flow 27/27; the window itself not tested headless.
- [ ] **User hand test of the queue:** Flow render shot A; once it's in the
      cloud, open shot B, batch render it, then batch render shot C (waits).
      Check the Render Queue list, the scene versions (`_002.ma`...), C
      starting after B, A's Watch before publishing window coming up in
      another shot and publishing to A. Then close Maya mid-batch and check
      the Script Editor warning on the next start.
- [ ] Delete the test render when done with it: ShotGrid Version 13643 and
      `G:\H\NWF_SHF\...\SEQ010_140\images\lighting\e131988\e131988_render_v001`
      (watermarked, every 30th frame at 25%).

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

- [ ] **Scene vs project** (spec §4e, 2026-10-28): open a SEQ010_140 scene,
      Set Project to the shed. Check that you're offered Open / New Scene /
      Keep. Pick Keep, then check that Build and Publish show the red banner
      and ask before acting, and that "Set Project to the scene's" clears it.
      Is the banner readable on the dark theme?
- [ ] **Shot working folders** (spec §4 "Shot working folders",
      2026-10-28): h_sync applied on the T7 2026-10-28 (363 working +
      3648 Studio Library folders; first apply since 2026-10-21). Set
      Project on SEQ010_140 and
      check your `scenes\lighting\e131988\` etc. Publish Animation with
      ABC ticked and check the caches land in `cache\alembic\anim\e131988\`.
- [ ] **Asset department Tasks** (spec "Publish thumbnail borders"): run
      `python desktopDev/asset_tasks.py --project 157 --apply` (61 Tasks,
      dry run checked 2026-10-28). Until then asset publishes stay
      iterative (blue) with a "no task" warning.
- [ ] **Thumbnail borders** (spec "Publish thumbnail borders"): publish
      iterative and check the Version and Shot thumbnails are dark blue;
      approve it, publish again, check green. Does ShotGrid's own thumbnail
      from the movie ever replace ours (thumbnail goes up after the movie)?
- [?] **Build by department** (spec §4 "Build by department", DRAFT): the
      department table is drafted. Decided 2026-10-28: asset scenes get
      turntable or witness cameras (never a shot's); a light rig publish
      from Animation, Layout or FX. Leaning: textures travel in a LookDev
      shader publish (like the rig's), no Substance Painter tool. Decided:
      Animation gets caches (to compare), FX gets no rigs; witness camera =
      a review camera made in the shot (§4d); light rigs publish under the
      shot's `scenes\lighting\`; model textures come from the model's
      shaders (optional). Decided 2026-10-30: light rigs publish to
      `scenes\lighting\<login>\`; other shot publishes stay put.
- [ ] **Build: Add to list / Build into** (built 2026-10-28): Set Project
      SEQ010_140, open an anim scene (`scenes\anim\e131988\`). Build into
      should read NWF_SHF | Shot | Animation | SEQ010 | SEQ010_140; Add to
      list offers Modeling / Rigging / Environment. Pick another shot in
      Build into: its list loads, the red banner says Build won't run, the
      Maya project doesn't move, Build Shot refuses; the banner button
      goes back. Open a scene saved in another shot: refused too, with
      Set Project to the scene's. Set Project to another shot with the
      Project Tool: Build into follows. Open a rig scene: Asset | Rigging,
      the same Build button. Keys from: pick another shot, its keys listed.
- [ ] **Animation caches are ticks** (spec §4k, built 2026-11-24): in a
      shot, add your animated items for Animation, tick **ABC** and **USD**
      on the row ("Publishes as" should end "+ ABC + USD cache"), publish.
      Check the thumbnail is green in ShotGrid, and the caches are in
      `cache\alembic\anim\<login>\` and `cache\usd\anim\<login>\`. Open a
      USD cache in Gaffer or as a Maya stage: does it play, with shaders?
      Then publish with no ticks: blue, no caches.
- [ ] **Shaders on caches** (built 2026-10-28, spec "Shaders on caches"):
      republish Scout's rig (it gets `_look.ma` / `_look.json` beside it)
      and a textured model; check the look files open with only shaders
      in them. Rebuild the rig into SEQ010_140, publish Animation with
      ABC ticked (§4k), then in an Animation scene tick Scout's cache
      row (it's in the list by itself), Build: the cache sits in `scoutrig_cache_GRP` (Reference display)
      beside the rig, wearing the rig's shaders and textures. Does Scout's
      MetaHuman face come through? Does the Reference display suit
      comparing, or should it be selectable / templated?
- [ ] **Lighting build** (spec §4 "Shot working folders"): Build a shot
      for rendering: newest Final caches, camera, full environment. Comes
      with Build by department; needs the open LookDev / lights decisions.
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
      2026-10-30: now **one list per shot per department**,
      `<shot>\data\build\<department>.json` on H; the old `build_list.json`
      is read as Layout/Animation's starting list, never written again.
- [ ] Hand test the department lists: Build SEQ010_140 as Animation, switch
      Build into to Layout (a different list), back to Animation (yours
      again); look in `G:\H\NWF_SHF\maya\sequences\SEQ010\SEQ010_140\data\build\`.
- [ ] **Output formats** (built 2026-10-30, spec "Students choose what a
      final publish makes"): publish a textured model with ABC, USD, FBX,
      OBJ ticked; check `<published name>_exports\` beside the `.ma`; open
      the FBX and USDZ in Blender/Unreal and check the textures show; publish
      the asset again and check the ticks came back. Next: the Unreal and
      Houdini presets (axis / scale), as settings.
- [ ] **Republish fieldA** (2026-10-30) with the new Publish: Asset →
      Modeling → environment → fieldA. Check H gets
      `fieldA_<login>_model_v001.ma` (not `_env_`) and Build in SEQ010_160
      lists it under Modeling. Its `_env_` publishes (and shed's) stay on H,
      not listed by Build.
- [ ] Stale test: `projectDev/test_projectMatch_mayapy.py` "Build: red
      banner shown" / "Build: asks first" fail (also on 2026-10-30's
      starting code): they expect Build to ask, but since 2026-10-28 Build
      refuses. Update the test to the refusal.
- [ ] **mpModel shelf, Convert to Model** (built 2026-10-30,
      `pipeDev/modelDev/modelTool_convert.py`, staff zip only): in an
      asset scene, Build the shed environment and a textured model (both
      referenced: Build into an asset references, like a shot, since
      2026-10-30); select each top node, Convert. Check: imported, no pipe
      group, no namespace, nothing moved or frozen, sky unlocked, `locators`
      gone, environment sets kept, textures copied into the asset's
      `sourceimages\<published name>\` and loading from there; save and
      republish. Also: reopen the asset scene on another drive and check
      Build's list for the asset comes back.
      Try it in a shot scene (refused) and with a `props_grp` already in the
      scene (refused). Open: should it work on rigs too (not now: models and
      environments only)?
- [ ] **One folder layout on scratch and H** (spec §4g, built 2026-11-23,
      `test_deptFolders_mayapy.py`). 2026-11-23: user test-published every
      published asset in SEQ010_160 -- "looks good". Still to check: Build
      lists old + new versions; an older shot's references; a model publish.
      Steps: reinstall the pipe, open SEQ010_160's
      `scenes\anim\e131988\setUP_v012.ma`, publish it as Animation. Check H
      gets `SEQ010_160\scenes\anim\e131988\SEQ010_160_e131988_anim_v002.ma`
      (v002: the old v001 is in `scenes\e131988\`, which isn't written to
      any more). Then a model or environment publish lands in
      `scenes\model\e131988\`. Build the shot and check it lists the old
      and new versions; open an older shot and check its references still
      load. Project Tool Update Scratch: other people's
      `scenes\<dept>\<login>\` come across (1:1, as decided).
- [ ] **Build loads published models as USD** (spec §4h, built 2026-11-23,
      `test_buildUsd_mayapy.py`): reinstall the pipe, open a copy of
      SEQ010_120's scene, Build, tick **USD** on grassB (v003) and Build.
      Answer Yes to switching: the grassB reference goes, `grassB_USD`
      appears where `grassB:geo` was. Check it draws, renders in Arnold,
      the scene file shrinks, and it reopens on another drive. Untick USD
      and Build to switch back. Then a new scene of the shot: grassB
      should start with USD ticked.
- [ ] **mpModel shelf, USD Hierarchy + USD Names** (built 2026-11-20;
      imported-model clean-up added 2026-11-23, `modelTool_usd.py`, test
      45/45 on 2025 + 2027, windows not yet driven in the GUI): import a
      bought/downloaded model with a namespace and junk in its names
      (`grassB_TypeGrassColor03_0610_GEO`). USD Names: pick its top group,
      Name to Field, cut it down to `_TypeGrassColor03_`, check the preview
      line, Remove; Strip Namespaces with the group picked, then with nothing
      picked (materials lose theirs too; a referenced model keeps its own).
      Ctrl+Z undoes each in one step. Then Build Hierarchy, Fix All, publish
      with USD ticked and open the `.usdz`.
- [ ] **shotSub / Jiffy shot data in the project's data folder** (built
      2026-10-30, for every student + the pipe): `<project>\scenes\<rel>` ->
      `<project>\data\shotgrid\<rel>` (shotSub + Jiffy SG link, publish log)
      and `<project>\data\jiffyShotData\<rel>` (JiffyPomo tasks, summary;
      Jiffy Schedule thumbnails in `data\jiffyShotData\thumbnails`). Show
      data (prompts, notes) stays in `~\jiffyData`. Old files are copied
      across on first read. Not yet in mpToolSet / studio4AnimToolset:
      resync shotSub.py, jiffyUtils.py, jiffySettingsTab.py,
      jiffySchedule.py when releasing (shotSub also carries the 2026-10-28
      burn-in change). Hand test: open a linked shot, publish in shotSub,
      check the link survived and `data\shotgrid\...` appeared; open
      JiffyPomo in a shot with old tasks.
- [ ] Hand test the shot list: build a shot on one drive, open a scene in
      that shot on another drive (T7 / D:), check the list comes back with
      the latest keys; "-" an asset, reopen, check it stays off.
- [ ] **Model textures** (2026-10-28): publish a textured model (a
      Painter export in sourceimages, UDIMs if you have them) and an
      untextured one. Check the textures land in
      `<asset>\sourceimages\e131988\<published name>\` on H, then Build the
      model into a shot on another drive and check they show.
- [x] Publish failure popup (2026-10-28): the red PUBLISH FAILED window
      checked by hand 2026-10-30 (RV not signed in).
- [ ] Publish popup additions (2026-10-30): with RV renamed or missing,
      publish and check you get the amber "PUBLISHED, BUT CHECK THIS" window
      for the movie warning. Unexpected (non-pipe) errors now end with
      "send it to your teacher"; you'll only see that when something
      genuinely breaks.
- [ ] Model/rig/lookDev folders (2026-10-28, spec "Asset working folders"):
      run h_sync on the T7 to add them to existing assets; Set Project an
      asset and check scenes\model|rig|lookDev\e131988 are made; Save Here a
      model scene; publish it and check it lands in scenes\e131988.
- [x] ~~Import into Asset (2026-10-28)~~: replaced 2026-10-30, Build into
      an asset references like a shot; Convert to Model makes it editable
      (see the mpModel item above).
- [?] MetaHuman model publish (2026-10-28): the plain model publish drags
      the original meshes in through the `*_pgcombined` face sets (Scout
      model v001 has the model twice) and those sets must be kept. Needs its
      own publish: how to detect it, what it keeps, where it goes next, name.
- [ ] **Send to Gaffer** (built 2026-11-24, spec §4j): in a shot scene saved
      in `scenes\lighting\<login>`, select a character, a light and the
      camera, press Gaffer on mpLighting. First time: locate the Arnold SDK
      (get 7.5.2.0 to match MtoA). Gaffer opens on the new `.gfr`; check the
      shaders, light and animation, and render. Change something in Maya,
      send again, Carry On: Gaffer isn't opened twice; press Reload on
      fromMaya. Start Again: a new `_v002.gfr`.
- [ ] **Gaffer bundle**: build mpPipe (with Gaffer), on another machine drag
      `gaffer\install.py` in: unzips to Documents\maya\gaffer, desktop
      shortcut works; `uninstall.py` removes it but leaves film files.
- [ ] **Gaffer renders in Scout** (OPEN, user 2026-11-24): a Gaffer
      dispatcher that hands renders to Scout's render service.
- [ ] Add `gaffer\` to h_sync's film structure (like `substancePainter\`).
- [ ] **Set Project Cancel** (built 2026-11-24, spec §4e): with a shot
      scene open, Set Project an asset and press Cancel on "Switch scene?".
      The Maya project, Studio Library and the scene stay as they were.
      Try Cancel on the unsaved-changes question too.
- [ ] **Publish versions up** (built 2026-11-24, spec renderSub "Publish
      does the same"): change your environment scene and press Publish. The
      question names the next file (e.g. `_004.ma`); Version Up and Publish
      saves it and you carry on in it. Publish again with no changes: no
      question, same file. Try Save Over once too.
- [ ] **MetaHuman face board not rendering** (built 2026-11-24, spec
      "Rig publish group + DNA"): republish Scout's rig, Build it into a
      shot and do a test render (renderSub). The face board shouldn't show;
      it should still show in the viewport and its sliders should still
      pick. The publish summary says how many meshes were set.
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
- [ ] **Unkeyed settings through a clean build** (spec §4 item 7,
      2026-10-28): reinstall the tools, republish SEQ010_140's animation
      (the old publish has no settings, and its AnimLayer1 arms were missed),
      then clean-build it. Scout's clavicles and FK arms should match the
      layered scene (baked, a key every frame). The character
      should be in camera with its master control unkeyed, and any space
      switches as they were. Also try a prop placed in the shot with no
      keys at all. Worth a look on a MetaHuman rig: how big the map gets
      and how long Build takes to set it.
- [ ] **One movie for camera + animation** (spec §4 item 1, 2026-10-28):
      tick the camera and a character for Animation and publish. You should
      get one review, one movie and one ShotGrid Version, with the
      Status line showing "vNNN (login), camera vNNN". On H: the camera's
      three files plus the anim files.
- [ ] **Scratch on a different drive** (spec §3i, 2026-10-22): copy a built
      shot's scratch film folder (shot + `maya\publish\`) to another drive
      letter, e.g. a USB stick as `E:\`. With the saved scratch setting
      still pointing at the old drive, open the shot from `E:\` and check:
      references, rig textures, MetaHuman DNA (rig logic runs) and the sky
      image plane all load from `E:\`; Build, Publish and the Project Tool
      each say "Scratch drive set to E:\". Then delete `E:\...\maya\publish\`
      and check Build/Repair pulls the shot's versions back from H.
- [x] **Unpublished textures on another drive**: CLOSED 2026-10-30. Left
      to the artist, like wip (item 0). Texturing happens off pipe
      (Substance, Photoshop). To publish textures, load them onto the model
      in Maya and publish from Maya; the publish finds them through the
      shaders and copies them to H. A missing texture already stops the
      publish and names the node.
- [ ] **Type and Item dropdowns, caches for Lighting** (spec §4l,
      2026-11-25): on SEQ010_040, publish Animation with ABC, USD and FBX
      ticked. Then in a Lighting scene on SEQ010_120, go to Add to list and
      pick Shot | Animation | SEQ010 | SEQ010_040. Check that Type offers
      Camera and Cache, and that Item shows `scout_ABC`, `scout_USD` and
      `scout_FBX`. Add and Build each one:
      - the ABC should come in as a reference wearing the LookDev look;
      - the USD should come in as a stage that plays and renders with its
        Arnold shaders;
      - the FBX should come in as a reference with its skeleton, posed
        correctly on the last frame.
      Also open the FBX in Unreal or Blender to check the skin and joints
      come through. And: is "every department builds everything" right
      once tested?

## 2. Decisions waiting on you

- [?] **Rollback undone by the default button** (review #4). Shot A is
      rolled back with "Only this shot", then updating shot B offers
      "Every shot" as the default (Enter) and re-updates A. Either make
      "Only this shot" the default, or remember rolled-back shots in the
      manifest and leave them unticked.
- [x] **Whole-scene rig publish** (review #6): DECIDED + BUILT 2026-10-30.
      The rigger selects the rig's top group and adds it; only what's inside
      that group is published (its shaders and textures come with the meshes
      in it), and anything outside stays behind. Nothing selected or two top
      groups is refused (`check_rig_selection`), and so is Whole Scene on a
      Rigging row. Hand test: add a Rigging row with nothing selected (it should
      be refused), then with the rig's top group selected (published, with a
      stray light left out).
- [x] **Environment cache in shots** (spec §4c): CLOSED 2026-10-30. The
      one-frame `.abc` is only for export to other software (e.g. Unreal),
      never used in shots.
- [?] Follow-on: should Build stop copying that `.abc` into scratch
      (`SIDE_FILES` in `buildTool_api.py`), since shots never use it?
- [?] **MetaHuman model publish** and **rollback default**: to discuss
      later (2026-10-30).
- [?] **Four MetaHuman DNA defaults**: folder, refuse if missing, warn on
      mismatch, full copy per version. These were my suggestions and were
      never confirmed one by one.
- [?] **Shot publish "not in v0" list**: explained 2026-10-15 but never
      explicitly confirmed.
- [?] **What decides the latest shot publish**: still open, doesn't block
      v0.
- [?] **Shot publishes pile up on H** (raised 2026-11-23, don't rush it;
      decide before March 2027). Every Layout/Animation publish writes, flat
      into `scenes\<dept>\<login>\`: the full shot `.ma`, a keys `.ma` + map
      `.json` per animated asset, a map `.json` per static asset with
      settings, and the camera files. SEQ010_160 v002 = 9 files; ~30
      publishes = a few hundred files in one folder. Nothing cleans up.
      The per-asset files are needed: Build's Keys column puts one asset's
      keys back on that asset, from any version (spec §4 item 7, DECIDED
      2026-10-23). Options (any mix):
      - **A. One keys file per publish:** `<shot>_<login>_anim_v002_keys.ma`
        + `_keys.json` holding every asset, grouped per asset; Build imports
        only the picked asset's curves. ~5 files a publish, Keys column
        unchanged.
      - **B. Version folders:** `scenes\anim\e131988\v002\` holds everything
        from that publish; easy to browse, archive or clear old versions.
        Touches Build, textures path, rig reference paths (§4a), Studio
        Library backups.
      - **C. A clean-up rule** later (e.g. keep the latest N + any version a
        later stage uses), easier on top of B.
      Suggestion: A + B as one spec change and one build; old flat files
      still read (like §4g). Caches stay one `.abc` per asset (final only).
      To do when decided:
      - [ ] Pick A / B / C; write it into the spec (§4g / §4 item 7)
      - [ ] Build it + tests; Build reads old flat + new layout
      - [ ] Hand test: publish SEQ010_160, Build it, pick keys per asset
- [ ] **SEQ010_160 `anim_v002.ma` is 537 MB** (v001: 84 MB). It holds
      3,740 meshes saved straight into the scene, not referenced: 1,870
      `grassTuft`, 1,425 under `grassBRNfosterParent` (orphaned from the
      grassB reference; likely names inside grassB changed after the shot
      referenced it, e.g. Renumber; not confirmed) and 354 `tuft_`. It comes
      from the working scene `setUP_v012`; every publish of it copies the
      lot. Look into it before the pile-up decision above: size, not file
      count, is what fills H.

## 3. Bugs and risks found in the review

- [x] Build lost its "Nothing has been published" message (#1), fixed.
- [x] Shapes in `cache_SET` made shots cache the whole rig (#2), fixed.
- [x] A group and a mesh inside it in `cache_SET` broke the Alembic (#3),
      now refused at rig publish.
- [x] **Namespace clash on publish** (#7): FIXED 2026-10-30. Stripping
      namespaces could make Maya silently rename a node (`head_rl4` →
      `head_rl5`). Publish now refuses before ShotGrid or the playblast,
      lists each clash, and leaves the scene as it was
      (`check_namespace_clashes`, `test_namespaceClash_mayapy.py`).
- [x] **MetaHuman face controls in a selection publish** (#8): FIXED
      2026-10-30. If `headGui_grp` isn't inside the published group, the
      Rigging row is refused (when added and at Publish) and the message
      names `headGui_grp`, instead of `face_controls_SET` coming out short.
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
- [x] ~~Confirm the **house-on-locator** workflow~~: dropped 2026-11-12.
      Publish no longer makes `_LOC` locators (spec §4c, 2026-11-12); an
      artist who wants one adds their own, and it publishes as is.
- [ ] Hand test in Maya: an environment with several groups (and groups
      inside groups) in `building_SET` publishes, and an older publish
      with a `locators` group still converts cleanly (Model).
- [x] Hand test in Maya: fieldA `set_002` (grass imported twice) hits a
      namespace clash, **Fix Namespace Clashes** clears it, and the
      environment publishes (spec 2026-11-12, namespaces). Done 2026-11-12.
- [ ] Hand test in Maya: Build > Add to list > **Shot** > Layout >
      SEQ010 > SEQ010_160 > + > Build into the fieldA environment. The
      camera arrives as `camera1` in `SEQ010_160_cam_GRP`, timeline set to
      the shot's range, the viewport shortcut finds it. Then commit
      (uncommitted 2026-11-12): Build work on a `pipe/` branch from `main`;
      `PIPE_RULES.md` item 2 + `run_tests.py` (skips userSetup) on
      `setup/contributors`.

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

- [ ] **Before the move to Maya 2027** (checked 2026-10-28, 2027 installed
      on this machine; pipe tests all pass under it):
      - Studio Library 2.20.2 won't import in 2027 (bundled `six` 1.12 vs
        Python 3.13). Update it in both toolsets (newer release, or a
        current `six`).
      - 2027 builds needed: mGear (Scout's rig; `mGear.mod` stops at 2026),
        MetaHuman for Maya (v1.2.50 lists 2023-2026), ngSkinTools2,
        DuBlast, MetaHumanExtraTools, Fab bridge.
      - Students rerun the installers in 2027 (shelves/prefs are per
        version; scripts are shared, so tools must keep working in both).
      - Decide: switch everyone at once, or allow a mixed year (Build now
        warns on files from a newer Maya).
      - If docked windows misbehave: Autodesk known issue MAYA-142238
        (Qt AA_DontCreateNativeWidgetSiblings in userSetup.py).

- [?] **PARKED 2026-10-26: things made in the shot + reusing them in
      another shot** (spec §4d). Your idea of a shot group with
      rig / model / lights / reference / cache / fx groups and sets, a
      custom one-shot rig, and publishing animation to another shot.
      Open questions are listed in §4d; come back to it later.

- [ ] **Build warning** when a rig's `pipe_plugins` aren't loaded. When
      building it, make the stamp list only the plug-ins used inside the
      selected rig group. Today it lists the whole scene's, so a stray
      Arnold light would give a false "needs mtoa" warning. Nothing reads
      the stamp until then, and it never affects Unreal or Houdini
      (2026-10-30).
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
