# ------------------------------------------------------------
# launch_shotSub.py
#
# Dev launcher — paste this whole file into Maya's Script Editor (Python
# tab) and run it to always get the LATEST shotSub.py straight from source,
# no copy-to-Maya's-scripts-folder step needed. shotSub.py is deliberately
# NOT staged anywhere on Maya's default script path (dev/test only, not for
# student rollout — see pipeDev/shotSubDev), so plain `import shotSub` fails
# with ModuleNotFoundError unless this folder is added to sys.path first.
#
# Safe to re-run repeatedly in the same Maya session: closes any existing
# shotSub window, reloads the module (so edits made since the last run
# take effect), then reopens it.
#
# NOTE: _DEV_DIR is hardcoded for this machine's clone location. If running
# from a different checkout (e.g. an RMIT lab machine), update the path.
# ------------------------------------------------------------
import sys
import importlib

_DEV_DIR = r"C:\Users\patsa\Documents\maya\scriptDev\pipeDev\shotSubDev"
if _DEV_DIR not in sys.path:
    sys.path.insert(0, _DEV_DIR)

import shotSub

if shotSub.cmds.window(shotSub.ShotSub.WINDOW_NAME, exists=True):
    shotSub.cmds.deleteUI(shotSub.ShotSub.WINDOW_NAME)

importlib.reload(shotSub)
shotSub.show_shotSub()
