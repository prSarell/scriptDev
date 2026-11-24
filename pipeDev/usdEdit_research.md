# USD Edit (mpModel shelf): research and proposal

Status: **RESEARCH + PROPOSAL, nothing built, nothing decided.** 2026-11-24.

The user (2026-11-24): "one of the key features of USD is that I can edit a
shot or an asset and pass that from the shot back to the asset and vice
versa. Managing which object and the layer inside the USD being edited is
pretty tricky. I would like to add an edit feature in our USD hierarchy tool
on the mpModeling shelf ... select a model on screen or in the outliner and
hit the edit button, move it to wherever, and save it ... support USD's
natural workflows, but also simplify this process for the students."

## 1. How USD does this (the natural workflow)

- A shot is a **stack of layers**: the shot's root layer sublayers one layer
  per department (layout, animation, lighting...), stronger on top. The
  layout layer **references** the assets.
- An edit is an **opinion** written into one layer. Moving the shed in a
  shot writes an `over` with the new transform into the shot's layout
  layer; the asset's own files don't change. Every shot can place it
  differently.
- Passing an edit **back to the asset** means writing that same opinion into
  one of the asset's own layers, at the asset's own path
  (`/hillShed_model_GRP/geo/...`, not the shot's `/set/hillShed/geo/...`).
  Every shot that uses the asset then gets it.
- **Asset to shot** needs nothing special: a shot references the asset, so a
  new asset version flows in, and the shot's own overrides stay on top as
  long as prim paths don't change (which is what the USD Names
  convention protects).
- What makes this "tricky" in Maya: everything you do goes to the **edit
  target** layer, and it's easy to edit the wrong one (or a read-only
  published file).

## 2. What Maya 2027 gives us (checked on this machine)

Maya **2027.2**, mayaUsd **0.37.0**.

| Tool | What it is | Use for us |
|---|---|---|
| Edit target (`mayaUsdEditTarget`, Layer Editor) | Which layer edits go to. Move tool, channel box, attribute editor all write there. | Shot edits: set it to the shot's layer. Enough on its own. |
| **Edit Forwarding** (`AdskUsdEditForward`, new in 0.37) | Rules that move edits from a source layer (default the session layer) to a target layer, **remapping the path through references** (`auto_resolve_site`). Python API; minimal UI in 0.37. | Asset edits from inside a shot. |
| Edit routers (`mayaUsd.lib.registerEditRouter`) | Older per-operation routing (visibility, parent, duplicate...). Manipulator moves bypass them (maya-usd discussion #3254). | Not needed. |
| Edit as Maya Data / Merge to USD | Pull a prim into Maya nodes, edit with any Maya tool, push back to the edit target. | Later, for edits beyond transforms/visibility. |
| maya-usd **0.38** (Maya **2027.3**) | Adds an "Edit Forward mode" and Edit Forwarding window in the Layer Editor, and a Composition Editor (see and reorder opinions across layers). | Nice to have; our tool can drive the 0.37 API without it. |

**Headless test (mayapy, 2027.2):** asset = edit layer over a published
version; shot = root → layout layer → reference to the asset at
`/set/hillShed`. A move written to the session layer, then forwarded:

- rule "target layer `SEQ010_160_layout`": the move landed in the shot's
  layout layer at `/set/hillShed/geo/render/hillShed_shed_GEO`; session
  layer emptied; composed result unchanged.
- rule "target layer `hillShed_edit`, auto resolve site": the move landed in
  the **asset's** edit layer at
  `/hillShed_model_GRP/geo/render/hillShed_shed_GEO`. The path was
  remapped through the reference automatically.

Rules are stored in a layer's custom data
(`RuleDef.WriteRuleSetToLayerCustomData`), read by `StageRuleProvider`, and
run on demand (`Forwarder.Execute`) or continuously. **Not yet tested in
the Maya UI**: that the Move tool writes to the session layer when it's the
edit target, and continuous forwarding through Maya's undo.

## 3. What the pipe has today, and what's missing

- Build loads a model's published `.usd` **directly** as the stage
  (§4h). There is no shot layer, so an edit could only go into the
  published file (read-only) or Maya's session layer (lost on save
  unless Maya saves it into the `.ma`).
