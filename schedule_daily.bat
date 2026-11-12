@echo off
setlocal
cd /d "%~dp0"

echo ========================================================
echo Starting India Professional Email Lead Finder Daily Run
echo Time: %date% %time%
echo ========================================================

python lead_finder.py --use-linkedin --headless >> cache\scheduler.log 2>&1

echo Run completed with exit code %ERRORLEVEL%.
echo ========================================================

