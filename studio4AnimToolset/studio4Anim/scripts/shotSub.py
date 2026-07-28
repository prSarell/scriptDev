# ------------------------------------------------------------
# shotSub.py
#
# Standalone Maya Shot Submission Tool
# (fork of pbTool — see pipeDev/pbToolDev/pbTool.py — intended to grow
# ShotGrid publish support and eventually replace pbTool)
#
# Features:
# - Separate standalone UI (no tabs)
# - Auto-derives playblast save path from current Maya project
# - Mirrors folder structure from:
#     <project>/scenes/...
#   into:
#     <project>/images/...
# - Saves playblasts to:
#     <project>/images/<scene-relative-folder>/v###
# - JPEG sequence only
# - Opens sequence in viewer after playblast
# - Burn-ins drawn directly onto JPEGs after playblast:
#     top-left   = frame rate
#     top-middle = scene filename
#     top-right  = frame number
# - Optional keep/delete workflow, plus an auto-prune cap on local versions
#   (local playblasts are disposable -- ShotGrid is the record of truth
#   once a version is published)
# - Uses render resolution from Maya render settings
# - Assumes ONE Maya project per film/show (single cmds.workspace, opened
#   manually by the student and left alone) -- shots/assets are plain
#   subfolders under its scenes/ directory, not separate nested Maya
#   projects. "Which shot is this" is resolved structurally, from where
#   the currently-open scene file sits under scenes/ (see
#   get_scene_relative_folder_from_scenes()/get_scene_folder_path()), not
#   from a per-shot workspace.
# - "Link to ShotGrid" writes a local shotgrid_link.json marker into the
#   current scene's own scenes/<sequence>/<shot> subfolder (see
#   get_link_file_path()), storing an explicit ShotGrid Project id + Shot
#   id (picked from existing ShotGrid Projects/Shots -- shotSub never
#   creates a Shot itself; Shots are created directly in ShotGrid's web UI
#   by the lecturer/TD).
#   "Publish Selected Version" then hands that shot_id off to
#   shotgridConnect.upload_playblast() (see
#   pipeDev/shotSubDev/shotgridConnect.py) -- shotSub owns its own
#   ShotGrid connection (Script API key + sudo_as_login, read from
#   <Maya userPrefDir>/shotSub_config.json), independent of JiffySG (see
#   timeManagementDev/jiffySGDev/), which is currently paused.
#   shotgridConnect.upload_playblast() creates a real ShotGrid Version
#   (+ Note, + Shot/Version thumbnail, + an rvio-encoded review movie,
#   using shotSub's own find_rv_executable() to locate rvio) from this
#   hand-off.
#
# Shelf button:
# import importlib
# import shotSub
# importlib.reload(shotSub)
# shotSub.show_shotSub()
# ------------------------------------------------------------

from __future__ import print_function

import os
import re
import json
import glob
import shutil
import subprocess
import threading
import time
from datetime import datetime

import maya.cmds as cmds
import maya.mel as mel
import maya.utils

# Qt binding in Maya
QT_AVAILABLE = True
try:
    from PySide6 import QtGui, QtCore, QtWidgets
except Exception:
    try:
        from PySide2 import QtGui, QtCore, QtWidgets
    except Exception:
        QT_AVAILABLE = False
        QtGui = None
        QtCore = None
        QtWidgets = None


