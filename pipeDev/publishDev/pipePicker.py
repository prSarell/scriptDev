"""
Pipe Picker — the row of dropdowns the Publish and Build tools share
(user, 2026-10-22): how a student says what they're publishing or building.

    Film | Asset or Shot | Department | Type or Sequence | Asset or Shot   [-] [+]

Asset or Shot is the student's choice; the Department list shows only
that side's departments (Rigging is an asset department, Animation a shot
one). The last two list what the tool says fits: asset types and assets,
or sequences and shots.
+ adds the picked thing to the tool's list, - takes the highlighted rows
off it. Each tool does the adding and removing itself.
"""

from PySide6 import QtWidgets, QtCore, QtGui

ASSET, SHOT = "asset", "shot"
# A department listed whatever Asset or Shot says (Build's fixed department
# list, user 2026-10-30); the last two dropdowns follow Asset or Shot.
ANY = "any"
KIND_LABELS = ((ASSET, "Asset"), (SHOT, "Shot"))
# What the last two dropdowns hold, by kind (their tooltips).
GROUP_LABELS = {ASSET: ("Asset type", "Asset"), SHOT: ("Sequence", "Shot")}
NONE_TEXT = "(none)"
PICK_TEXT = "(pick one)"


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
    """departments: [(label, code, kind, live[, lists])], kind ASSET or SHOT
    (the side it's listed under); not live shows as "(coming soon)";
    lists, ASSET or SHOT, what the last two dropdowns hold when it's not
    the same as the side (Environment is listed under Shot but publishes
    to an environment asset, user 2026-10-26). items_for(film, code, lists)
    returns the [(group, name)] that fit, group being the asset type or
    sequence."""

    add_clicked = QtCore.Signal()
    remove_clicked = QtCore.Signal()

    def __init__(self, departments, items_for, parent=None):
        super(TargetPicker, self).__init__(parent)
        self._take_departments(departments)
        self._items_for = items_for
        self._items = []
        # False: the last dropdown starts on "(pick one)" instead of the
        # first name, so nothing is chosen by default (user, 2026-10-26: a
        # scene was saved into ATKS just because it was listed first).
        self.pick_first = True

        self.film_combo = QtWidgets.QComboBox()
        self.film_combo.setToolTip("Film")
        self.kind_combo = QtWidgets.QComboBox()
        self._fill_kinds()
        self.kind_combo.setToolTip("Asset or Shot: sets which departments are listed.")
        self.dept_combo = QtWidgets.QComboBox()
        self.dept_combo.setToolTip("Department")
        self._fill_departments()
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
        for combo in (self.film_combo, self.kind_combo, self.dept_combo, self.group_combo):
            row.addWidget(combo)
        row.addWidget(self.name_combo, 1)
        row.addWidget(self.remove_btn)
        row.addWidget(self.add_btn)

        self.film_combo.currentIndexChanged.connect(lambda *_: self.refill())
        self.kind_combo.currentIndexChanged.connect(lambda *_: self._fill_departments(True))
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
        return self.kind_combo.currentData() or ASSET

    def group(self):
        return self.group_combo.currentData()

    def name(self):
        return self.name_combo.currentData()

    # -- filling ----------------------------------------------------------

    def set_films(self, films, film=None):
        _set_items(self.film_combo, [(f, f, True) for f in films], film or self.film())
        self.refill()

    def set_current(self, film=None, code=None, group=None, name=None, kind=None):
        """Pick these (any left out stay as they are), e.g. what the open
        scene is. A department also picks its side, Asset or Shot, unless
        it's listed on both (ANY): then kind says."""
        side = kind or self._kinds.get(code)
        for combo, data in ((self.film_combo, film), (self.kind_combo, side)):
            index = combo.findData(data) if data else -1
            if index >= 0:
                combo.blockSignals(True)
                combo.setCurrentIndex(index)
                combo.blockSignals(False)
        if code in self._kinds or kind:
            self._fill_departments(code=code)
        self.refill(group, name)

    def _take_departments(self, departments):
        self._departments = departments
        self._kinds = dict((d[1], d[2]) for d in departments)
        self._lists = dict((d[1], d[4] if len(d) > 4 else d[2]) for d in departments)

    def _fill_kinds(self):
        """Asset and Shot, a side with nothing listed under it greyed out."""
        sides = set(self._kinds.values())
        if ANY in sides:
            sides |= set(kind for kind, _ in KIND_LABELS)
        _set_items(self.kind_combo, [(label, kind, kind in sides) for kind, label in KIND_LABELS],
                   self.kind() if self.kind() in sides else None)

    def set_departments(self, departments):
        """Swap the Department list (Build's department filter, user
        2026-10-28), keeping what's picked where it's still listed, else
        moving to a side that has something."""
        code = self.department()
        self._take_departments(departments)
        self._fill_kinds()
        if code in self._kinds:
            self.set_current(code=code)
        else:
            self._fill_departments(True)

    def _fill_departments(self, refill=False, code=None):
        """The departments on the picked side (Asset or Shot), keeping the
        current one if it's there."""
        kind = self.kind()
        _set_items(self.dept_combo, [(label if live else "%s (coming soon)" % label, c, live)
                                     for label, c, k, live in (d[:4] for d in self._departments)
                                     if k in (kind, ANY)],
                   code or self.department())
        if refill:
            self.refill()

    def refill(self, group=None, name=None):
        """Re-read what fits the film, side and department."""
        film, code = self.film(), self.department()
        lists = self._lists.get(code, self.kind())
        if lists == ANY:
            lists = self.kind()
        group_label, name_label = GROUP_LABELS[lists]
        self.group_combo.setToolTip(group_label)
        self.name_combo.setToolTip(name_label)
        self._items = list(self._items_for(film, code, lists)) if film and code else []
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
        items = [(n, n, True) for n in names]
        if items and not self.pick_first:
            items.insert(0, (PICK_TEXT, None, True))
        _set_items(self.name_combo, items or [(NONE_TEXT, None, False)], name or self.name())


