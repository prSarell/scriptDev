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
import subprocess
import threading
import time

import maya.cmds as cmds
import maya.utils

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
    RV_TAG = "pbTool"

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
        self.widgets["open_in_rv"] = cmds.checkBox(label="Open in RV", value=True)
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
        the PBTOOL_RV_HOME env var override, PATH, the Windows registry
        install location, then common Autodesk/Shotgun RV install locations
        on Windows and Mac. Returns the highest version found.
        """
        env_home = os.environ.get("PBTOOL_RV_HOME")
        if env_home:
            for candidate in (
                os.path.join(env_home, exe_name + ".exe"),
                os.path.join(env_home, "bin", exe_name + ".exe"),
                os.path.join(env_home, exe_name),
                os.path.join(env_home, "bin", exe_name),
            ):
                if os.path.isfile(candidate):
                    return candidate
            cmds.warning("PBTOOL_RV_HOME is set to '{0}' but no {1} was found there.".format(env_home, exe_name))

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
                    self.open_in_rv(prefix)

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