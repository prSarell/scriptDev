# ps_namespace_stripper.py
# Maya UI tool:
# - Strip namespaces from selected objects (optional hierarchy)
# - Add prefix/suffix
# - Revert names to original (stored on nodes)
#
# Key points:
# - Supports transforms AND joints (joints are nodeType "joint")
# - Safe renaming (handles name collisions with _01, _02...)
# - UI refresh suspension during rename to avoid Property Panel / AE stale-path errors
#
# Usage (Script Editor, Python tab):
#   import importlib
#   import ps_namespace_stripper
#   importlib.reload(ps_namespace_stripper)
#   ps_namespace_stripper.show()

import re
import maya.cmds as cmds

_WINDOW = "psNamespaceStripperWin"
_ORIGINAL_NAME_ATTR = "psOriginalName"  # string attr stored on nodes


def _short_name(dag_path):
    return dag_path.split("|")[-1] if dag_path else dag_path


def _strip_namespace(name):
    return name.split(":")[-1] if ":" in name else name


def _is_transform_like(node):
    # Joints are nodeType "joint" but are valid DAG rename targets.
    try:
        return cmds.nodeType(node) in ("transform", "joint")
    except Exception:
        return False


def _safe_unique_name(target_leaf_name, parent=None):
    """
    Ensure a unique leaf name.
    - If parent is provided, uniqueness is checked among that parent's children.
    - Otherwise checks globally in scene.
    """
    base = (target_leaf_name or "node").strip()
    if not base:
        base = "node"

    def exists_in_parent(p, leaf):
        if not p:
            return cmds.objExists(leaf)
        kids = cmds.listRelatives(p, children=True, fullPath=False) or []
        return leaf in kids

    if not exists_in_parent(parent, base):
        return base

    i = 1
    while True:
        candidate = f"{base}_{i:02d}"
        if not exists_in_parent(parent, candidate):
            return candidate
        i += 1


def _ensure_original_attr(node):
    if not cmds.objExists(node):
        return
    if not cmds.attributeQuery(_ORIGINAL_NAME_ATTR, node=node, exists=True):
        cmds.addAttr(node, longName=_ORIGINAL_NAME_ATTR, dataType="string")


def _store_original_name(node, original_leaf):
    """
    Store original leaf name ONCE so revert can restore the true original.
    """
    _ensure_original_attr(node)
    try:
        current = cmds.getAttr(f"{node}.{_ORIGINAL_NAME_ATTR}") or ""
    except Exception:
        current = ""

    if not current:
        try:
            cmds.setAttr(f"{node}.{_ORIGINAL_NAME_ATTR}", original_leaf, type="string")
        except Exception:
            pass


def _get_stored_original(node):
    if not cmds.objExists(node):
        return ""
    if not cmds.attributeQuery(_ORIGINAL_NAME_ATTR, node=node, exists=True):
        return ""
    try:
        return cmds.getAttr(f"{node}.{_ORIGINAL_NAME_ATTR}") or ""
    except Exception:
        return ""


def _clear_stored_original(node):
    if not cmds.objExists(node):
        return
    if cmds.attributeQuery(_ORIGINAL_NAME_ATTR, node=node, exists=True):
        try:
            cmds.setAttr(f"{node}.{_ORIGINAL_NAME_ATTR}", "", type="string")
        except Exception:
            pass


def _selection_to_nodes(selection):
    """
    Convert selection items (components/shapes/transforms/joints) into owning DAG nodes.
    Returns long paths where possible.
    """
    nodes = []
    for s in selection:
        if not cmds.objExists(s):
            continue

        # For components like pCube1.vtx[0], this returns the owning object.
        owning = cmds.ls(s, o=True, long=True) or [s]
        node = owning[0]

        if not cmds.objExists(node):
            continue

        # If not transform-like, try parent (e.g. shape -> transform)
        if not _is_transform_like(node):
            parents = cmds.listRelatives(node, parent=True, fullPath=True) or []
            if parents:
                node = parents[0]

        if cmds.objExists(node) and _is_transform_like(node):
            nodes.append(node)

    # unique, preserve order
    return list(dict.fromkeys(nodes))


