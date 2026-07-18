from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ACTUAL_GENDER", "girl")
os.environ.setdefault("ADMIN_SECRET_PATH", "test-admin")
os.environ.setdefault("DEBUG", "0")
os.environ.setdefault("SOCKETIO_ASYNC_MODE", "threading")

from app import app, socketio  # noqa: E402
from database import DATABASE_PATH, get_connection, get_game_state, list_players  # noqa: E402


def remove_database_files() -> None:
    """Remove SQLite runtime files created by the smoke test."""
    for suffix in ("", "-shm", "-wal"):
        Path(f"{DATABASE_PATH}{suffix}").unlink(missing_ok=True)


def test_main_game_flow() -> None:
    """Exercise player entry, regular question, auction, final, secret round and reset."""
    remove_database_files()

    # Recreate the database because app initialization happened during module import.
    from database import init_database, seed_questions

    init_database()
    seed_questions()

    assert socketio.server.async_mode == "threading"

    admin_client = app.test_client()
    player_client = app.test_client()

    assert player_client.get("/").status_code == 200
    assert player_client.get("/api/admin/board").status_code == 403
    assert admin_client.get("/test-admin").status_code == 200
    assert admin_client.get("/api/admin/board").status_code == 200
    assert admin_client.get("/api/admin/player-link").status_code == 200
    assert player_client.get("/question-images/demo-balloons.jpg").status_code == 200

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
    identification_packets = socket_client.get_received()
    assert any(
        packet["name"] == "player_identified" and packet["args"][0]["ok"] is True
        for packet in identification_packets
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
    assert admin_client.post("/api/admin/questions/current/close").status_code == 200
    assert (
        next(player for player in list_players() if player["nickname"] == "Игрок 1")[
            "score"
        ]
        == 100
    )

    with patch(
        "app.probe_active_player_tokens",
        return_value={"token-1"},
    ):
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
    assert admin_client.post("/api/admin/questions/current/close").status_code == 200

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

        reveal_payload = reveal_response.get_json()
        assert reveal_payload["schedule"]["sequence_id"]

        # Give the Socket.IO background task time to complete the shortened reveal.
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
