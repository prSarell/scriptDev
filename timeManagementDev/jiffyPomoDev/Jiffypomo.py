# JiffyPomo - Maya 2025 / PySide6 version

from PySide6 import QtWidgets, QtGui, QtCore
import time, json, os, random, traceback
import maya.cmds as cmds
from maya import OpenMayaUI as omui
from maya import OpenMaya as om
from shiboken6 import wrapInstance
from datetime import datetime
import logging
import shutil

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Default file paths
DEFAULT_LOCAL_DATA_DIR = os.path.join(os.path.expanduser("~"), "jiffyData")
DEFAULT_PROMPTS_FILE = os.path.join(DEFAULT_LOCAL_DATA_DIR, "jiffypomo_prompts.json")
DEFAULT_NOTES_FILE = os.path.join(DEFAULT_LOCAL_DATA_DIR, "jiffypomo_notes.json")


# Helper function
def get_ordinal_suffix(day):
    if 11 <= day % 100 <= 13:
        return "th"
    else:
        suffixes = {1: "st", 2: "nd", 3: "rd"}
        return suffixes.get(day % 10, "th")


# Supporting Classes
class RewardDialog(QtWidgets.QDialog):
    def __init__(self, message, parent=None):
        super(RewardDialog, self).__init__(parent)
        self.setWindowTitle("Great Job!")
        # Window stays on top
        self.setWindowFlags(QtCore.Qt.Dialog | QtCore.Qt.WindowStaysOnTopHint)
        layout = QtWidgets.QVBoxLayout(self)

        label = QtWidgets.QLabel(message)
        font = QtGui.QFont()
        font.setPointSize(16)
        font.setBold(True)
        label.setFont(font)
        label.setAlignment(QtCore.Qt.AlignCenter)

        bright_colors = [
            "blue", "green", "yellow", "magenta", "cyan",
            "orange", "purple", "pink", "lime", "teal"
        ]
        label.setStyleSheet(f"color: {random.choice(bright_colors)};")
        layout.addWidget(label)

        QtCore.QTimer.singleShot(4000, self.accept)


class NotificationDialog(QtWidgets.QDialog):
    def __init__(self, message, parent=None):
        super().__init__(parent)
        logger.debug(f"Showing notification: {message}")
        self.setWindowTitle("Notification")
        self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
        layout = QtWidgets.QVBoxLayout(self)

        label = QtWidgets.QLabel(message)
        label.setFont(QtGui.QFont("", 14, QtGui.QFont.Bold))
        label.setAlignment(QtCore.Qt.AlignCenter)

        colors = [
            "blue", "green", "yellow", "magenta", "cyan",
            "orange", "purple", "pink", "lime", "teal"
        ]
        color = random.choice(colors)
        label.setStyleSheet(f"color: {color};")
        layout.addWidget(label)

        QtCore.QTimer.singleShot(3000, self.accept)


class PromptWidget(QtWidgets.QWidget):
    def __init__(self, prompt_text="", important=False, parent=None):
        super(PromptWidget, self).__init__(parent)
        self.important = important
        self.init_ui(prompt_text)

    def init_ui(self, prompt_text):
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.line_edit = QtWidgets.QLineEdit(prompt_text)
        layout.addWidget(self.line_edit)

        self.importance_checkbox = QtWidgets.QCheckBox("Important")
        self.importance_checkbox.setChecked(self.important)
        self.importance_checkbox.stateChanged.connect(self.update_importance)
        layout.addWidget(self.importance_checkbox)

        self.delete_button = QtWidgets.QPushButton("Delete")
        self.delete_button.setFixedWidth(60)
        layout.addWidget(self.delete_button)
        self.delete_button.clicked.connect(self.delete_self)

        self.update_importance()

    def update_importance(self):
        self.important = self.importance_checkbox.isChecked()
        self.line_edit.setStyleSheet(
            "color: green;" if self.important else "color: white;"
        )

    def delete_self(self):
        parent = self.parent()
        self.setParent(None)
        self.deleteLater()
        if parent and hasattr(parent, 'save_prompts'):
            parent.cached_prompts = parent.get_data()
            parent.save_prompts()

    def get_text(self):
        return self.line_edit.text()

    def is_important(self):
        return self.important


