# Создание готового Windows-релиза

Эта инструкция предназначена для владельца репозитория `tryVellum/gender-party-game`.

Обычный пользователь не выполняет эти действия. Он скачивает готовый установщик из раздела **Releases**.

## 1. Очистить временные и устаревшие файлы

Удалите из корня проекта:

```powershell
Remove-Item ".\apply_test_fix.bat" -Force -ErrorAction SilentlyContinue
Remove-Item ".\instance\runtime_paths.py" -Force -ErrorAction SilentlyContinue
Remove-Item ".\AUDIT_REPORT.md" -Force -ErrorAction SilentlyContinue
Remove-Item ".\PUBLISH_TO_GITHUB.md" -Force -ErrorAction SilentlyContinue
```

Удалите локальные кэши:

```powershell
Remove-Item ".\.pytest_cache" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item ".\.ruff_cache" -Recurse -Force -ErrorAction SilentlyContinue

Get-ChildItem . -Directory -Recurse -Filter "__pycache__" |
    Where-Object { $_.FullName -notlike "*\.venv\*" } |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
```

Файлы `.env`, `instance\game_settings.json`, `instance\runtime_config.json` и база SQLite являются локальными данными. Они не должны попадать в Git, но их необязательно удалять с рабочего компьютера.

Любые файлы вида `gender_party_game*.txt`, созданные сборщиком проекта, нельзя публиковать: они могут содержать секретные настройки и личные вопросы.

## 2. Проверить обязательные файлы сборки

Выполните:

```powershell
$required = @(
    "assets\gender-party.ico",
    "assets\gender-party.png",
    "build\GenderPartyGame.spec",
    "build\build_release.ps1",
    "build\generate_version_info.py",
    "build\installer.iss",
    "build\version_info.txt",
    ".github\workflows\release-windows.yml",
    "launcher.py",
    "runtime_paths.py",
    "version.py"
)

$missing = $required | Where-Object { -not (Test-Path $_) }

if ($missing) {
    Write-Host "Отсутствуют обязательные файлы:" -ForegroundColor Red
    $missing
} else {
    Write-Host "Все файлы сборки найдены." -ForegroundColor Green
}
```

Если список отсутствующих файлов пуст, можно продолжать.

## 3. Проверить личные данные

Текущий рабочий набор вопросов может содержать имена, семейные факты и фотографии.

Для публичного релиза выполните одно из двух действий:

1. замените `data\questions.json` и изображения на нейтральный демонстрационный набор;
2. сделайте репозиторий и Release приватными.

Проверьте файл:

```text
PRIVATE_CONTENT_CHECKLIST.md
```

Не публикуйте:

- `.env`;
- `instance\game.sqlite`;
- `instance\game_settings.json`;
- `instance\runtime_config.json`;
- семейные фотографии без согласия;
- текстовые отчёты, в которые попали секреты.

## 4. Проверить Git

```powershell
git status
```

Проверка запрещённых отслеживаемых файлов:

```powershell
git ls-files |
    Select-String -Pattern '(^|/)(\.env|game\.sqlite|game_settings\.json|runtime_config\.json|apply_test_fix\.bat|instance/runtime_paths\.py|gender_party_game.*\.txt)$'
```

Команда не должна ничего вывести.

Проверьте, что обязательные файлы сборки отслеживаются:

```powershell
git ls-files assets build .github/workflows/release-windows.yml
```

## 5. Проверить форматирование и тесты

Активируйте окружение:

```powershell
.\.venv\Scripts\Activate.ps1
```

Установите актуальные зависимости:

```powershell
python -m pip install -r requirements-dev.txt
```

Запустите:

```powershell
python -m ruff format --check `
    app.py config.py database.py init_env.py launcher.py `
    runtime_paths.py version.py build/generate_version_info.py tests

python -m ruff check `
    app.py config.py database.py init_env.py launcher.py `
    runtime_paths.py version.py build/generate_version_info.py tests

python -m pytest -q
```

Ожидаемый результат:

```text
All checks passed!
2 passed
```

## 6. Проверить версию

Текущая версия задаётся в:

```text
version.py
```

Для первого Windows-релиза:

```python
APP_VERSION = "1.2.1"
```

Версия тега должна полностью совпадать:

```text
v1.2.1
```

Файл `build\version_info.txt` обновляется во время сборки скриптом `build\generate_version_info.py`.

## 7. Обновить документацию

Замените:

```text
README.md
docs\RELEASE_CHECKLIST.md
CHANGELOG.md
.gitignore
```

готовыми файлами из комплекта документации.

Проверьте ссылки и номер версии `1.2.1`.

## 8. Создать коммит

```powershell
git add -A
git status
```

Перед коммитом ещё раз убедитесь, что нет `.env`, локальной базы, личного отчёта и временного `apply_test_fix.bat`.

```powershell
git commit -m "Prepare Windows release 1.2.1"
git push origin main
```

Откройте вкладку **Actions** и дождитесь зелёного workflow **Tests**.

## 9. Создать тег

Убедитесь, что тег ещё не существует:

```powershell
git tag --list "v1.2.1"
```

Если команда ничего не вывела:

```powershell
git tag -a v1.2.1 -m "Gender Party Game 1.2.1"
git push origin v1.2.1
```

Отправка тега автоматически запускает workflow:

```text
Build Windows Release
```

## 10. Дождаться сборки

На GitHub:

1. откройте **Actions**;
2. выберите **Build Windows Release**;
3. откройте запуск для тега `v1.2.1`;
4. дождитесь завершения всех этапов.

Workflow должен:

- установить зависимости;
- выполнить Ruff и Pytest;
- скачать локальный Socket.IO-клиент;
- собрать приложение через PyInstaller;
- проверить собранный EXE;
- создать portable ZIP;
- создать установщик через Inno Setup;
- прикрепить оба файла к GitHub Release.

## 11. Проверить GitHub Release

Откройте:

```text
https://github.com/tryVellum/gender-party-game/releases
```

В Release `v1.2.1` должны находиться:

```text
GenderPartyGame-Setup-1.2.1.exe
GenderPartyGame-Portable-1.2.1.zip
```

Наличие только `Source code (zip)` означает, что workflow не завершился или не прикрепил файлы.

## 12. Проверить установщик как обычный пользователь

Проверку лучше выполнять на другом компьютере Windows 10/11 или в чистой виртуальной машине.

Проверьте:

1. установка в `Program Files`;
2. создание ярлыка;
3. запуск без чёрного окна;
4. автоматическое открытие страницы администратора;
5. появление значка рядом с часами;
6. повторный запуск открывает существующую игру;
7. редактор сохраняет вопросы и пол ребёнка;
8. QR-код открывается на двух телефонах;
9. обычный вопрос;
10. аукцион;
11. финальный раунд со звуком;
12. секретный раунд;
13. полный сброс;
14. завершение через значок;
15. удаление через «Установленные приложения».

## 13. Контрольная репетиция

До передачи пользователям проведите игру минимум с двумя телефонами:

- компьютер и телефоны в одной Wi‑Fi-сети;
- VPN отключён;
- брандмауэр разрешён только для частной сети;
- звук включён;
- компьютер не переходит в сон;
- правильный пол проверен в редакторе.

После репетиции нажмите полный сброс.

## 14. Обновление следующей версии

Для версии `1.2.1`:

1. измените `APP_VERSION` в `version.py`;
2. обновите `CHANGELOG.md`;
3. замените номера версии в пользовательском README;
4. выполните тесты;
5. создайте коммит;
6. создайте тег `v1.2.1`;
7. отправьте тег на GitHub.

Не переиспользуйте уже опубликованный тег для другого содержимого.
