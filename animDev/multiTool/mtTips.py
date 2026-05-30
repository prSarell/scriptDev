import random
import maya.cmds as cmds

TIPS = [
    "Perfection is the death of progress!",
    "Defining a pose in your pose layer that shows weight, character and the performance is the most important part of animating your shot.",
    "A breakdown always sits exactly halfway between two poses — an equal number of frames on either side.",
]


def show_tip():
    tip = random.choice(TIPS)
    cmds.confirmDialog(
        title='Learn Me Something',
        message=tip,
        button=['Got it!'],
        defaultButton='Got it!'
    )
