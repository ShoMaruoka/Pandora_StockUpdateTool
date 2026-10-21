@echo off
cd /d "%~dp0"
py -3 amazon_report_compare.py %*
echo.
pause
