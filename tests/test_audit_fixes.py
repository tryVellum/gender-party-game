from __future__ import annotations

import concurrent.futures
import os
from pathlib import Path
from unittest.mock import patch

os.environ["ACTUAL_GENDER"] = "girl"
os.environ["ADMIN_SECRET_PATH"] = "test-admin"
os.environ["DEBUG"] = "0"
os.environ["SOCKETIO_ASYNC_MODE"] = "threading"

import pytest  # noqa: E402
from app import app, socketio  # noqa: E402
from database import (  # noqa: E402
    DATABASE_PATH,
    build_admin_board,
    create_player,
    force_finish_auction,
    get_game_state,
    init_database,
    reset_game,
    reveal_final_round,
    save_final_vote,
    schedule_final_reveal,
    seed_questions,
    set_current_question,
    set_player_connected,
    start_final_round,
    start_secret_round,
    submit_baby_name,
    update_player_score,
    vote_for_baby_name,
)
from launcher import wait_for_server  # noqa: E402


def setup_clean_db() -> None:
    """Prepare a fresh database for testing."""
    for suffix in ("", "-shm", "-wal"):
        Path(f"{DATABASE_PATH}{suffix}").unlink(missing_ok=True)
    init_database()
    seed_questions()
    reset_game(actual_gender="girl")


def test_build_admin_board_excludes_correct_answers() -> None:
    """Ensure build_admin_board never contains correct_answers."""
    setup_clean_db()
    board = build_admin_board()
    assert len(board) > 0

    for category_group in board:
        assert "category" in category_group
        for question in category_group["questions"]:
            if question is not None:
                assert "correct_answers" not in question
                assert "points" in question
                assert "id" in question


def test_socket_admin_request_board_security() -> None:
    """Socket event admin_request_board must reject unauthenticated clients."""
    setup_clean_db()

    # Client without admin session
    guest_client = app.test_client()
    socket_guest = socketio.test_client(app, flask_test_client=guest_client)
    assert socket_guest.is_connected()
    socket_guest.get_received()  # clear initial messages

    socket_guest.emit("admin_request_board")
    guest_messages = socket_guest.get_received()
    assert not any(msg["name"] == "board_updated" for msg in guest_messages)
    socket_guest.disconnect()

    # Admin client with authenticated session
    admin_client = app.test_client()
    admin_response = admin_client.get("/test-admin")
    assert admin_response.status_code == 200

    socket_admin = socketio.test_client(app, flask_test_client=admin_client)
    assert socket_admin.is_connected()
    socket_admin.get_received()

    socket_admin.emit("admin_request_board")
    admin_messages = socket_admin.get_received()
    board_events = [msg for msg in admin_messages if msg["name"] == "board_updated"]
    assert len(board_events) == 1
    board_payload = board_events[0]["args"][0]
    for row in board_payload["board"]:
        for q in row["questions"]:
            if q is not None:
                assert "correct_answers" not in q

    socket_admin.disconnect()


