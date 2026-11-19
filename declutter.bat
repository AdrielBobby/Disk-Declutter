@echo off
rem Double-click to scan, review and clean. Extra options pass through, e.g.: declutter.bat --ai --stale-days 60
cd /d "%~dp0"
python -m declutter go %*
echo.
pause
