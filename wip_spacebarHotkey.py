import maya.mel as mel
import maya.cmds as cmds
from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import Qt

_active_filter = None
HOLD_MS = 400  # ms before a press is treated as a hold (matches Maya's default hotbox delay)


class SpacePlayFilter(QtCore.QObject):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pressed = False
        self._held    = False
        self._timer   = QtCore.QTimer()
        self._timer.setSingleShot(True)
        self._timer.setInterval(HOLD_MS)
        self._timer.timeout.connect(self._on_hold)

    def _on_hold(self):
        self._held = True
        mel.eval('hotBox')  # show hotbox after threshold

    def eventFilter(self, obj, event):
        t = event.type()
        if t not in (QtCore.QEvent.Type.KeyPress, QtCore.QEvent.Type.KeyRelease):
            return False
        if event.key() != Qt.Key.Key_Space:
            return False

        if event.isAutoRepeat():
            return True  # consume auto-repeat — no rapid toggling or hotbox re-triggers

        if t == QtCore.QEvent.Type.KeyPress and not self._pressed:
            self._pressed = True
            self._held    = False
            self._timer.start()
            return True  # consume — prevents hotbox timer starting in Maya

        if t == QtCore.QEvent.Type.KeyRelease and self._pressed:
            self._pressed = False
            if self._held:
                self._held = False
                mel.eval('hotBox -release')  # dismiss hotbox on release
            else:
                self._timer.stop()
                mel.eval('togglePlayback')   # tap — play/stop
            return True

        return False


def bind_space():
    global _active_filter
    reset_space()
    app = QtWidgets.QApplication.instance()
    _active_filter = SpacePlayFilter(app)
    app.installEventFilter(_active_filter)
    cmds.inViewMessage(amg='Space: <hl>tap</hl> = play  |  <hl>hold</hl> = hotbox', pos='midCenter', fade=True)
    print('wip_spacebarHotkey: filter installed.')


def reset_space():
    global _active_filter
    if _active_filter is not None:
        QtWidgets.QApplication.instance().removeEventFilter(_active_filter)
        _active_filter = None
    cmds.inViewMessage(amg='Space <hl>reset</hl> to Maya defaults.', pos='midCenter', fade=True)
    print('wip_spacebarHotkey: filter removed.')


bind_space()
