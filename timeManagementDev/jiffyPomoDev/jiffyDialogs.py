# JiffyPomo popup dialogs — reward and notification toasts

from PySide6 import QtWidgets, QtGui, QtCore
import random
import logging

logger = logging.getLogger(__name__)


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
