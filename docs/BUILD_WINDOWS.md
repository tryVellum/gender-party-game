# Сборка Windows-версии

## Что формируется

Скрипт `build/build_release.ps1` создаёт два продукта:

1. `GenderPartyGame-Setup-<version>.exe` — основной установщик;
2. `GenderPartyGame-Portable-<version>.zip` — переносная версия.

## Требования к компьютеру сборки

- Windows 10/11 x64;
- Python 3.12;
- Inno Setup 6 или 7;
- доступ к интернету для установки Python-зависимостей и загрузки браузерного клиента Socket.IO.

## Локальная сборка

В корне проекта:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\Activate.ps1
.\build\build_release.ps1
```

Перед упаковкой выполняются Ruff и Pytest. Затем PyInstaller создаёт `onedir`-приложение без консольного окна, после чего Inno Setup формирует установщик.

## Указание версии

Версия по умолчанию берётся из `version.py`.

```powershell
.\build\build_release.ps1 -Version 1.2.1
```

Перед релизом одновременно обновите `APP_VERSION` в `version.py` и числовые значения в `build/version_info.txt`.

## GitHub Actions

Для ручной сборки:

1. откройте вкладку **Actions**;
2. выберите **Build Windows Release**;
3. нажмите **Run workflow**;
4. при необходимости укажите версию.

Для автоматической публикации Release:

```powershell
git tag v1.2.0
git push origin v1.2.0
```

Workflow:

- запускает тесты;
- собирает EXE;
- создаёт установщик;
- создаёт portable ZIP;
- сохраняет оба файла как Actions Artifact;
- при запуске по тегу прикрепляет файлы к GitHub Release.

## Данные пользователя

Установщик не хранит изменяемые файлы в `Program Files`. При первом запуске стандартные вопросы и изображения копируются в:

```text
%LOCALAPPDATA%\GenderPartyGame
```

Это исключает необходимость запуска игры от имени администратора и сохраняет пользовательские изменения при обновлении.

## Брандмауэр

Установщик добавляет входящее правило для:

- `GenderPartyGame.exe`;
- TCP-порта 5000;
- только профиля **Private**.

При удалении приложения правило удаляется. Пользовательские данные сохраняются.

## Подпись установщика

Без цифровой подписи Windows SmartScreen может показать предупреждение о неизвестном издателе. Для публичного распространения рекомендуется приобрести сертификат подписи кода и подписывать EXE после сборки.
