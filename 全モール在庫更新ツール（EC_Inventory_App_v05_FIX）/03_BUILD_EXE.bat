@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>&1
if errorlevel 1 (
  echo Python launcher "py" was not found.
  pause
  exit /b 1
)
py -m pip install pyinstaller
if errorlevel 1 goto :error
py -m PyInstaller --noconfirm --clean --onefile --windowed --name "EC_Inventory_Update" app.py
if errorlevel 1 goto :error
echo.
echo EXE created:
echo dist\EC_Inventory_Update.exe
echo.
pause
exit /b 0

:error
echo.
echo EXE build failed.
echo Please take a screenshot and send it to ChatGPT.
echo.
pause
exit /b 1
