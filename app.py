from __future__ import annotations

import base64
import socket
import time
import uuid
from io import BytesIO
from pathlib import Path
from typing import Any

import qrcode

from flask import Flask, abort, jsonify, render_template, request, send_from_directory, url_for
from flask_socketio import SocketIO, emit, join_room

from config import Config
from database import (
    NicknameAlreadyExistsError,
    QuestionAlreadyUsedError,
    QuestionNotFoundError,
    are_all_auction_bids_submitted,
    are_all_questions_used,
    build_admin_board,
    close_auction_question_and_calculate_score,
    close_question_and_calculate_scores,
    create_auction_snapshot,
    create_player,
    get_answer_for_player,
    get_auction_bid_for_player,
    get_auction_progress,
    get_auction_winner,
    get_game_state,
    get_player_by_token,
    get_question_by_id,
    init_database,
    list_auction_participants,
    list_players,
    save_auction_bid,
    save_player_answer,
    seed_questions,
    set_auction_winner,
    set_current_question,
    set_player_connected,
    synchronize_player_connections,
    get_final_vote_counts,
    get_final_vote_for_player,
    reveal_final_round,
    save_final_vote,
    schedule_final_reveal,
    start_final_round,
    get_baby_name_winner,
    list_baby_names,
    start_secret_round,
    submit_baby_name,
    vote_for_baby_name,
    reset_game,
)


app = Flask(__name__)
app.config.from_object(Config)

DATA_DIR = Path(app.root_path) / "data"

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="eventlet",
    ping_interval=5,
    ping_timeout=10,
)


connected_player_tokens_by_sid: dict[str, str] = {}
connected_sids_by_player_token: dict[str, set[str]] = {}
presence_acknowledgements_by_probe: dict[str, set[str]] = {}
active_final_reveal_sequences: set[str] = set()
auction_opening_question_ids: set[str] = set()

PRESENCE_PROBE_FIRST_WAIT_SECONDS = 0.8
PRESENCE_PROBE_SECOND_WAIT_SECONDS = 1.6
FINAL_DRUMROLL_DURATION_MS = 7_000
FINAL_SEQUENCE_START_DELAY_MS = 900
FINAL_REVEAL_BROADCAST_LEAD_MS = 700
ALLOWED_AUDIO_FILES = {
    "zvuk-barabannoj-drobi.mp3",
    "the-sound-of-happy-baby-laughter.mp3",
    "piano-chord-disturbing.mp3",
}


def get_lan_ip_address() -> str:
    """Return local network IP address for player connection URL."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe_socket:
            probe_socket.connect(("8.8.8.8", 80))
            return str(probe_socket.getsockname()[0])
    except OSError:
        return socket.gethostbyname(socket.gethostname())
    

def refresh_connected_players_from_socket_registry() -> None:
    """Restore connected=1 for players that currently have active socket sessions."""
    active_tokens = [
        device_token
        for device_token, sids in connected_sids_by_player_token.items()
        if sids
    ]

    for device_token in active_tokens:
        set_player_connected(device_token=device_token, connected=True)


def current_time_ms() -> int:
    """Return current Unix time in milliseconds."""
    return time.time_ns() // 1_000_000


def build_final_schedule_payload(state: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Build synchronized final reveal timing payload from persisted state."""
    state = state or get_game_state()
    sequence_id = state.get("final_reveal_sequence_id")
    drumroll_start_at_ms = state.get("final_drumroll_start_at_ms")
    reveal_at_ms = state.get("final_reveal_at_ms")

    if not sequence_id or drumroll_start_at_ms is None or reveal_at_ms is None:
        return None

    return {
        "sequence_id": str(sequence_id),
        "drumroll_start_at_ms": int(drumroll_start_at_ms),
        "reveal_at_ms": int(reveal_at_ms),
        "drumroll_duration_ms": FINAL_DRUMROLL_DURATION_MS,
        "server_time_ms": current_time_ms(),
    }


def probe_active_player_tokens() -> set[str]:
    """Confirm player presence through two invisible client acknowledgements."""
    probe_id = uuid.uuid4().hex
    presence_acknowledgements_by_probe[probe_id] = set()

    payload = {
        "probe_id": probe_id,
        "server_time_ms": current_time_ms(),
    }

    socketio.emit("presence_probe", payload)
    socketio.sleep(PRESENCE_PROBE_FIRST_WAIT_SECONDS)

    socketio.emit("presence_probe", payload)
    socketio.sleep(PRESENCE_PROBE_SECOND_WAIT_SECONDS)

    return presence_acknowledgements_by_probe.pop(probe_id, set())


