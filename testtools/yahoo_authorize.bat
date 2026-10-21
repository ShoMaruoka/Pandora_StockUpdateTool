@echo off
cd /d "%~dp0"
py -3 yahoo_authorize.py
if errorlevel 1 (
  echo.
  echo Pythonが見つからない場合は、Python 3 をインストールしてから再実行してください。
)
echo.
pause
