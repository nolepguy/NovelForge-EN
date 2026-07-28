@echo off
title NovelForge Backend
echo Starting NovelForge Backend...
echo.

cd /d "%~dp0backend"
venv\Scripts\python.exe main.py

pause
