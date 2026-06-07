from PySide6 import QtWidgets, QtCore
from shiboken6 import wrapInstance
from maya import OpenMayaUI as omui
import maya.cmds as cmds

import follicleRig_api as api

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


class _NodeField(QtWidgets.QWidget):
    '''Label + line edit + "<<" button that loads the first selected node.'''

    def __init__(self, label, parent=None):
        super(_NodeField, self).__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QtWidgets.QLabel(label))
        self.field = QtWidgets.QLineEdit()
        layout.addWidget(self.field)
        loadBtn = QtWidgets.QPushButton('<<')
        loadBtn.setFixedWidth(28)
        loadBtn.setToolTip('Load first selected node')
        loadBtn.clicked.connect(self._loadSelected)
        layout.addWidget(loadBtn)

    def _loadSelected(self):
        sel = cmds.ls(selection=True) or []
        if sel:
            self.field.setText(sel[0])

    def text(self):
        return self.field.text().strip()


class FollicleRigUI(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(FollicleRigUI, self).__init__(parent)
        self.setObjectName(WINDOW_NAME)
        self.setWindowTitle('Follicle Rig Tools')
        self.setWindowFlags(QtCore.Qt.Window)
        self.setMinimumWidth(360)

        layout = QtWidgets.QVBoxLayout(self)
        tabs = QtWidgets.QTabWidget()
        layout.addWidget(tabs)
        tabs.addTab(self._buildCreateTab(), 'Create Follicles')
        tabs.addTab(self._buildControlsTab(), 'Animation Controls')

        self.status = QtWidgets.QLabel('')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

    # ── Create Follicles tab ──────────────────────────────────────────────

    def _buildCreateTab(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)

        self.modeCombo = QtWidgets.QComboBox()
        self.modeCombo.addItems(['NURBS Grid', 'Polygon Vertices', 'Curve on Surface'])
        layout.addWidget(self.modeCombo)

        self.modeStack = QtWidgets.QStackedWidget()
        self.modeStack.addWidget(self._buildNurbsGridPage())
        self.modeStack.addWidget(self._buildPolyVertexPage())
        self.modeStack.addWidget(self._buildCurvePage())
        layout.addWidget(self.modeStack)
        self.modeCombo.currentIndexChanged.connect(self.modeStack.setCurrentIndex)

        layout.addSpacing(8)
        nameLayout = QtWidgets.QHBoxLayout()
        nameLayout.addWidget(QtWidgets.QLabel('Custom Name (optional)'))
        self.createNameField = QtWidgets.QLineEdit()
        nameLayout.addWidget(self.createNameField)
        layout.addLayout(nameLayout)

        createBtn = QtWidgets.QPushButton('Create Follicles')
        createBtn.clicked.connect(self._onCreateFollicles)
        layout.addWidget(createBtn)
        layout.addStretch()
        return page

    def _buildNurbsGridPage(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(page)
        self.gridSurfaceField = _NodeField('Surface')
        layout.addRow(self.gridSurfaceField)
        self.uCountSpin = QtWidgets.QSpinBox()
        self.uCountSpin.setRange(1, 100)
        self.uCountSpin.setValue(5)
        layout.addRow('U Count', self.uCountSpin)
        self.vCountSpin = QtWidgets.QSpinBox()
        self.vCountSpin.setRange(1, 100)
        self.vCountSpin.setValue(5)
        layout.addRow('V Count', self.vCountSpin)
        return page

    def _buildPolyVertexPage(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        note = QtWidgets.QLabel(
            'Select polygon vertices in the viewport, in the order\n'
            'you want follicles created, then click Create Follicles.')
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch()
        return page

    def _buildCurvePage(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(page)
        self.curveField = _NodeField('Curve')
        layout.addRow(self.curveField)
        self.curveSurfaceField = _NodeField('Surface')
        layout.addRow(self.curveSurfaceField)
        self.toleranceSpin = QtWidgets.QDoubleSpinBox()
        self.toleranceSpin.setRange(0.0001, 10.0)
        self.toleranceSpin.setDecimals(4)
        self.toleranceSpin.setValue(0.01)
        layout.addRow('Tolerance', self.toleranceSpin)
        return page

    def _onCreateFollicles(self):
        customName = self.createNameField.text().strip() or None
        mode = self.modeCombo.currentIndex()
        try:
            if mode == 0:
                surface = self.gridSurfaceField.text()
                if not surface:
                    raise api.FollicleRigError('Load a NURBS surface first')
                pairs = api.createNurbsGridFollicles(
                    surface, self.uCountSpin.value(), self.vCountSpin.value(), customName=customName)
            elif mode == 1:
                vertices = cmds.ls(selection=True, flatten=True) or []
                vertices = [v for v in vertices if '.vtx[' in v]
                pairs = api.createPolyVertexFollicles(vertices, customName=customName)
            else:
                curve = self.curveField.text()
                surface = self.curveSurfaceField.text()
                if not curve or not surface:
                    raise api.FollicleRigError('Load both a curve and a surface first')
                pairs = api.createCurveOnSurfaceFollicles(
                    curve, surface, customName=customName, tolerance=self.toleranceSpin.value())
        except api.FollicleRigError as err:
            self._setStatus(str(err), error=True)
            return
        except Exception as err:
            self._setStatus('Error: ' + str(err), error=True)
            return

        self._setStatus('Created %d follicle/joint pair(s).' % len(pairs))

    # ── Animation Controls tab ────────────────────────────────────────────

    def _buildControlsTab(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.addWidget(self._buildUVControlGroup())
        layout.addWidget(self._buildJointControlGroup())
        layout.addStretch()
        return page

    def _buildUVControlGroup(self):
        group = QtWidgets.QGroupBox('UV Driver Control')
        layout = QtWidgets.QFormLayout(group)

        self.uvFollicleField = _NodeField('Follicle')
        layout.addRow(self.uvFollicleField)
        self.uvSurfaceField = _NodeField('Surface')
        layout.addRow(self.uvSurfaceField)

        self.sensitivitySpin = QtWidgets.QDoubleSpinBox()
        self.sensitivitySpin.setRange(0.01, 100.0)
        self.sensitivitySpin.setValue(1.0)
        layout.addRow('Sensitivity', self.sensitivitySpin)

        self.uvArrowCheck = QtWidgets.QCheckBox('Use arrow control shape')
        self.uvArrowCheck.setChecked(True)
        layout.addRow(self.uvArrowCheck)

        self.uvNameField = QtWidgets.QLineEdit()
        layout.addRow('Custom Name (optional)', self.uvNameField)

        addBtn = QtWidgets.QPushButton('Add UV Driver Control')
        addBtn.clicked.connect(self._onAddUVControl)
        layout.addRow(addBtn)
        return group

    def _buildJointControlGroup(self):
        group = QtWidgets.QGroupBox('Joint Driver Control')
        layout = QtWidgets.QFormLayout(group)

        self.jointFollicleField = _NodeField('Follicle')
        layout.addRow(self.jointFollicleField)
        self.jointField = _NodeField('Joint')
        layout.addRow(self.jointField)

        self.jointStopSignCheck = QtWidgets.QCheckBox('Use stop-sign control shape')
        self.jointStopSignCheck.setChecked(True)
        layout.addRow(self.jointStopSignCheck)

        self.jointNameField = QtWidgets.QLineEdit()
        layout.addRow('Custom Name (optional)', self.jointNameField)

        addBtn = QtWidgets.QPushButton('Add Joint Driver Control')
        addBtn.clicked.connect(self._onAddJointControl)
        layout.addRow(addBtn)
        return group

    def _onAddUVControl(self):
        follicle = self.uvFollicleField.text()
        surface = self.uvSurfaceField.text()
        if not follicle or not surface:
            self._setStatus('Load both a follicle and a surface first', error=True)
            return
        customName = self.uvNameField.text().strip() or None
        try:
            ctrl = api.createUVDriverControl(
                follicle, surface, customName=customName,
                sensitivity=self.sensitivitySpin.value(), useArrowShape=self.uvArrowCheck.isChecked())
        except api.FollicleRigError as err:
            self._setStatus(str(err), error=True)
            return
        except Exception as err:
            self._setStatus('Error: ' + str(err), error=True)
            return
        self._setStatus('Created UV driver control: ' + ctrl)

    def _onAddJointControl(self):
        follicle = self.jointFollicleField.text()
        joint = self.jointField.text()
        if not follicle or not joint:
            self._setStatus('Load both a follicle and a joint first', error=True)
            return
        customName = self.jointNameField.text().strip() or None
        try:
            ctrl = api.createJointDriverControl(
                follicle, joint, customName=customName,
                useStopSignShape=self.jointStopSignCheck.isChecked())
        except api.FollicleRigError as err:
            self._setStatus(str(err), error=True)
            return
        except Exception as err:
            self._setStatus('Error: ' + str(err), error=True)
            return
        self._setStatus('Created joint driver control: ' + ctrl)

    # ── status ────────────────────────────────────────────────────────────

    def _setStatus(self, message, error=False):
        self.status.setText(message)
        self.status.setStyleSheet('color: #d65f5f;' if error else 'color: #6fbf73;')
