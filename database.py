from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "instance" / "game.sqlite"
QUESTIONS_PATH = BASE_DIR / "data" / "questions.json"


class NicknameAlreadyExistsError(ValueError):
    """Raised when a nickname is already used by another player."""


class PlayerNotFoundError(LookupError):
    """Raised when player was not found by device token."""


class QuestionNotFoundError(LookupError):
    """Raised when question was not found."""


class QuestionAlreadyUsedError(ValueError):
    """Raised when question is already used."""


class NoOpenQuestionError(ValueError):
    """Raised when there is no open question to close."""


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """Provide a SQLite connection and always close it after use."""
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DATABASE_PATH, timeout=10)
    connection.row_factory = sqlite3.Row

    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")
        connection.execute("PRAGMA busy_timeout = 5000")
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def ensure_column(
    *,
    connection: sqlite3.Connection,
    table_name: str,
    column_name: str,
    column_definition: str,
) -> None:
    """Add a column to SQLite table if it does not exist."""
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    existing_columns = {row["name"] for row in rows}

    if column_name in existing_columns:
        return

    connection.execute(
        f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
    )


def init_database() -> None:
    """Create required database tables."""
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_token TEXT UNIQUE NOT NULL,
                nickname TEXT UNIQUE NOT NULL,
                score INTEGER NOT NULL DEFAULT 0,
                connected INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS questions (
                id TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                points INTEGER NOT NULL,
                type TEXT NOT NULL,
                question TEXT NOT NULL,
                options_json TEXT NOT NULL,
                correct_answers_json TEXT NOT NULL,
                image_filename TEXT,
                is_auction INTEGER NOT NULL DEFAULT 0,
                is_used INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS game_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                current_phase TEXT NOT NULL DEFAULT 'waiting',
                current_question_id TEXT,
                question_open INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS answers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER NOT NULL,
                question_id TEXT NOT NULL,
                answer TEXT NOT NULL,
                is_correct INTEGER,
                points_delta INTEGER NOT NULL DEFAULT 0,
                locked INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(player_id, question_id)
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS auction_participants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id TEXT NOT NULL,
                player_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(question_id, player_id)
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS auction_bids (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id TEXT NOT NULL,
                player_id INTEGER NOT NULL,
                bid INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(question_id, player_id)
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS final_votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER UNIQUE NOT NULL,
                choice TEXT NOT NULL,
                locked INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS baby_names (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                display_name TEXT NOT NULL,
                normalized_name TEXT UNIQUE NOT NULL,
                rating INTEGER NOT NULL DEFAULT 0,
                created_by_player_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS name_votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER NOT NULL,
                name_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_answers_question_id
            ON answers(question_id)
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_final_votes_choice
            ON final_votes(choice)
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_baby_names_created_by_player_id
            ON baby_names(created_by_player_id)
            """
        )

        ensure_column(
            connection=connection,
            table_name="answers",
            column_name="is_correct",
            column_definition="INTEGER",
        )

        ensure_column(
            connection=connection,
            table_name="answers",
            column_name="points_delta",
            column_definition="INTEGER NOT NULL DEFAULT 0",
        )

        ensure_column(
            connection=connection,
            table_name="game_state",
            column_name="auction_winner_player_id",
            column_definition="INTEGER",
        )

        ensure_column(
            connection=connection,
            table_name="game_state",
            column_name="final_locked",
            column_definition="INTEGER NOT NULL DEFAULT 0",
        )

        ensure_column(
            connection=connection,
            table_name="game_state",
            column_name="actual_gender",
            column_definition="TEXT NOT NULL DEFAULT 'boy'",
        )

        ensure_column(
            connection=connection,
            table_name="game_state",
            column_name="secret_round_open",
            column_definition="INTEGER NOT NULL DEFAULT 0",
        )

        ensure_column(
            connection=connection,
            table_name="game_state",
            column_name="final_drumroll_start_at_ms",
            column_definition="INTEGER",
        )

        ensure_column(
            connection=connection,
            table_name="game_state",
            column_name="final_reveal_at_ms",
            column_definition="INTEGER",
        )

        ensure_column(
            connection=connection,
            table_name="game_state",
            column_name="final_reveal_sequence_id",
            column_definition="TEXT",
        )

        ensure_column(
            connection=connection,
            table_name="game_state",
            column_name="answer_reveal_sequence_id",
            column_definition="TEXT",
        )

        ensure_column(
            connection=connection,
            table_name="game_state",
            column_name="answer_reveal_started_at_ms",
            column_definition="INTEGER",
        )

        ensure_column(
            connection=connection,
            table_name="game_state",
            column_name="answer_reveal_ends_at_ms",
            column_definition="INTEGER",
        )

        ensure_column(
            connection=connection,
            table_name="questions",
            column_name="image_filename",
            column_definition="TEXT",
        )

        connection.execute(
            """
            INSERT OR IGNORE INTO game_state (
                id,
                current_phase,
                current_question_id,
                question_open
            )
            VALUES (1, 'waiting', NULL, 0)
            """
        )


def normalize_nickname(nickname: str) -> str:
    """Normalize nickname for validation and duplicate checks."""
    return nickname.strip()


def get_player_by_token(device_token: str) -> dict[str, Any] | None:
    """Return player by device token or None."""
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, device_token, nickname, score, connected
            FROM players
            WHERE device_token = ?
            """,
            (device_token,),
        ).fetchone()

    if row is None:
        return None

    return dict(row)


def get_player_by_nickname(nickname: str) -> dict[str, Any] | None:
    """Return player by nickname or None."""
    normalized_nickname = normalize_nickname(nickname)

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, device_token, nickname, score, connected
            FROM players
            WHERE lower(nickname) = lower(?)
            """,
            (normalized_nickname,),
        ).fetchone()

    if row is None:
        return None

    return dict(row)


def create_player(device_token: str, nickname: str) -> dict[str, Any]:
    """Create player and return created player."""
    normalized_nickname = normalize_nickname(nickname)

    if not device_token.strip():
        raise ValueError("Device token is required.")

    if not normalized_nickname:
        raise ValueError("Nickname is required.")

    existing_player = get_player_by_nickname(normalized_nickname)
    if existing_player is not None:
        raise NicknameAlreadyExistsError("Nickname already exists.")

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO players (device_token, nickname, score, connected)
            VALUES (?, ?, 0, 1)
            """,
            (device_token, normalized_nickname),
        )

    player = get_player_by_token(device_token)
    if player is None:
        raise PlayerNotFoundError("Created player was not found.")

    return player


def set_player_connected(device_token: str, connected: bool) -> None:
    """Update player connection flag by device token."""
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE players
            SET connected = ?, updated_at = CURRENT_TIMESTAMP
            WHERE device_token = ?
            """,
            (1 if connected else 0, device_token),
        )


def synchronize_player_connections(active_device_tokens: set[str]) -> None:
    """Replace stored connection flags with a freshly confirmed presence snapshot."""
    normalized_tokens = sorted(
        {
            token.strip()
            for token in active_device_tokens
            if isinstance(token, str) and token.strip()
        }
    )

    with get_connection() as connection:
        connection.execute(
            """
            UPDATE players
            SET connected = 0, updated_at = CURRENT_TIMESTAMP
            WHERE connected != 0
            """
        )

        if not normalized_tokens:
            return

        placeholders = ", ".join("?" for _ in normalized_tokens)
        connection.execute(
            f"""
            UPDATE players
            SET connected = 1, updated_at = CURRENT_TIMESTAMP
            WHERE device_token IN ({placeholders})
            """,
            normalized_tokens,
        )


def list_players() -> list[dict[str, Any]]:
    """Return all players ordered by score descending."""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, nickname, score, connected
            FROM players
            ORDER BY score DESC, id ASC
            """
        ).fetchall()

    return [dict(row) for row in rows]


