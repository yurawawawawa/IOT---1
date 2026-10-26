@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto missing
.venv\Scripts\python.exe scripts\setup_env.py
.venv\Scripts\python.exe detector.py
if errorlevel 1 pause
exit /b
:missing
echo Jalankan setup.bat terlebih dahulu.
pause
exit /b 1
