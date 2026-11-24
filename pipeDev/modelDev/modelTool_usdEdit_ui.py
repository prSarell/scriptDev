"""
Model Tool — the USD Edit window (mpModel shelf, spec §4i, user
2026-11-24). The work is in modelTool_usdEdit.

In a shot: pick a USD model (viewport or Outliner), choose this shot or the
asset, click Edit, move it with Maya's tools, click Save. The banner says
which layer is taking edits.
In the asset's own scene: Apply Asset Edits moves the Maya model to match
what shots saved for the asset; then publish as usual.
"""

import os

import maya.cmds as cmds

import modelTool_usdEdit as edit
from publishTool_api import PublishError

WINDOW = "modelToolUsdEditWin"
HOW_TO_WINDOW = "modelToolUsdEditHowToWin"
COLOURS = {None: (0.30, 0.30, 0.30), edit.SHOT: (0.20, 0.45, 0.25),
           edit.ASSET: (0.75, 0.40, 0.10)}

HOW_TO = """USD EDIT

Move a USD model for this shot, or for the asset in every shot.

In a shot
1. Select the model: click it in the viewport, or its USD stage or
   anything inside it in the Outliner.
2. Choose Edit for: This shot, or The asset (every shot).
3. Click Edit. The banner turns green (shot) or orange (asset).
4. Move, rotate or scale it with Maya's usual tools.
5. Click Save. Discard throws away what you haven't saved.

What goes where
- This shot: only this shot changes. Saved in the shot's usd folder.
- The asset: every shot using the asset on this computer sees it.
  It reaches the published model when the modeller applies it
  (below) and publishes.
- If a shot has already moved an object, moving that same object for
  the asset won't show in that shot: the shot's placement wins.
- The published file is never changed.

In the asset's own scene (Modeling)
1. Open the asset's scene. The window shows how many asset edits
   are waiting.
2. Click Apply Asset Edits: the Maya model moves to match.
   Ctrl+Z undoes it in one step.
3. Publish as usual, with USD ticked.
4. Click Clear Asset Edits once the new version is published."""


def _say(message, title="USD Edit"):
    cmds.confirmDialog(title=title, message=message, button=["OK"])