def load_questions_from_json() -> list[dict[str, Any]]:
    """Load questions from JSON file."""
    if not QUESTIONS_PATH.exists():
        raise FileNotFoundError(f"Questions file was not found: {QUESTIONS_PATH}")

    with QUESTIONS_PATH.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise ValueError("Questions JSON must contain a list.")

    return data


def seed_questions() -> None:
    """Synchronize question definitions from JSON while preserving game progress."""
    questions = load_questions_from_json()

    with get_connection() as connection:
        for question in questions:
            connection.execute(
                """
                INSERT INTO questions (
                    id,
                    category,
                    points,
                    type,
                    question,
                    options_json,
                    correct_answers_json,
                    image_filename,
                    is_auction,
                    is_used
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                ON CONFLICT(id)
                DO UPDATE SET
                    category = excluded.category,
                    points = excluded.points,
                    type = excluded.type,
                    question = excluded.question,
                    options_json = excluded.options_json,
                    correct_answers_json = excluded.correct_answers_json,
                    image_filename = excluded.image_filename,
                    is_auction = excluded.is_auction,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    question["id"],
                    question["category"],
                    int(question["points"]),
                    question["type"],
                    question["question"],
                    json.dumps(question.get("options", []), ensure_ascii=False),
                    json.dumps(question.get("correct_answers", []), ensure_ascii=False),
                    question.get("image"),
                    1 if question.get("is_auction", False) else 0,
                ),
            )


def parse_question_row(row: sqlite3.Row) -> dict[str, Any]:
    """Convert SQLite question row to dict."""
    return {
        "id": row["id"],
        "category": row["category"],
        "points": row["points"],
        "type": row["type"],
        "question": row["question"],
        "options": json.loads(row["options_json"]),
        "correct_answers": json.loads(row["correct_answers_json"]),
        "image": row["image_filename"],
        "is_auction": bool(row["is_auction"]),
        "is_used": bool(row["is_used"]),
    }


def list_questions() -> list[dict[str, Any]]:
    """Return all questions ordered by category and points."""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                category,
                points,
                type,
                question,
                options_json,
                correct_answers_json,
                image_filename,
                is_auction,
                is_used
            FROM questions
            ORDER BY
                CASE category
                    WHEN 'Беременность' THEN 1
                    WHEN 'Родители' THEN 2
                    WHEN 'Роды' THEN 3
                    WHEN 'Что это?' THEN 4
                    ELSE 99
                END,
                points ASC
            """
        ).fetchall()

    return [parse_question_row(row) for row in rows]


