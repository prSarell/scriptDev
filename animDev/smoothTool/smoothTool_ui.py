"""
Smooth Tool — UI
PySide6 interface for smoothTool_api / smoothTool_fkchain.
"""

import sys
import os

import maya.cmds as cmds
from maya import OpenMayaUI as omui
from PySide6 import QtWidgets, QtCore
import shiboken6

_DIR = os.path.dirname(__file__)
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

import smoothTool_api as api
import smoothTool_fkchain as fkchain


def _maya_main_window():
    ptr = omui.MQtUtil.mainWindow()
    return shiboken6.wrapInstance(int(ptr), QtWidgets.QWidget)


# ---------------------------------------------------------------------------
# Helpers shared by both tabs
# ---------------------------------------------------------------------------

def _load_from_selection(line_edit):
    """Populate a QLineEdit with the first selected transform."""
    sel = cmds.ls(selection=True, type='transform')
    if sel:
        line_edit.setText(sel[0])


def _make_field_row(label_text, button_text='<< Sel'):
    """Return (layout, line_edit, button)."""
    row = QtWidgets.QHBoxLayout()
    label = QtWidgets.QLabel(label_text)
    label.setFixedWidth(85)
    field = QtWidgets.QLineEdit()
    btn = QtWidgets.QPushButton(button_text)
    btn.setFixedWidth(50)
    row.addWidget(label)
    row.addWidget(field)
    row.addWidget(btn)
    return row, field, btn


def _make_slider_row(label_text, min_val, max_val, default, decimals=2):
    """Return (layout, slider, value_label)."""
    row = QtWidgets.QHBoxLayout()
    label = QtWidgets.QLabel(label_text)
    label.setFixedWidth(85)
    slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
    slider.setMinimum(0)
    slider.setMaximum(1000)
    frac = (default - min_val) / (max_val - min_val)
    slider.setValue(int(frac * 1000))
    val_label = QtWidgets.QLabel('{:.{}f}'.format(default, decimals))
    val_label.setFixedWidth(40)
    val_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
    row.addWidget(label)
    row.addWidget(slider)
    row.addWidget(val_label)
    return row, slider, val_label


_SLIDER_RANGES = {
    'strength': (0.0, 5.0),
    'blend':    (0.0, 1.0),
    'falloff':  (0.0, 0.5),
}
_SLIDER_DEFAULTS = {
    'strength': 1.0,
    'blend':    1.0,
    'falloff':  0.15,
}


def _slider_value(slider, key):
    lo, hi = _SLIDER_RANGES[key]
    return lo + (slider.value() / 1000.0) * (hi - lo)


def _reset_slider(slider, val_label, key):
    lo, hi = _SLIDER_RANGES[key]
    default = _SLIDER_DEFAULTS[key]
    frac = (default - lo) / (hi - lo)
    slider.setValue(int(frac * 1000))
    val_label.setText('{:.2f}'.format(default))


# ---------------------------------------------------------------------------
# Tab 1: Single Control
# ---------------------------------------------------------------------------

