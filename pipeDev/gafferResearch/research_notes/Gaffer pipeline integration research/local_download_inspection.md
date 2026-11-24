# Local inspection: the Gaffer build the studio downloaded (2026-11-24)

Primary source: `C:\Users\scout\Downloads\gaffer-1.7.7.0-windows.zip` (downloaded 2026-11-23,
472 MB zipped, 51,510 files, 1.65 GB unpacked; files dated 2026-11-12). Inspected by listing
the archive and reading text files inside it (`unzip -l` / `unzip -p`); nothing was extracted
or run. Also checked the Maya 2027 MtoA install on the same machine
(`C:\Program Files\Autodesk\Arnold\maya2027`).

## What the 1.7.7.0 Windows build contains
- Top level: `apps, arnold, bin, cycles, doc, fonts, glsl, graphics, include, libs, materialX,
  openColorIO, ops, plugin, python, qt, renderMan, resources, shaders, share, startup`, plus
  `DLLs` and `Lib` (an embedded CPython).
- Python **3.11** (`python311.dll`, `boost_python311.dll`). Maya 2027's Python, checked on
  this machine (`mayapy -c "import sys; print(sys.version)"`), is **3.13.9**. So Maya-side
  pipeline modules shared with Gaffer must stay compatible with 3.11 until Gaffer's next
  major (main moves to 3.13).
- Qt **6** (`Qt6Core.dll`), TBB 12, OpenImageIO, OpenColorIO, Alembic (+ `abcls`, `abcconvert`
  and other Alembic command-line tools in `bin`), MaterialX (full set: Core, Format, GenGlsl,
  GenMdl, GenMsl, GenOsl, Render...), OSL.
- USD **0.26.5** (`include/pxr/pxr.h`: PXR_MAJOR 0, MINOR 26, PATCH 5). Maya 2027 on this
  machine runs mayaUsd **0.37.0** with USD **0.25.11** (checked with `pxr.Usd.GetVersion()`
  in mayapy). Maya writes USD files from 25.11 and Gaffer reads them with 26.05, which is
  the safe direction. USD Gaffer writes back for Maya to read goes from newer to older;
  usually fine for plain .usda/.usd, but worth a hand test, especially for new schemas.
- Renderer modules shipped: `arnold/7.4/` and `arnold/7.5/` (GafferArnold, GafferArnoldUI,
  IECoreArnold, arnoldPlugins, startup), `cycles/` (Cycles itself bundled, with its licence
  readme), `renderMan/`. 3Delight: support is set up only if the `DELIGHT` env var points at
  a separate 3Delight install.
- Apps (`apps/`): `browser, cli, dispatch, env, execute, gui, license, mcp, python,
  screengrab, stats, test, view`.

## How the launcher sets up the environment (`bin/gaffer.cmd` -> `bin/__private/_gaffer.py`)
- `gaffer.cmd` sets `PYTHONHOME` to the install and runs the bundled `python.exe` on
  `_gaffer.py`, which sets the environment, then launches the app.
- Sets `GAFFER_ROOT`; `GAFFER_STARTUP_PATHS` and `CORTEX_STARTUP_PATHS` get
  `~/gaffer/startup` **prepended** and `<GAFFER_ROOT>/startup` appended, so anything a
  studio puts on these variables (before launching) is also searched. User config therefore
  lives in `%USERPROFILE%\gaffer\startup` by default (HOME is set from USERPROFILE).
- `GAFFER_EXTENSION_PATHS` is the mechanism the Arnold module itself uses (the matching
  `arnold/<ARCH>.<MAJOR>` folder is prepended to it), i.e. studio extensions can be packaged
  the same way.
- OSL: `OSLHOME` = install; compiled OSL code cached in `~/gaffer/oslCode`
  (`GAFFEROSL_CODE_DIRECTORY`).
- USD: `IECOREUSD_WRITE_CONFORMANT_OSL_SHADERS=1` and
  `IECOREUSD_WRITE_CONFORMANT_RENDERMAN_ATTRIBUTES=1` by default (USD written by Gaffer
  uses conformant shader/attribute naming). `PXR_USD_WINDOWS_DLL_PATH` set on Windows.
- Cycles: uses `CYCLES_ROOT` or the bundled `cycles` folder.
- **Arnold is NOT bundled.** `setUpArnold()` does nothing unless `ARNOLD_ROOT` is set. It
  reads `ARNOLD_ROOT/include/ai_version.h` for ARCH.MAJOR (e.g. 7.5) and loads
  `arnold/7.5` from Gaffer; if Gaffer has no module for that version it warns "GafferArnold
  extension not available for Arnold X.Y". It then puts `ARNOLD_ROOT/bin` on PATH,
  `ARNOLD_ROOT/python` on PYTHONPATH, `ARNOLD_ROOT/plugins` on ARNOLD_PLUGIN_PATH, and the
  usdArnold resources on PXR_PLUGINPATH_NAME. It sets `ARNOLD_ADP_DISABLE=1` (Autodesk
  analytics off) unless the studio opts in.
- Arnold version matching on this machine: MtoA for Maya 2027 ships Arnold core **7.5.2.0**
  (`maya2027\include\arnold\ai_version.h`), and Gaffer 1.7.7 has a 7.5 module, so the major
  versions line up. **Gotcha:** MtoA's header is at `include\arnold\ai_version.h`, but Gaffer
  looks for `include\ai_version.h` (the standalone Arnold SDK layout). Pointing ARNOLD_ROOT
  at the MtoA folder will probably fail the version check, so the standalone Arnold SDK
  7.5.x (from Autodesk) is likely needed. Untested; needs a hand test.

## `gaffer mcp` (new, 2026, copyright Cinesite)
- `apps/mcp/mcp-1.py`: "Makes scripts available to MCP clients such as coding agents."
  Runs an MCP server over stdio (`Gaffer.MCP.StreamServer`), one target per .gfr script
  given (or an empty script), and exits when the client closes its input.
- Its own help text suggests `claude mcp add gaffer-headless -- gaffer mcp` for Claude Code.
- Its own caution: "This gives clients full control over Gaffer, and anything else that can
  be done with Python."
- Relevance: pipeline TDs (and Claude Code) could build and check Gaffer graphs directly
  while developing the integration.
