from __future__ import annotations

import ctypes
import json
import logging
import os
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from logging.handlers import RotatingFileHandler
from pathlib import Path
from tkinter import Tk, messagebox
from typing import Any

import pystray
from PIL import Image

from runtime_paths import APP_DATA_ROOT, LOG_DIR, RESOURCE_ROOT, ensure_user_data
from version import APP_VERSION


APP_TITLE = "Gender Party Game"
MUTEX_NAME = "Local\\GenderPartyGameDesktopLauncher"
HEALTH_TIMEOUT_SECONDS = 25
POLL_INTERVAL_SECONDS = 0.25
_mutex_handle: int | None = None


def configure_logging() -> Path:
    """Configure a rotating launcher log in the writable user data folder."""
    ensure_user_data()
    log_path = LOG_DIR / "gender-party-game.log"

    handler = RotatingFileHandler(
        log_path,
        maxBytes=2 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        )
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    return log_path


def show_message(title: str, message: str, *, error: bool = False) -> None:
    """Show a native Windows dialog without leaving a visible Tk window."""
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        if error:
            messagebox.showerror(title, message, parent=root)
        else:
            messagebox.showinfo(title, message, parent=root)
    finally:
        root.destroy()


def acquire_single_instance_mutex() -> bool:
    """Acquire a named Windows mutex and report whether this is the first instance."""
    global _mutex_handle

    if os.name != "nt":
        return True

    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.argtypes = [
        ctypes.c_void_p,
        ctypes.c_bool,
        ctypes.c_wchar_p,
    ]
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    kernel32.GetLastError.argtypes = []
    kernel32.GetLastError.restype = ctypes.c_ulong

    handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if not handle:
        return True

    _mutex_handle = int(handle)
    return kernel32.GetLastError() != 183


def server_base_url() -> str:
    """Build the local loopback URL after application configuration is loaded."""
    from config import Config

    return f"http://127.0.0.1:{Config.PORT}"


def admin_url() -> str:
    """Return the private local administrator URL."""
    from config import Config

    return f"{server_base_url()}/{Config.ADMIN_SECRET_PATH}"


def editor_url() -> str:
    """Return the private game editor URL."""
    from config import Config

    return f"{server_base_url()}/{Config.ADMIN_SECRET_PATH}/editor"


def open_url(url: str) -> None:
    """Open a URL in the user's default browser unless disabled for smoke tests."""
    if os.getenv("GENDER_PARTY_NO_BROWSER", "0") == "1":
        return
    webbrowser.open(url, new=2)


def read_health() -> dict[str, Any] | None:
    """Read the local health endpoint when the expected game server is running."""
    try:
        with urllib.request.urlopen(
            f"{server_base_url()}/api/health",
            timeout=1.0,
        ) as response:
            if response.status != 200:
                return None
            payload = json.loads(response.read().decode("utf-8"))
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        urllib.error.URLError,
    ):
        return None

    if payload.get("app") != "gender-party-game":
        return None

    return payload


def wait_for_server() -> bool:
    """Wait until the local Flask server answers its identity endpoint."""
    deadline = time.monotonic() + HEALTH_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if read_health() is not None:
            return True
        time.sleep(POLL_INTERVAL_SECONDS)
    return False


def run_server() -> None:
    """Initialize the database and run the Socket.IO server in a background thread."""
    try:
        from app import app, socketio
        from config import Config
        from database import init_database, seed_questions

        init_database()
        seed_questions()

        logging.info(
            "Starting Gender Party Game %s on %s:%s",
            APP_VERSION,
            Config.HOST,
            Config.PORT,
        )

        socketio.run(
            app,
            host=Config.HOST,
            port=Config.PORT,
            debug=False,
            use_reloader=False,
            allow_unsafe_werkzeug=True,
        )
    except BaseException:
        logging.exception("The local game server stopped unexpectedly.")


def load_tray_image() -> Image.Image:
    """Load the bundled application icon for the notification area."""
    candidates = (
        RESOURCE_ROOT / "assets" / "gender-party.ico",
        RESOURCE_ROOT / "assets" / "gender-party.png",
    )

    for candidate in candidates:
        if candidate.is_file():
            with Image.open(candidate) as source:
                return source.convert("RGBA")

    return Image.new("RGBA", (64, 64), (255, 255, 255, 255))


def exit_application(icon: pystray.Icon, _item: pystray.MenuItem | None = None) -> None:
    """Stop the tray icon and terminate the local server process."""
    logging.info("Application exit requested from the tray menu.")
    icon.stop()
    os._exit(0)


def open_data_folder() -> None:
    """Open the writable user data folder in Windows Explorer."""
    if os.name == "nt":
        os.startfile(APP_DATA_ROOT)  # type: ignore[attr-defined]
        return

    open_url(APP_DATA_ROOT.as_uri())


def create_tray_icon() -> pystray.Icon:
    """Create the notification-area controls for the background server."""
    menu = pystray.Menu(
        pystray.MenuItem(
            "Открыть игру",
            lambda _icon, _item: open_url(admin_url()),
            default=True,
        ),
        pystray.MenuItem(
            "Редактор вопросов",
            lambda _icon, _item: open_url(editor_url()),
        ),
        pystray.MenuItem(
            "Папка данных",
            lambda _icon, _item: open_data_folder(),
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Завершить игру", exit_application),
    )

    return pystray.Icon(
        "GenderPartyGame",
        load_tray_image(),
        APP_TITLE,
        menu,
    )


def main() -> int:
    """Start or reopen the installed local game application."""
    log_path = configure_logging()
    logging.info("Launcher started. Version=%s", APP_VERSION)

    try:
        first_instance = acquire_single_instance_mutex()

        if not first_instance:
            if wait_for_server():
                open_url(admin_url())
                return 0

            show_message(
                APP_TITLE,
                "Игра уже запускается. Подождите несколько секунд и нажмите ярлык ещё раз.",
            )
            return 0

        existing_health = read_health()
        if existing_health is not None:
            open_url(admin_url())
            return 0

        server_thread = threading.Thread(
            target=run_server,
            name="gender-party-server",
            daemon=True,
        )
        server_thread.start()

        if not wait_for_server():
            show_message(
                "Не удалось запустить игру",
                "Сервер не запустился. Закройте другие программы, которые могут "
                "использовать порт 5000, и попробуйте снова.\n\n"
                f"Подробности записаны в:\n{log_path}",
                error=True,
            )
            return 1

        open_url(admin_url())

        if os.getenv("GENDER_PARTY_NO_TRAY", "0") == "1":
            while server_thread.is_alive():
                time.sleep(0.5)
            return 0

        tray_icon = create_tray_icon()
        tray_icon.run()
        return 0
    except Exception:
        logging.exception("Unexpected launcher failure")
        show_message(
            "Ошибка запуска Gender Party Game",
            f"Не удалось запустить игру.\n\nПодробности записаны в:\n{log_path}",
            error=True,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
