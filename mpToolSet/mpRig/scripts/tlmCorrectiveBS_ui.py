import maya.cmds as cmds

try:
    from PySide6 import QtWidgets, QtCore, QtGui
    from shiboken6 import wrapInstance
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui
    from shiboken2 import wrapInstance

import maya.OpenMayaUI as omui
import tlmCorrectiveBS_api as api


def getMayaMainWindow():
    ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(ptr), QtWidgets.QWidget)


def show():
    global _tlmCorrectiveBSWindow
    try:
        _tlmCorrectiveBSWindow.close()
        _tlmCorrectiveBSWindow.deleteLater()
    except Exception:
        pass
    _tlmCorrectiveBSWindow = CorrectiveBSWindow(parent=getMayaMainWindow())
    _tlmCorrectiveBSWindow.show()


# ── main window ───────────────────────────────────────────────────────────────

class CorrectiveBSWindow(QtWidgets.QWidget):

    DARK   = '#1e1e1e'
    MID    = '#2a2a2a'
    LIGHT  = '#3a3a3a'
    BORDER = '#4a4a4a'
    TEXT   = '#cccccc'
    DIM    = '#777777'
    ACCENT = '#7a6fa0'
    GREEN  = '#4a7a4a'
    RED    = '#7a3a3a'

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Corrective Blendshape Tool')
        self.setWindowFlags(QtCore.Qt.Tool)
        self.setMinimumWidth(380)
        self.setStyleSheet(self._stylesheet())

        self._dup_a               = None
        self._dup_b               = None
        self._bs_states           = []
        self._bs_node             = None
        self._target_index        = None
        self._custom_driver_attr  = None
        self._custom_driver_value = None

        self._buildUI()
        self._refreshTargetList()

    # ── UI construction ───────────────────────────────────────────────────────

    def _buildUI(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        root.addWidget(self._headerLabel('CORRECTIVE BLENDSHAPE TOOL'))

        # ── Mesh ──
        root.addWidget(self._sectionLabel('MESH'))
        root.addWidget(self._guideLabel(
            'Select the mesh that needs a corrective shape. This is '
            'typically a body or face mesh that already has a skin '
            'cluster bound to the skeleton.'))
        mesh_row = QtWidgets.QHBoxLayout()
        self._meshField = QtWidgets.QLineEdit()
        self._meshField.setPlaceholderText('Select mesh and click  ←')
        self._meshField.setReadOnly(True)
        pickMesh = self._iconButton('nudgeDown.png', 'Load selected mesh')
        pickMesh.clicked.connect(self._loadMesh)
        mesh_row.addWidget(self._meshField)
        mesh_row.addWidget(pickMesh)
        root.addLayout(mesh_row)

        self._stackLabel = QtWidgets.QLabel('')
        self._stackLabel.setStyleSheet('color: %s; font-size: 10px;' % self.DIM)
        root.addWidget(self._stackLabel)

        root.addWidget(self._divider())

        # ── Driver mode ──
        root.addWidget(self._sectionLabel('DRIVER MODE'))
        root.addWidget(self._guideLabel(
            'Auto detects what is driving the current pose — active '
            'blendShapes or joint rotations. Use Custom to wire the '
            'corrective to a specific attribute instead.'))

        self._modeAuto   = QtWidgets.QRadioButton('Auto — BlendShapes')
        self._modeCustom = QtWidgets.QRadioButton('Custom Attribute')
        self._modeAuto.setChecked(True)
        mode_row = QtWidgets.QHBoxLayout()
        mode_row.addWidget(self._modeAuto)
        mode_row.addWidget(self._modeCustom)
        root.addLayout(mode_row)

        self._customDriverRow = QtWidgets.QWidget()
        custom_layout = QtWidgets.QHBoxLayout(self._customDriverRow)
        custom_layout.setContentsMargins(0, 0, 0, 0)
        self._customDriverField = QtWidgets.QLineEdit()
        self._customDriverField.setPlaceholderText('e.g.  upperArm_jnt.rotateZ  or  chest_ctrl.breathe')
        pickDriver = self._iconButton('nudgeDown.png', 'Load selected attribute from Channel Box')
        pickDriver.clicked.connect(self._loadCustomDriver)
        custom_layout.addWidget(self._customDriverField)
        custom_layout.addWidget(pickDriver)
        self._customDriverRow.setVisible(False)
        root.addWidget(self._customDriverRow)

        self._modeAuto.toggled.connect(
            lambda checked: self._customDriverRow.setVisible(not checked))

        root.addWidget(self._divider())

        # ── Step 1: Capture Pose ──
        root.addWidget(self._sectionLabel('STEP 1  —  CAPTURE POSE'))
        root.addWidget(self._guideLabel(
            'Put the rig into the problem pose, name your corrective '
            'target, then Capture. This duplicates the mesh at its '
            'current deformed state — sculpt the correction on the '
            'visible copy.'))

        name_row = QtWidgets.QHBoxLayout()
        name_row.addWidget(QtWidgets.QLabel('Target name:'))
        self._nameField = QtWidgets.QLineEdit()
        self._nameField.setPlaceholderText('e.g.  L_shoulder_fix  or  smile_deep')
        name_row.addWidget(self._nameField)
        root.addLayout(name_row)

        self._startBtn = QtWidgets.QPushButton('Capture Pose  —  Start Sculpting')
        self._startBtn.setToolTip(
            'Duplicates the mesh at its current deformed state.\n'
            'One copy is hidden as a pose reference. Sculpt the\n'
            'correction on the visible duplicate, then Bake.')
        self._startBtn.clicked.connect(self._onStart)
        root.addWidget(self._startBtn)

        self._captureStatus = QtWidgets.QLabel('No pose captured yet.')
        self._captureStatus.setStyleSheet('color: %s; font-size: 10px;' % self.DIM)
        self._captureStatus.setWordWrap(True)
        root.addWidget(self._captureStatus)

        root.addWidget(self._divider())

        # ── Step 2: Bake ──
        root.addWidget(self._sectionLabel('STEP 2  —  BAKE CORRECTION'))
        root.addWidget(self._guideLabel(
            'After sculpting, bake the correction. The tool inverts '
            'the skin deformation to extract a clean delta and wires '
            'the driver automatically so the shape activates at the '
            'right pose.'))

        self._bakeBtn = QtWidgets.QPushButton('Bake Corrective Target')
        self._bakeBtn.setToolTip(
            'Computes the corrective delta and adds the blendShape target.\n'
            'The rig must still be at the same pose as Step 1.\n'
            'SDK driver is wired automatically from the captured drivers.')
        self._bakeBtn.setStyleSheet(
            'QPushButton { background: %s; } '
            'QPushButton:hover { background: %s; }' % (self.GREEN, '#5a8a5a'))
        self._bakeBtn.clicked.connect(self._onBake)
        root.addWidget(self._bakeBtn)

        self._bakeStatus = QtWidgets.QLabel('')
        self._bakeStatus.setStyleSheet('color: %s; font-size: 10px;' % self.DIM)
        self._bakeStatus.setWordWrap(True)
        root.addWidget(self._bakeStatus)

        root.addWidget(self._divider())

        # ── Target list ──
        root.addWidget(self._sectionLabel('TARGETS ON MESH'))
        root.addWidget(self._guideLabel(
            'All corrective targets on this mesh. Select one to update '
            'its sculpt or delete it. Add Shape lets you bring in an '
            'external sculpted mesh as a new target.'))

        self._targetList = QtWidgets.QListWidget()
        self._targetList.setFixedHeight(100)
        self._targetList.setStyleSheet(
            'QListWidget { background: %s; border: 1px solid %s; }'
            'QListWidget::item:selected { background: %s; }' % (
                self.MID, self.BORDER, self.ACCENT))
        self._targetList.itemSelectionChanged.connect(self._onTargetSelected)
        root.addWidget(self._targetList)

        addShape = QtWidgets.QPushButton('Add Shape')
        addShape.setToolTip(
            'Select a mesh in the scene and click to add it as a\n'
            'new target. Driver is auto-detected from active\n'
            'blendShapes, joint rotations, or a custom attribute.')
        addShape.setStyleSheet(
            'QPushButton { background: %s; } '
            'QPushButton:hover { background: %s; }' % (self.GREEN, '#5a8a5a'))
        addShape.clicked.connect(self._onAddShape)
        root.addWidget(addShape)

        sculpt_row = QtWidgets.QHBoxLayout()
        sculpt_row.addWidget(QtWidgets.QLabel('Sculpt:'))
        self._sculptField = QtWidgets.QLineEdit()
        self._sculptField.setPlaceholderText('auto-detected or pick from scene')
        self._sculptField.setReadOnly(True)
        pickSculpt = self._iconButton('nudgeDown.png', 'Pick selected mesh as sculpt source')
        pickSculpt.clicked.connect(self._pickSculptMesh)
        sculpt_row.addWidget(self._sculptField)
        sculpt_row.addWidget(pickSculpt)
        root.addLayout(sculpt_row)

        poseRef_row = QtWidgets.QHBoxLayout()
        poseRef_row.addWidget(QtWidgets.QLabel('PoseRef:'))
        self._poseRefField = QtWidgets.QLineEdit()
        self._poseRefField.setPlaceholderText('auto-detected or pick from scene')
        self._poseRefField.setReadOnly(True)
        pickPoseRef = self._iconButton('nudgeDown.png', 'Pick selected mesh as pose reference')
        pickPoseRef.clicked.connect(self._pickPoseRefMesh)
        poseRef_row.addWidget(self._poseRefField)
        poseRef_row.addWidget(pickPoseRef)
        root.addLayout(poseRef_row)

        target_btn_row = QtWidgets.QHBoxLayout()
        self._updateBtn = QtWidgets.QPushButton('Update Target')
        self._updateBtn.setToolTip(
            'Re-bake the selected target from the sculpt mesh.\n'
            'Preserves existing SDK wiring.')
        self._updateBtn.clicked.connect(self._onUpdate)
        self._deleteBtn = QtWidgets.QPushButton('Delete Target')
        self._deleteBtn.setStyleSheet(
            'QPushButton { background: %s; } '
            'QPushButton:hover { background: %s; }' % (self.RED, '#8a4a4a'))
        self._deleteBtn.clicked.connect(self._onDelete)
        target_btn_row.addWidget(self._updateBtn)
        target_btn_row.addWidget(self._deleteBtn)
        root.addLayout(target_btn_row)

        root.addWidget(self._divider())

        # ── Log ──
        log_header = QtWidgets.QHBoxLayout()
        log_lbl = QtWidgets.QLabel('LOG')
        log_lbl.setStyleSheet(
            'color: %s; font-size: 10px; font-weight: bold; letter-spacing: 1px;' % self.DIM)
        clear_btn = QtWidgets.QPushButton('Clear')
        clear_btn.setFixedWidth(48)
        clear_btn.setStyleSheet(
            'QPushButton { background: %s; border: 1px solid %s; color: %s; '
            'padding: 2px 6px; font-size: 10px; }'
            'QPushButton:hover { background: %s; }' % (
                self.LIGHT, self.BORDER, self.DIM, self.BORDER))
        log_header.addWidget(log_lbl)
        log_header.addStretch()
        log_header.addWidget(clear_btn)
        root.addLayout(log_header)

        self._log = QtWidgets.QTextEdit()
        self._log.setReadOnly(True)
        self._log.setFixedHeight(100)
        self._log.setStyleSheet(
            'QTextEdit { background: #111111; border: 1px solid %s; '
            'color: #aaaaaa; font-size: 10px; font-family: Consolas, monospace; }' % self.BORDER)
        clear_btn.clicked.connect(self._log.clear)
        root.addWidget(self._log)

    # ── slot handlers ─────────────────────────────────────────────────────────

    def _loadMesh(self):
        sel = cmds.ls(sl=True, transforms=True)
        if not sel:
            self._warn('Select a mesh transform first.')
            return
        mesh = sel[0]
        try:
            api.getMeshShape(mesh)
        except api.CorrectiveBSError as e:
            self._warn(str(e))
            return
        self._meshField.setText(mesh)
        self._refreshStackInfo(mesh)
        self._refreshTargetList()
        self._recoverSession(mesh)

    def _loadCustomDriver(self):
        sel = cmds.ls(sl=True)
        if not sel:
            self._warn('Select an object first.')
            return
        attrs = cmds.channelBox('mainChannelBox', query=True, selectedMainAttributes=True) or []
        if not attrs:
            self._warn('Select an attribute in the Channel Box first.')
            return
        self._customDriverField.setText(sel[0] + '.' + attrs[0])

    def _onPrintStack(self):
        mesh = self._meshField.text()
        if not mesh:
            self._warn('Load a mesh first.')
            return
        try:
            stack = api.getDeformationStack(mesh)
        except api.CorrectiveBSError as e:
            self._warn(str(e))
            return
        if not stack:
            self._log_msg('No deformers found on: ' + mesh)
            return
        self._log_msg('Deformation stack for: ' + mesh)
        for i, (node, node_type) in enumerate(stack):
            arrow = '  →  ' if i < len(stack) - 1 else ''
            self._log_msg('  [%d] %s  (%s)%s' % (i + 1, node, node_type, arrow))

    def _refreshStackInfo(self, mesh):
        sc = api.getSkinCluster(mesh)
        bs = api.getBlendShapeNode(mesh)
        parts = []
        if bs:
            parts.append('blendShape: ' + bs)
        if sc:
            parts.append('skinCluster: ' + sc)
        if not parts:
            parts.append('no deformers found')
        self._stackLabel.setText('  ' + '   →   '.join(parts))

    def _onStart(self):
        mesh = self._meshField.text()
        name = self._nameField.text().strip()
        if not mesh:
            self._warn('Load a mesh first.')
            return
        if not name:
            self._warn('Enter a target name first.')
            return

        use_custom = self._modeCustom.isChecked()
        if use_custom:
            driver_attr = self._customDriverField.text().strip()
            if not driver_attr:
                self._warn('Enter a driver attribute before capturing the pose.')
                return
            if not cmds.objExists(driver_attr):
                self._warn('Driver attribute not found: ' + driver_attr)
                return

        try:
            dup_a, dup_b, bs_states = api.startCorrection(mesh, name)
            self._dup_a     = dup_a
            self._dup_b     = dup_b
            self._bs_states = bs_states
            self._sculptField.setText(dup_a)
            self._poseRefField.setText(dup_b)

            if use_custom:
                self._custom_driver_attr  = driver_attr
                self._custom_driver_value = cmds.getAttr(driver_attr)
                driver_text = '  Driver: %s = %.4f' % (driver_attr, self._custom_driver_value)
                self._log_msg('Pose captured. Sculpt on: ' + dup_a)
                self._log_msg('  custom driver: %s = %.4f' % (driver_attr, self._custom_driver_value))
            else:
                self._custom_driver_attr  = None
                self._custom_driver_value = None
                if bs_states:
                    driver_lines = ['  Drivers:']
                    for attr, val in bs_states:
                        driver_lines.append('    %s = %.3f' % (attr, val))
                    driver_text = '\n'.join(driver_lines)
                else:
                    driver_text = '  No blendShape drivers active — no wiring will be created.'
                self._log_msg('Pose captured. Sculpt on: ' + dup_a)
                for attr, val in bs_states:
                    self._log_msg('  driver: %s = %.3f' % (attr, val))

            self._captureStatus.setText('Sculpt on: %s\n%s' % (dup_a, driver_text))
            self._captureStatus.setStyleSheet('color: %s; font-size: 10px;' % self.TEXT)
            cmds.select(dup_a, r=True)
        except Exception as e:
            self._warn(str(e))

    def _onBake(self):
        mesh = self._meshField.text()
        name = self._nameField.text().strip()
        if not mesh:
            self._warn('Load a mesh first.')
            return
        if not name:
            self._warn('Enter a target name first.')
            return
        if not self._dup_a or not cmds.objExists(self._dup_a):
            self._warn('Sculpt mesh not found. Use Step 1 to capture the pose.')
            return

        existing = api.listCorrectiveTargets(mesh)
        if name in existing:
            reply = QtWidgets.QMessageBox.question(
                self, 'Target Exists',
                'Target "%s" already exists.\n\nUpdate it instead?' % name,
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
            if reply == QtWidgets.QMessageBox.Yes:
                items = self._targetList.findItems(name, QtCore.Qt.MatchExactly)
                if items:
                    self._targetList.setCurrentItem(items[0])
                self._onUpdate()
            return

        try:
            use_custom = (self._custom_driver_attr is not None
                          and self._custom_driver_value is not None)
            if use_custom:
                bs_node, idx = api.bakeCorrection(
                    mesh, self._dup_a, name,
                    custom_driver_attr=self._custom_driver_attr,
                    custom_driver_value=self._custom_driver_value)
                wire_text = 'SDK: %s  [0 → %.4f]' % (
                    self._custom_driver_attr, self._custom_driver_value)
            else:
                bs_node, idx = api.bakeCorrection(
                    mesh, self._dup_a, name,
                    bs_states=self._bs_states)
                valid = [(a, v) for a, v in self._bs_states if abs(v) > 1e-4]
                if valid:
                    if len(valid) == 1:
                        wire_text = 'Network: %s  [0 → %.3f]' % valid[0]
                    else:
                        wire_text = 'Network: %d drivers multiplied' % len(valid)
                else:
                    wire_text = 'No driver wiring — no blendShape drivers were active.'

            self._bs_node      = bs_node
            self._target_index = idx
            self._bakeStatus.setText(
                'Baked "%s" → %s [%d]\n%s' % (name, bs_node, idx, wire_text))
            self._bakeStatus.setStyleSheet('color: %s; font-size: 10px;' % self.TEXT)
            self._log_msg('Baked "%s" → %s [%d]' % (name, bs_node, idx))
            self._log_msg(wire_text)
            self._onPrintStack()

            self._bs_states = []
            self._custom_driver_attr  = None
            self._custom_driver_value = None
            self._captureStatus.setText('Bake done. Pose to next problem pose, enter a new target name, then use Step 1.')
            self._captureStatus.setStyleSheet('color: %s; font-size: 10px;' % self.DIM)

            self._refreshTargetList()
            items = self._targetList.findItems(name, QtCore.Qt.MatchExactly)
            if items:
                self._targetList.setCurrentItem(items[0])
        except Exception as e:
            self._warn(str(e))

    def _onTargetSelected(self):
        if not self._resolveSelectedTarget():
            return
        target_name = self._targetList.selectedItems()[0].text()
        sculpt_name = target_name + '_sculpt'
        if cmds.objExists(sculpt_name):
            self._dup_a = sculpt_name
            self._sculptField.setText(sculpt_name)
        else:
            self._dup_a = None
            self._sculptField.clear()
        pose_name = target_name + '_poseRef'
        if cmds.objExists(pose_name):
            self._dup_b = pose_name
            self._poseRefField.setText(pose_name)
        else:
            self._dup_b = None
            self._poseRefField.clear()

    def _resolveSelectedTarget(self):
        mesh = self._meshField.text()
        items = self._targetList.selectedItems()
        if not items or not mesh:
            return False
        target_name = items[0].text()
        bs_node = api.getBlendShapeNode(mesh)
        if bs_node is None:
            return False
        try:
            idx = api._resolveTargetIndex(bs_node, target_name)
            self._bs_node      = bs_node
            self._target_index = idx
            self._nameField.setText(target_name)
            return True
        except api.CorrectiveBSError:
            return False

    def _onUpdate(self):
        mesh = self._meshField.text()
        if not mesh:
            self._warn('Load a mesh first.')
            return
        if not self._resolveSelectedTarget():
            self._warn('Select a target from the list first.')
            return

        items = self._targetList.selectedItems()
        target_name = items[0].text() if items else ''
        if not target_name:
            return

        if not self._dup_a or not cmds.objExists(self._dup_a):
            fallback = target_name + '_sculpt'
            if cmds.objExists(fallback):
                self._dup_a = fallback
                self._sculptField.setText(fallback)
            else:
                self._warn(
                    'Sculpt mesh not in scene.\n'
                    'Use Step 1 or pick a sculpt mesh below the target list.')
                return

        try:
            api.updateCorrectiveTarget(mesh, target_name, self._dup_a)
            self._bakeStatus.setText('Target "%s" updated.' % target_name)
            self._bakeStatus.setStyleSheet('color: %s; font-size: 10px;' % self.TEXT)
            self._log_msg('Updated target "%s"' % target_name)
            self._refreshTargetList()
            items = self._targetList.findItems(target_name, QtCore.Qt.MatchExactly)
            if items:
                self._targetList.setCurrentItem(items[0])
        except Exception as e:
            self._warn(str(e))

    def _onDelete(self):
        mesh = self._meshField.text()
        items = self._targetList.selectedItems()
        if not items or not mesh:
            self._warn('Select a target from the list first.')
            return
        target_name = items[0].text()
        confirm = QtWidgets.QMessageBox.question(
            self, 'Delete Target',
            'Delete corrective target "%s"?' % target_name,
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if confirm != QtWidgets.QMessageBox.Yes:
            return
        try:
            api.removeCorrectiveTarget(mesh, target_name)
            self._refreshTargetList()
            self._bs_node      = None
            self._target_index = None
        except api.CorrectiveBSError as e:
            self._warn(str(e))

    def _onAddShape(self):
        mesh = self._meshField.text()
        if not mesh:
            self._warn('Load a mesh first.')
            return

        sel = cmds.ls(sl=True, transforms=True)
        if not sel:
            self._warn('Select a shape mesh to add.')
            return
        shape_mesh = sel[0]
        if shape_mesh == mesh:
            self._warn('Select the shape mesh, not the base mesh.')
            return
        try:
            api.getMeshShape(shape_mesh)
        except api.CorrectiveBSError as e:
            self._warn(str(e))
            return

        target_name = shape_mesh.split('|')[-1].split(':')[-1]

        existing = api.listCorrectiveTargets(mesh)
        if target_name in existing:
            self._warn('Target "%s" already exists. Rename the mesh or use Update.' % target_name)
            return

        mode, data = api.detectDriverMode(mesh)

        try:
            if mode == 'blendshape':
                self._log_msg('Detected: BS-driven')
                for attr, val in data:
                    self._log_msg('  %s = %.3f' % (attr, val))
                bs_node, idx = api.bakeCorrection(
                    mesh, shape_mesh, target_name, bs_states=data)
            elif mode == 'joint':
                driver_attr, driver_val = data[0]
                self._log_msg('Detected: joint-driven')
                self._log_msg('  %s = %.1f' % (driver_attr, driver_val))
                bs_node, idx = api.bakeCorrection(
                    mesh, shape_mesh, target_name,
                    custom_driver_attr=driver_attr,
                    custom_driver_value=driver_val)
            else:
                driver_attr, driver_val = self._promptForAttribute()
                if driver_attr is None:
                    return
                self._log_msg('Attribute-driven')
                self._log_msg('  %s = %.3f' % (driver_attr, driver_val))
                bs_node, idx = api.bakeCorrection(
                    mesh, shape_mesh, target_name,
                    custom_driver_attr=driver_attr,
                    custom_driver_value=driver_val)

            self._log_msg('Added "%s" → %s [%d]' % (target_name, bs_node, idx))
            self._refreshTargetList()
            items = self._targetList.findItems(target_name, QtCore.Qt.MatchExactly)
            if items:
                self._targetList.setCurrentItem(items[0])
        except Exception as e:
            self._warn(str(e))

    def _promptForAttribute(self):
        msg = QtWidgets.QMessageBox(self)
        msg.setWindowTitle('Attribute Driver')
        msg.setText(
            'No active blendShapes or joint rotations detected.\n\n'
            'Select a control and highlight an attribute in the\n'
            'Channel Box, then click OK.')
        msg.setStandardButtons(
            QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel)
        if msg.exec_() != QtWidgets.QMessageBox.Ok:
            return None, None

        sel = cmds.ls(sl=True)
        if not sel:
            self._warn('No object selected.')
            return None, None
        attrs = cmds.channelBox('mainChannelBox', query=True,
                                selectedMainAttributes=True) or []
        if not attrs:
            self._warn('No attribute selected in Channel Box.')
            return None, None

        driver_attr = sel[0] + '.' + attrs[0]
        if not cmds.objExists(driver_attr):
            self._warn('Attribute not found: ' + driver_attr)
            return None, None

        driver_val = cmds.getAttr(driver_attr)
        if abs(driver_val) < 1e-4:
            driver_val = 1.0

        return driver_attr, driver_val

    def _recoverSession(self, mesh):
        targets = api.listCorrectiveTargets(mesh)
        if not targets:
            return

        recovered = []
        for target_name in targets:
            sculpt_name = target_name + '_sculpt'
            pose_name   = target_name + '_poseRef'

            has_sculpt = cmds.objExists(sculpt_name)
            has_pose   = cmds.objExists(pose_name)

            if has_sculpt and has_pose:
                recovered.append((target_name, sculpt_name, pose_name))

        if not recovered:
            return

        for name, sculpt, pose in recovered:
            self._log_msg('Session: found %s  (sculpt + poseRef in scene)' % name)

        last = recovered[-1]
        self._dup_a = last[1]
        self._dup_b = last[2]
        self._sculptField.setText(last[1])
        self._poseRefField.setText(last[2])
        self._nameField.setText(last[0])
        self._captureStatus.setText(
            'Recovered from scene: %s\n  sculpt = %s' % (last[0], last[1]))
        self._captureStatus.setStyleSheet('color: %s; font-size: 10px;' % self.TEXT)

        items = self._targetList.findItems(last[0], QtCore.Qt.MatchExactly)
        if items:
            self._targetList.setCurrentItem(items[0])

    def _pickSculptMesh(self):
        sel = cmds.ls(sl=True, transforms=True)
        if not sel:
            self._warn('Select a mesh transform first.')
            return
        try:
            api.getMeshShape(sel[0])
        except api.CorrectiveBSError as e:
            self._warn(str(e))
            return
        self._dup_a = sel[0]
        self._sculptField.setText(sel[0])
        self._log_msg('Sculpt mesh set: ' + sel[0])

    def _pickPoseRefMesh(self):
        sel = cmds.ls(sl=True, transforms=True)
        if not sel:
            self._warn('Select a mesh transform first.')
            return
        try:
            api.getMeshShape(sel[0])
        except api.CorrectiveBSError as e:
            self._warn(str(e))
            return
        self._dup_b = sel[0]
        self._poseRefField.setText(sel[0])
        self._log_msg('Pose reference set: ' + sel[0])

    def _refreshTargetList(self):
        self._targetList.clear()
        mesh = self._meshField.text()
        if not mesh:
            return
        for name in api.listCorrectiveTargets(mesh):
            self._targetList.addItem(name)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _log_msg(self, msg, error=False):
        color = '#d65f5f' if error else '#6fbf73'
        self._log.append(
            '<span style="color:{}">{}</span>'.format(
                color, msg.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')))

    def _warn(self, msg):
        self._log_msg(msg, error=True)
        QtWidgets.QMessageBox.warning(self, 'Corrective BS', msg)

    def _guideLabel(self, text):
        lbl = QtWidgets.QLabel(text)
        lbl.setStyleSheet(
            'color: %s; font-size: 10px; padding: 4px 8px 2px 8px;' % self.DIM)
        lbl.setWordWrap(True)
        return lbl

    def _headerLabel(self, text):
        lbl = QtWidgets.QLabel(text)
        lbl.setStyleSheet(
            'background: %s; color: %s; font-size: 11px; font-weight: bold;'
            'padding: 5px; letter-spacing: 1px;' % (self.LIGHT, self.TEXT))
        lbl.setAlignment(QtCore.Qt.AlignCenter)
        return lbl

    def _sectionLabel(self, text):
        lbl = QtWidgets.QLabel(text)
        lbl.setStyleSheet(
            'background: %s; color: %s; font-size: 10px; font-weight: bold;'
            'padding: 3px 5px; letter-spacing: 1px;' % (self.MID, self.DIM))
        return lbl

    def _divider(self):
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setStyleSheet('color: %s;' % self.BORDER)
        return line

    def _iconButton(self, icon, tooltip=''):
        btn = QtWidgets.QPushButton()
        btn.setIcon(QtGui.QIcon(':/%s' % icon))
        btn.setFixedSize(24, 24)
        btn.setToolTip(tooltip)
        btn.setStyleSheet(
            'QPushButton { background: %s; border: 1px solid %s; }'
            'QPushButton:hover { background: %s; }' % (
                self.LIGHT, self.BORDER, self.ACCENT))
        return btn

    def _stylesheet(self):
        return '''
            QWidget {
                background: %(DARK)s;
                color: %(TEXT)s;
                font-family: Arial;
                font-size: 11px;
            }
            QLineEdit {
                background: %(MID)s;
                border: 1px solid %(BORDER)s;
                padding: 3px 5px;
                color: %(TEXT)s;
            }
            QLineEdit:focus {
                border: 1px solid %(ACCENT)s;
            }
            QPushButton {
                background: %(LIGHT)s;
                border: 1px solid %(BORDER)s;
                padding: 4px 10px;
                color: %(TEXT)s;
            }
            QPushButton:hover {
                background: %(ACCENT)s;
            }
            QListWidget {
                background: %(MID)s;
                border: 1px solid %(BORDER)s;
                color: %(TEXT)s;
            }
            QLabel {
                color: %(TEXT)s;
            }
        ''' % {
            'DARK': self.DARK, 'MID': self.MID, 'LIGHT': self.LIGHT,
            'BORDER': self.BORDER, 'TEXT': self.TEXT, 'ACCENT': self.ACCENT,
        }
