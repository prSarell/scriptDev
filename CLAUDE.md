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
- **ngSkinTools2** is bundled in `mpToolSet/mpRig/ngskintools2/` and installed automatically.

### Deferred work

- **studio4AnimToolset** — a cut-down toolset for second-year students exists in `studio4AnimToolset/` but has no install package yet. Do not build this until mpToolSet is fully debugged and running cleanly on both Mac and Windows.

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

The `mpToolSet/` folder is automatically zipped and published as a GitHub Release whenever changes to it are pushed to `main`.

- **Workflow:** `.github/workflows/release-mptoolset.yml`
- **Release tag:** `latest` (always points to the current version)
- **Student download URL:** `github.com/prSarell/scriptDev/releases/latest`

No manual zipping or uploading needed — pushing a change to `mpToolSet/` on `main` triggers the release automatically. Local `*.zip` files are gitignored.

## Running / Testing Scripts

Scripts cannot be unit-tested outside Maya without mocking. To test:
- **Inside Maya**: open the Script Editor, paste or source the script, run in a Python tab.
- **mayapy**: run `mayapy <script.py>` from the Maya install directory for headless execution.
- **Stubs**: use `maya-stubs` for IDE type checking only — they do not execute Maya logic.
