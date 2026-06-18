import maya.cmds as cmds
import maya.mel as mel
import maya.OpenMayaUI as omui
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
from maya import OpenMayaAnim as oma
import os
import sys
import threading
import math
import csv

# Detect Maya version
maya_version = int(mel.eval("about -v"))

# Conditional imports based on Maya version
if maya_version > 2024:  # Maya 2025 and above use PySide6 and Shiboken6
    from PySide6 import QtCore, QtGui, QtWidgets
    from shiboken6 import wrapInstance, isValid
else:  # Maya 2023 and earlier use PySide2 and Shiboken2
    from PySide2 import QtCore, QtGui, QtWidgets
    from shiboken2 import wrapInstance, isValid

class PlaybackMonitorThread(QtCore.QThread):
    playback_state_changed = QtCore.Signal(bool)

    def __init__(self):
        super(PlaybackMonitorThread, self).__init__()
        self.stop_thread = False  # Flag to indicate whether the thread should stop

    def run(self):
        while not self.stop_thread:
            is_playing = cmds.play(query=True, state=True)
            self.playback_state_changed.emit(is_playing)
            # Sleep for a short interval to avoid high CPU usage
            self.msleep(100)

    def request_stop(self):
        self.stop_thread = True
        # Don't call self.wait() — it processes Qt events while blocking which
        # can fire signals and restart Maya callbacks during teardown.

