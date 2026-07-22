@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

echo Установка среды разработки Gender Party Game...

where py >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=py -3.12"
) else (
    set "PYTHON_CMD=python"
)

if not exist ".venv\Scripts\python.exe" (
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 goto error
)

".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto error

".venv\Scripts\python.exe" -m pip install -r requirements-dev.txt
if errorlevel 1 goto error

".venv\Scripts\python.exe" init_env.py
if errorlevel 1 goto error

echo.
echo Готово. Для разработки используйте start_game.bat.
pause
exit /b 0

:error
echo.
echo Установка завершилась с ошибкой.
pause
exit /b 1
