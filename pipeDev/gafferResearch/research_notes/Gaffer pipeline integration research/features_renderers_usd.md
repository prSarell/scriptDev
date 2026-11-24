# Gaffer feature set for lookdev, lighting and rendering; renderer support; USD support (state at 2026-11-24)

Research date: 2026-11-24. Current releases: **Gaffer 1.7.7.0** and the maintained **1.6.21.8**, both published 2026-11-12 ([GitHub Releases API / releases page](https://github.com/GafferHQ/gaffer/releases)). 1.7.0.0 shipped 2026-08-13. Unreleased work for the next major (1.8) is already on `main`.

Main primary source: the official changelog [Changes.md on GafferHQ/gaffer main](https://github.com/GafferHQ/gaffer/blob/main/Changes.md), downloaded in full (18,935 lines). It is cited below as **[Changes.md vX]**, where vX is the release that carried the entry. Release dates come from the GitHub Releases API (`api.github.com/repos/GafferHQ/gaffer/releases/tags/<tag>`, shown on [github.com/GafferHQ/gaffer/releases](https://github.com/GafferHQ/gaffer/releases)). Node lists come from the header files in the 1.7.7.0 source tree ([include/ at tag 1.7.7.0](https://github.com/GafferHQ/gaffer/tree/1.7.7.0/include)).

Key release dates used for date stamps: 0.61.2.0 = 2022-02-02; 1.0.0.0 = 2022-07-06; 1.0.3.0 = 2022-08-26; 1.2.0.0 = 2023-02-14; 1.3.0.0 = 2023-07-13; 1.3.1.0 = 2023-08-09; 1.3.8.0 = 2023-11-28; 1.3.11.0 = 2024-01-31; 1.4.0.0 = 2024-04-15; 1.5.0.0 = 2024-10-28; 1.5.9.0 = 2025-03-27; 1.6.0.0 = 2025-08-28; 1.6.15.0 = 2026-03-27; 1.7.0.0 = 2026-08-13; 1.7.7.0 = 2026-11-12 ([releases](https://github.com/GafferHQ/gaffer/releases)).

---

## Lookdev and shading: shader networks, OSL, Arnold shaders, assignment and tweaks, editors and viewer

### Takeaway
Gaffer builds lookdev non-destructively in a node graph. You create shader nodes (ArnoldShader, OSLShader, CyclesShader, RenderManShader, USDShader), bind them to locations with ShaderAssignment and filters or set expressions, and adjust anything upstream with ShaderTweaks, AttributeTweaks and similar nodes. The Light Editor, Attribute Editor, Render Pass Editor, Scene Inspector, Set Editor and Light Linking Editor all edit through these same tweak nodes or EditScopes. The Viewer can run Arnold, Cycles or 3Delight as a live interactive renderer, and there is a shader-ball preview. Gaffer has no built-in "LookDev" turntable template and no material-library browser. These are built from generic nodes or shipped as examples.

### Cited Findings
- **Shading and assignment nodes in GafferScene (1.7.7.0):** ShaderAssignment, ShaderTweaks, ShaderTweakProxy, ShaderQuery, AttributeTweaks, AttributeQuery, CustomAttributes, StandardAttributes, OpenGLShader, GlobalShader, RenderPassShader, Set, SetFilter, PathFilter, UnionFilter, LocaliseAttributes, CopyAttributes and ShuffleAttributes. — [GafferScene headers, 1.7.7.0](https://github.com/GafferHQ/gaffer/tree/1.7.7.0/include/GafferScene)
- **GafferArnold nodes:** ArnoldShader, ArnoldAttributes, ArnoldOptions, ArnoldLight, ArnoldLightFilter, ArnoldMeshLight, ArnoldDisplacement, ArnoldAOVShader, ArnoldAtmosphere, ArnoldBackground, ArnoldCameraShaders, ArnoldColorManager, ArnoldImager and ArnoldVDB. Python nodes: ArnoldShaderBall and ArnoldTextureBake. — [GafferArnold headers](https://github.com/GafferHQ/gaffer/tree/1.7.7.0/include/GafferArnold), [python/GafferArnold](https://github.com/GafferHQ/gaffer/tree/1.7.7.0/python/GafferArnold)
- **GafferOSL nodes:** OSLShader, OSLCode (write OSL inline in the UI, with a tutorial in the docs), OSLObject (OSL applied to geometry primvars), OSLImage (OSL applied to images) and OSLLight. — [GafferOSL headers](https://github.com/GafferHQ/gaffer/tree/1.7.7.0/include/GafferOSL), [docs: TutorialUsingTheOSLCodeNode](https://github.com/GafferHQ/gaffer/tree/1.7.7.0/doc/source/WorkingWithTheNodeGraph/TutorialUsingTheOSLCodeNode)
- **OSL version:** OpenShadingLanguage 1.14.11.0 is planned for the next major release (unreleased section). — [Changes.md 1.x.x.x unreleased](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **OSL ramps (1.7.0.0):** `Pattern/FloatSpline` and `Pattern/ColorSpline` were replaced by `Pattern/FloatRamp` and `Pattern/ColorRamp`. Old scripts are updated automatically on load. — [Changes.md 1.7.0.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Shader preview:** A ShaderBall and ShaderView preview exists. From 1.2.0.0 (2023-02-14), the Viewer prefers Arnold for OSL shader previews when Arnold is available, then falls back to Cycles. — [Changes.md 1.2.0.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Interactive viewport rendering:** Arnold, Cycles and 3Delight can be used as the Viewer renderer. There are per-renderer viewer settings files (`arnoldViewerSettings.gfr`, `cyclesViewerSettings.gfr`, `3delightViewerSettings.gfr`) in startup/gui. — [startup/gui listing, 1.7.7.0](https://github.com/GafferHQ/gaffer/tree/1.7.7.0/startup/gui)
  - Cycles GPU rendering in the Viewer was added in 1.4.12.0. — [Changes.md 1.4.12.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
  - The 3Delight interactive Viewer renderer was added in 1.4.5.0. — [Changes.md 1.4.5.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
  - The unreleased line fixes macOS crashes "when using Arnold, Cycles or 3Delight as the viewport renderer". — [Changes.md unreleased](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Light Editor:** added in **0.61.2.0 (2022-02-02)**, "a new editor UI for inspecting and editing lights", in the tab next to the Graph Editor. — [Changes.md 0.61.2.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Set Editor:** added in 1.2.1.0. Sets are shown hierarchically using ":" separators. — [Changes.md 1.2.1.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Render Pass Editor:** added in **1.3.11.0 (2024-01-31)**. — [Changes.md 1.3.11.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Attribute Editor:** added in **1.5.0.0 (2024-10-28)**, "for inspecting and editing attributes". — [Changes.md 1.5.0.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Light Linking Editor:** added in **1.7.0.0 (2026-08-13)**. — [Changes.md 1.7.0.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Scene Inspector:** gained a Statistics tab in 1.7.0.0 and a PointInstancer section in 1.7.4.0. — [Changes.md 1.7.0.0, 1.7.4.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **1.7.x editor additions:**
  - Light Editor: hierarchy filter.
  - Light Editor and Render Pass Editor: "All" section.
  - Compact columns in the Light, Render Pass and Attribute editors.
  - Drag a location from the Light Editor or Attribute Editor to jump to the node that created it.
  - Light Editor: USD lights show dimmed "fallback" values for parameters that have not been authored.
  — [Changes.md 1.7.x](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **EditScope (non-destructive edit container):**
  - 1.4.0.0 (2024-04-15) added a summary of edits in the NodeEditor.
  - 1.6.0.0 (2025-08-28) added in-place editing of attributes, options and shader parameters.
  - 1.7.4.0 added "Delete Contents".
  — [Changes.md 1.4.0.0, 1.6.0.0, 1.7.4.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **USD Preview Surface translation (render time):**
  - Arnold since 1.0.3.0 (2022-08-26).
  - Cycles since 1.4.1.0.
  - 3Delight since 1.4.2.0.
  - RenderMan: PR "RenderMan UsdPreviewSurface", 2025.
  — [Changes.md 1.0.3.0, 1.4.1.0, 1.4.2.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md), [PR #6302](https://github.com/GafferHQ/gaffer/pull/6302)
- **USDShader node** (1.3.1.0, 2023-08-09): loads shaders from USD's SdrRegistry, such as `UsdPreviewSurface` and `UsdUVTexture`. — [Changes.md 1.3.1.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Arnold volume shader assignment (1.7.0.0):** `standard_volume` is now assigned via `ai:volume` rather than `ai:surface`, to match USD import and export conventions. — [Changes.md 1.7.0.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Texture baking:** ArnoldTextureBake is a node in GafferArnold. — [python/GafferArnold](https://github.com/GafferHQ/gaffer/tree/1.7.7.0/python/GafferArnold)
- **Purpose-based material assignments:** SceneReader and SceneWriter have supported them since 1.0.0.0. To render them, a ShuffleAttributes node is needed to move them to the standard shader attributes. — [Changes.md 1.0.0.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)

### Inferences
- Gaffer's lookdev model is "assign plus tweak downstream of a read". That suits a studio that reads a published model USD and layers lookdev on top without touching the published asset.
- I found no dedicated turntable or LookDev setup node. A turntable would be Camera plus Transform with an expression or animation, plus a light rig, saved as a Box or Reference that students re-use. This is inferred from the node list, which contains no LookDev or turntable node.
- No material-library browser exists. Reusable shader networks are normally Box or Reference `.grf` files, which is standard Gaffer practice. This inference is not stated in the sources above.

### Gaps
- I found no official Gaffer doc page describing a recommended lookdev workflow. The docs source tree has no lookdev or lighting tutorial, only "Assembling the Gaffer Bot", Light Linking, Camera and Spreadsheet tutorials ([doc/source](https://github.com/GafferHQ/gaffer/tree/1.7.7.0/doc/source)).
- I did not verify whether MtoA's Maya-specific shading nodes are usable in Gaffer if MtoA's plugin folder is added to `ARNOLD_PLUGIN_PATH`. These are the `mtoa_shaders` plugin nodes such as Maya file and place2dTexture translations.

---

## Lighting: lights, filters, linking, sets, passes, AOVs

### Takeaway
Gaffer has a mature lighting toolset:
- Renderer-specific lights plus renderer-agnostic USDLux lights.
- Light filters (Arnold blockers, barndoor, gobo, decay).
- Mesh lights.
- Attribute-based light linking and shadow linking.
- A Light Tool for manipulators.
- The Light Editor and the Light Linking Editor (1.7).
- First-class render passes (RenderPasses node and Render Pass Editor).
- Outputs/AOV presets per renderer.
- Multi-layer EXR from Arnold (1.6+).
- Light groups.

### Cited Findings
- **USDLight node (1.3.1.0, 2023-08-09):** defines UsdLux lights from the `USD/Light` menu. Cycles UsdLux support was added in the same release. — [Changes.md 1.3.1.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **UsdLux renderer coverage:**
  - Arnold since 1.0.3.0.
  - 3Delight added support for USD Sphere, Rect, Disk, Distant, Dome and Cylinder lights in 1.3.11.0.
  - RenderMan-specific light parameters were added to USDLight in 1.6.13.0.
  - Cycles-specific parameters were added in 1.5.7.0.
  — [Changes.md](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **USDMeshLight node (1.7.x):** adds the attributes needed to turn geometry into a USD mesh light, with Arnold, RenderMan, 3Delight and Cycles rendering. — [Changes.md 1.7.x](https://github.com/GafferHQ/gaffer/blob/main/Changes.md), [PR #7098](https://github.com/GafferHQ/gaffer/pull/7098)
- **Light filter nodes:** LightFilter, ArnoldLightFilter and RenderManLightFilter. The Light Editor has supported Arnold light blockers and barndoor, gobo and decay filters since 1.4.8.0. — [Changes.md 1.4.8.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md), [headers](https://github.com/GafferHQ/gaffer/tree/1.7.7.0/include/GafferScene)
- **Light linking (1.7.0.0):** new StandardAttributes `linkedLights:exclusions`, `shadowedLights:exclusions` and `filteredLights:exclusions`. — [Changes.md 1.7.0.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Cycles linking:** light linking was added in 1.5.12.0 and shadow linking in 1.5.14.0. — [Changes.md](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Light Linking Basics example:** updated to use USD lights and shaders so that it applies to Cycles and RenderMan as well as Arnold (1.7.x). — [Changes.md 1.7.x](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Light linking docs page:** exists at [doc/source/WorkingWithScenes/LightLinking](https://github.com/GafferHQ/gaffer/tree/1.7.7.0/doc/source/WorkingWithScenes/LightLinking).
- **LightTool:** a 3D viewer tool for manipulating lights, added in 1.3.0.0 (2023-07-13). It started with spot cone and penumbra. — [Changes.md 1.3.0.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Render passes:** RenderPasses and DeleteRenderPasses nodes were added in **1.3.8.0 (2023-11-28)**. Pass names are stored in the `renderPass:names` option and "can be used to dispatch tasks that vary based on those". Further additions:
  - Render Pass Editor (1.3.11.0).
  - ShuffleRenderPasses (1.5.10.0).
  - RenderPassWedge and RenderPassTypeAdaptor Python nodes.
  - RenderMan XPU support for the built-in render pass types (1.6.10.0).
  — [Changes.md](https://github.com/GafferHQ/gaffer/blob/main/Changes.md), [python/GafferScene](https://github.com/GafferHQ/gaffer/tree/1.7.7.0/python/GafferScene)
- **Generic render nodes (1.3.14.0):** Render and InteractiveRender nodes that render to any supported renderer, chosen with the `render:defaultRenderer` option. — [Changes.md 1.3.14.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Visible Set rendering (1.7.0.0):** InteractiveRender gained a `useVisibleSet` plug that renders only the Visible Set. — [Changes.md 1.7.0.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Multi-layer EXR (1.6.0.0):** Arnold writes all outputs with the same filename to one file, and the `layerName` parameter controls EXR channel naming. Release 1.7.3.0 added `layerPerLightGroup` on outputs, which splits an output into one layer per light group. — [Changes.md 1.6.0.0, 1.7.3.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Cryptomatte:** a Cryptomatte node exists in GafferScene. RenderMan's PxrCryptomatte material output became stable under animation in 1.7.0.0. — [headers](https://github.com/GafferHQ/gaffer/tree/1.7.7.0/include/GafferScene), [Changes.md 1.7.0.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Default output presets:** in the unreleased line they are now registered per renderer module, so they are available outside the GUI. — [Changes.md unreleased](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Colour management:**
  - The default OCIO config has been ACES Studio 1.3 since 1.3.0.0.
  - Gaffer's OCIO config is translated to Arnold's colour manager automatically (1.3.0.0 and 1.4.0.0). An ArnoldColorManager node overrides this.
  - ACES Studio 2.0 configs were added in 1.7.0.0, but "the default config is still ACES 1.3, due to RenderMan not supporting ACES 2.0".
  — [Changes.md 1.3.0.0, 1.4.0.0, 1.7.0.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)

### Inferences
- Render passes plus a Spreadsheet and Wedge make per-pass or per-shot lighting variation a node-graph task rather than a Maya Render Setup task. For a student pipeline this means one Gaffer file can drive many passes through Tractor, Local or Flamenco dispatchers.
- The OCIO default is ACES 1.3. A Maya 2027 lookdev comparison should confirm that both apps use the same OCIO config and view, or Gaffer and MtoA renders will not match visually.

### Gaps
- I did not confirm whether light groups and AOV light-group naming match MtoA's conventions.
- I did not check the Light Tool's current full manipulator list beyond the 1.3.0.0 entry.

---

## Scene assembly: SceneReader formats, instancing, scene editing nodes

### Takeaway
SceneReader reads USD, Alembic and Cortex SceneCache (.scc), and Gaffer's VDB support covers volumes. Everything is converted into Gaffer's own scene hierarchy and then processed by nodes such as Prune, Isolate, Parent, MergeScenes, Group, Duplicate, CollectScenes, Encapsulate/Unencapsulate, Instancer and PointInstancer, Rename, SubTree and the constraints. Since 1.7, PointInstancer is the preferred instancing node: it exports to USD, renders faster and is editable downstream. The old Instancer is deprecated in the unreleased line.

### Cited Findings
- **Scene assembly and editing nodes in GafferScene (1.7.7.0):** SceneReader, SceneWriter, Prune, Isolate, Parent, MergeScenes, Group, Duplicate, CollectScenes, Encapsulate, Unencapsulate, Instancer, PointInstancerCore, PointInstancerQuery, Rename, SubTree, Transform, FreezeTransform, Scatter, ImageScatter, ExternalProcedural, Capsule, CopyObject, AimConstraint/ParentConstraint/PointConstraint/FramingConstraint/ReflectionConstraint, MotionPath, MeshTessellate, MeshSplit, VisibleSet and SceneStats. — [GafferScene headers, 1.7.7.0](https://github.com/GafferHQ/gaffer/tree/1.7.7.0/include/GafferScene)
- **PointInstancer node (1.7.0.0):** "Prototypes and points that are editable downstream", "Export to USD", "Faster rendering". In the unreleased line, the Instancer node is "Deprecated and removed from the node menu ... Use the PointInstancer node instead". A new PromotePointInstances node promotes instances to hero locations. — [Changes.md 1.7.0.0 and unreleased](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **USD PointInstancers:** in the unreleased line, UsdGeomPointInstancers "now always render as optimised native PointInstancer objects". The legacy adaptor and the Viewer's "Expand USD Instancers" item were removed. — [Changes.md unreleased](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Cycles PointInstancers:** rendering was added in 1.7.4.0. — [Changes.md 1.7.4.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Native USD instancing:** IECoreUSD performs "naive loading of USD instances" (Cortex 10.1.0.0), with later performance work for instanceable prims in Cortex 10.4.9.x. — [Cortex Changes](https://github.com/ImageEngine/cortex/blob/main/Changes)
- **Alembic:** SceneReader reads `P3d` and `N3d` GeomParams from Alembic (1.7.1.0). SceneWriter writes Alembic visibility attributes (1.0.3.0). — [Changes.md](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Cortex SceneCache inside USD:** .scc files can be loaded as USD references or sublayers through a SceneCacheFileFormat plugin (Cortex 10.1.8.0, 10.7.2.0). — [Cortex Changes](https://github.com/ImageEngine/cortex/blob/main/Changes)
- **Gaussian splats (1.7.4.0):** SceneReader loads ParticleField3DGaussianSplat USD prims. Arnold rendering of splats "requires Arnold version 7.5.2 or later". — [Changes.md 1.7.4.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Volumes:** OpenVDB support includes ArnoldVDB, DeleteGrids, LevelSetSmooth, half-typed grids and Arnold rendering of VDB volume LODs (1.7.x). — [Changes.md 1.7.x](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Dispatchers:** LocalDispatcher and TractorDispatcher. A FlamencoDispatcher (Blender's Flamenco farm manager) was added in 1.7.0.0. — [Changes.md 1.7.0.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)

### Inferences
- Gaffer's edit/tweak paradigm is procedural and pull-based. Nothing is baked into the input file, and every edit is a node downstream of the SceneReader. That fits a "publish model USD, lookdev reads it" pipeline well.

### Gaps
- I did not find a definitive list of SceneReader file extensions in the docs. USD (.usd/.usda/.usdc; .usdz not confirmed), Alembic (.abc) and Cortex .scc are evidenced by the changelog only.

---

## Image nodes and compositing; how Catalogue works

### Takeaway
GafferImage is a real 2D compositing toolkit (Merge, Grade, Resize, Transform, Shuffle, Deep, OCIO and more), though it is not a Nuke replacement. Renders stream live into a **Catalogue** node, which holds a browsable list of rendered images and snapshots that can be compared, ordered, named as numbered outputs, and fed into downstream image nodes or ContactSheets.

### Cited Findings
- **GafferImage nodes (1.7.7.0):**
  - Merge, Mix, Grade, CDL, Saturation, ColorSpace, LUT, LookTransform, DisplayTransform.
  - Resize, Resample, Crop, ImageTransform, Mirror, Offset, Warp, VectorWarp.
  - Blur, DiskBlur, Median, Dilate, Erode.
  - Shuffle, CopyChannels, DeleteChannels, Premultiply/Unpremultiply, Constant, Checkerboard, Ramp, Rectangle, Shape, Text.
  - ImageReader, ImageWriter, ImageStats, ImageSampler, CollectImages.
  - Multi-view nodes: CreateViews, SelectView, CopyViews.
  - Deep nodes: DeepMerge, DeepHoldout, DeepToFlat, FlatToDeep, DeepRecolor, DeepSlice.
  - ContactSheetCore, BleedFill, DeepTidy.
  — [GafferImage headers 1.7.7.0](https://github.com/GafferHQ/gaffer/tree/1.7.7.0/include/GafferImage), [python/GafferImage](https://github.com/GafferHQ/gaffer/tree/1.7.7.0/python/GafferImage)
- **Catalogue node documentation:** "Stores a catalogue of images to be browsed. Images can either be loaded from files or rendered directly into the catalogue." Live renders reach it via an `ieDisplay` output with `driverType: ClientDisplayDriver` and `remoteDisplayType: GafferScene::GafferDisplayDriver`, plus an optional `catalogue:name`. — [CatalogueUI.py, 1.7.7.0](https://github.com/GafferHQ/gaffer/blob/1.7.7.0/python/GafferSceneUI/CatalogueUI.py)
- **Catalogue features:**
  - "Output Index" column (1.1.1.0) for numbered outputs referenced from the Viewer and CatalogueSelect.
  - `imageNames` output plug (1.4.0.0) that can drive Wedge, ContactSheet and CatalogueSelect.
  - Fix for undoing snapshots (1.7.0.0).
  - Image-order metadata from before 1.4 is no longer supported (1.7.0.0).
  — [Changes.md](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Denoiser toggle:** a Viewer hotkey <kbd>D</kbd> switches between the denoised and undenoised layers (1.6.14.0). — [Changes.md 1.6.14.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **GafferML (machine learning inference) exists:** Inference, ImageToTensor and TensorToImage nodes. Experimental CUDA inference has been available since 1.6.0.0. — [GafferML headers](https://github.com/GafferHQ/gaffer/tree/1.7.7.0/include/GafferML), [Changes.md 1.6.0.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)

### Inferences
- The Catalogue works like a render-view history (similar to the Arnold RenderView snapshots in Maya) with snapshot comparison. Because it is also a node, lighting artists can do slap comps or contact sheets directly from renders.

### Gaps
- I did not verify where Catalogue snapshots are stored on disk (a directory plug), so this is not cited.

---

## Renderers: what is supported, how they install, Arnold version matching and licensing

### Takeaway
Gaffer 1.7.x supports these renderers:
- **Arnold:** 7.4 and 7.5. Not bundled; requires `ARNOLD_ROOT` pointing at an Arnold SDK install.
- **Cycles:** 5.1.0. Bundled, CPU and GPU (CUDA/OptiX).
- **3Delight:** via `DELIGHT`.
- **RenderMan:** 26.x/27.x via `RMANTREE`.
- **OpenGL** viewport.

Appleseed was removed in 1.3.0.0 (2023). Gaffer picks the matching GafferArnold build at startup from `ARNOLD_ROOT/include/ai_version.h`, keyed by Arnold "ARCH.MAJOR", so any Arnold **7.5.x** SDK works with 1.7.x. That matches Maya 2027's MtoA 5.6.x (Arnold 7.5.x core). Arnold inside Gaffer is Arnold core rendering, so Autodesk's normal licence rules apply: no licence means a watermark.

### Cited Findings
- **Supported third-party tools:** Arnold, Cycles, 3Delight, RenderMan and Tractor. "Gaffer comes with Cycles, so it will require no additional configuration. For the rest ... you will need to set some additional environment variables." — [ConfiguringGafferForThirdPartyTools doc, 1.7.7.0](https://github.com/GafferHQ/gaffer/blob/1.7.7.0/doc/source/GettingStarted/ConfiguringGafferForThirdPartyTools/index.md)
- **Arnold setup:** "For Gaffer to load the GafferArnold module, the `ARNOLD_ROOT` environment variable must point to the Arnold installation directory." The docs' example version and path are Arnold 7.4.1.0 at `C:\software\arnold-7.4.1.0` on Windows and `/opt/solidangle/arnold-7.4.1.0` on Linux. — [doc](https://github.com/GafferHQ/gaffer/blob/1.7.7.0/doc/source/GettingStarted/ConfiguringGafferForThirdPartyTools/index.md), [doc/source/conf.py](https://github.com/GafferHQ/gaffer/blob/1.7.7.0/doc/source/conf.py)
- **How the launcher picks GafferArnold:** it reads `ARNOLD_ROOT/include/ai_version.h`, parses `AI_VERSION_ARCH_NUM` and `AI_VERSION_MAJOR_NUM`, and loads `gafferRoot/arnold/<ARCH>.<MAJOR>`. Otherwise it prints "WARNING : GafferArnold extension not available for Arnold X.Y". It then adds `ARNOLD_ROOT/bin`, `ARNOLD_ROOT/python`, `ARNOLD_ROOT/plugins` (to `ARNOLD_PLUGIN_PATH`) and Arnold's `usdArnold` resources (to `PXR_PLUGINPATH_NAME`). It disables Autodesk Analytics (ADP) unless `ARNOLD_ADP_OPTIN` or `ARNOLD_ADP_DISABLE` is already set. — [bin/__private/_gaffer.py, main](https://github.com/GafferHQ/gaffer/blob/main/bin/__private/_gaffer.py)
- **Arnold versions built in CI:**
  - 1.7.7.0 builds and tests GafferArnold against **Arnold 7.4.1.0 and 7.5.1.0**.
  - 1.6.21.8 builds against **7.3.1.0, 7.4.1.0 and 7.5.1.0**.
  — [.github/workflows/main.yml @1.7.7.0](https://github.com/GafferHQ/gaffer/blob/1.7.7.0/.github/workflows/main.yml), [main.yml @1.6.21.8](https://github.com/GafferHQ/gaffer/blob/1.6.21.8/.github/workflows/main.yml)
- **Arnold version support timeline:**

  | Release | Date | Arnold change |
  |---|---|---|
  | 0.61.1.0 | | Arnold 7 support added |
  | 1.0.0.0 | 2022-07 | Requires Arnold 7.1.0.0 or newer |
  | 1.2.3.0 | | Arnold 7.2 support added |
  | 1.4.0.0 | 2024-04 | Arnold 7.3 support added (minimum 7.3.1.0); 7.1 support removed |
  | 1.5.9.0 | 2025-03-27 | Arnold 7.4 support added |
  | 1.6.0.0 | 2025-08 | Arnold 7.2 support removed |
  | 1.6.15.0 | 2026-03-27 | Arnold 7.5 support added |
  | 1.7.0.0 | 2026-08-13 | Arnold 7.3 support removed |
  | 1.7.4.0 | | Gaussian splats require Arnold 7.5.2 or later |

  — [Changes.md](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Arnold 7.5.2 compatibility fix:** 1.6.21.2 fixed a crash with Arnold 7.5.2 when setting the `driver_exr` "compression" parameter, which changed from a string to a string array. This shows that point releases of Arnold can need Gaffer fixes. — [Changes.md 1.6.21.2](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **MtoA USD interoperability:** 1.6.15.0 "Silenced warnings when rendering `ray_switch_shader` nodes exported to USD from MtoA". This is direct evidence of MtoA-to-USD-to-Gaffer workflows. — [Changes.md 1.6.15.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Other Arnold additions:**
  - ArnoldOptions "Scene Description" options (1.7.0.0): write ASCII `.ass` files and expand procedurals.
  - `reportFileName` for Arnold 7.4 HTML reports (1.5.9.0).
  - ArnoldImager node (0.61.3.0).
  - ArnoldCamera node for fisheye and spherical cameras (unreleased).
  - `ai:`-prefixed camera parameters (unreleased).
  — [Changes.md](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Maya 2027 Arnold versions:**
  - Autodesk's Maya 2027 What's New says "Arnold for Maya (MtoA) 5.6.0 uses Arnold 7.5.0.0". — [Autodesk Maya 2027 What's New: MtoA 5.6.0](https://help.autodesk.com/cloudhelp/2027/ENU/Maya-WhatsNew/files/GUID-82D13118-E987-4B5E-B1DA-C2A01F51058C.htm)
  - Later Arnold 7.5.x releases: Arnold 7.5.2 with Gaussian splats (June 2026), 7.5.3 (July 2026) and 7.5.4 with MtoA 5.6.4 (Oct/Nov 2026). — [CG Channel: Arnold 7.5.2](https://www.cgchannel.com/2026/06/autodesk-releases-arnold-7-5-2-with-support-for-gaussian-splatting/), [CG Channel: Arnold 7.5.3](https://www.cgchannel.com/2026/07/autodesk-releases-arnold-7-5-3/), [CG Channel: Arnold 7.5.4](https://cgchannel.com/2026/10/autodesk-releases-arnold-7-5-4), [Digital Production: Arnold 7.5.4](https://digitalproduction.com/2026/11/05/arnold-7-5-4-shader-imager-viewport-pausing/)
  - A search summary said Maya 2027.1 moved to MtoA 5.6.1.1 / Arnold 7.5.1.1 and Maya 2027.3 bundles MtoA 5.6.4. I could not open the CG Channel pages that carry these details (HTTP 403). The [Maya 2027.1 release notes](https://help.autodesk.com/cloudhelp/2027/ENU/Maya-ReleaseNotes/files/MAYA_RELEASENOTES_2027_1_HTML.html) did not state the MtoA version. Treat these as unverified.
  - **Conflict:** one CG Channel summary said Maya 2027 "shipped with older plugins" that needed separate download. That contradicts Autodesk's own Maya 2027 What's New entry for MtoA 5.6.0.
- **Cycles:**
  - Introduced in **1.0.3.0 (2022-08-26)** as an opt-in feature preview (`GAFFERCYCLES_FEATURE_PREVIEW=1`).
  - Enabled by default from 1.2.0.0 (2023-02-14).
  - CUDA and OptiX devices from 1.4.0.0 (GCC 11 and Windows builds).
  - OSL shading on OptiX from 1.5.0.0.
  - Updated to Cycles 5.1.0 in 1.7.0.0.
  - Can be hidden with `GAFFERCYCLES_HIDE_UI=1`.
  — [Changes.md](https://github.com/GafferHQ/gaffer/blob/main/Changes.md), [config doc](https://github.com/GafferHQ/gaffer/blob/1.7.7.0/doc/source/GettingStarted/ConfiguringGafferForThirdPartyTools/index.md)
- **RenderMan:**
  - Preliminary support in **1.5.9.0 (2025-03-27)**, needing RenderMan 26.3 and `GAFFERRENDERMAN_FEATURE_PREVIEW=1`.
  - From 1.6.0.0 the feature flag was removed and the extension is enabled whenever `RMANTREE` is set.
  - RenderMan 27.0 and XPU (1.6.6.0), 27.1 (1.6.8.0), 27.2 (1.6.14.0) and 27.3 (1.7.0.0) support followed.
  - 27.1 support was removed in 1.7.0.0.
  - 26.3 and 26.4 support is removed in the unreleased line.
  — [Changes.md](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **3Delight:**
  - Configured via `DELIGHT`. On Windows, Gaffer "currently requires 3Delight for Maya to be included as part of the 3Delight install for access to lights and shaders".
  - 3Delight Cloud renderer (1.4.3.0).
  — [config doc](https://github.com/GafferHQ/gaffer/blob/1.7.7.0/doc/source/GettingStarted/ConfiguringGafferForThirdPartyTools/index.md), [Changes.md 1.4.3.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Appleseed:** "Removed Appleseed support. We suggest Cycles as an actively maintained open-source alternative" (**1.3.0.0, 2023-07-13**). — [Changes.md 1.3.0.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Official Windows builds:** since 1.2.0.0 (2023-02-14). The 1.7.7.0 release ships `gaffer-1.7.7.0-windows.zip` and `gaffer-1.7.7.0-linux.tar.gz`. — [Changes.md 1.2.0.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md), [release 1.7.7.0](https://github.com/GafferHQ/gaffer/releases/tag/1.7.7.0)
- **Arnold licensing:**
  - "The watermark will appear on renders if Arnold can't find a license." Licensing needs a running licence server with a valid licence, and "Abort On License Fail" makes farm renders fail instead of watermarking. — [Autodesk Arnold for Maya: Watermarks](https://help.autodesk.com/cloudhelp/2024/ENU/AR-Maya/files/am-Arnold_for_Maya_User_Guide/getting-started/arnold_for_maya_getting_started_am_Watermarks_html.html)
  - Gaffer exposes `ai:abort_on_license_fail` (default behaviour fixed for 7.3+ in 1.6.0.0). Its CI sets `ARNOLD_LICENSE_ORDER: none` and `ARNOLD_FORCE_ABORT_ON_LICENSE_FAIL: 0` to render unlicensed (watermarked) during tests. — [Changes.md 1.6.0.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md), [main.yml @1.7.7.0](https://github.com/GafferHQ/gaffer/blob/1.7.7.0/.github/workflows/main.yml)
  - Licensing overview: [Arnold Licensing Home](https://help.autodesk.com/cloudhelp/ENU/AR-Core/files/arnold-setup/arnold_user_guide_arnold_setup_ac_licensing_home_html.html). I could not fetch it for detail.

### Inferences
- **Version match:** Gaffer 1.7.x (or 1.6.21.x) and Maya 2027's MtoA 5.6.x are both on the Arnold **7.5** line. Installing the Arnold 7.5.x SDK at the same point version as the students' MtoA (for example 7.5.4 if Maya 2027.3 with MtoA 5.6.4) gives the most consistent shaders and renders. Gaffer only cares about the 7.5 ARCH.MAJOR, so the point version is the studio's choice. Matching matters because MtoA-exported `.ass` and USD files carry core shader parameter sets that change between 7.5.x releases, for example the `driver_exr` compression type change in 7.5.2.
- **Not bundled:** Gaffer needs a separate Arnold SDK download (headers plus `bin`), because the launcher requires `include/ai_version.h`. I did not verify whether an MtoA install folder contains `include/ai_version.h` and could stand in for the SDK.
- **Licensing (inferred, not verified):** Gaffer renders call Arnold core directly, outside Maya. So they presumably need the same Arnold licence that `kick` or standalone batch rendering would need, interactive Viewer renders in Gaffer included. Without a licence they watermark. Whether an Autodesk education or Maya-bundled entitlement covers Arnold core use from third-party hosts like Gaffer needs confirming with Autodesk or the institution's licence admin.

### Gaps
- I found no Autodesk documentation that names Gaffer, and no "Arnold for Gaffer" product page. Autodesk does not appear to ship or document a Gaffer plugin. Gaffer's Arnold integration is written and maintained by GafferHQ.
- I could not verify the batch versus interactive licence distinction for Maya, or how it applies to Gaffer. The Autodesk support article was blocked (HTTP 403).
- I could not confirm the exact Arnold core version for each Maya 2027.x point release from a primary Autodesk source.

---

## USD: reading, writing, layers, variants, purposes, payloads, USDLux, UsdShade, resolvers, Hydra, round tripping

### Takeaway
Gaffer is a **scene-graph translation** of USD, not a Solaris-style stage editor:
- SceneReader composes the stage and converts prims into Gaffer locations, attributes, sets and shaders. Composition arcs are not preserved.
- SceneWriter writes a flattened USD.
- **USDLayerWriter** (0.61.13.0) writes the minimal difference between two Gaffer scenes as a USD layer. This is the realistic way to export lookdev or light edits as an overlay layer for other DCCs.

Supported:
- UsdShade materials, including purpose-based bindings.
- UsdLux lights for all renderers.
- UsdPreviewSurface translated at render time.
- `usd:purpose` filtering.
- USD `kind` and purpose authoring (USDAttributes).
- UsdSkel baked on load.
- Volumes and PointInstancers.
- In-memory stages via `stageCache:`.

Bundled USD version: **26.05** in 1.7.0.0; 25.05.01 in 1.6. I found no evidence of variant-selection, payload-control or Hydra render-delegate features in Gaffer itself.

### Cited Findings
- **USD versions bundled:**

  | Gaffer release | USD version |
  |---|---|
  | 0.56.1.0 | 20.02 |
  | 1.0.0.0 | 21.11 |
  | 1.3.0.0 | 23.05 |
  | 1.4.0.0 | 23.11 |
  | 1.5.0.0 | 24.08 |
  | 1.6.0.0 | 25.05.01 |
  | 1.7.0.0 | **26.05** |

  1.7.x also notes "Fixed build compatibility with USD 25.08". — [Changes.md](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **UsdShade:** "Added support for reading and writing shader assignments via UsdShade" (0.61.2.0, 2022-02-02). — [Changes.md 0.61.2.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **USDLayerWriter (0.61.13.0):** "a new node for baking the difference between two Gaffer scenes into a minimal USD layer on disk". Performance improved with a "50x speedup for one benchmark" in 1.5.5.0. — [Changes.md 0.61.13.0, 1.5.5.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **USDAttributes node (0.61.13.0):** sets USD `kind` and `purpose`. — [Changes.md 0.61.13.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Purposes:**
  - Loaded as the `usd:purpose` attribute (Cortex 10.1.1.0).
  - StandardOptions `includedPurposes` controls render inclusion (1.3.4.0).
  - Per-purpose Viewer visibility (1.3.4.0).
  - Viewer presets Render, Preview and Preview with Guides (1.6.4.0).
  - A `usd:purpose` diagnostic shading mode (1.4.11.0).
  — [Changes.md](https://github.com/GafferHQ/gaffer/blob/main/Changes.md), [Cortex Changes](https://github.com/ImageEngine/cortex/blob/main/Changes)
- **USD Kind:** Viewer selection can snap to ancestors whose `usd:kind` matches Assembly, Component, Group and so on (1.4.0.0). — [Changes.md 1.4.0.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **UsdLux:**
  - Basic loading in 1.0.0.0 ("needs manual conversion"). Render-time translation for Arnold in 1.0.3.0, which also put all UsdLuxLights in `defaultLights`.
  - USDLight node in 1.3.1.0.
  - USDShader loads from UsdSchemaRegistry for UsdLux in 1.4.2.0.
  - UsdLux IES parameters translated to Arnold in 1.5.11.0.
  — [Changes.md](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **UsdSkel:** IECoreUSD applies UsdSkel blendshapes and linear-blend skinning on load. It is "just baking the deformation onto the Cortex Primitive", not exposing UsdSkel (Cortex 10.1.3.0). — [Cortex Changes](https://github.com/ImageEngine/cortex/blob/main/Changes)
- **In-memory stages:** SceneReader reads them via `stageCache:{id}.usd` from `UsdUtilsStageCache` (1.3.3.0). — [Changes.md 1.3.3.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Volumes:** limited reading and writing of Usd Volume prims (1.3.1.0). — [Changes.md 1.3.1.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **USD export conventions:**
  - 1.7.0.0 defaults to writing OSL shaders and `ri:` attributes in an `hdPrman`-compatible format "for rendering in `usdview` and other Hydra-based applications". `IECOREUSD_WRITE_CONFORMANT_OSL_SHADERS=0` and `IECOREUSD_WRITE_CONFORMANT_RENDERMAN_ATTRIBUTES=0` revert this.
  - Arnold OSL ramps now survive a USD export/re-import round trip (1.7.x).
  — [Changes.md 1.7.0.0, 1.7.x](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Arnold-USD conventions:** Gaffer supports Arnold-USD's convention for connections to array indices (1.1.8.0). The launcher puts Arnold's `usdArnold` schema resources on `PXR_PLUGINPATH_NAME`. — [Changes.md 1.1.8.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md), [_gaffer.py](https://github.com/GafferHQ/gaffer/blob/main/bin/__private/_gaffer.py)
- **Hydra:** "USD : Removed Embree Hydra delegate" (1.4.0.0). This means Gaffer once bundled a Hydra delegate for usdview, but Gaffer's own viewer and renders go through its native renderer backends, not Hydra. — [Changes.md 1.4.0.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Composition is lost on load:** a gaffer-dev discussion says that once a USD file is loaded, Gaffer treats it as a native scene and loses its composition information (references and layers). — [gaffer-dev: "Layered USD in Gaffer and Scene Assembly"](https://groups.google.com/g/gaffer-dev/c/btfWzh2szwk) (discussion thread, not official docs)
- **Known limitations and open issues:**
  - Per-face GeomSubset shader assignments not working through SceneReader (reported December 2024). — [gaffer-dev thread](https://groups.google.com/g/gaffer-dev/c/wMGduLaghKI)
  - Open issue #7012 (2026-07-08): "USD: Use 'asset' type parameters instead of 'string' for filepaths". This affects how file paths are written for asset resolvers. — [issue #7012](https://github.com/GafferHQ/gaffer/issues/7012)
- **Relative prototype paths (1.7.0.0):** SceneReader removed the `./` prefix from relative prototype paths loaded from USD, and `GAFFERSCENE_INSTANCER_EXPLICIT_ABSOLUTE_PATHS` now defaults to 1. — [Changes.md 1.7.0.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)

### Inferences
- **For a Maya 2027 + USD model-publish pipeline:** Gaffer can read the published model `.usd` directly. It can export lookdev back out either as a full USD via SceneWriter or as a sparse overlay layer via USDLayerWriter. Maya would then compose that layer over the model through mayaUsd or MtoA's USD procedural.
- The USD that Gaffer sees is the composed result of the stage's authored variant selections. Switching variants in Gaffer would need an upstream USD layer or a separate SceneReader per variant. This is inferred from the absence of any variant feature in Gaffer's or Cortex's changelogs.
- **Version check:** USD 26.05 in Gaffer 1.7 is newer than the USD in Maya 2027's mayaUsd. Files written with newer schemas, such as Gaussian-splat prims, may not open in Maya's older USD.

### Gaps
- **Variants:** I found no Gaffer or Cortex changelog entry, doc page or issue documenting variant-set selection in SceneReader. GitHub issue search for "variant" in GafferHQ/gaffer returned nothing relevant.
- **Payloads:** issue search for "payload" in GafferHQ/gaffer returned no results. I could not verify whether payloads load by default (likely load-all) or whether there is a control.
- **Asset resolver:** I found no doc stating that custom ArResolver plugins are honoured. Because Gaffer bundles stock USD, a resolver plugin would presumably work if built against USD 26.05 and put on `PXR_PLUGINPATH_NAME`, but this is unverified.
- I found no SIGGRAPH or USD working-group talk material within the call budget.
- I did not establish the exact USD version in Maya 2027's mayaUsd.

---

## MaterialX support status

### Takeaway
Gaffer bundles the MaterialX library (1.39.4 in 1.7.0.0), but I found no Gaffer node or feature for authoring or rendering MaterialX documents. Its shader nodes are ArnoldShader, OSL, Cycles, RenderMan and USDShader (Sdr). The old OSL-generated MaterialX shader set was dropped in 1.2.0.0. MaterialX is effectively a dependency, not a lookdev workflow.

### Cited Findings
- **MaterialX library versions:**

  | Gaffer release | MaterialX version |
  |---|---|
  | 1.3.0.0 | "Added version 1.38.4" |
  | 1.4.0.0 | 1.38.8 |
  | 1.5.0.0 | 1.38.10 |
  | 1.6.0.0 | 1.39.3 |
  | 1.7.0.0 | 1.39.4 |

  — [Changes.md](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Old MaterialX OSL shaders removed (1.2.0.0):** "The majority of OSL shaders in `shaders/MaterialX` are no longer provided, as the `OpenShadingLanguage` project removed them and no direct equivalent exists in the `MaterialX` project itself." — [Changes.md 1.2.0.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **No MaterialX node:** no MaterialX-specific node exists in any 1.7.7.0 module header list (GafferScene, GafferArnold, GafferOSL, GafferUSD, GafferCycles, GafferRenderMan). — [include/ @1.7.7.0](https://github.com/GafferHQ/gaffer/tree/1.7.7.0/include)
- **USDShader nodes:** contributor PRs in 2024 improved USDShader shader-type namespacing and assignment. Search results associate them with MaterialX, but I did not read them. — [PR #6076](https://github.com/GafferHQ/gaffer/pull/6076), [PR #6083](https://github.com/GafferHQ/gaffer/pull/6083)
- **Arnold Operators:** a community PR "Arnold Operators" (#5841, 2024) is closed. No ArnoldOperator node exists in 1.7.7.0 headers, so Arnold's `materialx` operator route is not exposed as a node. — [PR #5841](https://github.com/GafferHQ/gaffer/pull/5841), [GafferArnold headers](https://github.com/GafferHQ/gaffer/tree/1.7.7.0/include/GafferArnold)

### Inferences
- Lookdev that must travel between Maya and Gaffer is safest as Arnold-native shader networks (standard_surface and similar) in USD, or as UsdPreviewSurface for broad interchange. MaterialX is not a practical bridge in Gaffer today.
- Whether MaterialX nodes in a read USD file render through Arnold in Gaffer depends on Arnold core's own USD/MaterialX handling, not on Gaffer.

### Gaps
- I could not confirm whether UsdShade networks using MaterialX `ND_*` nodes, as authored by Maya's LookdevX, are read by SceneReader and rendered by Arnold in Gaffer. I found no source testing this.
