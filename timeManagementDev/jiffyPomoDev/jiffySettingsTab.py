# JiffyPomo Settings tab — file path configuration for tasks/summary/notes/prompts

from PySide6 import QtWidgets
import os
import maya.cmds as cmds

from jiffyUtils import DEFAULT_NOTES_FILE, DEFAULT_PROMPTS_FILE


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
