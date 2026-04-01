@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
if /I "%SCRIPT_DIR:~0,4%"=="\\?\" set "SCRIPT_DIR=%SCRIPT_DIR:~4%"
cd /d "%SCRIPT_DIR%"
powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%run_all.ps1"
