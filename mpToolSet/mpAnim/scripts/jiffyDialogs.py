# JiffyPomo popup dialogs — reward and notification toasts

from PySide6 import QtWidgets, QtGui, QtCore
import random
import logging

logger = logging.getLogger(__name__)


class RewardDialog(QtWidgets.QDialog):
    def __init__(self, message, parent=None):
        super(RewardDialog, self).__init__(parent)
        self.setWindowTitle("Great Job!")
        self.setWindowFlags(QtCore.Qt.Dialog | QtCore.Qt.WindowStaysOnTopHint)
        self.setMinimumWidth(320)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(14)

        label = QtWidgets.QLabel(message)
        label.setWordWrap(True)
        font = QtGui.QFont()
        font.setPointSize(14)
        font.setBold(True)
        label.setFont(font)
        label.setAlignment(QtCore.Qt.AlignCenter)

        bright_colors = [
            "#4caf50", "#e0a030", "#4D90D4", "#9575cd",
            "#e05050", "#26a69a", "#ef6c00", "#ec407a",
        ]
        label.setStyleSheet(f"color: {random.choice(bright_colors)};")
        layout.addWidget(label)

        btn = QtWidgets.QPushButton("Got it!")
        btn.setMinimumHeight(28)
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)


class NotificationDialog(QtWidgets.QDialog):
    def __init__(self, message, parent=None):
        super().__init__(parent)
        logger.debug(f"Showing notification: {message}")
        self.setWindowTitle("Notification")
        self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
        self.setMinimumWidth(320)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(14)

        label = QtWidgets.QLabel(message)
        label.setWordWrap(True)
        label.setFont(QtGui.QFont("", 14, QtGui.QFont.Bold))
        label.setAlignment(QtCore.Qt.AlignCenter)

        colors = [
            "#4caf50", "#e0a030", "#4D90D4", "#9575cd",
            "#e05050", "#26a69a", "#ef6c00", "#ec407a",
        ]
        color = random.choice(colors)
        label.setStyleSheet(f"color: {color};")
        layout.addWidget(label)

        btn = QtWidgets.QPushButton("Got it!")
        btn.setMinimumHeight(28)
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)
