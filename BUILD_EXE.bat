@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  py -3.12 -m venv .venv 2>nul || py -3.11 -m venv .venv 2>nul || python -m venv .venv
  if errorlevel 1 (echo Python 3.11 or 3.12 is required. & pause & exit /b 1)
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt -r requirements-build.txt
if errorlevel 1 (echo Dependency installation failed. & pause & exit /b 1)
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean WatermarkMinhDien.spec
if errorlevel 1 (echo Build failed. & pause & exit /b 1)
echo Done: dist\WatermarkMinhDien.exe
pause
