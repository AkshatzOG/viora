@echo off
cd /d "%~dp0"

if exist "venv\Scripts\python.exe" (
    start "" "venv\Scripts\python.exe" launcher.py
) else (
    start "" python launcher.py
)
