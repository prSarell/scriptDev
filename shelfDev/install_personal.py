# install_personal.py
# Drag onto Maya viewport to install mpAnim + mpRig shelves for personal dev.
#
# All shelf buttons load directly from dev folders — no Python files are copied.
# Re-run any time after moving the scriptDev folder or adding a new button.
#
# What this does:
#   - Copies custom icons to Maya's bitmaps dir
#   - Creates mpAnim and mpRig shelf buttons (wired to dev paths)
#   - Patches userSetup.py so multiTool auto-loads and key paths are on sys.path

import os


def _install():
    import shutil
    import maya.cmds as cmds
    import maya.mel as mel

    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.normpath(os.path.join(here, ".."))

    # Dev folder for each tool — all paths computed relative to this file
    P = {
        "anim_tools":    os.path.join(here, "mpAnim", "tools"),
        "multitool":     os.path.join(root, "animDev", "multiTool"),
        "jiffypomo":     os.path.join(root, "timeManagementDev", "jiffyPomoDev"),
        "jiffyschedule": os.path.join(root, "timeManagementDev", "jiffyScheduleDev"),
        "clothchain":    os.path.join(root, "simDev", "tmClothSimToolDev"),
        "correctivebs":  os.path.join(root, "rigDev", "correctiveBSToolDev"),
        "rigdev":        os.path.join(root, "rigDev"),
        "metahuman":     os.path.join(root, "metahuman_facial_transfer"),
        "studiolib":     os.path.join(root, "animDev", "studiolibrary-2.20.2", "src"),
    }

    def _cmd(path, clear_tags, body):
        """Build a shelf button command that injects a dev path and clears stale modules."""
        lines = [
            "import importlib, sys",
            f"_p = r'{path}'",
            "if _p not in sys.path:",
            "    sys.path.insert(0, _p)",
        ]
        if clear_tags:
            tags = ", ".join(f"'{t}'" for t in clear_tags)
            lines += [
                f"for _k in list(sys.modules.keys()):",
                f"    if any(_k == t or _k.startswith(t) for t in [{tags}]):",
                f"        del sys.modules[_k]",
            ]
        lines.append(body)
        return "\n".join(lines)

    SHELVES = {
        "mpAnim": {
            "icons_dir": os.path.join(here, "mpAnim", "icons"),
            "buttons": [
                {
                    "label":   "Playblast",
                    "tooltip": "Open the Playblast Manager — creates versioned JPEG sequences with burn-ins",
                    "icon":    "playblast.png",
                    "command": _cmd(P["anim_tools"], ["pbTool"],
                        "import pbTool\n"
                        "importlib.reload(pbTool)\n"
                        "pbTool.show_pbTool()"),
                },
                {
                    "label":   "CamPreset",
                    "tooltip": "Open the Camera Preset Manager — save and apply named camera/render presets",
                    "icon":    "iconCamPreset.png",
                    "command": _cmd(P["anim_tools"], ["ps_cam_preset_simple"],
                        "import ps_cam_preset_simple as ps\n"
                        "importlib.reload(ps)\n"
                        "ps.show()"),
                },
                {
                    "label":   "ClothChain",
                    "tooltip": "Open the Cloth Chain Sim tool — build and control nCloth chain rigs",
                    "icon":    "iconClothChain.png",
                    "command": _cmd(P["clothchain"], ["tlmClothChain"],
                        "import tlmClothChain\n"
                        "importlib.reload(tlmClothChain)\n"
                        "import maya.cmds as cmds\n"
                        "run = tlmClothChain.SimClothRig()\n"
                        "cmds.evalDeferred(run.UI)"),
                },
                {
                    "label":   "StudioLib",
                    "tooltip": "Open Studio Library — animation pose and clip manager",
                    "icon":    "iconStudioLib.png",
                    "command": _cmd(P["studiolib"], ["studiolibrary", "studioqt", "studiolibrarymaya", "studiovendor"],
                        "import studiolibrary\n"
                        "importlib.reload(studiolibrary)\n"
                        "studiolibrary.main()"),
                },
                {
                    "label":   "JiffyPomo",
                    "tooltip": "Open JiffyPomo — Pomodoro timer and task tracker for Maya artists",
                    "icon":    "iconJiffy.png",
                    "command": _cmd(P["jiffypomo"],
                        ["Jiffypomo", "jiffyUtils", "jiffyDialogs", "jiffyWidgets",
                         "jiffyPromptsTab", "jiffyNotepadTab", "jiffyPomoTab",
                         "jiffySummaryTab", "jiffySettingsTab"],
                        "import Jiffypomo\n"
                        "importlib.reload(Jiffypomo)\n"
                        "Jiffypomo.run_jiffypomo()"),
                },
                {
                    "label":   "JiffySched",
                    "tooltip": "Open JiffySchedule — production schedule and asset tracker",
                    "icon":    "iconJiffySchedule.png",
                    "command": _cmd(P["jiffyschedule"], ["jiffySchedule"],
                        "import jiffySchedule\n"
                        "importlib.reload(jiffySchedule)\n"
                        "jiffySchedule.run_jiffyschedule()"),
                },
                {
                    "label":   "shortCuts",
                    "tooltip": "Open shortCuts — manage and switch hotkey presets per workflow",
                    "icon":    "iconShortCuts.png",
                    "command": _cmd(P["anim_tools"], ["shortCuts"],
                        "import shortCuts\n"
                        "importlib.reload(shortCuts)\n"
                        "shortCuts.show()"),
                },
                {
                    "label":   "MHTransfer",
                    "tooltip": "Open Metahuman Facial Transfer — retarget Unreal facial animation to Maya",
                    "icon":    "iconMetahuman.png",
                    "command": _cmd(P["metahuman"], ["metahuman_facial_transfer_25"],
                        "import metahuman_facial_transfer_25 as mh\n"
                        "importlib.reload(mh)\n"
                        "mh.UI()"),
                },
            ],
        },
        "mpRig": {
            "icons_dir": os.path.join(here, "mpRig", "icons"),
            "buttons": [
                {
                    "label":   "ps_spine",
                    "tooltip": "Open ps_spine — build a ribbon spine rig from a drawn curve",
                    "icon":    "iconSpine.png",
                    "command": _cmd(P["rigdev"], ["ps_spine"],
                        "import ps_spine\n"
                        "importlib.reload(ps_spine)\n"
                        "ps_spine.show()"),
                },
                {
                    "label":   "Follicle Rig",
                    "tooltip": "Open Follicle Rig Tools — scatter follicles across NURBS or poly surfaces",
                    "icon":    "iconFollicleRig.png",
                    "command": _cmd(P["rigdev"], ["follicleRig_api", "follicleRig_ui"],
                        "import follicleRig_api, follicleRig_ui\n"
                        "importlib.reload(follicleRig_api)\n"
                        "importlib.reload(follicleRig_ui)\n"
                        "follicleRig_ui.show()"),
                },
                {
                    "label":   "CorrectiveBS",
                    "tooltip": "Open Corrective Blendshape Tool — add corrective and performance blendshape targets to skinned rigs",
                    "icon":    "iconCorrectiveBS.png",
                    "command": _cmd(P["correctivebs"], ["tlmCorrectiveBS_api", "tlmCorrectiveBS_ui"],
                        "import tlmCorrectiveBS_api, tlmCorrectiveBS_ui\n"
                        "importlib.reload(tlmCorrectiveBS_api)\n"
                        "importlib.reload(tlmCorrectiveBS_ui)\n"
                        "tlmCorrectiveBS_ui.show()"),
                },
            ],
        },
    }

    # --- Icons ---
    icons_dir = cmds.internalVar(userBitmapsDir=True)
    os.makedirs(icons_dir, exist_ok=True)
    for shelf_data in SHELVES.values():
        src_dir = shelf_data["icons_dir"]
        for btn in shelf_data["buttons"]:
            icon = btn.get("icon", "")
            src = os.path.join(src_dir, icon)
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(icons_dir, icon))

    # --- userSetup.py ---
    scripts_dir = os.path.join(cmds.internalVar(userAppDir=True), "scripts")
    os.makedirs(scripts_dir, exist_ok=True)
    usersetup_path = os.path.join(scripts_dir, "userSetup.py")

    MARKER     = "# mpAnim personal dev setup — managed by install_personal.py"
    END_MARKER = "# end mpAnim personal dev setup"

    usersetup_block = "\n".join([
        "",
        MARKER,
        "import sys",
        "for _p in [",
        f"    r'{P['multitool']}',",
        f"    r'{P['studiolib']}',",
        f"    r'{P['anim_tools']}',",
        "]:",
        "    if _p not in sys.path:",
        "        sys.path.insert(0, _p)",
        "import maya.utils",
        "maya.utils.executeDeferred('import multiTool; multiTool.show()')",
        "maya.utils.executeDeferred('import mpAnimConfig; mpAnimConfig.get_save_path()')",
        END_MARKER,
        "",
    ])

    existing = ""
    if os.path.exists(usersetup_path):
        with open(usersetup_path, "r", encoding="utf-8") as fh:
            existing = fh.read()

    # Remove our managed block if present
    if MARKER in existing and END_MARKER in existing:
        start = existing.index(MARKER)
        end   = existing.index(END_MARKER, start) + len(END_MARKER)
        existing = existing[:start].rstrip() + existing[end:]

    # Strip stale animMultiTool lines left by older installers
    _stale = [
        "# animMultiTool auto-load (mpAnim installer)",
        "# multiTool auto-load (mpAnim installer)",
        "import animMultiTool; animMultiTool.show()",
        "import maya.utils; maya.utils.executeDeferred('import animMultiTool; animMultiTool.show()')",
    ]
    for line in _stale:
        existing = existing.replace(line, "")
    existing = "\n".join(ln for ln in existing.splitlines() if ln.strip())

    with open(usersetup_path, "w", encoding="utf-8") as fh:
        fh.write(existing.rstrip() + usersetup_block)

    print("[install_personal] patched userSetup.py")

    # --- Shelves ---
    shelf_top     = mel.eval("$tmpVar=$gShelfTopLevel")
    existing_tabs = cmds.shelfTabLayout(shelf_top, query=True, childArray=True) or []

    for shelf_name, shelf_data in SHELVES.items():
        if shelf_name not in existing_tabs:
            mel.eval(f'addNewShelfTab "{shelf_name}"')
            print(f"[install_personal] created shelf: {shelf_name}")

        shelf = f"{shelf_top}|{shelf_name}"
        for old_btn in cmds.shelfLayout(shelf, query=True, childArray=True) or []:
            cmds.deleteUI(old_btn)

        for btn in shelf_data["buttons"]:
            cmds.shelfButton(
                parent=shelf,
                label=btn["label"],
                annotation=btn["tooltip"],
                image1=btn.get("icon", "commandButton.png"),
                command=btn["command"],
                sourceType="python",
            )
            print(f"[install_personal] added button: {shelf_name} / {btn['label']}")

    mel.eval("saveAllShelves $gShelfTopLevel")

    cmds.evalDeferred("import multiTool; multiTool.show()")
    cmds.evalDeferred("import mpAnimConfig; mpAnimConfig.get_save_path()")

    cmds.inViewMessage(
        amg="<b>mpAnim + mpRig</b> personal dev shelves installed.",
        pos="midCenter",
        fade=True,
    )
    print("[install_personal] done")


def onMayaDroppedPythonFile(*args):
    _install()
