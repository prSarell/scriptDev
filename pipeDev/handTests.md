# Pipe hand tests (2026-11-03)

Everything here passes its automated (mayapy) tests but has never been
tried by hand in Maya. Work through it on the T7, in order. Each test has
an ID: if something goes wrong, send me the **ID**, **what you saw**, and
the **Script Editor output** (or a screenshot).

Tick `[x]` when it passes, `[!]` when it fails.

Your login folder below is `e131988`. Test shot: **SEQ010_140**.

---

## A. Setup (do first)

- [ ] **A1 Rebuild and install.** Run `mayapy pipeDev/pipelineInstaller/build_zip.py`, drag `install.py` from the new zip into Maya.
      Check: the mpPipe, mpLayout and mpModel shelves appear, with no errors in the Script Editor.
- [ ] **A2 Asset Tasks.** Run `python desktopDev/asset_tasks.py --project 157 --apply`.
      Check: the NWF assets in ShotGrid now have Model / Rig / etc. Tasks.
- [ ] **A3 Folders.** Run h_sync on the T7.
      Check: assets have `scenes\model`, `scenes\rig` and `scenes\lookDev`; shots have `scenes\layout`, `scenes\anim`, `scenes\fx` and `scenes\lighting`.

## B. Project Tool

- [ ] **B1 Set Project.** Set Project to SEQ010_140.
      Check: File > Open starts in that project, it's in Recent Projects, and it's still set after you restart Maya.
