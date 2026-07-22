from __future__ import annotations

import os
import re

from dotenv import load_dotenv

from runtime_paths import ENV_PATH, load_or_create_runtime_config


load_dotenv(ENV_PATH)
_RUNTIME_CONFIG = load_or_create_runtime_config()


class Config:
    """Application configuration for source, installed, and portable modes."""

    SECRET_KEY: str = os.getenv("SECRET_KEY") or str(_RUNTIME_CONFIG["secret_key"])
    ADMIN_SECRET_PATH: str = (
        (os.getenv("ADMIN_SECRET_PATH") or str(_RUNTIME_CONFIG["admin_secret_path"]))
        .strip()
        .strip("/")
    )
    ACTUAL_GENDER: str = os.getenv("ACTUAL_GENDER", "boy").strip().lower()
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", str(_RUNTIME_CONFIG["port"])))
    DEBUG: bool = os.getenv("DEBUG", "0") == "1"
    SOCKETIO_ASYNC_MODE: str = (
        os.getenv(
            "SOCKETIO_ASYNC_MODE",
            "threading",
        )
        .strip()
        .lower()
    )


if not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", Config.ADMIN_SECRET_PATH):
    raise RuntimeError(
        "ADMIN_SECRET_PATH must contain 8-80 letters, digits, '-' or '_'."
    )

if Config.ACTUAL_GENDER not in {"boy", "girl"}:
    raise RuntimeError("ACTUAL_GENDER must be either 'boy' or 'girl'.")

if not 1024 <= Config.PORT <= 65535:
    raise RuntimeError("PORT must be between 1024 and 65535.")

if Config.SOCKETIO_ASYNC_MODE not in {
    "threading",
    "eventlet",
    "gevent",
    "gevent_uwsgi",
}:
    raise RuntimeError("Unsupported SOCKETIO_ASYNC_MODE value.")
