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


HOW_TO_WINDOW = "modelToolUsdHowToWin"

HIERARCHY_HOW_TO = """USD HIERARCHY

Puts the model in the layout a USD publish needs:
   geo_USD     red in the Outliner: built (Publish writes it as geo)
      render    the meshes that render
      proxy     an optional light stand-in
Publish adds <asset>_model_GRP on top.

1. Open the asset's scene (saved in its scenes folder).
2. Click Build Hierarchy. With nothing selected, all geometry
   outside geo_USD goes into render.
3. To place things yourself: select them, then Selected to Render
   or Selected to Proxy. A mesh brings its whole top group, so your
   groups are kept (nest them as deep as you like). Nothing moves
   in the world.
4. Check the list "Geometry outside geo_USD" is empty (click a row to
   select it). Refresh updates it.
5. Next: USD Names, then Publish with USD ticked.

Ctrl+Z undoes each button in one step."""

NAMES_HOW_TO = """USD NAMES

Names meshes <asset>_<part>_GEO and groups <part>_GRP, unique and
USD-safe.

Naming your own model
1. Select meshes or groups, type a part name (seat, legL) and click
   Name Selected. Several get 01, 02, ...
2. Click Check Names; click a row to select that node.
3. Click Fix All. Maya default names (pCube1) are left for you:
   name those with step 1.

Cleaning an imported model (do these first)
1. Strip Namespaces: select the model's group (or nothing, for every
   namespace in the scene, materials too). References are skipped.
2. Remove text: select the group, click Name to Field and cut the
   name down to the junk (e.g. _TypeGrassColor03_), or type it.
   A * stands for any number: _TypeGrassColor*_. Check the preview
   line, then click Remove.
3. Renumber 000, 001, ...: select the group to number its meshes
   again, top to bottom in the Outliner.
4. Then Check Names and Fix All as above.

The tick box "and everything under the picked groups" applies to
Remove and Renumber. Ctrl+Z undoes each button in one step."""


