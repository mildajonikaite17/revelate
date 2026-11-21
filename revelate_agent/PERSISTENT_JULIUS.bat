@echo off
cd /d "%~dp0"
echo Persistent single-target run: the full contact budget is spent on one twin,
echo reconsidering materially different next steps instead of stopping after silence.
echo You will paste the revel8 TEAM KEY, then your OpenAI API key (both hidden).
echo.
py agent.py --targets julius --persistent %*
echo.
pause