def _get_targets(selection, include_hierarchy):
    """
    Return full DAG paths for rename targets.
    - Accepts transforms AND joints.
    - Optional: include hierarchy (descendants that are transform/joint).
    - Renames deepest-first to minimize DAG path invalidation issues.
    """
    if not selection:
        return []

    roots = _selection_to_nodes(selection)
    if not roots:
        return []

    if not include_hierarchy:
        return roots

    all_targets = []
    for r in roots:
        all_targets.append(r)
        descendants = cmds.listRelatives(r, allDescendents=True, fullPath=True) or []
        for d in descendants:
            if cmds.objExists(d) and _is_transform_like(d):
                all_targets.append(d)

    all_targets = list(dict.fromkeys(all_targets))
    all_targets.sort(key=lambda p: p.count("|"), reverse=True)  # deepest first
    return all_targets


def _rename_targets(targets, prefix, suffix, strip_ns=True):
    """
    Rename targets safely, storing original names.
    Returns: (renamed_count, errors_list, new_nodes_fullpaths)
    """
    renamed = 0
    errors = []
    new_nodes = []

    for fullpath in targets:
        if not cmds.objExists(fullpath):
            continue

        leaf = _short_name(fullpath)
        parent = "|".join(fullpath.split("|")[:-1]) if "|" in fullpath else None
        original_leaf = leaf

        _store_original_name(fullpath, original_leaf)

        new_leaf = _strip_namespace(leaf) if strip_ns else leaf
        new_leaf = f"{prefix}{new_leaf}{suffix}"
        new_leaf = re.sub(r"\s+", "_", new_leaf).strip("_")

        if not new_leaf or new_leaf == leaf:
            continue

        new_leaf_unique = _safe_unique_name(new_leaf, parent=parent)

        try:
            new_full = cmds.rename(fullpath, new_leaf_unique)
            renamed += 1
            new_nodes.append(new_full)
        except Exception as e:
            errors.append(f"{fullpath}  ->  {new_leaf_unique}  ({e})")

    return renamed, errors, new_nodes


def _revert_targets(targets):
    """
    Revert to stored original names (if present).
    Returns: (reverted_count, errors_list, new_nodes_fullpaths)
    """
    reverted = 0
    errors = []
    new_nodes = []

    for fullpath in targets:
        if not cmds.objExists(fullpath):
            continue

        original_leaf = _get_stored_original(fullpath)
        if not original_leaf:
            continue

        parent = "|".join(fullpath.split("|")[:-1]) if "|" in fullpath else None
        current_leaf = _short_name(fullpath)

        if original_leaf == current_leaf:
            continue

        original_leaf_unique = _safe_unique_name(original_leaf, parent=parent)

        try:
            new_full = cmds.rename(fullpath, original_leaf_unique)
            reverted += 1
            new_nodes.append(new_full)
        except Exception as e:
            errors.append(f"{fullpath}  ->  {original_leaf_unique}  ({e})")

    return reverted, errors, new_nodes


def _ui_print(msg):
    try:
        cmds.inViewMessage(amg=msg, pos="midCenterTop", fade=True)
    except Exception:
        print(msg)


def _run_with_ui_suspension(work_fn):
    """
    Prevent Property Panel / AE from querying stale names mid-rename.
    - store selection
    - clear selection
    - suspend refresh
    - run work_fn
    - resume refresh
    - reselect returned nodes (if any) else restore previous selection
    """
    prev_sel = cmds.ls(sl=True, long=True) or []
    try:
        cmds.select(clear=True)
    except Exception:
        pass

    cmds.undoInfo(openChunk=True)
    try:
        cmds.refresh(suspend=True)
        result = work_fn()
    finally:
        cmds.refresh(suspend=False)
        cmds.undoInfo(closeChunk=True)

    # Let UI catch up
    try:
        cmds.evalDeferred("import maya.cmds as cmds; cmds.refresh(f=True)")
    except Exception:
        pass

    try:
        if isinstance(result, (list, tuple)) and result:
            cmds.select(list(result), replace=True)
        elif prev_sel:
            cmds.select(prev_sel, replace=True)
    except Exception:
        pass

    return result


