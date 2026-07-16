# Публикация Gender Party Game в аккаунте tryVellum

Эта инструкция предназначена для первой публикации проекта в новый публичный репозиторий GitHub.

Рекомендуемое имя репозитория:

```text
gender-party-game
```

Итоговый адрес:

```text
https://github.com/tryVellum/gender-party-game
```

## 1. Подготовка папки

Используйте подготовленную публичную папку проекта. Она уже содержит:

- `README.md`;
- лицензию MIT;
- `.gitignore`;
- `.env.example`;
- автоматические тесты;
- GitHub Actions;
- нейтральные демонстрационные вопросы;
- тестовое изображение без личных данных.

Перед публикацией ещё раз проверьте, что в папке нет:

- файла `.env`;
- базы `instance/game.sqlite`;
- папок `.venv`, `venv`, `.test-venv`;
- личных фотографий;
- вопросов с фамилиями, адресами или личными историями;
- токенов, паролей и ключей.

## 2. Установите Git

Проверьте в PowerShell:

```powershell
git --version
```

Если команда не найдена, установите Git for Windows, затем заново откройте PowerShell.

Во время установки удобно оставить включённым **Git Credential Manager**: он позволяет войти через браузер и не вводить токен при каждом `push`.

## 3. Настройте имя автора коммитов

Выполните один раз:

```powershell
git config --global user.name "tryVellum"
git config --global user.email "ВАШ_EMAIL_ИЗ_GITHUB"
```

Проверка:

```powershell
git config --global --list
```

Можно использовать приватный GitHub email формата `ID+tryVellum@users.noreply.github.com`, если он показан в настройках аккаунта GitHub.

## 4. Создайте пустой репозиторий на GitHub

1. Войдите в аккаунт `tryVellum`.
2. Нажмите значок **+** в правом верхнем углу.
3. Выберите **New repository**.
4. В поле **Owner** выберите `tryVellum`.
5. Введите имя:

```text
gender-party-game
```

6. Description:

```text
Локальная многопользовательская викторина для гендер-пати на Flask и Socket.IO
```

7. Выберите **Public**.
8. Не включайте:
   - Add a README file;
   - Add .gitignore;
   - Choose a license.

Эти файлы уже подготовлены локально. Если создать их повторно на GitHub, перед первым `push` возникнет лишний конфликт истории.

9. Нажмите **Create repository**.

## 5. Откройте PowerShell в папке проекта

Пример:

```powershell
cd "C:\Users\NAndrunin\Desktop\gender-party-game-github"
```

Убедитесь, что в папке видны `app.py`, `README.md` и `LICENSE`:

```powershell
Get-ChildItem
```

## 6. Инициализируйте Git

```powershell
git init
git branch -M main
```

## 7. Проверьте, что секретные файлы игнорируются

Сначала посмотрите полный статус:

```powershell
git status
```

Файл `.env` не должен находиться в разделе **Untracked files**.

Дополнительная проверка:

```powershell
git check-ignore -v .env
git check-ignore -v instance\game.sqlite
git check-ignore -v .venv
```

Для каждого существующего файла команда должна показать правило из `.gitignore`.

Если локального `.env` или базы нет, Git может вывести пустой результат — это нормально.

## 8. Добавьте файлы и ещё раз проверьте состав

```powershell
git add .
git status
```

В списке подготовленных файлов должны быть исходники, README, лицензия, демонстрационная картинка и workflow.

Не должно быть:

```text
.env
instance/game.sqlite
.venv/
__pycache__/
```

Проверка уже отслеживаемых нежелательных файлов:

```powershell
git ls-files | Select-String -Pattern "(^|/)\.env$|game\.sqlite|\.venv|__pycache__"
```

Команда не должна ничего вывести.

Обратите внимание: `.env.example` должен находиться в репозитории — это безопасный шаблон, а не локальный секрет.

## 9. Создайте первый коммит

```powershell
git commit -m "Initial public release"
```

Проверьте:

```powershell
git log --oneline -1
```

## 10. Подключите репозиторий GitHub

```powershell
git remote add origin https://github.com/tryVellum/gender-party-game.git
git remote -v
```

Ожидаемый результат содержит `origin` для fetch и push.