class TempoSlider(MayaQWidgetDockableMixin, QtWidgets.QDialog):
    obj = "customPlaybackObject"
    attr_name = "customPlaybackAttribute"
    rig_data_attr = "tempoRigData"   # string attr on the locator that persists rig assignments

    def __init__(self):
        super(TempoSlider, self).__init__(maya_main_window())
        self.setWindowTitle("Playback Tempo Tool")
        self.resize(400, 20)

        self.deleted = False  # Flag to track if the object is deleted
        self.create_ui()
        self.set_defaults()
        self.create_connections()
        self.csv_saved = False  # Flag to track if CSV file has been saved
        self.save_to_csv = False  # Add save_to_csv attribute and initialize it to False
        self.is_enabled = True
        # Data model: { root_full_path: [ctrl_full_path, ...], ... }
        # Controllers are pre-scanned animated descendants stored at assign time.
        self._rig_data = {}
        
        # Check if the object exists, if not, create it with the custom attribute
        if not cmds.objExists(self.obj):
            self.obj = cmds.spaceLocator(name=self.obj)[0]
            cmds.addAttr(self.obj, ln=self.attr_name, at='double', dv=1, k=True)
        else:
            if not cmds.attributeQuery(self.attr_name, node=self.obj, exists=True):
                cmds.addAttr(self.obj, ln=self.attr_name, at='double', dv=1, k=True)

        # Ensure the rig-data persistence string attribute exists
        if not cmds.attributeQuery(self.rig_data_attr, node=self.obj, exists=True):
            cmds.addAttr(self.obj, ln=self.rig_data_attr, dt='string')
            cmds.setAttr(self.obj + '.' + self.rig_data_attr, '{}', type='string')

        # Load any previously saved rig assignments from the scene
        self._load_rig_data()

        # Lock the custom attribute
        #cmds.setAttr(self.obj + '.' + self.attr_name, keyable=True, channelBox=True)
        
        # Create a timer to periodically check for updates to the playback rate
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.check_playback_rate)

        # Create and start the playback monitor thread
        self.playback_monitor_thread = PlaybackMonitorThread()
        self.playback_monitor_thread.playback_state_changed.connect(self.handle_playback_state_change)
        self.playback_monitor_thread.start()

        # Initialize playback state
        self.is_playing = False

    def get_frame_range(self):
        return int(self.start_frame_spinbox.value()), int(self.end_frame_spinbox.value())

    def _is_alive(self):
        if self.deleted:
            return False
        try:
            return isValid(self)
        except Exception:
            return False

    def handle_playback_state_change(self, is_playing):
        if not self._is_alive():
            return
        self.is_playing = is_playing
        if self.is_playing:
            if not self.timer.isActive():
                self.timer.start(100)
        else:
            if self.timer.isActive():
                self.timer.stop()

    def monitor_playback_state(self):
        # Legacy dead code path — monitoring is handled by PlaybackMonitorThread.
        pass

    def create_ui(self):
        self.wgt_temposlider = QtWidgets.QSlider(orientation=QtCore.Qt.Horizontal)
        self.wgt_temposlider.setMinimum(0)
        self.wgt_temposlider.setMaximum(2000)
        self.wgt_temposlider.setValue(1000)
        self.wgt_temposlider.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.Fixed)
    
        self.wgt_rate_spinbox = QtWidgets.QDoubleSpinBox()
        self.wgt_rate_spinbox.setMinimum(0)
        self.wgt_rate_spinbox.setMaximum(2)
        self.wgt_rate_spinbox.setValue(1)
        self.wgt_rate_spinbox.setSingleStep(0.01)
        self.wgt_rate_spinbox.setFixedWidth(80)
    
        self.wgt_btn_add_keyframe = QtWidgets.QPushButton("Add Keyframe")
        self.wgt_btn_remove_keyframe = QtWidgets.QPushButton("Remove Keyframe")
        self.wgt_btn_bake = QtWidgets.QPushButton("Bake Keyframes")
        self.wgt_btn_increment_frames = QtWidgets.QPushButton("Increment Frames")
        self.wgt_btn_reset = QtWidgets.QPushButton("Reset")
        
        self.wgt_chkbx_showsubframes = QtWidgets.QCheckBox("Show Subframes")
        self.wgt_chkbx_save_to_csv = QtWidgets.QCheckBox("Export CSV")
        self.wgt_chkbx_enable_smoothing = QtWidgets.QCheckBox("Enable Smoothing")
        self.wgt_chkbx_show_notifications = QtWidgets.QCheckBox("Notifications")
        self.wgt_chkbx_show_notifications.setToolTip(
            "Show a completion dialog after Bake Keyframes / Increment Frames."
        )
        
        self.wgt_toggle_enabled = QtWidgets.QPushButton("Tool: ON")
        self.wgt_toggle_enabled.setCheckable(True)
        self.wgt_toggle_enabled.setChecked(True)
        
        self.start_frame_spinbox = QtWidgets.QSpinBox()
        self.start_frame_spinbox.setMinimum(-100000)
        self.start_frame_spinbox.setMaximum(100000)
        self.start_frame_spinbox.setValue(int(cmds.playbackOptions(q=True, min=True)))
        self.start_frame_spinbox.setPrefix("Start: ")
        
        self.end_frame_spinbox = QtWidgets.QSpinBox()
        self.end_frame_spinbox.setMinimum(-100000)
        self.end_frame_spinbox.setMaximum(100000)
        self.end_frame_spinbox.setValue(int(cmds.playbackOptions(q=True, max=True)))
        self.end_frame_spinbox.setPrefix("End: ")
   
        self.lbl_frame_count = QtWidgets.QLabel()

        # --- Rig target tree ---
        self.wgt_rig_search = QtWidgets.QLineEdit()
        self.wgt_rig_search.setPlaceholderText("Search controllers...")
        self.wgt_rig_search.setClearButtonEnabled(True)

        self.wgt_rig_tree = QtWidgets.QTreeWidget()
        self.wgt_rig_tree.setHeaderHidden(True)
        self.wgt_rig_tree.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.wgt_rig_tree.setMinimumHeight(120)
        self.wgt_rig_tree.setToolTip(
            "Rig roots and their tracked controllers.\n"
            "Select any node and click Assign — if its rig root is new it registers\n"
            "the whole rig; if the root already exists it adds the node as a controller."
        )

        self.wgt_btn_assign = QtWidgets.QPushButton("Assign")
        self.wgt_btn_assign.setToolTip(
            "Selected node's root not yet registered → registers the rig and scans all animated descendants.\n"
            "Selected node's root already registered → adds only the selected nodes as controllers."
        )
        self.wgt_btn_remove_rig = QtWidgets.QPushButton("Remove Selected")
        self.wgt_btn_remove_rig.setToolTip(
            "Remove highlighted items.\n"
            "Removing a rig root removes the entire rig.\n"
            "Removing controller items removes only those controllers."
        )
        self.wgt_btn_playblast = QtWidgets.QPushButton("Playblast")
        self.wgt_btn_playblast.setToolTip(
            "Run a playblast where each output frame is sampled according to the\n"
            "tempo curve — slow sections repeat frames, fast sections skip them.\n"
            "Uses the same frame range as the Start/End spinboxes."
        )
        self.wgt_btn_reload_rigs = QtWidgets.QPushButton("↺ Reload")
        self.wgt_btn_reload_rigs.setToolTip(
            "Re-read saved rig assignments from the scene.\n"
            "Useful after loading a new scene or reloading the plugin."
        )

        lyt_rig_buttons = QtWidgets.QHBoxLayout()
        lyt_rig_buttons.addWidget(self.wgt_btn_assign)
        lyt_rig_buttons.addWidget(self.wgt_btn_remove_rig)
        lyt_rig_buttons.addWidget(self.wgt_btn_reload_rigs)
        lyt_rig_buttons.addWidget(self.wgt_btn_playblast)

        lyt_slider = QtWidgets.QHBoxLayout()
        lyt_slider.addWidget(self.wgt_temposlider)
        
        lyt_range = QtWidgets.QHBoxLayout()
        lyt_range.addWidget(self.start_frame_spinbox)
        lyt_range.addWidget(self.end_frame_spinbox)
    
        lyt_rate = QtWidgets.QHBoxLayout()
        lyt_rate.addWidget(QtWidgets.QLabel("Playback Rate:"))
        lyt_rate.addWidget(self.wgt_rate_spinbox)
        lyt_rate.addWidget(self.wgt_btn_reset)
        lyt_rate.addWidget(self.wgt_chkbx_showsubframes)
        lyt_rate.addWidget(self.wgt_chkbx_save_to_csv)
        lyt_rate.addWidget(self.wgt_chkbx_enable_smoothing)
        lyt_rate.addWidget(self.wgt_chkbx_show_notifications)
        lyt_rate.addWidget(self.wgt_toggle_enabled)
        
        lyt_buttons = QtWidgets.QHBoxLayout()
        lyt_buttons.addWidget(self.wgt_btn_add_keyframe)
        lyt_buttons.addWidget(self.wgt_btn_remove_keyframe)
        lyt_buttons.addWidget(self.wgt_btn_bake)
        lyt_buttons.addWidget(self.wgt_btn_increment_frames)
    
        lyt_main = QtWidgets.QVBoxLayout(self)
        lyt_main.addLayout(lyt_slider)
        lyt_main.addLayout(lyt_rate)
        lyt_main.addLayout(lyt_buttons)
        lyt_main.addWidget(self.lbl_frame_count)
        lyt_main.addLayout(lyt_range)
        lyt_main.addWidget(QtWidgets.QLabel("Rig Targets:"))
        lyt_main.addWidget(self.wgt_rig_search)
        lyt_main.addWidget(self.wgt_rig_tree)
        lyt_main.addLayout(lyt_rig_buttons)

    def create_connections(self):
        # Track scriptJob IDs so they can be killed cleanly on close
        self._script_jobs = []
        self._script_jobs.append(
            cmds.scriptJob(event=["timeChanged", self.check_playback_rate])
        )
        self._script_jobs.append(
            cmds.scriptJob(event=["playbackRangeChanged", self.sync_frame_range_spinboxes])
        )
        self._script_jobs.append(
            cmds.scriptJob(attributeChange=[self.obj + '.' + self.attr_name, self.update_ui_from_attribute])
        )

        self.wgt_temposlider.valueChanged.connect(self.slider_value_changed)
        self.wgt_rate_spinbox.valueChanged.connect(self.box_value_changed)
        self.wgt_btn_reset.clicked.connect(self.reset_rate)
        self.wgt_chkbx_showsubframes.clicked.connect(self.show_subframes_changed)
        self.wgt_chkbx_save_to_csv.stateChanged.connect(self.toggle_csv_saving)
        self.wgt_btn_add_keyframe.clicked.connect(self.add_keyframe)
        self.wgt_btn_remove_keyframe.clicked.connect(self.remove_keyframe)
        self.wgt_btn_bake.clicked.connect(self.bake_keyframes)
        self.wgt_btn_increment_frames.clicked.connect(self.increment_frames)
        self.wgt_chkbx_enable_smoothing.stateChanged.connect(self.toggle_smoothing)
        self.wgt_btn_assign.clicked.connect(self.assign)
        self.wgt_btn_remove_rig.clicked.connect(self.remove_selected)
        self.wgt_rig_search.textChanged.connect(self._filter_rig_tree)
        self.wgt_btn_reload_rigs.clicked.connect(self._reload_rig_data)
        self.wgt_btn_playblast.clicked.connect(self.do_playblast)
        self.wgt_toggle_enabled.toggled.connect(self.toggle_enabled_state)

    def sync_frame_range_spinboxes(self):
        if not self._is_alive():
            return
        try:
            self.start_frame_spinbox.setValue(int(cmds.playbackOptions(q=True, min=True)))
            self.end_frame_spinbox.setValue(int(cmds.playbackOptions(q=True, max=True)))
        except RuntimeError:
            pass

    # ------------------------------------------------------------------
    # Playblast visualisation
    # ------------------------------------------------------------------

    def _build_playblast_frame_sequence(self):
        """
        Walk the tempo curve the same way bake does and return the ordered list
        of source-frame times that should be captured by the playblast.

        At rate < 1 (slow-mo): the same source frame is repeated
        round(1/rate) times so the output video holds on it long enough.
        At rate >= 1 (fast): one frame per step, skipping intermediate frames.
        """
        start_frame, end_frame = self.get_frame_range()
        sequence = []
        pos = float(start_frame)

        while pos <= end_frame:
            rate = cmds.getAttr(self.obj + '.' + self.attr_name, time=pos)
            if rate <= 0:
                rate = 1.0

            if rate < 1 and self.wgt_chkbx_showsubframes.isChecked():
                # Repeat this frame to represent slow-motion hold
                repeat = int(round(1.0 / rate))
                sequence.extend([pos] * repeat)
            else:
                sequence.append(pos)

            pos += rate

        return sequence

    def do_playblast(self):
        """
        Run a playblast where the captured frames follow the tempo curve.
        Slow sections (rate < 1) repeat the same source frame so the output
        holds longer; fast sections (rate > 1) skip source frames so the output
        speeds through them. Uses cmds.playblast(frame=[...]) to supply the
        exact frame list — no scriptJob hooks needed.
        """
        frame_sequence = self._build_playblast_frame_sequence()
        if not frame_sequence:
            cmds.warning("Tempo curve produced an empty frame sequence — check your Start/End range.")
            return

        # Ask Maya for its current playblast settings so we respect them,
        # but override only the frame list.
        start_frame, end_frame = self.get_frame_range()
        total_output_frames = len(frame_sequence)

        # Determine output path — use Maya's default temp location if none set
        pb_filename = cmds.optionVar(q="playblastFile") or ""
        if not pb_filename:
            import tempfile, os
            pb_filename = os.path.join(tempfile.gettempdir(), "playblast_tempo")

        # Read current viewer/format settings from optionVars where available
        fmt        = cmds.optionVar(q="playblastFormat")        if cmds.optionVar(exists="playblastFormat")        else "qt"
        encoding   = cmds.optionVar(q="playblastCompression")   if cmds.optionVar(exists="playblastCompression")   else "H.264"
        quality    = cmds.optionVar(q="playblastQuality")       if cmds.optionVar(exists="playblastQuality")       else 70
        width      = cmds.optionVar(q="playblastWidthHeight")   if cmds.optionVar(exists="playblastWidthHeight")   else None
        viewer     = bool(cmds.optionVar(q="playblastViewer"))  if cmds.optionVar(exists="playblastViewer")        else True

        pb_kwargs = dict(
            filename    = pb_filename,
            format      = fmt,
            compression = encoding,
            quality     = quality,
            frame       = frame_sequence,
            showOrnaments = True,
            viewer      = viewer,
            forceOverwrite = True,
        )
        if width:
            # optionVar stores [w, h] as a two-element int array
            try:
                w, h = width[0], width[1]
                pb_kwargs["widthHeight"] = (w, h)
            except (TypeError, IndexError):
                pass

        cmds.playblast(**pb_kwargs)

    def toggle_enabled_state(self, enabled):
        if enabled:
            self.wgt_toggle_enabled.setText("Tool: ON")
            self.is_enabled = True
            if self.is_playing:
                self.timer.start(100)
        else:
            self.wgt_toggle_enabled.setText("Tool: OFF")
            self.is_enabled = False
            self.timer.stop()
            cmds.playbackOptions(playbackSpeed=1)
            cmds.playbackOptions(maxPlaybackSpeed=1)
            cmds.playbackOptions(by=1)

    def set_defaults(self):
        self.wgt_chkbx_showsubframes.setChecked(True)
        self.wgt_chkbx_enable_smoothing.setChecked(False)
        self.wgt_chkbx_show_notifications.setChecked(True)

    def toggle_smoothing(self, state):
        self.smoothing_enabled = state == QtCore.Qt.Checked
        
    def slider_value_changed(self):
        if not self._is_alive():
            return
        val = round(self.wgt_temposlider.value()/1000, 2)
        self.wgt_rate_spinbox.blockSignals(True)
        self.wgt_rate_spinbox.setValue(val)
        self.wgt_rate_spinbox.blockSignals(False)
        self.set_playrate(val)
        
    def box_value_changed(self):
        if not self._is_alive():
            return
        val = round(self.wgt_rate_spinbox.value(), 2)
        self.set_playrate(val)

    def reset_rate(self):
        target_rate = 1
        self.wgt_temposlider.blockSignals(True)
        self.wgt_rate_spinbox.blockSignals(True)
        self.wgt_temposlider.setValue(target_rate * 1000)
        self.wgt_rate_spinbox.setValue(target_rate)
        self.wgt_temposlider.blockSignals(False)
        self.wgt_rate_spinbox.blockSignals(False)
        self.set_playrate(target_rate)

    def show_subframes_changed(self):
        if not self._is_alive():
            return
        self.set_playrate(round(self.wgt_rate_spinbox.value(), 2))

    def add_keyframe(self):
        current_value = self.wgt_rate_spinbox.value()
        current_frame = cmds.currentTime(query=True)
        cmds.setKeyframe(self.obj, attribute=self.attr_name, time=current_frame, value=current_value)
        # Update the spinbox and slider values to reflect the new keyframe
        self.update_ui_from_attribute()

    def remove_keyframe(self):
        # Get the current frame
        current_frame = cmds.currentTime(query=True)

        # Remove the keyframe at the current frame
        cmds.cutKey(self.obj, time=(current_frame, current_frame), attribute=self.attr_name)

        # Update UI elements
        self.update_ui_from_attribute()
    
    def set_playrate(self, target_rate):
        if not self._is_alive():
            return

        # Update UI — block signals to prevent valueChanged feedback loops
        self.wgt_rate_spinbox.blockSignals(True)
        self.wgt_temposlider.blockSignals(True)
        self.wgt_rate_spinbox.setValue(target_rate)
        self.wgt_temposlider.setValue(int(target_rate * 1000))
        self.wgt_rate_spinbox.blockSignals(False)
        self.wgt_temposlider.blockSignals(False)

        # Only write to scene and playbackOptions when the tool is ON
        if not self.is_enabled:
            return

        cmds.setAttr(self.obj + '.' + self.attr_name, target_rate)

        if target_rate < 1 and self.wgt_chkbx_showsubframes.isChecked():
            cmds.playbackOptions(maxPlaybackSpeed=target_rate)
            cmds.playbackOptions(playbackSpeed=0)
            cmds.playbackOptions(by=target_rate)
        else:
            cmds.playbackOptions(playbackSpeed=target_rate)
            cmds.playbackOptions(by=target_rate)

    def update_ui_from_attribute(self):
        if not self._is_alive():
            return
        try:
            cmds.undoInfo(stateWithoutFlush=False)
            target_rate = cmds.getAttr(self.obj + '.' + self.attr_name)
            self.wgt_rate_spinbox.blockSignals(True)
            self.wgt_temposlider.blockSignals(True)
            self.wgt_rate_spinbox.setValue(target_rate)
            self.wgt_temposlider.setValue(int(target_rate * 1000))
            self.wgt_rate_spinbox.blockSignals(False)
            self.wgt_temposlider.blockSignals(False)
            cmds.undoInfo(stateWithoutFlush=True)
        except RuntimeError:
            pass

    def check_playback_rate(self):
        if not self._is_alive():
            return
        if not self.is_enabled:
            return
        try:
            current_frame = cmds.currentTime(query=True)
            target_rate = round(cmds.getAttr(self.obj + '.' + self.attr_name, time=current_frame), 4)
            if target_rate is not None:
                self.set_playrate(target_rate)
            frame_count = self.calculate_frame_count()
            self.lbl_frame_count.setText(f"Approx. Frame Count: {frame_count}")
        except RuntimeError:
            pass

    def calculate_frame_count(self):
        start_frame, end_frame = self.get_frame_range()
        output_frames = 0
        pos = float(start_frame)
        while pos <= end_frame:
            playback_rate = cmds.getAttr(self.obj + '.' + self.attr_name, time=pos)
            if playback_rate <= 0:
                playback_rate = 1.0

            if playback_rate < 1 and self.wgt_chkbx_showsubframes.isChecked():
                # Slow motion: one source frame becomes multiple output subframes
                output_frames += int(round(1.0 / playback_rate))
            else:
                # Normal/fast: each step is one output frame
                output_frames += 1

            pos += playback_rate

        return round(output_frames)

    def bake_animation(self):
        frame_count = self.calculate_frame_count()
        self.bake_subframes(frame_count)

    def get_playback_rate_for_frame(self, frame):
        """
        Retrieves the playback rate for a specific frame from the customPlaybackObject's customPlaybackAttribute.
        """
        custom_playback_object = "customPlaybackObject"  # Name of the custom object
    
        try:
            # Fetch the playback rate from the correct object and attribute
            playback_rate = cmds.getAttr(f"{custom_playback_object}.customPlaybackAttribute", time=frame)
    
            # Handle invalid playback rate values
            if playback_rate <= 0:
                playback_rate = 1  # Default to 1 if invalid or zero
        except Exception:
            playback_rate = 1  # Fallback to 1 on error

        return playback_rate
    
    # ------------------------------------------------------------------
    # Rig target management
    # ------------------------------------------------------------------

    def _get_dag_root(self, node):
        """Walk up the DAG until we hit a node with no parent (the scene root)."""
        current = node
        while True:
            parents = cmds.listRelatives(current, parent=True, fullPath=True)
            if not parents:
                return current
            current = parents[0]

    def _scan_animated_descendants(self, root):
        """Return all nodes in root's hierarchy that have at least one animCurve."""
        all_nodes = [root] + (cmds.listRelatives(root, allDescendents=True, fullPath=True) or [])
        return [n for n in all_nodes if cmds.listConnections(n, type='animCurve')]

    def _add_rig_to_tree(self, root_path, controllers):
        """Add a root item and its controller children to the QTreeWidget."""
        short_root = root_path.split("|")[-1]
        root_item = QtWidgets.QTreeWidgetItem([short_root])
        root_item.setData(0, QtCore.Qt.UserRole, root_path)
        root_item.setData(0, QtCore.Qt.UserRole + 1, "root")
        bold = root_item.font(0)
        bold.setBold(True)
        root_item.setFont(0, bold)
        self.wgt_rig_tree.addTopLevelItem(root_item)

        for ctrl_path in controllers:
            short_ctrl = ctrl_path.split("|")[-1]
            ctrl_item = QtWidgets.QTreeWidgetItem([short_ctrl])
            ctrl_item.setData(0, QtCore.Qt.UserRole, ctrl_path)
            ctrl_item.setData(0, QtCore.Qt.UserRole + 1, "ctrl")
            root_item.addChild(ctrl_item)

        root_item.setExpanded(False)
        return root_item

    # ------------------------------------------------------------------
    # Rig data persistence (stored on the customPlaybackObject locator)
    # ------------------------------------------------------------------

    def _save_rig_data(self):
        """Serialise _rig_data to a JSON string and write it onto the scene locator."""
        import json
        if not cmds.objExists(self.obj):
            return
        # Store short names so the data is portable if the file is referenced
        # or if full paths change.  On load we resolve back via cmds.ls.
        storable = {}
        for root_path, ctrl_paths in self._rig_data.items():
            root_short = root_path.split("|")[-1]
            ctrl_shorts = [c.split("|")[-1] for c in ctrl_paths]
            storable[root_short] = ctrl_shorts
        try:
            cmds.setAttr(
                self.obj + '.' + self.rig_data_attr,
                json.dumps(storable),
                type='string'
            )
        except Exception:
            pass

    def _load_rig_data(self):
        """Read saved rig data from the locator and rebuild _rig_data + tree."""
        import json
        if not cmds.objExists(self.obj):
            return
        if not cmds.attributeQuery(self.rig_data_attr, node=self.obj, exists=True):
            return

        raw = cmds.getAttr(self.obj + '.' + self.rig_data_attr) or '{}'
        try:
            storable = json.loads(raw)
        except ValueError:
            return

        for root_short, ctrl_shorts in storable.items():
            # Resolve short name → full path.  ls() returns [] if node is gone.
            root_matches = cmds.ls(root_short, long=True)
            if not root_matches:
                continue
            root_path = root_matches[0]
            if root_path in self._rig_data:
                continue  # Already in tree (shouldn't happen on fresh load)

            ctrl_paths = []
            for cs in ctrl_shorts:
                matches = cmds.ls(cs, long=True)
                if matches:
                    ctrl_paths.append(matches[0])

            self._rig_data[root_path] = ctrl_paths
            self._add_rig_to_tree(root_path, ctrl_paths)

    def _reload_rig_data(self):
        """Clear the tree and re-read from the scene locator (Reload button)."""
        self.wgt_rig_tree.clear()
        self._rig_data = {}
        self._load_rig_data()

    def assign(self):
        """
        Smart assign — one button, two behaviours based on whether the selected
        node's rig root is already registered:
          • Root not yet known → register the rig and scan all animated descendants.
          • Root already known → add the selected nodes as additional controllers.
        """
        selection = cmds.ls(selection=True, long=True)
        if not selection:
            cmds.warning("Select at least one node to assign.")
            return

        for node in selection:
            root = self._get_dag_root(node)

            if root not in self._rig_data:
                # New rig — scan full hierarchy
                controllers = self._scan_animated_descendants(root)
                self._rig_data[root] = controllers
                self._add_rig_to_tree(root, controllers)
            else:
                # Rig already registered — add this node as an extra controller
                if node in self._rig_data[root]:
                    continue
                self._rig_data[root].append(node)
                for i in range(self.wgt_rig_tree.topLevelItemCount()):
                    top = self.wgt_rig_tree.topLevelItem(i)
                    if top.data(0, QtCore.Qt.UserRole) == root:
                        short = node.split("|")[-1]
                        child = QtWidgets.QTreeWidgetItem([short])
                        child.setData(0, QtCore.Qt.UserRole, node)
                        child.setData(0, QtCore.Qt.UserRole + 1, "ctrl")
                        top.addChild(child)
                        break

        self._save_rig_data()

    def remove_selected(self):
        """
        Remove highlighted items from the tree.
        - Root item  → remove the entire rig.
        - Ctrl items → remove only those controllers from their parent rig.
        """
        selected = self.wgt_rig_tree.selectedItems()
        if not selected:
            return

        roots_to_remove = set()
        ctrls_to_remove = []  # (root_path, ctrl_path)

        for item in selected:
            kind = item.data(0, QtCore.Qt.UserRole + 1)
            path = item.data(0, QtCore.Qt.UserRole)
            if kind == "root":
                roots_to_remove.add(path)
            else:
                parent_path = item.parent().data(0, QtCore.Qt.UserRole)
                # If the parent root is also being removed, skip — it'll all go
                if parent_path not in roots_to_remove:
                    ctrls_to_remove.append((parent_path, path))

        # Remove whole rigs
        for root_path in roots_to_remove:
            del self._rig_data[root_path]
            for i in range(self.wgt_rig_tree.topLevelItemCount()):
                top = self.wgt_rig_tree.topLevelItem(i)
                if top.data(0, QtCore.Qt.UserRole) == root_path:
                    self.wgt_rig_tree.takeTopLevelItem(i)
                    break

        # Remove individual controllers
        for root_path, ctrl_path in ctrls_to_remove:
            if root_path not in self._rig_data:
                continue
            if ctrl_path in self._rig_data[root_path]:
                self._rig_data[root_path].remove(ctrl_path)
            # Remove tree child item
            for i in range(self.wgt_rig_tree.topLevelItemCount()):
                top = self.wgt_rig_tree.topLevelItem(i)
                if top.data(0, QtCore.Qt.UserRole) == root_path:
                    for j in range(top.childCount()):
                        child = top.child(j)
                        if child.data(0, QtCore.Qt.UserRole) == ctrl_path:
                            top.takeChild(j)
                            break
                    break

        self._save_rig_data()

    def _filter_rig_tree(self, text):
        """Show/hide tree items based on search text. Always keep matched parents visible."""
        text = text.strip().lower()
        for i in range(self.wgt_rig_tree.topLevelItemCount()):
            top = self.wgt_rig_tree.topLevelItem(i)
            root_name = top.text(0).lower()
            any_child_visible = False

            for j in range(top.childCount()):
                child = top.child(j)
                ctrl_name = child.text(0).lower()
                visible = (not text) or (text in ctrl_name) or (text in root_name)
                child.setHidden(not visible)
                if visible:
                    any_child_visible = True

            # Root is visible if it matches itself or any child matched
            root_visible = (not text) or (text in root_name) or any_child_visible
            top.setHidden(not root_visible)
            if text and any_child_visible:
                top.setExpanded(True)

    def _get_target_objects(self):
        """
        Return a flat list of (root, [controllers]) tuples to operate on.
        Falls back to current Maya selection if no rigs are registered.
        """
        if self._rig_data:
            valid = {}
            for root, ctrls in self._rig_data.items():
                if not cmds.objExists(root):
                    cmds.warning(f"Rig root '{root.split('|')[-1]}' no longer exists — skipped.")
                    continue
                valid_ctrls = [c for c in ctrls if cmds.objExists(c)]
                if valid_ctrls:
                    valid[root] = valid_ctrls
            return valid

        # Fallback to selection
        sel = cmds.ls(selection=True, long=True)
        if not sel:
            cmds.warning("No rig targets assigned and nothing selected.")
            return {}
        # Wrap selection as pseudo-rig-data: each node is its own root
        return {node: [node] for node in sel}

    def bake_keyframes(self):
        target_data = self._get_target_objects()
        if not target_data:
            return

        start_frame, end_frame = self.get_frame_range()

        # Flatten to a deduplicated list of objects to bake
        objects_to_bake = []
        seen = set()
        for root, ctrls in target_data.items():
            for c in ctrls:
                if c not in seen:
                    seen.add(c)
                    objects_to_bake.append(c)
    
        # Dictionary to store sampled values for each object and attribute
        sampled_values = {}
        original_keyframes = {}
    
        # First pass: Sample and store the values
        for obj_to_bake in objects_to_bake:
            anim_curves = cmds.listConnections(obj_to_bake, type='animCurve')
            if not anim_curves:
                continue

            keyable_attrs = cmds.listAttr(obj_to_bake, k=True) or []

            # Store original keyframes before baking
            original_keyframes[obj_to_bake] = {}
            for attr in keyable_attrs:
                original_keyframes[obj_to_bake][attr] = cmds.keyframe(
                    obj_to_bake, attribute=attr, query=True, time=(start_frame, end_frame)
                )

            sampled_values[obj_to_bake] = {}

            current_frame = start_frame
            while current_frame <= end_frame:
                playback_rate = self.get_playback_rate_for_frame(current_frame)

                for attr in keyable_attrs:
                    if not cmds.objExists(obj_to_bake + '.' + attr):
                        continue
                    if not cmds.listConnections(obj_to_bake + '.' + attr, type='animCurve'):
                        continue

                    sampled_value = cmds.keyframe(
                        obj_to_bake, attribute=attr, time=(current_frame,), eval=True, query=True
                    )
                    value = sampled_value[0] if sampled_value else cmds.getAttr(
                        obj_to_bake + '.' + attr, time=current_frame
                    )

                    if attr not in sampled_values[obj_to_bake]:
                        sampled_values[obj_to_bake][attr] = []
                    sampled_values[obj_to_bake][attr].append((current_frame, value))

                current_frame += playback_rate

        # Second pass: Place the keyframes with stored values
        for obj_to_bake in sampled_values:
            for attr in sampled_values[obj_to_bake]:
                for (frame, value) in sampled_values[obj_to_bake][attr]:
                    cmds.setKeyframe(obj_to_bake, attribute=attr, time=frame, value=value, insertBlend=False)

        # Cleanup phase: Remove keyframes that weren't part of the bake
        for obj_to_bake in original_keyframes:
            for attr in original_keyframes[obj_to_bake]:
                if obj_to_bake not in sampled_values or attr not in sampled_values[obj_to_bake]:
                    continue

                baked_keyframes = set(frame for (frame, _) in sampled_values[obj_to_bake][attr])
                original_frames = set(original_keyframes[obj_to_bake][attr] or [])
                keyframes_to_remove = original_frames - baked_keyframes

                for frame in keyframes_to_remove:
                    try:
                        cmds.cutKey(obj_to_bake, attribute=attr, time=(frame,))
                    except Exception:
                        pass

        if self.wgt_chkbx_show_notifications.isChecked():
            cmds.confirmDialog(
                title="Bake Keyframes",
                message="Keyframes baked and cleaned up successfully.",
                button="OK"
            )


    def toggle_csv_saving(self, state):
        self.save_to_csv = state == QtCore.Qt.Checked

    def save_to_csv_file(self, playback_rates_after_redistribution):
        # Prompt user to choose a file location
        file_path = QtWidgets.QFileDialog.getSaveFileName(self, "Save CSV File", "", "CSV Files (*.csv)")
        if not file_path[0]:
            return  # User canceled the dialog
    
        file_path = file_path[0]
    
        # Write data to CSV file
        with open(file_path, 'w') as csv_file:
            writer = csv.writer(csv_file, delimiter=' ')
            for frame, rate in playback_rates_after_redistribution.items():
                writer.writerow([frame, rate])
    
        cmds.confirmDialog(title="CSV Saved", message=f"CSV file saved successfully at: {file_path}", button="OK", defaultButton="OK")

    def increment_frames(self):
        target_data = self._get_target_objects()
        if not target_data:
            return

        # Flatten to a deduplicated list
        seen = set()
        all_targets = []
        for root, ctrls in target_data.items():
            for c in ctrls:
                if c not in seen:
                    seen.add(c)
                    all_targets.append(c)

        for obj in all_targets:
            self.increment_frames_recursive(obj)

        for obj in all_targets:
            self.adjust_smoothing(obj)

        if self.wgt_chkbx_show_notifications.isChecked():
            cmds.confirmDialog(
                title="Increment Frames",
                message="Frames incremented successfully.",
                button="OK",
                defaultButton="OK"
            )

    def increment_frames_recursive(self, obj):
        # Check if the object or any of its descendants have animation curves
        if not self.has_animation_data(obj):
            return
    
        # Initialize a set to keep track of processed attributes for the current object
        processed_attributes = set()
    
        # Get keyable attributes of the object
        keyable_attrs = cmds.listAttr(obj, k=True) or []
    
        # Iterate over keyable attributes
        for attr in keyable_attrs:
            # Check if the attribute has already been processed for the current object
            if attr in processed_attributes:
                continue
    
            try:
                # Check if the attribute has animation curves
                if cmds.listConnections(obj + '.' + attr, type='animCurve'):
                    # Get keyframes data for the attribute
                    keyframes_data = self.collect_keyframes(obj, attr)
                    if keyframes_data:
                        self.redistribute_keyframes(obj, attr, keyframes_data)
    
                    # Add the attribute to the set of processed attributes for the current object
                    processed_attributes.add(attr)
            except Exception:
                continue
    
        # Recursively apply to children
        children = cmds.listRelatives(obj, children=True, fullPath=True) or []
        for child in children:
            self.increment_frames_recursive(child)

    def adjust_smoothing(self, obj):
        # Check if the object or any of its descendants have animation curves
        if not self.has_animation_data(obj):
            return
    
        # Get keyable attributes of the object
        keyable_attrs = cmds.listAttr(obj, k=True) or []
    
        # Iterate over keyable attributes
        for attr in keyable_attrs:
            # Check if the attribute has animation curves
            attr_path = cmds.ls(obj + '.' + attr, long=True)
            if not attr_path or not cmds.listConnections(attr_path[0], type='animCurve'):
                continue
    
            # Get keyframes data for the attribute
            keyframes_data = self.collect_keyframes(obj, attr)
            if keyframes_data:
                self.redistribute_keyframes(obj, attr, keyframes_data)
        
        # Recursively apply to children
        children = cmds.listRelatives(obj, children=True, fullPath=True) or []
        for child in children:
            self.adjust_smoothing(child)

    def collect_keyframes(self, obj, attr):
        keyframes_data = {}  # Dictionary to store keyframe data
        
        # Get all keyframes for the attribute
        keyframes = cmds.keyframe(obj, attribute=attr, q=True, timeChange=True)
        if not keyframes:
            return None
            
        for keyframe in keyframes:
            # Get keyframe value
            keyframe_value = cmds.keyframe(obj, attribute=attr, query=True, time=(keyframe, keyframe), valueChange=True)
            if keyframe_value is not None:
                # Get playback rate from custom playback object
                playback_rate = cmds.getAttr(self.obj + '.' + self.attr_name, time=keyframe)
                keyframes_data[keyframe] = {'value': keyframe_value[0], 'playback_rate': playback_rate}
        
        return keyframes_data

    def detect_peak_values(self, obj, attr):
        # Get keyframe data
        keyframes = cmds.keyframe(obj, attribute=attr, query=True, timeChange=True)
        values = cmds.keyframe(obj, attribute=attr, query=True, valueChange=True)
        
        # Dictionary to store peak values with integer keys
        peak_values = {}
        peak_frames = []
    
        for i in range(1, len(values) - 1):
            if values[i] > values[i-1] and values[i] > values[i+1]:
                peak_value = values[i]
                peak_frame = int(keyframes[i])  # Ensure the frame number is an integer
                peak_values[peak_frame] = peak_value
                peak_frames.append(peak_frame)
            elif values[i] < values[i-1] and values[i] < values[i+1]:
                peak_value = values[i]
                peak_frame = int(keyframes[i])  # Ensure the frame number is an integer
                peak_values[peak_frame] = peak_value
                peak_frames.append(peak_frame)
    
        return peak_values, peak_frames
        
    def redistribute_keyframes(self, obj, attr, keyframes_data, smoothing_strength=5):
        if not keyframes_data:
            return
                
        # Dictionary to store the playback rates after redistribution
        playback_rates_after_redistribution = {}
        
        # Clear existing animation data for the attribute
        cmds.cutKey(obj, attribute=attr)
        
        # Sort keyframes in order
        sorted_keyframes = sorted(keyframes_data.keys())
        
        start_frame, _ = self.get_frame_range()
        current_frame = start_frame
        for idx, keyframe in enumerate(sorted_keyframes, start=1):         
            # Set keyframe on the current frame
            cmds.setKeyframe(obj, attribute=attr, time=current_frame, value=keyframes_data[keyframe]['value'])
            
            # Store the playback rate after redistribution
            original_playback_rate = keyframes_data[keyframe]['playback_rate']
            playback_rates_after_redistribution[current_frame] = original_playback_rate
    
            # Move to the next frame
            current_frame += 1

        # Print adjusted playback rates after redistribution
        # print("Playback Rates After Redistribution:", playback_rates_after_redistribution)
    
        # Detect and store peak values and frames for smoothing
        original_peak_values, peak_frames = self.detect_peak_values(obj, attr)
        
        # Pass sorted keyframes from playback_rates_after_redistribution
        sorted_keyframes = sorted(playback_rates_after_redistribution.keys())
        playback_ranges = self.find_playback_ranges(sorted_keyframes, playback_rates_after_redistribution)
       
        # Pass original_peak_values to smooth_animation_curve function
        self.smooth_animation_curve(obj, attr, smoothing_strength, peak_frames, original_peak_values, playback_ranges, playback_rates_after_redistribution)

        # Save to CSV if checkbox is checked and CSV has not been saved yet
        if self.save_to_csv and not self.csv_saved:
            self.save_to_csv_file(playback_rates_after_redistribution)
            self.csv_saved = True  # Update flag to indicate CSV has been saved
        # Notify user
        #print("Animation data redistributed for attribute", attr)
        
    def smooth_animation_curve(self, obj, attr, smoothing_strength, peak_frames, original_peak_values, playback_ranges, playback_rates_after_redistribution):
        if not self.wgt_chkbx_enable_smoothing.isChecked():
            return
            
        # Get keyframe data
        keyframes = cmds.keyframe(obj, attribute=attr, query=True, timeChange=True)
        values = cmds.keyframe(obj, attribute=attr, query=True, valueChange=True)
    
        # Store original values before smoothing for frames outside the playback range
        original_values = dict()
        for i, frame in enumerate(keyframes):
            if not any(start <= frame <= end for start, end in playback_ranges):
                original_values[frame] = values[i]
    
        # Apply smoothing based on playback rate proximity to 1 using a nonlinear function
        smoothed_values = []
        frames_to_skip = set()  # To store frames with consecutive values
        for i, frame in enumerate(keyframes):
            playback_rate = playback_rates_after_redistribution[frame]
            # Check if playback rate is 1 or more or consecutive frames share the same value
            if playback_rate >= 1 or (i > 0 and values[i] == values[i - 1]):
                smoothed_values.append(values[i])  # No smoothing
            else:
                # Check if current frame shares the same value with both its previous and next frames
                if (i == 0 or values[i] != values[i - 1]) and (i == len(values) - 1 or values[i] != values[i + 1]):
                    # Calculate smoothing factor based on proximity to 1 using a cubic function
                    smoothing_factor = 0
                    for start, end in playback_ranges:
                        if start <= frame <= end:
                            dist_from_start = min(abs(frame - start), smoothing_strength)
                            dist_from_end = min(abs(frame - end), smoothing_strength)
                            smoothing_factor += min(dist_from_start, dist_from_end) / smoothing_strength
                    smoothing_factor /= len(playback_ranges)
                    smoothing_factor = smoothing_factor ** 2  # Cubic adjustment
                    
                    left_smooth_range = max(0, i - smoothing_strength)
                    right_smooth_range = min(len(values) - 1, i + smoothing_strength)
                    smoothed_value = sum(values[left_smooth_range:right_smooth_range + 1]) / (right_smooth_range - left_smooth_range + 1)
                    smoothed_values.append((1 - smoothing_factor) * values[i] + smoothing_factor * smoothed_value)
                else:
                    smoothed_values.append(values[i])  # No smoothing, retain original value
                    frames_to_skip.add(frame)  # Add frame to skip list
        
        # Update keyframes with smoothed values from the first pass
        for i, frame in enumerate(keyframes):
            if frame in peak_frames:
                smoothed_values[i] = original_peak_values[frame]
            cmds.keyframe(obj, attribute=attr, time=(frame, frame), valueChange=smoothed_values[i])
    
        # print("Animation curve smoothed based on playback rates for attribute:", attr)
    
        # Additional smoothing pass to eliminate abrupt changes for non-peak frames
        for playback_range_start, playback_range_end in playback_ranges:
            for i in range(keyframes.index(playback_range_start) + 1, keyframes.index(playback_range_end)):
                if keyframes[i] not in peak_frames and keyframes[i] not in frames_to_skip:
                    smoothed_values[i] = (smoothed_values[i-1] + smoothed_values[i] + smoothed_values[i+1]) / 3
        
        # Update keyframes with the values from the additional smoothing pass for non-peak frames
        for i, frame in enumerate(keyframes):
            if frame not in peak_frames and frame not in frames_to_skip:
                cmds.keyframe(obj, attribute=attr, time=(frame, frame), valueChange=smoothed_values[i])
        
        # print("Additional pass of smoothing to eliminate abrupt changes for attribute (non-peak frames within playback range):", attr)
        
        # Apply additional smoothing around peak frames while retaining peak values
        for peak_frame in peak_frames:
            peak_index = keyframes.index(peak_frame)
            left_smooth_range = max(0, peak_index - smoothing_strength)
            right_smooth_range = min(len(values) - 1, peak_index + smoothing_strength)
        
            # Retain the original peak value within the smoothing range
            peak_value = original_peak_values[peak_frame]
        
            # Calculate the influence of the peak value within the smoothing range
            for j in range(left_smooth_range, right_smooth_range + 1):
                # Calculate the weighting factor based on the distance from the peak frame to the current frame
                distance_to_peak = abs(peak_index - j)
                max_distance = smoothing_strength
                smoothing_factor = max(0, (max_distance - distance_to_peak) / max_distance) ** 2
        
                # Interpolate between the neighboring values and the peak value
                if j != peak_index:
                    # Smoothly interpolate between the neighboring values and the peak value
                    corrected_smoothing_factor = smoothing_factor * 1.1  # Adjust the correction factor as needed
                    smoothed_values[j] = (smoothed_values[j] * (1 - corrected_smoothing_factor)) + (peak_value * corrected_smoothing_factor)
        
        # Update keyframes with peak-smoothed values, retaining original peak values
        for i, frame in enumerate(keyframes):
            if frame not in peak_frames:
                cmds.keyframe(obj, attribute=attr, time=(frame, frame), valueChange=smoothed_values[i])
        
        # print("Additional smoothing applied around peaks for attribute:", attr)
    
        # Restore original values for frames outside smoothing range
        for frame, value in original_values.items():
            cmds.setKeyframe(obj, attribute=attr, time=frame, value=value)
            
        # Restore original values for start and end frames of the playback range
        for start, end in playback_ranges:
            cmds.setKeyframe(obj, attribute=attr, time=start, value=original_values.get(start, values[keyframes.index(start)]))
            cmds.setKeyframe(obj, attribute=attr, time=end, value=original_values.get(end, values[keyframes.index(end)]))

    def find_playback_ranges(self, keyframes, playback_rates_after_redistribution):
        playback_ranges = []
        playback_range_start = None
        in_range = False
        # Iterate over the keyframes to find the playback range
        for i, frame in enumerate(keyframes):
            # Get the playback rate for the current frame
            current_rate = playback_rates_after_redistribution[frame]
            # If not already in a range, look for the beginning of a range
            if not in_range:
                next_rate = playback_rates_after_redistribution[keyframes[i+1]] if i < len(keyframes) - 1 else None
                if next_rate is not None and current_rate != next_rate:
                    # Start of playback range found
                    playback_range_start = frame
                    in_range = True
            else:
                next_rate = playback_rates_after_redistribution[keyframes[i+1]] if i < len(keyframes) - 1 else None
                if next_rate is None or current_rate == next_rate:
                    # End of playback range found
                    playback_ranges.append((playback_range_start, frame))
                    in_range = False
        # If still in range at the end, finalize the current range
        if in_range:
            playback_ranges.append((playback_range_start, keyframes[-1]))
        return playback_ranges
    
    def has_animation_data(self, obj):
        # Check if the object itself has animation curves
        if cmds.listConnections(obj, type='animCurve'):
            return True
    
        # Check if any of its descendants have animation curves
        descendants = cmds.listRelatives(obj, allDescendents=True, fullPath=True) or []
        for descendant in descendants:
            if cmds.listConnections(descendant, type='animCurve'):
                return True
    
        return False

    def _on_dock_closed(self):
        """Called by MayaQWidgetDockableMixin when the workspace panel is closed."""
        self._shutdown()

    def hideEvent(self, event):
        """hideEvent fires reliably whenever the panel is hidden/closed by any means."""
        self._shutdown()
        super(TempoSlider, self).hideEvent(event)

    def closeEvent(self, event):
        """closeEvent fires when the widget is closed as a floating window."""
        self._shutdown()
        if event is not None:
            super(TempoSlider, self).closeEvent(event)

    def _shutdown(self):
        """Single teardown entry point — safe to call multiple times."""
        global _tempo_tool_window

        if self.deleted:
            return
        self.deleted = True

        # 1. Turn the tool toggle OFF — fires toggle_enabled_state(False) which
        #    stops the timer and resets playbackOptions through the normal path.
        try:
            self.is_enabled = True   # ensure toggle_enabled_state sees a real transition
            self.wgt_toggle_enabled.setChecked(False)
        except Exception:
            self.is_enabled = False

        # 2. Stop the QTimer so check_playback_rate cannot fire again.
        try:
            self.timer.stop()
        except Exception:
            pass

        # 3. Disconnect and stop the monitor thread.
        try:
            self.playback_monitor_thread.playback_state_changed.disconnect()
        except Exception:
            pass
        try:
            self.playback_monitor_thread.stop_thread = True
        except Exception:
            pass

        # 4. Kill all scriptJobs.
        for job_id in getattr(self, '_script_jobs', []):
            try:
                if cmds.scriptJob(exists=job_id):
                    cmds.scriptJob(kill=job_id, force=True)
            except Exception:
                pass
        self._script_jobs = []

        # 5. Reset playback unconditionally — belt-and-suspenders after toggle.
        try:
            cmds.playbackOptions(playbackSpeed=1)
            cmds.playbackOptions(maxPlaybackSpeed=1)
            cmds.playbackOptions(by=1)
        except Exception:
            pass

        # 6. Restore the custom attribute.
        try:
            cmds.setAttr(self.obj + '.' + self.attr_name, lock=False)
            cmds.setAttr(self.obj + '.' + self.attr_name, keyable=True, channelBox=True)
        except Exception:
            pass

        # 7. Defer a final reset in case Maya restores scene state post-close.
        try:
            mel.eval('evalDeferred("playbackOptions -playbackSpeed 1; playbackOptions -maxPlaybackSpeed 1; playbackOptions -by 1;")')
        except Exception:
            pass

        _tempo_tool_window = None