class PromptsDisplay(QtWidgets.QLabel):
    def __init__(self, prompts_tab, parent=None):
        super(PromptsDisplay, self).__init__(parent)
        self.prompts_tab = prompts_tab
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.setFixedHeight(80)
        self.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)

        self.start_timer()
        self.prompts_tab.refresh_interval_changed.connect(self.update_interval)
        self.random_prompt()

    def start_timer(self):
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.random_prompt)
        self.timer.start(self.prompts_tab.get_refresh_interval())

    def random_prompt(self):
        data = self.prompts_tab.cached_prompts
        if data:
            important = [p for p in data if p["important"]]
            regular = [p for p in data if not p["important"]]

            if important and random.random() < 0.6:
                chosen = random.choice(important)
                self.setText(chosen["text"])
                self.setStyleSheet(
                    "font-weight: bold; font-size: 14px; color: green;"
                )
                interval = self.prompts_tab.get_refresh_interval() * 1.25
            elif regular:
                chosen = random.choice(regular)
                self.setText(chosen["text"])
                self.setStyleSheet(
                    "font-weight: bold; font-size: 14px; color: white;"
                )
                interval = self.prompts_tab.get_refresh_interval()
            else:
                self.setText("No prompts available")
                self.setStyleSheet(
                    "font-weight: bold; font-size: 14px; color: white;"
                )
                interval = self.prompts_tab.get_refresh_interval()

            self.timer.start(int(interval))
        else:
            self.setText("No prompts available")
            self.setStyleSheet(
                "font-weight: bold; font-size: 14px; color: white;"
            )
            self.timer.start(self.prompts_tab.get_refresh_interval())

    def update_interval(self, new_interval):
        self.timer.start(new_interval)
        self.random_prompt()


class TimerCircleWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(TimerCircleWidget, self).__init__(parent)
        self.total_seconds = 0
        self.remaining_seconds = 0
        self.setMinimumSize(300, 300)

    def set_time(self, total_seconds, remaining_seconds):
        self.total_seconds = total_seconds
        self.remaining_seconds = remaining_seconds
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        rect = self.rect()
        center = rect.center()
        radius = min(rect.width(), rect.height()) // 2 - 10

        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor(144, 238, 144))  # Light green

        if self.total_seconds > 0:
            angle = int((self.remaining_seconds / self.total_seconds) * 360 * 16)
            painter.drawPie(
                center.x() - radius,
                center.y() - radius,
                radius * 2,
                radius * 2,
                90 * 16,
                angle
            )
        else:
            painter.drawEllipse(center, radius, radius)