def get_question_by_id(question_id: str) -> dict[str, Any] | None:
    """Return question by id or None."""
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                id,
                category,
                points,
                type,
                question,
                options_json,
                correct_answers_json,
                image_filename,
                is_auction,
                is_used
            FROM questions
            WHERE id = ?
            """,
            (question_id,),
        ).fetchone()

    if row is None:
        return None

    return parse_question_row(row)


def mark_question_used(question_id: str) -> None:
    """Mark question as used."""
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE questions
            SET is_used = 1, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (question_id,),
        )


def are_all_questions_used() -> bool:
    """Return True if all questions are used."""
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS remaining_count
            FROM questions
            WHERE is_used = 0
            """
        ).fetchone()

    return int(row["remaining_count"]) == 0


def build_admin_board() -> list[dict[str, Any]]:
    """Build admin board grouped by category."""
    questions = list_questions()
    categories_order = ["Беременность", "Родители", "Роды", "Что это?"]

    board: list[dict[str, Any]] = []

    for category in categories_order:
        category_questions = [
            question for question in questions if question["category"] == category
        ]

        questions_by_points = {
            question["points"]: question for question in category_questions
        }

        board.append(
            {
                "category": category,
                "questions": [
                    questions_by_points.get(points)
                    for points in [100, 200, 300, 400, 500]
                ],
            }
        )

    return board


def get_game_state() -> dict[str, Any]:
    """Return current game state."""
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                id,
                current_phase,
                current_question_id,
                question_open,
                auction_winner_player_id,
                final_locked,
                actual_gender,
                secret_round_open,
                final_drumroll_start_at_ms,
                final_reveal_at_ms,
                final_reveal_sequence_id,
                answer_reveal_sequence_id,
                answer_reveal_started_at_ms,
                answer_reveal_ends_at_ms
            FROM game_state
            WHERE id = 1
            """
        ).fetchone()

    if row is None:
        raise LookupError("Game state was not initialized.")

    return dict(row)


def set_current_question(
    question_id: str,
    *,
    phase: str = "question_open",
    auction_winner_player_id: int | None = None,
) -> None:
    """Set current open question with selected phase."""
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE game_state
            SET
                current_phase = ?,
                current_question_id = ?,
                question_open = 1,
                auction_winner_player_id = ?,
                answer_reveal_sequence_id = NULL,
                answer_reveal_started_at_ms = NULL,
                answer_reveal_ends_at_ms = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
            """,
            (phase, question_id, auction_winner_player_id),
        )


def clear_current_question() -> None:
    """Clear current question and return game to waiting phase."""
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE game_state
            SET
                current_phase = 'waiting',
                current_question_id = NULL,
                question_open = 0,
                auction_winner_player_id = NULL,
                answer_reveal_sequence_id = NULL,
                answer_reveal_started_at_ms = NULL,
                answer_reveal_ends_at_ms = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
            """
        )


def start_answer_reveal(
    *,
    question_id: str,
    sequence_id: str,
    started_at_ms: int,
    ends_at_ms: int,
) -> None:
    """Persist the temporary correct-answer reveal phase."""
    if not question_id.strip():
        raise ValueError("Question id is required for answer reveal.")

    if not sequence_id.strip():
        raise ValueError("Sequence id is required for answer reveal.")

    if started_at_ms <= 0 or ends_at_ms <= started_at_ms:
        raise ValueError("Answer reveal timing is invalid.")

    with get_connection() as connection:
        connection.execute(
            """
            UPDATE game_state
            SET
                current_phase = 'answer_reveal',
                current_question_id = ?,
                question_open = 0,
                auction_winner_player_id = NULL,
                answer_reveal_sequence_id = ?,
                answer_reveal_started_at_ms = ?,
                answer_reveal_ends_at_ms = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
            """,
            (question_id, sequence_id, started_at_ms, ends_at_ms),
        )


def finish_answer_reveal(sequence_id: str) -> bool:
    """Finish one answer reveal sequence and return whether it was active."""
    with get_connection() as connection:
        result = connection.execute(
            """
            UPDATE game_state
            SET
                current_phase = 'waiting',
                current_question_id = NULL,
                question_open = 0,
                auction_winner_player_id = NULL,
                answer_reveal_sequence_id = NULL,
                answer_reveal_started_at_ms = NULL,
                answer_reveal_ends_at_ms = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
              AND current_phase = 'answer_reveal'
              AND answer_reveal_sequence_id = ?
            """,
            (sequence_id,),
        )

    return result.rowcount == 1


def save_player_answer(
    *,
    player_id: int,
    question_id: str,
    answer: str,
) -> None:
    """Save or update player's answer for an open question."""
    normalized_answer = answer.strip()

    if not normalized_answer:
        raise ValueError("Answer is required.")

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO answers (
                player_id,
                question_id,
                answer,
                locked
            )
            VALUES (?, ?, ?, 0)
            ON CONFLICT(player_id, question_id)
            DO UPDATE SET
                answer = excluded.answer,
                updated_at = CURRENT_TIMESTAMP
            WHERE locked = 0
            """,
            (player_id, question_id, normalized_answer),
        )


def lock_answers_for_question(question_id: str) -> None:
    """Lock all answers for selected question."""
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE answers
            SET locked = 1, updated_at = CURRENT_TIMESTAMP
            WHERE question_id = ?
            """,
            (question_id,),
        )


