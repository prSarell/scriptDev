#!/bin/bash
# H drive sync (staff desktop tool): double-click to check ShotGrid for new
# assets/shots with no folder on the H drive, then choose whether to build
# them. Never overwrites anything.
#
# Where the H drive is: change this line if it's somewhere else.
H_ROOT="/Volumes/T7/H"

HERE="$(cd "$(dirname "$0")" && pwd)"
PY=""
if command -v python3 >/dev/null 2>&1 && python3 -c "import sys" >/dev/null 2>&1; then
    PY="python3"
else
    for v in 2026 2025; do
        m="/Applications/Autodesk/maya$v/Maya.app/Contents/bin/mayapy"
        if [ -x "$m" ]; then PY="$m"; break; fi
    done
fi
if [ -z "$PY" ]; then
    echo "Python 3 isn't installed. Get it from python.org, then double-click this again."
    read -r -p "Press Return to close."
    exit 1
fi

"$PY" "$HERE/h_sync.py" --h-root "$H_ROOT" --ask
echo
read -r -p "Press Return to close."
