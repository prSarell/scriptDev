import random

import maya.cmds as cmds
from maya import OpenMayaUI as omui

try:
    from PySide6 import QtWidgets, QtGui, QtCore
    from shiboken6 import wrapInstance
except ImportError:
    from PySide2 import QtWidgets, QtGui, QtCore
    from shiboken2 import wrapInstance

TIPS = [
    "Perfection is the death of progress!",
    "Defining a pose in your pose layer that shows weight, character and the performance is the most important part of animating your shot.",
    "A breakdown always sits exactly halfway between two poses — an equal number of frames on either side.",
    "50% of the weight is in the hands.",
    "Look for the points of contact to define your poses.",
    "If your motion looks floaty that means the performance is unclear.",
    "Inertia is the tendency of an object to resist changes in its motion — things at rest want to stay at rest, things in motion want to keep moving.",
    "Gravity + Mass = Weight",
    "The knee should almost always align over the top of the foot — always check your knee position.",
    "Think of the arm as three points — shoulder, elbow, wrist. The elbow should never rise above the shoulder-to-wrist line, and never collapse to the inside of it.",
    "Hands, body, and face each require equal attention.",
    "Your blocking pass is not complete without working contacts.",
    "A good blocking has weight, timing, working contacts, strong poses, holds, good body mechanics and clear performance.",
    "Ask yourself 'How does the motion feel?'",
    "CHECK IT IN THE CUT!!!",
    "Always check your motion in world space and screen space.",
    "Arms are not passengers in a walk cycle. Their weight and kinetic energy drives the walk.",
    "Stride length, speed, distance and timing are the foundations of a good walk.",
    "Favoring = posing an in-between to resemble the preceding or upcoming pose. It doesn't change the timing of the breakdown — it changes the spacing around the breakdown.",
    "Pose and extreme mean the same thing.",
    "Antic = short-hand for anticipation.",
    "Plussing = improving.",
    "A good pose shows character, weight, story and action.",
    "Work self. Home self.",
    "Never apologize for your work.",
    "Respond to critical feedback with 'I see what you're saying,' then see where the conversation leads.",
    "If feedback is unclear, ask for clarification.",
    "Time management is as important as ability.",
    "Authenticity and clarity are the two most important things in any creative work.",
    "Good contacts are the most important part of posing.",
    "Consider the possibility of multiple base poses for complex shots.",
]

BRIGHT_COLORS = [
    "#4caf50", "#e0a030", "#4D90D4", "#9575cd",
    "#e05050", "#26a69a", "#ef6c00", "#ec407a",
]


def _maya_main_window():
    return wrapInstance(int(omui.MQtUtil.mainWindow()), QtWidgets.QWidget)


class TipDialog(QtWidgets.QDialog):
    def __init__(self, message, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Learn Me Something")
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
        label.setStyleSheet(f"color: {random.choice(BRIGHT_COLORS)};")
        layout.addWidget(label)

        btn = QtWidgets.QPushButton("Got it!")
        btn.setMinimumHeight(28)
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)


def show_tip():
    tip = random.choice(TIPS)
    dlg = TipDialog(tip, parent=_maya_main_window())
    dlg.exec_()