def get_answer_for_player(
    *,
    player_id: int,
    question_id: str,
) -> dict[str, Any] | None:
    """Return player's answer for selected question."""
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                id,
                player_id,
                question_id,
                answer,
                is_correct,
                points_delta,
                locked
            FROM answers
            WHERE player_id = ? AND question_id = ?
            """,
            (player_id, question_id),
        ).fetchone()

    if row is None:
        return None

    return dict(row)


def normalize_answer(answer: str) -> str:
    """Normalize answer for comparison across common spelling and punctuation variants."""
    normalized = answer.casefold().replace("ё", "е").replace("_", " ")
    normalized = re.sub(r"[^\w]+", " ", normalized, flags=re.UNICODE)
    return " ".join(normalized.split())


def is_answer_correct(
    *,
    player_answer: str,
    correct_answers: list[str],
) -> bool:
    """Check player answer against allowed correct answers."""
    normalized_player_answer = normalize_answer(player_answer)

    normalized_correct_answers = {
        normalize_answer(correct_answer)
        for correct_answer in correct_answers
    }

    return normalized_player_answer in normalized_correct_answers


def list_unlocked_answers_for_question(question_id: str) -> list[dict[str, Any]]:
    """Return all answers for selected question."""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, player_id, question_id, answer, locked
            FROM answers
            WHERE question_id = ?
            """,
            (question_id,),
        ).fetchall()

    return [dict(row) for row in rows]


def update_player_score(
    *,
    player_id: int,
    points_delta: int,
) -> int:
    """Update player score and return new score."""
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE players
            SET score = score + ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (points_delta, player_id),
        )

        row = connection.execute(
            """
            SELECT score
            FROM players
            WHERE id = ?
            """,
            (player_id,),
        ).fetchone()

    if row is None:
        raise PlayerNotFoundError("Player was not found.")

    return int(row["score"])


def set_answer_result(
    *,
    answer_id: int,
    is_correct: bool,
    points_delta: int,
) -> None:
    """Save answer checking result."""
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE answers
            SET
                is_correct = ?,
                points_delta = ?,
                locked = 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (1 if is_correct else 0, points_delta, answer_id),
        )


def close_question_and_calculate_scores(question_id: str) -> list[dict[str, Any]]:
    """Close question, check answers, update scores, and return score updates."""
    question = get_question_by_id(question_id)

    if question is None:
        raise QuestionNotFoundError("Question was not found.")

    if question["is_used"]:
        raise QuestionAlreadyUsedError("Question is already used.")

    normalized_correct_answers = {
        normalize_answer(correct_answer)
        for correct_answer in question["correct_answers"]
    }

    score_updates: list[dict[str, Any]] = []

    with get_connection() as connection:
        answers = connection.execute(
            """
            SELECT id, player_id, question_id, answer, locked
            FROM answers
            WHERE question_id = ?
            """,
            (question_id,),
        ).fetchall()

        for answer in answers:
            correct = normalize_answer(answer["answer"]) in normalized_correct_answers
            points_delta = (
                int(question["points"])
                if correct
                else -int(question["points"])
            )

            connection.execute(
                """
                UPDATE players
                SET score = score + ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (points_delta, int(answer["player_id"])),
            )

            player_row = connection.execute(
                """
                SELECT score
                FROM players
                WHERE id = ?
                """,
                (int(answer["player_id"]),),
            ).fetchone()

            if player_row is None:
                raise PlayerNotFoundError("Player was not found.")

            connection.execute(
                """
                UPDATE answers
                SET
                    is_correct = ?,
                    points_delta = ?,
                    locked = 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (1 if correct else 0, points_delta, int(answer["id"])),
            )

            score_updates.append(
                {
                    "player_id": int(answer["player_id"]),
                    "score": int(player_row["score"]),
                    "points_delta": points_delta,
                    "is_correct": correct,
                }
            )

        connection.execute(
            """
            UPDATE answers
            SET locked = 1, updated_at = CURRENT_TIMESTAMP
            WHERE question_id = ?
            """,
            (question_id,),
        )

        connection.execute(
            """
            UPDATE questions
            SET is_used = 1, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (question_id,),
        )

        connection.execute(
            """
            UPDATE game_state
            SET
                current_phase = 'waiting',
                current_question_id = NULL,
                question_open = 0,
                auction_winner_player_id = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
            """
        )

    return score_updates


def list_active_players() -> list[dict[str, Any]]:
    """Return connected players who can participate in auction."""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, nickname, score, connected
            FROM players
            WHERE connected = 1
              AND score > 0
            ORDER BY id ASC
            """
        ).fetchall()

    return [dict(row) for row in rows]


