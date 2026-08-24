@echo off
rem Batch transcription. You can also drop files or folders onto this file.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo .venv not found. Run setup.bat first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" "cli.py" %*
echo.
pause