Если `origin` уже существует:

```powershell
git remote set-url origin https://github.com/tryVellum/gender-party-game.git
```

## 11. Отправьте проект

```powershell
git push -u origin main
```

При первом входе Git Credential Manager обычно откроет браузер. Авторизуйтесь в аккаунте `tryVellum` и подтвердите доступ.

GitHub больше не принимает обычный пароль аккаунта для операций Git по HTTPS. При ручной авторизации используется Personal Access Token вместо пароля, но для Windows проще и безопаснее вход через Git Credential Manager или GitHub CLI.

После успешной отправки обновите страницу репозитория.

## 12. Проверьте результат на GitHub

На главной странице должны отображаться:

- описание из `README.md`;
- значок лицензии MIT;
- папки `data`, `static`, `templates`, `tests`;
- вкладка **Actions**;
- последний коммит в ветке `main`.

Откройте вкладку **Actions** и дождитесь завершения workflow **CI**. Тесты запускаются для Python 3.11, 3.12 и 3.13.

Если workflow зелёный, автоматическая проверка прошла.

## 13. Настройте карточку репозитория

На главной странице в блоке **About** нажмите шестерёнку.

Description:

```text
Локальная многопользовательская викторина для гендер-пати на Flask и Socket.IO
```

Topics:

```text
python
flask
socketio
party-game
gender-reveal
local-network
quiz-game
```

Можно включить **Releases** и **Issues**.

## 14. Сделайте репозиторий шаблоном

Это удобно для других пользователей: вместо fork они смогут нажать **Use this template** и создать собственную копию без общей истории коммитов.

1. Откройте **Settings** репозитория.
2. Раздел **General**.
3. Найдите параметр **Template repository**.
4. Поставьте галочку.

После этого на главной странице появится кнопка **Use this template**.

## 15. Создайте релиз v1.0.0

### Вариант через Git

```powershell
git tag -a v1.0.0 -m "First public release"
git push origin v1.0.0
```

Затем на GitHub:

1. Откройте **Releases**.
2. Нажмите **Draft a new release**.
3. Выберите тег `v1.0.0`.
4. Release title:

```text
Gender Party Game v1.0.0
```

5. Пример описания:

```markdown
Первый публичный релиз локальной игры для гендер-пати.

Включено:
- вопросы с выбором и текстовым ответом;
- фото-карточки;
- аукцион;
- финальное голосование;
- секретный раунд имён;
- QR-код подключения;
- настройка пола ребёнка через .env;
- автоматические тесты для Python 3.11–3.13.
```

6. Отметьте **Set as latest release**.
7. Нажмите **Publish release**.

GitHub автоматически предложит исходный код релиза в ZIP и TAR.GZ.

## 16. Как публиковать дальнейшие изменения

После редактирования проекта:

```powershell
git status
git add .
git commit -m "Краткое описание изменения"
git push
```

Пример:

```powershell
git add .
git commit -m "Improve question image layout"
git push
```

Перед каждым `git add .` проверяйте, что в папке не появились личные фотографии и локальный `.env`.

## 17. Как отменить случайное добавление файла до коммита

Если файл попал в staged:

```powershell
git restore --staged ПУТЬ_К_ФАЙЛУ
```

Пример:

```powershell
git restore --staged .env
```

Затем добавьте правило в `.gitignore`, если его ещё нет.

Если секрет уже был отправлен на GitHub, простого удаления новым коммитом недостаточно: он остаётся в истории. Сразу смените секрет и удалите его из истории репозитория.

## 18. Альтернатива: GitHub Desktop

1. Установите GitHub Desktop.
2. Войдите через браузер в аккаунт `tryVellum`.
3. Выберите **File → Add local repository**.
4. Укажите папку проекта.
5. Если Git ещё не инициализирован, выберите создание репозитория.
6. Создайте коммит `Initial public release`.
7. Нажмите **Publish repository**.
8. Имя: `gender-party-game`.
9. Снимите галочку **Keep this code private**, чтобы репозиторий был публичным.
10. Нажмите **Publish Repository**.

Командная строка предпочтительнее для первой публикации, потому что позволяет явно проверить `.gitignore` и состав коммита.