class ShotSub(object):
    WINDOW_NAME = "shotSubWindow"
    RV_TAG = "shotSub"

    def __init__(self):
        self.widgets = {}
        self.last_created_version_folder = ""
        self.last_created_files = []
        # Tracks the RV process we launched directly for audio review (bypasses
        # rvpush -- see open_in_rv_with_audio) so the previous one can be closed
        # before opening a new one, instead of piling up windows.
        self.audio_rv_process = None

    # --------------------------------------------------------
    # UI
    # --------------------------------------------------------
    def show(self):
        if cmds.window(self.WINDOW_NAME, exists=True):
            cmds.deleteUI(self.WINDOW_NAME)

        cmds.window(
            self.WINDOW_NAME,
            title="shotSub - Playblast Manager",
            sizeable=True,
            widthHeight=(560, 820)
        )

        scroll = cmds.scrollLayout(childResizable=True)
        root = cmds.columnLayout(adj=True, parent=scroll)
        cmds.separator(h=8, style="none")

        cmds.frameLayout(
            label="Output Location",
            collapsable=False,
            marginHeight=8,
            marginWidth=8,
            parent=root
        )
        inner = cmds.columnLayout(adj=True)
        self.widgets["scene_field"] = self._readonly_field("Scene File")
        self.widgets["shot_field"] = self._readonly_field("Shot Folder")
        self.widgets["version_field"] = self._readonly_field("Next Version")
        self.widgets["output_field"] = self._readonly_field("Output Folder")
        self.widgets["resolution_field"] = self._readonly_field("Render Size")

        cmds.separator(h=6, style="none")
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnWidth2=(180, 180))
        cmds.button(label="Refresh Path Info", h=30, c=lambda *_: self.refresh_ui_state())
        cmds.button(label="Open Output Folder", h=30, c=lambda *_: self.open_output_folder())
        cmds.setParent("..")
        cmds.setParent("..")

        cmds.separator(h=6, style="none")

        cmds.frameLayout(
            label="ShotGrid Link",
            collapsable=False,
            marginHeight=8,
            marginWidth=8,
            parent=root
        )
        inner = cmds.columnLayout(adj=True)
        self.widgets["link_status_field"] = self._readonly_field("Linked Shot")
        cmds.separator(h=6, style="none")
        cmds.button(label="Link to ShotGrid", h=30, c=lambda *_: self.link_to_shotgrid())
        cmds.setParent("..")
        cmds.setParent("..")

        cmds.separator(h=6, style="none")

        cmds.frameLayout(
            label="Burn-ins",
            collapsable=False,
            marginHeight=8,
            marginWidth=8,
            parent=root
        )
        inner = cmds.columnLayout(adj=True)
        self.widgets["show_fps"] = cmds.checkBox(label="Show Frame Rate", value=True)
        self.widgets["show_scene"] = cmds.checkBox(label="Show Scene Name", value=True)
        self.widgets["show_frame"] = cmds.checkBox(label="Show Frame Number", value=True)
        self.widgets["show_focal"] = cmds.checkBox(label="Show Focal Length", value=True)
        self.widgets["show_student"] = cmds.checkBox(label="Show Student Name/ID", value=True)
        cmds.setParent("..")
        cmds.setParent("..")

        cmds.separator(h=6, style="none")

        cmds.frameLayout(
            label="File Options",
            collapsable=False,
            marginHeight=8,
            marginWidth=8,
            parent=root
        )
        inner = cmds.columnLayout(adj=True)
        self.widgets["keep_files"] = cmds.checkBox(label="Keep Playblast Files", value=True)
        self.widgets["open_in_rv"] = cmds.checkBox(label="Open in RV", value=True)
        cmds.separator(h=6, style="none")
        auto_prune = self.get_auto_prune_enabled()
        self.widgets["auto_prune"] = cmds.checkBox(
            label="Auto-prune old local versions",
            value=auto_prune,
            changeCommand=lambda checked: self._on_auto_prune_toggled(checked)
        )
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnWidth2=(200, 60))
        cmds.text(label="Max Local Versions")
        self.widgets["max_versions"] = cmds.intField(
            value=self.get_max_versions_to_keep(),
            minValue=0,
            width=60,
            enable=auto_prune,
            changeCommand=lambda value: self.set_max_versions_to_keep(value)
        )
        cmds.setParent("..")
        cmds.setParent("..")

        cmds.separator(h=6, style="none")

        cmds.frameLayout(
            label="Local Versions",
            collapsable=False,
            marginHeight=8,
            marginWidth=8,
            parent=root
        )
        inner = cmds.columnLayout(adj=True)
        self.widgets["version_list"] = cmds.textScrollList(numberOfRows=6, allowMultiSelection=False)
        cmds.separator(h=6, style="none")
        cmds.text(label="Notes (sent with this publish)", align="left")
        self.widgets["publish_notes"] = cmds.scrollField(
            height=50,
            wordWrap=True,
            annotation='e.g. "blocking pass, ignore the left arm" — posted '
                       "to ShotGrid with the selected version."
        )
        cmds.separator(h=6, style="none")
        cmds.button(label="Publish Selected Version", h=30, c=lambda *_: self.publish_selected_version())
        cmds.setParent("..")
        cmds.setParent("..")

        cmds.separator(h=6, style="none")

        cmds.frameLayout(
            label="Actions",
            collapsable=False,
            marginHeight=8,
            marginWidth=8,
            parent=root
        )
        inner = cmds.columnLayout(adj=True)
        cmds.button(label="Create Playblast", h=40, c=lambda *_: self.create_playblast())
        cmds.separator(h=8, style="none")
        cmds.button(label="Delete Last Playblast", h=30, c=lambda *_: self.delete_last_playblast())
        cmds.setParent("..")
        cmds.setParent("..")

        cmds.separator(h=8, style="none")

        self.refresh_ui_state()
        cmds.showWindow(self.WINDOW_NAME)

    def _readonly_field(self, label):
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=2, columnWidth2=(100, 380))
        cmds.text(label=label)
        field = cmds.textField(editable=False)
        cmds.setParent("..")
        return field

    # --------------------------------------------------------
    # Scene / path helpers
    # --------------------------------------------------------
    def get_scene_path(self):
        return cmds.file(q=True, sn=True) or ""

    def ensure_scene_saved(self):
        scene_path = self.get_scene_path()
        if not scene_path:
            raise RuntimeError("Please save the scene before creating a playblast.")
        return scene_path

    def get_scene_name(self):
        return os.path.basename(self.ensure_scene_saved())

    def get_scene_basename_no_ext(self):
        return os.path.splitext(self.get_scene_name())[0]

    def get_project_root(self):
        root = cmds.workspace(q=True, rootDirectory=True)
        if not root:
            raise RuntimeError("Unable to determine Maya project root.")
        return os.path.normpath(os.path.abspath(root))

    def get_images_root(self):
        images_root = os.path.join(self.get_project_root(), "images")
        if not os.path.isdir(images_root):
            os.makedirs(images_root)
        return images_root

    def get_scenes_root(self):
        project_root = self.get_project_root()
        # cmds.workspace(fileRuleEntry="scene", query=True) raises
        # "Flag 'fileRuleEntry' must be passed a boolean argument when query
        # flag is set" in real Maya (confirmed on 2025) -- a broken Python
        # binding for this flag combo even though the equivalent MEL command
        # works fine, so query through mel.eval instead.
        scene_rule = mel.eval('workspace -q -fileRuleEntry "scene";') or "scenes"
        return os.path.normpath(os.path.join(project_root, scene_rule))

    def get_scene_relative_folder_from_scenes(self):
        """
        Returns the scene directory path relative to the current Maya
        project's own scenes directory (its workspace "scene" file rule,
        normally "scenes") -- not a bare string search for "scenes"
        anywhere in the absolute path, since one Maya project can contain
        several sequence/shot subfolders under scenes/ that would each
        match a naive search.

        Example:
            <project>/scenes/sequence001/shot001/file.ma
        returns:
            sequence001/shot001
        """
        scene_path = os.path.normpath(os.path.abspath(self.ensure_scene_saved()))
        scene_dir = os.path.dirname(scene_path)
        scenes_root = self.get_scenes_root()

        cmp_scene_dir = scene_dir.lower() if cmds.about(nt=True) else scene_dir
        cmp_scenes_root = scenes_root.lower() if cmds.about(nt=True) else scenes_root

        if cmp_scene_dir != cmp_scenes_root and not cmp_scene_dir.startswith(cmp_scenes_root + os.sep):
            raise RuntimeError(
                "Scene is not saved inside the current Maya project's scenes "
                "folder ('{0}'). Save it there before publishing.".format(scenes_root)
            )

        relative = os.path.relpath(scene_dir, scenes_root)
        return "" if relative == "." else relative

    def get_scene_folder_path(self):
        """Absolute path to the current scene's own subfolder inside the
        project's scenes/ directory -- e.g. <project_root>/scenes/
        sequence001/shot001. This is also where Jiffy SG's per-Shot/Asset
        "Settings" link writes shotgrid_link.json (see jiffySG.py's
        _link_item_folder) -- shotSub resolving its link/publish-log paths
        the same way is what lets the two tools agree on "which shot is
        this" structurally, from where the scene file actually is, rather
        than either one guessing from names."""
        relative_folder = self.get_scene_relative_folder_from_scenes()
        scenes_root = self.get_scenes_root()
        return os.path.join(scenes_root, relative_folder) if relative_folder else scenes_root

    def get_shot_root(self, create=True):
        images_root = self.get_images_root()
        relative_folder = self.get_scene_relative_folder_from_scenes()

        if relative_folder:
            shot_root = os.path.normpath(os.path.join(images_root, relative_folder))
        else:
            shot_root = images_root

        if create and not os.path.isdir(shot_root):
            os.makedirs(shot_root)

        return shot_root

    def get_existing_version_numbers(self, shot_root):
        version_numbers = []
        if not os.path.isdir(shot_root):
            return version_numbers

        for name in os.listdir(shot_root):
            full_path = os.path.join(shot_root, name)
            if os.path.isdir(full_path):
                match = re.match(r"^v(\d{3})$", name, flags=re.IGNORECASE)
                if match:
                    version_numbers.append(int(match.group(1)))

        return sorted(version_numbers)

    def get_next_version_folder(self, create=False):
        shot_root = self.get_shot_root(create=create)
        existing = self.get_existing_version_numbers(shot_root)
        next_num = existing[-1] + 1 if existing else 1
        version_folder = os.path.join(shot_root, "v{0:03d}".format(next_num))

        if create and not os.path.isdir(version_folder):
            os.makedirs(version_folder)

        return version_folder

    # --------------------------------------------------------
    # Version rotation — mirrors Maya's autosave "number of saves" cap so
    # playblast JPEG sequences don't quietly fill up student drives. Ported
    # from the same feature already shipped in pbTool (mpToolSet/
    # studio4AnimToolset) -- local versions are disposable once ShotGrid is
    # the record of truth for anything actually published.
    # --------------------------------------------------------
    MAX_VERSIONS_OPTIONVAR = "shotSub_maxLocalVersions"
    AUTO_PRUNE_OPTIONVAR = "shotSub_autoPruneEnabled"
    DEFAULT_MAX_VERSIONS = 5

    def get_max_versions_to_keep(self):
        if cmds.optionVar(exists=self.MAX_VERSIONS_OPTIONVAR):
            return cmds.optionVar(q=self.MAX_VERSIONS_OPTIONVAR)
        return self.DEFAULT_MAX_VERSIONS

    def set_max_versions_to_keep(self, value):
        cmds.optionVar(iv=(self.MAX_VERSIONS_OPTIONVAR, max(0, int(value))))

    def get_auto_prune_enabled(self):
        if cmds.optionVar(exists=self.AUTO_PRUNE_OPTIONVAR):
            return bool(cmds.optionVar(q=self.AUTO_PRUNE_OPTIONVAR))
        return True

    def set_auto_prune_enabled(self, enabled):
        cmds.optionVar(iv=(self.AUTO_PRUNE_OPTIONVAR, 1 if enabled else 0))

    def _on_auto_prune_toggled(self, checked):
        self.set_auto_prune_enabled(checked)
        cmds.intField(self.widgets["max_versions"], edit=True, enable=checked)

    def prune_old_versions(self, shot_root, max_versions):
        """
        Delete the oldest version folders in shot_root until at most
        max_versions remain. max_versions <= 0 means unlimited (no-op).

        Deletes unconditionally, regardless of whether a version was ever
        published to ShotGrid (see shotgrid_publish_log.json / decision to
        use a straight rolling window, not gated on publish status) --
        prints a non-blocking warning when a pruned version was never
        published, so the deletion stays visible without being blocked.
        """
        if max_versions <= 0:
            return

        existing = self.get_existing_version_numbers(shot_root)
        excess_count = len(existing) - max_versions
        if excess_count <= 0:
            return

        publish_log = self.read_publish_log()

        for version_num in existing[:excess_count]:
            version_name = "v{0:03d}".format(version_num)
            version_folder = os.path.join(shot_root, version_name)
            if version_name not in publish_log:
                cmds.warning(
                    "shotSub: pruning local version '{0}' that was never "
                    "published to ShotGrid (retention cap is {1}).".format(
                        version_name, max_versions))
            try:
                shutil.rmtree(version_folder)
                print("shotSub: pruned old version {0} (keeping last {1})".format(
                    version_folder, max_versions))
            except Exception as exc:
                cmds.warning("shotSub: could not prune {0} — {1}".format(version_folder, exc))

    def get_playblast_prefix(self, version_folder):
        return os.path.join(version_folder, self.get_scene_basename_no_ext())

    def refresh_ui_state(self):
        scene_path = self.get_scene_path()
        scene_name = os.path.basename(scene_path) if scene_path else "<unsaved scene>"
        shot_folder = "<unsaved scene>"
        next_version = ""
        output_folder = ""
        render_size = ""

        if scene_path:
            try:
                shot_folder = self.get_scene_relative_folder_from_scenes() or "<scenes root>"
                output_folder = self.get_next_version_folder(create=False)
                next_version = os.path.basename(output_folder)
            except Exception as exc:
                shot_folder = "<invalid scenes path>"
                next_version = "<n/a>"
                output_folder = str(exc)

        try:
            width, height = self.get_render_resolution()
            render_size = "{0} x {1}".format(width, height)
        except Exception:
            render_size = "<unable to read render settings>"

        cmds.textField(self.widgets["scene_field"], e=True, text=scene_name)
        cmds.textField(self.widgets["shot_field"], e=True, text=shot_folder)
        cmds.textField(self.widgets["version_field"], e=True, text=next_version)
        cmds.textField(self.widgets["output_field"], e=True, text=output_folder)
        cmds.textField(self.widgets["resolution_field"], e=True, text=render_size)

        link = self.read_shotgrid_link()
        link_text = "{0} / {1}".format(link["sg_project_name"], link["sg_entity_code"]) if link else "<not linked>"
        cmds.textField(self.widgets["link_status_field"], e=True, text=link_text)

        self.populate_version_list()

    # --------------------------------------------------------
    # ShotGrid link + publish-log (local marker files only -- no
    # credentials live here, see the module header comment)
    # --------------------------------------------------------
    LINK_FILENAME = "shotgrid_link.json"
    PUBLISH_LOG_FILENAME = "shotgrid_publish_log.json"

    def get_link_file_path(self):
        # Lives in the current scene's own scenes/ subfolder, not the bare
        # project root -- one Maya project now covers the whole film, so a
        # single project-root marker file could only ever represent one
        # shot. See get_scene_folder_path()'s docstring.
        return os.path.join(self.get_scene_folder_path(), self.LINK_FILENAME)

    def read_shotgrid_link(self):
        """Returns the current scene's shotgrid_link.json as a dict, or
        None if unlinked/unreadable. A corrupt file warns (visible mistake)
        rather than silently behaving as unlinked.

        Generalized keys are sg_entity_type/sg_entity_id/sg_entity_code
        (schema_version 2 -- covers both Shots and Assets, written either by
        link_to_shotgrid() below or by Jiffy SG's per-row "Settings" link,
        see jiffySG.py's _link_item_folder). schema_version 1 files
        (sg_shot_id/sg_shot_code, Shot-only -- from
        before Assets were supported) are migrated on read so projects
        linked before this change don't silently break; new writes always
        use v2."""
        try:
            path = self.get_link_file_path()
        except Exception:
            return None
        if not os.path.isfile(path):
            return None
        try:
            with open(path, "r") as f:
                data = json.load(f)
        except (ValueError, OSError) as exc:
            cmds.warning("shotSub: could not read {0} — {1}".format(path, exc))
            return None

        if data.get("schema_version") == 1:
            data["sg_entity_type"] = "Shot"
            data["sg_entity_id"] = data.get("sg_shot_id")
            data["sg_entity_code"] = data.get("sg_shot_code")
        return data

    def write_shotgrid_link(self, sg_project_id, sg_project_name, entity_type, entity_id, entity_code):
        """Writes the explicit ShotGrid Project id + Shot-or-Asset id this
        project is linked to. Ids are authoritative for every downstream
        ShotGrid call (upload_playblast() keys off entity_type/entity_id
        alone) -- the name/code fields are display-only convenience copies,
        never re-resolved by name, so a later ShotGrid rename can't break
        the link the way folder-name guessing could."""
        linked_by = ""
        try:
            import shotgridConnect
            linked_by = shotgridConnect.current_login()
        except Exception:
            pass

        data = {
            "schema_version": 2,
            "sg_project_id": sg_project_id,
            "sg_project_name": sg_project_name,
            "sg_entity_type": entity_type,
            "sg_entity_id": entity_id,
            "sg_entity_code": entity_code,
            "linked_at": datetime.now().isoformat(timespec="seconds"),
            "linked_by": linked_by,
        }
        with open(self.get_link_file_path(), "w") as f:
            json.dump(data, f, indent=2)
        return data

    def get_publish_log_path(self):
        # Same reasoning as get_link_file_path(): rooted at the current
        # scene's own scenes/ subfolder, not project root -- a single
        # project-root log would collide version names (e.g. "v001") across
        # every shot in the film, mislabeling other shots' versions as
        # published/pruneable.
        return os.path.join(self.get_scene_folder_path(), self.PUBLISH_LOG_FILENAME)

    def read_publish_log(self):
        try:
            path = self.get_publish_log_path()
        except Exception:
            return {}
        if not os.path.isfile(path):
            return {}
        try:
            with open(path, "r") as f:
                return json.load(f)
        except (ValueError, OSError) as exc:
            cmds.warning("shotSub: could not read {0} — {1}".format(path, exc))
            return {}

    def write_publish_log(self, log):
        with open(self.get_publish_log_path(), "w") as f:
            json.dump(log, f, indent=2)

    def mark_version_published(self, version_name, sg_version_id=None):
        linked_by = ""
        try:
            import shotgridConnect
            linked_by = shotgridConnect.current_login()
        except Exception:
            pass

        log = self.read_publish_log()
        log[version_name] = {
            "published_at": datetime.now().isoformat(timespec="seconds"),
            "published_by": linked_by,
            "sg_version_id": sg_version_id,
        }
        self.write_publish_log(log)

    def is_version_published(self, version_name):
        return version_name in self.read_publish_log()

    def get_local_versions(self):
        """[{"name": "v005", "path": ..., "published": bool}, ...] for the
        current shot's local versions, newest first. [] if the scene is
        unsaved or not inside the current project's scenes folder."""
        try:
            shot_root = self.get_shot_root(create=False)
        except Exception:
            return []

        publish_log = self.read_publish_log()
        versions = []
        for version_num in reversed(self.get_existing_version_numbers(shot_root)):
            name = "v{0:03d}".format(version_num)
            versions.append({
                "name": name,
                "path": os.path.join(shot_root, name),
                "published": name in publish_log,
            })
        return versions

    def populate_version_list(self):
        if "version_list" not in self.widgets:
            return
        cmds.textScrollList(self.widgets["version_list"], e=True, removeAll=True)
        for version in self.get_local_versions():
            label = "{0}  [published]".format(version["name"]) if version["published"] else version["name"]
            cmds.textScrollList(self.widgets["version_list"], e=True, append=label)

    def get_selected_version_folder(self):
        if "version_list" not in self.widgets:
            return None
        selected = cmds.textScrollList(self.widgets["version_list"], q=True, selectItem=True)
        if not selected:
            return None
        version_name = selected[0].split()[0]
        for version in self.get_local_versions():
            if version["name"] == version_name:
                return version["path"]
        return None

    # --------------------------------------------------------
    # Camera / viewport helpers
    # --------------------------------------------------------
    def get_active_model_panel(self):
        panel = cmds.getPanel(withFocus=True)
        if panel and cmds.getPanel(typeOf=panel) == "modelPanel":
            return panel

        visible_panels = cmds.getPanel(vis=True) or []
        for panel_name in visible_panels:
            if cmds.getPanel(typeOf=panel_name) == "modelPanel":
                return panel_name

        raise RuntimeError("Unable to determine an active model panel.")

    def get_render_resolution(self):
        width = cmds.getAttr("defaultResolution.width")
        height = cmds.getAttr("defaultResolution.height")

        width = max(64, int(width))
        height = max(64, int(height))

        return [width, height]

    # --------------------------------------------------------
    # Frame / playback helpers
    # --------------------------------------------------------
    def get_frame_rate_label(self):
        unit = cmds.currentUnit(q=True, time=True)
        mapping = {
            "game": "15 fps",
            "film": "24 fps",
            "pal": "25 fps",
            "ntsc": "30 fps",
            "show": "48 fps",
            "palf": "50 fps",
            "ntscf": "60 fps",
        }

        if unit in mapping:
            return mapping[unit]

        if unit.lower().endswith("fps"):
            return unit.lower()

        return unit

    def get_frame_range(self):
        start = int(round(cmds.playbackOptions(q=True, minTime=True)))
        end = int(round(cmds.playbackOptions(q=True, maxTime=True)))
        return start, end

    def get_scene_audio_info(self):
        """
        Returns (audio_file_path, offset_frames) for the audio node currently
        shown on Maya's time slider -- Maya's own concept of "the reference
        audio for this scene" -- or (None, 0) if no audio is set there.
        """
        try:
            time_control = mel.eval("$tmpVar=$gPlayBackSlider")
            audio_node = cmds.timeControl(time_control, query=True, sound=True)
        except Exception:
            return None, 0

        if not audio_node:
            return None, 0

        filename = cmds.getAttr(audio_node + ".filename")
        if not filename or not os.path.isfile(filename):
            return None, 0

        offset = cmds.getAttr(audio_node + ".offset")
        return filename, offset

    def get_fps_value(self):
        return mel.eval("currentTimeUnitToFPS")

    # --------------------------------------------------------
    # Burn-in drawing
    # --------------------------------------------------------
    def _parse_frame_number_from_file(self, filepath):
        basename = os.path.basename(filepath)
        match = re.search(r"\.(\d+)\.jpg$", basename, flags=re.IGNORECASE)
        if match:
            return match.group(1)
        return ""

    def _draw_text_block(self, painter, rect, text, alignment):
        if not text:
            return

        shadow_pen = QtGui.QPen(QtGui.QColor(0, 0, 0, 180))
        painter.setPen(shadow_pen)
        shadow_rect = QtCore.QRect(rect)
        shadow_rect.translate(2, 2)
        painter.drawText(shadow_rect, alignment, text)

        main_pen = QtGui.QPen(QtGui.QColor(255, 255, 255, 230))
        painter.setPen(main_pen)
        painter.drawText(rect, alignment, text)

    def apply_burnins_to_sequence(self, files):
        if not files:
            return

        if not QT_AVAILABLE:
            cmds.warning("Qt image tools are unavailable. Playblast was created without burn-ins.")
            return

        show_fps = cmds.checkBox(self.widgets["show_fps"], q=True, value=True)
        show_scene = cmds.checkBox(self.widgets["show_scene"], q=True, value=True)
        show_frame = cmds.checkBox(self.widgets["show_frame"], q=True, value=True)
        show_focal = cmds.checkBox(self.widgets["show_focal"], q=True, value=True)
        show_student = cmds.checkBox(self.widgets["show_student"], q=True, value=True)

        fps_text = self.get_frame_rate_label() if show_fps else ""
        scene_text = self.get_scene_name() if show_scene else ""

        # Reads whatever's already saved (see ensure_student_identity()) --
        # deliberately does NOT prompt here, so a playblast never blocks on
        # a dialog; just omits the burn-in if nothing's been entered yet.
        student_text = ""
        if show_student:
            identity = self.read_student_identity()
            if identity:
                student_text = "{0} ({1})".format(identity["student_name"], identity["student_id"])

        render_width, render_height = self.get_render_resolution()
        render_aspect = float(render_width) / float(render_height)

        target_aspect = render_aspect
        focal_text = ""
        try:
            panel = self.get_active_model_panel()
            cam = cmds.modelEditor(panel, q=True, camera=True)

            if cmds.objectType(cam) == "transform":
                shapes = cmds.listRelatives(cam, shapes=True, fullPath=True) or []
                cam_shapes = [s for s in shapes if cmds.nodeType(s) == "camera"]
                if cam_shapes:
                    cam = cam_shapes[0]

            if cmds.nodeType(cam) == "camera":
                h_ap = cmds.getAttr(cam + ".horizontalFilmAperture")
                v_ap = cmds.getAttr(cam + ".verticalFilmAperture")
                if v_ap and v_ap != 0:
                    target_aspect = float(h_ap) / float(v_ap)
                if show_focal:
                    fl = cmds.getAttr(cam + ".focalLength")
                    focal_text = "{0:.0f}mm".format(fl)
        except Exception:
            pass

        for filepath in files:
            image = QtGui.QImage(filepath)
            if image.isNull():
                continue

            painter = QtGui.QPainter(image)
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            painter.setRenderHint(QtGui.QPainter.TextAntialiasing, True)

            width = image.width()
            height = image.height()
            image_aspect = float(width) / float(height)

            if image_aspect > target_aspect:
                active_height = height
                active_width = int(round(height * target_aspect))
                active_x = int(round((width - active_width) * 0.5))
                active_y = 0
            else:
                active_width = width
                active_height = int(round(width / target_aspect))
                active_x = 0
                active_y = int(round((height - active_height) * 0.5))

            font_size = max(12, int(active_height * 0.022))
            margin_x = max(36, int(active_width * 0.04))
            text_height = max(34, int(active_height * 0.055))
            top_inset = active_y + max(28, int(active_height * 0.04))
            bottom_inset = active_y + active_height - max(28, int(active_height * 0.04)) - text_height

            font = QtGui.QFont("Arial", font_size)
            font.setBold(True)
            painter.setFont(font)

            frame_text = self._parse_frame_number_from_file(filepath) if show_frame else ""

            left_rect = QtCore.QRect(
                active_x + margin_x,
                top_inset,
                int(active_width * 0.25) - margin_x,
                text_height
            )

            center_rect = QtCore.QRect(
                active_x + int(active_width * 0.25),
                top_inset,
                int(active_width * 0.50),
                text_height
            )

            right_rect = QtCore.QRect(
                active_x + int(active_width * 0.75),
                top_inset,
                int(active_width * 0.25) - margin_x,
                text_height
            )

            self._draw_text_block(
                painter,
                left_rect,
                fps_text,
                int(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            )

            self._draw_text_block(
                painter,
                center_rect,
                scene_text,
                int(QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter)
            )

            self._draw_text_block(
                painter,
                right_rect,
                frame_text,
                int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            )

            bottom_left_rect = QtCore.QRect(
                active_x + margin_x,
                bottom_inset,
                int(active_width * 0.25) - margin_x,
                text_height
            )
            self._draw_text_block(
                painter,
                bottom_left_rect,
                focal_text,
                int(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            )

            # Bottom-right (unused by any other burn-in) -- see
            # ensure_student_identity()/read_student_identity() above.
            bottom_right_rect = QtCore.QRect(
                active_x + int(active_width * 0.75),
                bottom_inset,
                int(active_width * 0.25) - margin_x,
                text_height
            )
            self._draw_text_block(
                painter,
                bottom_right_rect,
                student_text,
                # TextDontClip -- "Name (ID)" is routinely longer than this
                # quarter-width band (sized for short strings like "50mm"/
                # frame numbers) fits; without it, Qt's default rect-clipping
                # silently drops the name and leaves only the right-anchored
                # ID visible.
                int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter | QtCore.Qt.TextDontClip)
            )

            painter.end()
            image.save(filepath, "JPG", quality=95)

    # --------------------------------------------------------
    # RV
    # --------------------------------------------------------
    def _rv_install_roots_from_registry(self):
        """
        Reads InstallLocation from the Windows Uninstall registry for any
        RV / Shotgun / ShotGrid / Flow Production Tracking entry. Install
        paths and version-folder names vary by machine/imaging, but the
        installer always registers the real path here.
        """
        try:
            import winreg
        except ImportError:
            return []

        hives_and_keys = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]

        roots = []
        for hive, key_path in hives_and_keys:
            try:
                key = winreg.OpenKey(hive, key_path)
            except OSError:
                continue

            for i in range(winreg.QueryInfoKey(key)[0]):
                try:
                    subkey = winreg.OpenKey(key, winreg.EnumKey(key, i))
                    display_name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                    if re.search(r"\bRV\b|Shotgun|ShotGrid|Flow Production Tracking", display_name, re.IGNORECASE):
                        install_location = winreg.QueryValueEx(subkey, "InstallLocation")[0]
                        if install_location:
                            roots.append(install_location)
                except OSError:
                    continue

        return roots

    def find_rv_executable(self, exe_name):
        """
        Locates an RV binary by name (e.g. "rvpush" or "rv"). Checks, in order:
        the SHOTSUB_RV_HOME env var override, PATH, the Windows registry
        install location, then common Autodesk/Shotgun RV install locations
        on Windows and Mac. Returns the highest version found.
        """
        env_home = os.environ.get("SHOTSUB_RV_HOME")
        if env_home:
            for candidate in (
                os.path.join(env_home, exe_name + ".exe"),
                os.path.join(env_home, "bin", exe_name + ".exe"),
                os.path.join(env_home, exe_name),
                os.path.join(env_home, "bin", exe_name),
            ):
                if os.path.isfile(candidate):
                    return candidate
            cmds.warning("SHOTSUB_RV_HOME is set to '{0}' but no {1} was found there.".format(env_home, exe_name))

        found = shutil.which(exe_name)
        if found:
            return found

        candidates = []

        if cmds.about(nt=True):
            for install_root in self._rv_install_roots_from_registry():
                for candidate in (
                    os.path.join(install_root, exe_name + ".exe"),
                    os.path.join(install_root, "bin", exe_name + ".exe"),
                ):
                    if os.path.isfile(candidate):
                        candidates.append(candidate)

            search_globs = [
                r"C:\Program Files\Autodesk\RV-*\bin\{0}.exe".format(exe_name),
                r"C:\Program Files\Shotgun\RV-*\bin\{0}.exe".format(exe_name),
                r"C:\Program Files\ShotGrid\RV-*\bin\{0}.exe".format(exe_name),
            ]
        elif cmds.about(mac=True):
            search_globs = [
                "/Applications/RV*.app/Contents/MacOS/{0}".format(exe_name),
                "/Applications/Autodesk/RV-*.app/Contents/MacOS/{0}".format(exe_name),
                "/Applications/Shotgun/RV*.app/Contents/MacOS/{0}".format(exe_name),
                os.path.expanduser("~/Applications/RV*.app/Contents/MacOS/{0}".format(exe_name)),
            ]
        else:
            search_globs = [
                "/usr/bin/{0}".format(exe_name),
                "/usr/local/bin/{0}".format(exe_name),
            ]

        for pattern in search_globs:
            candidates.extend(glob.glob(pattern))

        if not candidates:
            return ""

        def version_key(path):
            match = re.search(r"RV-([\d.]+)", path)
            if not match:
                return (0,)
            return tuple(int(part) for part in match.group(1).split("."))

        candidates.sort(key=version_key)
        return candidates[-1]

    def open_in_rv(self, prefix):
        rvpush = self.find_rv_executable("rvpush")
        if not rvpush:
            cmds.warning("Could not find RV (rvpush) on this machine. Skipped opening in RV.")
            return

        sequence_pattern = prefix + ".#.jpg"
        cmd = [rvpush, "-tag", self.RV_TAG, "set", sequence_pattern]

        # rvpush blocks synchronously while it connects -- if the previous RV under
        # this tag was just closed, that first connect attempt has to time out against
        # the dead session before rvpush falls through to spawning a fresh one, which
        # can take a few seconds. Running that on Maya's main thread freezes the whole
        # UI for the duration (Windows shows it as a ghosted/not-responding window), so
        # the retry loop runs on a background thread instead -- nothing in it touches
        # the Maya API directly, only cmds.warning() marshals back to the main thread.
        thread = threading.Thread(target=self._push_to_rv, args=(cmd,))
        thread.daemon = True
        thread.start()

    def open_in_rv_with_audio(self, prefix, audio_path, audio_offset, start_frame):
        """
        rvpush's "set" command (used by open_in_rv) does not support RV's
        multi-file source grouping -- confirmed empirically: it silently drops
        the audio and loads the image sequence alone, whether pushed into an
        already-running tagged RV or during a cold start. The only combination
        that actually works is RV's own command-line argv parsing of a bracket
        group (`rv [ seq.#.jpg audio.wav ]`), which only happens at true process
        startup -- so audio playblasts bypass rvpush entirely and launch rv
        directly. That means no in-place window update for this path: the
        previous audio-review RV window (if we started one) is closed first so
        they don't pile up across repeated playblasts.
        """
        rv_exe = self.find_rv_executable("rv")
        if not rv_exe:
            cmds.warning("Could not find RV on this machine. Skipped opening in RV.")
            return

        if self.audio_rv_process is not None and self.audio_rv_process.poll() is None:
            self.audio_rv_process.terminate()

        sequence_pattern = prefix + ".#.jpg"
        cmd = [rv_exe, "[", sequence_pattern, audio_path]

        if audio_offset != start_frame:
            fps = self.get_fps_value()
            offset_seconds = (audio_offset - start_frame) / fps
            cmd += ["-ao", str(offset_seconds)]

        cmd += ["]"]

        no_window_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            self.audio_rv_process = subprocess.Popen(cmd, creationflags=no_window_flags)
        except Exception as exc:
            cmds.warning("Failed to launch RV with audio: {0}".format(exc))

    def _push_to_rv(self, cmd):
        # Maya has no console of its own, so each subprocess.run() below would
        # otherwise flash open a new console window for rvpush -- CREATE_NO_WINDOW
        # stops that (Windows-only flag; harmless no-op value on other platforms).
        no_window_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        # When no tagged RV is running, rvpush's cold start spawns RV but does not
        # forward the media (exit code 15) -- the sequence only loads once that new
        # session's network listener comes up, so retry the push briefly until it does.
        # Only the first attempt is allowed to spawn: exit 15 means "started a new RV",
        # so retrying the same command with spawning still enabled would cold-start a
        # second (and third...) RV every second a slow-starting session takes to bring
        # its listener up. RVPUSH_RV_EXECUTABLE_PATH=none on every retry after the first
        # tells rvpush not to spawn anything -- it just fails to connect (exit 11) until
        # the one RV we already started is ready.
        no_spawn_env = os.environ.copy()
        no_spawn_env["RVPUSH_RV_EXECUTABLE_PATH"] = "none"

        for attempt in range(15):
            spawning_allowed = (attempt == 0)
            env = os.environ if spawning_allowed else no_spawn_env
            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True, env=env,
                    creationflags=no_window_flags,
                )
            except Exception as exc:
                self._warn_from_thread("Failed to launch RV: {0}".format(exc))
                return

            if result.returncode == 0:
                return

            if result.returncode == 15 or (result.returncode == 11 and not spawning_allowed):
                time.sleep(1)
                continue

            self._warn_from_thread("Failed to open sequence in RV (rvpush exit {0}): {1}".format(
                result.returncode, (result.stderr or result.stdout or "").strip()
            ))
            return

        self._warn_from_thread("Timed out waiting for a newly-launched RV to accept the playblast sequence.")

    def _warn_from_thread(self, message):
        maya.utils.executeInMainThreadWithResult(lambda: cmds.warning(message))

    # --------------------------------------------------------
    # Playblast
    # --------------------------------------------------------
    def create_playblast(self):
        try:
            self.ensure_scene_saved()

            version_folder = self.get_next_version_folder(create=True)
            prefix = self.get_playblast_prefix(version_folder)
            start_frame, end_frame = self.get_frame_range()

            panel = self.get_active_model_panel()
            render_width, render_height = self.get_render_resolution()

            cmds.playblast(
                format="image",
                filename=prefix,
                sequenceTime=False,
                clearCache=True,
                viewer=False,
                showOrnaments=False,
                offScreen=True,
                percent=100,
                compression="jpg",
                quality=90,
                framePadding=4,
                startTime=start_frame,
                endTime=end_frame,
                forceOverwrite=True,
                widthHeight=[render_width, render_height]
            )

            self.last_created_version_folder = version_folder
            self.last_created_files = sorted(glob.glob(prefix + ".*.jpg"))

            if self.last_created_files:
                self.apply_burnins_to_sequence(self.last_created_files)

                open_in_rv = cmds.checkBox(self.widgets["open_in_rv"], q=True, value=True)
                if open_in_rv:
                    audio_path, audio_offset = self.get_scene_audio_info()
                    if audio_path:
                        self.open_in_rv_with_audio(prefix, audio_path, audio_offset, start_frame)
                    else:
                        self.open_in_rv(prefix)

            if self.get_auto_prune_enabled():
                self.prune_old_versions(os.path.dirname(version_folder), self.get_max_versions_to_keep())

            self.refresh_ui_state()

            keep_files = cmds.checkBox(self.widgets["keep_files"], q=True, value=True)
            if not keep_files:
                cmds.inViewMessage(
                    amg='Playblast created. Use <hl>Delete Last Playblast</hl> when done reviewing.',
                    pos='midCenter',
                    fade=True
                )

            print("Playblast created:")
            print("  Scene: {0}".format(self.get_scene_name()))
            print("  Output: {0}".format(version_folder))
            print("  Resolution: {0} x {1}".format(render_width, render_height))
            print("  Files: {0}".format(len(self.last_created_files)))

        except Exception as exc:
            cmds.warning("Playblast failed: {0}".format(exc))
            raise

    def delete_last_playblast(self):
        if not self.last_created_version_folder:
            cmds.warning("No playblast has been created yet in this session.")
            return

        if not os.path.isdir(self.last_created_version_folder):
            cmds.warning("Last playblast folder no longer exists.")
            return

        try:
            shutil.rmtree(self.last_created_version_folder)

            shot_root = os.path.dirname(self.last_created_version_folder)
            if os.path.isdir(shot_root) and not os.listdir(shot_root):
                os.rmdir(shot_root)

            self.last_created_version_folder = ""
            self.last_created_files = []
            self.refresh_ui_state()

            cmds.inViewMessage(
                amg='Deleted last playblast.',
                pos='midCenter',
                fade=True
            )

        except Exception as exc:
            cmds.warning("Failed to delete last playblast: {0}".format(exc))

    def open_output_folder(self):
        try:
            next_version_folder = self.get_next_version_folder(create=False)
            parent_folder = os.path.dirname(next_version_folder)

            if not os.path.isdir(parent_folder):
                os.makedirs(parent_folder)

            if cmds.about(nt=True):
                os.startfile(parent_folder)
            elif cmds.about(mac=True):
                os.system('open "{0}"'.format(parent_folder.replace('"', '\\"')))
            else:
                os.system('xdg-open "{0}"'.format(parent_folder.replace('"', '\\"')))

        except Exception as exc:
            cmds.warning("Failed to open output folder: {0}".format(exc))

    # --------------------------------------------------------
    # Student identity (local only -- name/id typed once per machine,
    # never sent to ShotGrid credentials or shotgridConnect; used only to
    # (a) filter the Link-to-ShotGrid Shot picker down to this student's
    # own Shots -- see provision_shotgrid_class.py's shot-naming
    # convention, "<prefix>_<type>_<studentID>" -- and (b) burn into the
    # bottom-right corner of playblasts, see apply_burnins_to_sequence())
    # --------------------------------------------------------
    STUDENT_IDENTITY_FILENAME = "shotSub_student.json"

    def get_student_identity_file(self):
        prefs = cmds.internalVar(userPrefDir=True)
        return os.path.join(prefs, self.STUDENT_IDENTITY_FILENAME).replace("\\", "/")

    def read_student_identity(self):
        path = self.get_student_identity_file()
        if not os.path.isfile(path):
            return None
        try:
            with open(path, "r") as f:
                data = json.load(f)
        except (ValueError, OSError):
            return None
        if not data.get("student_name") or not data.get("student_id"):
            return None
        return data

    def write_student_identity(self, name, student_id):
        data = {"student_name": name, "student_id": student_id}
        with open(self.get_student_identity_file(), "w") as f:
            json.dump(data, f, indent=2)
        return data

    def prompt_for_student_identity(self):
        name, ok = QtWidgets.QInputDialog.getText(None, "shotSub setup", "Your name:")
        if not ok or not name.strip():
            return None
        student_id, ok = QtWidgets.QInputDialog.getText(None, "shotSub setup", "Your student ID:")
        if not ok or not student_id.strip():
            return None
        return self.write_student_identity(name.strip(), student_id.strip())

    def ensure_student_identity(self):
        """Returns the saved {student_name, student_id}, prompting once
        (and saving the answer for every future launch) if nothing's saved
        yet. Returns None only if the student cancels the one-time
        prompt -- callers must treat that as "identity unknown", not an
        error, and fall back to showing everything unfiltered rather than
        blocking them outright."""
        identity = self.read_student_identity()
        if identity:
            return identity
        return self.prompt_for_student_identity()

    # --------------------------------------------------------
    # ShotGrid hand-off
    # --------------------------------------------------------
    def link_to_shotgrid(self):
        """
        Attach the current scene's own scenes/<sequence>/<shot> subfolder
        (see get_scene_folder_path()) to an EXISTING ShotGrid Shot -- never
        creates one, that's done directly in ShotGrid's web UI by the
        lecturer/TD (see shotgridConnect.list_project_shots()'s docstring).
        Two QInputDialog.getItem pickers (Project, then Shot within it),
        run synchronously on Maya's main thread -- a brief pause during an
        occasional, deliberate "link" action is fine.
        """
        try:
            import shotgridConnect
        except ImportError:
            cmds.warning(
                "shotSub: shotgridConnect.py (and its bundled shotgun_api3) "
                "must sit alongside shotSub.py — check pipeDev/shotSubDev."
            )
            return

        try:
            projects = shotgridConnect.list_visible_projects()
        except Exception as exc:
            cmds.warning("Could not reach ShotGrid to list Projects: {0}".format(exc))
            return
        if not projects:
            cmds.warning("No ShotGrid Projects are visible to your account.")
            return

        project_name, ok = QtWidgets.QInputDialog.getItem(
            None, "Link to ShotGrid", "ShotGrid Project:",
            [p["name"] for p in projects], 0, False
        )
        if not ok or not project_name:
            return
        project = next(p for p in projects if p["name"] == project_name)

        try:
            shots = shotgridConnect.list_project_shots(project_name)
        except Exception as exc:
            cmds.warning("Could not reach ShotGrid to list Shots: {0}".format(exc))
            return
        if not shots:
            cmds.warning(
                "No Shots found in ShotGrid Project '{0}' — ask your lecturer to "
                "create one in ShotGrid first.".format(project_name)
            )
            return

        # Filter the picker down to this student's own Shots, matching
        # provision_shotgrid_class.py's "<prefix>_<type>_<studentID>"
        # naming convention -- avoids a student mis-picking a classmate's
        # identically-structured Shot out of a long list. Falls back to
        # the full unfiltered list (with a warning) if identity is
        # unknown (student cancelled the one-time prompt) or nothing
        # matches their ID (typo, or genuinely not on this assignment).
        identity = self.ensure_student_identity()
        if identity:
            student_id = identity["student_id"].lower()
            matching_shots = [s for s in shots if student_id in s["code"].lower()]
            if matching_shots:
                shots = matching_shots
            else:
                cmds.warning(
                    "No Shots matching student ID '{0}' found — showing all Shots "
                    "in '{1}' instead.".format(identity["student_id"], project_name)
                )
        else:
            cmds.warning("No student ID on file — showing all Shots in '{0}'.".format(project_name))

        shot_code, ok = QtWidgets.QInputDialog.getItem(
            None, "Link to ShotGrid", "ShotGrid Shot:",
            [s["code"] for s in shots], 0, False
        )
        if not ok or not shot_code:
            return
        shot = next(s for s in shots if s["code"] == shot_code)

        try:
            self.write_shotgrid_link(project["id"], project["name"], "Shot", shot["id"], shot["code"])
        except Exception as exc:
            cmds.warning("Failed to write {0}: {1}".format(self.LINK_FILENAME, exc))
            return

        self.refresh_ui_state()
        cmds.inViewMessage(
            amg='Linked to ShotGrid Shot <hl>{0}</hl>.'.format(shot_code),
            pos='midCenter',
            fade=True
        )

    def publish_version(self, version_folder):
        """
        Hand-off to shotgridConnect.upload_playblast() for an explicit
        local version (picked from the Local Versions list, not
        necessarily this session's last playblast -- publishing is
        deliberately decoupled from playblast creation). Resolves the
        linked ShotGrid Shot from the local shotgrid_link.json marker file
        rather than guessing a name from folder structure -- that marker
        was written by this tool's own link_to_shotgrid().

        Only ever sends the raw JPEG sequence as-is plus fps -- no video
        encoding step in shotSub itself beyond resolving rvio's path;
        shotgridConnect.upload_playblast() does the actual mp4 encode (via
        rvio) and decides what to do with the sequence.
        """
        if not version_folder or not os.path.isdir(version_folder):
            cmds.warning("Selected version folder no longer exists.")
            return

        link = self.read_shotgrid_link()
        if not link:
            cmds.warning("This shot isn't linked to ShotGrid yet — use 'Link to ShotGrid' first.")
            return

        try:
            import shotgridConnect
        except ImportError:
            cmds.warning(
                "shotSub: shotgridConnect.py (and its bundled shotgun_api3) "
                "must sit alongside shotSub.py — check pipeDev/shotSubDev."
            )
            return

        files = sorted(glob.glob(os.path.join(version_folder, "*.jpg")))
        notes = cmds.scrollField(self.widgets["publish_notes"], q=True, text=True).strip()
        rvio_path = self.find_rv_executable("rvio")

        try:
            result = shotgridConnect.upload_playblast(
                link.get("sg_entity_type", "Shot"),
                link["sg_entity_id"],
                version_folder,
                files=files,
                notes=notes or None,
                fps=self.get_fps_value(),
                rvio_path=rvio_path,
            )
        except NotImplementedError as exc:
            cmds.warning("ShotGrid publish isn't built yet: {0}".format(exc))
            return
        except Exception as exc:
            cmds.warning("Failed to send playblast to ShotGrid: {0}".format(exc))
            return

        sg_version_id = result.get("id") if isinstance(result, dict) else None
        version_name = os.path.basename(version_folder)
        self.mark_version_published(version_name, sg_version_id=sg_version_id)
        cmds.scrollField(self.widgets["publish_notes"], e=True, text="")
        self.refresh_ui_state()
        cmds.inViewMessage(
            amg='Published <hl>{0}</hl> to ShotGrid.'.format(version_name),
            pos='midCenter',
            fade=True
        )

    def publish_selected_version(self):
        version_folder = self.get_selected_version_folder()
        if not version_folder:
            cmds.warning("Select a local version to publish first.")
            return
        self.publish_version(version_folder)


def show_shotSub():
    tool = ShotSub()
    tool.show()
    return tool
