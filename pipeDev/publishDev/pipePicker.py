"""
Pipe Picker — the row of dropdowns the Publish and Build tools share
(user, 2026-10-22): how a student says what they're publishing or building.

    Film | Department | Asset or Shot | Type or Sequence | Asset or Shot   [-] [+]

The department decides Asset or Shot (Rigging is always an asset,
Animation always a shot), so that dropdown follows it. The last two list
what the tool says fits: asset types and assets, or sequences and shots.
+ adds the picked thing to the tool's list, - takes the highlighted rows
off it. Each tool does the adding and removing itself.
"""

from PySide6 import QtWidgets, QtCore, QtGui

ASSET, SHOT = "asset", "shot"
KIND_LABELS = ((ASSET, "Asset"), (SHOT, "Shot"))
# What the last two dropdowns hold, by kind (their tooltips).
GROUP_LABELS = {ASSET: ("Asset type", "Asset"), SHOT: ("Sequence", "Shot")}
NONE_TEXT = "(none)"


def _model(parent, items):
    """A dropdown model of (label, data, enabled) items."""
    model = QtGui.QStandardItemModel(parent)
    for label, data, enabled in items:
        item = QtGui.QStandardItem(label)
        item.setData(data, QtCore.Qt.UserRole)
        item.setEnabled(enabled)
        model.appendRow(item)
    return model


def _set_items(combo, items, keep=None):
    """Refill a dropdown without signals, keeping 'keep' picked if it's
    still there (else the first enabled item)."""
    combo.blockSignals(True)
    combo.setModel(_model(combo, items))
    index = combo.findData(keep) if keep is not None else -1
    if index < 0:
        index = next((i for i, (_, _, enabled) in enumerate(items) if enabled), 0)
    combo.setCurrentIndex(index)
    combo.blockSignals(False)


class TargetPicker(QtWidgets.QWidget):
    """departments: [(label, code, kind, live)], kind ASSET or SHOT; not
    live shows as "(coming soon)". items_for(film, code, kind) returns the
    [(group, name)] that fit, group being the asset type or sequence."""

    add_clicked = QtCore.Signal()
    remove_clicked = QtCore.Signal()

    def __init__(self, departments, items_for, parent=None):
        super(TargetPicker, self).__init__(parent)
        self._departments = departments
        self._kinds = dict((code, kind) for _, code, kind, _ in departments)
        self._items_for = items_for
        self._items = []

        self.film_combo = QtWidgets.QComboBox()
        self.film_combo.setToolTip("Film")
        self.dept_combo = QtWidgets.QComboBox()
        self.dept_combo.setToolTip("Department")
        _set_items(self.dept_combo, [(label if live else "%s (coming soon)" % label, code, live)
                                     for label, code, _, live in departments])
        self.kind_combo = QtWidgets.QComboBox()
        _set_items(self.kind_combo, [(label, kind, True) for kind, label in KIND_LABELS])
        self.kind_combo.setEnabled(False)
        self.kind_combo.setToolTip("Set by the department: Rigging is always an asset, "
                                   "Animation always a shot.")
        self.group_combo = QtWidgets.QComboBox()
        self.name_combo = QtWidgets.QComboBox()
        self.name_combo.setMinimumWidth(160)
        self.remove_btn = QtWidgets.QPushButton("-")
        self.add_btn = QtWidgets.QPushButton("+")
        for button in (self.remove_btn, self.add_btn):
            button.setFixedWidth(30)
        self.remove_btn.setToolTip("Take the highlighted rows off the list.")
        self.add_btn.setToolTip("Add what's picked here to the list.")

        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        for combo in (self.film_combo, self.dept_combo, self.kind_combo, self.group_combo):
            row.addWidget(combo)
        row.addWidget(self.name_combo, 1)
        row.addWidget(self.remove_btn)
        row.addWidget(self.add_btn)

        self.film_combo.currentIndexChanged.connect(lambda *_: self.refill())
        self.dept_combo.currentIndexChanged.connect(lambda *_: self.refill())
        self.group_combo.currentIndexChanged.connect(lambda *_: self._fill_names())
        self.remove_btn.clicked.connect(self.remove_clicked)
        self.add_btn.clicked.connect(self.add_clicked)

    # -- what's picked ----------------------------------------------------

    def film(self):
        return self.film_combo.currentData()

    def department(self):
        return self.dept_combo.currentData()

    def kind(self):
        return self._kinds.get(self.department(), ASSET)

    def group(self):
        return self.group_combo.currentData()

    def name(self):
        return self.name_combo.currentData()

    # -- filling ----------------------------------------------------------

    def set_films(self, films, film=None):
        _set_items(self.film_combo, [(f, f, True) for f in films], film or self.film())
        self.refill()

    def set_current(self, film=None, code=None, group=None, name=None):
        """Pick these (any left out stay as they are), e.g. what the open
        scene is."""
        for combo, data in ((self.film_combo, film), (self.dept_combo, code)):
            index = combo.findData(data) if data else -1
            if index >= 0:
                combo.blockSignals(True)
                combo.setCurrentIndex(index)
                combo.blockSignals(False)
        self.refill(group, name)

    def refill(self, group=None, name=None):
        """Re-read what fits the film and department."""
        kind = self.kind()
        self.kind_combo.setCurrentIndex(self.kind_combo.findData(kind))
        group_label, name_label = GROUP_LABELS[kind]
        self.group_combo.setToolTip(group_label)
        self.name_combo.setToolTip(name_label)
        film, code = self.film(), self.department()
        self._items = list(self._items_for(film, code, kind)) if film and code else []
        groups = []
        for g, _ in self._items:
            if g not in groups:
                groups.append(g)
        _set_items(self.group_combo, [(g, g, True) for g in groups] or [(NONE_TEXT, None, False)],
                   group or self.group())
        self._fill_names(name)

    def _fill_names(self, name=None):
        group = self.group()
        names = [n for g, n in self._items if g == group]
        _set_items(self.name_combo, [(n, n, True) for n in names] or [(NONE_TEXT, None, False)],
                   name or self.name())
