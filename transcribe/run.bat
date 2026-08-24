@echo off
rem 画面を出して起動する。音声・動画ファイルをこの bat に放り込むと、そのまま文字起こしする
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (
  start "" ".venv\Scripts\pythonw.exe" "app.py" %*
) else (
  echo .venv が無い。先に setup.bat を実行すること。
  pause
)
