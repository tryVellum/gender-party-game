@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Виртуальное окружение не найдено. Запускаю установку...
    call setup.bat
    if errorlevel 1 exit /b 1
)

if not exist ".env" ".venv\Scripts\python.exe" init_env.py

for /f "usebackq delims=" %%U in (`".venv\Scripts\python.exe" -c "from config import Config; print(f'http://127.0.0.1:{Config.PORT}/{Config.ADMIN_SECRET_PATH}')"`) do set "ADMIN_URL=%%U"

start "Gender Party Server" cmd /k "cd /d ""%~dp0"" ^&^& "".venv\Scripts\python.exe"" app.py"

timeout /t 3 /nobreak >nul
start "" "%ADMIN_URL%"

echo.
echo Сервер Gender Party запущен.
echo Администратор: %ADMIN_URL%
echo.
echo Ссылку и QR-код для игроков можно открыть кнопкой

echo с иконкой QR-кода на странице администратора.
echo.
echo Чтобы остановить сервер, закройте окно Gender Party Server.
pause
