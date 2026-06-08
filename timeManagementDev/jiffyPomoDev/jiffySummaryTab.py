# JiffyPomo Summary tab — review and manually edit completed-shot history

from PySide6 import QtWidgets
import json
import os
import time


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
