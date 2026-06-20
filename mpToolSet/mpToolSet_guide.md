# mpToolSet — Tool Guide

## Installation

1. Drag `install.py` onto the Maya viewport
2. Both shelves (mpRig, mpAnim) are built automatically
3. To uninstall, drag `uninstall.py` onto the viewport

---

## mpRig Shelf

### Ribbon Spine (WIP Testing)

Builds an IK spline ribbon spine rig from a hand-drawn CV curve.

- Draw a CV curve along the spine path
- Select the curve and open the tool
- Set a prefix name (e.g. `spine`, `tail`, `neck`)
- Click Build
- The tool creates FK joints at each CV, an IK spline solver, a NURBS ribbon surface, and follicle-driven skeleton joints

### Follicle Rig (WIP Testing)

Scatters follicle-driven joints across NURBS or polygon surfaces for surface-riding controls.

- **NURBS Grid tab:** select a NURBS surface, set U/V count, click Create Follicles
- **Poly Vertices tab:** select vertices on a polygon mesh, click Create Follicles
- Select created follicles or their joints, click Add Controllers to generate control curves
- Joints automatically track the surface as it deforms

### MH Blendshape Baker (WIP Testing)

Bakes a Metahuman RigLogic face rig into a portable blendshape rig that works without Epic's plugins.

- Open a scene with the Metahuman face rig loaded
- Set the namespace (`:` for root)
- Auto-detect or manually set the face mesh and teeth mesh
- **Phase 1 — Single Shapes:** poses each control channel to its extreme, captures blendshape targets, and wires weights back via SDK. Set in-between count if needed
- **Phase 2 — Corrective Shapes:** searches control-pair combinations for residual deformation errors, bakes corrective targets. Set a vertex threshold. Can run overnight

### MH Rig Recycle (WIP Testing)

Strips the Metahuman plugin dependency from a baked face rig so it opens cleanly in vanilla Maya.

- Open the scene with the baked blendshape rig
- Set namespace and face mesh (auto-detected)
- Preview Comparison — templates the original RL mesh to wireframe so both rigs respond to the faceboard side by side
- Delete Original Face Meshes — removes all RigLogic-driven meshes once the comparison looks good
- Remove RigLogic Nodes — deletes embeddedNodeRL4 and dnaFileNode plugin nodes
- Delete Face Joints — removes FACIAL_ joints (keeps eyes, head, neck, body)
- Export Standalone Scene — saves a clean .ma with no plugin dependencies
- Delete Bake Targets — removes editable target meshes (irreversible, only after final QA)

### MH DNA Repair (WIP Testing)

Fixes a broken Metahuman DNA file path when the face rig stops evaluating after file relocation.

- Open the tool — it auto-detects the embeddedNodeRL4 or dnaFileNode
- The current DNA path is displayed
- Click Browse to locate the correct `.dna` file on disk
- Click Apply to update the path and restore the rig

### MH Body Clean (WIP Testing)

Cleans up a Metahuman body scene by removing Unreal-specific elements and assigning base colour textures.

- Open a scene with the Metahuman body
- **LODs section:** check which LODs to keep (LOD 0 by default), click Delete Unchecked LODs
- **Lights section:** click Delete Unreal Lights to remove imported Unreal light rigs
- **Textures section:** browse to a maps folder, click Scan to auto-detect head/eyes/teeth/body textures, click Apply Textures to assign them

### VP Shader (WIP Testing)

Assigns colour-coded viewport shaders to Virtual Pancakes selection sets so joint boundary edge loops are visible before sculpting.

- Open the tool — it auto-detects VP selection sets in the scene
- Review the colour key (orange = joint boundary, tan = VP region, blue = structural, grey = secondary)
- Click Apply Shaders
- Click Remove VP Shaders to revert to the original material assignments

### Double Skin Face Rig (WIP Testing)

Adds a second layer of fine surface-joint control to an existing face rig mid-production using a follicle-based two-mesh system.

- **Prep Rig:** select the face mesh, click Prep My Rig — duplicates the mesh, wraps it to the original, creates the two-mesh architecture
- **Follicles:** select faces, edges, or vertices where you want fine control, click Add Selected — each component becomes a follicle-driven joint tracking the surface
- **Build:** click Build Rig — creates the second skin cluster on the duplicate mesh. New joints start at zero weight for painting in without affecting existing weights

### Namespace Stripper (WIP Testing)

Strips namespaces, adds prefix/suffix, and supports reverting names on selected transforms and joints.

- Select objects (optionally with hierarchy)
- Click Strip Namespaces to remove all namespace prefixes
- Use Add Prefix/Suffix to batch-rename
- Click Revert to restore original names (stored on each node)

### ngSkinTools

Layer-based skin weight painting and editing. Installed automatically with mpToolSet.

### Corrective Blendshape Tool (WIP Development)

