@echo off
rem H drive sync (staff desktop tool): double-click to check ShotGrid for new
rem assets/shots with no folder on the H drive, then choose whether to build
rem them. Never overwrites anything.
rem
rem Where the H drive is: change this line if it's somewhere else.
set "H_ROOT=G:\H"

set "HERE=%~dp0"
set "PY="
rem A real Python, not Windows' "get Python from the Store" placeholder.
python -c "import sys" >nul 2>nul && set "PY=python"
if not defined PY if exist "C:\Program Files\Autodesk\Maya2026\bin\mayapy.exe" set "PY=C:\Program Files\Autodesk\Maya2026\bin\mayapy.exe"
if not defined PY if exist "C:\Program Files\Autodesk\Maya2025\bin\mayapy.exe" set "PY=C:\Program Files\Autodesk\Maya2025\bin\mayapy.exe"
if not defined PY (
    echo Python 3 isn't installed. Get it from python.org, then double-click this again.
    pause
    exit /b 1
)

"%PY%" "%HERE%h_sync.py" --h-root "%H_ROOT%" --ask
echo.
pause
