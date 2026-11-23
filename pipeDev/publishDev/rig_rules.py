"""
Rig rules — the names Publish relies on to recognise MetaHuman, mGear and
Advanced Skeleton parts of a rig. Data only: when a new MetaHuman or mGear
version renames something, edit it here (and bump VERSION) rather than the
tool code (user, 2026-10-20: "we may need to account for metahuman and
mgear updates"). Publish stops with a clear message when a rule finds
nothing, so an out-of-date rule shows up at publish time.

Design: pipeDev/filmPipeline_spec.md §4, "Rig sets: controls and render geo".
"""

VERSION = 2

# The sets a rig publish needs, by the asset's type folder
# (maya\assets\<type>\). The rigger makes them (or the mpRig shelf's Rig
# Sets tool does, on the rigger's say-so); Publish never does. A character
# splits its controls into body and face sets; every other asset
# (environment, prop, vehicle...) has one controls set and no face set
# (user, 2026-11-11). "body" is the required controls set, "face" the
# optional one (required for a MetaHuman).
CACHE_SET = "cache_SET"
CHARACTER_TYPES = ("character",)
CHARACTER_CONTROL_SETS = {"body": "body_controls_SET", "face": "face_controls_SET"}
OTHER_CONTROL_SETS = {"body": "controls_SET", "face": None}

# Names the Rig Sets tool takes as controls when it suggests what goes in
# the controls set (curve transforms only; fnmatch, case sensitive). If no
# curve in the rig matches, every visible curve transform is suggested.
CONTROL_NAMES = ["*_ctl", "*_CTL", "*_Ctl", "*_ctrl", "*_CTRL", "*_Ctrl",
                 "*Ctrl", "CTRL_*", "*_ctl[0-9]*", "*_CTL[0-9]*"]

# A MetaHuman face: its face controls count as face controls automatically
# (Publish adds any missing ones to face_controls_SET in the published file).
# Checked against scoutPrevis_rig_002 (mGear + MetaHuman, 2026-10-20): 181
# CTRL_ transforms under headGui_grp, of which these six are the face board
# itself and utility nodes, not controls -> 175 face controls.
METAHUMAN = {
    "dna_node_type": "embeddedNodeRL4",
    "dna_path_attr": "dnaFilePath",      # can't hold $PIPE_SCRATCH (tested 2026-10-20)
    "face_gui_group": "headGui_grp",
    "control_prefix": "CTRL_",
    "not_controls": [
        "CTRL_faceGUI",
        "CTRL_faceTweakersGUI",
        "CTRL_faceAndEyesAimFollowHeadGUI",
        "CTRL_GUIswitch",
        "CTRL_rigLogic",
        "CTRL_expressions",
    ],
}

# Sets other rigging tools make, named in Publish's messages so the rigger
# knows what to drop into the pipe's sets (sets can hold sets). Patterns
# match the set's name without namespace (fnmatch). The role says which
# pipe set it belongs in ("body", "face", or None = neither); {body} and
# {face} in the text become that asset's set names (a non-character's face
# controls go in its one controls set).
KNOWN_SETS = [
    ("*_controllers_grp", "body", "mGear's controllers set: put it in {body}"),
    ("FacialControls", "face", "looks like face controls: put it in {face}"),
    ("ControlSet", "body", "Advanced Skeleton's controls set: put it in {body}"),
    ("FaceControlSet", "face", "Advanced Skeleton's face controls set: put it in {face}"),
    ("AllSet", None, "Advanced Skeleton's AllSet holds every rig node, not just controls: don't use it"),
]


def control_sets_for(asset_type):
    """{"body": name, "face": name or None} for an asset type folder
    (e.g. "character", "prop"). None = character (the strictest)."""
    if asset_type is None or asset_type.lower() in CHARACTER_TYPES:
        return dict(CHARACTER_CONTROL_SETS)
    return dict(OTHER_CONTROL_SETS)


def known_set_text(text, asset_type):
    names = control_sets_for(asset_type)
    return text.format(body=names["body"], face=names["face"] or names["body"])
