#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ]; then
  ./setup.sh
fi

if [ ! -f .env ]; then
  .venv/bin/python init_env.py
fi

.venv/bin/python app.py
