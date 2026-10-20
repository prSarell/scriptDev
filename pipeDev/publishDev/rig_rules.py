"""
Rig rules — the names Publish relies on to recognise MetaHuman, mGear and
Advanced Skeleton parts of a rig. Data only: when a new MetaHuman or mGear
version renames something, edit it here (and bump VERSION) rather than the
tool code (user, 2026-10-20: "we may need to account for metahuman and
mgear updates"). Publish stops with a clear message when a rule finds
nothing, so an out-of-date rule shows up at publish time.

Design: pipeDev/filmPipeline_spec.md §4, "Rig sets: controls and render geo".
"""

VERSION = 1

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
# match the set's name without namespace (fnmatch).
KNOWN_SETS = [
    ("*_controllers_grp", "mGear's controllers set: put it in body_controls_SET"),
    ("FacialControls", "looks like face controls: put it in face_controls_SET"),
    ("ControlSet", "Advanced Skeleton's controls set: put it in body_controls_SET"),
    ("FaceControlSet", "Advanced Skeleton's face controls set: put it in face_controls_SET"),
    ("AllSet", "Advanced Skeleton's AllSet holds every rig node, not just controls: don't use it"),
]
