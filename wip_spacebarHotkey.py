import maya.mel as mel
import maya.cmds as cmds
from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import Qt

_APP_ATTR = '_wip_spacebarHotkey_filter'
HOLD_MS = 400


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
        mel.eval('hotBox')

    def eventFilter(self, obj, event):
        t = event.type()
        if t not in (QtCore.QEvent.Type.KeyPress, QtCore.QEvent.Type.KeyRelease):
            return False
        if event.key() != Qt.Key.Key_Space:
            return False

        # Detect text-input widgets by isinstance first, then inputMethodQuery fallback.
        # We consume the event here and inject a space directly so Maya's C++ playback
        # handler never sees it.
        focus_widget = QtWidgets.QApplication.focusWidget()
        if focus_widget is not None:
            is_text = isinstance(focus_widget, (QtWidgets.QTextEdit,
                                                QtWidgets.QPlainTextEdit,
                                                QtWidgets.QLineEdit))
            if not is_text:
                try:
                    is_text = bool(focus_widget.inputMethodQuery(
                        Qt.InputMethodQuery.ImEnabled))
                except Exception:
                    pass
            if is_text:
                if t == QtCore.QEvent.Type.KeyPress and not event.isAutoRepeat():
                    if hasattr(focus_widget, 'insertPlainText'):
                        focus_widget.insertPlainText(' ')
                    elif hasattr(focus_widget, 'insert'):
                        focus_widget.insert(' ')
                return True  # consume — blocks Maya's C++ layer

        try:
            panel = cmds.getPanel(withFocus=True)
            if not panel or cmds.getPanel(typeOf=panel) != 'modelPanel':
                return False
        except Exception:
            return False

        if event.isAutoRepeat():
            return True

        if t == QtCore.QEvent.Type.KeyPress and not self._pressed:
            self._pressed = True
            self._held    = False
            self._timer.start()
            return True

        if t == QtCore.QEvent.Type.KeyRelease and self._pressed:
            self._pressed = False
            if self._held:
                self._held = False
                mel.eval('hotBox -release')
            else:
                self._timer.stop()
                mel.eval('togglePlayback')
            return True

        return False


def bind_space():
    reset_space()
    cmds.hotkey(keyShortcut='space', name='', releaseName='')
    app = QtWidgets.QApplication.instance()
    f = SpacePlayFilter(app)
    setattr(app, _APP_ATTR, f)
    app.installEventFilter(f)
    cmds.inViewMessage(amg='Space: <hl>tap</hl> = play  |  <hl>hold</hl> = hotbox', pos='midCenter', fade=True)
    print('wip_spacebarHotkey: filter installed.')


def reset_space():
    app = QtWidgets.QApplication.instance()
    old = getattr(app, _APP_ATTR, None)
    if old is not None:
        app.removeEventFilter(old)
        setattr(app, _APP_ATTR, None)
    cmds.hotkey(keyShortcut='space', name='', releaseName='')
    print('wip_spacebarHotkey: filter removed.')


bind_space()