- §4f already decided where shot layers live: a fixed `<shot>\usd\` folder
  that Build writes, linked by relative paths.
- Pipe rules that shape this: H holds only publishes (rule 3); Build in,
  Publish out (4); the model's source of truth is the Modeling `.ma` plus
  its `.usd` export.

## 4. Proposal (for discussion)

**One Edit button, two targets.** Select the object (viewport or Outliner)
→ **Edit** → a small window: "Edit for: (•) this shot  ( ) the asset
(all shots)" → move it → **Save**.

1. **This shot.** The tool sets the edit target to the shot's layer for that
   asset (`<shot>\usd\<dept>.usda`, made by Build) and saves that layer on
   Save. Plain USD, no forwarding needed. Each asset in a shot gets its
   own small layer or one shared layout layer (decide).
2. **The asset (all shots).** Edits go to the session layer, and on Save
   the tool forwards them with an `auto_resolve_site` rule into an
   **asset edit layer** on scratch, e.g.
   `assets\<type>\<asset>\usd\<login>\<asset>_edit.usda`. That layer is
   not a publish. It reaches the asset in one of two ways (decide):
   - **(a) Through the model scene (recommended).** In the asset's Maya
     scene, an "Apply USD edits" button moves the Maya nodes to match the
     edit layer (paths map 1:1: `geo_USD|render|...` ↔ `/<asset>_model_GRP/geo/render/...`),
     then the student publishes as normal. `.ma` and `.usd` stay in
     step; H still only gets publishes.
   - (b) Publish the edit layer itself as a new asset USD version. Faster,
     but the `.ma` falls behind the `.usd`.
3. **What a student sees.** Which layer they're editing is shown in the
   window (shot / asset, in colour, like the red `geo_USD` cue), not in
   the Layer Editor. Edits outside the tool keep working the normal USD
   way; the tool refuses to make a published file the edit target.

## 5. Decisions needed

1. Order: shot edits first (needs Build to write a shot layer, §4f) or the
   asset path first?
2. Shot layer: one per department (`layout.usda`, the USD convention) or one
   per asset per shot?
3. Asset edits: route (a) through the model scene, or (b) publish the edit
   layer?
4. What can be edited at first: transforms only, or visibility too, or more
   (materials, variants)?
5. Upgrade the machines to Maya 2027.3 (maya-usd 0.38) for the Edit Forward
   UI and Composition Editor, or stay on 2027.2 and drive the API?
6. Staff trial first (as §4h), students from March 2027?

## Sources

- maya-usd releases (0.37.0 introduces Edit Forwarding, 0.38.0 adds the
  Layer Editor UI): https://github.com/autodesk/maya-usd/releases
- Edit routing: https://help.autodesk.com/cloudhelp/ENU/Maya-USD/files/USD-for-Maya/USD-Layer-Editor/GUID-A0349D7B-3AD6-4FEB-839E-7A002A9E91A6.html
- Manipulators bypass edit routers: https://github.com/Autodesk/maya-usd/discussions/3254
- Edit as Maya Data / Merge to USD: https://help.autodesk.com/cloudhelp/2026/ENU/Maya-USD/files/USD-for-Maya/Get-Started-with-USD-in-Maya/GUID-C1C08BA5-24EA-44FF-9497-71E0A6843744.html
- Shot layers per department (Houdini Solaris): https://www.sidefx.com/docs/houdini/solaris/tutorial_4.html
- USD composition (Siggraph 2019): https://openusd.org/files/Siggraph2019_USD%20Composition.pdf
- Local headers: `C:\Program Files\Autodesk\MayaUSD\Maya2027\0.37.0\mayausd\MayaUSD\include\AdskUsdEditForward\`
