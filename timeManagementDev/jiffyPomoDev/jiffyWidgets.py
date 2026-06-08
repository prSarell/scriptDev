# JiffyPomo shared widgets used across multiple tabs

from PySide6 import QtWidgets, QtGui, QtCore
import random
import logging

logger = logging.getLogger(__name__)


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

            if important and (not regular or random.random() < 0.6):
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
