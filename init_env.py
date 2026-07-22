from __future__ import annotations

import secrets
from pathlib import Path


ENV_PATH = Path(__file__).resolve().parent / ".env"


def build_env_text() -> str:
    """Build safe local development settings."""
    secret_key = secrets.token_hex(32)
    admin_path = f"admin-{secrets.token_urlsafe(20)}"
    return (
        f"SECRET_KEY={secret_key}\n"
        f"ADMIN_SECRET_PATH={admin_path}\n"
        "ACTUAL_GENDER=boy\n"
        "HOST=0.0.0.0\n"
        "PORT=5000\n"
        "DEBUG=0\n"
        "SOCKETIO_ASYNC_MODE=threading\n"
    )


def main() -> None:
    """Create .env for source development without overwriting existing secrets."""
    if ENV_PATH.exists():
        print(f"Файл уже существует: {ENV_PATH}")
        return

    ENV_PATH.write_text(build_env_text(), encoding="utf-8", newline="\n")
    print(f"Создан файл: {ENV_PATH}")


if __name__ == "__main__":
    main()