Adds corrective blendshape targets that activate at specific poses to fix deformation errors.

- **Mesh:** select the skinned mesh and load it
- **Driver Mode:** Auto detects active blendshapes or joint rotations driving the current pose. Switch to Custom to wire the corrective to a specific attribute
- Pose the rig to the problem position
- Click Add Shape — the tool duplicates the mesh for sculpting
- Sculpt the correction on the duplicate
- Click Apply — the tool computes the per-vertex skin-matrix inversion, creates the blendshape target, and wires it to the detected driver

---

## mpAnim Shelf

### multiTool (WIP Testing)

Dockable animation utilities panel that lives in the Channel Box tab area. Contains collapsible sections:

- **Snap:** select objects (driver last), click Snap. Shift+click for translate/rotate/scale options
- **Constraints:** one-click point, orient, or parent constraints. Select driven then driver last. Ctrl+click for no offset
- **Aim Rig:** builds a temporary aim rig for overlap/follow-through animation. No selection = origin, one object = snap to it, multiple = chained aim. Bake & Flip or Bake Aim when done
- **Physics:** Gravity Ball creates a bouncing ball sim from selection. Ballistics bakes a projectile arc (shift+click for presets, optional floor plane)
- **Ref Plane:** pins a reference image plane to the top-right of the active camera. Right-click to remove. Sync Frame Offset matches image sequence timing
- **Cycle Keys:** tiles selected keyframes forward, backward, or both by N reps
- **Bake:** Bake to World (one object), Bake to Object (driven then driver), Bake to Origin Space (removes constraints, optional anim layer target)
- **Learn Me Something:** random animation tip
- **Panic:** take a breath

### Playblast Manager (WIP Testing)

Creates versioned JPEG playblast sequences with frame burn-ins.

- Open the tool — output path is auto-derived from the current Maya project
- Review the output location (mirrors `scenes/` folder structure into `images/`)
- Click Playblast — creates a versioned subfolder (`v001`, `v002`, etc.)
- Burn-ins are stamped onto JPEGs: frame rate (top-left), scene name (top-centre), frame number (top-right)
- After playblast, opens the sequence in the system viewer
- Optional keep/delete workflow for reviewing takes

### Camera Preset Manager (WIP Testing)

Saves and applies named camera and viewport presets to JSON files on disk.

- Enter or load a camera name from selection
- Type a preset name (e.g. `previs_001`, `blocking_001`)
- Click Save Preset — stores camera transform, viewport mask flags, and render settings
- Select a preset from the dropdown and click Apply to restore it
- Delete or Refresh presets as needed

### Cloth Chain Sim (WIP Testing)

Builds and controls nCloth chain rigs for secondary animation (tails, ropes, dangling objects).

- Select the joint chain or curve to rig
- Build the cloth chain rig
- Adjust nCloth material presets (silk, leather, rubber, chain mail, etc.)
- Keyframe per-segment dynamic constraint strength for partial pinning
- Use the aim chain mode for twist-stable secondary motion
- Adjust nucleus settings (gravity, wind) in the tool

### Studio Library (3rd Party)

Animation pose and clip library manager. Ships bundled with mpToolSet.

### JiffyPomo (WIP Testing)

Pomodoro timer and task tracker that runs inside Maya.

- Set a focus duration and break duration
- Start the timer and work on your shot
- Use the Prompts tab for reflection questions between sessions
- Use the Notepad tab for quick notes
- View session history in the Summary tab
- Configure preferences in Settings

### JiffySchedule (WIP Testing)

Production schedule and shot tracker for managing animation assignments inside Maya.

- Add shots to the shot list with status, assignee, and deadline
- Track progress per shot
- View the schedule overview

### shortCuts (WIP Testing)

Hotkey preset manager for switching between workflow-specific hotkey sets.

- View current hotkey assignments
- Switch between named presets (e.g. animation, rigging, modelling)
- Customise bindings per preset

### Playback Tempo Tool (WIP Testing)

Keyframes variable playback speed across a shot and bakes the result into rig animation.

- A locator is created with a custom playback speed attribute
- Keyframe the speed attribute across the timeline (e.g. slow for impacts, fast for anticipation)
- Assign rigs to the tempo tool so it knows which controllers to retime
- Click Bake — the tool resamples all assigned rig animation at the variable speed and writes new keys

### MH Facial Transfer (WIP Testing)

Transfers FBX facial animation exported from Unreal back onto the Metahuman face control board in Maya.

- In Unreal: bake the face animation sequence, export as FBX (compatibility 2020, morph targets on, preview mesh on)
- In Maya: open or reference the Metahuman scene with the face control board
- Select anything on the Metahuman and click Set Current Metahuman
- Click Import FBX and browse to the exported animation file
- The tool maps the FBX morph target curves onto the matching face board controls
- Export Facial FBX to save the result for re-import into Unreal's level sequence
