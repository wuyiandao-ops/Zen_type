@echo off
chcp 65001 >nul
title ZenType
cd /d "%~dp0"

echo ============================================
echo    ZenType - offline voice input
echo ============================================
echo.
echo Reminder: make sure Ollama is running (usually in the tray).
echo.
echo [1/2] Starting SenseVoice service (port 8009)...
echo       If it is already running, the new window will report the
echo       port is in use - just close that new window.
start "SenseVoice-8009" cmd /k python "%~dp0sensevoice_server.py"
echo.
echo       Waiting ~15s for the model to load...
timeout /t 15 /nobreak >nul
echo.
echo [2/2] Starting ZenType client...
start "ZenType" cmd /k python "%~dp0zen_type.py"
echo.
echo Done. Hold Right-Ctrl and speak; release to paste.
echo You can close this launcher window.
timeout /t 3 /nobreak >nul