def create_auction_snapshot(question_id: str) -> list[dict[str, Any]]:
    """Create auction participants snapshot from currently active players."""
    active_players = list_active_players()

    with get_connection() as connection:
        connection.execute(
            "DELETE FROM auction_participants WHERE question_id = ?",
            (question_id,),
        )
        connection.execute(
            "DELETE FROM auction_bids WHERE question_id = ?",
            (question_id,),
        )

        connection.executemany(
            """
            INSERT OR IGNORE INTO auction_participants (
                question_id,
                player_id
            )
            VALUES (?, ?)
            """,
            [
                (question_id, int(player["id"]))
                for player in active_players
            ],
        )

    return active_players


def list_auction_participants(question_id: str) -> list[dict[str, Any]]:
    """Return auction participants for selected question."""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                players.id,
                players.nickname,
                players.score
            FROM auction_participants
            JOIN players ON players.id = auction_participants.player_id
            WHERE auction_participants.question_id = ?
            ORDER BY auction_participants.id ASC
            """,
            (question_id,),
        ).fetchall()

    return [dict(row) for row in rows]


def list_auction_bids(question_id: str) -> list[dict[str, Any]]:
    """Return auction bids ordered by bid desc and time asc."""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                auction_bids.id,
                auction_bids.question_id,
                auction_bids.player_id,
                auction_bids.bid,
                auction_bids.created_at,
                players.nickname,
                players.score
            FROM auction_bids
            JOIN players ON players.id = auction_bids.player_id
            WHERE auction_bids.question_id = ?
            ORDER BY auction_bids.bid DESC, auction_bids.created_at ASC, auction_bids.id ASC
            """,
            (question_id,),
        ).fetchall()

    return [dict(row) for row in rows]


def get_auction_bid_for_player(
    *,
    question_id: str,
    player_id: int,
) -> dict[str, Any] | None:
    """Return auction bid for player or None."""
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, question_id, player_id, bid, created_at
            FROM auction_bids
            WHERE question_id = ? AND player_id = ?
            """,
            (question_id, player_id),
        ).fetchone()

    if row is None:
        return None

    return dict(row)


def is_auction_participant(
    *,
    question_id: str,
    player_id: int,
) -> bool:
    """Return True if player participates in auction."""
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT 1
            FROM auction_participants
            WHERE question_id = ? AND player_id = ?
            """,
            (question_id, player_id),
        ).fetchone()

    return row is not None


def save_auction_bid(
    *,
    question_id: str,
    player_id: int,
    bid: int,
) -> None:
    """Save player's auction bid."""
    if bid < 0:
        raise ValueError("Ставка не может быть отрицательной.")

    with get_connection() as connection:
        player_row = connection.execute(
            """
            SELECT score
            FROM players
            WHERE id = ?
            """,
            (player_id,),
        ).fetchone()

        if player_row is None:
            raise PlayerNotFoundError("Player was not found.")

        player_score = int(player_row["score"])

        if player_score <= 0:
            raise ValueError("У вас нет положительных баллов для ставки.")

        if bid > player_score:
            raise ValueError("Ставка не может быть больше ваших баллов.")

        participant_row = connection.execute(
            """
            SELECT 1
            FROM auction_participants
            WHERE question_id = ? AND player_id = ?
            """,
            (question_id, player_id),
        ).fetchone()

        if participant_row is None:
            raise ValueError("Вы не участвуете в этом аукционе.")

        connection.execute(
            """
            INSERT INTO auction_bids (
                question_id,
                player_id,
                bid
            )
            VALUES (?, ?, ?)
            """,
            (question_id, player_id, bid),
        )


def get_auction_progress(question_id: str) -> dict[str, int]:
    """Return auction bidding progress."""
    with get_connection() as connection:
        participants_count = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM auction_participants
            WHERE question_id = ?
            """,
            (question_id,),
        ).fetchone()["count"]

        bids_count = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM auction_bids
            WHERE question_id = ?
            """,
            (question_id,),
        ).fetchone()["count"]

    return {
        "participants_count": int(participants_count),
        "bids_count": int(bids_count),
    }


def are_all_auction_bids_submitted(question_id: str) -> bool:
    """Return True if all auction participants submitted bids."""
    progress = get_auction_progress(question_id)

    return (
        progress["participants_count"] > 0
        and progress["bids_count"] >= progress["participants_count"]
    )


