# Gaffer: history, governance, architecture and platform basics (state as of 2026-11-24)

Research notes for a pipeline TD team assessing Gaffer for a teaching studio pipeline (Maya 2027, Arnold, USD, ShotGrid, Windows workstations, shared network storage). Release dates come from the GitHub Releases API (`api.github.com/repos/GafferHQ/gaffer/releases`), pulled 2026-11-24. Build and dependency facts come from `Changes.md` on `main` (https://github.com/GafferHQ/gaffer/blob/main/Changes.md), pulled the same day. gafferhq.org was up, but several of its documentation URLs returned 404 or 503 to the fetch tool. Documentation facts were therefore read from the Sphinx sources in the repo (`doc/source/...`), which is what gafferhq.org/documentation is built from.

## History: origins, open-sourcing, Cinesite, maintainers, governance, contributors

### Takeaway
John Haddon started Gaffer on his own in 2007. It was open-sourced in 2011 and adopted by Image Engine, which joined the Cinesite group in 2015. Cinesite now describes its group as the developer and supporter of Gaffer. Image Engine, Cinesite and Haddon jointly hold the copyright. Releases are cut by the core team on GitHub. I found no formal governance document or foundation membership.

### Cited Findings
- Image Engine's R&D account (Feb 2017) says Gaffer was "started independently in 2007 by John Haddon" and that Image Engine has used and extended it in production "since it was open-sourced in 2011". The same account says Cortex development started in 2007 at Image Engine, as a "common codebase" of VFX datatypes and algorithms with support libraries for Maya, Nuke, Houdini, RenderMan and Arnold — [Post Magazine, "Workflow: Image Engine's open-source VFX tools", Feb 2017](https://postmagazine.com/Publications/Post-Magazine/2017/February-1-2017/Workflow-Image-Engines-open-source-VFX-tools.aspx)
- At the time, Image Engine's proprietary asset management system "Jabuka" was built on Gaffer and Cortex. Its automation was used for multi-shot lighting on *Kingsglaive: Final Fantasy XV* — [Post Magazine 2017](https://postmagazine.com/Publications/Post-Magazine/2017/February-1-2017/Workflow-Image-Engines-open-source-VFX-tools.aspx)
- The 2016 DigiPro paper "Gaffer: an open-source application framework for VFX" was written by Haddon, Andrew Kaufman, David Minor, Daniel Dresser, Ivan Imanishi and Paulo Nogueira (all Image Engine at the time) — [researchr listing](https://researchr.org/publication/HaddonKMDIN16); [SIGGRAPH History Archive](https://history.siggraph.org/experience/gaffer-an-open-source-application-framework-for-vfx-by-kaufman)
- There was also a SIGGRAPH talk, "Gaffer: Open Source Lookdev, Lighting, and Automation" by Kaufman and Haddon — [SIGGRAPH History Archive](https://history.siggraph.org/experience/gaffer-open-source-lookdev-lighting-and-automation-by-kaufman-and-haddon)
- Image Engine partnered with Cinesite in July 2015 and is now part of the Cinesite group, alongside Trixter and L'Atelier Animation — [Wikipedia: Image Engine](https://en.wikipedia.org/wiki/Image_Engine)
- Cinesite's technology page says the Cinesite group "fully develops and supports" Gaffer and calls it free, open source and production-ready — [cinesite.com/technology](https://cinesite.com/technology/)
- The repo README names three copyright holders for 2011–2026: John Haddon, Image Engine Design Inc. and Cinesite VFX Ltd — [GafferHQ/gaffer README](https://github.com/GafferHQ/gaffer)
- The code moved from the `ImageEngine/gaffer` GitHub organisation to `GafferHQ/gaffer`. Old ImageEngine URLs still resolve — [github.com/ImageEngine/gaffer](https://github.com/ImageEngine/gaffer)
- Repo statistics on 2026-11-24: about 24,242 commits, 1.1k stars, 227 forks, 93 watchers — [GafferHQ/gaffer](https://github.com/GafferHQ/gaffer)
- Cortex now describes Gaffer as "a proof-of-concept demonstration of Cortex's power as a framework". Cortex still lives under the ImageEngine GitHub organisation and has Google Groups for discussion (cortexdev) — [ImageEngine/cortex README](https://github.com/ImageEngine/cortex)
- Gaffer 1.0.0.0 was published on 2022-07-06, after the 0.x series ran from 0.1 to 0.61 (0.61.0.0 was 2021-11-19) — [GitHub Releases API](https://api.github.com/repos/GafferHQ/gaffer/releases); [PixelSham, "GafferHQ releases Gaffer 1.0.0.0", 2022-07-06](https://www.pixelsham.com/2022/07/06/gafferhq-releases-gaffer-1-0-0-0)

### Inferences
- Funding is effectively in-house studio R&D at Cinesite and Image Engine, plus an open-source community. Day-to-day changes flow through GitHub pull requests with issue numbers (as cited throughout Changes.md), and the core team at these studios tags the releases.
- Haddon's personal copyright line suggests he retained rights from the pre-Image Engine period (2007–2011).

### Gaps
- I found no published governance document (TSC, charter or roadmap process), and no evidence that Gaffer is an ASWF project. The decision-making process could not be confirmed from a primary source.
- I could not get an exact current contributor count. The GitHub contributors API was not queried successfully, because the `gh` CLI was unavailable.
- Haddon's current employer and role are not confirmed in any 2026 source.
- I did not read any fxguide, CG Channel or befores & afters interviews in this pass.

## Licence and commercial support

### Takeaway
Gaffer is BSD-3-Clause. Its bundled dependencies are mostly permissive open-source VFX libraries. Arnold, RenderMan and 3Delight are not bundled: you supply them and they are found through environment variables. I found no commercial support offering.

### Cited Findings
- Gaffer's licence is BSD-3-Clause — [GafferHQ/gaffer README](https://github.com/GafferHQ/gaffer)
- The README says Gaffer is "built on the Cortex libraries" and supports Python and OSL scripting — [README](https://github.com/GafferHQ/gaffer)
- Third-party libraries are built from the separate GafferHQ/dependencies project. That project exists to get developers running quickly and to "provide a record of exactly which dependencies were used for each release of Gaffer, and how they were built". Prebuilt binary dependency releases are provided — [GafferHQ/dependencies README](https://github.com/GafferHQ/dependencies)
- The 1.7.0.0 build stack is Boost 1.85.0, Cortex 10.7.0.0, Cycles 5.1.0, Embree 4.4.0, Imath 3.1.12, LLVM 17.0.6, MaterialX 1.39.4, Nanobind 2.12.0, OpenColorIO 2.4.2 (with ACES 2.0 configs), OpenEXR 3.3.6, OSL 1.14.8.0, OpenSubdiv 3.6.1, OpenVDB 12.1.1, PySide/Qt 6.5.8, Python 3.11.14, TBB 2021.13.0 and USD 26.05 — [Changes.md, 1.7.0.0 Build section](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- Cycles is bundled. Arnold (`ARNOLD_ROOT`), 3Delight (`DELIGHT`) and RenderMan (`RMANTREE`) are optional and need environment variables. Tractor is also supported — [doc/source/GettingStarted/ConfiguringGafferForThirdPartyTools](https://github.com/GafferHQ/gaffer/blob/main/doc/source/GettingStarted/ConfiguringGafferForThirdPartyTools/index.md)
- The repo has a `license` app (`apps/license`), which presumably prints the bundled licences — [repo tree, apps/](https://github.com/GafferHQ/gaffer/tree/main/apps)

### Inferences
- Commercial renderers carry their own licensing. For Arnold on Windows, a classroom would need the Autodesk Arnold licence (Gaffer uses the Arnold SDK found at `ARNOLD_ROOT`, for example a standalone Arnold SDK install).
- The `license` app's exact output was not checked.

### Gaps
- I did not check the licence of each bundled dependency one by one. Most are BSD, Apache-2.0 or MPL in the ASWF style, but Qt/PySide are LGPL and that was not confirmed in-session.
- I found no vendor offering paid Gaffer support. The community support channel (Google Group gaffer-dev vs Discourse) was not confirmed in this pass.

## Core architecture

### Takeaway
Gaffer is a C++ and Python node-graph framework. Nodes hold plugs. Output values are computed lazily, on a pull, by ComputeNodes: each one first computes a hash of everything that affects the result, then uses the hash as a cache key. A Context carries the variables for each request (frame, scene path, tile and so on), and each thread has its own. Scenes and images are not monolithic objects. They are sets of child plugs computed per location, or per tile and channel, so huge scenes can be generated on demand and in parallel. Cortex (IECore) supplies the data types.

### Cited Findings
- **ComputeNode, hash and compute.** "When an output ValuePlug::getValue() method is called the value will be computed using a combination of the hash() and compute() methods". Computations "are threadsafe (multiple threads may call getValue() with multiple Contexts concurrently) and make use of an in-memory caching mechanism". `hash()` must hash all inputs used and "the value of any context items that will be accessed". A pass-through node should copy the input's hash directly so that cache entries are shared — [include/Gaffer/ComputeNode.h](https://github.com/GafferHQ/gaffer/blob/main/include/Gaffer/ComputeNode.h)
- **Cache policies.** ValuePlug defines per-plug cache policies for values and hashes. In 1.7.0.0 the deprecated policies were removed: `TaskIsolation` was replaced by `TaskCollaboration`, `Legacy` by `Default`, and `Standard` is replaced by `TaskCollaboration` for `computeCachePolicy()` and `Default` for `hashCachePolicy()` — [include/Gaffer/ValuePlug.h](https://github.com/GafferHQ/gaffer/blob/main/include/Gaffer/ValuePlug.h); [Changes.md 1.7.0.0 Breaking Changes](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Contexts.** A Context is "a bundle of variables provided to each operation performed by a node". Typical variables are frame, scene location, image tile and image channel. Contexts flow upstream while data flows downstream, and "each computing thread has its own Context". Nodes such as CollectScenes add variables, TimeWarp modifies the frame, and Spreadsheet, NameSwitch and Expression read variables — [doc/source/WorkingWithTheNodeGraph/Contexts](https://github.com/GafferHQ/gaffer/blob/main/doc/source/WorkingWithTheNodeGraph/Contexts/index.md)
- **Pull-based evaluation.** The thing that makes a request (a dispatcher or an editor) creates the context. Input plugs then pull on upstream plugs in a chain reaction until the output value is computed — [Contexts doc](https://github.com/GafferHQ/gaffer/blob/main/doc/source/WorkingWithTheNodeGraph/Contexts/index.md)
- **ScenePlug child plugs.** `bound`, `transform`, `attributes`, `object`, `childNames`, `exists`, `childBounds`, `globals`, `setNames`, `set` (a PathMatcherData) and `sortedChildNames` — [include/GafferScene/ScenePlug.h](https://github.com/GafferHQ/gaffer/blob/main/include/GafferScene/ScenePlug.h)
- **Scene model.** A scene is a hierarchy of *locations* with paths such as `/world/city/building01`. "Each property of each location is computed independently, allowing Gaffer to generate the scene lazily". Properties are transform (a 4x4 local matrix), bound (the union of the location and its descendants, in local space), object (primitive or camera, typically at leaves, with primitive variables P, N, uv and so on) and attributes (inherited by children and overridable). Globals are options, outputs and sets. Lights and cameras sets are maintained automatically — [doc/source/WorkingWithScenes/AnatomyOfAScene](https://github.com/GafferHQ/gaffer/blob/main/doc/source/WorkingWithScenes/AnatomyOfAScene/index.md)
- **Terminology for Maya users.** The doc says: "Maya users should note that attributes in Gaffer are not equivalent to attributes in Maya's Attribute Editor. The equivalent term in Gaffer is plug." Options and outputs are compared to Maya's render globals — [AnatomyOfAScene](https://github.com/GafferHQ/gaffer/blob/main/doc/source/WorkingWithScenes/AnatomyOfAScene/index.md)
- **ImagePlug child plugs.** `viewNames`, `format`, `dataWindow`, `metadata`, `deep`, `sampleOffsets`, `channelNames` and `channelData`, with a static `tileSize()` — [include/GafferImage/ImagePlug.h](https://github.com/GafferHQ/gaffer/blob/main/include/GafferImage/ImagePlug.h)
- **Image model.** Pixels are 32-bit float internally and are processed in 128x128 tiles, so they can be "computed in parallel, on a per-tile, per-channel basis". Format is the OpenEXR display window plus pixel aspect, data windows can differ from the display window, and channel naming follows OpenEXR — [doc/source/WorkingWithImages/AnatomyOfAnImage](https://github.com/GafferHQ/gaffer/blob/main/doc/source/WorkingWithImages/AnatomyOfAnImage/index.md)
- **Multi-view and deep images.** ImageNodes can output multiple "views" (since 1.0), and there are deep image plugs (`deep`, `sampleOffsets`) — [Changes.md 1.0.0.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md); [ImagePlug.h](https://github.com/GafferHQ/gaffer/blob/main/include/GafferImage/ImagePlug.h)
- **Performance and filters.** Cost is roughly locations × nodes. The docs advise applying lookdev per asset before grouping (linear rather than quadratic cost). The `...` path wildcard is expensive in hierarchy-changing nodes such as Prune and Isolate, and `/.../something` is the worst case — [doc/source/WorkingWithTheNodeGraph/PerformanceBestPractices](https://github.com/GafferHQ/gaffer/blob/main/doc/source/WorkingWithTheNodeGraph/PerformanceBestPractices/index.md)
- **Expressions.** Python and OSL are supported. In a test with a per-instance expression on 100,000 instances, OSL gave a 2× speedup on 1 thread and 16× on 12 threads. A Python expression that does not read `scene:path` or another fast-changing variable is cached and runs only once — [PerformanceBestPractices](https://github.com/GafferHQ/gaffer/blob/main/doc/source/WorkingWithTheNodeGraph/PerformanceBestPractices/index.md)
- **Instancer.** The upstream instance graph is evaluated per instance. 1.7.0.0 added a PointInstancer node, with editable prototypes and points, USD export and faster rendering — [PerformanceBestPractices](https://github.com/GafferHQ/gaffer/blob/main/doc/source/WorkingWithTheNodeGraph/PerformanceBestPractices/index.md); [Changes.md 1.7.0.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Set expressions and Spreadsheets.** Both have dedicated reference and tutorial pages in the docs (`Reference/ScriptingReference/SetExpressions`, `WorkingWithTheNodeGraph/SpreadsheetNode`, `TutorialSettingUpASpreadsheet`). 1.7.0.0 added an "Output" row to SpreadsheetUI — [repo doc tree](https://github.com/GafferHQ/gaffer/tree/main/doc/source); [Changes.md](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Boxes and References.** 1.7.0.0 added a GraphEditor location bar for navigating through Boxes and References and removed the deprecated Box plug promotion methods (use `PlugAlgo`). Node files saved as `.gfr` are referenced in Changes.md ("Removed ability to load from `.gfr` files prior to version 0.45.0.0") — [Changes.md 1.7.0.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Python modules on `main`.** Gaffer, GafferDispatch, GafferScene, GafferImage, GafferOSL, GafferUSD, GafferVDB, GafferML, GafferArnold, GafferCycles, GafferDelight, GafferRenderMan, GafferTractor and GafferFlamenco (each with UI and Test variants), plus the IECoreArnold, IECoreDelight and IECoreRenderMan renderer backends — [repo tree python/](https://github.com/GafferHQ/gaffer/tree/main/python)
- **Dispatchers.** LocalDispatcher, TractorDispatcher and FlamencoDispatcher (new in 1.7.0.0, for Blender's Flamenco farm manager) — [repo tree](https://github.com/GafferHQ/gaffer/tree/main/python/GafferDispatch); [Changes.md 1.7.0.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **New 1.7 task and file nodes.** FileList, CopyFiles, DeleteFiles and RenameFiles, plus DataStore, which keeps large data alongside a script — [Changes.md 1.7.0.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **USD.** USD support is through Cortex's IECoreUSD (SceneReader and SceneWriter). In 1.7 the writer defaults to hdPrman-conformant RenderMan attributes and OSL shaders, with `IECOREUSD_WRITE_CONFORMANT_*=0` to revert. Since 1.4.x, USD asset paths on Windows use `/` (`IECOREUSD_FORCE_ASSET_PATH_FORWARD_SLASH=0` reverts) — [Changes.md](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Cortex.** Cortex is "a framework for computation, rendering, and file I/O that provides a set of high-quality C++ libraries and Python modules tailored for software development in the VFX industry". Gaffer 1.7.0.0 builds against Cortex 10.7.0.0, and 1.7.5.0 against 10.7.4.0 — [Cortex README](https://github.com/ImageEngine/cortex); [GitHub Releases](https://github.com/GafferHQ/gaffer/releases)

### Inferences
- TBB is the threading library (it is in the dependency list, and 1.5 switched Windows to the TBB allocator). The task-collaboration cache policy shows that the caching layer is TBB-aware.
- The hash-then-cache design means a cheap edit far upstream only invalidates what depends on it. This is the main mental-model difference from Maya's DG and dirty propagation that students would face.

### Gaps
- PathFilter, SetFilter, Wedge, the Box/Reference file extension details and the TaskNode/TaskPlug class docs were not read directly in this pass. They exist in the codebase but are not quoted here. Reference files are conventionally `.grf` and scripts `.gfr`, but only `.gfr` was confirmed in-session.
- I did not confirm the exact list of built-in context variables (frame, framesPerSecond, script:name, scene:path and so on). See `doc/source/Reference/ContextVariables`.

## Apps that ship with Gaffer

### Takeaway
Gaffer is a launcher for a set of "apps": `gui`, `execute`, `dispatch`, `view`, `browser`, `stats`, `env`, `python`, `cli`, `test`, `screengrab`, `license` and, new in 1.7.5, `mcp`.

### Cited Findings
- `apps/` on `main` contains browser, cli, dispatch, env, execute, gui, license, mcp, python, screengrab, stats, test and view — [repo tree apps/](https://github.com/GafferHQ/gaffer/tree/main/apps)
- In 1.7.5.0, a `gaffer mcp` app was added "to allow AI assistants and large language models to launch and control a headless Gaffer session". A PythonEditor `mcpEnabled` setting was added at the same time — [Changes.md](https://github.com/GafferHQ/gaffer/blob/main/Changes.md); [Releases](https://github.com/GafferHQ/gaffer/releases)
- Since 1.7.0.0, apps run through a dedicated `gaffer` executable rather than `python`. The `bin/gaffer` (Linux) and `bin/gaffer.cmd` (Windows) launchers are still the entry points — [Changes.md 1.7.0.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- `gaffer env` exists, and a Windows bug that upper-cased environment variable names in LocalDispatcher, SystemCommand and `gaffer env` was fixed in 1.6 — [Changes.md](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)

### Inferences
- `gaffer execute` and `gaffer dispatch` are what a render farm or ShotGrid-triggered automation would call headlessly. `gaffer stats` is useful for profiling student scenes.

### Gaps
- I did not read each app's command-line flags. See `doc/source/Reference/CommandLineReference`.

## Versions, release cadence and VFX Reference Platform

### Takeaway
On 2026-11-24 the newest release is **1.7.7.0 (2026-11-12)**. The 1.7 series began with 1.7.0.0 on 2026-08-13, after ten alphas from May to August 2026. 1.6 is still maintained in parallel (1.6.21.8, also 2026-11-12). There is roughly one major (1.x) a year, with point releases about every 1–3 weeks. The README says the project targets **VFX Reference Platform CY2025**, and 1.7 ships Python 3.11.14 with Qt/PySide 6.5.8. The next major release (`1.x.x.x` on main) moves to Python 3.13 and Qt 6.8.5.

### Cited Findings
- Major release dates — [GitHub Releases API](https://api.github.com/repos/GafferHQ/gaffer/releases):
  - 1.0.0.0: 2022-07-06
  - 1.1.0.0: 2022-10-03
  - 1.2.0.0: 2023-02-14
  - 1.3.0.0: 2023-07-13
  - 1.4.0.0: 2024-04-15
  - 1.5.0.0: 2024-10-28
  - 1.6.0.0: 2025-08-28
  - 1.7.0.0: 2026-08-13
- 1.7 point releases — [GitHub Releases API](https://api.github.com/repos/GafferHQ/gaffer/releases):
  - 1.7.1.0: 2026-08-28
  - 1.7.2.0: 2026-09-15
  - 1.7.3.0: 2026-09-18
  - 1.7.3.1: 2026-09-25
  - 1.7.4.0: 2026-10-09
  - 1.7.4.1: 2026-10-21
  - 1.7.5.0: 2026-10-22
  - 1.7.6.0: 2026-10-29
  - 1.7.7.0: 2026-11-12, marked Latest
- Nightly builds are also published as a "nightly" pre-release (Linux tar.gz and Windows zip, for example `gaffer-nightly-2026_11_22-...-windows.zip`) — [GitHub Releases API](https://api.github.com/repos/GafferHQ/gaffer/releases)
- Version scheme: four parts, MILESTONE.MAJOR.MINOR.PATCH. Breaking changes land only in x.Y.0.0 releases (each has a "Breaking Changes" section) — [Changes.md](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- VFX Platform: the README says Gaffer "targets the CY2025 VFX Reference Platform" and builds with gcc 11.2.1 — [README](https://github.com/GafferHQ/gaffer). An older README snapshot said CY2022 — [search result on ImageEngine/gaffer](https://github.com/ImageEngine/gaffer). The 1.4 notes describe gcc11 builds aligning "with VFX Platform 2023" as beta ahead of 1.5 — [Changes.md 1.4.0.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- Python history (from Changes.md):
  - Python 2 was removed in 1.2.0.0, and "All builds are now using Python 3".
  - 1.4 updated to Python 3.10.13 (with Qt/PySide 5.15.12).
  - 1.6 moved to Python 3.11.12 and PySide/Qt 6.5.6.
  - 1.7 is on Python 3.11.14 and Qt 6.5.8.
  - The unreleased `1.x.x.x` section on main lists Python 3.13.16, PySide/Qt 6.8.5, a minimum of Qt 6, TBB 2022.3.0, OpenVDB 13.1.0, OIIO 3.2.2.0 and OCIO 2.5.2.

  [Changes.md](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- Arnold support timeline (from Changes.md):
  - Arnold 7.2 was added in 1.3.
  - Arnold 7.3 was added in 1.4 (minimum 7.3.1.0).
  - Arnold 7.4 was added in 1.5.
  - Arnold 7.2 was removed in 1.6.
  - Arnold 7.5 was added in the 1.6 series.
  - 1.7.0.0 removed Arnold 7.3, so 1.7 supports Arnold 7.4 and 7.5.
  - Gaussian splat rendering in Arnold (1.7.4.0) needs Arnold 7.5.2.0 or later.

  [Changes.md](https://github.com/GafferHQ/gaffer/blob/main/Changes.md); [Releases](https://github.com/GafferHQ/gaffer/releases)
- Other major changes by release (from Changes.md and the release notes):
  - 1.2: Cycles enabled by default, official Windows builds, Visible Set.
  - 1.3: Appleseed removed (Cycles recommended).
  - 1.4: Cycles CUDA/OptiX support (gcc11 and Windows builds only).
  - 1.5: AttributeEditor added, end of GCC 9 Linux builds.
  - 1.6: DiskBlur, FocalBlur, Arnold multi-layer EXR, ImageSelectionTool, ColorInspectorTool.
  - 1.7: LightLinkingEditor, PointInstancer, FlamencoDispatcher, file task nodes, DataStore, RenderMan 27.3, Cycles 5.1, SplinePlug renamed to RampPlug, built-in Maya/Houdini GLWidget hosting removed.
  - 1.7.4: USDMeshLight and USD 25.08 build compatibility.
  - 1.7.5: `gaffer mcp` and vertex paint.

  [Changes.md](https://github.com/GafferHQ/gaffer/blob/main/Changes.md); [Releases](https://github.com/GafferHQ/gaffer/releases)
- RenderMan 26.4 is no longer supported on Windows because it is unavailable for download — [Changes.md](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)

### Inferences
- Maya 2027 most likely tracks CY2026 (Python 3.13). The README says Gaffer 1.7 targets CY2025 and ships Python 3.11. So Gaffer and Maya **cannot share a Python interpreter or site-packages**, and any shared pipeline Python code must stay version-agnostic. The next Gaffer major release (Python 3.13 on main) will probably line up better.
- The 1.7.0.0 note "GLWidget: Removed built-in support for hosting in Maya and Houdini" confirms that Gaffer is not meant to run inside Maya. Integration should go through files (USD and Alembic via IECoreScene) and command-line apps.

### Gaps
- Maya 2027's VFX Platform year and Python version were not verified in this pass.
- I found no published fixed release cadence or support-window policy. Cadence is inferred from the dates.

## System requirements, platform support and deployment basics

### Takeaway
Linux (RHEL/Rocky/Alma 9) and Windows 10/11 are the officially supported, tested platforms. Official Windows builds started with **1.2.0.0 (Feb 2023)** and have matured since, with a steady stream of Windows fixes. macOS has no prebuilt binaries. Deployment is a self-contained zip or tar.gz extracted anywhere. You run `bin\gaffer.cmd` (Windows) or `bin/gaffer` (Linux), which sets up the environment. Studio configuration is done through `GAFFER_STARTUP_PATHS` and related environment variables.

### Cited Findings
- **Supported platforms.** "Officially supported and tested on Linux (RHEL/Rocky/AlmaLinux 9) and Windows 10/11" — [README](https://github.com/GafferHQ/gaffer)
- **Windows builds.** "Windows : Added official builds for Windows" is listed in 1.2.0.0 (2023-02-14). Windows install instructions were added to Getting Started at around the same time — [Changes.md 1.2.0.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Windows maturity milestones** (from Changes.md):
  - 1.4: compiler moved to Visual Studio 2022 / MSVC 17.8.
  - 1.4.x: usdview added on Windows.
  - 1.5: the TBB memory allocator gave "significantly better performance".
  - Fixes for exFAT paths, file:// URLs and the "{path} was unexpected" startup error when PATH contains quotes.
  - Arnold ADP crash reporting disabled by default on Windows.
  - `PXR_USD_WINDOWS_DLL_PATH` handling added to stop clashes with other software on PATH.
  - 1.7: main thread stack raised to 4MB.
  - The unreleased main branch updates the Windows SDK to 10.0.22621.0 and adds `CORTEX_STARTUP_PATHS` to the Windows wrapper "to match the Linux wrapper".

  [Changes.md](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **UNC paths.** On Windows, FileSystemPath gained Windows path support in 1.1, and "Paths beginning with a single `/` or `\` not followed by a drive letter are interpreted as UNC paths" — [Changes.md 1.1.0.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Windows prerequisites.** Gaffer requires the Microsoft Visual C++ Redistributable (vc_redist.x64). The docs suggest extracting the zip with 7-Zip for speed and use `C:\software\gaffer-<ver>-windows` as the example location — [doc/source/GettingStarted/InstallingGaffer](https://github.com/GafferHQ/gaffer/blob/main/doc/source/GettingStarted/InstallingGaffer/index.md)
- **macOS.** "Pre-built versions of Gaffer are currently unavailable on macOS" — [InstallingGaffer doc](https://github.com/GafferHQ/gaffer/blob/main/doc/source/GettingStarted/InstallingGaffer/index.md). The 1.7 build notes still include macOS-specific items (SSE2NEON added, Jemalloc removed on macOS), and there are recent macOS crash fixes, so building from source on Apple Silicon is being kept working — [Changes.md](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Packages.** 1.7.7.0 ships `gaffer-1.7.7.0-linux.tar.gz` (about 535 MB) and `gaffer-1.7.7.0-windows.zip` (about 471 MB). 1.6.21.8 ships `linux-gcc11` and `windows` packages — [GitHub Releases API](https://api.github.com/repos/GafferHQ/gaffer/releases)
- **Install layout.** "The Gaffer package is a self-contained directory". It is extracted and used in place, with no installer. Add `<install>\bin` to PATH to get the `gaffer` command — [InstallingGaffer](https://github.com/GafferHQ/gaffer/blob/main/doc/source/GettingStarted/InstallingGaffer/index.md); [SettingUpGafferCommand](https://github.com/GafferHQ/gaffer/blob/main/doc/source/GettingStarted/SettingUpGafferCommand/index.md)
- **Wrapper scripts.** `bin/gaffer.cmd` sets `HOME` from `USERPROFILE`, sets `PYTHONHOME` to the install root, prepends `bin` to PATH and defers to `bin/__private/_gaffer.py` to build the environment. `GAFFER_DEBUG` and `GAFFER_DEBUGGER` are supported — [bin/gaffer.cmd](https://github.com/GafferHQ/gaffer/blob/main/bin/gaffer.cmd)
- **Environment variables handled by `_gaffer.py`.**
  - Gaffer: `GAFFER_ROOT`, `GAFFER_STARTUP_PATHS`, `GAFFER_APP_PATHS`, `GAFFER_EXTENSION_PATHS`, `GAFFERUI_IMAGE_PATHS`, `GAFFEROSL_CODE_DIRECTORY`
  - Cortex: `CORTEX_STARTUP_PATHS`, `IECORE_*`
  - Renderers: `ARNOLD_ROOT`, `ARNOLD_PLUGIN_PATH`, `ARNOLD_ADP_DISABLE`, `DELIGHT`, `RMANTREE`, `CYCLES_ROOT`
  - Colour, shading and USD: `OCIO`, `OSL_SHADER_PATHS`, `PXR_PLUGINPATH_NAME`, `PXR_MTLX_STDLIB_SEARCH_PATHS`, `PXR_USD_WINDOWS_DLL_PATH`
  - Qt and Python: `QT_OPENGL`, `PYTHONNOUSERSITE`, `PYTHONPATH`
  - Machine learning: `GAFFERML_USE_CUDA`, `ONNX_ROOT`

  [bin/__private/_gaffer.py](https://github.com/GafferHQ/gaffer/blob/main/bin/__private/_gaffer.py)
- **Startup configuration.** The startup-config tutorials (`WorkingWithThePythonScriptingAPI/TutorialStartupConfig1-3`) document how studio Python config is loaded from `GAFFER_STARTUP_PATHS` — [repo doc tree](https://github.com/GafferHQ/gaffer/tree/main/doc/source/WorkingWithThePythonScriptingAPI)
- **Cycles on GPU.** CUDA and OptiX device support was added in 1.4, for gcc11 and Windows builds only — [Changes.md 1.4.0.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Building from source.** The build uses scons, gcc 11.2.1 and inkscape (for the UI graphics), with dependencies installed by `config/installDependencies.sh` from GafferHQ/dependencies. A Docker build container is available at github.com/GafferHQ/build. Docs need Sphinx 4.3.1+ — [README](https://github.com/GafferHQ/gaffer); [dependencies README](https://github.com/GafferHQ/dependencies)

### Inferences
- For a Windows classroom on shared storage, there are two options:
  - Extract one versioned `gaffer-1.7.x.x-windows` folder to a local path (for example by imaging or a deploy script), and point `GAFFER_STARTUP_PATHS` and `OSL_SHADER_PATHS` at a shared network config folder.
  - Run directly from a UNC share. This should work given the UNC path support, but load time will be slower because the install is about 470 MB zipped with many DLLs. Test it.
- Gaffer bundles its own USD and Python, so its `PXR_PLUGINPATH_NAME` and Python paths must be kept separate from Maya 2027's mayaUsd environment in any launcher. The `PXR_USD_WINDOWS_DLL_PATH` fix exists for exactly this kind of clash.
- `HOME` is rewritten to `%USERPROFILE%` with forward slashes, so per-user Gaffer prefs land in `%USERPROFILE%/gaffer`. That is a roaming-profile consideration for lab machines. This was not verified.

### Gaps
- I found no explicit minimum GPU or OpenGL version or RAM requirement in the README or docs I read. The `QT_OPENGL` handling in the wrapper hints that there is an OpenGL backend choice on Windows. Check `LaunchingGafferFirstTime` and the issues tracker for OpenGL and driver caveats (for example on remote desktop or virtual machines).
- I did not survey open Windows-specific issues on the GitHub tracker, so current known Windows bugs are unquantified.
- Whether the Arnold SDK bundled with MtoA for Maya 2027 can serve as `ARNOLD_ROOT` for Gaffer 1.7 was not verified. Gaffer 1.7 supports Arnold 7.4 and 7.5, and the Arnold version in Maya 2027's MtoA was not checked.
