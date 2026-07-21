@echo off
setlocal EnableExtensions

chcp 65001 >nul
cd /d "%~dp0"

set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
set "APP_FILE=%~dp0app.py"
set "ENV_FILE=%~dp0.env"

if not exist "%PYTHON_EXE%" (
    echo Виртуальное окружение не найдено. Запускаю установку...
    call "%~dp0setup.bat"

    if errorlevel 1 (
        echo.
        echo Установка завершилась с ошибкой.
        pause
        exit /b 1
    )
)

if not exist "%ENV_FILE%" (
    echo Файл .env не найден. Создаю локальные настройки...
    "%PYTHON_EXE%" "%~dp0init_env.py"

    if errorlevel 1 (
        echo.
        echo Не удалось создать файл .env.
        pause
        exit /b 1
    )
)

set "PORT=5000"
set "ADMIN_SECRET_PATH="

for /f "usebackq eol=# tokens=1,* delims==" %%A in ("%ENV_FILE%") do (
    if /i "%%A"=="PORT" set "PORT=%%B"
    if /i "%%A"=="ADMIN_SECRET_PATH" set "ADMIN_SECRET_PATH=%%B"
)

if not defined ADMIN_SECRET_PATH (
    echo.
    echo В файле .env не задан параметр ADMIN_SECRET_PATH.
    echo Запустите setup.bat или исправьте файл .env.
    pause
    exit /b 1
)

set "ADMIN_URL=http://127.0.0.1:%PORT%/%ADMIN_SECRET_PATH%"

echo Запускаю сервер Gender Party...
start "Gender Party Server" /D "%~dp0" "%PYTHON_EXE%" "%APP_FILE%"

set /a WAIT_ATTEMPT=0

:wait_for_server
powershell -NoProfile -Command ^
    "try { Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:%PORT%/' -TimeoutSec 1 | Out-Null; exit 0 } catch { exit 1 }" ^
    >nul 2>&1

if not errorlevel 1 goto server_ready

set /a WAIT_ATTEMPT+=1

if %WAIT_ATTEMPT% GEQ 20 goto server_timeout

timeout /t 1 /nobreak >nul
goto wait_for_server

:server_ready
start "" "%ADMIN_URL%"
exit /b 0

:server_timeout
echo.
echo Сервер не запустился в течение 20 секунд.
echo Проверьте окно Gender Party Server: в нём должна быть указана причина ошибки.
pause
exit /b 1
