# JiffyPomo Pomo tab — countdown timer, completion handling and rewards

from PySide6 import QtWidgets, QtGui, QtCore
import time
import random
import maya.cmds as cmds

from jiffyWidgets import PromptsDisplay, TimerCircleWidget
from jiffyDialogs import RewardDialog, NotificationDialog


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