class _SingleControlTab(QtWidgets.QWidget):
    """Original single-control smoothing tab — unchanged behavior, moved
    into its own tab class so a new FK Chain tab can sit alongside it."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._core = api.SmoothToolCore()
        self._curves_live = False

        self._face_core = api.FaceSmoothCore()
        self._face_curves_live = False

        self._build_ui()
        self._connect_signals()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setSpacing(8)

        tabs = QtWidgets.QTabWidget()
        tabs.addTab(self._build_rig_tab(), 'Rig Smooth')
        tabs.addTab(self._build_face_tab(), 'Face Smooth')
        root.addWidget(tabs)

    def _build_rig_tab(self):
        tab = QtWidgets.QWidget()
        root = QtWidgets.QVBoxLayout(tab)
        root.setSpacing(8)

        # --- Source / Target ---
        source_box = QtWidgets.QGroupBox('Objects')
        source_lay = QtWidgets.QVBoxLayout(source_box)
        source_lay.setSpacing(4)

        r, self._mesh_field, self._mesh_btn = _make_field_row('Source Geo')
        source_lay.addLayout(r)
        r, self._target_field, self._target_btn = _make_field_row('Bake Target')
        source_lay.addLayout(r)
        r, self._parent_field, self._parent_btn = _make_field_row('Parent Space')
        source_lay.addLayout(r)

        self._vert_mode = QtWidgets.QComboBox()
        self._vert_mode.addItems(['Auto-pick verts/CVs', 'Use selected verts/CVs',
                                   'Control only (no mesh)'])
        vert_row = QtWidgets.QHBoxLayout()
        lbl = QtWidgets.QLabel('Vertex Mode')
        lbl.setFixedWidth(85)
        vert_row.addWidget(lbl)
        vert_row.addWidget(self._vert_mode)
        source_lay.addLayout(vert_row)

        root.addWidget(source_box)

        # --- Create ---
        self._create_btn = QtWidgets.QPushButton('Create Curves')
        self._create_btn.setStyleSheet(
            'background-color: #993333; color: white; padding: 6px;')
        root.addWidget(self._create_btn)

        # --- Sliders ---
        slider_box = QtWidgets.QGroupBox('Smooth Controls')
        slider_lay = QtWidgets.QVBoxLayout(slider_box)
        slider_lay.setSpacing(4)

        r, self._strength_slider, self._strength_val = _make_slider_row(
            'Strength', *_SLIDER_RANGES['strength'],
            _SLIDER_DEFAULTS['strength'])
        slider_lay.addLayout(r)
        r, self._blend_slider, self._blend_val = _make_slider_row(
            'Blend', *_SLIDER_RANGES['blend'],
            _SLIDER_DEFAULTS['blend'])
        slider_lay.addLayout(r)
        r, self._falloff_slider, self._falloff_val = _make_slider_row(
            'Falloff', *_SLIDER_RANGES['falloff'],
            _SLIDER_DEFAULTS['falloff'])
        slider_lay.addLayout(r)

        root.addWidget(slider_box)

        # --- Bake ---
        bake_box = QtWidgets.QGroupBox('Bake')
        bake_lay = QtWidgets.QVBoxLayout(bake_box)
        bake_lay.setSpacing(4)

        self._layer_check = QtWidgets.QCheckBox('Bake to Layer')
        self._layer_check.setChecked(True)
        bake_lay.addWidget(self._layer_check)

        self._additive_check = QtWidgets.QCheckBox('Additive Layer')
        self._additive_check.setChecked(True)
        bake_lay.addWidget(self._additive_check)

        btn_row = QtWidgets.QHBoxLayout()
        self._bake_btn = QtWidgets.QPushButton('Bake')
        self._bake_btn.setStyleSheet(
            'background-color: #339933; color: white; padding: 6px;')
        self._reset_btn = QtWidgets.QPushButton('Reset')
        self._reset_btn.setStyleSheet('padding: 6px;')
        btn_row.addWidget(self._bake_btn)
        btn_row.addWidget(self._reset_btn)
        bake_lay.addLayout(btn_row)

        root.addWidget(bake_box)
        return tab

    def _build_face_tab(self):
        tab = QtWidgets.QWidget()
        root = QtWidgets.QVBoxLayout(tab)
        root.setSpacing(8)

        # --- Controls ---
        ctrl_box = QtWidgets.QGroupBox('Controls')
        ctrl_lay = QtWidgets.QVBoxLayout(ctrl_box)
        ctrl_lay.setSpacing(4)

        self._face_list = QtWidgets.QListWidget()
        self._face_list.setSelectionMode(
            QtWidgets.QAbstractItemView.ExtendedSelection)
        ctrl_lay.addWidget(self._face_list)

        list_btn_row = QtWidgets.QHBoxLayout()
        self._face_add_btn = QtWidgets.QPushButton('Add Selected')
        self._face_remove_btn = QtWidgets.QPushButton('Remove Selected')
        self._face_clear_btn = QtWidgets.QPushButton('Clear')
        list_btn_row.addWidget(self._face_add_btn)
        list_btn_row.addWidget(self._face_remove_btn)
        list_btn_row.addWidget(self._face_clear_btn)
        ctrl_lay.addLayout(list_btn_row)

        root.addWidget(ctrl_box)

        # --- Create ---
        self._face_create_btn = QtWidgets.QPushButton('Create Curves')
        self._face_create_btn.setStyleSheet(
            'background-color: #993333; color: white; padding: 6px;')
        root.addWidget(self._face_create_btn)

        # --- Sliders ---
        slider_box = QtWidgets.QGroupBox('Smooth Controls')
        slider_lay = QtWidgets.QVBoxLayout(slider_box)
        slider_lay.setSpacing(4)

        r, self._face_strength_slider, self._face_strength_val = _make_slider_row(
            'Strength', *_SLIDER_RANGES['strength'],
            _SLIDER_DEFAULTS['strength'])
        slider_lay.addLayout(r)
        r, self._face_blend_slider, self._face_blend_val = _make_slider_row(
            'Blend', *_SLIDER_RANGES['blend'],
            _SLIDER_DEFAULTS['blend'])
        slider_lay.addLayout(r)
        r, self._face_falloff_slider, self._face_falloff_val = _make_slider_row(
            'Falloff', *_SLIDER_RANGES['falloff'],
            _SLIDER_DEFAULTS['falloff'])
        slider_lay.addLayout(r)

        root.addWidget(slider_box)

        # --- Bake ---
        bake_box = QtWidgets.QGroupBox('Bake')
        bake_lay = QtWidgets.QVBoxLayout(bake_box)
        bake_lay.setSpacing(4)

        self._face_layer_check = QtWidgets.QCheckBox('Bake to Layer')
        self._face_layer_check.setChecked(True)
        bake_lay.addWidget(self._face_layer_check)

        self._face_additive_check = QtWidgets.QCheckBox('Additive Layer')
        self._face_additive_check.setChecked(True)
        bake_lay.addWidget(self._face_additive_check)

        btn_row = QtWidgets.QHBoxLayout()
        self._face_bake_btn = QtWidgets.QPushButton('Bake')
        self._face_bake_btn.setStyleSheet(
            'background-color: #339933; color: white; padding: 6px;')
        self._face_reset_btn = QtWidgets.QPushButton('Reset')
        self._face_reset_btn.setStyleSheet('padding: 6px;')
        btn_row.addWidget(self._face_bake_btn)
        btn_row.addWidget(self._face_reset_btn)
        bake_lay.addLayout(btn_row)

        root.addWidget(bake_box)
        return tab

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------

    def _connect_signals(self):
        self._mesh_btn.clicked.connect(
            lambda: _load_from_selection(self._mesh_field))
        self._target_btn.clicked.connect(
            lambda: _load_from_selection(self._target_field))
        self._parent_btn.clicked.connect(
            lambda: _load_from_selection(self._parent_field))

        self._create_btn.clicked.connect(self._on_create)
        self._bake_btn.clicked.connect(self._on_bake)
        self._reset_btn.clicked.connect(self._on_reset)

        self._strength_slider.valueChanged.connect(self._on_strength)
        self._blend_slider.valueChanged.connect(self._on_blend)
        self._falloff_slider.valueChanged.connect(self._on_falloff)

        self._face_add_btn.clicked.connect(self._on_face_add)
        self._face_remove_btn.clicked.connect(self._on_face_remove)
        self._face_clear_btn.clicked.connect(self._face_list.clear)
        self._face_create_btn.clicked.connect(self._on_face_create)
        self._face_bake_btn.clicked.connect(self._on_face_bake)
        self._face_reset_btn.clicked.connect(self._on_face_reset)

        self._face_strength_slider.valueChanged.connect(self._on_face_strength)
        self._face_blend_slider.valueChanged.connect(self._on_face_blend)
        self._face_falloff_slider.valueChanged.connect(self._on_face_falloff)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _on_create(self):
        mesh = self._mesh_field.text().strip()
        target = self._target_field.text().strip()
        parent = self._parent_field.text().strip() or None

        if not mesh:
            sel = cmds.ls(selection=True, type='transform')
            if not sel:
                cmds.warning('Select an object or fill in Source Geo.')
                return
            mesh = sel[0]
            self._mesh_field.setText(mesh)
            if not target:
                target = mesh
                self._target_field.setText(target)

        if not target:
            cmds.warning('Set a bake target.')
            return

        locked = [a for a in ('tx', 'ty', 'tz', 'rx', 'ry', 'rz')
                  if cmds.getAttr('{}.{}'.format(target, a), lock=True)]
        if locked:
            cmds.warning('Cannot smooth: locked transforms on "{}": {}'.format(
                target, ', '.join(locked)))
            return

        vert_mode = self._vert_mode.currentIndex()
        control_only = vert_mode == 2

        if not control_only:
            if vert_mode == 1:
                try:
                    sel_mesh, indices = api.SmoothToolCore.indices_from_selection()
                    if sel_mesh != mesh:
                        cmds.warning(
                            'Selected verts/CVs are not on the source geo.')
                        return
                except RuntimeError as e:
                    cmds.warning(str(e))
                    return
            else:
                try:
                    indices = api.SmoothToolCore.find_spread_vertices(mesh)
                except RuntimeError as e:
                    cmds.warning(str(e))
                    return

        start, end = api.SmoothToolCore.get_frame_range()
        if control_only:
            self._core.sample_control(target, start, end, parent=parent)
        else:
            self._core.sample(mesh, indices, target, start, end, parent=parent)
        self._core.create_curves()

        strength = _slider_value(self._strength_slider, 'strength')
        self._core.falloff = _slider_value(
            self._falloff_slider, 'falloff')
        self._core.blend = _slider_value(self._blend_slider, 'blend')
        self._core.update_smooth(strength)

        self._curves_live = True
        cmds.inViewMessage(amg='Smooth curves created.', pos='topCenter',
                           fade=True)

    def _on_strength(self, _):
        if not self._curves_live:
            return
        val = _slider_value(self._strength_slider, 'strength')
        self._strength_val.setText('{:.2f}'.format(val))
        self._core.update_smooth(val)

    def _on_blend(self, _):
        if not self._curves_live:
            return
        val = _slider_value(self._blend_slider, 'blend')
        self._blend_val.setText('{:.2f}'.format(val))
        self._core.update_blend(val)

    def _on_falloff(self, _):
        if not self._curves_live:
            return
        val = _slider_value(self._falloff_slider, 'falloff')
        self._falloff_val.setText('{:.2f}'.format(val))
        self._core.update_falloff(val)

    def _on_bake(self):
        if not self._curves_live:
            cmds.warning('Create curves first.')
            return
        to_layer = self._layer_check.isChecked()
        additive = self._additive_check.isChecked()
        try:
            self._core.bake(to_layer=to_layer, additive=additive)
            self._curves_live = False
            cmds.inViewMessage(amg='<hl>Smooth bake complete.</hl>',
                               pos='topCenter', fade=True)
        except Exception as e:
            cmds.warning('Bake failed: {}'.format(e))
            raise

    def _on_reset(self):
        self._core.reset()
        self._curves_live = False

        self._mesh_field.clear()
        self._target_field.clear()
        self._parent_field.clear()
        self._vert_mode.setCurrentIndex(0)

        _reset_slider(self._strength_slider, self._strength_val, 'strength')
        _reset_slider(self._blend_slider, self._blend_val, 'blend')
        _reset_slider(self._falloff_slider, self._falloff_val, 'falloff')

        self._layer_check.setChecked(True)
        self._additive_check.setChecked(True)

        cmds.inViewMessage(amg='Smooth tool reset.', pos='topCenter',
                           fade=True)

    def _on_face_add(self):
        sel = cmds.ls(selection=True, type='transform')
        if not sel:
            cmds.warning('Select one or more controls first.')
            return
        existing = {self._face_list.item(i).text()
                   for i in range(self._face_list.count())}
        for s in sel:
            if s not in existing:
                self._face_list.addItem(s)
                existing.add(s)

    def _on_face_remove(self):
        for item in self._face_list.selectedItems():
            self._face_list.takeItem(self._face_list.row(item))

    def _on_face_create(self):
        targets = [self._face_list.item(i).text()
                  for i in range(self._face_list.count())]
        if not targets:
            cmds.warning('Add one or more controls first.')
            return

        start, end = api.SmoothToolCore.get_frame_range()
        skipped = self._face_core.sample(targets, start, end)
        if skipped:
            cmds.warning('No free translate channel, skipped: {}'.format(
                ', '.join(skipped)))
        if not self._face_core.targets:
            return

        self._face_core.create_curves()

        strength = _slider_value(self._face_strength_slider, 'strength')
        self._face_core.falloff = _slider_value(
            self._face_falloff_slider, 'falloff')
        self._face_core.blend = _slider_value(
            self._face_blend_slider, 'blend')
        self._face_core.update_smooth(strength)

        self._face_curves_live = True
        cmds.inViewMessage(amg='Face smooth curves created.',
                           pos='topCenter', fade=True)

    def _on_face_strength(self, _):
        if not self._face_curves_live:
            return
        val = _slider_value(self._face_strength_slider, 'strength')
        self._face_strength_val.setText('{:.2f}'.format(val))
        self._face_core.update_smooth(val)

    def _on_face_blend(self, _):
        if not self._face_curves_live:
            return
        val = _slider_value(self._face_blend_slider, 'blend')
        self._face_blend_val.setText('{:.2f}'.format(val))
        self._face_core.update_blend(val)

    def _on_face_falloff(self, _):
        if not self._face_curves_live:
            return
        val = _slider_value(self._face_falloff_slider, 'falloff')
        self._face_falloff_val.setText('{:.2f}'.format(val))
        self._face_core.update_falloff(val)

    def _on_face_bake(self):
        if not self._face_curves_live:
            cmds.warning('Create curves first.')
            return
        to_layer = self._face_layer_check.isChecked()
        additive = self._face_additive_check.isChecked()
        try:
            self._face_core.bake(to_layer=to_layer, additive=additive)
            self._face_curves_live = False
            cmds.inViewMessage(amg='<hl>Face smooth bake complete.</hl>',
                               pos='topCenter', fade=True)
        except Exception as e:
            cmds.warning('Bake failed: {}'.format(e))
            raise

    def _on_face_reset(self):
        self._face_core.reset()
        self._face_curves_live = False
        self._face_list.clear()

        _reset_slider(
            self._face_strength_slider, self._face_strength_val, 'strength')
        _reset_slider(
            self._face_blend_slider, self._face_blend_val, 'blend')
        _reset_slider(
            self._face_falloff_slider, self._face_falloff_val, 'falloff')

        self._face_layer_check.setChecked(True)
        self._face_additive_check.setChecked(True)

        cmds.inViewMessage(amg='Face smooth tool reset.', pos='topCenter',
                           fade=True)

    def cleanup(self):
        if self._curves_live:
            self._core.delete_curves()
        if self._face_curves_live:
            self._face_core.delete_curves()


# ---------------------------------------------------------------------------
# Tab 2: FK Chain
# ---------------------------------------------------------------------------

class _FKChainSmoothTab(QtWidgets.QWidget):
    """FK-chain smoothing tab: smooths a tip's trajectory (reusing
    SmoothToolCore unchanged, via smoothTool_fkchain.FKChainSolver) then
    FABRIK-solves + twist-propagates the rest of a selected chain,
    baking rotate-only keys across every control. See
    smoothTool_fkchain.py for the solver -- kept as a separate module per
    smoothTool_roadmap.md's architectural note rather than grown into
    SmoothToolCore."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tip_core = api.SmoothToolCore()
        self._solver = fkchain.FKChainSolver()
        self._solver.set_tip_core(self._tip_core)
        self._curves_live = False

        self._build_ui()
        self._connect_signals()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setSpacing(8)

        chain_box = QtWidgets.QGroupBox('Chain')
        chain_lay = QtWidgets.QVBoxLayout(chain_box)
        chain_lay.setSpacing(4)

        r, self._base_field, self._base_btn = _make_field_row('Base Control')
        chain_lay.addLayout(r)
        r, self._tip_field, self._tip_btn = _make_field_row('Tip Control')
        chain_lay.addLayout(r)

        self._chain_list = QtWidgets.QListWidget()
        self._chain_list.setSelectionMode(
            QtWidgets.QAbstractItemView.ExtendedSelection)
        self._chain_list.setMaximumHeight(120)
        chain_lay.addWidget(self._chain_list)

        list_btn_row = QtWidgets.QHBoxLayout()
        self._add_btn = QtWidgets.QPushButton('Add Selected')
        self._remove_btn = QtWidgets.QPushButton('Remove Selected')
        list_btn_row.addWidget(self._add_btn)
        list_btn_row.addWidget(self._remove_btn)
        chain_lay.addLayout(list_btn_row)

        order_btn_row = QtWidgets.QHBoxLayout()
        self._parent_walk_btn = QtWidgets.QPushButton('Auto-fill from Parent Walk')
        self._arc_length_btn = QtWidgets.QPushButton('Reorder by Arc Length')
        order_btn_row.addWidget(self._parent_walk_btn)
        order_btn_row.addWidget(self._arc_length_btn)
        chain_lay.addLayout(order_btn_row)

        root.addWidget(chain_box)

        # --- Create ---
        self._create_btn = QtWidgets.QPushButton('Create Curves')
        self._create_btn.setStyleSheet(
            'background-color: #993333; color: white; padding: 6px;')
        root.addWidget(self._create_btn)

        # --- Sliders ---
        slider_box = QtWidgets.QGroupBox('Smooth Controls')
        slider_lay = QtWidgets.QVBoxLayout(slider_box)
        slider_lay.setSpacing(4)

        r, self._strength_slider, self._strength_val = _make_slider_row(
            'Strength', *_SLIDER_RANGES['strength'],
            _SLIDER_DEFAULTS['strength'])
        slider_lay.addLayout(r)
        r, self._blend_slider, self._blend_val = _make_slider_row(
            'Blend', *_SLIDER_RANGES['blend'],
            _SLIDER_DEFAULTS['blend'])
        slider_lay.addLayout(r)
        r, self._falloff_slider, self._falloff_val = _make_slider_row(
            'Falloff', *_SLIDER_RANGES['falloff'],
            _SLIDER_DEFAULTS['falloff'])
        slider_lay.addLayout(r)

        root.addWidget(slider_box)

        # --- Bake ---
        bake_box = QtWidgets.QGroupBox('Bake')
        bake_lay = QtWidgets.QVBoxLayout(bake_box)
        bake_lay.setSpacing(4)

        self._layer_check = QtWidgets.QCheckBox('Bake to Layer')
        self._layer_check.setChecked(True)
        bake_lay.addWidget(self._layer_check)

        btn_row = QtWidgets.QHBoxLayout()
        self._bake_btn = QtWidgets.QPushButton('Bake')
        self._bake_btn.setStyleSheet(
            'background-color: #339933; color: white; padding: 6px;')
        self._reset_btn = QtWidgets.QPushButton('Reset')
        self._reset_btn.setStyleSheet('padding: 6px;')
        btn_row.addWidget(self._bake_btn)
        btn_row.addWidget(self._reset_btn)
        bake_lay.addLayout(btn_row)

        root.addWidget(bake_box)
        root.addStretch(1)

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------

    def _connect_signals(self):
        self._base_btn.clicked.connect(
            lambda: _load_from_selection(self._base_field))
        self._tip_btn.clicked.connect(
            lambda: _load_from_selection(self._tip_field))

        self._add_btn.clicked.connect(self._on_add_selected)
        self._remove_btn.clicked.connect(self._on_remove_selected)
        self._parent_walk_btn.clicked.connect(self._on_parent_walk)
        self._arc_length_btn.clicked.connect(self._on_arc_length)

        self._create_btn.clicked.connect(self._on_create)
        self._bake_btn.clicked.connect(self._on_bake)
        self._reset_btn.clicked.connect(self._on_reset)

        self._strength_slider.valueChanged.connect(self._on_slider_changed)
        self._blend_slider.valueChanged.connect(self._on_slider_changed)
        self._falloff_slider.valueChanged.connect(self._on_slider_changed)

    # ------------------------------------------------------------------
    # Chain list helpers
    # ------------------------------------------------------------------

    def _list_items(self):
        return [self._chain_list.item(i).text()
                for i in range(self._chain_list.count())]

    def _set_list_items(self, items):
        self._chain_list.clear()
        self._chain_list.addItems(items)

    def _on_add_selected(self):
        sel = cmds.ls(selection=True, type='transform')
        if not sel:
            cmds.warning('Select one or more controls to add.')
            return
        existing = self._list_items()
        for s in sel:
            if s not in existing:
                self._chain_list.addItem(s)

    def _on_remove_selected(self):
        for item in self._chain_list.selectedItems():
            self._chain_list.takeItem(self._chain_list.row(item))

    def _on_parent_walk(self):
        base = self._base_field.text().strip()
        tip = self._tip_field.text().strip()
        if not base or not tip:
            cmds.warning('Set Base Control and Tip Control first.')
            return
        try:
            chain = fkchain.order_chain_from_parent_walk(base, tip)
        except RuntimeError as e:
            cmds.warning(str(e))
            return
        self._set_list_items(chain)

    def _on_arc_length(self):
        base = self._base_field.text().strip()
        items = self._list_items()
        if not base:
            cmds.warning('Set Base Control first.')
            return
        if not items:
            cmds.warning('Add controls to the chain list first.')
            return
        try:
            ordered = fkchain.order_chain_by_arc_length(items, base)
        except RuntimeError as e:
            cmds.warning(str(e))
            return
        self._set_list_items(ordered)

    # ------------------------------------------------------------------
    # Create / preview / bake / reset
    # ------------------------------------------------------------------

    def _on_create(self):
        chain = self._list_items()
        if len(chain) < 2:
            cmds.warning('Add at least a base and a tip control to the chain list.')
            return

        tip_field = self._tip_field.text().strip()
        if tip_field and tip_field != chain[-1]:
            cmds.warning(
                'Tip Control ("{}") does not match the last entry in the '
                'chain list ("{}") -- reorder the list or update the Tip '
                'Control field so they agree.'.format(tip_field, chain[-1]))
            return
        tip = chain[-1]

        locked = [a for a in ('tx', 'ty', 'tz', 'rx', 'ry', 'rz')
                  if cmds.getAttr('{}.{}'.format(tip, a), lock=True)]
        if locked:
            cmds.warning('Cannot smooth: locked transforms on "{}": {}'.format(
                tip, ', '.join(locked)))
            return

        try:
            self._solver.set_chain(chain)
            self._solver.sample_rest_pose()
        except RuntimeError as e:
            cmds.warning(str(e))
            return

        start, end = api.SmoothToolCore.get_frame_range()
        self._tip_core.sample_control(tip, start, end)
        self._tip_core.create_curves()

        strength = _slider_value(self._strength_slider, 'strength')
        blend = _slider_value(self._blend_slider, 'blend')
        falloff = _slider_value(self._falloff_slider, 'falloff')
        self._solver.preview(strength=strength, blend=blend, falloff=falloff)

        self._curves_live = True
        cmds.inViewMessage(amg='FK chain preview created.', pos='topCenter',
                           fade=True)

    def _on_slider_changed(self, _value=None):
        if not self._curves_live:
            return
        strength = _slider_value(self._strength_slider, 'strength')
        blend = _slider_value(self._blend_slider, 'blend')
        falloff = _slider_value(self._falloff_slider, 'falloff')
        self._strength_val.setText('{:.2f}'.format(strength))
        self._blend_val.setText('{:.2f}'.format(blend))
        self._falloff_val.setText('{:.2f}'.format(falloff))
        self._solver.preview(strength=strength, blend=blend, falloff=falloff)

    def _on_bake(self):
        if not self._curves_live:
            cmds.warning('Create curves first.')
            return
        to_layer = self._layer_check.isChecked()
        try:
            self._solver.bake(to_layer=to_layer)
            self._curves_live = False
            cmds.inViewMessage(amg='<hl>FK chain bake complete.</hl>',
                               pos='topCenter', fade=True)
        except Exception as e:
            cmds.warning('Bake failed: {}'.format(e))
            raise

    def _on_reset(self):
        self._solver.reset()
        self._tip_core.reset()
        self._solver.set_tip_core(self._tip_core)
        self._curves_live = False

        self._base_field.clear()
        self._tip_field.clear()
        self._chain_list.clear()

        _reset_slider(self._strength_slider, self._strength_val, 'strength')
        _reset_slider(self._blend_slider, self._blend_val, 'blend')
        _reset_slider(self._falloff_slider, self._falloff_val, 'falloff')

        self._layer_check.setChecked(True)

        cmds.inViewMessage(amg='FK Chain tab reset.', pos='topCenter',
                           fade=True)

    def cleanup(self):
        self._solver.cleanup()
        if self._curves_live:
            self._tip_core.delete_curves()


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class SmoothToolUI(QtWidgets.QDialog):

    TITLE = 'Smooth Tool'

    def __init__(self, parent=_maya_main_window()):
        super().__init__(parent)
        self.setWindowTitle(self.TITLE)
        self.setMinimumWidth(380)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.Tool)

        self._single_tab = _SingleControlTab()
        self._fk_chain_tab = _FKChainSmoothTab()

        tabs = QtWidgets.QTabWidget()
        tabs.addTab(self._single_tab, 'Single Control')
        tabs.addTab(self._fk_chain_tab, 'FK Chain')

        root = QtWidgets.QVBoxLayout(self)
        root.addWidget(tabs)

    def closeEvent(self, event):
        self._single_tab.cleanup()
        self._fk_chain_tab.cleanup()
        super().closeEvent(event)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

_instance = None


def show():
    global _instance
    if _instance is not None:
        try:
            _instance.close()
        except RuntimeError:
            pass
    _instance = SmoothToolUI()
    _instance.show()
    return _instance
