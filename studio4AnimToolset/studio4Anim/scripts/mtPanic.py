import maya.cmds as cmds


def show_panic():
    saying = "There's no such thing as an art emergency."
    cmds.confirmDialog(
        title='Panic Button',
        message=saying,
        button=['Ok, fine.'],
        defaultButton='Ok, fine.'
    )
