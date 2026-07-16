"""
Smooth Tool — UI
PySide6 interface for smoothTool_api.
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


def _maya_main_window():
    ptr = omui.MQtUtil.mainWindow()
    return shiboken6.wrapInstance(int(ptr), QtWidgets.QWidget)


# ---------------------------------------------------------------------------
# Helpers
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


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

class SmoothToolUI(QtWidgets.QDialog):

    TITLE = 'Smooth Tool'

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

    def __init__(self, parent=_maya_main_window()):
        super().__init__(parent)
        self.setWindowTitle(self.TITLE)
        self.setMinimumWidth(380)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.Tool)

        self._core = api.SmoothToolCore()
        self._curves_live = False

        self._build_ui()
        self._connect_signals()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setSpacing(8)

        # --- Source / Target ---
        source_box = QtWidgets.QGroupBox('Objects')
        source_lay = QtWidgets.QVBoxLayout(source_box)
        source_lay.setSpacing(4)

        r, self._mesh_field, self._mesh_btn = _make_field_row('Source Mesh')
        source_lay.addLayout(r)
        r, self._target_field, self._target_btn = _make_field_row('Bake Target')
        source_lay.addLayout(r)
        r, self._parent_field, self._parent_btn = _make_field_row('Parent Space')
        source_lay.addLayout(r)

        self._vert_mode = QtWidgets.QComboBox()
        self._vert_mode.addItems(['Auto-pick vertices', 'Use selected vertices'])
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
            'Strength', *self._SLIDER_RANGES['strength'],
            self._SLIDER_DEFAULTS['strength'])
        slider_lay.addLayout(r)
        r, self._blend_slider, self._blend_val = _make_slider_row(
            'Blend', *self._SLIDER_RANGES['blend'],
            self._SLIDER_DEFAULTS['blend'])
        slider_lay.addLayout(r)
        r, self._falloff_slider, self._falloff_val = _make_slider_row(
            'Falloff', *self._SLIDER_RANGES['falloff'],
            self._SLIDER_DEFAULTS['falloff'])
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

    # ------------------------------------------------------------------
    # Slider value helpers
    # ------------------------------------------------------------------

    def _slider_value(self, slider, key):
        lo, hi = self._SLIDER_RANGES[key]
        return lo + (slider.value() / 1000.0) * (hi - lo)

    def _reset_slider(self, slider, val_label, key):
        lo, hi = self._SLIDER_RANGES[key]
        default = self._SLIDER_DEFAULTS[key]
        frac = (default - lo) / (hi - lo)
        slider.setValue(int(frac * 1000))
        val_label.setText('{:.2f}'.format(default))

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
                cmds.warning('Select an object or fill in Source Mesh.')
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

        if self._vert_mode.currentIndex() == 1:
            try:
                sel_mesh, indices = api.SmoothToolCore.indices_from_selection()
                if sel_mesh != mesh:
                    cmds.warning(
                        'Selected vertices are not on the source mesh.')
                    return
            except RuntimeError as e:
                cmds.warning(str(e))
                return
        else:
            indices = api.SmoothToolCore.find_spread_vertices(mesh)

        start, end = api.SmoothToolCore.get_frame_range()
        self._core.sample(mesh, indices, target, start, end, parent=parent)
        self._core.create_curves()

        strength = self._slider_value(self._strength_slider, 'strength')
        self._core.falloff = self._slider_value(
            self._falloff_slider, 'falloff')
        self._core.blend = self._slider_value(self._blend_slider, 'blend')
        self._core.update_smooth(strength)

        self._curves_live = True
        cmds.inViewMessage(amg='Smooth curves created.', pos='topCenter',
                           fade=True)

    def _on_strength(self, _):
        if not self._curves_live:
            return
        val = self._slider_value(self._strength_slider, 'strength')
        self._strength_val.setText('{:.2f}'.format(val))
        self._core.update_smooth(val)

    def _on_blend(self, _):
        if not self._curves_live:
            return
        val = self._slider_value(self._blend_slider, 'blend')
        self._blend_val.setText('{:.2f}'.format(val))
        self._core.update_blend(val)

    def _on_falloff(self, _):
        if not self._curves_live:
            return
        val = self._slider_value(self._falloff_slider, 'falloff')
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

        self._reset_slider(self._strength_slider, self._strength_val, 'strength')
        self._reset_slider(self._blend_slider, self._blend_val, 'blend')
        self._reset_slider(self._falloff_slider, self._falloff_val, 'falloff')

        self._layer_check.setChecked(True)
        self._additive_check.setChecked(True)

        cmds.inViewMessage(amg='Smooth tool reset.', pos='topCenter',
                           fade=True)

    def closeEvent(self, event):
        if self._curves_live:
            self._core.delete_curves()
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