- [ ] **B2 Working folders.** After B1, check `scenes\anim\e131988\` (and the other departments' folders) exist. Then do the same for an asset.
- [ ] **B3 Scene vs project.** Open a SEQ010_140 scene, then Set Project to the shed.
      Check: you're offered Open / New Scene / Keep. Pick Keep, then check:
      - Build and Publish show a red banner, and it's readable on the dark theme.
      - Both refuse to run.
      - "Set Project to the scene's" clears the banner.
- [ ] **B4 Studio Library.** Set Project on a shot.
      Check: there are two libraries, "NWF_SHF Show" and "NWF_SHF SEQ010_140 (mine)", and the shot one opens by default. If Studio Library was already open, does it need reopening?

## C. Modeling publish

- [ ] **C1 Textured model.** Publish a model with textures (UDIMs if you have them).
      Check: the textures land in `<asset>\sourceimages\e131988\<published name>\` on H.
- [ ] **C2 Untextured model.** Publish a model with no textures.
      Check: it publishes with no texture errors.
- [ ] **C3 Output formats.** Tick ABC, USD, FBX and OBJ and publish.
      Check:
      - A `<published name>_exports\` folder sits beside the `.ma`.
      - The FBX and USDZ open in Blender or Unreal with their textures.
      - The ticks come back the next time you publish that asset.
- [ ] **C4 Thumbnail colour.** Make an iterative publish: its thumbnail is dark blue. Approve it in ShotGrid, publish again: the thumbnail is green.
- [ ] **C5 fieldA.** Publish Asset → Modeling → environment → fieldA.
      Check: H gets `fieldA_e131988_model_v001.ma` (not `_env_`), and Build in SEQ010_160 lists it under Modeling.
- [ ] **C6 Watch, then cancel.** Publish, watch the movie in RV, then press Cancel.
      Check: the window comes to the front over Maya, and nothing is left on H, ShotGrid or scratch.
- [ ] **C7 No RV.** Temporarily rename RV, then publish.
      Check: you get the amber "PUBLISHED, BUT CHECK THIS" window.

## D. Rigging

- [ ] **D1 Rig selection.** Add a Rigging row with nothing selected: it's refused. Select the rig's top group and add it again, with a stray light outside the group.
      Check: it publishes, and the light is left out.
- [ ] **D2 Look files.** Republish Scout's rig.
      Check: `_look.ma` and `_look.json` sit beside it, and the look file holds only shaders.
- [ ] **D3 Selecting controls.** Build Scout v004 into a shot.
      Check: can you click-select the controls? Then try again with `selectPref -containerCentricSelection` on.

## E. Build

- [ ] **E1 Build into.** In SEQ010_140, open an anim scene.
      Check: Build into reads NWF_SHF | Shot | Animation | SEQ010 | SEQ010_140.
      Then pick another shot in Build into:
      - that shot's list loads;
      - a red banner shows and Build Shot refuses;
      - the banner's button takes you back.
- [ ] **E2 Following the project.** Change the project with the Project Tool.
      Check: Build into follows it. Then open a rig scene: Build shows Asset | Rigging.
- [ ] **E3 Department lists.** Build SEQ010_140 as Animation. Switch to Layout (a different list), then back to Animation (your list again).
      Check: `G:\H\NWF_SHF\maya\sequences\SEQ010\SEQ010_140\data\build\` holds a file per department.
- [ ] **E4 Remove and filter.** Try Remove from List and the Show: department filter.
- [ ] **E5 List on another drive.** Build a shot on the T7, then open a scene from that shot on D:.
      Check: the list comes back with the latest keys. "-" an asset, reopen the scene: it stays off.
- [ ] **E6 Rig in two shots.** Build Scout into two shots, then update the rig in one of them. Try "Every shot", then "Only this shot", and reopen both.
      Check: each shot has the rig version you expect.

## F. Animation

- [ ] **F1 One movie.** Tick the camera and a character for Animation and publish.
      Check: you get one movie and one ShotGrid Version, the status says "vNNN (login), camera vNNN", and the camera's three files are on H.
- [ ] **F2 Clean build.** Republish SEQ010_140's animation, then build it into a clean scene.
      Check:
      - Scout's clavicles and FK arms match the layered scene.
      - The character is in camera, and space switches are as they were.
      - A prop with no keys at all comes through.
- [ ] **F3 Keys on another drive.** Publish Animation on one drive. On another drive, in a fresh scene, add Scout's rig and Build.
      Check: the keys are on the same frames. Roll back to a layout publish, then take keys from another shot.
- [ ] **F4 Caches.** Publish Animation with Final approved. In an Animation scene, tick Scout's cache row and Build.
      Check:
      - The cache sits in `scoutrig_cache_GRP` with the rig's shaders and textures.
      - The caches landed in `cache\alembic\e131988\`.
      - Does the MetaHuman face come through?
      - Is the Reference display right for comparing?
- [ ] **F5 Shot publish.** Make a real publish on EAP_010_010 with an Approved Version on its Layout / Blocking / Final tasks.

## G. Changing drives

- [ ] **G1 Scratch on another drive.** Copy a built shot (the shot folder plus `maya\publish\`) to a USB stick (e.g. `E:\`) and open it from there.
      Check:
      - References, rig textures, the MetaHuman face and the sky image all load from `E:\`.
      - Build, Publish and the Project Tool each say "Scratch drive set to E:\".
      - After you delete `E:\...\maya\publish\`, Repair pulls the files back from H.
- [ ] **G2 MetaHuman face.** Open a Scout shot from a different drive letter.
      Check: the face moves.
- [ ] **G3 Sky.** In a shot with the shed built into it, check the sky image plane shows its picture.

## H. Convert to Model (mpModel shelf)

- [ ] **H1 Convert.** In an asset scene, Build the shed and a textured model, select each top node, and Convert.
      Check:
      - It's imported, with no pipe group, no namespace, and nothing moved or frozen.
      - The `locators` group is gone, but the environment sets are kept.
      - The textures are copied into the asset's `sourceimages\` and load from there.
      - You can save and republish.
- [ ] **H2 Refused.** Try Convert in a shot scene, then in a scene that already has `props_grp`.
      Check: both are refused.

## I. shotSub and Jiffy data

- [ ] **I1** Open a shot that's linked to ShotGrid and publish in shotSub.
      Check: the link survives and `data\shotgrid\...` appears. Open JiffyPomo in a shot with old tasks: are they still there?

## J. Real student login

- [ ] **J1** At RMIT, log in with a real student login (not `scout`) and run through B1, C1, E1 and F1.
      Check: the work lands in that login's folders. Also time how long Set Project takes to restore Studio Library.

## K. Storage targets: SharePoint and a server

Point the pipe's **H setting** at each target in turn. Copy a small test
film there first (e.g. NWF_SHF with SEQ010_140 and Scout). Do K1–K6 on
**SharePoint** and again on the **server**. Note the target in each
report.

- SharePoint: a document library synced with OneDrive, e.g. `C:\Users\<you>\<Org>\<Site> - Documents\H`. Turn **"Always keep on this device"** on for the H folder, then try once with it off.
- Server: a share, once as a **UNC path** (`\\server\share\H`) and once as a **mapped drive letter**.

- [ ] **K1 Set Project and Build.** Do B1, then E1.
      Check: the asset list loads, Build works, and you note how long Set Project and Build take.
- [ ] **K2 Publish.** Make a model publish (C1).
      Check:
      - The file is on H and read-only (on SharePoint: after it has synced).
      - It shows in Build on a second machine.
- [ ] **K3 Big pull.** Build Scout's rig into a shot on an empty scratch drive.
      Check: the textures and MetaHuman DNA all arrive and the face moves. Note how long it takes. On SharePoint, also try with "Always keep on this device" off (online-only files).
- [ ] **K4 Same version number.** Two people publish the same asset at the same moment, from two machines.
      Check: do they both get the same `v###`? (This is the risk on SharePoint, where syncing lags.)
- [ ] **K5 Newest version.** Make two publishes a minute apart.
      Check: Build shows the newer one as newest on both machines.
- [ ] **K6 Studio Library.** Do B4, save a pose, then Set Project on a second machine.
      Check: the pose is there, and the library isn't corrupted.

---

## After the ShotGrid move (new site, ~2 weeks)

A short check once the new site is live. Point `pipeline.json` and the connection settings at it first.

- [ ] **S1** Project Tool lists your project (you're assigned to it).
- [ ] **S2** Publish a model: its Version appears on the right Asset, linked to its Task.
- [ ] **S3** Approve it, publish again: the thumbnail is green (Final).
- [ ] **S4** Make an Animation publish on a shot: its Version appears on the Shot.
