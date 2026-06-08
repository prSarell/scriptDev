# JiffyPomo Prompts tab — editable list of rotating motivational prompts

from PySide6 import QtWidgets, QtCore
import json
import os
import logging

from jiffyUtils import DEFAULT_PROMPTS_FILE
from jiffyWidgets import PromptWidget

logger = logging.getLogger(__name__)


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
        self.cached_prompts = current_ui_data[:]

        logger.debug(f"Saving {len(current_ui_data)} prompts to {self.prompts_file}")
        try:
            os.makedirs(os.path.dirname(self.prompts_file), exist_ok=True)
            with open(self.prompts_file + ".tmp", "w") as f:
                json.dump(
                    {
                        "prompts": current_ui_data,
                        "refresh_interval": self.get_refresh_interval()
                    },
                    f,
                    indent=4
                )
            os.replace(self.prompts_file + ".tmp", self.prompts_file)
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
