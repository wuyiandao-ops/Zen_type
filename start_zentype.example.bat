@echo off
chcp 65001 >nul
title ZenType 啟動器
REM ============================================================
REM  第一次使用:把下面這行改成你電腦上 app_sensevoice.py 的實際路徑,
REM  然後把本檔另存為 start_zentype.bat (個人版不會被上傳到 GitHub)。
set "SENSEVOICE_SCRIPT=C:\path\to\app_sensevoice.py"
REM ============================================================

echo ============================================
echo    ZenType 離線語音輸入 一鍵啟動
echo ============================================
echo.
echo 前置提醒:請確認 Ollama 已在執行 (安裝後通常常駐於工作列)。
echo.
echo [1/2] 啟動 SenseVoice 辨識服務 (埠 8009)...
echo       若服務已在執行, 新視窗會顯示「埠被佔用」, 直接關掉那個新視窗即可。
start "SenseVoice-8009" cmd /k python "%SENSEVOICE_SCRIPT%"
echo.
echo       等待模型載入 (約 10 秒)...
timeout /t 10 /nobreak >nul
echo.
echo [2/2] 啟動 ZenType 語音輸入客戶端...
start "ZenType" cmd /k python "%~dp0zen_type.py"
echo.
echo 完成! 已開啟兩個視窗。本啟動視窗可直接關閉。
timeout /t 3 /nobreak >nul
