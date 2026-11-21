@echo off
cd /d "%~dp0"
echo Verifying the Revelate agent offline (no keys, no network)...
echo.
py verify.py
echo.
pause
