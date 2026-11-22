@echo off
setlocal enableextensions
cd /d "%~dp0"
title Revelate - live run
set "PYEXE="
py -c "import sys" >nul 2>nul && set "PYEXE=py"
if not defined PYEXE python -c "import sys" >nul 2>nul && set "PYEXE=python"
if not defined PYEXE echo [ERROR] Python 3 was not found. Install Python 3.10+ from https://www.python.org/downloads/ and tick "Add python.exe to PATH", then run this again. & echo. & pause & exit /b 1
echo ============================================================
echo  Revelate - LIVE run against the real revel8 twins (Julius)
echo ============================================================
echo.
echo You will be asked for TWO keys, one at a time. They stay hidden
echo while you paste - the line looks blank, that is normal - and are
echo never saved to disk.
echo   1) revel8 TEAM KEY  (starts with  rv8_ )
echo   2) your OpenAI key  (starts with  sk- )
echo.
echo This uses OpenAI credits and spends from the 30-contact practice budget.
echo.
pause
%PYEXE% agent.py --targets julius
echo.
echo ------------------------------------------------------------
echo If you got an SSL / certificate error, your work firewall is
echo blocking it. Easiest fix: connect to a personal phone hotspot and
echo run this again. (An on-the-work-wifi workaround is in START_HERE.md.)
echo For any other error, copy the text above and send it to Claude.
echo ------------------------------------------------------------
pause
