from __future__ import annotations

import json
import os
import secrets
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any


APP_DIRECTORY_NAME = "GenderPartyGame"
SOURCE_ROOT = Path(__file__).resolve().parent
IS_FROZEN = bool(getattr(sys, "frozen", False))
RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", SOURCE_ROOT)).resolve()
INSTALL_ROOT = Path(sys.executable).resolve().parent if IS_FROZEN else SOURCE_ROOT


def _default_local_app_data() -> Path:
    """Return a writable per-user application data directory."""
    configured = os.getenv("LOCALAPPDATA", "").strip()
    if configured:
        return Path(configured)

    if os.name == "nt":
        return Path.home() / "AppData" / "Local"

    return Path.home() / ".local" / "share"


def is_portable_mode() -> bool:
    """Return whether the packaged application should keep data beside the EXE."""
    return (
        os.getenv("GENDER_PARTY_PORTABLE", "0") == "1"
        or (INSTALL_ROOT / "portable.flag").is_file()
    )


def _resolve_app_data_root() -> Path:
    """Choose the mutable data root for source, installed, and portable modes."""
    explicit_root = os.getenv("GENDER_PARTY_DATA_DIR", "").strip()
    if explicit_root:
        return Path(explicit_root).expanduser().resolve()

    if not IS_FROZEN:
        return SOURCE_ROOT

    if is_portable_mode():
        return INSTALL_ROOT / "user-data"

    return _default_local_app_data() / APP_DIRECTORY_NAME


APP_DATA_ROOT = _resolve_app_data_root()
USER_DATA_DIR = APP_DATA_ROOT / "data"
INSTANCE_DIR = APP_DATA_ROOT / "instance"
LOG_DIR = APP_DATA_ROOT / "logs"
QUESTIONS_PATH = USER_DATA_DIR / "questions.json"
GAME_SETTINGS_PATH = INSTANCE_DIR / "game_settings.json"
RUNTIME_CONFIG_PATH = INSTANCE_DIR / "runtime_config.json"
DATABASE_PATH = INSTANCE_DIR / "game.sqlite"
_EXPLICIT_DATA_ROOT = bool(os.getenv("GENDER_PARTY_DATA_DIR", "").strip())
ENV_PATH = (
    APP_DATA_ROOT / ".env" if IS_FROZEN or _EXPLICIT_DATA_ROOT else SOURCE_ROOT / ".env"
)

RESOURCE_DATA_DIR = RESOURCE_ROOT / "data"
STATIC_DIR = RESOURCE_ROOT / "static"
TEMPLATES_DIR = RESOURCE_ROOT / "templates"
DEFAULT_QUESTIONS_PATH = RESOURCE_DATA_DIR / "questions.json"


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON atomically to avoid half-written settings after interruption."""
    path.parent.mkdir(parents=True, exist_ok=True)

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary_path = Path(temporary_name)

    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def ensure_user_data() -> None:
    """Create writable folders and copy editable defaults on first launch."""
    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    try:
        same_data_directory = USER_DATA_DIR.resolve() == RESOURCE_DATA_DIR.resolve()
    except OSError:
        same_data_directory = False

    if same_data_directory:
        return

    if not QUESTIONS_PATH.exists():
        if not DEFAULT_QUESTIONS_PATH.is_file():
            raise FileNotFoundError(
                f"Default questions file was not found: {DEFAULT_QUESTIONS_PATH}"
            )
        shutil.copy2(DEFAULT_QUESTIONS_PATH, QUESTIONS_PATH)

    if RESOURCE_DATA_DIR.is_dir():
        for source in RESOURCE_DATA_DIR.iterdir():
            if source.suffix.lower() not in {".jpg", ".jpeg"}:
                continue

            destination = USER_DATA_DIR / source.name
            if not destination.exists():
                shutil.copy2(source, destination)


def load_or_create_runtime_config() -> dict[str, Any]:
    """Load persistent private runtime settings or create them on first launch."""
    ensure_user_data()

    payload: dict[str, Any] = {}
    if RUNTIME_CONFIG_PATH.is_file():
        try:
            loaded = json.loads(RUNTIME_CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                payload = loaded
        except (OSError, json.JSONDecodeError):
            payload = {}

    changed = False

    secret_key = str(payload.get("secret_key", "")).strip()
    if len(secret_key) < 32:
        secret_key = secrets.token_hex(32)
        payload["secret_key"] = secret_key
        changed = True

    admin_secret_path = str(payload.get("admin_secret_path", "")).strip().strip("/")
    if not admin_secret_path:
        token = secrets.token_urlsafe(24).replace("-", "").replace("_", "")
        admin_secret_path = f"admin-{token[:28]}"
        payload["admin_secret_path"] = admin_secret_path
        changed = True

    try:
        port = int(payload.get("port", 5000))
    except (TypeError, ValueError):
        port = 5000

    if not 1024 <= port <= 65535:
        port = 5000

    if payload.get("port") != port:
        payload["port"] = port
        changed = True

    if changed or not RUNTIME_CONFIG_PATH.exists():
        _atomic_write_json(RUNTIME_CONFIG_PATH, payload)

    return payload
