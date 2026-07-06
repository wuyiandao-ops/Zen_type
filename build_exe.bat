@echo off
chcp 65001 >nul
title Build ZenType.exe
cd /d "%~dp0"
echo ============================================
echo   Build ZenType.exe with PyInstaller
echo ============================================
echo   Requires: pip install pyinstaller
echo.
echo   --collect-all opencc      : bundle opencc s2tw dictionaries
echo                               (without it, s->t conversion crashes)
echo   --collect-all sounddevice : bundle PortAudio native DLL (recording)
echo   --collect-all soundfile   : bundle libsndfile native DLL
echo.
pyinstaller --onefile --name ZenType ^
  --collect-all opencc ^
  --collect-all sounddevice ^
  --collect-all soundfile ^
  zen_type.py
echo.
echo ============================================
echo   Done. EXE is at  dist\ZenType.exe
echo   Copy corrections.csv into dist\ (next to the EXE).
echo   At runtime you still need the SenseVoice service (8009)
echo   and Ollama running.
echo ============================================
pause
