@echo off
cd /d "%~dp0.."
py -3 tools\build_exe.py
echo.
pause
