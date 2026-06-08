# JiffyPomo Note Pad tab — simple persisted scratchpad

from PySide6 import QtWidgets, QtCore
import time
import json
import os
import logging

from jiffyUtils import DEFAULT_NOTES_FILE

logger = logging.getLogger(__name__)


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
