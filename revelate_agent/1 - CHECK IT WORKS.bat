@echo off
setlocal enableextensions
cd /d "%~dp0"
title Revelate - check it works
set "PYEXE="
py -c "import sys" >nul 2>nul && set "PYEXE=py"
if not defined PYEXE python -c "import sys" >nul 2>nul && set "PYEXE=python"
if not defined PYEXE echo [ERROR] Python 3 was not found. Install Python 3.10+ from https://www.python.org/downloads/ and tick "Add python.exe to PATH", then run this again. & echo. & pause & exit /b 1
echo Using Python: %PYEXE%
echo Running the full offline check (no keys, no internet needed)...
echo.
%PYEXE% verify.py
echo.
echo ------------------------------------------------------------
echo If you see "RESULT: PASS" above, everything is working.
echo ------------------------------------------------------------
pause