def complete_scheduled_final_reveal(sequence_id: str, reveal_at_ms: int) -> None:
    """Finalize scores shortly before the shared visual reveal timestamp."""
    try:
        broadcast_at_ms = reveal_at_ms - FINAL_REVEAL_BROADCAST_LEAD_MS
        delay_seconds = max(0.0, (broadcast_at_ms - current_time_ms()) / 1000)
        socketio.sleep(delay_seconds)

        state = get_game_state()
        if (
            state.get("current_phase") != "final_drumroll"
            or state.get("final_reveal_sequence_id") != sequence_id
        ):
            return

        score_updates = reveal_final_round()
        players = list_players()
        counts = get_final_vote_counts()

        socketio.emit(
            "final_revealed",
            {
                "answer": str(state.get("actual_gender") or "boy"),
                "counts": counts,
                "score_updates": score_updates,
                "sequence_id": sequence_id,
                "reveal_at_ms": reveal_at_ms,
                "server_time_ms": current_time_ms(),
            },
        )

        delay_until_visual_reveal = max(0.0, (reveal_at_ms - current_time_ms()) / 1000)
        socketio.sleep(delay_until_visual_reveal)

        socketio.emit("rating_updated", {"players": players})

        for score_update in score_updates:
            socketio.emit(
                "score_updated",
                {
                    "player_id": score_update["player_id"],
                    "score": score_update["score"],
                    "points_delta": score_update["points_delta"],
                    "is_correct": True,
                    "effective_at_ms": reveal_at_ms,
                },
            )
    finally:
        active_final_reveal_sequences.discard(sequence_id)


def ensure_final_reveal_task(state: dict[str, Any] | None = None) -> None:
    """Start or restore the background task for a pending final reveal."""
    state = state or get_game_state()

    if state.get("current_phase") != "final_drumroll":
        return

    sequence_id = state.get("final_reveal_sequence_id")
    reveal_at_ms = state.get("final_reveal_at_ms")

    if not sequence_id or reveal_at_ms is None:
        return

    normalized_sequence_id = str(sequence_id)
    if normalized_sequence_id in active_final_reveal_sequences:
        return

    active_final_reveal_sequences.add(normalized_sequence_id)
    socketio.start_background_task(
        complete_scheduled_final_reveal,
        normalized_sequence_id,
        int(reveal_at_ms),
    )


def build_current_question_payload() -> dict[str, Any] | None:
    """Build current question payload for clients."""
    state = get_game_state()
    question_id = state.get("current_question_id")

    if not question_id:
        return None

    question = get_question_by_id(str(question_id))

    if question is None:
        return None

    return {
        "id": question["id"],
        "category": question["category"],
        "points": question["points"],
        "type": question["type"],
        "question": question["question"],
        "options": question["options"],
        "image_url": (
            url_for("question_image", filename=question["image"])
            if question.get("image")
            else None
        ),
        "is_auction": question["is_auction"],
    }


def build_auction_public_payload(question_id: str) -> dict[str, Any]:
    """Build public auction payload including the immutable participant snapshot."""
    progress = get_auction_progress(question_id)
    participants = list_auction_participants(question_id)

    return {
        "question_id": question_id,
        "participants_count": progress["participants_count"],
        "bids_count": progress["bids_count"],
        "participant_player_ids": [
            int(participant["id"])
            for participant in participants
        ],
    }


@app.get("/question-images/<path:filename>")
def question_image(filename: str) -> Any:
    """Serve JPG question images stored in the data directory."""
    image_path = Path(filename)

    if image_path.name != filename or image_path.suffix.lower() not in {".jpg", ".jpeg"}:
        abort(404)

    return send_from_directory(DATA_DIR, filename, max_age=3600)


@app.get("/game-audio/<path:filename>")
def game_audio(filename: str) -> Any:
    """Serve only the three configured MP3 files from the data directory."""
    if Path(filename).name != filename or filename not in ALLOWED_AUDIO_FILES:
        abort(404)

    return send_from_directory(DATA_DIR, filename, max_age=3600)


@app.get("/")
def player_page() -> str:
    """Render player screen."""
    return render_template("player.html")


@app.get("/admin-secret-2026")
def admin_page() -> str:
    """Render admin screen by secret URL."""
    return render_template("admin.html")


@app.get("/admin")
def blocked_admin_page() -> None:
    """Block obvious admin URL."""
    abort(404)


