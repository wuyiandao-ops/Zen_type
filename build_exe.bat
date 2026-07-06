@echo off
chcp 65001 >nul
title 打包 ZenType.exe
cd /d "%~dp0"
echo ============================================
echo   用 PyInstaller 打包 ZenType.exe
echo ============================================
echo   需先安裝: pip install pyinstaller
echo.
echo   --collect-all opencc     : 收 opencc 的簡繁字典資料(不收會在轉繁時崩潰)
echo   --collect-all sounddevice: 收錄音用的 PortAudio 原生 DLL
echo   --collect-all soundfile  : 收 libsndfile 原生 DLL
echo.
pyinstaller --onefile --name ZenType ^
  --collect-all opencc ^
  --collect-all sounddevice ^
  --collect-all soundfile ^
  zen_type.py
echo.
echo ============================================
echo   完成! EXE 位於  dist\ZenType.exe
echo   請把 corrections.csv 複製到 dist\ (與 EXE 同層) 才會套用校正表。
echo   執行前仍需: SenseVoice 服務(8009) 與 Ollama 都在跑。
echo ============================================
pause
