from __future__ import annotations

import io
import json
import os
import shutil
from pathlib import Path
from unittest.mock import patch

from PIL import Image


os.environ.setdefault("ACTUAL_GENDER", "girl")
os.environ.setdefault("ADMIN_SECRET_PATH", "test-admin")
os.environ.setdefault("DEBUG", "0")
os.environ.setdefault("SOCKETIO_ASYNC_MODE", "threading")

from app import app, socketio  # noqa: E402
from database import (  # noqa: E402
    DATABASE_PATH,
    finish_answer_reveal,
    get_connection,
    get_game_state,
    get_question_by_id,
    list_players,
)


def remove_database_files() -> None:
    """Remove SQLite runtime files created by the smoke test."""
    for suffix in ("", "-shm", "-wal"):
        Path(f"{DATABASE_PATH}{suffix}").unlink(missing_ok=True)


def close_question_with_short_reveal(admin_client):
    """Close a question and verify idempotence without timing races."""

    def keep_reveal_state(state=None):
        """Return persisted state without starting the background timer."""
        return state or get_game_state()

    with (
        patch("app.ANSWER_REVEAL_PLAYER_DURATION_MS", 20),
        patch("app.ANSWER_REVEAL_ADMIN_DURATION_MS", 10),
        patch("app.ensure_answer_reveal_task", side_effect=keep_reveal_state),
    ):
        response = admin_client.post("/api/admin/questions/current/close")
        assert response.status_code == 200
        payload = response.get_json()
        assert payload["answer_reveal"]["correct_answer"]

        repeated_response = admin_client.post("/api/admin/questions/current/close")
        assert repeated_response.status_code == 200
        assert repeated_response.get_json()["already_closed"] is True

    sequence_id = payload["answer_reveal"]["sequence_id"]
    assert finish_answer_reveal(sequence_id) is True
    assert get_game_state()["current_phase"] == "waiting"
    return payload


