from PySide6 import QtWidgets, QtCore
from shiboken6 import wrapInstance
from maya import OpenMayaUI as omui
import maya.cmds as cmds

import follicleRig_api as api


def _adj(hex_color, amt):
    h = hex_color.lstrip('#')
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    clamp = lambda v: max(0, min(255, v + amt))
    return '#{:02x}{:02x}{:02x}'.format(clamp(r), clamp(g), clamp(b))


def _btn(bg, fg='white'):
    return (
        'QPushButton {{ background-color:{bg}; color:{fg}; border:none; '
        'padding:3px 6px; font-size:11px; }}'
        'QPushButton:hover {{ background-color:{light}; }}'
        'QPushButton:pressed {{ background-color:{dark}; }}'
        'QPushButton:disabled {{ background-color:#333; color:#666; }}'
    ).format(bg=bg, fg=fg, light=_adj(bg, 25), dark=_adj(bg, -30))

WINDOW_NAME = 'follicleRigTool'
_win = None


def _maya_main_window():
    ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(ptr), QtWidgets.QWidget)


def show():
    global _win
    try:
        _win.close()
        _win.deleteLater()
    except Exception:
        pass
    _win = FollicleRigUI(_maya_main_window())
    _win.show()


def _addControllersFromSelection(setStatus):
    nodes = cmds.ls(selection=True) or []
    if not nodes:
        setStatus('Select follicles or their joints first', error=True)
        return
    try:
        results = api.addControllersForSelection(nodes)
    except api.FollicleRigError as err:
        setStatus(str(err), error=True)
        return
    except Exception as err:
        setStatus('Error: ' + str(err), error=True)
        return
    setStatus('Added controllers for %d follicle(s)' % len(results))


# ── tabs ──────────────────────────────────────────────────────────────────────

class _NurbsGridTab(QtWidgets.QWidget):
    def __init__(self, setStatus, parent=None):
        super().__init__(parent)
        self._setStatus = setStatus

        layout = QtWidgets.QVBoxLayout(self)

        form = QtWidgets.QFormLayout()
        self.uSpin = QtWidgets.QSpinBox()
        self.uSpin.setRange(1, 100)
        self.uSpin.setValue(5)
        self.vSpin = QtWidgets.QSpinBox()
        self.vSpin.setRange(1, 100)
        self.vSpin.setValue(5)
        form.addRow('U Count', self.uSpin)
        form.addRow('V Count', self.vSpin)
        layout.addLayout(form)

        layout.addSpacing(8)
        createBtn = QtWidgets.QPushButton('Create Follicles')
        createBtn.setStyleSheet(_btn('#2A5E6B'))
        createBtn.clicked.connect(self._onCreate)
        layout.addWidget(createBtn)

        ctrlBtn = QtWidgets.QPushButton('Add Controllers')
        ctrlBtn.setStyleSheet(_btn('#6B4A2A'))
        ctrlBtn.clicked.connect(lambda: _addControllersFromSelection(self._setStatus))
        layout.addWidget(ctrlBtn)

        layout.addStretch()

    def _onCreate(self):
        sel = cmds.ls(selection=True) or []
        if not sel:
            self._setStatus('Select a NURBS surface first', error=True)
            return
        try:
            group, pairs = api.createNurbsGridFollicles(sel[0], self.uSpin.value(), self.vSpin.value())
        except api.FollicleRigError as err:
            self._setStatus(str(err), error=True)
            return
        except Exception as err:
            self._setStatus('Error: ' + str(err), error=True)
            return
        self._setStatus('Created %d follicle(s) in %s' % (len(pairs), group))


class _PolyVerticesTab(QtWidgets.QWidget):
    def __init__(self, setStatus, parent=None):
        super().__init__(parent)
        self._setStatus = setStatus

        layout = QtWidgets.QVBoxLayout(self)

        note = QtWidgets.QLabel(
            'Select a polygon mesh and click Enter Vertex Mode,\n'
            'then pick vertices in the order you want follicles created.')
        note.setWordWrap(True)
        layout.addWidget(note)

        layout.addSpacing(8)
        vertBtn = QtWidgets.QPushButton('Enter Vertex Mode')
        vertBtn.setStyleSheet(_btn('#3D5A3A'))
        vertBtn.clicked.connect(self._onEnterVertexMode)
        layout.addWidget(vertBtn)

        layout.addSpacing(8)
        createBtn = QtWidgets.QPushButton('Create Follicles')
        createBtn.setStyleSheet(_btn('#2A5E6B'))
        createBtn.clicked.connect(self._onCreate)
        layout.addWidget(createBtn)

        ctrlBtn = QtWidgets.QPushButton('Add Controllers')
        ctrlBtn.setStyleSheet(_btn('#6B4A2A'))
        ctrlBtn.clicked.connect(lambda: _addControllersFromSelection(self._setStatus))
        layout.addWidget(ctrlBtn)

        layout.addStretch()

    def _onEnterVertexMode(self):
        sel = cmds.ls(selection=True) or []
        if not sel:
            self._setStatus('Select a polygon mesh first', error=True)
            return
        try:
            api.enterVertexMode(sel[0])
        except api.FollicleRigError as err:
            self._setStatus(str(err), error=True)
            return
        self._setStatus('Vertex mode active — pick vertices in order')

    def _onCreate(self):
        vertices = [v for v in (cmds.ls(selection=True, flatten=True) or []) if '.vtx[' in v]
        if not vertices:
            self._setStatus('Select polygon vertices first', error=True)
            return
        try:
            group, pairs = api.createPolyVertexFollicles(vertices)
        except api.FollicleRigError as err:
            self._setStatus(str(err), error=True)
            return
        except Exception as err:
            self._setStatus('Error: ' + str(err), error=True)
            return
        self._setStatus('Created %d follicle(s) in %s' % (len(pairs), group))