@app.get("/api/player")
def api_get_player() -> Any:
    """Return player by device token."""
    device_token = request.args.get("device_token", "").strip()

    if not device_token:
        return jsonify(
            {
                "ok": False,
                "error": "device_token_required",
                "message": "Не передан device_token.",
            }
        ), 400

    player = get_player_by_token(device_token)

    if player is None:
        return jsonify(
            {
                "ok": False,
                "error": "player_not_found",
                "message": "Игрок не найден.",
            }
        ), 404

    return jsonify(
        {
            "ok": True,
            "player": player,
        }
    )


@app.post("/api/player")
def api_create_player() -> Any:
    """Create player with nickname."""
    payload = request.get_json(silent=True) or {}

    device_token = str(payload.get("device_token", "")).strip()
    nickname = str(payload.get("nickname", "")).strip()

    if not device_token:
        return jsonify(
            {
                "ok": False,
                "error": "device_token_required",
                "message": "Не передан device_token.",
            }
        ), 400

    if not nickname:
        return jsonify(
            {
                "ok": False,
                "error": "nickname_required",
                "message": "Введите никнейм.",
            }
        ), 400

    if len(nickname) > 24:
        return jsonify(
            {
                "ok": False,
                "error": "nickname_too_long",
                "message": "Никнейм должен быть не длиннее 24 символов.",
            }
        ), 400

    try:
        player = create_player(device_token=device_token, nickname=nickname)
    except NicknameAlreadyExistsError:
        return jsonify(
            {
                "ok": False,
                "error": "nickname_exists",
                "message": "Такой никнейм уже занят. Выберите другой.",
            }
        ), 409

    return jsonify(
        {
            "ok": True,
            "player": player,
        }
    ), 201


@app.get("/api/players")
def api_list_players() -> Any:
    """Return players rating list."""
    return jsonify(
        {
            "ok": True,
            "players": list_players(),
        }
    )


@app.get("/api/admin/player-link")
def api_admin_player_link() -> Any:
    """Return actual player connection URL and QR code."""
    lan_ip = get_lan_ip_address()
    player_url = f"{request.scheme}://{lan_ip}:{Config.PORT}/"

    qr_image = qrcode.make(player_url)
    buffer = BytesIO()
    qr_image.save(buffer, format="PNG")

    qr_base64 = base64.b64encode(buffer.getvalue()).decode("ascii")
    qr_data_uri = f"data:image/png;base64,{qr_base64}"

    return jsonify(
        {
            "ok": True,
            "url": player_url,
            "qr_data_uri": qr_data_uri,
        }
    )


@app.get("/api/admin/board")
def api_admin_board() -> Any:
    """Return admin game board."""
    return jsonify(
        {
            "ok": True,
            "board": build_admin_board(),
            "all_questions_used": are_all_questions_used(),
        }
    )


@app.post("/api/admin/game/reset")
def api_reset_game() -> Any:
    """Reset game progress."""
    reset_game()


    connected_player_tokens_by_sid.clear()
    connected_sids_by_player_token.clear()
    presence_acknowledgements_by_probe.clear()
    auction_opening_question_ids.clear()
    active_final_reveal_sequences.clear()

    board = build_admin_board()
    players = list_players()

    socketio.emit(
        "game_reset",
        {
            "board": board,
            "players": players,
            "all_questions_used": False,
        },
    )

    socketio.emit(
        "board_updated",
        {
            "board": board,
            "all_questions_used": False,
        },
    )

    socketio.emit(
        "rating_updated",
        {
            "players": players,
        },
    )

    return jsonify(
        {
            "ok": True,
            "board": board,
            "players": players,
            "all_questions_used": False,
        }
    )


