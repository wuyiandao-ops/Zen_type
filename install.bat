@echo off
chcp 65001 >nul
title ZenType Installer
cd /d "%~dp0"

echo ============================================
echo    ZenType - one-time installer
echo ============================================
echo.

echo [Step 1/4] Checking Python...
python --version
if errorlevel 1 (
  echo.
  echo [ERROR] Python not found.
  echo Please install Python first, and tick "Add python.exe to PATH".
  echo See the install guide in this folder for details, then run this again.
  pause
  exit /b 1
)
echo.

echo [Step 2/4] Installing Python packages...
echo           ^(This can take several minutes; torch is large. Please wait.^)
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo [ERROR] pip install failed. Check your internet connection and run again.
  pause
  exit /b 1
)
echo.

echo [Step 3/4] Pulling the Qwen model via Ollama...
where ollama >nul 2>nul
if errorlevel 1 (
  echo [WARN] Ollama not found. Please install Ollama, then run:  ollama pull qwen2.5:3b
) else (
  ollama pull qwen2.5:3b
)
echo.

echo [Step 4/4] Downloading the SenseVoice model ^(~900MB, one time^)...
python -c "from funasr import AutoModel; AutoModel(model='iic/SenseVoiceSmall', vad_model='fsmn-vad', disable_update=True)"
echo.

echo ============================================
echo   Install finished! Now double-click  start.bat  to run ZenType.
echo ============================================
pause
