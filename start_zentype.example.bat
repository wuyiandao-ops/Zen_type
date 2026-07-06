@echo off
chcp 65001 >nul
title ZenType Launcher
REM ============================================================
REM  FIRST-TIME SETUP:
REM  1. Change the path below to your own app_sensevoice.py path.
REM  2. Save this file as  start_zentype.bat  (your personal copy
REM     is gitignored and will not be uploaded to GitHub).
set "SENSEVOICE_SCRIPT=C:\path\to\app_sensevoice.py"
REM ============================================================

echo ============================================
echo    ZenType - offline voice input launcher
echo ============================================
echo.
echo Reminder: make sure Ollama is running (usually in the tray).
echo.
echo [1/2] Starting SenseVoice service (port 8009)...
echo       If it is already running, the new window will report the
echo       port is in use - just close that new window.
start "SenseVoice-8009" cmd /k python "%SENSEVOICE_SCRIPT%"
echo.
echo       Waiting ~10s for the model to load...
timeout /t 10 /nobreak >nul
echo.
echo [2/2] Starting ZenType client...
start "ZenType" cmd /k python "%~dp0zen_type.py"
echo.
echo Done. Two windows opened. You can close this launcher window.
timeout /t 3 /nobreak >nul