@app.post("/api/admin/questions/<question_id>/open")
def api_open_question(question_id: str) -> Any:
    """Open selected question for admin and players."""
    question = get_question_by_id(question_id)

    if question is None:
        return jsonify(
            {
                "ok": False,
                "error": "question_not_found",
                "message": "Вопрос не найден.",
            }
        ), 404

    if question["is_used"]:
        return jsonify(
            {
                "ok": False,
                "error": "question_already_used",
                "message": "Вопрос уже использован.",
            }
        ), 409

    state = get_game_state()
    if state["question_open"]:
        return jsonify(
            {
                "ok": False,
                "error": "question_already_open",
                "message": "Сначала закройте текущий вопрос.",
            }
        ), 409

    if question["is_auction"]:
        if question_id in auction_opening_question_ids:
            return jsonify(
                {
                    "ok": False,
                    "error": "auction_presence_check_in_progress",
                    "message": "Проверка подключения игроков уже выполняется.",
                }
            ), 409

        auction_opening_question_ids.add(question_id)

        try:
            confirmed_tokens = probe_active_player_tokens()
            synchronize_player_connections(confirmed_tokens)
            participants = create_auction_snapshot(question_id)
            players = list_players()

            socketio.emit("rating_updated", {"players": players})

            if not participants:
                return jsonify(
                    {
                        "ok": False,
                        "error": "no_auction_participants",
                        "message": (
                            "Аукцион нельзя начать: ни один подключённый игрок "
                            "с положительным рейтингом не подтвердил связь."
                        ),
                    }
                ), 409

            set_current_question(question_id, phase="auction_bidding")

            auction_payload = build_auction_public_payload(question_id)
            question_payload = build_current_question_payload()

            socketio.emit(
                "auction_started",
                {
                    "auction": auction_payload,
                    "participants": participants,
                },
            )

            return jsonify(
                {
                    "ok": True,
                    "question": question_payload,
                    "auction": auction_payload,
                    "participants": participants,
                }
            )
        finally:
            auction_opening_question_ids.discard(question_id)

    set_current_question(question_id)

    question_payload = build_current_question_payload()

    socketio.emit(
        "question_opened",
        {
            "question": question_payload,
        },
    )

    return jsonify(
        {
            "ok": True,
            "question": question_payload,
        }
    )


@app.post("/api/admin/questions/current/close")
def api_close_current_question() -> Any:
    """Close current question, calculate scores, and mark it as used."""
    state = get_game_state()
    question_id = state.get("current_question_id")

    if not question_id:
        return jsonify(
            {
                "ok": False,
                "error": "no_open_question",
                "message": "Сейчас нет открытого вопроса.",
            }
        ), 409

    try:
        if state["current_phase"] == "auction_question":
            score_updates = close_auction_question_and_calculate_score(str(question_id))
        elif state["current_phase"] == "auction_bidding":
            return jsonify(
                {
                    "ok": False,
                    "error": "auction_bidding_not_finished",
                    "message": "Сначала дождитесь завершения ставок.",
                }
            ), 409
        else:
            score_updates = close_question_and_calculate_scores(str(question_id))
    except QuestionNotFoundError:
        return jsonify(
            {
                "ok": False,
                "error": "question_not_found",
                "message": "Вопрос не найден.",
            }
        ), 404
    except QuestionAlreadyUsedError:
        return jsonify(
            {
                "ok": False,
                "error": "question_already_used",
                "message": "Вопрос уже использован.",
            }
        ), 409
    except ValueError as error:
        return jsonify(
            {
                "ok": False,
                "error": "invalid_question_close",
                "message": str(error),
            }
        ), 400

    board = build_admin_board()
    all_questions_used = are_all_questions_used()
    players = list_players()

    socketio.emit(
        "question_closed",
        {
            "question_id": question_id,
            "board": board,
            "all_questions_used": all_questions_used,
            "score_updates": score_updates,
        },
    )

    socketio.emit(
        "board_updated",
        {
            "board": board,
            "all_questions_used": all_questions_used,
        },
    )

    socketio.emit(
        "rating_updated",
        {
            "players": players,
        },
    )

    for score_update in score_updates:
        socketio.emit(
            "score_updated",
            {
                "player_id": score_update["player_id"],
                "score": score_update["score"],
                "points_delta": score_update["points_delta"],
                "is_correct": score_update["is_correct"],
            },
        )

    return jsonify(
        {
            "ok": True,
            "board": board,
            "all_questions_used": all_questions_used,
            "players": players,
            "score_updates": score_updates,
        }
    )


