from __future__ import annotations

import os
import re
import secrets

from dotenv import load_dotenv


load_dotenv()


class Config:
    """Application configuration."""

    SECRET_KEY: str = os.getenv("SECRET_KEY") or secrets.token_hex(32)
    ADMIN_SECRET_PATH: str = os.getenv("ADMIN_SECRET_PATH", "").strip().strip("/")
    ACTUAL_GENDER: str = os.getenv("ACTUAL_GENDER", "boy").strip().lower()
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "5000"))
    DEBUG: bool = os.getenv("DEBUG", "0") == "1"
    SOCKETIO_ASYNC_MODE: str = (
        os.getenv(
            "SOCKETIO_ASYNC_MODE",
            "threading",
        )
        .strip()
        .lower()
    )


if not Config.ADMIN_SECRET_PATH:
    raise RuntimeError("ADMIN_SECRET_PATH must be set in .env.")

if not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", Config.ADMIN_SECRET_PATH):
    raise RuntimeError(
        "ADMIN_SECRET_PATH must contain 8-80 letters, digits, '-' or '_'."
    )

if Config.ACTUAL_GENDER not in {"boy", "girl"}:
    raise RuntimeError("ACTUAL_GENDER must be either 'boy' or 'girl'.")

if Config.SOCKETIO_ASYNC_MODE not in {
    "threading",
    "eventlet",
    "gevent",
    "gevent_uwsgi",
}:
    raise RuntimeError("Unsupported SOCKETIO_ASYNC_MODE value.")
