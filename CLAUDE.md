# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Maya Python tool development workspace for a 3D animation teaching pipeline. Scripts are developed and tested here before being deployed to Maya's scripts folder for student use.

**Maya versions:** Maya 2025 (primary), with Maya 2026 migration planned. Both use Python 3.x — maintain compatibility with both where possible.

## Folder Structure & Development Workflow

Development follows the existing folder structure — always save files in the correct location, never create ad-hoc locations.

### Three-stage pipeline

1. **Develop** — tool scripts are written and iterated on in the `*Dev/` folders:
   - `rigDev/` — rigging tool scripts
   - `animDev/` — animation tool scripts
   - `simDev/` — simulation tool scripts
   - `renderDev/` — rendering tool scripts
   - `pipeDev/` — pipeline tool scripts

2. **Stage for testing** — when a tool is ready to test in Maya, its scripts and icons go into the corresponding `shelfDev/` subfolder:
   - `shelfDev/mpRig/scripts/` — rigging tool scripts ready for shelf
   - `shelfDev/mpRig/icons/` — rigging shelf icons
   - `shelfDev/mpAnim/scripts/` — animation tool scripts ready for shelf
   - `shelfDev/mpAnim/icons/` — animation shelf icons
   - The mpToolSet installer (`install.py`) deploys from here to Maya's prefs folders for testing.

3. **Deploy to students** — copy final scripts and icons from `shelfDev/` into `mpToolSet/` for student rollout:
   - `mpToolSet/mpRig/scripts/`, `mpToolSet/mpRig/icons/`
   - `mpToolSet/mpAnim/scripts/`, `mpToolSet/mpAnim/icons/`

### Rules

- Never edit tool scripts or icons directly in `mpToolSet/` — always update from the source folders.
- Never save files outside the established folder structure (no loose files in `scriptDev/` root, etc.).
- Icons always live in the `icons/` folder within their specific `shelfDev/` shelf folder.

### mpToolSet-only files (can be edited in place)

- `install.py` / `uninstall.py` — drag-and-drop installer/uninstaller
- `shelf_config.py` (in each shelf folder) — shelf button definitions
- `mpToolSet_guide.md` — student documentation

The end goal is two drag-and-drop files: one to install/update, one to uninstall. Each file should handle everything on its own — students should never need to run extra steps.

### Third-party tools

- **SHAPES** is dev-only — do not include in mpToolSet or distribute to students.
- **ngSkinTools2** is bundled in `mpToolSet/ngSkinTools2/` — a top-level folder alongside `install.py`/`uninstall.py`, with its own self-contained `install.py`/`uninstall.py` pair. It ships inside the same mpToolSet download (one download for students) but installs separately: students drag `ngSkinTools2/install.py` in only if they need it, decoupled from the main installer's manifest/backup system. See `mpToolSet/dev_notes.md` for why (recurring install failures when it was auto-installed).
- **Studio Library** is bundled the same way, in `mpToolSet/studioLibrary/` and `studio4AnimToolset/studioLibrary/` — each a top-level folder with its own self-contained `install.py`/`uninstall.py`, installed separately from the main installer for the same reason as ngSkinTools2: it's a set of plain Python packages (`mutils`, `studiolibrary`, `studiolibrarymaya`, `studioqt`, `studiovendor`) that can be actively loaded in a running Maya session, so bundling it into the frequently-rerun main installer risked a `shutil.rmtree` `PermissionError` on Windows that could abort the rest of the install (including shelf building) partway through.

### Two student toolsets

Both toolsets now ship the same way — install package, backup/rollback, and automated GitHub Release. Keep both in mind when updating shared tools (e.g. `shortCuts.py`, `ps_spine.py`) since each has its own hand-synced copy under its respective folder.

- **mpToolSet** (`mpToolSet/`) — full toolset: both mpAnim and mpRig shelves, MetaHuman pipeline tools, cloth sim, corrective blendshapes, ngSkinTools2, etc.
- **studio4AnimToolset** (`studio4AnimToolset/`) — cut-down, single `studio4Anim` shelf for the second-year class: multiTool, ps_spine, Playblast, CamPreset, Studio Library, the Jiffy tools, and shortCuts only. No rigging/MetaHuman/sim tools.

### Tools that stay in scriptDev (not for students)

- **Eucalyptus tree generator** (`renderDev/eucalyptusGen.py`, `eucalyptusGen_ui.py`, `eucalyptusLeaves.py`, `eucalyptusLeaves_ui.py`, `gumTreeBark.py`) — a personal/production tool for the user's own environment art work, not part of the student toolset. Do not stage it into `shelfDev/` or `mpToolSet/` as part of the normal three-stage pipeline. It deploys straight from `renderDev/` to the live Maya scripts folder for the user's own testing — see the deploy note in the project memory for that tool.

## Icons

- All new shelf/tool icons must be **256×256 pixels**, PNG format, with **rounded corners**.
- MetaHuman-related tool icons include a small dot with an "m" in the bottom-right corner: black dot / white "m" by default, or white dot / black "m" if the icon background is black.
- Exceptions: Studio Library and ngSkinTools icons keep their original dimensions.

## Code Conventions

- Use `maya.cmds` for all new code. Avoid `pymel` dependencies — pymel is not guaranteed in future Maya versions.
- UI tools use **PySide6** (Maya 2025+). Use `shiboken6` for `wrapInstance`. PySide2/shiboken2 are not available in Maya 2025+.
- Prefer `maya.api.OpenMaya` over the legacy `maya.OpenMaya` bindings when C++ API access is needed.

Key Maya modules available at runtime:
- `maya.cmds` — primary command interface
- `maya.mel` — MEL bridge
- `maya.api.OpenMaya` — C++ API bindings
- `PySide6` — UI framework (Maya 2025+)

## Student Distribution

Both `mpToolSet/` and `studio4AnimToolset/` are automatically zipped and published as GitHub Releases whenever changes to them are pushed to `main`. No manual zipping or uploading needed — local `*.zip` files are gitignored.

- **mpToolSet**
  - Workflow: `.github/workflows/release-mptoolset.yml`
  - Release tag: `latest` (this is also the repo's overall "latest release")
  - Student download URL: `github.com/prSarell/scriptDev/releases/latest`
- **studio4AnimToolset**
  - Workflow: `.github/workflows/release-studio4anim.yml`
  - Release tag: `studio4anim-latest` (does not affect the repo's overall "latest release", which stays pinned to mpToolSet)
  - Student download URL: `github.com/prSarell/scriptDev/releases/tag/studio4anim-latest`

## Running / Testing Scripts

Scripts cannot be unit-tested outside Maya without mocking. To test:
- **Inside Maya**: open the Script Editor, paste or source the script, run in a Python tab.
- **mayapy**: run `mayapy <script.py>` from the Maya install directory for headless execution.
- **Stubs**: use `maya-stubs` for IDE type checking only — they do not execute Maya logic.