@app.post("/api/player/answer")
def api_save_player_answer() -> Any:
    """Save player's answer for current question."""
    payload = request.get_json(silent=True) or {}

    device_token = str(payload.get("device_token", "")).strip()
    question_id = str(payload.get("question_id", "")).strip()
    answer = str(payload.get("answer", "")).strip()

    if not device_token:
        return jsonify(
            {
                "ok": False,
                "error": "device_token_required",
                "message": "Не передан device_token.",
            }
        ), 400

    if not question_id:
        return jsonify(
            {
                "ok": False,
                "error": "question_id_required",
                "message": "Не передан question_id.",
            }
        ), 400

    if not answer:
        return jsonify(
            {
                "ok": False,
                "error": "answer_required",
                "message": "Введите или выберите ответ.",
            }
        ), 400

    player = get_player_by_token(device_token)
    if player is None:
        return jsonify(
            {
                "ok": False,
                "error": "player_not_found",
                "message": "Игрок не найден.",
            }
        ), 404

    state = get_game_state()

    if not state["question_open"] or state["current_question_id"] != question_id:
        return jsonify(
            {
                "ok": False,
                "error": "question_is_not_open",
                "message": "Вопрос уже закрыт или не открыт.",
            }
        ), 409
    
    if state["current_phase"] == "auction_bidding":
        return jsonify(
            {
                "ok": False,
                "error": "auction_bidding_not_finished",
                "message": "Сначала дождитесь завершения ставок.",
            }
        ), 409

    if state["current_phase"] == "auction_question":
        winner_player_id = state.get("auction_winner_player_id")

        if int(player["id"]) != int(winner_player_id):
            return jsonify(
                {
                    "ok": False,
                    "error": "not_auction_winner",
                    "message": "На этот вопрос отвечает только победитель аукциона.",
                }
            ), 403

    try:
        save_player_answer(
            player_id=int(player["id"]),
            question_id=question_id,
            answer=answer,
        )
    except ValueError as error:
        return jsonify(
            {
                "ok": False,
                "error": "invalid_answer",
                "message": str(error),
            }
        ), 400

    socketio.emit(
        "player_answer_saved",
        {
            "player_id": player["id"],
            "nickname": player["nickname"],
            "question_id": question_id,
        },
    )

    return jsonify(
        {
            "ok": True,
            "message": "Ответ сохранён.",
        }
    )


@app.post("/api/player/auction-bid")
def api_save_auction_bid() -> Any:
    """Save player's auction bid."""
    payload = request.get_json(silent=True) or {}

    device_token = str(payload.get("device_token", "")).strip()
    question_id = str(payload.get("question_id", "")).strip()

    try:
        bid = int(payload.get("bid", 0))
    except (TypeError, ValueError):
        return jsonify(
            {
                "ok": False,
                "error": "invalid_bid",
                "message": "Введите ставку числом.",
            }
        ), 400

    if not device_token:
        return jsonify(
            {
                "ok": False,
                "error": "device_token_required",
                "message": "Не передан device_token.",
            }
        ), 400

    if not question_id:
        return jsonify(
            {
                "ok": False,
                "error": "question_id_required",
                "message": "Не передан question_id.",
            }
        ), 400

    player = get_player_by_token(device_token)
    if player is None:
        return jsonify(
            {
                "ok": False,
                "error": "player_not_found",
                "message": "Игрок не найден.",
            }
        ), 404

    state = get_game_state()

    if state["current_phase"] != "auction_bidding" or state["current_question_id"] != question_id:
        return jsonify(
            {
                "ok": False,
                "error": "auction_is_not_open",
                "message": "Аукцион уже закрыт или не открыт.",
            }
        ), 409

    existing_bid = get_auction_bid_for_player(
        question_id=question_id,
        player_id=int(player["id"]),
    )

    if existing_bid is not None:
        return jsonify(
            {
                "ok": False,
                "error": "bid_already_submitted",
                "message": "Вы уже сделали ставку.",
            }
        ), 409

    try:
        save_auction_bid(
            question_id=question_id,
            player_id=int(player["id"]),
            bid=bid,
        )
    except ValueError as error:
        return jsonify(
            {
                "ok": False,
                "error": "invalid_bid",
                "message": str(error),
            }
        ), 400

    auction_payload = build_auction_public_payload(question_id)

    socketio.emit(
        "auction_progress_updated",
        {
            "auction": auction_payload,
        },
    )

    winner = None
    question_payload = None
    winner_payload = None

    if are_all_auction_bids_submitted(question_id):
        winner = get_auction_winner(question_id)

        if winner is not None:
            winner_player_id = int(winner["player_id"])

            set_auction_winner(
                question_id=question_id,
                winner_player_id=winner_player_id,
            )

            question_payload = build_current_question_payload()

            winner_payload = {
                "player_id": winner_player_id,
                "nickname": winner["nickname"],
                "bid": winner["bid"],
            }

            socketio.emit(
                "auction_winner_selected",
                {
                    "winner": winner_payload,
                },
            )

            socketio.emit(
                "auction_question_for_winner",
                {
                    "question": question_payload,
                    "bid": winner["bid"],
                },
                to=f"player_{winner_player_id}",
            )

    return jsonify(
        {
            "ok": True,
            "message": "Ставка сохранена.",
            "auction": auction_payload,
            "winner": winner_payload,
            "question": question_payload,
        }
    )


