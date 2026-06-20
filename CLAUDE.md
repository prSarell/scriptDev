# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Maya Python tool development workspace for a 3D animation teaching pipeline. Scripts are developed and tested here before being deployed to Maya's scripts folder for student use.

**Maya versions:** Maya 2025 (primary), with Maya 2026 migration planned. Both use Python 3.x — maintain compatibility with both where possible.

## Folder Structure

- `rigDev/` — rigging tools
- `animDev/` — animation tools
- `simDev/` — simulation tools
- `renderDev/` — rendering tools
- `pipeDev/` — pipeline tools
- `shelfDev/` — Maya shelf tools and buttons
- `mpToolSet/` — **student deployment package only** (see below)

## mpToolSet Workflow

`mpToolSet/` is the student-facing install package. All development and testing happens in the `*Dev/` folders — never edit tool scripts directly in `mpToolSet/`. Scripts and icons inside `mpToolSet/mpRig/` and `mpToolSet/mpAnim/` are copies from dev folders and must be updated by re-copying from the source, not by editing in place.

Files that live exclusively in `mpToolSet/` and can be edited there:
- `install.py` / `uninstall.py` — drag-and-drop installer/uninstaller
- `shelf_config.py` (in each shelf folder) — shelf button definitions
- `mpToolSet_guide.md` — student documentation

The end goal is two drag-and-drop files: one to install/update, one to uninstall. Each file should handle everything on its own — students should never need to run extra steps.

Third-party tools:
- **SHAPES** is dev-only — do not include in mpToolSet or distribute to students.
- **ngSkinTools2** is bundled in `mpToolSet/mpRig/ngskintools2/` and installed automatically.

After making changes to scripts in the `*Dev/` folders, check whether the corresponding files in `mpToolSet/` need to be updated to match.

## Code Conventions

- Use `maya.cmds` for all new code. Avoid `pymel` dependencies — pymel is not guaranteed in future Maya versions.
- UI tools use **PySide6** (Maya 2025+). Use `shiboken6` for `wrapInstance`. PySide2/shiboken2 are not available in Maya 2025+.
- Prefer `maya.api.OpenMaya` over the legacy `maya.OpenMaya` bindings when C++ API access is needed.

Key Maya modules available at runtime:
- `maya.cmds` — primary command interface
- `maya.mel` — MEL bridge
- `maya.api.OpenMaya` — C++ API bindings
- `PySide6` — UI framework (Maya 2025+)

## Running / Testing Scripts

Scripts cannot be unit-tested outside Maya without mocking. To test:
- **Inside Maya**: open the Script Editor, paste or source the script, run in a Python tab.
- **mayapy**: run `mayapy <script.py>` from the Maya install directory for headless execution.
- **Stubs**: use `maya-stubs` for IDE type checking only — they do not execute Maya logic.