# Tab Classes
class PromptsTab(QtWidgets.QWidget):
    refresh_interval_changed = QtCore.Signal(int)

    def __init__(self, parent=None):
        super(PromptsTab, self).__init__(parent)
        self.parent_widget = parent
        self.prompts_file = (
            DEFAULT_PROMPTS_FILE
            if not parent
            else self.parent_widget.settings_tab.get_load_prompts_file_path()
        )
        self.cached_prompts = []
        self.init_ui()
        self.load_prompts()

    def init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        # Input for new prompts
        input_layout = QtWidgets.QHBoxLayout()
        self.prompt_input = QtWidgets.QTextEdit()
        self.prompt_input.setFixedHeight(60)
        self.prompt_input.setStyleSheet(
            "color: white; background-color: #1e1e1e;"
        )
        self.add_prompt_button = QtWidgets.QPushButton("Add Prompt")
        input_layout.addWidget(self.prompt_input)
        input_layout.addWidget(self.add_prompt_button)
        layout.addLayout(input_layout)

        # Refresh interval
        interval_layout = QtWidgets.QHBoxLayout()
        interval_label = QtWidgets.QLabel("Refresh Interval (MM:SS):")
        self.refresh_interval_lineedit = QtWidgets.QLineEdit("00:10")
        interval_layout.addWidget(interval_label)
        interval_layout.addWidget(self.refresh_interval_lineedit)
        layout.addLayout(interval_layout)

        self.refresh_interval_lineedit.textChanged.connect(
            self.emit_refresh_interval
        )

        # Scroll area for prompts
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.prompt_container = QtWidgets.QWidget()
        self.prompt_layout = QtWidgets.QVBoxLayout(self.prompt_container)
        self.prompt_layout.setAlignment(QtCore.Qt.AlignTop)
        self.scroll_area.setWidget(self.prompt_container)
        layout.addWidget(self.scroll_area)

        # Save button
        self.save_button = QtWidgets.QPushButton("Save Prompts")
        self.save_button.clicked.connect(self.save_prompts)
        layout.addWidget(self.save_button)

        self.add_prompt_button.clicked.connect(self.add_prompt)

    def save_prompts(self):
        self.prompts_file = self.parent_widget.settings_tab.get_prompts_file_path()
        current_ui_data = self.get_data()

        # Ensure cached_prompts is updated to reflect the current UI state
        self.cached_prompts = current_ui_data[:]

        # Load existing prompts from file
        existing_data = []
        if os.path.exists(self.prompts_file):
            try:
                with open(self.prompts_file, "r") as f:
                    file_data = json.load(f)
                existing_data = file_data.get("prompts", [])
            except Exception as e:
                logger.error(f"Error loading existing prompts for merge: {str(e)}")

        # Merge prompts, prioritizing UI data and removing duplicates
        merged_prompts = []
        seen = set()  # Track (text, important) tuples to avoid duplicates
        for prompt in current_ui_data + existing_data:
            key = (prompt["text"], prompt["important"])
            if key not in seen:
                merged_prompts.append(prompt)
                seen.add(key)

        logger.debug(f"Saving {len(merged_prompts)} prompts to {self.prompts_file}")
        try:
            os.makedirs(os.path.dirname(self.prompts_file), exist_ok=True)
            with open(self.prompts_file + ".tmp", "w") as f:
                json.dump(
                    {
                        "prompts": merged_prompts,
                        "refresh_interval": self.get_refresh_interval()
                    },
                    f,
                    indent=4
                )
            os.replace(self.prompts_file + ".tmp", self.prompts_file)
            self.cached_prompts = merged_prompts  # Update cache after successful save
        except Exception as e:
            logger.error(f"ERROR saving prompts: {str(e)}")
            QtWidgets.QMessageBox.warning(
                self,
                "Save Error",
                f"Failed to save prompts: {str(e)}"
            )

    def load_prompts(self):
        self.prompts_file = self.parent_widget.settings_tab.get_load_prompts_file_path()
        if os.path.exists(self.prompts_file):
            try:
                with open(self.prompts_file, "r") as f:
                    show_data = json.load(f)
                prompts = show_data.get("prompts", [])
                refresh_interval = show_data.get("refresh_interval", 10000)
                total_sec = refresh_interval // 1000
                minutes = total_sec // 60
                seconds = total_sec % 60
                self.refresh_interval_lineedit.setText(
                    f"{minutes:02d}:{seconds:02d}"
                )

                # Clear existing widgets
                while self.prompt_layout.count():
                    item = self.prompt_layout.takeAt(0)
                    if item.widget():
                        item.widget().deleteLater()

                # Rebuild from file
                for prompt_data in prompts:
                    text = prompt_data.get("text", "")
                    important = prompt_data.get("important", False)
                    self.prompt_layout.addWidget(
                        PromptWidget(prompt_text=text, important=important, parent=self)
                    )

                self.cached_prompts = self.get_data()
            except Exception as e:
                logger.error(f"Error loading prompts: {str(e)}")

    def emit_refresh_interval(self):
        text = self.refresh_interval_lineedit.text().strip()
        parts = text.split(":")
        if len(parts) == 2:
            try:
                minutes = int(parts[0])
                seconds = int(parts[1])
                total_seconds = minutes * 60 + seconds
                self.refresh_interval_changed.emit(total_seconds * 1000)
            except ValueError:
                pass

    def add_prompt(self):
        text = self.prompt_input.toPlainText().strip()
        if text:
            prompt_widget = PromptWidget(prompt_text=text, parent=self)
            self.prompt_layout.addWidget(prompt_widget)
            self.prompt_input.clear()
            self.cached_prompts = self.get_data()

    def get_data(self):
        data = []
        for i in range(self.prompt_layout.count()):
            widget = self.prompt_layout.itemAt(i).widget()
            if widget and isinstance(widget, PromptWidget):
                data.append(
                    {
                        "text": widget.get_text(),
                        "important": widget.is_important()
                    }
                )
        return data

    def get_refresh_interval(self):
        text = self.refresh_interval_lineedit.text().strip()
        parts = text.split(":")
        if len(parts) == 2:
            try:
                minutes = int(parts[0])
                seconds = int(parts[1])
                return (minutes * 60 + seconds) * 1000
            except ValueError:
                return 10000
        return 10000