@app.post("/api/admin/final/start")
def api_start_final_round() -> Any:
    """Start final round."""
    if not are_all_questions_used():
        return jsonify(
            {
                "ok": False,
                "error": "questions_not_finished",
                "message": "Финальный раунд доступен только после закрытия всех вопросов.",
            }
        ), 409

    state = get_game_state()

    if state["current_phase"] not in {"waiting", "final_revealed"}:
        return jsonify(
            {
                "ok": False,
                "error": "invalid_phase",
                "message": "Сейчас нельзя начать финальный раунд.",
            }
        ), 409

    start_final_round()

    counts = get_final_vote_counts()

    socketio.emit(
        "final_started",
        {
            "counts": counts,
        },
    )

    return jsonify(
        {
            "ok": True,
            "counts": counts,
        }
    )


@app.post("/api/player/final-vote")
def api_save_final_vote() -> Any:
    """Save player's final vote."""
    payload = request.get_json(silent=True) or {}

    device_token = str(payload.get("device_token", "")).strip()
    choice = str(payload.get("choice", "")).strip()

    if not device_token:
        return jsonify(
            {
                "ok": False,
                "error": "device_token_required",
                "message": "Не передан device_token.",
            }
        ), 400

    player = get_player_by_token(device_token)

    if player is None:
        return jsonify(
            {
                "ok": False,
                "error": "player_not_found",
                "message": "Игрок не найден.",
            }
        ), 404

    try:
        save_final_vote(
            player_id=int(player["id"]),
            choice=choice,
        )
    except ValueError as error:
        return jsonify(
            {
                "ok": False,
                "error": "invalid_final_vote",
                "message": str(error),
            }
        ), 400

    counts = get_final_vote_counts()

    socketio.emit(
        "final_vote_updated",
        {
            "counts": counts,
        },
    )

    return jsonify(
        {
            "ok": True,
            "choice": choice,
            "counts": counts,
        }
    )


@app.post("/api/admin/final/reveal")
def api_reveal_final_round() -> Any:
    """Schedule one synchronized seven-second final reveal sequence."""
    state = get_game_state()

    if state["current_phase"] == "final_drumroll":
        schedule_payload = build_final_schedule_payload(state)
        ensure_final_reveal_task(state)

        return jsonify(
            {
                "ok": True,
                "already_scheduled": True,
                "schedule": schedule_payload,
            }
        )

    if state["current_phase"] != "final_open":
        return jsonify(
            {
                "ok": False,
                "error": "invalid_final_reveal",
                "message": "Финальный раунд сейчас нельзя раскрыть.",
            }
        ), 409

    sequence_id = uuid.uuid4().hex
    drumroll_start_at_ms = current_time_ms() + FINAL_SEQUENCE_START_DELAY_MS
    reveal_at_ms = drumroll_start_at_ms + FINAL_DRUMROLL_DURATION_MS

    try:
        schedule_final_reveal(
            drumroll_start_at_ms=drumroll_start_at_ms,
            reveal_at_ms=reveal_at_ms,
            sequence_id=sequence_id,
        )
    except ValueError as error:
        return jsonify(
            {
                "ok": False,
                "error": "invalid_final_reveal",
                "message": str(error),
            }
        ), 409

    state = get_game_state()
    schedule_payload = build_final_schedule_payload(state)

    socketio.emit(
        "final_reveal_scheduled",
        {
            "schedule": schedule_payload,
        },
    )

    ensure_final_reveal_task(state)

    return jsonify(
        {
            "ok": True,
            "already_scheduled": False,
            "schedule": schedule_payload,
        }
    )


@socketio.on("connect")
def handle_connect() -> None:
    """Handle socket connection."""
    emit("server_message", {"message": "Подключение к серверу установлено"})


@socketio.on("time_sync_request")
def handle_time_sync_request(data: dict[str, Any] | None = None) -> None:
    """Return server time while echoing the client's send timestamp."""
    payload = data or {}
    emit(
        "time_sync_response",
        {
            "client_sent_at_ms": payload.get("client_sent_at_ms"),
            "server_time_ms": current_time_ms(),
        },
    )


@socketio.on("presence_ack")
def handle_presence_ack(data: dict[str, Any] | None = None) -> None:
    """Record an invisible presence acknowledgement for an active auction probe."""
    payload = data or {}
    probe_id = str(payload.get("probe_id", "")).strip()
    device_token = str(payload.get("device_token", "")).strip()

    if not probe_id or not device_token:
        return

    acknowledgements = presence_acknowledgements_by_probe.get(probe_id)
    if acknowledgements is None:
        return

    player = get_player_by_token(device_token)
    if player is None:
        return

    acknowledgements.add(device_token)
    set_player_connected(device_token=device_token, connected=True)


