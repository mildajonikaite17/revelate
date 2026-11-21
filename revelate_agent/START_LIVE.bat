@echo off
cd /d "%~dp0"
echo Live run against the revel8 practice simulator.
echo You will paste the revel8 TEAM KEY, then your OpenAI API key. Both stay hidden
echo and are never written to disk.
echo.
echo Default target is julius. To pick another:  START_LIVE.bat --targets tom
echo To force a niche:  START_LIVE.bat --targets tom --category technical
echo.
py agent.py --targets julius %*
echo.
pause
