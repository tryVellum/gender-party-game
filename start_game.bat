@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" (
    echo Среда разработки не установлена.
    echo Сначала запустите setup.bat.
    pause
    exit /b 1
)

start "" ".venv\Scripts\pythonw.exe" "%~dp0launcher.py"
exit /b 0