class SimpleNotePadTab(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(SimpleNotePadTab, self).__init__(parent)
        self.parent_widget = parent
        self.notes_file = (
            DEFAULT_NOTES_FILE
            if not parent
            else self.parent_widget.settings_tab.get_load_notes_file_path()
        )
        self.last_save_time = 0
        self.save_cooldown = 1.0

        self.init_ui()

        self.save_timer = QtCore.QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self.save_notes)

        self.load_notes()

    def init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        self.note_text = QtWidgets.QTextEdit()
        self.note_text.setStyleSheet(
            "color: white; background-color: #1e1e1e;"
        )
        self.note_text.textChanged.connect(self.trigger_save)
        layout.addWidget(self.note_text)

        self.save_button = QtWidgets.QPushButton("Save Notes (Manual)")
        self.save_button.clicked.connect(self.save_notes)
        layout.addWidget(self.save_button)

    def trigger_save(self):
        if not self.save_timer.isActive():
            self.save_timer.start(1000)

    def save_notes(self):
        current_time = time.time()
        if current_time - self.last_save_time >= self.save_cooldown:
            self.notes_file = self.parent_widget.settings_tab.get_notes_file_path()
            notes = self.note_text.toPlainText()
            try:
                os.makedirs(os.path.dirname(self.notes_file), exist_ok=True)
                with open(self.notes_file, "w") as f:
                    json.dump({"notepad": notes}, f, indent=4)
                self.last_save_time = current_time
            except Exception as e:
                logger.error(f"ERROR saving notes: {str(e)}")

    def load_notes(self):
        self.notes_file = self.parent_widget.settings_tab.get_load_notes_file_path()
        if os.path.exists(self.notes_file):
            try:
                with open(self.notes_file, "r") as f:
                    data = json.load(f)
                notes = data.get("notepad", "")
                self.note_text.setPlainText(notes)
            except Exception as e:
                logger.error(f"ERROR loading notes: {str(e)}")
        else:
            self.note_text.setPlainText("")


