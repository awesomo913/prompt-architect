@echo off
title Prompt Architect v4.0
cd /d "%~dp0"
python prompt_architect.py
if errorlevel 1 (
    echo.
    echo ERROR: Python could not run the app.
    echo Make sure Python 3.11+ is installed and on your PATH.
    echo.
    pause
)
