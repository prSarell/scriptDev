import importlib
import sys

TOOL_PATH = r"C:\Users\patsa\OneDrive\Documents\maya\scriptDev\timeManagementDev\jiffyScheduleDev"

if TOOL_PATH not in sys.path:
    sys.path.insert(0, TOOL_PATH)

for mod in list(sys.modules.keys()):
    if "jiffySchedule" in mod:
        del sys.modules[mod]

import jiffySchedule
importlib.reload(jiffySchedule)
jiffySchedule.run_jiffyschedule()
