@echo off
setlocal enableextensions
cd /d "%~dp0"
title Revelate - watch a demo
set "PYEXE="
py -c "import sys" >nul 2>nul && set "PYEXE=py"
if not defined PYEXE python -c "import sys" >nul 2>nul && set "PYEXE=python"
if not defined PYEXE echo [ERROR] Python 3 was not found. Install Python 3.10+ from https://www.python.org/downloads/ and tick "Add python.exe to PATH", then run this again. & echo. & pause & exit /b 1
echo Full offline demo (no keys, no internet): research, niche, both
echo challenge rounds, and a credential capture - with a simulated twin.
echo.
%PYEXE% agent.py --offline --category founder
echo.
echo ------------------------------------------------------------
echo That was the "founder" niche. To watch another, change
echo --category founder  to e.g.  --category intern  or  --category technical
echo (founder executive manager individual_contributor technical
echo  hr_learning operations intern independent)
echo ------------------------------------------------------------
pause