def test_force_finish_auction_endpoint_and_logic() -> None:
    """Verify force finish auction resolves deadlocks when bidders disconnect."""
    setup_clean_db()

    p1 = create_player("token-p1", "Игрок 1")
    p2 = create_player("token-p2", "Игрок 2")
    update_player_score(player_id=p1["id"], points_delta=200)
    update_player_score(player_id=p2["id"], points_delta=150)

    admin_client = app.test_client()
    admin_client.get("/test-admin")

    # Non-admin gets 403 on force-finish
    anon_client = app.test_client()
    assert anon_client.post("/api/admin/auction/force-finish").status_code == 403

    # Outside auction_bidding returns 409
    assert admin_client.post("/api/admin/auction/force-finish").status_code == 409

    # Open auction question (parents_300 is the default auction question)
    with patch("app.probe_active_player_tokens", return_value={"token-p1", "token-p2"}):
        res = admin_client.post("/api/admin/questions/parents_300/open")
        assert res.status_code == 200

    state = get_game_state()
    assert state["current_phase"] == "auction_bidding"

    # Only player 1 submits bid, player 2 goes offline / never bids
    bid_res = anon_client.post(
        "/api/player/auction-bid",
        json={"device_token": "token-p1", "question_id": "parents_300", "bid": 100},
    )
    assert bid_res.status_code == 200
    assert bid_res.get_json()["winner"] is None  # Waiting for p2

    # Normal close fails because bidding is not finished
    close_res = admin_client.post("/api/admin/questions/current/close")
    assert close_res.status_code == 409
    assert close_res.get_json()["error"] == "auction_bidding_not_finished"

    # Admin forces auction finish
    force_res = admin_client.post("/api/admin/auction/force-finish")
    assert force_res.status_code == 200
    data = force_res.get_json()
    assert data["ok"] is True
    assert data["winner"]["player_id"] == p1["id"]
    assert data["winner"]["bid"] == 100

    # Phase is now auction_question
    new_state = get_game_state()
    assert new_state["current_phase"] == "auction_question"
    assert new_state["auction_winner_player_id"] == p1["id"]


def test_force_finish_auction_when_no_bids_submitted() -> None:
    """Verify force finish works even if 0 bids were submitted."""
    setup_clean_db()

    p1 = create_player("token-solo", "Соло Игрок")
    update_player_score(player_id=p1["id"], points_delta=100)

    admin_client = app.test_client()
    admin_client.get("/test-admin")

    with patch("app.probe_active_player_tokens", return_value={"token-solo"}):
        admin_client.post("/api/admin/questions/parents_300/open")

    assert get_game_state()["current_phase"] == "auction_bidding"

    # No one placed any bids; admin forces finish
    force_res = admin_client.post("/api/admin/auction/force-finish")
    assert force_res.status_code == 200
    data = force_res.get_json()
    assert data["winner"]["player_id"] == p1["id"]
    assert data["winner"]["bid"] == 0
    assert get_game_state()["current_phase"] == "auction_question"


def test_final_negative_score_not_doubled() -> None:
    """Correct guess in final must not double negative score (worsening penalty)."""
    setup_clean_db()

    p_neg = create_player("token-neg", "Игрок В Минусе")
    p_pos = create_player("token-pos", "Игрок В Плюсе")

    update_player_score(player_id=p_neg["id"], points_delta=-200)
    update_player_score(player_id=p_pos["id"], points_delta=300)

    start_final_round(actual_gender="girl")
    save_final_vote(player_id=p_neg["id"], choice="girl")
    save_final_vote(player_id=p_pos["id"], choice="girl")

    schedule_final_reveal(
        drumroll_start_at_ms=1000,
        reveal_at_ms=2000,
        sequence_id="test-seq-1",
    )

    score_updates = reveal_final_round()
    updates_by_id = {u["player_id"]: u for u in score_updates}

    # Negative player must NOT have score = -400; penalty is reset to 0
    assert updates_by_id[p_neg["id"]]["old_score"] == -200
    assert updates_by_id[p_neg["id"]]["score"] == 0
    assert updates_by_id[p_neg["id"]]["points_delta"] == 200

    # Positive player doubled normally: 300 -> 600
    assert updates_by_id[p_pos["id"]]["old_score"] == 300
    assert updates_by_id[p_pos["id"]]["score"] == 600
    assert updates_by_id[p_pos["id"]]["points_delta"] == 300


