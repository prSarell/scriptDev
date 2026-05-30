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

## Code Conventions

- Use `maya.cmds` for all new code. Avoid `pymel` dependencies — pymel is not guaranteed in future Maya versions.
- UI tools use **PySide6** (Maya 2025+). Use `shiboken6` for `wrapInstance`. PySide2/shiboken2 are not available in Maya 2025+.
- Prefer `maya.api.OpenMaya` over the legacy `maya.OpenMaya` bindings when C++ API access is needed.

Key Maya modules available at runtime:
- `maya.cmds` — primary command interface
- `maya.mel` — MEL bridge
- `maya.api.OpenMaya` — C++ API bindings
- `PySide2` — UI framework

## Running / Testing Scripts

Scripts cannot be unit-tested outside Maya without mocking. To test:
- **Inside Maya**: open the Script Editor, paste or source the script, run in a Python tab.
- **mayapy**: run `mayapy <script.py>` from the Maya install directory for headless execution.
- **Stubs**: use `maya-stubs` for IDE type checking only — they do not execute Maya logic.
