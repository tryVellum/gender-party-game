@echo off
setlocal
cd /d "%~dp0"

echo ========================================
echo   Gender Party Game - установка

echo ========================================

where py >nul 2>nul
if %errorlevel%==0 (
    py -3.12 -m venv .venv 2>nul
    if errorlevel 1 py -3 -m venv .venv
) else (
    python -m venv .venv
)

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo Не удалось создать виртуальное окружение.
    echo Установите Python 3.11, 3.12 или 3.13 с сайта python.org
    echo и включите пункт "Add Python to PATH".
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :install_error

".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :install_error

".venv\Scripts\python.exe" init_env.py

echo.
echo Установка завершена.
echo Перед первой игрой откройте файл .env и настройте:
echo   ADMIN_SECRET_PATH

echo   ACTUAL_GENDER=boy или ACTUAL_GENDER=girl

echo Затем запустите start_game.bat
pause
exit /b 0

:install_error
echo.
echo Ошибка установки зависимостей. Проверьте подключение к интернету.
pause
exit /b 1
