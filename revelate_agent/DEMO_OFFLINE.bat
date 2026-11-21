@echo off
cd /d "%~dp0"
echo Full offline demo: research - niche - two-round challenge - credential capture.
echo No revel8 key and no OpenAI key are needed; nothing leaves this machine.
echo.
echo Tip: add a niche, e.g.  DEMO_OFFLINE.bat --category intern
echo Niches: founder executive manager individual_contributor technical hr_learning operations intern independent
echo.
py agent.py --offline %*
echo.
pause
