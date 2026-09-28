@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  py -3.12 -m venv .venv 2>nul || py -3.11 -m venv .venv 2>nul || python -m venv .venv
  if errorlevel 1 (echo Python 3.11 or 3.12 is required. & pause & exit /b 1)
)
".venv\Scripts\python.exe" -c "import PySide6, PIL" >nul 2>nul
if errorlevel 1 (
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 (echo Dependency installation failed. & pause & exit /b 1)
)
".venv\Scripts\python.exe" main.py
if errorlevel 1 pause
