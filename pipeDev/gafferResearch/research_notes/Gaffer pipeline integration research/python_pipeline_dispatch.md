# Gaffer: Python extension, pipeline configuration and farm dispatch

Researched 2026-11-24. Most facts come from the GafferHQ/gaffer `main` branch source and docs. Release dates come from the GitHub API. Current releases: **1.7.7.0 (2026-11-12)** and **1.6.21.8 (2026-11-12)**, both published the same day ([GitHub releases API](https://api.github.com/repos/GafferHQ/gaffer/releases)). Source links point at `main`, so behaviour in older releases may differ.

## Python API: scripting the graph, custom nodes, custom UI, Python version, headless apps

### Takeaway
Gaffer is a hybrid C++/Python application, and you can drive the whole graph from Python. Custom nodes can be written in pure Python by subclassing `Gaffer.ComputeNode` and overriding `affects`/`hash`/`compute`. Gaffer bundles its own Python: **3.11.14 in 1.7.x, with 3.13.16 already on `main` for the next major**. Headless work runs through the `gaffer execute`, `gaffer python`, `gaffer stats` and `gaffer dispatch` apps.

### Cited Findings
- **Bundled dependency versions in 1.7.0.0:** Python 3.11.14, Qt 6.5.8, PySide 6.5.8, USD 26.05, OpenColorIO 2.4.2 (ACES 2.0 configs added), MaterialX 1.39.4, Cycles 5.1.0, OpenVDB 12.1.1 — [Changes.md, 1.7.0.0 dependencies](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Unreleased `main` ("1.x.x.x relative to 1.7.x.x"):** Python 3.13.16, PySide/Qt 6.8.5, minimum Qt raised to 6, OpenImageIO 3.2.2.0, OCIO 2.5.2. GafferUI "is now accessed directly via PySide6 rather than via Qt.py" (Qt.py is still shipped but will be removed), and legacy PySide2/PyQt compatibility code is gone — [Changes.md](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Older bundled versions:** 1.6.x used Python 3.11.12, Qt/PySide 6.5.6 and USD 25.05.01. 1.5-era releases used PySide/Qt 5.15.14 and USD 24.08. 1.4-era releases used Python 3.10.13 and USD 23.11 — [Changes.md](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Launcher:** applications now run through a dedicated `gaffer` executable rather than `python`, but users should still launch with `bin/gaffer` (Linux) or `bin/gaffer.cmd` (Windows) (1.7.0.0) — [Changes.md](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Windows launch script:** `gaffer.cmd` sets `HOME=%USERPROFILE%` with forward slashes and sets `PYTHONHOME` to the install. It then runs `bin\python.exe bin/__private/_gaffer.py`, which builds the environment — [bin/gaffer.cmd](https://github.com/GafferHQ/gaffer/blob/main/bin/gaffer.cmd)
- **Bundled apps in `apps/`:** `browser`, `cli`, `dispatch`, `env`, `execute`, `gui`, `license`, `mcp`, `python`, `screengrab`, `stats`, `test`, `view` — [apps/ in source tree](https://github.com/GafferHQ/gaffer/tree/main/apps)
- **`gaffer mcp` (1.7.5.0):** launches and controls a headless Gaffer session for AI assistants. The PythonEditor gained an `mcpEnabled` setting, and the `Gaffer.MCP.Server`/`HTTPServer`/`StreamServer`/`Tool` classes were added — [Changes.md 1.7.5.0](https://github.com/GafferHQ/gaffer/blob/main/Changes.md); press coverage at [Digital Production, 2026-11-10](https://digitalproduction.com/2026/11/10/gaffer-1-7-6-painting-lighting-and-mcp/)
- **Farm command line:** both farm dispatchers execute a batch with `gaffer execute -script <file> -nodes <node> -frames <framelist> -context -<var> <repr(value)> ...`. Only context variables that differ from the script's own context are passed — [TractorDispatcher.py](https://github.com/GafferHQ/gaffer/blob/main/python/GafferTractor/TractorDispatcher.py); [LocalDispatcher.py](https://github.com/GafferHQ/gaffer/blob/main/python/GafferDispatch/LocalDispatcher.py)
- **Pure-Python custom node pattern** (`GafferTest.AddNode`):
  - Subclass `Gaffer.ComputeNode`.
  - Add `Gaffer.IntPlug(..., Direction.In/Out)` children.
  - Override `affects(input)`: call the base class, then append the outputs that input affects.
  - Override `hash(output, context, h)`: call `self["op1"].hash(h)` and so on for each input.
  - Override `compute(plug, context)`: call `plug.setValue(...)`.
  - Optionally override `correspondingInput()` and provide `enabledPlug()` for pass-through behaviour.
  - Register the type with `IECore.registerRunTimeTyped(AddNode, "GafferTest::AddNode")`.
  - [python/GafferTest/AddNode.py](https://github.com/GafferHQ/gaffer/blob/main/python/GafferTest/AddNode.py)
- **Custom dispatchers and task nodes can be pure Python too:** `LocalDispatcher`, `PythonCommand`, `SystemCommand`, `Wedge`, `TaskSwitch`, `TaskContextVariables` and `TractorDispatcher` are all `.py` files under `python/GafferDispatch/` and `python/GafferTractor/` — [source tree](https://github.com/GafferHQ/gaffer/tree/main/python/GafferDispatch)
- **Metadata API (1.6/1.7 era):**
  - `Metadata.registerNode()` and `registerValues()` accept dictionaries, which "should be preferred to the previous list-based" form.
  - Wildcard string targets are supported.
  - `ValueFunctions` now receive a `target` argument (1.7.0.0 API change).
  - `MetadataAlgo.createPlugFromMetadata()` was added.
  - [Changes.md](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Custom widgets:** the standard way to swap a widget is to register `plugValueWidget:type` metadata. The built-in project startup does this, for example `Gaffer.Metadata.registerValue(renderPassPlug["value"], "plugValueWidget:type", "GafferSceneUI.RenderPassEditor._RenderPassPlugValueWidget")` — [startup/gui/project.py](https://github.com/GafferHQ/gaffer/blob/main/startup/gui/project.py)
- **Menus:** you add node-menu entries with `GafferUI.NodeMenu.acquire(application).append(path, creatorFn, postCreator=..., searchText=...)`. A "custom node" can just be a `Gaffer.Reference` loading a `.grf`, with its own icon, colour and name, and needs no compiled code — [Tutorial: Startup Config 3](https://github.com/GafferHQ/gaffer/blob/main/doc/source/WorkingWithThePythonScriptingAPI/TutorialStartupConfig3/index.md)
- **External Python packages:**
  - Gaffer sets `PYTHONNOUSERSITE=1`, so the user site-packages directory is ignored. Set `PYTHONNOUSERSITE=0` to revert ([Changes.md](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)).
  - The launcher *prepends* `$GAFFER_ROOT/python` to `PYTHONPATH`, and each extension's `python/` folder is *appended*. Third-party packages therefore go on `PYTHONPATH` or in an extension `python/` folder, and they must be built for the bundled Python ABI (3.11 for 1.7) ([bin/__private/_gaffer.py](https://github.com/GafferHQ/gaffer/blob/main/bin/__private/_gaffer.py)).
- **Windows environment variable case:**
  - `Gaffer.environment()` returns all environment variables and, unlike `os.environ`, preserves case on Windows.
  - A fix in LocalDispatcher, SystemCommand and `gaffer env` stopped environment variable names being upper-cased on Windows (#6371).
  - [Changes.md](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **`FileSystemPath`** implements `os.PathLike`, so it can be passed straight to Python's standard filesystem functions — [Changes.md](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)

### Inferences
- Gaffer 1.7 bundles Python 3.11, the same minor version as Maya 2025/2026. Pure-Python pipeline libraries (path resolvers, ShotGrid API, the pipe's own `pipeEnv`-style modules) should import unchanged. Compiled wheels must match the version Gaffer bundles, and Gaffer's next major moves to 3.13, so pin a Gaffer version per show or term.
- Run a farm or render service with the `gaffer execute -script -nodes -frames -context` contract that Gaffer's own dispatchers use. A custom render service can call that same command line directly.
- `gaffer mcp` offers a supported headless control channel that a pipeline tool or AI agent could drive. It is new (1.7.5), so treat it as experimental.

### Gaps
- I did not fetch the `gaffer python`, `gaffer execute` or `gaffer stats` argument references (the generated CommandLineReference). Flags beyond `-script/-nodes/-frames/-context/-ignoreScriptLoadErrors` are unverified here.
- I found no official prose tutorial on writing Python ComputeNodes or custom PlugValueWidgets. The pattern above is taken from test code.

## Configuration: startup paths, extension paths, per-app startup folders, context variables, string substitution

### Takeaway
Gaffer configures itself with Python startup scripts found on `GAFFER_STARTUP_PATHS`, one subfolder per app (`gui`, `execute`, `dispatch` and so on). Studios add global context variables (the `project:*` pattern), bookmarks, menus and dispatcher defaults there. `GAFFER_EXTENSION_PATHS` (added in 0.52.2.0) bundles a whole extension root in one entry.

### Cited Findings
- **Default search paths set by the launcher:**
  - `~/gaffer/startup` is prepended to `GAFFER_STARTUP_PATHS` and `$GAFFER_ROOT/startup` is appended.
  - `~/gaffer/apps` and `$GAFFER_ROOT/apps` are on `GAFFER_APP_PATHS`.
  - `~/gaffer/shaders` is on `OSL_SHADER_PATHS`.
  - [bin/__private/_gaffer.py](https://github.com/GafferHQ/gaffer/blob/main/bin/__private/_gaffer.py)
- **Startup configs:** Gaffer "consists of multiple applications ... such as GUI, Dispatch, Execute, and Stats". Each app loads any number of Python scripts ("startup configs") from one or more paths, for example `~/gaffer/startup/gui/customVariables.py` — [Tutorial: Startup Config 1](https://github.com/GafferHQ/gaffer/blob/main/doc/source/WorkingWithThePythonScriptingAPI/TutorialStartupConfig1/index.md)
- **Startup folder layout:** the startup tree has per-app folders (`startup/gui/` holds `bookmarks.py`, `menus.py`, `layouts.py`, `project.py`, `ocio.py`, `usd.py`, `localDispatcher.py` and others) and per-module folders (`startup/GafferScene/`, `startup/GafferDispatch/` and so on) for compatibility shims — [startup/ tree](https://github.com/GafferHQ/gaffer/tree/main/startup)
- **Global context variables:** the documented recipe is to connect to `application.root()["scripts"].childAddedSignal()`, then call `script["variables"].addMember("project:resources", IECore.StringData("${GAFFER_ROOT}/resources/"), "projectResources")` and `Gaffer.MetadataAlgo.setReadOnly(...)` on the variable name. The docs suggest building pipeline paths such as `/${showPath}/${sequencePath}/${shotPath}/${assetPath}` from these variables. Because they are plugs, they are saved in the `.gfr` and travel with the script to other machines and the farm — [Tutorial: Startup Config 1](https://github.com/GafferHQ/gaffer/blob/main/doc/source/WorkingWithThePythonScriptingAPI/TutorialStartupConfig1/index.md)
- **Built-in project variables** (from `startup/gui/project.py`):
  - Every script gets `project:name` (default `"default"`) and `project:rootDirectory` (default `$HOME/gaffer/projects/${project:name}`).
  - Bookmarks for "Project", scripts (`${project:rootDirectory}/scripts`) and references (`${project:rootDirectory}/references`) are set up.
  - `jobName` userDefault is set to `${script:name}` and `jobsDirectory` to `${project:rootDirectory}/dispatcher/<local|tractor|flamenco>` for LocalDispatcher, TractorDispatcher and FlamencoDispatcher.
  - The file notes it "is shared with the `dispatch` app", so it guards UI imports with `if "GafferUI" in sys.modules`.
  - [startup/gui/project.py](https://github.com/GafferHQ/gaffer/blob/main/startup/gui/project.py)
- **Defaults via userDefault metadata:** any plug's default can be overridden by registering `userDefault` metadata, for example `Gaffer.Metadata.registerValue(GafferArnold.ArnoldTextureBake, "bakeDirectory", "userDefault", "${project:rootDirectory}/bakedTextures/${script:name}/")` — [startup/gui/project.py](https://github.com/GafferHQ/gaffer/blob/main/startup/gui/project.py)
- **Bookmarks:**
  - `GafferUI.Bookmarks.acquire(application[, category="image"|"script"|"reference"|"font"|"shader"])`, then `.add(name, path)` or `.setDefault(path_or_callable)`.
  - Bookmarks live per application, not per graph.
  - On Windows, the stock config enumerates drive letters with `GetLogicalDrives()` and adds a `Drives/X:` bookmark for each.
  - [startup/gui/bookmarks.py](https://github.com/GafferHQ/gaffer/blob/main/startup/gui/bookmarks.py); [Tutorial: Startup Config 2](https://github.com/GafferHQ/gaffer/blob/main/doc/source/WorkingWithThePythonScriptingAPI/TutorialStartupConfig2/index.md)
- **String substitution syntax:** `#`/`####` for the (padded) frame, `~` for home, `${name}` for **both context variables and environment variables**, and `\\` to escape — [String Substitution Syntax reference](https://github.com/GafferHQ/gaffer/blob/main/doc/source/Reference/ScriptingReference/StringSubstitutionSyntax/index.md)
- **Startup config history:** `GAFFER_STARTUP_PATHS` also feeds IECoreArnold/IECoreDelight config files (support added in a 1.5-era release) — [Changes.md](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Hiding UI:** `GAFFERCYCLES_HIDE_UI=1` hides Cycles nodes and presets, and `GAFFERUSD_HIDE_LIGHT_UI=1` hides USDLight nodes — [Configuring Gaffer for Third-Party Tools](https://github.com/GafferHQ/gaffer/blob/main/doc/source/GettingStarted/ConfiguringGafferForThirdPartyTools/index.md); [Changes.md](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Renderer and farm discovery:**
  - Arnold needs `ARNOLD_ROOT` (on Windows via `setx ARNOLD_ROOT ...`), 3Delight needs `DELIGHT`, and RenderMan needs `RMANTREE`.
  - Tractor is listed as a supported third-party tool.
  - The launcher reads the Arnold version from `ai_version.h` and puts `$GAFFER_ROOT/arnold/<ARCH.MAJOR>` on `GAFFER_EXTENSION_PATHS`.
  - It also disables Arnold ADP telemetry by default (`ARNOLD_ADP_DISABLE=1`).
  - [Configuring Gaffer for Third-Party Tools](https://github.com/GafferHQ/gaffer/blob/main/doc/source/GettingStarted/ConfiguringGafferForThirdPartyTools/index.md); [_gaffer.py](https://github.com/GafferHQ/gaffer/blob/main/bin/__private/_gaffer.py)

### Inferences
- **Config to replicate for the Scout pipe:** a studio extension's `startup/gui/` and `startup/dispatch/` (and `startup/execute/`, where farm jobs need it) can do the following:
  1. Add `pipe:root` (= `${PIPE_SCRATCH}` or `${PIPE_H}`), `pipe:show`, `pipe:asset` and `pipe:shot` as read-only global variables.
  2. Override `project:rootDirectory`.
  3. Set the dispatcher `jobsDirectory` userDefault.
  4. Add Project/Shot bookmarks.

  Plug values such as `${PIPE_SCRATCH}/...` expand environment variables at evaluation time, so the same `.gfr` works on T7, SharePoint-synced or UNC targets, provided each machine sets the variable.
- The default `project:rootDirectory` points into `$HOME` (the Windows user profile), so a pipeline should override it. Otherwise dispatcher jobs and bakes land in each user's profile.
- Code shared between the gui and dispatch/execute apps must not import GafferUI unconditionally. This is the same guard pattern Gaffer itself uses.

### Gaps
- I did not verify whether startup scripts for a custom script template or "new script" default exist (for example a default `.gfr` loaded on File > New). I found no doc for it.
- I did not confirm the exact per-app folder names for every app beyond gui, nor whether `execute` reads `startup/execute/`. The tutorial names the apps, and this follows Gaffer's per-app convention, but it is unverified.

## Extensions: packaging, Python vs C++, ABI

### Takeaway
An extension is a folder on `GAFFER_EXTENSION_PATHS` with conventional subfolders (`python/`, `startup/`, `lib/`, `bin/`, `apps/`, `graphics/`, `glsl/`, `shaders/`). Python-only extensions need no compiling. C++ extensions must be built against the exact Gaffer major version, since ABI breaks happen between majors and occasionally within one.

### Cited Findings
- **Folder mapping:** for each `GAFFER_EXTENSION_PATHS` entry, the launcher appends:
  - `lib/` to the library path (and to `IECORE_DLL_DIRECTORIES` on Windows)
  - `bin/` to `PATH`
  - `python/` to `PYTHONPATH`
  - `apps/` to `GAFFER_APP_PATHS`
  - `graphics/` to `GAFFERUI_IMAGE_PATHS`
  - `glsl/` to `IECOREGL_SHADER_PATHS`
  - `shaders/` to `OSL_SHADER_PATHS`

  It *prepends* `startup/` to `GAFFER_STARTUP_PATHS` — [bin/__private/_gaffer.py, setUp3rdPartyExtensions](https://github.com/GafferHQ/gaffer/blob/main/bin/__private/_gaffer.py)
- **History:** `GAFFER_EXTENSION_PATHS` was added "for easy configuration of 3rd party extensions" in 0.52.2.0 — [Changes.md](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Gaffer's own extensions use this mechanism:** GafferArnold and GafferRenderMan are loaded by prepending `$GAFFER_ROOT/arnold/<ver>` or the RenderMan plugin root to `GAFFER_EXTENSION_PATHS` — [_gaffer.py](https://github.com/GafferHQ/gaffer/blob/main/bin/__private/_gaffer.py)
- **Exporting Box-based tools as nodes:** `Gaffer.ExtensionAlgo.exportNode()`/`exportNodeUI()` (added in 1.3/1.4) turn a Box authored in the UI into a Python node class. In 1.7.0.0 the base class of exported extension nodes changed from SubGraph to DependencyNode, and exported extensions now get `childNodesAreReadOnly` metadata — [Changes.md](https://github.com/GafferHQ/gaffer/blob/main/Changes.md); [python/Gaffer/ExtensionAlgo.py](https://github.com/GafferHQ/gaffer/blob/main/python/Gaffer/ExtensionAlgo.py)
- **ABI policy:** an ABI break inside a minor release was "not normally allowed without a change of major version", and the IECoreArnold `SubstitutionFunction` change was a "rare exception". The convention is ABI stability within a major version (`1.N`) — [Changes.md](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Loading old scripts:** 1.7.0.0 removed the ability to load `.gfr` files from before 0.45.0.0 ("resave from Gaffer 1.6") — [Changes.md](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Build toolchain:** 1.7 added Nanobind 2.12.0 to its dependencies — [Changes.md](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Real-world extension layouts:**
  - GafferDeadline is installed by adding its repo root to `GAFFER_EXTENSION_PATHS`. It has `python/GafferDeadline/*.py` and a startup folder ([GafferDeadline README](https://github.com/hypothetical-inc/GafferDeadline); tree mirrored in [RVXStudio/ayon-gaffer deploy/GafferDeadline](https://github.com/RVXStudio/ayon-gaffer)).
  - Community examples: [BHGCGafferCameraGuides](https://github.com/BrianHanke/BHGCGafferCameraGuides) (camera guide overlays, pushed 2026-09) and [Gaffer-GafferCortex-extension](https://github.com/hradec/Gaffer-GafferCortex-extension), which keeps the deprecated GafferCortex alive as an extension.

### Inferences
- A pure-Python Scout extension would be one folder on the share, for example `${PIPE_ROOT}\gaffer\scoutGaffer\{python,startup\gui,startup\dispatch,graphics,apps}`, added to `GAFFER_EXTENSION_PATHS` by the launcher or the render service. No compiling is needed, and it works across Gaffer minor updates, unless an API call it uses is removed in a new major (watch "Breaking Changes" in Changes.md).
- Avoid C++ extensions unless strictly needed. Each Gaffer major (1.6 to 1.7 to the next) would need a rebuild with MSVC and matching dependencies.

### Gaps
- I found no official "Extending Gaffer" doc page in the current doc tree. The layout above is taken from the launcher code, not from prose docs.

## Asset resolution and paths: USD resolver, variables, Windows/UNC, case sensitivity

### Takeaway
Gaffer reads and writes USD through Cortex's IECoreUSD (SceneReader/SceneWriter, plus GafferUSD nodes) and puts its own USD plug-ins on `PXR_PLUGINPATH_NAME`. A studio ArResolver is therefore a standard USD plug-in made visible through that variable. I found no Gaffer-specific resolver docs. Paths in plugs expand `${ENV}` and context variables. Windows-specific handling covers environment variable case, DLL search paths and drive bookmarks, and I found nothing documented on UNC.

### Cited Findings
- **USD environment set by the launcher:** it prepends `$GAFFER_ROOT/resources/IECoreUSD` to `PXR_PLUGINPATH_NAME` and the MaterialX library to `PXR_MTLX_STDLIB_SEARCH_PATHS`. On Windows it sets `PXR_USD_WINDOWS_DLL_PATH=""` to "Prevent USD from adding entries from `PATH` to Python binary search paths". Arnold's and RenderMan's USD plug-ins are also prepended to `PXR_PLUGINPATH_NAME` — [_gaffer.py](https://github.com/GafferHQ/gaffer/blob/main/bin/__private/_gaffer.py)
- **Bundled USD:** USD 26.05 in Gaffer 1.7 — [Changes.md](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Custom resolver discussion:** a gaffer-dev thread on loading caches "in a production/robust way" proposes a "custom asset resolver for OpenUSD that talks to shotgrid/flow for 'ground truth' publishes". It notes SceneReader "is too basic here to fine-tune with just a `fileName` string" — [gaffer-dev: Loading in caches in a production/robust way](https://groups.google.com/g/gaffer-dev/c/4Sum6eKTZPg)
- **Older USD behaviour:** a 2018 gaffer-dev thread says only SceneReader/SceneWriter "talk" USD, and loaded USD becomes a native Gaffer scene that loses its composition — [gaffer-dev: Layered USD in Gaffer and Scene Assembly](https://groups.google.com/g/gaffer-dev/c/btfWzh2szwk). This is old and partly superseded by later GafferUSD nodes and PointInstancer USD export (1.7) per [Changes.md](https://github.com/GafferHQ/gaffer/blob/main/Changes.md).
- **Resolver plug-ins in general:** with no ArResolver plug-in, USD falls back to the default search-path resolver. Custom resolvers register via `AR_DEFINE_RESOLVER` and plug-in discovery — [OpenUSD Ar docs](https://openusd.org/release/wp_ar2.html)
- **Windows path and environment handling:**
  - Environment variable names are no longer upper-cased on Windows by LocalDispatcher, SystemCommand or `gaffer env` (#6371).
  - `Gaffer.environment()` preserves case.
  - `HOME` is set to `%USERPROFILE%` with forward slashes by `gaffer.cmd`.
  - [Changes.md](https://github.com/GafferHQ/gaffer/blob/main/Changes.md); [bin/gaffer.cmd](https://github.com/GafferHQ/gaffer/blob/main/bin/gaffer.cmd)
- **Escaped substitutions:** the Render node now translates string substitutions escaped with backslashes correctly (e.g. `\\<attr:user:texturePath\\>`). Backslash is the escape character in Gaffer string substitution — [Changes.md](https://github.com/GafferHQ/gaffer/blob/main/Changes.md); [String Substitution Syntax](https://github.com/GafferHQ/gaffer/blob/main/doc/source/Reference/ScriptingReference/StringSubstitutionSyntax/index.md)

### Inferences
- Because `\` is Gaffer's substitution escape character, Windows paths in plugs should use forward slashes (`G:/scratch/...`, `//server/share/...`). Raw backslash UNC paths (`\\server\share`) are likely to be mangled by substitution. This is an inference from the documented escape rule plus the launcher's own forward-slash `HOME`, not a documented UNC statement.
- The Scout pipe already decided on relative USD paths and `$PIPE_SCRATCH` on Maya stage nodes. In Gaffer the equivalent is `${PIPE_SCRATCH}/...` in SceneReader `fileName`, or relative asset paths inside the USD layers resolved by USD's default resolver. Neither needs a custom ArResolver.

### Gaps
- No primary source confirms how Gaffer handles UNC paths, mapped-drive vs UNC equivalence, or case-insensitive path comparison on Windows (for example in file browsers or Reference reloading). Hand-test before relying on it.
- I found no public studio ArResolver that ships specifically for Gaffer.

## Dispatch and farm: TaskNodes, LocalDispatcher, Tractor, Deadline, OpenCue, custom dispatchers

### Takeaway
GafferDispatch builds a tree of `TaskBatch` objects from TaskNode dependencies. A dispatcher subclass implements `_doDispatch(rootBatch)` and turns each batch into a farm task that runs `gaffer execute`.
- **Official dispatchers:** Local, Tractor, and (new in 1.7) Flamenco.
- **Deadline:** covered by the community/Hypothetical Inc. GafferDeadline, which is actively maintained (commits Oct–Nov 2026, latest release 0.59.0.1 from July 2025).
- **OpenCue:** a dispatcher exists but is stale (2022).

### Cited Findings
- **LocalDispatcher plugs:** `executeInBackground` (default False), `ignoreScriptLoadErrors` and `environmentCommand`. In the background it spawns subprocesses, and on Windows uses `shell=True` when an `environmentCommand` is set. Its arguments are `shlex.split(environmentCommand) + ["gaffer","execute",...]` — [LocalDispatcher.py](https://github.com/GafferHQ/gaffer/blob/main/python/GafferDispatch/LocalDispatcher.py)
- **TractorDispatcher as a reference implementation** for a custom dispatcher:
  - Subclasses `GafferDispatch.Dispatcher` and adds plugs (`service`, `envKey`, `startPaused`).
  - Implements `_doDispatch(self, rootBatch)` and walks `batch.preTasks()` recursively.
  - Each batch becomes one task, de-duplicated so diamond dependencies become Tractor `Instance`s.
  - `batch.frames()` is compressed with `IECore.frameListFromList`.
  - `batch.context()["dispatcher:scriptFileName"]` gives the saved script.
  - Per-node settings are read from `batch.node()["dispatcher"]["tractor"]` (service, tags).
  - Exposes a `preSpoolSignal()` for studio hooks that modify the job before spooling.
  - Writes `job.alf` into `self.jobDirectory()` for debugging.
  - [TractorDispatcher.py](https://github.com/GafferHQ/gaffer/blob/main/python/GafferTractor/TractorDispatcher.py)
- **Recent dispatcher changes (1.6-era):** TractorDispatcher gained `startPaused`, Tractor and Local task names gained a context variable summary, and `Dispatcher.TaskBatch.name()` was added. Separately, `gaffer dispatch` dropped restrictions that blocked dispatching Switch/ContextVariables nodes — [Changes.md](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **FlamencoDispatcher (1.7.0.0):** a new node for Blender's Flamenco farm manager, and a third official dispatcher (pure Python, in `GafferFlamenco`) — [Changes.md](https://github.com/GafferHQ/gaffer/blob/main/Changes.md); [startup/gui/project.py](https://github.com/GafferHQ/gaffer/blob/main/startup/gui/project.py)
- **File-management task nodes (1.7.0.0):** FileList, CopyFiles, DeleteFiles and RenameFiles, which are useful for publish steps — [Changes.md](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)
- **Wedge:** a `TaskContextProcessor` with modes FloatRange, IntRange, ColorRange, FloatList, IntList and StringList. It sets the `wedge:value`/`wedge:index` context variables, so one upstream task becomes N context variants — [Wedge.py](https://github.com/GafferHQ/gaffer/blob/main/python/GafferDispatch/Wedge.py)
- **Other task utilities:** PythonCommand, SystemCommand, TaskSwitch and TaskContextVariables are pure-Python task utilities in GafferDispatch — [source tree](https://github.com/GafferHQ/gaffer/tree/main/python/GafferDispatch)
- **GafferDeadline basics** (Hypothetical Inc., Eric Mehl; BSD-3):
  - Three parts: a Gaffer dispatcher, a Deadline plugin (copied to `<repo>/custom/plugins/Gaffer`), and `gaffer_batch_dependency.py`, which Deadline runs periodically to release tasks whose Gaffer DAG dependencies are complete.
  - It auto-selects frame-to-frame dependencies where possible, otherwise scripted task dependencies or job-to-job per node, and each node can override this ("Full Job" is safest).
  - Environment variables: `GAFFER_EXTENSION_PATHS` (repo root), `DEADLINE_DEPENDENCY_SCRIPT_PATH` and `DEADLINE_PATH`.
  - The Deadline plugin pins the submitting Gaffer version and fails if no matching executable is configured in `Gaffer.param`.
  - Tested on Linux and Windows.
  - [hypothetical-inc/GafferDeadline README](https://github.com/hypothetical-inc/GafferDeadline)
- **GafferDeadline maintenance:**
  - Created 2019-06 with 41 stars.
  - Releases: 0.58.0.0 (2024-08-17, added the `/Dispatch/Deadline Dispatch` menu "for compatibility with Gaffer 1.4"), 0.59.0.0 (2024-09-11), 0.59.0.1 (2025-07-08, fixed Wedge dependencies). The unreleased 0.59.0.2 fixes Python 3 in the dependency script and context substitution in DeadlineTask.
  - Last commit 2026-11-18 ("DeadlineTask" dependency PR #96).
  - It adds `extraDeadlineSettings`/`extraEnvironmentVariables` (`AtomicCompoundDataPlug`, settable via `userDefault` metadata or expressions) and a `DeadlineTask` node.
  - [GitHub API: releases](https://api.github.com/repos/hypothetical-inc/GafferDeadline/releases); [commits](https://api.github.com/repos/hypothetical-inc/GafferDeadline/commits); [GafferDeadline Changes.md](https://github.com/hypothetical-inc/GafferDeadline/blob/main/Changes.md)
- **Other Deadline implementations:** a Thinkbox forum post says Whiskytree runs its own in-house Deadline plugin for Gaffer — [Thinkbox forum: Gaffer support](https://forums.thinkboxsoftware.com/t/gaffer-support/13511). `ericmehl/GafferDeadline` is the author's fork — [ericmehl/GafferDeadline](https://github.com/ericmehl/GafferDeadline)
- **OpenCue:** [boberfly/GafferOpenCue](https://github.com/boberfly/GafferOpenCue) is an "OpenCue Dispatcher for Gaffer" (17 stars) whose last push was 2022-10-28. It is likely stale against Gaffer 1.4+ dispatcher API changes.
- **gaffer-dev threads:** "render farm submission workflow" covers how dispatchers are structured for custom farms — [gaffer-dev: render farm submission workflow](https://groups.google.com/g/gaffer-dev/c/IXZtQt3L9uc/m/qCQjTX1bBQAJ); "Chaining dispatcher nodes" — [gaffer-dev](https://groups.google.com/g/gaffer-dev/c/YbhysX3riJg)

### Inferences
- For the Scout render manager, two routes:
  - **(a)** Write a ~150-line pure-Python `ScoutDispatcher(GafferDispatch.Dispatcher)` modelled on TractorDispatcher. Walk `rootBatch`, and per batch submit `gaffer execute -script <jobDir copy> -nodes <n> -frames <f> -context ...` to the render service queue, with dependency edges from `preTasks()`.
  - **(b)** Use `LocalDispatcher` with `executeInBackground` and an `environmentCommand` wrapper for single-machine runs.
- If Deadline is adopted, GafferDeadline is the only maintained option and is already used in AYON production.
- Dispatch copies the script into `jobsDirectory`, which the default config puts under `${project:rootDirectory}/dispatcher/...`. Point it at shared storage that farm nodes can see, or keep it local for a single-workstation queue.

### Gaps
- I did not verify the exact `GafferDispatch.Dispatcher` C++ base API (for example `frameRange` and `batchSize` handling, or the `jobDirectory()` naming) beyond what TractorDispatcher uses.
- I found no official Gaffer Deadline dispatcher, and no evidence of AWS Deadline Cloud support for Gaffer.

## Pipeline integration examples: AYON, ShotGrid, Prism, studios

### Takeaway
Two community AYON addons exist:
- **RVXStudio/ayon-gaffer:** production-used, with publishing and Deadline renders.
- **sosoyan/ayon-gaffer:** context switching, publishing scenes and Reference boxes.

There is an unofficial ShotGrid Toolkit engine (tk-gaffer, 2021, tested on Gaffer 0.59 on Windows). I found no Ynput-official addon and no Prism integration. Image Engine and Cinesite are the main studio users.

### Cited Findings
- **RVXStudio/ayon-gaffer** (created 2024-03, pushed 2026-11-04):
  - Creates publish types through the AYON publisher, sets the frame range, and publishes renders via Deadline only ("no local renders").
  - Works with AYON, not OpenPype, and may need small ayon-core changes.
  - Workflow: RenderSettings box, then RenderLayer box, then a publish node created from the `Ayon>Create` menu.
  - Ships versioned Box `.gfr` nodes and vendors GafferDeadline under `client/ayon_gaffer/deploy/`.
  - "Used in production, but it's still very much under development."
  - [RVXStudio/ayon-gaffer](https://github.com/RVXStudio/ayon-gaffer)
- **sosoyan/ayon-gaffer** (created 2025-01, pushed 2026-08-17):
  - A "minimal" addon with an AYON top menu.
  - Switches the AYON context on the fly inside one Gaffer script (a multi-shot template), applies script settings, variables and tags on task switch, and creates/loads/publishes Gaffer scenes and Reference boxes.
  - Render publishing is not done yet.
  - Its create/load/publish plugins are derived from RVXStudio's.
  - [sosoyan/ayon-gaffer](https://github.com/sosoyan/ayon-gaffer)
- **Ynput:** a GitHub search found no official `ynput/ayon-gaffer` (the URL returns 404) — [GitHub search](https://api.github.com/search/repositories?q=ayon-gaffer)
- **tk-gaffer:**
  - A ShotGrid Toolkit engine by Diego Garcia Huerta, adding a ShotGrid menu.
  - Hooks for tk-multi-workfiles2, snapshot, loader2, publish2, breakdown and setframerange.
  - "Developed and tested in Windows 10 using Gaffer version 0.59.0", "has not been used in production".
  - Last pushed 2021-10.
  - [diegogarciahuerta/tk-gaffer](https://github.com/diegogarciahuerta/tk-gaffer)
- **Prism:** the plugin list reviewed shows Maya, Houdini, Blender, Nuke and others, with no Gaffer plugin found — [Prism plugins docs](https://prism-pipeline.com/docs/latest/plugins/) (search result only, page not fully read)
- **Studios:**
  - Gaffer has been "used and extended in production at Image Engine since [it was] open-sourced in 2011" — [GafferHQ/ImageEngine repo](https://github.com/ImageEngine/gaffer)
  - Cinesite describes Gaffer as "fully developed and supported by the Cinesite group ... used within the Cinesite Group to produce both Visual Effects and Feature Animation, and has a growing user base in other studios" — [Cinesite Technology](https://cinesite.com/technology/)
  - Whiskytree used Gaffer with its own Deadline plugin — [Thinkbox forum](https://forums.thinkboxsoftware.com/t/gaffer-support/13511)
  - The SIGGRAPH talk "Gaffer: Open Source Lookdev, Lighting, and Automation" was given by Kaufman and Haddon — [SIGGRAPH History Archive](https://history.siggraph.org/experience/gaffer-open-source-lookdev-lighting-and-automation-by-kaufman-and-haddon)
- **Publishing building blocks inside Gaffer:**
  - SceneWriter/USD export, including PointInstancer export to USD (1.7).
  - ImageWriter for EXR.
  - The 1.7 file task nodes (CopyFiles, RenameFiles).
  - The DataStore node (1.7) for large data stored alongside a script.
  - [Changes.md](https://github.com/GafferHQ/gaffer/blob/main/Changes.md)

### Inferences
- No integration fits the Scout pipe as-is. The AYON addons are the best code to borrow patterns from:
  - versioned Box `.gfr` "pipeline nodes";
  - a top-level menu from a startup gui script;
  - context switching that sets script variables;
  - Deadline publishing via GafferDeadline.
- A ShotGrid hookup would be pipe-side Python (shotgun_api3 is pure Python, so it can go on `PYTHONPATH`), called from a PythonCommand task or a post-dispatch hook, rather than reviving tk-gaffer.
- Gaffer is free with no licence server and ships a Windows build, which suits school or lab deployment. Arnold rendering still needs Arnold licensing, and Cycles is bundled and free.

### Gaps
- I found no public detail on Image Engine's or Cinesite's internal Gaffer pipelines: their dispatchers, asset systems or resolvers.
- I found no public evidence of schools or universities using Gaffer in teaching. I did not search this deeply.
- I did not open the Prism plugin list page to confirm there is no Gaffer plugin.
