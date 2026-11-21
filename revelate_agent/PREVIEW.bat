@echo off
cd /d "%~dp0"
py preview.py
start "" "previews\index.html"