def get_auction_winner(question_id: str) -> dict[str, Any] | None:
    """Return auction winner by highest bid and earliest bid time."""
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                auction_bids.id,
                auction_bids.question_id,
                auction_bids.player_id,
                auction_bids.bid,
                auction_bids.created_at,
                players.nickname,
                players.score
            FROM auction_bids
            JOIN players ON players.id = auction_bids.player_id
            WHERE auction_bids.question_id = ?
            ORDER BY auction_bids.bid DESC, auction_bids.created_at ASC, auction_bids.id ASC
            LIMIT 1
            """,
            (question_id,),
        ).fetchone()

    if row is None:
        return None

    return dict(row)


def set_auction_winner(
    *,
    question_id: str,
    winner_player_id: int,
) -> None:
    """Move auction to question phase and save winner."""
    set_current_question(
        question_id,
        phase="auction_question",
        auction_winner_player_id=winner_player_id,
    )


def close_auction_question_and_calculate_score(
    question_id: str,
) -> list[dict[str, Any]]:
    """Close auction question and calculate winner score by bid."""
    state = get_game_state()
    winner_player_id = state.get("auction_winner_player_id")

    if winner_player_id is None:
        raise ValueError("Auction winner is not selected.")

    question = get_question_by_id(question_id)
    if question is None:
        raise QuestionNotFoundError("Question was not found.")

    if question["is_used"]:
        raise QuestionAlreadyUsedError("Question is already used.")

    winner_bid = get_auction_bid_for_player(
        question_id=question_id,
        player_id=int(winner_player_id),
    )

    if winner_bid is None:
        raise ValueError("Auction winner bid was not found.")

    winner_answer = get_answer_for_player(
        player_id=int(winner_player_id),
        question_id=question_id,
    )

    score_updates: list[dict[str, Any]] = []

    if winner_answer is not None:
        correct = is_answer_correct(
            player_answer=winner_answer["answer"],
            correct_answers=question["correct_answers"],
        )

        bid = int(winner_bid["bid"])
        points_delta = bid if correct else -bid

        new_score = update_player_score(
            player_id=int(winner_player_id),
            points_delta=points_delta,
        )

        set_answer_result(
            answer_id=int(winner_answer["id"]),
            is_correct=correct,
            points_delta=points_delta,
        )

        score_updates.append(
            {
                "player_id": int(winner_player_id),
                "score": new_score,
                "points_delta": points_delta,
                "is_correct": correct,
            }
        )

    lock_answers_for_question(question_id)
    mark_question_used(question_id)
    clear_current_question()

    return score_updates


def normalize_actual_gender(actual_gender: str) -> str:
    """Validate and normalize the configured actual gender."""
    normalized_gender = actual_gender.strip().lower()

    if normalized_gender not in {"boy", "girl"}:
        raise ValueError("Actual gender must be either 'boy' or 'girl'.")

    return normalized_gender


def start_final_round(*, actual_gender: str) -> None:
    """Start final gender voting round."""
    normalized_gender = normalize_actual_gender(actual_gender)

    with get_connection() as connection:
        connection.execute(
            """
            DELETE FROM final_votes
            """
        )

        connection.execute(
            """
            UPDATE game_state
            SET
                current_phase = 'final_open',
                current_question_id = NULL,
                question_open = 0,
                auction_winner_player_id = NULL,
                final_locked = 0,
                actual_gender = ?,
                final_drumroll_start_at_ms = NULL,
                final_reveal_at_ms = NULL,
                final_reveal_sequence_id = NULL,
                answer_reveal_sequence_id = NULL,
                answer_reveal_started_at_ms = NULL,
                answer_reveal_ends_at_ms = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
            """,
            (normalized_gender,),
        )


def schedule_final_reveal(
    *,
    drumroll_start_at_ms: int,
    reveal_at_ms: int,
    sequence_id: str,
) -> None:
    """Lock final votes and persist the synchronized drumroll schedule."""
    if drumroll_start_at_ms <= 0 or reveal_at_ms <= drumroll_start_at_ms:
        raise ValueError("Некорректное время раскрытия финала.")

    if not sequence_id.strip():
        raise ValueError("Не задан идентификатор раскрытия финала.")

    with get_connection() as connection:
        claimed = connection.execute(
            """
            UPDATE game_state
            SET
                current_phase = 'final_drumroll',
                final_locked = 1,
                final_drumroll_start_at_ms = ?,
                final_reveal_at_ms = ?,
                final_reveal_sequence_id = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = 1 AND current_phase = 'final_open'
            """,
            (drumroll_start_at_ms, reveal_at_ms, sequence_id),
        )

        if claimed.rowcount != 1:
            raise ValueError("Финальный раунд сейчас нельзя раскрыть.")

        connection.execute(
            """
            UPDATE final_votes
            SET locked = 1, updated_at = CURRENT_TIMESTAMP
            """
        )


def save_final_vote(
    *,
    player_id: int,
    choice: str,
) -> None:
    """Save or update player's final gender vote."""
    if choice not in {"boy", "girl"}:
        raise ValueError("Некорректный вариант ответа.")

    state = get_game_state()

    if state["current_phase"] != "final_open":
        raise ValueError("Финальный раунд сейчас не открыт.")

    if int(state["final_locked"]):
        raise ValueError("Ответы финального раунда уже зафиксированы.")

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO final_votes (
                player_id,
                choice,
                locked
            )
            VALUES (?, ?, 0)
            ON CONFLICT(player_id)
            DO UPDATE SET
                choice = excluded.choice,
                updated_at = CURRENT_TIMESTAMP
            WHERE locked = 0
            """,
            (player_id, choice),
        )


def get_final_vote_counts() -> dict[str, int]:
    """Return final vote counts."""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT choice, COUNT(*) AS count
            FROM final_votes
            GROUP BY choice
            """
        ).fetchall()

    counts = {
        "boy": 0,
        "girl": 0,
    }

    for row in rows:
        counts[str(row["choice"])] = int(row["count"])

    return counts