def maya_main_window():
    main_window = omui.MQtUtil.mainWindow()
    if sys.version_info.major >= 3:
        return wrapInstance(int(main_window), QtWidgets.QWidget)
    else:
        return wrapInstance(long(main_window), QtWidgets.QWidget)  # type: ignore

_tempo_tool_window = None
_WINDOW_OBJECT_NAME  = "PlaybackTempoToolWindow"
_WORKSPACE_CTRL_NAME = _WINDOW_OBJECT_NAME + "WorkspaceControl"

def show():
    global _tempo_tool_window

    if cmds.workspaceControl(_WORKSPACE_CTRL_NAME, exists=True):
        if _tempo_tool_window is not None:
            try:
                cmds.workspaceControl(_WORKSPACE_CTRL_NAME, e=True, restore=True)
                _tempo_tool_window.raise_()
                return
            except RuntimeError:
                pass
        cmds.deleteUI(_WORKSPACE_CTRL_NAME)
        _tempo_tool_window = None

    if not cmds.objExists(TempoSlider.obj):
        TempoSlider.obj = cmds.spaceLocator(name=TempoSlider.obj)[0]
        cmds.addAttr(TempoSlider.obj, ln=TempoSlider.attr_name, at='double', dv=1, k=True)
    else:
        TempoSlider.obj = cmds.ls(TempoSlider.obj)[0]

    _tempo_tool_window = TempoSlider()
    _tempo_tool_window.setObjectName(_WINDOW_OBJECT_NAME)
    _tempo_tool_window.show(dockable=True)

    # Connect the dock-panel close signal.
    # This only exists as a proper Qt signal after show(dockable=True).
    # hideEvent is the reliable fallback if this connection fails.
    try:
        _tempo_tool_window.dockCloseEventTriggered.connect(
            _tempo_tool_window._on_dock_closed
        )
    except Exception:
        pass

    # Reset playback on open.
    cmds.playbackOptions(playbackSpeed=1)
    cmds.playbackOptions(maxPlaybackSpeed=1)
    cmds.playbackOptions(by=1)

    cmds.setAttr(
        _tempo_tool_window.obj + '.' + _tempo_tool_window.attr_name,
        keyable=False,
        channelBox=True,
    )

def _reset_playback():
    """Reset Maya playback to neutral. Called on scene open and app init."""
    try:
        cmds.playbackOptions(playbackSpeed=1)
        cmds.playbackOptions(maxPlaybackSpeed=1)
        cmds.playbackOptions(by=1)
    except Exception:
        pass

# Reset on every scene open — prevents stale playbackOptions saved in scene files.
cmds.scriptJob(event=["SceneOpened", _reset_playback], permanent=True)

# Run immediately when executed via Script Editor or shelf button.
show()