@echo off
chcp 65001 >nul
echo ====================================================
echo  🚀 Kalibrovka Web Appni Serverga Joylash
echo ====================================================
python -c "import shutil, os; os.makedirs('public', exist_ok=True); shutil.copy('index.html', 'public/index.html')"
call npx surge public kalibrovka-3d.surge.sh
echo.
echo ====================================================
echo  ✅ Muvaffaqiyatli serverga yuklandi!
echo  🌐 Havola: https://kalibrovka-3d.surge.sh
echo ====================================================
pause