def get_final_vote_for_player(player_id: int) -> dict[str, Any] | None:
    """Return player's final vote or None."""
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, player_id, choice, locked
            FROM final_votes
            WHERE player_id = ?
            """,
            (player_id,),
        ).fetchone()

    if row is None:
        return None

    return dict(row)


def reveal_final_round() -> list[dict[str, Any]]:
    """Finalize the scheduled answer and double scores for correct voters once."""
    score_updates: list[dict[str, Any]] = []

    with get_connection() as connection:
        state = connection.execute(
            """
            SELECT current_phase, actual_gender
            FROM game_state
            WHERE id = 1
            """
        ).fetchone()

        if state is None or state["current_phase"] != "final_drumroll":
            raise ValueError("Финальное раскрытие не запланировано или уже выполнено.")

        claimed = connection.execute(
            """
            UPDATE game_state
            SET current_phase = 'final_revealing', updated_at = CURRENT_TIMESTAMP
            WHERE id = 1 AND current_phase = 'final_drumroll'
            """
        )

        if claimed.rowcount != 1:
            raise ValueError("Финальное раскрытие уже выполняется.")

        actual_gender = str(state["actual_gender"])

        correct_votes = connection.execute(
            """
            SELECT player_id
            FROM final_votes
            WHERE choice = ?
            """,
            (actual_gender,),
        ).fetchall()

        for vote in correct_votes:
            player_id = int(vote["player_id"])

            player_row = connection.execute(
                """
                SELECT score
                FROM players
                WHERE id = ?
                """,
                (player_id,),
            ).fetchone()

            if player_row is None:
                continue

            old_score = int(player_row["score"])
            new_score = old_score * 2

            connection.execute(
                """
                UPDATE players
                SET score = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (new_score, player_id),
            )

            score_updates.append(
                {
                    "player_id": player_id,
                    "score": new_score,
                    "old_score": old_score,
                    "points_delta": new_score - old_score,
                    "is_correct": True,
                }
            )

        connection.execute(
            """
            UPDATE game_state
            SET
                current_phase = 'final_revealed',
                final_locked = 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
            """
        )

    return score_updates


def normalize_baby_name(name: str) -> str:
    """Normalize baby name for duplicate checks."""
    return name.strip().lower().replace("ё", "е")


def start_secret_round() -> None:
    """Start secret baby name round."""
    state = get_game_state()

    if state["current_phase"] != "final_revealed":
        raise ValueError("Секретный раунд доступен только после раскрытия финала.")

    with get_connection() as connection:
        connection.execute(
            """
            DELETE FROM baby_names
            """
        )

        connection.execute(
            """
            DELETE FROM name_votes
            """
        )

        connection.execute(
            """
            UPDATE game_state
            SET
                current_phase = 'secret_names',
                secret_round_open = 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
            """
        )


