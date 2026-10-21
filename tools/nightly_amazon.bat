@echo off
py -3 "%~dp0nightly_amazon.py" --dry-run
exit /b %ERRORLEVEL%
