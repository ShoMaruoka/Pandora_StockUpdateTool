@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo ==========================================
echo   EC Inventory App - Initial Setup
echo ==========================================
echo.
where py >nul 2>&1
if errorlevel 1 (
  echo Python launcher "py" was not found.
  echo Please install Python 3.11 or later first.
  echo During installation, enable "Add Python to PATH".
  echo.
  pause
  exit /b 1
)
py -m pip install --upgrade pip
if errorlevel 1 goto :error
py -m pip install -r requirements.txt
if errorlevel 1 goto :error
echo.
echo Setup completed successfully.
echo Next, double-click 02_START.bat
echo.
pause
exit /b 0

:error
echo.
echo Setup failed.
echo Please take a screenshot of this window and send it to ChatGPT.
echo.
pause
exit /b 1