def list_baby_names() -> list[dict[str, Any]]:
    """Return baby names ordered by rating."""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                baby_names.id,
                baby_names.display_name,
                baby_names.normalized_name,
                baby_names.rating,
                baby_names.created_by_player_id,
                players.nickname AS created_by_nickname
            FROM baby_names
            JOIN players ON players.id = baby_names.created_by_player_id
            ORDER BY baby_names.rating DESC, baby_names.id ASC
            """
        ).fetchall()

    return [dict(row) for row in rows]


def submit_baby_name(
    *,
    player_id: int,
    name: str,
) -> dict[str, Any]:
    """Submit baby name suggestion and return saved name."""
    display_name = name.strip()
    normalized_name = normalize_baby_name(display_name)

    if not display_name:
        raise ValueError("Введите имя.")

    if len(display_name) > 32:
        raise ValueError("Имя должно быть не длиннее 32 символов.")

    state = get_game_state()

    if state["current_phase"] != "secret_names":
        raise ValueError("Секретный раунд сейчас не открыт.")

    with get_connection() as connection:
        existing_player_name = connection.execute(
            """
            SELECT
                baby_names.id,
                baby_names.display_name,
                baby_names.normalized_name,
                baby_names.rating,
                baby_names.created_by_player_id,
                players.nickname AS created_by_nickname
            FROM baby_names
            JOIN players ON players.id = baby_names.created_by_player_id
            WHERE baby_names.created_by_player_id = ?
            """,
            (player_id,),
        ).fetchone()

        if existing_player_name is not None:
            raise ValueError("Вы уже предложили имя. Один игрок может предложить только одно имя.")

        existing = connection.execute(
            """
            SELECT id
            FROM baby_names
            WHERE normalized_name = ?
            """,
            (normalized_name,),
        ).fetchone()

        if existing is not None:
            row = connection.execute(
                """
                SELECT
                    baby_names.id,
                    baby_names.display_name,
                    baby_names.normalized_name,
                    baby_names.rating,
                    baby_names.created_by_player_id,
                    players.nickname AS created_by_nickname
                FROM baby_names
                JOIN players ON players.id = baby_names.created_by_player_id
                WHERE baby_names.id = ?
                """,
                (int(existing["id"]),),
            ).fetchone()

            return dict(row)

        connection.execute(
            """
            INSERT INTO baby_names (
                display_name,
                normalized_name,
                rating,
                created_by_player_id
            )
            VALUES (?, ?, 0, ?)
            """,
            (display_name, normalized_name, player_id),
        )

        row = connection.execute(
            """
            SELECT
                baby_names.id,
                baby_names.display_name,
                baby_names.normalized_name,
                baby_names.rating,
                baby_names.created_by_player_id,
                players.nickname AS created_by_nickname
            FROM baby_names
            JOIN players ON players.id = baby_names.created_by_player_id
            WHERE baby_names.normalized_name = ?
            """,
            (normalized_name,),
        ).fetchone()

    if row is None:
        raise LookupError("Baby name was not saved.")

    return dict(row)


def vote_for_baby_name(
    *,
    player_id: int,
    name_id: int,
    amount: int,
) -> dict[str, Any]:
    """Vote for baby name using player's score."""
    if amount <= 0:
        raise ValueError("Ставка должна быть больше 0.")

    state = get_game_state()

    if state["current_phase"] != "secret_names":
        raise ValueError("Секретный раунд сейчас не открыт.")

    with get_connection() as connection:
        player_row = connection.execute(
            """
            SELECT score
            FROM players
            WHERE id = ?
            """,
            (player_id,),
        ).fetchone()

        if player_row is None:
            raise PlayerNotFoundError("Player was not found.")

        current_score = int(player_row["score"])

        if amount > current_score:
            raise ValueError("Нельзя отдать больше баллов, чем у вас есть.")

        name_row = connection.execute(
            """
            SELECT id
            FROM baby_names
            WHERE id = ?
            """,
            (name_id,),
        ).fetchone()

        if name_row is None:
            raise ValueError("Такого имени нет.")

        connection.execute(
            """
            INSERT INTO name_votes (
                player_id,
                name_id,
                amount
            )
            VALUES (?, ?, ?)
            """,
            (player_id, name_id, amount),
        )

        connection.execute(
            """
            UPDATE baby_names
            SET rating = rating + ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (amount, name_id),
        )

        new_score = current_score - amount

        connection.execute(
            """
            UPDATE players
            SET score = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (new_score, player_id),
        )

    return {
        "player_id": player_id,
        "score": new_score,
        "points_delta": -amount,
        "name_id": name_id,
        "amount": amount,
    }


def get_baby_name_winner() -> dict[str, Any] | None:
    """Return baby name with highest rating."""
    names = list_baby_names()

    if not names:
        return None

    return names[0]


def reset_game(*, actual_gender: str) -> None:
    """Reset the whole game, including registered players."""
    normalized_gender = normalize_actual_gender(actual_gender)

    with get_connection() as connection:
        connection.execute("DELETE FROM answers")
        connection.execute("DELETE FROM auction_participants")
        connection.execute("DELETE FROM auction_bids")
        connection.execute("DELETE FROM final_votes")
        connection.execute("DELETE FROM baby_names")
        connection.execute("DELETE FROM name_votes")
        connection.execute("DELETE FROM players")

        connection.execute(
            """
            UPDATE questions
            SET
                is_used = 0,
                updated_at = CURRENT_TIMESTAMP
            """
        )

        connection.execute(
            """
            UPDATE game_state
            SET
                current_phase = 'waiting',
                current_question_id = NULL,
                question_open = 0,
                auction_winner_player_id = NULL,
                final_locked = 0,
                actual_gender = ?,
                secret_round_open = 0,
                final_drumroll_start_at_ms = NULL,
                final_reveal_at_ms = NULL,
                final_reveal_sequence_id = NULL,
                answer_reveal_sequence_id = NULL,
                answer_reveal_started_at_ms = NULL,
                answer_reveal_ends_at_ms = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
            """,
            (normalized_gender,),
        )

