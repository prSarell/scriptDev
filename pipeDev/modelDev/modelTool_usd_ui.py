"""
Model Tool — the USD Hierarchy and USD Names windows (mpModel shelf,
user 2026-11-20). The work is in modelTool_usd; see it for the layout and
the naming convention.

Dev launch (Script Editor, Python tab):

    import sys, importlib
    for p in (r"C:\\Users\\scout\\Documents\\maya\\scriptDev\\pipeDev\\publishDev",
              r"C:\\Users\\scout\\Documents\\maya\\scriptDev\\pipeDev\\modelDev"):
        if p not in sys.path: sys.path.insert(0, p)
    import publishTool_api, modelTool_usd, modelTool_usd_ui
    for m in (publishTool_api, modelTool_usd, modelTool_usd_ui):
        importlib.reload(m)
    modelTool_usd_ui.show_hierarchy()      # or show_names()
"""

import maya.cmds as cmds

import modelTool_usd as usd
from publishTool_api import PublishError

HIERARCHY_WINDOW = "modelToolUsdHierarchyWin"
NAMES_WINDOW = "modelToolUsdNamesWin"


def _say(message, title="USD"):
    cmds.confirmDialog(title=title, message=message, button=["OK"])


def _selection():
    return cmds.ls(selection=True, long=True) or []


def _asset():
    try:
        return usd.asset_name()
    except PublishError as e:
        _say(str(e))
        return None


# ---------------------------------------------------------------------------
# USD Hierarchy
# ---------------------------------------------------------------------------

class HierarchyWindow(object):

    def __init__(self):
        self.w = {}

    def build(self):
        if cmds.window(HIERARCHY_WINDOW, exists=True):
            cmds.deleteUI(HIERARCHY_WINDOW)
        cmds.window(HIERARCHY_WINDOW, title="USD Hierarchy", widthHeight=(360, 330))
        cmds.columnLayout(adjustableColumn=True, rowSpacing=6, columnAttach=("both", 8))
        cmds.text(label="", height=2)
        cmds.text(align="left", wordWrap=True, label=(
            "Publish puts this in <asset>_model_GRP, the USD's top prim:\n"
            "   geo\n      render    the meshes that render\n"
            "      proxy     an optional light stand-in"))
        cmds.button(label="Build Hierarchy", height=32, command=lambda *_: self.make(),
                    annotation="Makes geo, render and proxy. With nothing picked, the "
                               "geometry outside geo goes into render.")
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnAttach=[(1, "both", 0),
                                                                           (2, "both", 4)])
        cmds.button(label="Selected to Render", height=28,
                    command=lambda *_: self.add(usd.RENDER))
        cmds.button(label="Selected to Proxy", height=28,
                    command=lambda *_: self.add(usd.PROXY))
        cmds.setParent("..")
        cmds.text(label="Geometry outside geo (not in the USD's layout):", align="left")
        self.w["left"] = cmds.textScrollList(numberOfRows=6, allowMultiSelection=True,
                                             selectCommand=lambda *_: self.pick())
        cmds.button(label="Refresh", height=24, command=lambda *_: self.refresh())
        cmds.showWindow(HIERARCHY_WINDOW)
        self.refresh()

    def refresh(self):
        cmds.textScrollList(self.w["left"], edit=True, removeAll=True)
        self._left = usd.left_out()
        for node in self._left:
            cmds.textScrollList(self.w["left"], edit=True, append=node.split("|")[-1])
        if not self._left:
            cmds.textScrollList(self.w["left"], edit=True, append="(none)")

    def pick(self):
        rows = cmds.textScrollList(self.w["left"], query=True, selectIndexedItem=True) or []
        nodes = [self._left[i - 1] for i in rows if i <= len(self._left)]
        if nodes:
            cmds.select(nodes, replace=True)

    def make(self):
        if not _asset():
            return
        picked = _selection()
        try:
            cmds.undoInfo(openChunk=True, chunkName="USD Hierarchy")
            usd.build()
            moved = usd.add(picked or usd.left_out())
        except PublishError as e:
            return _say(str(e))
        finally:
            cmds.undoInfo(closeChunk=True)
        self.refresh()
        cmds.inViewMessage(amg="USD hierarchy built%s." % (
            "; <hl>%d</hl> moved into render" % len(moved) if moved else ""),
            pos="topCenter", fade=True)

    def add(self, purpose):
        picked = _selection()
        if not picked:
            return _say("Pick what goes into %s first." % purpose)
        if not _asset():
            return
        try:
            cmds.undoInfo(openChunk=True, chunkName="USD Hierarchy")
            moved = usd.add(picked, purpose)
        except PublishError as e:
            return _say(str(e))
        finally:
            cmds.undoInfo(closeChunk=True)
        self.refresh()
        cmds.inViewMessage(amg="<hl>%d</hl> moved into geo|%s." % (len(moved), purpose),
                           pos="topCenter", fade=True)