class _Window(object):
    def __init__(self):
        if cmds.window(WINDOW, exists=True):
            cmds.deleteUI(WINDOW)
        cmds.window(WINDOW, title="USD Edit", widthHeight=(340, 420))
        cmds.columnLayout(adjustableColumn=True, rowSpacing=6, columnAttach=("both", 8))
        cmds.text(label="", height=2)
        cmds.button(label="How to use", height=22, command=lambda *_: self.how_to())
        self.picked = cmds.text(label="", align="left", wordWrap=True)
        cmds.frameLayout(label="In a shot", collapsable=False, marginWidth=6, marginHeight=6)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=6)
        self.role = cmds.radioButtonGrp(label="Edit for:", labelArray2=["This shot",
                                                                        "The asset (every shot)"],
                                        numberOfRadioButtons=2, select=1,
                                        columnWidth3=(60, 90, 160))
        self.banner = cmds.text(label="", height=30, backgroundColor=COLOURS[None])
        cmds.rowLayout(numberOfColumns=3, adjustableColumn=1, columnAttach3=("both",) * 3)
        cmds.button(label="Edit", height=32, command=lambda *_: self.begin())
        cmds.button(label="Save", height=32, command=lambda *_: self.save())
        cmds.button(label="Discard", height=32, command=lambda *_: self.discard())
        cmds.setParent("..")
        self.upgrade_btn = cmds.button(label="Update Stage (give it edit layers)", height=26,
                                       command=lambda *_: self.upgrade(), visible=False)
        cmds.setParent("..")
        cmds.setParent("..")
        cmds.frameLayout(label="In the asset's own scene", collapsable=False, marginWidth=6,
                         marginHeight=6)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=6)
        self.waiting = cmds.text(label="", align="left", wordWrap=True)
        cmds.button(label="Apply Asset Edits", height=30, command=lambda *_: self.apply())
        cmds.button(label="Clear Asset Edits", height=24, command=lambda *_: self.clear())
        cmds.setParent("..")
        cmds.setParent("..")
        cmds.button(label="Refresh", height=22, command=lambda *_: self.refresh())
        cmds.scriptJob(event=("SelectionChanged", self.refresh), parent=WINDOW)
        cmds.scriptJob(event=("SceneOpened", self.refresh), parent=WINDOW)
        cmds.showWindow(WINDOW)
        self.refresh()

    # -- state ---------------------------------------------------------------
    def _shape(self, quiet=False):
        shape, _ = edit.picked()
        if not shape and not quiet:
            _say("Select a USD model Build loaded: click it in the viewport, or pick its "
                 "stage in the Outliner.")
        return shape

    def refresh(self, *_):
        if not cmds.window(WINDOW, exists=True):
            return
        shape, prim = edit.picked()
        role, upgrade = None, False
        if shape:
            try:
                asset = edit.asset_of(shape)[1]
                upgrade = edit.needs_upgrade(shape)
                role = None if upgrade else edit.editing(shape)
                label = "Selected: %s%s" % (asset, (" (%s)" % prim.split("/")[-1]) if prim else "")
            except PublishError as e:
                label = str(e)
        else:
            label = "Select a USD model (viewport or Outliner)."
        cmds.text(self.picked, edit=True, label=label)
        cmds.button(self.upgrade_btn, edit=True, visible=upgrade)
        unsaved = shape and not upgrade and edit.dirty(shape)
        if role:
            text = "Editing: %s%s" % (edit.LABELS[role], "  (unsaved)" if unsaved else "")
        else:
            text = "Not editing"
        cmds.text(self.banner, edit=True, label=text, backgroundColor=COLOURS[role])
        try:
            moves, missing, other = edit.pending()
            waiting = "%d asset edit(s) waiting for this model." % len(moves)
            if missing:
                waiting += " %d for objects not in this scene." % len(missing)
        except Exception:
            waiting = "Open the asset's own scene to apply its edits."
        cmds.text(self.waiting, edit=True, label=waiting)

    # -- buttons ---------------------------------------------------------------
    def begin(self):
        shape = self._shape()
        if not shape:
            return
        role = edit.SHOT if cmds.radioButtonGrp(self.role, query=True, select=True) == 1 \
            else edit.ASSET
        try:
            edit.begin(shape, role)
        except PublishError as e:
            _say(str(e))
        self.refresh()

    def save(self):
        shape = self._shape()
        if not shape:
            return
        saved = edit.save(shape)
        cmds.inViewMessage(amg="Saved: <hl>%s</hl>" % (", ".join(edit.LABELS[r] for r in saved)
                                                       or "nothing to save"),
                           pos="topCenter", fade=True)
        self.refresh()

    def discard(self):
        shape = self._shape()
        if not shape or not edit.dirty(shape):
            return
        if cmds.confirmDialog(title="USD Edit", message="Throw away the edits you haven't "
                              "saved?", button=["Discard", "Cancel"], defaultButton="Cancel",
                              cancelButton="Cancel") != "Discard":
            return
        edit.discard(shape)
        self.refresh()

    def upgrade(self):
        shape = self._shape()
        if shape:
            try:
                edit.upgrade(shape)
            except PublishError as e:
                _say(str(e))
        self.refresh()

    def apply(self):
        try:
            moved, missing, other = edit.apply_to_model()
        except PublishError as e:
            _say(str(e))
            return
        message = "Moved %d object(s) to match the asset edits." % len(moved)
        if missing:
            message += "\n\nNot in this scene (renamed or deleted?):\n  " + "\n  ".join(missing)
        if other:
            message += "\n\nOther edits not applied (only moves are):\n  " + "\n  ".join(other)
        message += "\n\nNext: publish with USD ticked, then Clear Asset Edits."
        _say(message)
        self.refresh()

    def clear(self):
        try:
            path = edit.asset_layer_file()
        except PublishError as e:
            _say(str(e))
            return
        if not os.path.isfile(path):
            return
        if cmds.confirmDialog(title="USD Edit", message="Clear this asset's edits? Shots on "
                              "this computer stop seeing them. Do this after publishing the "
                              "model with them applied.", button=["Clear", "Cancel"],
                              defaultButton="Cancel", cancelButton="Cancel") != "Clear":
            return
        edit.clear_asset_edits()
        self.refresh()

    def how_to(self):
        if cmds.window(HOW_TO_WINDOW, exists=True):
            cmds.deleteUI(HOW_TO_WINDOW)
        cmds.window(HOW_TO_WINDOW, title="USD Edit: how to", widthHeight=(460, 520))
        cmds.scrollField(text=HOW_TO, editable=False, wordWrap=True)
        cmds.showWindow(HOW_TO_WINDOW)


def show():
    return _Window()