def test_atomic_baby_name_voting() -> None:
    """Verify vote_for_baby_name rejects insufficient funds and updates score atomically."""
    setup_clean_db()

    p = create_player("token-vote", "Голосующий")
    update_player_score(player_id=p["id"], points_delta=50)

    # Set up secret round
    start_final_round(actual_gender="girl")
    schedule_final_reveal(
        drumroll_start_at_ms=1000,
        reveal_at_ms=2000,
        sequence_id="test-seq-final",
    )
    reveal_final_round()
    start_secret_round()

    name_item = submit_baby_name(player_id=p["id"], name="Алиса")
    name_id = name_item["id"]

    # Trying to spend more than balance (100 > 50) must raise ValueError
    with pytest.raises(ValueError, match="Нельзя отдать больше баллов"):
        vote_for_baby_name(player_id=p["id"], name_id=name_id, amount=100)

    # Spending valid amount (30 <= 50) must succeed
    result = vote_for_baby_name(player_id=p["id"], name_id=name_id, amount=30)
    assert result["score"] == 20
    assert result["points_delta"] == -30


def test_wait_for_server_dead_thread() -> None:
    """wait_for_server must return False immediately if server_thread terminates."""

    class DummyThread:
        def is_alive(self):
            return False

    with patch("launcher.read_health", return_value=None):
        with patch("launcher.POLL_INTERVAL_SECONDS", 0.01):
            assert wait_for_server(DummyThread()) is False


def test_force_finish_auction_when_participants_empty_prefers_connected() -> None:
    """When auction_participants has 0 rows, fallback must select connected player without SQL error."""
    setup_clean_db()

    p_offline = create_player("token-off", "Офлайн Игрок")
    p_online = create_player("token-on", "Онлайн Игрок")

    update_player_score(player_id=p_offline["id"], points_delta=500)
    update_player_score(player_id=p_online["id"], points_delta=100)

    # p_online is connected (connected=1), p_offline is not
    set_player_connected("token-off", False)
    set_player_connected("token-on", True)

    set_current_question("parents_300", phase="auction_bidding")

    # Force finish when auction_participants is empty
    winner = force_finish_auction("parents_300")
    assert winner is not None
    assert winner["player_id"] == p_online["id"]
    assert winner["bid"] == 0

    state = get_game_state()
    assert state["current_phase"] == "auction_question"
    assert state["auction_winner_player_id"] == p_online["id"]


def test_api_game_state_returns_player_profile() -> None:
    """api_game_state must include player object for valid device_token to support mobile resync."""
    setup_clean_db()

    player = create_player("token-resync", "Ресинхронизируемый")
    update_player_score(player_id=player["id"], points_delta=175)

    client = app.test_client()
    res = client.get("/api/game-state?device_token=token-resync")
    assert res.status_code == 200
    data = res.get_json()

    assert data["ok"] is True
    assert "player" in data
    assert data["player"]["id"] == player["id"]
    assert data["player"]["nickname"] == "Ресинхронизируемый"
    assert data["player"]["score"] == 175


def test_concurrent_writes_and_atomic_balance() -> None:
    """Concurrent baby name votes must never overdraft balance or deadlock SQLite."""
    setup_clean_db()

    player = create_player("token-stress", "Стресс Игрок")
    update_player_score(player_id=player["id"], points_delta=100)

    start_final_round(actual_gender="girl")
    schedule_final_reveal(
        drumroll_start_at_ms=1000,
        reveal_at_ms=2000,
        sequence_id="test-seq-stress",
    )
    reveal_final_round()
    start_secret_round()

    item = submit_baby_name(player_id=player["id"], name="София")
    name_id = item["id"]

    # 10 concurrent threads each attempt to vote 20 points (total 200 > 100 available)
    successes = 0
    failures = 0

    def attempt_vote() -> bool:
        try:
            vote_for_baby_name(player_id=player["id"], name_id=name_id, amount=20)
            return True
        except ValueError:
            return False

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(attempt_vote) for _ in range(10)]
        for f in concurrent.futures.as_completed(futures):
            if f.result():
                successes += 1
            else:
                failures += 1

    # Exactly 5 transactions of 20 points should succeed (5 * 20 = 100), and 5 must fail
    assert successes == 5
    assert failures == 5
