@echo off
rem Start the app. You can also drop audio/video files onto this file.
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (
  start "" ".venv\Scripts\pythonw.exe" "app.py" %*
) else (
  echo .venv not found. Run setup.bat first.
  pause
)
