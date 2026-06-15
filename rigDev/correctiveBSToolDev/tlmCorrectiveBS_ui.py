import maya.cmds as cmds
import maya.mel as mel

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
    ORANGE = '#8a6a30'

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Corrective Blendshape Tool')
        self.setWindowFlags(QtCore.Qt.Tool)
        self.setMinimumWidth(380)
        self.setStyleSheet(self._stylesheet())

        self._sculpt_mesh = None
        self._bs_node = None
        self._target_index = None

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

        # ── Step 1: Sculpt ──
        root.addWidget(self._sectionLabel('STEP 1  —  CAPTURE POSE'))

        name_row = QtWidgets.QHBoxLayout()
        name_row.addWidget(QtWidgets.QLabel('Target name:'))
        self._nameField = QtWidgets.QLineEdit()
        self._nameField.setPlaceholderText('e.g.  L_shoulder_fix  or  smile_deep')
        name_row.addWidget(self._nameField)
        root.addLayout(name_row)

        sculpt_row = QtWidgets.QHBoxLayout()
        self._startBtn = QtWidgets.QPushButton('Duplicate for Sculpting')
        self._startBtn.setToolTip(
            'Duplicates the mesh at its current deformed state.\n'
            'Sculpt the correction on this duplicate, then continue to Step 2.')
        self._startBtn.clicked.connect(self._onStart)
        sculpt_row.addWidget(self._startBtn)
        root.addLayout(sculpt_row)

        self._sculptStatus = QtWidgets.QLabel('No sculpt mesh captured yet.')
        self._sculptStatus.setStyleSheet('color: %s; font-size: 10px;' % self.DIM)
        root.addWidget(self._sculptStatus)

        # Import from external app
        import_row = QtWidgets.QHBoxLayout()
        import_row.addWidget(QtWidgets.QLabel('or load sculpted mesh:'))
        self._sculptField = QtWidgets.QLineEdit()
        self._sculptField.setPlaceholderText('Select sculpted mesh and click  ←')
        self._sculptField.setReadOnly(True)
        pickSculpt = self._iconButton('nudgeDown.png', 'Load selected mesh as sculpt target')
        pickSculpt.clicked.connect(self._loadSculptMesh)
        import_row.addWidget(self._sculptField)
        import_row.addWidget(pickSculpt)
        root.addLayout(import_row)

        root.addWidget(self._divider())

        # ── Step 2: Bake ──
        root.addWidget(self._sectionLabel('STEP 2  —  BAKE CORRECTION'))

        self._bakeBtn = QtWidgets.QPushButton('Bake Corrective Target')
        self._bakeBtn.setToolTip(
            'Extracts the delta between the sculpted mesh and the skinned mesh,\n'
            'then adds the result as a blendshape target.\n'
            'The rig must still be at the same pose as Step 1.')
        self._bakeBtn.setStyleSheet(
            'QPushButton { background: %s; } '
            'QPushButton:hover { background: %s; }' % (self.GREEN, '#5a8a5a'))
        self._bakeBtn.clicked.connect(self._onBake)
        root.addWidget(self._bakeBtn)

        self._bakeStatus = QtWidgets.QLabel('')
        self._bakeStatus.setStyleSheet('color: %s; font-size: 10px;' % self.DIM)
        root.addWidget(self._bakeStatus)

        root.addWidget(self._divider())

        # ── Step 3: Driver ──
        root.addWidget(self._sectionLabel('STEP 3  —  WIRE DRIVER'))

        driver_row = QtWidgets.QHBoxLayout()
        driver_row.addWidget(QtWidgets.QLabel('Driver attr:'))
        self._driverField = QtWidgets.QLineEdit()
        self._driverField.setPlaceholderText('e.g.  L_arm_JNT.rotateZ')
        pickDriver = self._iconButton('nudgeDown.png', 'Load selected channel from Channel Box')
        pickDriver.clicked.connect(self._loadDriverAttr)
        driver_row.addWidget(self._driverField)
        driver_row.addWidget(pickDriver)
        root.addLayout(driver_row)

        range_row = QtWidgets.QHBoxLayout()
        range_row.addWidget(QtWidgets.QLabel('Drive range:'))
        self._rangeMinField = QtWidgets.QLineEdit('0')
        self._rangeMinField.setFixedWidth(55)
        self._rangeMaxField = QtWidgets.QLineEdit('90')
        self._rangeMaxField.setFixedWidth(55)
        range_row.addWidget(self._rangeMinField)
        range_row.addWidget(QtWidgets.QLabel('→'))
        range_row.addWidget(self._rangeMaxField)
        range_row.addStretch()
        root.addLayout(range_row)

        self._wireBtn = QtWidgets.QPushButton('Wire SDK Driver')
        self._wireBtn.setToolTip(
            'Creates a Set Driven Key on the blendshape weight.\n'
            'The driver attribute goes from the start to end value\n'
            'as the blendshape weight goes from 0 to 1.')
        self._wireBtn.setStyleSheet(
            'QPushButton { background: %s; } '
            'QPushButton:hover { background: %s; }' % (self.ACCENT, '#8a7fb0'))
        self._wireBtn.clicked.connect(self._onWire)
        root.addWidget(self._wireBtn)

        root.addWidget(self._divider())

        # ── Target list ──
        root.addWidget(self._sectionLabel('TARGETS ON MESH'))

        self._targetList = QtWidgets.QListWidget()
        self._targetList.setFixedHeight(100)
        self._targetList.setStyleSheet(
            'QListWidget { background: %s; border: 1px solid %s; }'
            'QListWidget::item:selected { background: %s; }' % (
                self.MID, self.BORDER, self.ACCENT))
        self._targetList.itemSelectionChanged.connect(self._onTargetSelected)
        root.addWidget(self._targetList)

        target_btn_row = QtWidgets.QHBoxLayout()
        self._updateBtn = QtWidgets.QPushButton('Update Target')
        self._updateBtn.setToolTip(
            'Re-bake the selected target using the current sculpt mesh.\n'
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

    def _loadSculptMesh(self):
        sel = cmds.ls(sl=True, transforms=True)
        if not sel:
            self._warn('Select the sculpted mesh first.')
            return
        mesh = sel[0]
        try:
            api.getMeshShape(mesh)
        except api.CorrectiveBSError as e:
            self._warn(str(e))
            return
        self._sculpt_mesh = mesh
        self._sculptField.setText(mesh)
        self._sculptStatus.setText('Sculpt mesh loaded: ' + mesh)
        self._sculptStatus.setStyleSheet('color: %s; font-size: 10px;' % self.TEXT)

    def _onStart(self):
        mesh = self._meshField.text()
        name = self._nameField.text().strip()
        if not mesh:
            self._warn('Load a mesh first.')
            return
        if not name:
            self._warn('Enter a target name first.')
            return
        try:
            dup = api.startCorrection(mesh, name)
            self._sculpt_mesh = dup
            self._sculptField.setText(dup)
            self._sculptStatus.setText(
                'Sculpt mesh ready: %s   —   sculpt this, then Bake.' % dup)
            self._sculptStatus.setStyleSheet(
                'color: %s; font-size: 10px;' % self.TEXT)
            self._log_msg('Sculpt mesh created: ' + dup)
            cmds.select(dup, r=True)
        except Exception as e:
            self._warn(str(e))

    def _onBake(self):
        mesh = self._meshField.text()
        sculpt = self._sculptField.text()
        name = self._nameField.text().strip()

        if not mesh:
            self._warn('Load a mesh first.')
            return
        if not sculpt or not cmds.objExists(sculpt):
            self._warn('No sculpted mesh loaded — use Step 1 or load one manually.')
            return
        if not name:
            self._warn('Enter a target name first.')
            return

        try:
            bs_node, idx = api.bakeCorrection(mesh, sculpt, name)
            self._bs_node = bs_node
            self._target_index = idx
            self._bakeStatus.setText(
                'Target "%s" baked to %s [%d]' % (name, bs_node, idx))
            self._bakeStatus.setStyleSheet(
                'color: %s; font-size: 10px;' % self.TEXT)
            self._log_msg('Baked "%s" → %s [%d]' % (name, bs_node, idx))
            self._refreshTargetList()
            # Select the baked target in the list
            items = self._targetList.findItems(name, QtCore.Qt.MatchExactly)
            if items:
                self._targetList.setCurrentItem(items[0])
        except Exception as e:
            self._warn(str(e))

    def _loadDriverAttr(self):
        """Load the first selected channel from the Channel Box."""
        main_cb = mel.eval('$tmpVar = $gChannelBoxName')
        attrs = cmds.channelBox(main_cb, query=True, selectedMainAttributes=True) or []
        sel = cmds.ls(sl=True)
        if not sel or not attrs:
            self._warn(
                'Select a node and highlight a channel in the Channel Box first.')
            return
        full_attr = sel[0] + '.' + attrs[0]
        self._driverField.setText(full_attr)

    def _onWire(self):
        if self._bs_node is None or self._target_index is None:
            # Try to resolve from current list selection
            if not self._resolveSelectedTarget():
                self._warn('Bake a target first, or select one from the list.')
                return

        driver = self._driverField.text().strip()
        if not driver:
            self._warn('Enter or load a driver attribute first.')
            return

        try:
            rmin = float(self._rangeMinField.text())
            rmax = float(self._rangeMaxField.text())
        except ValueError:
            self._warn('Drive range values must be numbers.')
            return

        if not cmds.objExists(driver.rsplit('.', 1)[0]):
            self._warn('Driver node not found: ' + driver)
            return

        try:
            api.wireSDKDriver(self._bs_node, self._target_index,
                              driver, (rmin, rmax))
            self._bakeStatus.setText(
                'SDK wired: %s  [%s → %s]' % (driver, rmin, rmax))
            self._bakeStatus.setStyleSheet(
                'color: %s; font-size: 10px;' % self.TEXT)
            self._log_msg('SDK wired: %s [%s → %s]' % (driver, rmin, rmax))
        except Exception as e:
            self._warn(str(e))

    def _onTargetSelected(self):
        self._resolveSelectedTarget()

    def _resolveSelectedTarget(self):
        """Sync _bs_node / _target_index from the current list selection."""
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
            self._bs_node = bs_node
            self._target_index = idx
            self._nameField.setText(target_name)
            return True
        except api.CorrectiveBSError:
            return False

    def _onUpdate(self):
        mesh = self._meshField.text()
        sculpt = self._sculptField.text()
        if not mesh:
            self._warn('Load a mesh first.')
            return
        if not sculpt or not cmds.objExists(sculpt):
            self._warn('No sculpted mesh loaded.')
            return
        if not self._resolveSelectedTarget():
            self._warn('Select a target from the list first.')
            return

        items = self._targetList.selectedItems()
        target_name = items[0].text() if items else ''
        if not target_name:
            self._warn('Select a target from the list first.')
            return

        try:
            target_positions = api.extractDelta(mesh, sculpt)
            api.updateCorrectiveTarget(mesh, target_name, target_positions)
            self._bakeStatus.setText('Target "%s" updated.' % target_name)
            self._bakeStatus.setStyleSheet(
                'color: %s; font-size: 10px;' % self.TEXT)
            self._log_msg('Updated target "%s"' % target_name)
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
            self._bs_node = None
            self._target_index = None
        except api.CorrectiveBSError as e:
            self._warn(str(e))

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