@socketio.on("player_identify")
def handle_player_identify(data: dict[str, str]) -> None:
    """Identify connected player by device token."""
    device_token = data.get("device_token", "").strip()

    if not device_token:
        emit(
            "player_identified",
            {
                "ok": False,
                "error": "device_token_required",
            },
        )
        return

    player = get_player_by_token(device_token)

    if player is None:
        emit(
            "player_identified",
            {
                "ok": False,
                "error": "player_not_found",
            },
        )
        return

    set_player_connected(device_token=device_token, connected=True)
    connected_player_tokens_by_sid[request.sid] = device_token

    if device_token not in connected_sids_by_player_token:
        connected_sids_by_player_token[device_token] = set()

    connected_sids_by_player_token[device_token].add(request.sid)

    join_room(f"player_{player['id']}")

    emit(
        "player_identified",
        {
            "ok": True,
            "player": player,
        },
    )

    socketio.emit(
        "rating_updated",
        {
            "players": list_players(),
        },
    )


@socketio.on("player_ping")
def handle_player_ping(data: dict[str, str]) -> None:
    """Handle test event from player screen."""
    emit("server_message", {"message": "Игрок подключён к real-time серверу"})


@socketio.on("admin_ping")
def handle_admin_ping(data: dict[str, str]) -> None:
    """Handle test event from admin screen."""
    emit("server_message", {"message": "Администратор подключён к real-time серверу"})


@socketio.on("admin_request_rating")
def handle_admin_request_rating() -> None:
    """Send current rating to admin."""
    emit(
        "rating_updated",
        {
            "players": list_players(),
        },
    )


@socketio.on("admin_request_board")
def handle_admin_request_board() -> None:
    """Send current board to admin."""
    emit(
        "board_updated",
        {
            "board": build_admin_board(),
            "all_questions_used": are_all_questions_used(),
        },
    )


@app.get("/api/game-state")
def api_game_state() -> Any:
    """Return current game state and synchronized timing for reconnects."""
    device_token = request.args.get("device_token", "").strip()

    state = get_game_state()
    ensure_final_reveal_task(state)

    question_payload = build_current_question_payload()
    final_schedule = build_final_schedule_payload(state)

    player = get_player_by_token(device_token) if device_token else None
    player_answer = None
    auction_bid = None
    auction = None
    auction_winner = None
    final_vote = None
    final_counts = None
    final_result = None
    baby_names = None

    if question_payload is not None:
        if question_payload["is_auction"]:
            auction = build_auction_public_payload(question_payload["id"])

        if player is not None:
            player_answer = get_answer_for_player(
                player_id=int(player["id"]),
                question_id=question_payload["id"],
            )

            if question_payload["is_auction"]:
                auction_bid = get_auction_bid_for_player(
                    question_id=question_payload["id"],
                    player_id=int(player["id"]),
                )

        if state["current_phase"] == "auction_question":
            winner = get_auction_winner(question_payload["id"])

            if winner is not None:
                auction_winner = {
                    "player_id": int(winner["player_id"]),
                    "nickname": winner["nickname"],
                    "bid": winner["bid"],
                }

    if state["current_phase"] in {
        "final_open",
        "final_drumroll",
        "final_revealing",
        "final_revealed",
    }:
        final_counts = get_final_vote_counts()

        if player is not None:
            final_vote = get_final_vote_for_player(int(player["id"]))

            if state["current_phase"] == "final_revealed":
                final_result = {
                    "is_correct": bool(
                        final_vote
                        and final_vote.get("choice") == state.get("actual_gender")
                    ),
                    "score": int(player["score"]),
                }

    if state["current_phase"] == "secret_names":
        baby_names = list_baby_names()

    return jsonify(
        {
            "ok": True,
            "server_time_ms": current_time_ms(),
            "state": {
                "current_phase": state["current_phase"],
                "question_open": bool(state["question_open"]),
                "auction_winner_player_id": state.get("auction_winner_player_id"),
                "final_locked": bool(state.get("final_locked")),
                "actual_gender": state.get("actual_gender"),
                "secret_round_open": bool(state.get("secret_round_open")),
            },
            "question": question_payload,
            "player_answer": player_answer,
            "auction_bid": auction_bid,
            "auction": auction,
            "auction_winner": auction_winner,
            "final_vote": final_vote,
            "final_counts": final_counts,
            "final_schedule": final_schedule,
            "final_result": final_result,
            "baby_names": baby_names,
        }
    )