# ---------------------------------------------------------------------------
# Open scene vs Maya project (user, 2026-10-28): when they're in different
# shots or assets, Build and Publish show this red banner above the list,
# and ask before building or publishing ("warn, but let me carry on").
# The text comes from publishTool_api.mismatch_text.
# ---------------------------------------------------------------------------

class ProjectBanner(QtWidgets.QFrame):
    """Red banner with a 'Set Project to the scene's' button. Hidden until
    show_mismatch is given some text."""

    def __init__(self, on_match, parent=None):
        super(ProjectBanner, self).__init__(parent)
        self.setStyleSheet("ProjectBanner { background: #5a1f1f; border: 2px solid #e05050; "
                           "border-radius: 4px; }")
        self.label = QtWidgets.QLabel()
        self.label.setWordWrap(True)
        self.label.setTextFormat(QtCore.Qt.RichText)
        font = QtGui.QFont()
        font.setPointSize(10)
        font.setBold(True)
        self.label.setFont(font)
        self.label.setStyleSheet("color: #ffb3ab; background: transparent; border: none;")
        self.match_btn = QtWidgets.QPushButton("Set Project to the scene's")
        self.match_btn.setToolTip("Set the Maya project to the shot or asset the open scene "
                                  "is in, so they match.")
        self.match_btn.clicked.connect(on_match)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.addWidget(self.label, 1)
        layout.addWidget(self.match_btn)
        self.hide()

    def show_mismatch(self, text):
        """text: the banner's rich text, or None to hide it."""
        self.label.setText(text or "")
        self.setVisible(bool(text))


def confirm_mismatch(parent, text, action):
    """Ask before acting on a scene that isn't in the Maya project. True to
    carry on. action: the button's word ("Publish", "Build")."""
    box = QtWidgets.QMessageBox(parent)
    box.setIcon(QtWidgets.QMessageBox.Warning)
    box.setWindowTitle("Scene and project don't match")
    box.setTextFormat(QtCore.Qt.RichText)
    box.setText(text + "<br><br>%s anyway?" % action)
    go = box.addButton("%s Anyway" % action, QtWidgets.QMessageBox.AcceptRole)
    box.addButton(QtWidgets.QMessageBox.Cancel)
    box.setDefaultButton(QtWidgets.QMessageBox.Cancel)
    box.exec()
    return box.clickedButton() == go