def show_hierarchy():
    win = HierarchyWindow()
    win.build()
    return win


# ---------------------------------------------------------------------------
# USD Names
# ---------------------------------------------------------------------------

class NamesWindow(object):

    def __init__(self):
        self.w = {}
        self._found = []

    def build(self):
        if cmds.window(NAMES_WINDOW, exists=True):
            cmds.deleteUI(NAMES_WINDOW)
        asset = _asset()
        if not asset:
            return
        self.asset = asset
        cmds.window(NAMES_WINDOW, title="USD Names: %s" % asset, widthHeight=(440, 420))
        cmds.columnLayout(adjustableColumn=True, rowSpacing=6, columnAttach=("both", 8))
        cmds.text(label="", height=2)
        cmds.text(align="left", label="Meshes:  %s_<part>_GEO        Groups:  <part>_GRP" % asset)
        cmds.rowLayout(numberOfColumns=3, adjustableColumn=2,
                       columnAttach=[(1, "right", 4), (2, "both", 0), (3, "left", 4)])
        cmds.text(label="Part")
        self.w["part"] = cmds.textField(
            placeholderText="e.g. seat, legL, wheelFront",
            textChangedCommand=lambda *_: self.preview(),
            enterCommand=lambda *_: self.name(),
            annotation="Several picked get 01, 02, ... A name something else has gets the "
                       "next number.")
        cmds.button(label="Name Selected", width=110, command=lambda *_: self.name())
        cmds.setParent("..")
        self.w["preview"] = cmds.text(label="", align="left")
        cmds.separator(height=8, style="in")
        cmds.text(label="Names to fix before a USD publish (click one to select it):",
                  align="left")
        self.w["problems"] = cmds.textScrollList(numberOfRows=10, allowMultiSelection=True,
                                                 selectCommand=lambda *_: self.pick())
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=1,
                       columnAttach=[(1, "both", 0), (2, "both", 4)])
        cmds.button(label="Check Names", height=28, command=lambda *_: self.check())
        cmds.button(label="Fix All", height=28, command=lambda *_: self.fix(),
                    annotation="Clashing names made unique, namespaces off, _GEO / _GRP and "
                               "the asset's name added, shapes named after their transform. "
                               "Maya's default names (pCube1) are left for you to name.")
        cmds.setParent("..")
        cmds.showWindow(NAMES_WINDOW)
        self.preview()
        self.check()

    def preview(self):
        part = usd.clean_part(cmds.textField(self.w["part"], query=True, text=True), self.asset)
        cmds.text(self.w["preview"], edit=True,
                  label="  -> %s_%s_GEO  /  %s_GRP" % (self.asset, part, part) if part else "")

    def name(self):
        part = cmds.textField(self.w["part"], query=True, text=True)
        try:
            cmds.undoInfo(openChunk=True, chunkName="USD Names")
            done = usd.name(_selection(), part, self.asset)
        except PublishError as e:
            return _say(str(e))
        finally:
            cmds.undoInfo(closeChunk=True)
        cmds.select([n for _, n in done], replace=True)
        cmds.inViewMessage(amg="Named <hl>%s</hl>" % ", ".join(n for _, n in done[:4]) +
                           (" and %d more" % (len(done) - 4) if len(done) > 4 else ""),
                           pos="topCenter", fade=True)
        self.check()

    def check(self):
        self._found = usd.problems(self.asset)
        cmds.textScrollList(self.w["problems"], edit=True, removeAll=True)
        for f in self._found:
            label = "%s   %s" % (f["name"], f["why"])
            if f["fix"] and f["fix"] != f["name"]:
                label += "   -> %s" % f["fix"]
            cmds.textScrollList(self.w["problems"], edit=True, append=label)
        if not self._found:
            cmds.textScrollList(self.w["problems"], edit=True,
                                append="All names are ready for USD.")

    def pick(self):
        rows = cmds.textScrollList(self.w["problems"], query=True, selectIndexedItem=True) or []
        nodes = [usd._path(self._found[i - 1]["uuid"]) for i in rows if i <= len(self._found)]
        nodes = [n for n in nodes if n]
        if nodes:
            cmds.select(nodes, replace=True)

    def fix(self):
        try:
            cmds.undoInfo(openChunk=True, chunkName="USD Names")
            done = usd.fix(self.asset)
        except PublishError as e:
            return _say(str(e))
        finally:
            cmds.undoInfo(closeChunk=True)
        self.check()
        left = len(self._found)
        cmds.inViewMessage(amg="Renamed <hl>%d</hl>.%s" % (
            len(done), " %d still need a name from you." % left if left else ""),
            pos="topCenter", fade=True)


def show_names():
    win = NamesWindow()
    win.build()
    return win
