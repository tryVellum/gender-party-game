#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"

python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt

.venv/bin/python init_env.py

printf '\nУстановка завершена. Настройте .env и запустите ./start_game.sh\n'
