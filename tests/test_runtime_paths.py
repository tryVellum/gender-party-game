from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def test_first_launch_creates_private_runtime_files(tmp_path: Path) -> None:
    """Create editable defaults and persistent private settings in an isolated folder."""
    project_root = Path(__file__).resolve().parents[1]
    data_root = tmp_path / "GenderPartyGame"
    environment = os.environ.copy()
    environment["GENDER_PARTY_DATA_DIR"] = str(data_root)
    environment.pop("ADMIN_SECRET_PATH", None)
    environment.pop("SECRET_KEY", None)

    script = """
from runtime_paths import (
    GAME_SETTINGS_PATH,
    QUESTIONS_PATH,
    RUNTIME_CONFIG_PATH,
    ensure_user_data,
    load_or_create_runtime_config,
)
ensure_user_data()
config = load_or_create_runtime_config()
from config import Config
assert Config.ADMIN_SECRET_PATH == config[\"admin_secret_path\"]
assert Config.SECRET_KEY == config[\"secret_key\"]
print(QUESTIONS_PATH)
print(RUNTIME_CONFIG_PATH)
print(config[\"admin_secret_path\"])
"""

    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=project_root,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout.strip()
    questions_path = data_root / "data" / "questions.json"
    runtime_config_path = data_root / "instance" / "runtime_config.json"
    assert questions_path.is_file()
    assert runtime_config_path.is_file()

    questions = json.loads(questions_path.read_text(encoding="utf-8"))
    runtime_config = json.loads(runtime_config_path.read_text(encoding="utf-8"))
    assert len(questions) == 20
    assert runtime_config["admin_secret_path"].startswith("admin-")
    assert len(runtime_config["secret_key"]) >= 32
