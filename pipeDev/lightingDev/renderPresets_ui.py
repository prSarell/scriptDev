"""
renderPresets_ui.py: the Render Presets window (mpLighting shelf). Laid out
like the camera presets tool (ps_cam_preset_simple): name a preset and save
it; pick one and apply or delete it. See renderPresets_api for what a
preset holds.

    import renderPresets_ui; renderPresets_ui.show()
"""

import maya.cmds as cmds

import renderPresets_api as api

WIN = "mpRenderPresetsWin"
_NAME = WIN + "_name"
_MENU = WIN + "_menu"
_INFO = WIN + "_info"
_WHERE = WIN + "_where"
_STATUS = WIN + "_status"


def _say(message):
    if cmds.control(_STATUS, exists=True):
        cmds.text(_STATUS, e=True, label=message)


def _selected():
    if not cmds.control(_MENU, exists=True):
        return ""
    value = cmds.optionMenu(_MENU, q=True, value=True)
    return "" if value == api.NO_PRESET else value or ""


def _show_info(*_):
    name = _selected()
    text = ""
    if name:
        try:
            text = api.describe(api.read_preset(name))
        except api.PresetError as e:
            text = str(e)
    cmds.text(_INFO, e=True, label=text)


def refresh(select=None):
    """Rebuild the list from the current scene's preset folder (a different
    film's scene sees that film's presets)."""
    if not cmds.control(_MENU, exists=True):
        return
    cmds.text(_WHERE, e=True, label="Presets: " + api.where_label())
    for item in cmds.optionMenu(_MENU, q=True, itemListLong=True) or []:
        cmds.deleteUI(item)
    names = api.list_presets()
    for name in names or [api.NO_PRESET]:
        cmds.menuItem(label=name, parent=_MENU)
    if select in names:
        cmds.optionMenu(_MENU, e=True, value=select)
    _show_info()


def save(*_):
    name = api.clean_name(cmds.textField(_NAME, q=True, text=True))
    if not name:
        return _say("Enter a preset name first, e.g. lookdev_001.")
    if name in api.list_presets():
        answer = cmds.confirmDialog(
            title="Render Presets", message="There's already a preset called '%s'. Replace it "
            "with this shot's settings and lights?" % name,
            button=["Replace", "Cancel"], defaultButton="Cancel", cancelButton="Cancel",
            dismissString="Cancel")
        if answer != "Replace":
            return _say("Not saved.")
    try:
        _, preset = api.save(name)
    except (api.PresetError, OSError) as e:
        return _say("Save failed: %s" % e)
    cmds.textField(_NAME, e=True, text="")
    refresh(select=name)
    text = "Saved '%s': %d light(s), %d AOV(s)." % (name, len(preset["lights"]), len(preset["aovs"]))
    fed = api.lit_by(preset)
    if fed:
        text += " " + "; ".join(fed) + "."
    if preset.get("skippedLights"):
        text += " Mesh lights aren't saved: %s." % ", ".join(preset["skippedLights"])
    _say(text)


def apply(*_):
    name = _selected()
    if not name:
        return _say("No preset picked.")
    try:
        preset = api.read_preset(name)
        api.ensure_arnold()
    except api.PresetError as e:
        return _say(str(e))
    extras = [api._short(api._transform(s)) for s in api.extra_lights(preset)]
    remove = False
    if extras:
        shown = ", ".join(extras[:8]) + (" and %d more" % (len(extras) - 8) if len(extras) > 8 else "")
        answer = cmds.confirmDialog(
            title="Render Presets",
            message="This shot has %d light(s) that aren't in '%s':\n%s\n\nRemove them, so the "
                    "shot's lights match the preset, or keep them as well?" % (len(extras), name, shown),
            button=["Remove them", "Keep them", "Cancel"], defaultButton="Keep them",
            cancelButton="Cancel", dismissString="Cancel")
        if answer == "Cancel":
            return _say("Not applied.")
        remove = answer == "Remove them"
    try:
        counts = api.apply(preset, remove_extra=remove)
    except api.PresetError as e:
        return _say(str(e))
    _say("Applied '%s': %s (Ctrl+Z undoes it.)" % (name, api.summary(counts)))


def delete(*_):
    name = _selected()
    if not name:
        return _say("No preset picked to delete.")
    if cmds.confirmDialog(title="Render Presets",
                          message="Delete the preset '%s'? Every shot of the film uses this "
                                  "list." % name,
                          button=["Delete", "Cancel"], defaultButton="Cancel",
                          cancelButton="Cancel", dismissString="Cancel") != "Delete":
        return _say("Not deleted.")
    try:
        api.delete_preset(name)
    except OSError as e:
        return _say("Couldn't delete '%s': %s" % (name, e))
    refresh()
    _say("Deleted '%s'." % name)


def show():
    if cmds.window(WIN, exists=True):
        cmds.deleteUI(WIN)
    cmds.window(WIN, title="Render Presets", sizeable=True, width=330)
    cmds.columnLayout(adj=True, rowSpacing=6, columnAttach=("both", 10))
    cmds.separator(height=4, style="none")
    cmds.text(label="Save this shot's Arnold settings, AOVs and lights as a preset,\n"
                    "then apply it in any other shot.", align="left")
    cmds.text(_WHERE, label="", align="left", font="smallObliqueLabelFont")
    cmds.separator(height=6, style="in")

    cmds.text(label="CREATE PRESET", font="boldLabelFont", align="left")
    cmds.textField(_NAME, placeholderText="Preset name  (e.g. lookdev_001)",
                   enterCommand=save)
    cmds.button(label="Save Preset", height=28, command=save)
    cmds.separator(height=6, style="in")

    cmds.text(label="APPLY PRESET", font="boldLabelFont", align="left")
    cmds.optionMenu(_MENU, changeCommand=_show_info)
    cmds.text(_INFO, label="", align="left", font="smallPlainLabelFont", wordWrap=True)
    form = cmds.formLayout()
    a = cmds.button(label="Apply Preset", height=32, command=apply)
    d = cmds.button(label="Delete Preset", height=32, command=delete)
    cmds.formLayout(form, e=True,
                    attachForm=[(a, "left", 0), (a, "top", 0), (d, "right", 0), (d, "top", 0)],
                    attachPosition=[(a, "right", 2, 50), (d, "left", 2, 50)])
    cmds.setParent("..")
    cmds.separator(height=6, style="in")
    cmds.text(_STATUS, label="Ready.", align="left", wordWrap=True)
    cmds.separator(height=4, style="none")
    cmds.showWindow(WIN)
    # Another scene may be in another film (or not in one): follow it.
    cmds.scriptJob(event=["SceneOpened", refresh], parent=WIN)
    cmds.scriptJob(event=["SceneSaved", refresh], parent=WIN)
    refresh()