def test_main_game_flow() -> None:
    """Exercise player entry, answer reveal, auction, final, secret and reset."""
    remove_database_files()

    from database import init_database, seed_questions

    init_database()
    seed_questions()

    assert socketio.server.async_mode == "threading"

    admin_client = app.test_client()
    player_client = app.test_client()

    assert player_client.get("/").status_code == 200
    assert player_client.get("/api/admin/board").status_code == 403
    assert player_client.get("/api/admin/editor").status_code == 403
    assert admin_client.get("/test-admin").status_code == 200
    assert admin_client.get("/test-admin/editor").status_code == 200
    assert admin_client.get("/api/admin/board").status_code == 200
    assert admin_client.get("/api/admin/player-link").status_code == 200
    assert player_client.get("/question-images/demo-balloons.jpg").status_code == 200

    source_questions = json.loads(
        Path("data/questions.json").read_text(encoding="utf-8")
    )
    editor_questions = []
    for source_question in source_questions:
        editor_question = dict(source_question)
        editor_question.pop("image", None)
        editor_questions.append(editor_question)

    editor_data_dir = Path("instance/test-editor-data")
    editor_data_dir.mkdir(parents=True, exist_ok=True)
    editor_questions_path = editor_data_dir / "questions.json"
    editor_settings_path = editor_data_dir / "game_settings.json"
    editor_questions_path.write_text(
        json.dumps(editor_questions, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    image_buffer = io.BytesIO()
    Image.new("RGB", (24, 24), "white").save(image_buffer, format="JPEG")
    image_buffer.seek(0)

    with (
        patch("app.DATA_DIR", editor_data_dir),
        patch("database.QUESTIONS_PATH", editor_questions_path),
        patch("database.GAME_SETTINGS_PATH", editor_settings_path),
    ):
        editor_response = admin_client.get("/api/admin/editor")
        assert editor_response.status_code == 200
        editor_payload = editor_response.get_json()
        assert len(editor_payload["questions"]) == 20

        save_editor_response = admin_client.post(
            "/api/admin/editor",
            data={
                "payload": json.dumps(
                    {
                        "actual_gender": "girl",
                        "questions": editor_payload["questions"],
                    },
                    ensure_ascii=False,
                ),
                "image_pregnancy_100": (image_buffer, "question-photo.jpg"),
            },
            content_type="multipart/form-data",
        )
        assert save_editor_response.status_code == 200
        saved_editor_payload = save_editor_response.get_json()
        assert saved_editor_payload["actual_gender"] == "girl"
        saved_first_question = next(
            question
            for question in saved_editor_payload["questions"]
            if question["id"] == "pregnancy_100"
        )
        assert saved_first_question["image"].endswith(".jpg")
        assert (editor_data_dir / saved_first_question["image"]).is_file()
        assert editor_settings_path.is_file()

    shutil.rmtree(editor_data_dir, ignore_errors=True)

    assert (
        player_client.post(
            "/api/player",
            json={"device_token": "token-1", "nickname": "Игрок 1"},
        ).status_code
        == 201
    )
    assert (
        player_client.post(
            "/api/player",
            json={"device_token": "token-2", "nickname": "Игрок 2"},
        ).status_code
        == 201
    )

    socket_client = socketio.test_client(app, flask_test_client=player_client)
    assert socket_client.is_connected()
    assert any(
        packet["name"] == "server_message" for packet in socket_client.get_received()
    )

    socket_client.emit("player_identify", {"device_token": "token-1"})
    assert any(
        packet["name"] == "player_identified" and packet["args"][0]["ok"] is True
        for packet in socket_client.get_received()
    )

    assert (
        admin_client.post("/api/admin/questions/pregnancy_100/open").status_code == 200
    )
    assert (
        player_client.post(
            "/api/player/answer",
            json={
                "device_token": "token-1",
                "question_id": "pregnancy_100",
                "answer": "40 недель",
            },
        ).status_code
        == 200
    )

    close_payload = close_question_with_short_reveal(admin_client)
    assert close_payload["answer_reveal"]["correct_answer"] == "40 недель"
    assert (
        close_payload["answer_reveal"]["admin_reveal_until_ms"]
        - close_payload["answer_reveal"]["started_at_ms"]
        == 10
    )
    assert (
        close_payload["answer_reveal"]["player_reveal_until_ms"]
        - close_payload["answer_reveal"]["started_at_ms"]
        == 20
    )
    assert (
        next(player for player in list_players() if player["nickname"] == "Игрок 1")[
            "score"
        ]
        == 100
    )

    # A stale timestamp must not prevent closing a question after several minutes.
    assert (
        admin_client.post("/api/admin/questions/pregnancy_200/open").status_code == 200
    )
    with get_connection() as connection:
        connection.execute(
            "UPDATE game_state "
            "SET updated_at = datetime('now', '-3 minutes') "
            "WHERE id = 1"
        )
    assert (
        player_client.post(
            "/api/player/answer",
            json={
                "device_token": "token-1",
                "question_id": "pregnancy_200",
                "answer": get_question_by_id("pregnancy_200")["correct_answers"][0],
            },
        ).status_code
        == 200
    )
    close_question_with_short_reveal(admin_client)

    with patch("app.probe_active_player_tokens", return_value={"token-1"}):
        auction_open_response = admin_client.post(
            "/api/admin/questions/parents_500/open"
        )

    assert auction_open_response.status_code == 200

    bid_response = player_client.post(
        "/api/player/auction-bid",
        json={
            "device_token": "token-1",
            "question_id": "parents_500",
            "bid": 50,
        },
    )
    assert bid_response.status_code == 200
    assert bid_response.get_json()["winner"]["nickname"] == "Игрок 1"

    assert (
        player_client.post(
            "/api/player/answer",
            json={
                "device_token": "token-1",
                "question_id": "parents_500",
                "answer": "два",
            },
        ).status_code
        == 200
    )

    close_question_with_short_reveal(admin_client)

    with get_connection() as connection:
        connection.execute("UPDATE questions SET is_used = 1")

    assert admin_client.post("/api/admin/final/start").status_code == 200
    assert get_game_state()["actual_gender"] == "girl"

    assert (
        player_client.post(
            "/api/player/final-vote",
            json={"device_token": "token-1", "choice": "girl"},
        ).status_code
        == 200
    )

    with (
        patch("app.FINAL_SEQUENCE_START_DELAY_MS", 1),
        patch("app.FINAL_DRUMROLL_DURATION_MS", 1),
        patch("app.FINAL_REVEAL_BROADCAST_LEAD_MS", 0),
    ):
        reveal_response = admin_client.post("/api/admin/final/reveal")
        assert reveal_response.status_code == 200
        assert reveal_response.get_json()["schedule"]["sequence_id"]
        socketio.sleep(0.1)

    final_state = get_game_state()
    assert final_state["current_phase"] == "final_revealed"
    assert final_state["actual_gender"] == "girl"

    assert admin_client.post("/api/admin/secret/start").status_code == 200
    assert (
        player_client.post(
            "/api/player/baby-name",
            json={"device_token": "token-1", "name": "Саша"},
        ).status_code
        == 200
    )
    assert (
        player_client.post(
            "/api/player/baby-name",
            json={"device_token": "token-1", "name": "Миша"},
        ).status_code
        == 400
    )

    assert admin_client.post("/api/admin/game/reset").status_code == 200
    assert list_players() == []
    assert get_game_state()["actual_gender"] == "girl"

    socket_client.disconnect()
    remove_database_files()
