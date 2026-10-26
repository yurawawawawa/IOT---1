@echo off
setlocal
cd /d "%~dp0"
echo Menyiapkan BuddyCheck...
python -m venv .venv
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto fail
.venv\Scripts\python.exe scripts\setup_env.py
if errorlevel 1 goto fail
echo.
echo Setup selesai. Jalankan run.bat untuk membuka detector.
pause
exit /b 0
:fail
echo Setup gagal. Pastikan Python 3.10 atau lebih baru terpasang dan internet aktif.
pause
exit /b 1
