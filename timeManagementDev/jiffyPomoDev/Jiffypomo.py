# JiffyPomo - Maya 2025 / PySide6 version
#
# This module assembles the JiffyPomo window from the tab modules below.
# Each tab lives in its own sibling module (jiffy*Tab.py) — add a new tab by
# building a QWidget there following the same init_ui/load_*/save_* pattern,
# then registering it in JiffyPomo.init_ui.

from PySide6 import QtWidgets, QtCore
import time
import json
import os
import logging
import shutil
import maya.cmds as cmds
from maya import OpenMayaUI as omui
from maya import OpenMaya as om
from shiboken6 import wrapInstance
from datetime import datetime

from jiffyUtils import get_ordinal_suffix
from jiffyWidgets import PromptsDisplay
from jiffyPromptsTab import PromptsTab
from jiffyNotepadTab import SimpleNotePadTab
from jiffyPomoTab import PomoTab
from jiffySummaryTab import SummaryTab
from jiffySettingsTab import SettingsTab

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class JiffyPomo(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(JiffyPomo, self).__init__(parent)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setWindowTitle("JiffyPomo")
        self.resize(600, 950)
        self.last_save_time = 0
        self.save_cooldown = 1.0
        self.last_summary_data = None
        self.settings_tab = SettingsTab(self)
        self.scene_open_callback_id = None
        self.scene_save_callback_id = None

        self.init_ui()
        self.load_state_auto()
        self.make_dockable()
        self.register_scene_callbacks()

    def init_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)

        scene_path = cmds.file(query=True, sceneName=True)
        scene_name = (
            os.path.splitext(os.path.basename(scene_path))[0]
            if scene_path
            else "Unsaved Scene"
        )
        self.scene_file_label = QtWidgets.QLabel(scene_name)
        self.scene_file_label.setStyleSheet(
            "font-size: 12px; color: white; font-weight: bold;"
        )
        self.scene_file_label.setAlignment(QtCore.Qt.AlignCenter)
        main_layout.addWidget(self.scene_file_label)

        self.tabs = QtWidgets.QTabWidget()
        main_layout.addWidget(self.tabs)

        self.prompts_tab = PromptsTab(self)
        self.notepad_tab = SimpleNotePadTab(self)
        self.pomo_tab = PomoTab(self)
        self.summary_tab = SummaryTab(self)

        self.tasks_tab = QtWidgets.QWidget()
        tasks_layout = QtWidgets.QVBoxLayout(self.tasks_tab)

        self.prompts_display = PromptsDisplay(self.prompts_tab)
        tasks_layout.addWidget(self.prompts_display)

        time_layout = QtWidgets.QHBoxLayout()
        self.stage = QtWidgets.QLineEdit(placeholderText="e.g., Blocking")

        current_date = datetime.now()
        date_str = f"{current_date.strftime('%B')} {current_date.day}{get_ordinal_suffix(current_date.day)}"
        self.date = QtWidgets.QLineEdit(date_str)
        self.date.textChanged.connect(self.save_state_auto)

        self.due = QtWidgets.QLineEdit(placeholderText="e.g., 8 hours")
        self.artist_time = QtWidgets.QLineEdit("00:00", inputMask="99:99")

        for label, widget in [
            ("Stage:", self.stage),
            ("Date:", self.date),
            ("Due:", self.due),
            ("Artist Time:", self.artist_time)
        ]:
            time_layout.addWidget(QtWidgets.QLabel(label))
            time_layout.addWidget(widget)
            widget.textChanged.connect(self.update_pomo_display)

        self.artist_time.textChanged.connect(self.update_pomo_timer_time)
        tasks_layout.addLayout(time_layout)

        self.task_text = QtWidgets.QTextEdit(
            styleSheet="color: white; background-color: #1e1e1e;"
        )
        self.task_text.textChanged.connect(self.update_pomo_display)
        tasks_layout.addWidget(self.task_text)

        self.tabs.addTab(self.tasks_tab, "Tasks")
        self.tabs.addTab(self.pomo_tab, "Pomo")
        self.tabs.addTab(self.prompts_tab, "Prompts")
        self.tabs.addTab(self.notepad_tab, "Note Pad")
        self.tabs.addTab(self.summary_tab, "Summary")
        self.tabs.addTab(self.settings_tab, "Settings")

        self.tabs.currentChanged.connect(self.handle_tab_change)

        self.date_timer = QtCore.QTimer(self)
        self.date_timer.timeout.connect(self.update_date)
        self.date_timer.start(60 * 60 * 1000)  # Check hourly

    def update_date(self):
        current_date = datetime.now()
        date_str = f"{current_date.strftime('%B')} {current_date.day}{get_ordinal_suffix(current_date.day)}"
        current_text = self.date.text().strip()
        if not self.date.hasFocus() and current_text != date_str:
            self.date.setText(date_str)
            logger.debug(f"Updated date to: {date_str} (was: {current_text})")
        else:
            logger.debug(
                f"Date not updated: has focus={self.date.hasFocus()}, "
                f"current={current_text}, new={date_str}"
            )

    def handle_tab_change(self, index):
        if self.tabs.tabText(index) == "Pomo":
            self.pomo_tab.update_display()
        if self.tabs.tabText(index) == "Tasks":
            self.update_date()
            self.prompts_display.random_prompt()

    def register_scene_callbacks(self):
        if self.scene_open_callback_id is not None:
            om.MEventMessage.removeCallback(self.scene_open_callback_id)
        if self.scene_save_callback_id is not None:
            om.MEventMessage.removeCallback(self.scene_save_callback_id)

        try:
            self.scene_open_callback_id = om.MEventMessage.addEventCallback(
                "SceneOpened",
                self.update_scene_name
            )
            self.scene_save_callback_id = om.MEventMessage.addEventCallback(
                "SceneSaved",
                self.update_scene_name
            )
            logger.debug("Registered scene open and save callbacks")
        except Exception as e:
            logger.error(f"Failed to register scene callbacks: {e}")

    def update_scene_name(self, *args):
        scene_path = cmds.file(query=True, sceneName=True)
        scene_name = (
            os.path.splitext(os.path.basename(scene_path))[0]
            if scene_path
            else "Unsaved Scene"
        )
        self.scene_file_label.setText(scene_name)
        logger.debug(f"Updated scene name to: {scene_name}")

        new_tasks_file = self.settings_tab.get_default_tasks_file()
        if new_tasks_file != self.settings_tab.default_tasks_file:
            if os.path.exists(self.settings_tab.default_tasks_file) and self.has_unsaved_changes():
                reply = QtWidgets.QMessageBox.question(
                    self,
                    "Unsaved Changes",
                    f"Unsaved changes in {self.settings_tab.default_tasks_file}. Save before switching?",
                    QtWidgets.QMessageBox.Save | QtWidgets.QMessageBox.Discard
                )
                if reply == QtWidgets.QMessageBox.Save:
                    self.save_state_auto()

            backup_path = self.settings_tab.default_tasks_file + ".bak"
            if os.path.exists(self.settings_tab.default_tasks_file):
                shutil.copy2(self.settings_tab.default_tasks_file, backup_path)
                logger.debug(f"Backed up tasks file to: {backup_path}")

            self.settings_tab.default_tasks_file = new_tasks_file
            self.settings_tab.load_tasks_file = new_tasks_file
            self.settings_tab.default_summary_file = self.settings_tab.get_default_summary_file()
            self.settings_tab.load_summary_file = self.settings_tab.default_summary_file
            logger.debug(f"Updated tasks file path to: {new_tasks_file}")

            self.load_state_auto()

    def has_unsaved_changes(self):
        current_state = {
            "stage": self.stage.text(),
            "date": self.date.text(),
            "due": self.due.text(),
            "tasks": self.task_text.toPlainText(),
            "timer_state": self.pomo_tab.get_timer_state()
        }

        tasks_file = self.settings_tab.get_tasks_file_path()
        if not os.path.exists(tasks_file):
            return bool(current_state["tasks"] or current_state["stage"])

        try:
            with open(tasks_file, "r") as f:
                saved_data = json.load(f)
            return any(
                current_state[k] != saved_data.get(k, "")
                for k in current_state
                if k != "timer_state"
            )
        except Exception as e:
            logger.error(f"Error checking unsaved changes: {e}")
            return True

    def load_state_auto(self):
        tasks_file = self.settings_tab.get_load_tasks_file_path()
        logger.debug(f"Loading tasks state from: {tasks_file}")
        timer_was_loaded = False

        if os.path.exists(tasks_file):
            try:
                with open(tasks_file, "r") as f:
                    tasks_data = json.load(f)

                self.stage.setText(tasks_data.get("stage", ""))
                self.due.setText(tasks_data.get("due", ""))

                artist_seconds = (
                    tasks_data.get("artist_time_hours", 0) * 3600
                    + tasks_data.get("artist_time_minutes", 0) * 60
                )
                self.artist_time.setText(self._format_time(artist_seconds))
                self.task_text.setPlainText(tasks_data.get("tasks", ""))

                timer_state = tasks_data.get("timer_state", {})
                if timer_state:
                    self.pomo_tab.load_timer_state(timer_state)
                    timer_was_loaded = True

                logger.debug(f"Loaded tasks data: {tasks_data}")
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Load State",
                    f"Error loading tasks data: {str(e)}"
                )
                logger.error(f"Error loading tasks data: {str(e)}")

        self.update_date()
        QtCore.QTimer.singleShot(0, self.update_date)

        self.prompts_tab.load_prompts()
        self.notepad_tab.load_notes()
        self.summary_tab.load_summary()

        scene_path = cmds.file(query=True, sceneName=True)
        scene_name = (
            os.path.splitext(os.path.basename(scene_path))[0]
            if scene_path
            else "Unsaved Scene"
        )
        self.scene_file_label.setText(scene_name)

    def save_shot_state(self):
        tasks_file = self.settings_tab.get_tasks_file_path()
        summary_file = self.settings_tab.get_summary_file_path()

        artist_seconds = self._parse_time(self.artist_time.text())

        # Save Tasks data
        tasks_data = {}
        if os.path.exists(tasks_file):
            try:
                with open(tasks_file, "r") as f:
                    tasks_data = json.load(f)
            except Exception as e:
                logger.error(f"Error reading tasks data: {str(e)}")

        tasks_data.update({
            "stage": self.stage.text(),
            "date": self.date.text(),
            "due": self.due.text(),
            "artist_time_hours": artist_seconds // 3600,
            "artist_time_minutes": (artist_seconds % 3600) // 60,
            "tasks": self.task_text.toPlainText(),
            "timer_state": self.pomo_tab.get_timer_state()
        })

        try:
            os.makedirs(os.path.dirname(tasks_file), exist_ok=True)
            with open(tasks_file + ".tmp", "w") as f:
                json.dump(tasks_data, f, indent=4)
            os.replace(tasks_file + ".tmp", tasks_file)
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self,
                "Save State",
                f"Error saving tasks data: {str(e)}"
            )

        # Save Summary data
        summary_data = self.get_summary_data()
        if self.last_summary_data:
            data_no_timestamp = {
                k: v
                for k, v in self.last_summary_data.items()
                if k != "timestamp"
            }
            if (
                not summary_data
                or {
                    k: v
                    for k, v in summary_data[-1].items()
                    if k != "timestamp"
                } != data_no_timestamp
            ):
                summary_data.append(self.last_summary_data)
            self.last_summary_data = None

        try:
            os.makedirs(os.path.dirname(summary_file), exist_ok=True)
            with open(summary_file + ".tmp", "w") as f:
                json.dump(summary_data, f, indent=4)
            os.replace(summary_file + ".tmp", summary_file)
            self.summary_tab.load_summary()
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self,
                "Save State",
                f"Error saving summary data: {str(e)}"
            )

    def get_summary_data(self):
        summary_file = self.settings_tab.get_summary_file_path()
        if os.path.exists(summary_file):
            try:
                with open(summary_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error reading summary data: {str(e)}")
                return []
        return []

    def save_state_auto(self):
        current_time = time.time()
        if current_time - self.last_save_time >= self.save_cooldown:
            self.save_shot_state()
            self.last_save_time = current_time

    def closeEvent(self, event):
        self.save_state_auto()
        self.prompts_tab.save_prompts()
        self.notepad_tab.save_notes()
        try:
            if self.scene_open_callback_id is not None:
                om.MEventMessage.removeCallback(self.scene_open_callback_id)
                self.scene_open_callback_id = None
            if self.scene_save_callback_id is not None:
                om.MEventMessage.removeCallback(self.scene_save_callback_id)
                self.scene_save_callback_id = None
        except RuntimeError as e:
            logger.debug(f"Error removing callbacks: {str(e)}")
        event.accept()

    def make_dockable(self):
        ptr = omui.MQtUtil.mainWindow()
        if ptr:
            parent = wrapInstance(int(ptr), QtWidgets.QMainWindow)
            self.setParent(parent)
            self.setWindowFlags(QtCore.Qt.Window)

    def _parse_time(self, text):
        try:
            h, m = map(int, text.split(":"))
            return h * 3600 + m * 60
        except ValueError:
            return 0

    def _format_time(self, seconds):
        h = seconds // 3600
        m = (seconds % 3600) // 60
        return f"{h:02d}:{m:02d}"

    def update_pomo_display(self):
        self.pomo_tab.update_display()

    def update_pomo_timer_time(self):
        new_total_seconds = self._parse_time(self.artist_time.text())
        if new_total_seconds <= 0:
            return

        timer_state = self.pomo_tab.get_timer_state()
        elapsed_time = 0

        if timer_state["original_seconds"] > 0:
            if timer_state["is_running"] and timer_state["start_time"]:
                elapsed_time = int(time.time() - timer_state["start_time"])
            elif not timer_state["is_running"] and timer_state["start_time"]:
                elapsed_time = (
                    timer_state["original_seconds"]
                    - timer_state["remaining_seconds"]
                )

        self.pomo_tab.original_seconds = new_total_seconds
        if elapsed_time > 0:
            self.pomo_tab.remaining_seconds = new_total_seconds - elapsed_time
        else:
            self.pomo_tab.remaining_seconds = new_total_seconds

        self.pomo_tab.timer_display.setText(
            self.pomo_tab._format_time(self.pomo_tab.remaining_seconds)
        )
        self.pomo_tab.timer_widget.set_time(
            self.pomo_tab.original_seconds,
            self.pomo_tab.remaining_seconds
        )
        self.pomo_tab.update_display()
        self.save_state_auto()


def run_jiffypomo():
    try:
        app = QtWidgets.QApplication.instance()
        if not app:
            logger.debug("No existing QApplication, creating new one")
            app = QtWidgets.QApplication([])
    except Exception as e:
        logger.error(f"Error initializing QApplication: {str(e)}")
        app = QtWidgets.QApplication([])

    global jiffypomo_window
    if 'jiffypomo_window' in globals() and isinstance(jiffypomo_window, QtWidgets.QWidget):
        jiffypomo_window.close()
        logger.debug("Closed existing JiffyPomo window")

    jiffypomo_window = JiffyPomo()
    jiffypomo_window.show()
    jiffypomo_window.raise_()
    logger.debug("JiffyPomo window launched")
    return jiffypomo_window


if __name__ == "__main__":
    run_jiffypomo()