@app.post("/api/admin/secret/start")
def api_start_secret_round() -> Any:
    """Start secret baby name round."""
    try:
        start_secret_round()
    except ValueError as error:
        return jsonify(
            {
                "ok": False,
                "error": "invalid_secret_start",
                "message": str(error),
            }
        ), 409

    names = list_baby_names()

    socketio.emit(
        "secret_started",
        {
            "names": names,
        },
    )

    return jsonify(
        {
            "ok": True,
            "names": names,
        }
    )


@app.post("/api/player/baby-name")
def api_submit_baby_name() -> Any:
    """Submit baby name from player."""
    payload = request.get_json(silent=True) or {}

    device_token = str(payload.get("device_token", "")).strip()
    name = str(payload.get("name", "")).strip()

    if not device_token:
        return jsonify(
            {
                "ok": False,
                "error": "device_token_required",
                "message": "Не передан device_token.",
            }
        ), 400

    player = get_player_by_token(device_token)

    if player is None:
        return jsonify(
            {
                "ok": False,
                "error": "player_not_found",
                "message": "Игрок не найден.",
            }
        ), 404

    try:
        saved_name = submit_baby_name(
            player_id=int(player["id"]),
            name=name,
        )
    except ValueError as error:
        return jsonify(
            {
                "ok": False,
                "error": "invalid_baby_name",
                "message": str(error),
            }
        ), 400

    names = list_baby_names()

    socketio.emit(
        "baby_names_updated",
        {
            "names": names,
        },
    )

    return jsonify(
        {
            "ok": True,
            "name": saved_name,
            "names": names,
        }
    )


@app.post("/api/player/baby-name-vote")
def api_vote_for_baby_name() -> Any:
    """Vote for baby name."""
    payload = request.get_json(silent=True) or {}

    device_token = str(payload.get("device_token", "")).strip()

    try:
        name_id = int(payload.get("name_id", 0))
        amount = int(payload.get("amount", 0))
    except (TypeError, ValueError):
        return jsonify(
            {
                "ok": False,
                "error": "invalid_vote",
                "message": "Введите ставку числом.",
            }
        ), 400

    if not device_token:
        return jsonify(
            {
                "ok": False,
                "error": "device_token_required",
                "message": "Не передан device_token.",
            }
        ), 400

    player = get_player_by_token(device_token)

    if player is None:
        return jsonify(
            {
                "ok": False,
                "error": "player_not_found",
                "message": "Игрок не найден.",
            }
        ), 404

    try:
        score_update = vote_for_baby_name(
            player_id=int(player["id"]),
            name_id=name_id,
            amount=amount,
        )
    except ValueError as error:
        return jsonify(
            {
                "ok": False,
                "error": "invalid_name_vote",
                "message": str(error),
            }
        ), 400

    names = list_baby_names()
    players = list_players()

    socketio.emit(
        "baby_names_updated",
        {
            "names": names,
        },
    )

    socketio.emit(
        "rating_updated",
        {
            "players": players,
        },
    )

    socketio.emit(
        "score_updated",
        {
            "player_id": score_update["player_id"],
            "score": score_update["score"],
            "points_delta": score_update["points_delta"],
            "is_correct": True,
        },
    )

    return jsonify(
        {
            "ok": True,
            "score_update": score_update,
            "names": names,
            "players": players,
        }
    )


@app.get("/api/baby-names")
def api_list_baby_names() -> Any:
    """Return baby names."""
    return jsonify(
        {
            "ok": True,
            "names": list_baby_names(),
            "winner": get_baby_name_winner(),
        }
    )


@socketio.on("disconnect")
def handle_disconnect() -> None:
    """Mark player as disconnected when all socket connections are lost."""
    device_token = connected_player_tokens_by_sid.pop(request.sid, None)

    if not device_token:
        return

    player_sids = connected_sids_by_player_token.get(device_token)

    if player_sids is not None:
        player_sids.discard(request.sid)

        if not player_sids:
            connected_sids_by_player_token.pop(device_token, None)
            set_player_connected(device_token=device_token, connected=False)

    socketio.emit(
        "rating_updated",
        {
            "players": list_players(),
        },
    )


if __name__ == "__main__":
    init_database()
    seed_questions()

    socketio.run(
        app,
        host=Config.HOST,
        port=Config.PORT,
        debug=Config.DEBUG,
    )