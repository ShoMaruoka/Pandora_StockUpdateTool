@echo off
cd /d "%~dp0"
py -3 logiless_export_stock.py
if errorlevel 1 (
  echo.
  echo Pythonが見つからない場合は、Python 3 をインストールしてから再実行してください。
)
echo.
pause