class _CurveOnSurfaceTab(QtWidgets.QWidget):
    def __init__(self, setStatus, parent=None):
        super().__init__(parent)
        self._setStatus = setStatus
        self._original = None
        self._duplicate = None
        self._preExistingCurves = None

        layout = QtWidgets.QVBoxLayout(self)

        note = QtWidgets.QLabel(
            'Select a surface and click Create Curve. Draw your path\n'
            'with the EP curve tool, then click Create Follicles.')
        note.setWordWrap(True)
        layout.addWidget(note)

        layout.addSpacing(8)
        self._createCurveBtn = QtWidgets.QPushButton('Create Curve')
        self._createCurveBtn.setStyleSheet(_btn('#7A5C2A'))
        self._createCurveBtn.clicked.connect(self._onCreateCurve)
        layout.addWidget(self._createCurveBtn)

        self._stateLabel = QtWidgets.QLabel('')
        self._stateLabel.setWordWrap(True)
        self._stateLabel.setStyleSheet('color: #aaaaaa; font-style: italic;')
        layout.addWidget(self._stateLabel)

        layout.addSpacing(8)
        self._createFolliclesBtn = QtWidgets.QPushButton('Create Follicles')
        self._createFolliclesBtn.setStyleSheet(_btn('#2A5E6B'))
        self._createFolliclesBtn.clicked.connect(self._onCreate)
        self._createFolliclesBtn.setEnabled(False)
        layout.addWidget(self._createFolliclesBtn)

        ctrlBtn = QtWidgets.QPushButton('Add Controllers')
        ctrlBtn.setStyleSheet(_btn('#6B4A2A'))
        ctrlBtn.clicked.connect(lambda: _addControllersFromSelection(self._setStatus))
        layout.addWidget(ctrlBtn)

        layout.addStretch()

    def _onCreateCurve(self):
        # Clean up any previous session
        if self._duplicate is not None:
            try:
                if cmds.objExists(self._duplicate):
                    cmds.delete(self._duplicate)
                if self._original and cmds.objExists(self._original):
                    cmds.showHidden(self._original)
            except Exception:
                pass
        self._original = self._duplicate = self._preExistingCurves = None
        self._createFolliclesBtn.setEnabled(False)
        self._stateLabel.setText('')

        sel = cmds.ls(selection=True) or []
        if not sel:
            self._setStatus('Select a surface first', error=True)
            return
        try:
            original, duplicate, preExisting = api.setupCurveOnSurface(sel[0])
        except api.FollicleRigError as err:
            self._setStatus(str(err), error=True)
            return
        except Exception as err:
            self._setStatus('Error: ' + str(err), error=True)
            return

        self._original = original
        self._duplicate = duplicate
        self._preExistingCurves = preExisting
        self._createFolliclesBtn.setEnabled(True)

        if duplicate is not None:
            self._stateLabel.setText('Drawing on duplicate of: ' + original)
        else:
            self._stateLabel.setText('Drawing on: ' + original)
        self._setStatus('Surface ready — activate the EP Curve Tool, draw your path, then click Create Follicles')

    def _onCreate(self):
        if self._original is None:
            self._setStatus('Click Create Curve first', error=True)
            return
        try:
            group, pairs = api.createFolliclesFromCurveSetup(
                self._original, self._duplicate, self._preExistingCurves)
        except api.FollicleRigError as err:
            self._setStatus(str(err), error=True)
            return
        except Exception as err:
            self._setStatus('Error: ' + str(err), error=True)
            return

        self._original = self._duplicate = self._preExistingCurves = None
        self._createFolliclesBtn.setEnabled(False)
        self._stateLabel.setText('')
        self._setStatus('Created %d follicle(s) in %s' % (len(pairs), group))


# ── main window ───────────────────────────────────────────────────────────────

class FollicleRigUI(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName(WINDOW_NAME)
        self.setWindowTitle('Follicle Rig Tools')
        self.setWindowFlags(QtCore.Qt.Window)
        self.setMinimumWidth(360)

        layout = QtWidgets.QVBoxLayout(self)
        tabs = QtWidgets.QTabWidget()
        layout.addWidget(tabs)

        tabs.addTab(_NurbsGridTab(self._setStatus), 'NURBS Grid')
        tabs.addTab(_PolyVerticesTab(self._setStatus), 'Poly Vertices')
        tabs.addTab(_CurveOnSurfaceTab(self._setStatus), 'Curve on Surface')

        self.status = QtWidgets.QLabel('')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

    def _setStatus(self, message, error=False):
        self.status.setText(message)
        self.status.setStyleSheet('color: #d65f5f;' if error else 'color: #6fbf73;')
