@echo off
rem Batch transcription. You can also drop files or folders onto this file.
cd /d "%~dp0"
set "VENV=%LOCALAPPDATA%\MojiOkoshi\venv"
if not exist "%VENV%\Scripts\python.exe" set "VENV=%~dp0.venv"
if not exist "%VENV%\Scripts\python.exe" (
  echo Not installed yet. Run setup.bat first.
  pause
  exit /b 1
)
"%VENV%\Scripts\python.exe" "%~dp0cli.py" %*
echo.
pause
