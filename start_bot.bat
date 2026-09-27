@echo off
chcp 65001 >nul
title 3D Kalibrovka Telegram Boti (@KALIBROVA3D_bot)
echo ====================================================
echo  🤖 3D Kalibrovka Telegram Boti Ishga Tushmoqda...
echo  🌐 Web App: https://kalibrovka-3d.surge.sh
echo ====================================================
:loop
python -u bot.py
echo.
echo ⚠️ Bot to'xtadi yoki uzildi. 3 soniyadan so'ng qayta ishga tushadi...
timeout /t 3 /nobreak >nul
goto loop
