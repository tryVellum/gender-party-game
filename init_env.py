from __future__ import annotations

import secrets
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
EXAMPLE_PATH = BASE_DIR / ".env.example"


def create_env_file() -> bool:
    """Create a local .env file with generated secret values if it does not exist."""
    if ENV_PATH.exists():
        return False

    template = EXAMPLE_PATH.read_text(encoding="utf-8")
    secret_key = secrets.token_urlsafe(48)
    admin_path = f"admin-{secrets.token_hex(8)}"

    content = template.replace(
        "replace-with-a-long-random-string",
        secret_key,
    ).replace(
        "my-private-admin-page",
        admin_path,
    )

    ENV_PATH.write_text(content, encoding="utf-8")
    print(f"Создан файл: {ENV_PATH}")
    print(f"Секретный адрес администратора: http://127.0.0.1:5000/{admin_path}")
    return True


if __name__ == "__main__":
    if not create_env_file():
        print(f"Файл {ENV_PATH} уже существует. Настройки сохранены без изменений.")
