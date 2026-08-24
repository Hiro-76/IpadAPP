@echo off
rem Start the app. You can also drop audio/video files onto this file.
cd /d "%~dp0"
set "VENV=%LOCALAPPDATA%\MojiOkoshi\venv"
if not exist "%VENV%\Scripts\pythonw.exe" set "VENV=%~dp0.venv"
if exist "%VENV%\Scripts\pythonw.exe" (
  start "" "%VENV%\Scripts\pythonw.exe" "%~dp0app.py" %*
) else (
  echo Not installed yet. Run setup.bat first.
  pause
)