def _how_to(title, text):
    """A small read-only window with a tool's how-to."""
    if cmds.window(HOW_TO_WINDOW, exists=True):
        cmds.deleteUI(HOW_TO_WINDOW)
    cmds.window(HOW_TO_WINDOW, title="How To: " + title, widthHeight=(460, 440))
    cmds.paneLayout()
    cmds.scrollField(text=text, editable=False, wordWrap=False, font="fixedWidthFont")
    cmds.showWindow(HOW_TO_WINDOW)


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
        cmds.window(HIERARCHY_WINDOW, title="USD Hierarchy", widthHeight=(360, 340))
        cmds.columnLayout(adjustableColumn=True, rowSpacing=6, columnAttach=("both", 8))
        cmds.text(label="", height=2)
        cmds.text(align="left", wordWrap=True, label=(
            "Publish puts this in <asset>_model_GRP, the USD's top prim:\n"
            "   geo_USD   red in the Outliner (written as geo)\n      render    the meshes that render\n"
            "      proxy     an optional light stand-in"))
        cmds.button(label="Build Hierarchy", height=32, command=lambda *_: self.make(),
                    annotation="Makes geo_USD (red), render and proxy. With nothing picked, the "
                               "geometry outside geo_USD goes into render.")
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnAttach=[(1, "both", 0),
                                                                           (2, "both", 4)])
        cmds.button(label="Selected to Render", height=28,
                    command=lambda *_: self.add(usd.RENDER))
        cmds.button(label="Selected to Proxy", height=28,
                    command=lambda *_: self.add(usd.PROXY))
        cmds.setParent("..")
        cmds.text(label="Geometry outside geo_USD (not in the USD's layout):", align="left")
        self.w["left"] = cmds.textScrollList(numberOfRows=6, allowMultiSelection=True,
                                             selectCommand=lambda *_: self.pick())
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=1,
                       columnAttach=[(1, "both", 0), (2, "both", 4)])
        cmds.button(label="Refresh", height=24, command=lambda *_: self.refresh())
        cmds.button(label="How To", height=24, width=80,
                    command=lambda *_: _how_to("USD Hierarchy", HIERARCHY_HOW_TO))
        cmds.setParent("..")
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
        self.warn_strays()

    def warn_strays(self):
        found = usd.strays()
        if found:
            _say("These cameras / lights came into geo_USD with their group and don't belong "
                 "in the model's USD. Move them out of geo_USD:\n  %s"
                 % "\n  ".join(n.split("|")[-1] for n in found[:15]))

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
        cmds.inViewMessage(amg="<hl>%d</hl> moved into geo_USD|%s." % (len(moved), purpose),
                           pos="topCenter", fade=True)
        self.warn_strays()


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
        cmds.window(NAMES_WINDOW, title="USD Names: %s" % asset, widthHeight=(460, 590))
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

        # Imported models: unwanted text and namespaces (user 2026-11-23).
        cmds.text(label="Imported models: take out text an import added to the names",
                  align="left")
        cmds.rowLayout(numberOfColumns=3, adjustableColumn=2,
                       columnAttach=[(1, "right", 4), (2, "both", 0), (3, "left", 4)])
        cmds.text(label="Text")
        self.w["text"] = cmds.textField(
            placeholderText="e.g. _TypeGrassColor03_  or  _TypeGrassColor*_",
            textChangedCommand=lambda *_: self.preview_text(),
            enterCommand=lambda *_: self.remove_text(),
            annotation="Every time it's in a name it comes out; the gap is left as one _. "
                       "A * stands for any letters or digits up to the next _: "
                       "_TypeGrassColor*_ takes out _TypeGrassColor03_, "
                       "_TypeGrassColor003_, ...")
        cmds.button(label="Remove", width=110, command=lambda *_: self.remove_text())
        cmds.setParent("..")
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=1,
                       columnAttach=[(1, "left", 30), (2, "both", 4)])
        self.w["below"] = cmds.checkBox(label="and everything under the picked groups",
                                        value=True,
                                        changeCommand=lambda *_: self.preview_text())
        cmds.button(label="Name to Field", width=110, command=lambda *_: self.name_to_field(),
                    annotation="Puts the picked name in the Text field, to cut down to the "
                               "part to remove.")
        cmds.setParent("..")
        self.w["text_preview"] = cmds.text(label="", align="left")
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=1,
                       columnAttach=[(1, "both", 0), (2, "both", 4)])
        cmds.button(label="Renumber 000, 001, ...", height=28,
                    command=lambda *_: self.renumber(),
                    annotation="Numbers the picked meshes (or the meshes under the picked "
                               "groups) again from 000, top to bottom in the Outliner: "
                               "grassB_017102_GEO -> grassB_000_GEO. Each name numbered on "
                               "its own.")
        cmds.button(label="Strip Namespaces", height=28, command=lambda *_: self.strip(),
                    annotation="Off what's picked and everything under it. With nothing "
                               "picked: every namespace in the scene (materials too), not "
                               "references. A name already taken gets the next number.")
        cmds.setParent("..")
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
        cmds.button(label="How To", height=24,
                    command=lambda *_: _how_to("USD Names", NAMES_HOW_TO))
        cmds.showWindow(NAMES_WINDOW)
        cmds.scriptJob(event=["SelectionChanged", self.preview_text], parent=NAMES_WINDOW)
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

    def _text(self):
        return cmds.textField(self.w["text"], query=True, text=True)

    def _below(self):
        return cmds.checkBox(self.w["below"], query=True, value=True)

    def preview_text(self):
        label = ""
        text = self._text().strip()
        picked = _selection()
        if text and picked:
            try:
                done, skipped = usd.remove_text(picked, text, self._below(), dry_run=True)
                label = "  %d name%s: %s -> %s" % (len(done), "" if len(done) == 1 else "s",
                                                   done[0][0], done[0][1]) if done else ""
                if skipped:
                    label += "   (%d skipped)" % len(skipped)
            except PublishError as e:
                label = "  " + str(e)
        elif text:
            label = "  Pick the objects or groups first."
        cmds.text(self.w["text_preview"], edit=True, label=label)

    def name_to_field(self):
        picked = _selection()
        if not picked:
            return _say("Pick an object whose name has the text in it.")
        cmds.textField(self.w["text"], edit=True,
                       text=picked[0].split("|")[-1].split(":")[-1])
        self.preview_text()

    def remove_text(self):
        picked = _selection()
        if not picked:
            return _say("Pick the objects or groups to take the text out of.")
        try:
            cmds.undoInfo(openChunk=True, chunkName="USD Names")
            done, skipped = usd.remove_text(picked, self._text(), self._below())
        except PublishError as e:
            return _say(str(e))
        finally:
            cmds.undoInfo(closeChunk=True)
        if skipped:
            _say("Renamed %d. Left as they were:\n  %s" % (
                len(done), "\n  ".join("%s: %s" % s for s in skipped[:15])))
        else:
            cmds.inViewMessage(amg="Renamed <hl>%d</hl>." % len(done),
                               pos="topCenter", fade=True)
        self.preview_text()
        self.check()

    def renumber(self):
        picked = _selection()
        if not picked:
            return _say("Pick the meshes, or the group they're in, to number.")
        try:
            cmds.undoInfo(openChunk=True, chunkName="USD Names")
            cmds.waitCursor(state=True)
            done = usd.renumber(picked, self._below())
        except PublishError as e:
            return _say(str(e))
        finally:
            cmds.waitCursor(state=False)
            cmds.undoInfo(closeChunk=True)
        cmds.inViewMessage(amg="Renumbered <hl>%d</hl>%s." % (
            len(done), ": %s ... %s" % (done[0][1], done[-1][1]) if done else ""),
            pos="topCenter", fade=True)
        self.preview_text()
        self.check()

    def strip(self):
        picked = _selection()
        try:
            cmds.undoInfo(openChunk=True, chunkName="USD Names")
            done, removed = usd.strip_namespaces(picked or None)
        except PublishError as e:
            return _say(str(e))
        finally:
            cmds.undoInfo(closeChunk=True)
        if not done:
            return _say("No namespaces on %s." % ("what's picked" if picked else
                                                  "the scene's own nodes"))
        cmds.inViewMessage(amg="Namespace off <hl>%d</hl>%s." % (
            len(done), "; removed %s" % ", ".join(removed) if removed else ""),
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
