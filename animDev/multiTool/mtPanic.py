import random
import maya.cmds as cmds

SAYINGS = [
    "Don't panic.",
    "There's no such thing as an art emergency.",
    "Go home and sleep.",
    "Move on to something else.",
    "Save your file and walk away.",
    "It's not rocket surgery or brain science.",
    "The only thing you learn from success is what you already know.",
]


def show_panic():
    saying = random.choice(SAYINGS)
    cmds.confirmDialog(
        title='Panic Button',
        message=saying,
        button=['Ok, fine.'],
        defaultButton='Ok, fine.'
    )
