@echo off
REM Windows batch equivalent of ttcron.sh
REM Schedule with Task Scheduler for automated time tracking

REM Change to the script directory (adjust path as needed)
cd /d "%~dp0"

REM Run ttclock with desired action
uv run ttclock %*

REM Log to file (optional)
echo %date% %time% - ttclock %* >> ttcron.log