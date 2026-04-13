@echo off
title Advanced Prompt Architect
cd /d "%~dp0"
pip install -r requirements.txt >nul 2>&1
python prompt_architect.py
pause