class PomoTab(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.is_running = False
        self.remaining_seconds = 0
        self.original_seconds = 0
        self.start_time = None

        self._setup_ui()

        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.update_timer)

    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        self.time_info = QtWidgets.QLabel("Stage: N/A | Date: N/A | Due: N/A | Artist Time: 00:00")
        self.time_info.setStyleSheet("font-size: 14px; color: white;")
        layout.addWidget(self.time_info)

        button_layout = QtWidgets.QHBoxLayout()
        self.start_pause_btn = QtWidgets.QPushButton("Start")
        self.start_pause_btn.clicked.connect(self.toggle_timer)
        self.start_pause_btn.setFixedWidth(100)
        self.start_pause_btn.setStyleSheet("font-size: 16px;")
        button_layout.addWidget(self.start_pause_btn)

        self.complete_btn = QtWidgets.QPushButton("Complete")
        self.complete_btn.clicked.connect(self.handle_complete)
        self.complete_btn.setFixedWidth(100)
        self.complete_btn.setStyleSheet("font-size: 16px;")
        button_layout.addWidget(self.complete_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        if self.parent:
            self.prompts_display = PromptsDisplay(self.parent.prompts_tab, self)
            layout.addWidget(self.prompts_display)

        layout.addStretch()

        self.timer_widget = TimerCircleWidget(self)
        timer_layout = QtWidgets.QVBoxLayout(self.timer_widget)
        self.timer_display = QtWidgets.QLabel("00:00:00")
        self.timer_display.setFont(QtGui.QFont("", 48, QtGui.QFont.Bold))
        self.timer_display.setStyleSheet("color: white; background-color: transparent;")
        self.timer_display.setAlignment(QtCore.Qt.AlignCenter)
        timer_layout.addWidget(self.timer_display)
        layout.addWidget(self.timer_widget)

        layout.addStretch()

        self.tasks_display = QtWidgets.QLabel("No tasks entered")
        self.tasks_display.setStyleSheet("font-size: 12px; color: white;")
        self.tasks_display.setAlignment(QtCore.Qt.AlignCenter)
        self.tasks_display.setWordWrap(True)
        layout.addWidget(self.tasks_display)

    def _parse_time(self, text):
        try:
            h, m = map(int, text.split(":"))
            return h * 3600 + m * 60
        except ValueError:
            return 0

    def _format_time(self, seconds):
        is_negative = seconds < 0
        abs_seconds = abs(seconds)
        h = abs_seconds // 3600
        m = (abs_seconds % 3600) // 60
        s = abs_seconds % 60
        return (
            f"-{h:02d}:{m:02d}:{s:02d}"
            if is_negative
            else f"{h:02d}:{m:02d}:{s:02d}"
        )

    def toggle_timer(self):
        if not self.is_running:
            if self.remaining_seconds == 0 and self.parent:
                self.remaining_seconds = self._parse_time(self.parent.artist_time.text())
                self.original_seconds = self.remaining_seconds

            if self.remaining_seconds != 0 or self.original_seconds > 0:
                self.is_running = True
                if not self.start_time:
                    self.start_time = time.time()
                else:
                    elapsed = self.original_seconds - self.remaining_seconds
                    self.start_time = time.time() - elapsed

                self.start_pause_btn.setText("Pause")
                self.timer.start(1000)
                self.timer_widget.set_time(self.original_seconds, self.remaining_seconds)

                cmds.evalDeferred(lambda: NotificationDialog("Timer started", self).show())
                if self.parent:
                    self.parent.save_state_auto()
        else:
            self.is_running = False
            self.start_pause_btn.setText("Start")
            self.timer.stop()
            cmds.evalDeferred(lambda: NotificationDialog("Timer paused", self).show())
            if self.parent:
                self.parent.save_state_auto()

    def update_timer(self):
        if self.is_running:
            elapsed = int(time.time() - self.start_time)
            self.remaining_seconds = self.original_seconds - elapsed
            self.timer_display.setText(self._format_time(self.remaining_seconds))
            self.timer_widget.set_time(self.original_seconds, self.remaining_seconds)

    def handle_complete(self):
        if self.is_running:
            self.is_running = False
            self.start_pause_btn.setText("Start")
            self.timer.stop()
            elapsed = int(time.time() - self.start_time)
            self.remaining_seconds = self.original_seconds - elapsed
            self.timer_widget.set_time(self.original_seconds, self.remaining_seconds)
            cmds.evalDeferred(
                lambda: NotificationDialog("Timer stopped via Complete", self).show()
            )

        if self.parent:
            actual_time = self.original_seconds - self.remaining_seconds
            self.parent.last_summary_data = {
                "tasks": self.parent.task_text.toPlainText().strip(),
                "stage": self.parent.stage.text() or "N/A",
                "date": self.parent.date.text() or "N/A",
                "due": self.parent.due.text() or "N/A",
                "artist_time": self.parent.artist_time.text(),
                "actual_time": self._format_time(actual_time),
                "timestamp": time.time()
            }
            self.parent.save_state_auto()
            self.parent.artist_time.setText("00:00")

        if self.remaining_seconds > 0:
            cmds.evalDeferred(
                lambda: NotificationDialog(
                    f"Completed early with {self.remaining_seconds} seconds remaining",
                    self
                ).show()
            )
            self.show_reward()
        elif self.remaining_seconds == 0:
            cmds.evalDeferred(
                lambda: NotificationDialog(
                    "Completed exactly on time - no reward", self
                ).show()
            )
        else:
            overrun_seconds = abs(self.remaining_seconds)
            cmds.evalDeferred(
                lambda: NotificationDialog(
                    f"Completed late by {self._format_time(overrun_seconds)} - no reward",
                    self
                ).show()
            )

        self.remaining_seconds = 0
        self.original_seconds = 0
        self.start_time = None
        self.timer_display.setText("00:00:00")
        self.timer_widget.set_time(0, 0)

    def show_reward(self):
        reward_messages = [
            "Great job, you smashed it!",
            "You are killing it today!",
            "Fantastic work!",
            "On fire",
            "Yeah Bouy!",
            "Fernsteuerung! Fernsteuerung!",
            "Way to go, superstar!",
            "You're crushing it!",
            "Nailed it!",
            "Bravo, that was amazing!",
            "Impressive work, well done!",
            "Smashing work Gromit!",
            "Superb effort, keep shining!",
            "You're unstoppable!",
            "What a triumph!",
            "Amazing job, keep up the great work!",
            "There's a new Sheriff in Town!!!",
            "Incredible, you're a rockstar!",
            "Sensational performance!",
            "Ayyappan! Yes I can!! Yes I can!!!",
            "Your productivity is inspiring!",
            "Mike, you F*cken LEGEND!!!",
            "They said you'd never make it, but you finally came through!",
            "You’re a wizard Harry!"
        ]
        message = random.choice(reward_messages)
        cmds.evalDeferred(lambda: RewardDialog(message, self).show())

    def update_display(self):
        if self.parent:
            stage = self.parent.stage.text() or "N/A"
            date = self.parent.date.text() or "N/A"
            due = self.parent.due.text() or "N/A"
            artist_time = self.parent.artist_time.text()
            self.time_info.setText(
                f"Stage: {stage} | Date: {date} | Due: {due} | Artist Time: {artist_time}"
            )

            if not self.is_running:
                self.timer_display.setText(self._format_time(self.remaining_seconds))
                self.timer_widget.set_time(self.original_seconds, self.remaining_seconds)

            tasks_text = self.parent.task_text.toPlainText().strip() or "No tasks entered"
            self.tasks_display.setText(tasks_text)

    def get_timer_state(self):
        return {
            "is_running": self.is_running,
            "original_seconds": self.original_seconds,
            "remaining_seconds": (
                self.remaining_seconds
                if not self.is_running
                else self.original_seconds - int(time.time() - self.start_time)
            ),
            "start_time": self.start_time
        }

    def load_timer_state(self, state):
        self.is_running = state.get("is_running", False)
        self.original_seconds = state.get("original_seconds", 0)
        self.remaining_seconds = state.get("remaining_seconds", 0)
        self.start_time = state.get("start_time", None)

        if not self.original_seconds and self.parent:
            self.original_seconds = self._parse_time(self.parent.artist_time.text())
            self.remaining_seconds = self.original_seconds

        if self.is_running and self.start_time:
            elapsed_since_close = int(time.time() - self.start_time)
            self.remaining_seconds = self.original_seconds - elapsed_since_close
            self.start_time = time.time() - (
                self.original_seconds - self.remaining_seconds
            )
            self.timer.start(1000)
            self.start_pause_btn.setText("Pause")
        else:
            self.start_pause_btn.setText("Start")

        self.timer_display.setText(self._format_time(self.remaining_seconds))
        self.timer_widget.set_time(self.original_seconds, self.remaining_seconds)


class SummaryTab(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(SummaryTab, self).__init__(parent)
        self.parent = parent
        self.init_ui()

    def init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        self.summary_text = QtWidgets.QTextEdit()
        self.summary_text.setStyleSheet(
            "color: white; background-color: #1e1e1e;"
        )
        layout.addWidget(self.summary_text)

        self.save_button = QtWidgets.QPushButton("Save")
        self.save_button.clicked.connect(self.save_manual_edits)
        layout.addWidget(self.save_button)

    def load_summary(self):
        summary_file = (
            self.parent.settings_tab.get_summary_file_path()
            if self.parent
            else os.path.join(os.path.expanduser("~"), "jiffypomo_summary.json")
        )

        if os.path.exists(summary_file):
            try:
                with open(summary_file, "r") as f:
                    summary_data = json.load(f)

                text = ""
                for entry in summary_data:
                    if not isinstance(entry, dict):
                        continue
                    text += f"Tasks: {entry.get('tasks', 'N/A')}\n"
                    text += f"Stage: {entry.get('stage', 'N/A')}\n"
                    text += f"Date: {entry.get('date', 'N/A')}\n"
                    text += f"Due: {entry.get('due', 'N/A')}\n"
                    text += f"Artist Time: {entry.get('artist_time', 'N/A')}\n"
                    text += f"Actual Time Taken: {entry.get('actual_time', 'N/A')}\n"
                    text += "-" * 50 + "\n"

                self.summary_text.setPlainText(
                    text.strip() or "No summary data available yet."
                )
            except Exception as e:
                self.summary_text.setPlainText(f"Error loading summary: {str(e)}")
        else:
            self.summary_text.setPlainText("No summary data available yet.")

    def save_manual_edits(self):
        summary_file = (
            self.parent.settings_tab.get_summary_file_path()
            if self.parent
            else os.path.join(os.path.expanduser("~"), "jiffypomo_summary.json")
        )

        text = self.summary_text.toPlainText().strip()
        summary_data = []

        if text and "No summary data" not in text and "Error" not in text:
            entries = text.split("-" * 50)
            for entry in entries:
                if entry.strip():
                    lines = [
                        line.strip()
                        for line in entry.split("\n")
                        if line.strip()
                    ]
                    entry_dict = {}
                    for line in lines:
                        for key, prefix in [
                            ("tasks", "Tasks: "),
                            ("stage", "Stage: "),
                            ("date", "Date: "),
                            ("due", "Due: "),
                            ("artist_time", "Artist Time: "),
                            ("actual_time", "Actual Time Taken: ")
                        ]:
                            if line.startswith(prefix):
                                entry_dict[key] = line.replace(prefix, "")
                                break
                    if len(entry_dict) == 6:
                        entry_dict["timestamp"] = time.time()
                        summary_data.append(entry_dict)

        try:
            os.makedirs(os.path.dirname(summary_file), exist_ok=True)
            with open(summary_file + ".tmp", "w") as f:
                json.dump(summary_data, f, indent=4)
            os.replace(summary_file + ".tmp", summary_file)
            QtWidgets.QMessageBox.information(
                self, "Save Summary", "Manual edits saved successfully."
            )
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self,
                "Save Summary",
                f"Error saving manual edits: {str(e)}"
            )


class SettingsTab(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(SettingsTab, self).__init__(parent)
        self.default_tasks_file = self.get_default_tasks_file()
        self.default_summary_file = self.get_default_summary_file()
        self.default_notes_file = self.get_default_notes_file()
        self.default_prompts_file = self.get_default_prompts_file()

        self.load_tasks_file = self.default_tasks_file
        self.load_summary_file = self.default_summary_file
        self.load_notes_file = self.default_notes_file
        self.load_prompts_file = self.default_prompts_file

        self.init_ui()

    def init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        # Tasks
        tasks_layout = QtWidgets.QHBoxLayout()
        tasks_label = QtWidgets.QLabel("Tasks File:")
        self.tasks_file_lineedit = QtWidgets.QLineEdit(self.load_tasks_file)
        self.tasks_file_lineedit.setMinimumWidth(400)
        tasks_browse = QtWidgets.QPushButton("Browse")
        tasks_layout.addWidget(tasks_label)
        tasks_layout.addWidget(self.tasks_file_lineedit)
        tasks_layout.addWidget(tasks_browse)

        # Summary
        summary_layout = QtWidgets.QHBoxLayout()
        summary_label = QtWidgets.QLabel("Summary File:")
        self.summary_file_lineedit = QtWidgets.QLineEdit(self.load_summary_file)
        self.summary_file_lineedit.setMinimumWidth(400)
        summary_browse = QtWidgets.QPushButton("Browse")
        summary_layout.addWidget(summary_label)
        summary_layout.addWidget(self.summary_file_lineedit)
        summary_layout.addWidget(summary_browse)

        # Notes
        notes_layout = QtWidgets.QHBoxLayout()
        notes_label = QtWidgets.QLabel("Notes File:")
        self.notes_file_lineedit = QtWidgets.QLineEdit(self.load_notes_file)
        self.notes_file_lineedit.setMinimumWidth(400)
        notes_browse = QtWidgets.QPushButton("Browse")
        notes_layout.addWidget(notes_label)
        notes_layout.addWidget(self.notes_file_lineedit)
        notes_layout.addWidget(notes_browse)

        # Prompts
        prompts_layout = QtWidgets.QHBoxLayout()
        prompts_label = QtWidgets.QLabel("Prompts File:")
        self.prompts_file_lineedit = QtWidgets.QLineEdit(self.load_prompts_file)
        self.prompts_file_lineedit.setMinimumWidth(400)
        prompts_browse = QtWidgets.QPushButton("Browse")
        prompts_layout.addWidget(prompts_label)
        prompts_layout.addWidget(self.prompts_file_lineedit)
        prompts_layout.addWidget(prompts_browse)

        layout.addLayout(tasks_layout)
        layout.addLayout(summary_layout)
        layout.addLayout(notes_layout)
        layout.addLayout(prompts_layout)

        button_layout = QtWidgets.QHBoxLayout()
        self.set_save_path_btn = QtWidgets.QPushButton("Set as Save Path")
        self.set_save_path_btn.clicked.connect(self.set_save_path)
        button_layout.addWidget(self.set_save_path_btn)
        layout.addLayout(button_layout)

        tasks_browse.clicked.connect(self.browse_tasks_file)
        summary_browse.clicked.connect(self.browse_summary_file)
        notes_browse.clicked.connect(self.browse_notes_file)
        prompts_browse.clicked.connect(self.browse_prompts_file)

    def get_default_tasks_file(self):
        scene_path = cmds.file(query=True, sceneName=True)
        if not scene_path or scene_path == "":
            return os.path.join(os.path.expanduser("~"), "jiffypomo_tasks.json")
        scene_dir = os.path.dirname(scene_path)
        shot_folder = os.path.join(scene_dir, "jiffyShotData")
        return os.path.join(shot_folder, "jiffypomo_tasks.json")

    def get_default_summary_file(self):
        scene_path = cmds.file(query=True, sceneName=True)
        if not scene_path or scene_path == "":
            return os.path.join(os.path.expanduser("~"), "jiffypomo_summary.json")
        scene_dir = os.path.dirname(scene_path)
        shot_folder = os.path.join(scene_dir, "jiffyShotData")
        return os.path.join(shot_folder, "jiffypomo_summary.json")

    def get_default_notes_file(self):
        return DEFAULT_NOTES_FILE

    def get_default_prompts_file(self):
        return DEFAULT_PROMPTS_FILE

    def browse_tasks_file(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select Tasks File",
            self.load_tasks_file,
            "JSON Files (*.json)"
        )
        if file_path and os.path.exists(file_path):
            self.tasks_file_lineedit.setText(file_path)
            self.load_tasks_file = file_path
            if self.parent():
                self.parent().load_state_auto()

    def browse_summary_file(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select Summary File",
            self.load_summary_file,
            "JSON Files (*.json)"
        )
        if file_path and os.path.exists(file_path):
            self.summary_file_lineedit.setText(file_path)
            self.load_summary_file = file_path
            if self.parent():
                self.parent().summary_tab.load_summary()

    def browse_notes_file(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select Notes File",
            self.load_notes_file,
            "JSON Files (*.json)"
        )
        if file_path and os.path.exists(file_path):
            self.notes_file_lineedit.setText(file_path)
            self.load_notes_file = file_path
            if self.parent():
                self.parent().notepad_tab.load_notes()

    def browse_prompts_file(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select Prompts File",
            self.load_prompts_file,
            "JSON Files (*.json)"
        )
        if file_path and os.path.exists(file_path):
            self.prompts_file_lineedit.setText(file_path)
            self.load_prompts_file = file_path
            if self.parent():
                self.parent().prompts_tab.load_prompts()

    def set_save_path(self):
        self.default_tasks_file = self.load_tasks_file
        self.default_summary_file = self.load_summary_file
        self.default_notes_file = self.load_notes_file
        self.default_prompts_file = self.load_prompts_file
        QtWidgets.QMessageBox.information(
            self,
            "Save Path Updated",
            "Save path set to selected load paths."
        )

    def get_tasks_file_path(self):
        return self.default_tasks_file

    def get_summary_file_path(self):
        return self.default_summary_file

    def get_notes_file_path(self):
        return self.default_notes_file

    def get_prompts_file_path(self):
        return self.default_prompts_file

    def get_load_tasks_file_path(self):
        return self.load_tasks_file

    def get_load_summary_file_path(self):
        return self.load_summary_file

    def get_load_notes_file_path(self):
        return self.load_notes_file

    def get_load_prompts_file_path(self):
        return self.load_prompts_file


class JiffyPomo(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(JiffyPomo, self).__init__(parent)
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
