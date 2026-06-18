# ------------------------------------------------------------
# pbTool.py
#
# Standalone Maya Playblast Tool
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
# - Optional keep/delete workflow
# - Uses render resolution from Maya render settings
#
# Shelf button:
# import importlib
# import pbTool
# importlib.reload(pbTool)
# pbTool.show_pbTool()
# ------------------------------------------------------------

from __future__ import print_function

import os
import re
import glob
import shutil

import maya.cmds as cmds

# Qt binding in Maya
QT_AVAILABLE = True
try:
    from PySide6 import QtGui, QtCore
except Exception:
    try:
        from PySide2 import QtGui, QtCore
    except Exception:
        QT_AVAILABLE = False
        QtGui = None
        QtCore = None


class PBTool(object):
    WINDOW_NAME = "pbToolWindow"

    def __init__(self):
        self.widgets = {}
        self.last_created_version_folder = ""
        self.last_created_files = []

    # --------------------------------------------------------
    # UI
    # --------------------------------------------------------
    def show(self):
        if cmds.window(self.WINDOW_NAME, exists=True):
            cmds.deleteUI(self.WINDOW_NAME)

        cmds.window(
            self.WINDOW_NAME,
            title="pbTool - Playblast Manager",
            sizeable=True,
            widthHeight=(560, 560)
        )

        root = cmds.columnLayout(adj=True)
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

    def _split_path_parts(self, path_string):
        norm = os.path.normpath(os.path.abspath(path_string))
        drive, tail = os.path.splitdrive(norm)
        parts = [p for p in tail.replace("\\", "/").split("/") if p]
        if drive:
            parts.insert(0, drive)
        return parts

    def get_scene_relative_folder_from_scenes(self):
        """
        Returns the scene directory path *after* the 'scenes' folder.

        Example:
            <project>/scenes/scene1/shot001/file.ma
        returns:
            scene1/shot001
        """
        scene_path = os.path.normpath(os.path.abspath(self.ensure_scene_saved()))
        scene_dir = os.path.dirname(scene_path)

        scene_parts = self._split_path_parts(scene_dir)
        lower_parts = [p.lower() for p in scene_parts]

        if "scenes" not in lower_parts:
            raise RuntimeError(
                "Scene is not saved inside a 'scenes' folder. "
                "Please save it under your Maya project's scenes directory."
            )

        scenes_index = lower_parts.index("scenes")
        relative_parts = scene_parts[scenes_index + 1:]

        if not relative_parts:
            return ""

        return os.path.join(*relative_parts)

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

        fps_text = self.get_frame_rate_label() if show_fps else ""
        scene_text = self.get_scene_name() if show_scene else ""

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

            painter.end()
            image.save(filepath, "JPG", quality=95)

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
                viewer=True,
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


def show_pbTool():
    tool = PBTool()
    tool.show()
    return tool
