import random
import maya.cmds as cmds

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
]


def show_tip():
    tip = random.choice(TIPS)
    cmds.confirmDialog(
        title='Learn Me Something',
        message=tip,
        button=['Got it!'],
        defaultButton='Got it!'
    )
