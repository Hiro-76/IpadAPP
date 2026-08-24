@echo off
rem まとめて文字起こしする。ファイルやフォルダをこの bat に放り込んでもよい
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo .venv が無い。先に setup.bat を実行すること。
  pause
  exit /b 1
)
".venv\Scripts\python.exe" "cli.py" %*
echo.
pause
