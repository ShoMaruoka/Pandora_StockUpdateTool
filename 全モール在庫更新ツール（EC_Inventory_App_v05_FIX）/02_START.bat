@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>&1
if errorlevel 1 (
  echo Python launcher "py" was not found.
  echo Run 01_SETUP.bat after installing Python 3.11 or later.
  pause
  exit /b 1
)
py app.py
if errorlevel 1 (
  echo.
  echo The application could not start.
  echo Please take a screenshot of this window and send it to ChatGPT.
  echo.
  pause
)
