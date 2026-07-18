from __future__ import annotations

import os
import re
import secrets

from dotenv import load_dotenv


load_dotenv()


class Config:
    """Application configuration loaded from environment variables."""

    SECRET_KEY: str = os.getenv("SECRET_KEY") or secrets.token_hex(32)
    ADMIN_SECRET_PATH: str = os.getenv("ADMIN_SECRET_PATH", "").strip().strip("/")
    ACTUAL_GENDER: str = os.getenv("ACTUAL_GENDER", "boy").strip().lower()
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "5000"))
    DEBUG: bool = os.getenv("DEBUG", "0") == "1"
    SOCKETIO_ASYNC_MODE: str = (
        os.getenv(
            "SOCKETIO_ASYNC_MODE",
            "eventlet",
        )
        .strip()
        .lower()
    )


if not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", Config.ADMIN_SECRET_PATH):
    raise ValueError(
        "ADMIN_SECRET_PATH must contain 8-80 Latin letters, digits, underscores or "
        "hyphens. Run init_env.py or create a valid .env file."
    )

if Config.ACTUAL_GENDER not in {"boy", "girl"}:
    raise ValueError("ACTUAL_GENDER must be either 'boy' or 'girl'.")

if Config.SOCKETIO_ASYNC_MODE not in {"eventlet", "threading"}:
    raise ValueError("SOCKETIO_ASYNC_MODE must be either 'eventlet' or 'threading'.")
