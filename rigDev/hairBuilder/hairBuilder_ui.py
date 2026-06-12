"""hairBuilder_ui.py — PySide6 UI for the 6-step hair rig workflow."""
import maya.cmds as cmds
import maya.OpenMayaUI as omui
import shiboken6
from PySide6 import QtWidgets, QtCore
import hairBuilder_api as api

# ── window singleton ──────────────────────────────────────────────────────────

WINDOW_TITLE = 'Hair Builder'
WINDOW_OBJ   = 'hairBuilderUI'


def _maya_main_window():
    ptr = omui.MQtUtil.mainWindow()
    return shiboken6.wrapInstance(int(ptr), QtWidgets.QWidget)


class HairBuilderUI(QtWidgets.QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName(WINDOW_OBJ)
        self.setWindowTitle(WINDOW_TITLE)
        self.setMinimumWidth(320)
        self.setWindowFlags(self.windowFlags() |
                            QtCore.Qt.WindowType.Tool)

        # Runtime state persisted between button presses
        self._prefix       = None
        self._pointNumber  = None
        self._tip_count    = 4
        self._skin_cluster = None
        self._scalp_mesh   = None
        self._scalp_fol    = None

        self._build_ui()

    # ── UI layout ─────────────────────────────────────────────────────────────

    def _build_ui(self):
        outer = QtWidgets.QVBoxLayout(self)
        outer.setSpacing(4)
        outer.setContentsMargins(8, 8, 8, 8)

        # ── options ───────────────────────────────────────────────────────────
        opt_box = QtWidgets.QGroupBox('Options')
        opt_lay = QtWidgets.QFormLayout(opt_box)
        opt_lay.setFieldGrowthPolicy(
            QtWidgets.QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        opt_lay.setSpacing(4)

        self._tip_spin = QtWidgets.QSpinBox()
        self._tip_spin.setRange(1, 12)
        self._tip_spin.setValue(self._tip_count)
        self._tip_spin.setToolTip('Number of daisy-chain FK tip controls '
                                  'above the spine rig')
        opt_lay.addRow('Tip joints:', self._tip_spin)

        self._spans_spin = QtWidgets.QSpinBox()
        self._spans_spin.setRange(1, 16)
        self._spans_spin.setValue(3)
        self._spans_spin.setSingleStep(2)
        self._spans_spin.setToolTip('Surface V spans (odd numbers work best)')
        opt_lay.addRow('Surface spans:', self._spans_spin)
        outer.addWidget(opt_box)

        # ── step buttons ──────────────────────────────────────────────────────
        steps_box = QtWidgets.QGroupBox('Steps')
        steps_lay = QtWidgets.QVBoxLayout(steps_box)
        steps_lay.setSpacing(6)
        outer.addWidget(steps_box)

        btn_defs = [
            ('1 — Build Hair Rig',
             'Select the hair curve, then press to build the full rig.',
             self._on_build),
            ('2 — Skin Hair',
             'Select the hair clump geo, then press to bind it to the SKL chain.',
             self._on_skin),
            ('3 — Position Hair',
             'Select a vertex on the scalp surface, then press to attach the rig.',
             self._on_position),
            ('4 — Bake && Clean',
             'Bake SKL joints, delete the rig and skin cluster.',
             self._on_bake),
            ('5 — Snap Base to Surface',
             'Select the base edge loop, then press to snap verts to the scalp.',
             self._on_snap),
            ('6 — Reskin Hair',
             'Bind the hair clump to the baked SKL joints.',
             self._on_reskin),
        ]
        self._btns = []
        for label, tip, slot in btn_defs:
            btn = QtWidgets.QPushButton(label)
            btn.setToolTip(tip)
            btn.setMinimumHeight(28)
            btn.clicked.connect(slot)
            steps_lay.addWidget(btn)
            self._btns.append(btn)

        # Disable steps 2–6 until rig is built
        for btn in self._btns[1:]:
            btn.setEnabled(False)

        # ── log ───────────────────────────────────────────────────────────────
        self._log = QtWidgets.QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setFixedHeight(80)
        self._log.setPlaceholderText('Messages appear here...')
        outer.addWidget(self._log)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _log_msg(self, msg):
        self._log.appendPlainText(msg)

    def _set_steps_from(self, step_idx):
        """Enable buttons from *step_idx* onward, disable those before."""
        for i, btn in enumerate(self._btns):
            btn.setEnabled(i >= step_idx)

    # ── button slots ─────────────────────────────────────────────────────────

    def _on_build(self):
        sel = cmds.ls(sl=True)
        if not sel:
            self._log_msg('Step 1 — ERROR: Select the hair curve first.')
            return
        prefix = sel[0]
        shapes = cmds.listRelatives(prefix, shapes=True,
                                    noIntermediate=True) or []
        if not shapes or cmds.objectType(shapes[0]) != 'nurbsCurve':
            self._log_msg(f'Step 1 — ERROR: "{prefix}" is not a NURBS curve.')
            return
        tip_count    = self._tip_spin.value()
        surface_spans = self._spans_spin.value()
        self._log_msg(f'Step 1 — Building "{prefix}" '
                      f'({surface_spans} spans, {tip_count} tip joints)...')
        try:
            point_number = api.buildHairRig(prefix,
                                            surface_spans=surface_spans,
                                            tip_count=tip_count)
            self._prefix      = prefix
            self._pointNumber = point_number
            self._tip_count   = tip_count
            self._log_msg(f'Step 1 — Done. Rig built: "{prefix}".')
            self._set_steps_from(1)
        except Exception as e:
            self._log_msg(f'Step 1 — ERROR: {e}')

    def _on_skin(self):
        if not self._prefix:
            self._log_msg('Step 2 — ERROR: Build the rig first (Step 1).')
            return
        sel = cmds.ls(sl=True)
        if not sel:
            self._log_msg('Step 2 — ERROR: Select the hair clump geo first.')
            return
        geo = sel[0]
        self._log_msg(f'Step 2 — Skinning "{geo}" to SKL chain...')
        try:
            sc = api.skin_hair(geo, self._prefix,
                               self._pointNumber, self._tip_count)
            self._skin_cluster = sc
            self._geo           = geo
            self._log_msg(f'Step 2 — Done. skinCluster: "{sc}".')
            self._set_steps_from(2)
        except Exception as e:
            self._log_msg(f'Step 2 — ERROR: {e}')

    def _on_position(self):
        if not self._prefix:
            self._log_msg('Step 3 — ERROR: Build the rig first (Step 1).')
            return
        sel = cmds.ls(sl=True, fl=True)
        if not sel:
            self._log_msg('Step 3 — ERROR: Select a vertex on the scalp surface.')
            return
        vert = sel[0]
        if '.vtx[' not in vert:
            self._log_msg('Step 3 — ERROR: Selection must be a single vertex.')
            return
        self._log_msg(f'Step 3 — Positioning rig on scalp at "{vert}"...')
        try:
            mesh, fol = api.position_hair(self._prefix, vert)
            self._scalp_mesh = mesh
            self._scalp_fol  = fol
            self._log_msg(f'Step 3 — Done. Rig attached to follicle "{fol}".')
            self._set_steps_from(3)
        except Exception as e:
            self._log_msg(f'Step 3 — ERROR: {e}')

    def _on_bake(self):
        if not self._prefix:
            self._log_msg('Step 4 — ERROR: Build the rig first (Step 1).')
            return
        self._log_msg('Step 4 — Baking SKL joints and cleaning rig...')
        try:
            api.bake_and_clean(self._prefix, self._scalp_mesh,
                               self._scalp_fol,
                               self._skin_cluster or '',
                               self._pointNumber, self._tip_count)
            self._log_msg('Step 4 — Done. SKL joints baked; rig removed.')
            self._set_steps_from(4)
        except Exception as e:
            self._log_msg(f'Step 4 — ERROR: {e}')

    def _on_snap(self):
        if not self._scalp_mesh:
            self._log_msg('Step 5 — ERROR: Complete Step 3 first '
                          '(scalp surface not recorded).')
            return
        sel = cmds.ls(sl=True)
        if not sel:
            self._log_msg('Step 5 — ERROR: Select the base edge loop first.')
            return
        self._log_msg('Step 5 — Snapping base verts to scalp surface...')
        try:
            api.snap_base_to_surface(self._scalp_mesh)
            self._log_msg('Step 5 — Done.')
            self._set_steps_from(5)
        except Exception as e:
            self._log_msg(f'Step 5 — ERROR: {e}')

    def _on_reskin(self):
        if not self._prefix:
            self._log_msg('Step 6 — ERROR: Build the rig first (Step 1).')
            return
        geo = getattr(self, '_geo', None)
        if not geo:
            self._log_msg('Step 6 — ERROR: Complete Step 2 first '
                          '(geo not recorded).')
            return
        self._log_msg(f'Step 6 — Reskinning "{geo}" to SKL chain...')
        try:
            sc = api.reskin_hair(geo, self._prefix,
                                 self._pointNumber, self._tip_count)
            self._skin_cluster = sc
            self._log_msg(f'Step 6 — Done. skinCluster: "{sc}".')
        except Exception as e:
            self._log_msg(f'Step 6 — ERROR: {e}')


# ── show ──────────────────────────────────────────────────────────────────────

def show():
    parent = _maya_main_window()
    for widget in parent.findChildren(QtWidgets.QDialog, WINDOW_OBJ):
        widget.close()
        widget.deleteLater()
    win = HairBuilderUI(parent)
    win.show()
    return win
