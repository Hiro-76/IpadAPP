@echo off
rem PowerShell の実行ポリシーに関係なく setup.ps1 を動かす
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1" %*
echo.
pause
