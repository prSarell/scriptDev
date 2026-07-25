# ------------------------------------------------------------
# launch_jiffySG.py
#
# Dev launcher — paste this whole file into Maya's Script Editor (Python
# tab) and run it to always get the LATEST jiffySG.py straight from source,
# no copy-to-Maya's-scripts-folder step needed. jiffySG.py is deliberately
# NOT staged anywhere on Maya's default script path (see jiffySG_brief.md —
# dev/test only, not for student rollout), so plain `import jiffySG` fails
# with ModuleNotFoundError unless this folder is added to sys.path first.
#
# Safe to re-run repeatedly in the same Maya session: closes any existing
# Jiffy SG window, reloads the module (so edits made since the last run
# take effect), then reopens it.
#
# NOTE: _DEV_DIR is hardcoded for this machine's clone location. If running
# from a different checkout (e.g. an RMIT lab machine), update the path.
# ------------------------------------------------------------
import sys
import importlib

_DEV_DIR = r"C:\Users\patsa\Documents\maya\scriptDev\timeManagementDev\jiffySGDev"
if _DEV_DIR not in sys.path:
    sys.path.insert(0, _DEV_DIR)

import jiffySG

if jiffySG._jiffysg_window is not None:
    jiffySG._jiffysg_window.close()

importlib.reload(jiffySG)
jiffySG.run_jiffySG()