def show():
    if cmds.window(_WINDOW, exists=True):
        cmds.deleteUI(_WINDOW)

    cmds.window(_WINDOW, title="Namespace Stripper + Prefix/Suffix", sizeable=False)
    cmds.columnLayout(adj=True, rowSpacing=8)

    cmds.text(
        label="Rename selected nodes (Transforms + Joints).\n"
              "Optionally includes hierarchy. Stores original names for Revert.",
        align="left"
    )

    cmds.separator(h=8, style="in")

    include_hierarchy_chk = cmds.checkBox(
        label="Include hierarchy (selected + all descendant transforms/joints)",
        value=True
    )
    strip_ns_chk = cmds.checkBox(
        label="Strip namespaces (a:b:c -> c)",
        value=True
    )

    cmds.separator(h=8, style="in")

    cmds.rowLayout(numberOfColumns=2, adjustableColumn=2, columnAlign=(1, "right"), columnAttach=(1, "both", 0))
    cmds.text(label="Prefix:")
    prefix_field = cmds.textField(text="")
    cmds.setParent("..")

    cmds.rowLayout(numberOfColumns=2, adjustableColumn=2, columnAlign=(1, "right"), columnAttach=(1, "both", 0))
    cmds.text(label="Suffix:")
    suffix_field = cmds.textField(text="")
    cmds.setParent("..")

    cmds.separator(h=10, style="in")

    def do_apply(*_):
        sel = cmds.ls(sl=True, long=True) or []
        if not sel:
            _ui_print("<span style='color:#ffaaaa'>Nothing selected.</span>")
            return

        include_hierarchy = cmds.checkBox(include_hierarchy_chk, q=True, value=True)
        strip_ns = cmds.checkBox(strip_ns_chk, q=True, value=True)
        prefix = cmds.textField(prefix_field, q=True, text=True) or ""
        suffix = cmds.textField(suffix_field, q=True, text=True) or ""

        targets = _get_targets(sel, include_hierarchy)
        if not targets:
            _ui_print("<span style='color:#ffaaaa'>No valid transform/joint targets found.</span>")
            return

        def _work():
            count, errors, new_nodes = _rename_targets(targets, prefix, suffix, strip_ns=strip_ns)

            if errors:
                print("---- Namespace Stripper: Errors ----")
                for e in errors:
                    print(e)

            _ui_print(
                f"<span style='color:#aaffaa'>Renamed:</span> {count}   "
                f"<span style='color:#aaaaff'>Targets:</span> {len(targets)}   "
                f"<span style='color:#ffddaa'>Errors:</span> {len(errors)}"
            )
            return new_nodes

        _run_with_ui_suspension(_work)

    def do_revert(*_):
        sel = cmds.ls(sl=True, long=True) or []
        if not sel:
            _ui_print("<span style='color:#ffaaaa'>Nothing selected.</span>")
            return

        include_hierarchy = cmds.checkBox(include_hierarchy_chk, q=True, value=True)
        targets = _get_targets(sel, include_hierarchy)
        if not targets:
            _ui_print("<span style='color:#ffaaaa'>No valid transform/joint targets found.</span>")
            return

        def _work():
            count, errors, new_nodes = _revert_targets(targets)

            if errors:
                print("---- Namespace Stripper: Revert Errors ----")
                for e in errors:
                    print(e)

            _ui_print(
                f"<span style='color:#aaffaa'>Reverted:</span> {count}   "
                f"<span style='color:#aaaaff'>Targets:</span> {len(targets)}   "
                f"<span style='color:#ffddaa'>Errors:</span> {len(errors)}"
            )
            return new_nodes

        _run_with_ui_suspension(_work)

    def do_clear_original(*_):
        sel = cmds.ls(sl=True, long=True) or []
        if not sel:
            _ui_print("<span style='color:#ffaaaa'>Nothing selected.</span>")
            return

        include_hierarchy = cmds.checkBox(include_hierarchy_chk, q=True, value=True)
        targets = _get_targets(sel, include_hierarchy)

        cmds.undoInfo(openChunk=True)
        try:
            cleared = 0
            for t in targets:
                if cmds.objExists(t) and cmds.attributeQuery(_ORIGINAL_NAME_ATTR, node=t, exists=True):
                    _clear_stored_original(t)
                    cleared += 1
        finally:
            cmds.undoInfo(closeChunk=True)

        _ui_print(f"Cleared stored originals on {cleared} nodes.")

    cmds.rowLayout(
        numberOfColumns=2,
        adjustableColumn=1,
        columnAttach=[(1, "both", 0), (2, "both", 0)],
        columnWidth=[(1, 220), (2, 220)]
    )
    cmds.button(label="Apply (Strip + Prefix/Suffix)", height=34, command=do_apply)
    cmds.button(label="Revert to Original", height=34, command=do_revert)
    cmds.setParent("..")

    cmds.button(label="Clear Stored Originals (optional)", height=26, command=do_clear_original)

    cmds.separator(h=8, style="none")
    cmds.text(
        label="Original names are stored on nodes via string attr: psOriginalName",
        align="left",
        font="smallPlainLabelFont"
    )

    cmds.showWindow(_WINDOW)