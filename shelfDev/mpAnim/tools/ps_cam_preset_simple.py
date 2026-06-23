# -*- coding: utf-8 -*-
"""
ps_cam_preset_simple.py

UI:
- Camera field (type or load from current selection)
- Preset Name field (type a name like previs_001, blocking_001, etc.)
- Saved Presets dropdown
- Save Preset button: saves camera + viewport mask flags + render settings to a named JSON preset on disk
- Apply Selected Preset button: applies selected preset to the camera named in the field
- Delete Selected Preset button: deletes the selected preset JSON from disk
- Refresh Preset List button: rebuilds the preset dropdown from disk

Usage:
import importlib
import ps_cam_preset_simple as ps
importlib.reload(ps)
ps.show()
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Optional, Tuple, List

import maya.cmds as cmds


# -------------------------
# Persistence
# -------------------------

_PRESET_DIRNAME = "ps_cam_preset_simple"


def _preset_dir() -> str:
    user_dir = cmds.internalVar(userAppDir=True)  # Documents/maya/<ver>/
    folder = os.path.join(user_dir, _PRESET_DIRNAME)
    if not os.path.isdir(folder):
        try:
            os.makedirs(folder)
        except Exception:
            folder = user_dir
    return folder


def _sanitize_preset_name(name: str) -> str:
    """
    Keep names predictable and filesystem-safe.
    Allows letters, numbers, underscore, dash.
    Converts spaces to underscores.
    """
    if not name:
        return ""
    name = name.strip().replace(" ", "_")
    name = re.sub(r"[^A-Za-z0-9_\-]", "", name)
    return name


def _preset_path_from_name(name: str) -> str:
    safe_name = _sanitize_preset_name(name)
    return os.path.join(_preset_dir(), "{}.json".format(safe_name))


def _write_json(path: str, data: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)


def _read_json(path: str) -> Optional[Dict[str, Any]]:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _list_presets() -> List[str]:
    folder = _preset_dir()
    if not os.path.isdir(folder):
        return []

    out = []
    for f in os.listdir(folder):
        if f.lower().endswith(".json"):
            out.append(os.path.splitext(f)[0])

    out.sort()
    return out


def _delete_preset_file(name: str) -> bool:
    path = _preset_path_from_name(name)
    if not os.path.exists(path):
        return False
    try:
        os.remove(path)
        return True
    except Exception:
        return False


# -------------------------
# Safe attr helpers
# -------------------------

def _get(node_attr: str) -> Any:
    try:
        if cmds.objExists(node_attr):
            v = cmds.getAttr(node_attr)
            if isinstance(v, (list, tuple)) and len(v) == 1:
                return v[0]
            return v
    except Exception:
        pass
    return None


def _set(node_attr: str, value: Any) -> bool:
    try:
        if not cmds.objExists(node_attr):
            return False

        attr_type = cmds.getAttr(node_attr, type=True)

        if attr_type == "bool":
            cmds.setAttr(node_attr, bool(value))

        elif attr_type in ("long", "short", "byte", "enum"):
            cmds.setAttr(node_attr, int(value))

        elif attr_type in ("float", "double", "doubleAngle", "doubleLinear"):
            cmds.setAttr(node_attr, float(value))

        elif attr_type == "string":
            cmds.setAttr(node_attr, str(value), type="string")

        elif attr_type in ("double3", "float3"):
            if isinstance(value, (list, tuple)) and len(value) == 3:
                cmds.setAttr(node_attr, value[0], value[1], value[2], type=attr_type)
            else:
                return False

        else:
            cmds.setAttr(node_attr, value)

        return True

    except Exception:
        return False


# -------------------------
# Camera / viewport capture
# -------------------------

_CAMERA_SHAPE_ATTRS = [
    # Filmback / framing
    "horizontalFilmAperture",
    "verticalFilmAperture",
    "filmFit",
    "filmFitOffset",
    "overscan",
    "lensSqueezeRatio",

    # Lens
    "focalLength",
    "cameraScale",
    "focusDistance",
    "fStop",
    "shutterAngle",
    "nearClipPlane",
    "farClipPlane",

    # Film translate/offset
    "filmTranslateH",
    "filmTranslateV",
    "horizontalFilmOffset",
    "verticalFilmOffset",
    "preScale",
    "postScale",

    # DOF
    "depthOfField",

    # Camera display / display options
    "displayFilmGate",
    "displayResolution",
    "displayGateMask",
    "displaySafeAction",
    "displaySafeTitle",
    "displayFilmOrigin",
    "displayFilmPivot",
    "displayFilmTranslate",
    "displayFieldChart",
    "displayOverscan",
    "displayGateMaskOpacity",
    "displayGateMaskColor",

    # Optional useful camera attrs often tied to shot setup
    "orthographic",
    "orthographicWidth",
    "shakeEnabled",
    "horizontalShake",
    "verticalShake",
]

_MODELEDITOR_FLAGS = [
    "displayFilmGate",
    "displayResolution",
    "displayGateMask",
    "displaySafeAction",
    "displaySafeTitle",
    "displayFilmOrigin",
    "displayFilmPivot",
    "displayFilmTranslate",
    "displayFieldChart",
    "displayOverscan",
]


def _camera_shape(cam_transform: str) -> Optional[str]:
    shapes = cmds.listRelatives(cam_transform, shapes=True, type="camera", fullPath=False) or []
    return shapes[0] if shapes else None


def _active_model_panel() -> Optional[str]:
    p = cmds.getPanel(withFocus=True)
    if p and cmds.getPanel(typeOf=p) == "modelPanel":
        return p
    for vp in (cmds.getPanel(vis=True) or []):
        if cmds.getPanel(typeOf=vp) == "modelPanel":
            return vp
    return None


def _capture_camera(cam_transform: str) -> Dict[str, Any]:
    shape = _camera_shape(cam_transform)
    if not shape:
        raise RuntimeError("Camera transform has no camera shape.")

    attrs: Dict[str, Any] = {}
    for a in _CAMERA_SHAPE_ATTRS:
        node_attr = "{}.{}".format(shape, a)
        v = _get(node_attr)
        if v is not None:
            attrs[a] = v

    return {"cameraAttrs": attrs}


def _apply_camera(cam_transform: str, cam_data: Dict[str, Any]) -> Tuple[int, int]:
    shape = _camera_shape(cam_transform)
    if not shape:
        raise RuntimeError("Target camera transform has no camera shape.")

    applied = 0
    skipped = 0

    for a, v in (cam_data.get("cameraAttrs", {}) or {}).items():
        if _set("{}.{}".format(shape, a), v):
            applied += 1
        else:
            skipped += 1

    return applied, skipped


def _capture_viewport_flags() -> Dict[str, Any]:
    panel = _active_model_panel()
    flags: Dict[str, Any] = {}

    if panel:
        for f in _MODELEDITOR_FLAGS:
            try:
                flags[f] = bool(cmds.modelEditor(panel, q=True, **{f: True}))
            except Exception:
                pass

    return {"modelEditorFlags": flags}


def _apply_viewport_flags(vp_data: Dict[str, Any]) -> Tuple[int, int]:
    flags = vp_data.get("modelEditorFlags", {}) or {}
    if not flags:
        return 0, 0

    panels = cmds.getPanel(type="modelPanel") or []
    edits = 0
    skips = 0

    for p in panels:
        if not cmds.modelPanel(p, exists=True):
            continue
        for f, v in flags.items():
            try:
                cmds.modelEditor(p, e=True, **{f: bool(v)})
                edits += 1
            except Exception:
                skips += 1

    return edits, skips


# -------------------------
# Render settings capture
# -------------------------

_RENDER_NODES_AND_ATTRS = {
    "defaultRenderGlobals": [
        "currentRenderer",
        "animation",
        "startFrame",
        "endFrame",
        "byFrameStep",
        "extensionPadding",
        "outFormatControl",
        "periodInExt",
        "putFrameBeforeExt",
        "imageFilePrefix",
    ],
    "defaultResolution": [
        "width",
        "height",
        "deviceAspectRatio",
        "pixelAspect",
        "aspectLock",
    ],
    # Arnold (if present)
    "defaultArnoldRenderOptions": [
        "AA_samples",
        "GI_diffuse_samples",
        "GI_specular_samples",
        "GI_transmission_samples",
        "GI_sss_samples",
        "GI_volume_samples",
    ],
    "defaultArnoldDriver": [
        "ai_translator",
        "halfPrecision",
        "mergeAOVs",
        "exrCompression",
    ],
}


def _capture_render() -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for node, attrs in _RENDER_NODES_AND_ATTRS.items():
        if not cmds.objExists(node):
            continue

        node_data: Dict[str, Any] = {}
        for a in attrs:
            v = _get("{}.{}".format(node, a))
            if v is not None:
                node_data[a] = v

        if node_data:
            out[node] = node_data

    return out


def _apply_render(rdata: Dict[str, Any]) -> Tuple[int, int]:
    if not rdata:
        return 0, 0

    edits = 0
    skips = 0

    for node, attrs in rdata.items():
        if not cmds.objExists(node):
            continue

        for a, v in attrs.items():
            if _set("{}.{}".format(node, a), v):
                edits += 1
            else:
                skips += 1

    return edits, skips


# -------------------------
# Selection helper
# -------------------------

def _selected_camera() -> Optional[str]:
    sel = cmds.ls(sl=True, long=False) or []
    if not sel:
        return None
    node = sel[0]
    if cmds.nodeType(node) == "camera":
        parents = cmds.listRelatives(node, parent=True, fullPath=False) or []
        if not parents:
            return None
        node = parents[0]
    if _camera_shape(node):
        return node
    return None


# -------------------------
# UI
# -------------------------

_WIN = "psCamPresetSimpleWin"
_PRESET_NAME_FIELD = "psCamPresetSimple_presetNameField"
_PRESET_MENU = "psCamPresetSimple_presetMenu"
_STATUS = "psCamPresetSimple_status"


def _set_status(msg: str) -> None:
    if cmds.control(_STATUS, exists=True):
        cmds.text(_STATUS, e=True, label=msg)


def _get_preset_name_from_field() -> str:
    if not cmds.control(_PRESET_NAME_FIELD, exists=True):
        return ""
    raw = cmds.textField(_PRESET_NAME_FIELD, q=True, text=True).strip()
    return _sanitize_preset_name(raw)


def _get_selected_preset() -> str:
    if not cmds.control(_PRESET_MENU, exists=True):
        return ""
    try:
        value = cmds.optionMenu(_PRESET_MENU, q=True, value=True)
        if value == "-- None --":
            return ""
        return value
    except Exception:
        return ""


def _set_selected_preset(name: str) -> None:
    if not cmds.control(_PRESET_MENU, exists=True):
        return
    items = _list_presets()
    if name in items:
        try:
            cmds.optionMenu(_PRESET_MENU, e=True, value=name)
        except Exception:
            pass


def _refresh_preset_menu(select_name: Optional[str] = None) -> None:
    if not cmds.control(_PRESET_MENU, exists=True):
        return

    existing = cmds.optionMenu(_PRESET_MENU, q=True, itemListLong=True) or []
    for item in existing:
        try:
            cmds.deleteUI(item)
        except Exception:
            pass

    presets = _list_presets()
    if not presets:
        cmds.menuItem(label="-- None --", parent=_PRESET_MENU)
        return

    for p in presets:
        cmds.menuItem(label=p, parent=_PRESET_MENU)

    if select_name and select_name in presets:
        _set_selected_preset(select_name)
    else:
        try:
            cmds.optionMenu(_PRESET_MENU, e=True, value=presets[0])
        except Exception:
            pass


def _no_camera_warning() -> None:
    cmds.inViewMessage(
        amg="<hl>No camera selected</hl> — select a camera first.",
        pos="midCenter",
        fade=True,
    )


def save_preset(*_) -> None:
    cam = _selected_camera()
    if not cam:
        _no_camera_warning()
        return

    preset_name = _get_preset_name_from_field()
    if not preset_name:
        _set_status("Enter a preset name first, for example: previs_001")
        return

    try:
        preset = {
            "version": 3,
            "presetName": preset_name,
            "cameraSource": cam,
            "camera": _capture_camera(cam),
            "viewport": _capture_viewport_flags(),
            "render": _capture_render(),
        }

        path = _preset_path_from_name(preset_name)
        _write_json(path, preset)
        _refresh_preset_menu(select_name=preset_name)
        cmds.textField(_PRESET_NAME_FIELD, e=True, text="")
        _set_status("Saved '{}' from {}".format(preset_name, cam))

    except Exception as e:
        _set_status("Save failed: {}".format(e))


def apply_selected_preset(*_) -> None:
    cam = _selected_camera()
    if not cam:
        _no_camera_warning()
        return

    preset_name = _get_selected_preset()
    if not preset_name:
        _set_status("No preset selected.")
        return

    path = _preset_path_from_name(preset_name)
    preset = _read_json(path)
    if not preset:
        _set_status("Could not read preset '{}'.".format(preset_name))
        return

    try:
        r_edits, _ = _apply_render(preset.get("render", {}))
        c_applied, _ = _apply_camera(cam, preset.get("camera", {}))
        v_edits, _ = _apply_viewport_flags(preset.get("viewport", {}))

        _set_status(
            "Applied '{}' to {}  (cam:{} vp:{} render:{})".format(
                preset_name, cam, c_applied, v_edits, r_edits
            )
        )

    except Exception as e:
        _set_status("Apply failed: {}".format(e))


def delete_selected_preset(*_) -> None:
    preset_name = _get_selected_preset()
    if not preset_name:
        _set_status("No preset selected to delete.")
        return

    result = cmds.confirmDialog(
        title="Delete Preset",
        message="Delete preset '{}'?".format(preset_name),
        button=["Delete", "Cancel"],
        defaultButton="Delete",
        cancelButton="Cancel",
        dismissString="Cancel"
    )

    if result != "Delete":
        _set_status("Delete cancelled.")
        return

    if _delete_preset_file(preset_name):
        _refresh_preset_menu()
        _set_status("Deleted '{}'.".format(preset_name))
    else:
        _set_status("Could not delete '{}'.".format(preset_name))


def show() -> None:
    if cmds.window(_WIN, exists=True):
        cmds.deleteUI(_WIN)

    cmds.window(_WIN, title="Camera Preset Manager", sizeable=False, width=200)
    cmds.columnLayout(adj=True, rowSpacing=6, columnAttach=("both", 10))

    cmds.separator(height=4, style="none")
    cmds.text(label="Select a camera in the viewport, then save or apply presets.",
              align="left")
    cmds.separator(height=6, style="in")

    # ── Create Preset ──
    cmds.text(label="CREATE PRESET", font="boldLabelFont", align="left")
    cmds.separator(height=2, style="none")

    cmds.textField(_PRESET_NAME_FIELD, placeholderText="Preset name  (e.g. previs_001)")
    cmds.button(label="Save Preset", height=28, c=save_preset)

    cmds.separator(height=6, style="in")

    # ── Apply Preset ──
    cmds.text(label="APPLY PRESET", font="boldLabelFont", align="left")
    cmds.separator(height=2, style="none")

    cmds.optionMenu(_PRESET_MENU)

    cmds.separator(height=2, style="none")

    btn_form = cmds.formLayout()
    apply_btn = cmds.button(label="Apply Preset", height=32, c=apply_selected_preset)
    delete_btn = cmds.button(label="Delete Preset", height=32, c=delete_selected_preset)
    cmds.formLayout(btn_form, e=True,
        attachForm=[(apply_btn, "left", 0), (apply_btn, "top", 0),
                     (delete_btn, "right", 0), (delete_btn, "top", 0)],
        attachPosition=[(apply_btn, "right", 2, 50),
                        (delete_btn, "left", 2, 50)],
    )
    cmds.setParent("..")

    cmds.separator(height=6, style="in")
    cmds.text(_STATUS, label="Ready.", align="left")
    cmds.separator(height=4, style="none")

    cmds.showWindow(_WIN)
    _refresh_preset_menu()