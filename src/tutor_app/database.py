from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _conn():
    import psycopg2
    import psycopg2.extras
    url = os.environ["DATABASE_URL"]
    conn = psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = False
    return conn


class Database:
    def __init__(self) -> None:
        self._init_schema()

    def _init_schema(self) -> None:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id       TEXT PRIMARY KEY,
                        username      TEXT UNIQUE NOT NULL,
                        display_name  TEXT NOT NULL,
                        age_group     TEXT NOT NULL DEFAULT '8-10',
                        coins         INTEGER NOT NULL DEFAULT 0,
                        current_streak INTEGER NOT NULL DEFAULT 0,
                        best_streak   INTEGER NOT NULL DEFAULT 0,
                        total_steps_correct INTEGER NOT NULL DEFAULT 0,
                        total_steps_attempted INTEGER NOT NULL DEFAULT 0,
                        sessions_completed INTEGER NOT NULL DEFAULT 0,
                        created_at    TEXT NOT NULL,
                        updated_at    TEXT NOT NULL
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS session_history (
                        id            SERIAL PRIMARY KEY,
                        user_id       TEXT NOT NULL,
                        session_id    TEXT NOT NULL,
                        question      TEXT NOT NULL,
                        age_group     TEXT NOT NULL,
                        total_steps   INTEGER NOT NULL DEFAULT 0,
                        steps_correct_first_try INTEGER NOT NULL DEFAULT 0,
                        total_attempts INTEGER NOT NULL DEFAULT 0,
                        coins_earned  INTEGER NOT NULL DEFAULT 0,
                        is_complete   INTEGER NOT NULL DEFAULT 0,
                        summary_json  TEXT,
                        created_at    TEXT NOT NULL,
                        completed_at  TEXT,
                        FOREIGN KEY (user_id) REFERENCES users(user_id)
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS step_attempts (
                        id            SERIAL PRIMARY KEY,
                        session_id    TEXT NOT NULL,
                        user_id       TEXT NOT NULL,
                        step_index    INTEGER NOT NULL,
                        step_title    TEXT NOT NULL,
                        answer        TEXT NOT NULL,
                        is_correct    INTEGER NOT NULL,
                        attempt_number INTEGER NOT NULL,
                        feedback      TEXT,
                        created_at    TEXT NOT NULL
                    )
                """)
                cur.execute("CREATE INDEX IF NOT EXISTS idx_session_history_user ON session_history(user_id)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_step_attempts_session ON step_attempts(session_id)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_step_attempts_user ON step_attempts(user_id)")
            conn.commit()

    # ---- User operations ----

    def create_user(self, user_id: str, username: str, display_name: str, age_group: str = "8-10") -> dict[str, Any]:
        now = _now_iso()
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO users (user_id, username, display_name, age_group, created_at, updated_at) VALUES (%s, %s, %s, %s, %s, %s)",
                    (user_id, username.lower(), display_name, age_group, now, now),
                )
            conn.commit()
        return self.get_user(user_id)  # type: ignore[return-value]

    def get_user(self, user_id: str) -> dict[str, Any] | None:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
                row = cur.fetchone()
        return dict(row) if row else None

    def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM users WHERE username = %s", (username.lower(),))
                row = cur.fetchone()
        return dict(row) if row else None

    def update_user_age_group(self, user_id: str, age_group: str) -> None:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET age_group = %s, updated_at = %s WHERE user_id = %s",
                    (age_group, _now_iso(), user_id),
                )
            conn.commit()

    def add_coins(self, user_id: str, amount: int) -> int:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET coins = coins + %s, updated_at = %s WHERE user_id = %s RETURNING coins",
                    (amount, _now_iso(), user_id),
                )
                row = cur.fetchone()
            conn.commit()
        return row["coins"] if row else 0

    def update_streak(self, user_id: str, correct: bool) -> dict[str, int]:
        user = self.get_user(user_id)
        if not user:
            return {"current_streak": 0, "best_streak": 0}

        if correct:
            new_streak = user["current_streak"] + 1
            best = max(user["best_streak"], new_streak)
        else:
            new_streak = 0
            best = user["best_streak"]

        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET current_streak = %s, best_streak = %s, updated_at = %s WHERE user_id = %s",
                    (new_streak, best, _now_iso(), user_id),
                )
            conn.commit()
        return {"current_streak": new_streak, "best_streak": best}

    def increment_stats(self, user_id: str, correct: bool) -> None:
        with _conn() as conn:
            with conn.cursor() as cur:
                if correct:
                    cur.execute(
                        "UPDATE users SET total_steps_correct = total_steps_correct + 1, total_steps_attempted = total_steps_attempted + 1, updated_at = %s WHERE user_id = %s",
                        (_now_iso(), user_id),
                    )
                else:
                    cur.execute(
                        "UPDATE users SET total_steps_attempted = total_steps_attempted + 1, updated_at = %s WHERE user_id = %s",
                        (_now_iso(), user_id),
                    )
            conn.commit()

    def increment_sessions_completed(self, user_id: str) -> None:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET sessions_completed = sessions_completed + 1, updated_at = %s WHERE user_id = %s",
                    (_now_iso(), user_id),
                )
            conn.commit()

    # ---- Leaderboard ----

    def get_leaderboard(self, limit: int = 20) -> list[dict[str, Any]]:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT user_id, username, display_name, coins, best_streak, current_streak, sessions_completed, total_steps_correct "
                    "FROM users ORDER BY coins DESC, best_streak DESC LIMIT %s",
                    (limit,),
                )
                rows = cur.fetchall()
        return [dict(r) for r in rows]

    # ---- Session history ----

    def record_session_start(self, user_id: str, session_id: str, question: str, age_group: str, total_steps: int) -> None:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO session_history (user_id, session_id, question, age_group, total_steps, created_at) VALUES (%s, %s, %s, %s, %s, %s)",
                    (user_id, session_id, question, age_group, total_steps, _now_iso()),
                )
            conn.commit()

    def record_session_complete(self, session_id: str, steps_correct_first_try: int, total_attempts: int, coins_earned: int, summary_json: str | None = None) -> None:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE session_history SET is_complete = 1, steps_correct_first_try = %s, total_attempts = %s, coins_earned = %s, summary_json = %s, completed_at = %s WHERE session_id = %s",
                    (steps_correct_first_try, total_attempts, coins_earned, summary_json, _now_iso(), session_id),
                )
            conn.commit()

    def record_step_attempt(self, session_id: str, user_id: str, step_index: int, step_title: str, answer: str, is_correct: bool, attempt_number: int, feedback: str) -> None:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO step_attempts (session_id, user_id, step_index, step_title, answer, is_correct, attempt_number, feedback, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (session_id, user_id, step_index, step_title, answer, int(is_correct), attempt_number, feedback, _now_iso()),
                )
            conn.commit()

    def get_user_sessions(self, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM session_history WHERE user_id = %s ORDER BY created_at DESC LIMIT %s",
                    (user_id, limit),
                )
                rows = cur.fetchall()
        return [dict(r) for r in rows]

    def get_user_step_attempts(self, user_id: str, limit: int = 200) -> list[dict[str, Any]]:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM step_attempts WHERE user_id = %s ORDER BY created_at DESC LIMIT %s",
                    (user_id, limit),
                )
                rows = cur.fetchall()
        return [dict(r) for r in rows]

    def get_user_error_patterns(self, user_id: str) -> list[dict[str, Any]]:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT step_title, COUNT(*) as total_attempts,
                              SUM(CASE WHEN is_correct = 0 THEN 1 ELSE 0 END) as wrong_count,
                              SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) as correct_count
                       FROM step_attempts WHERE user_id = %s
                       GROUP BY step_title
                       HAVING SUM(CASE WHEN is_correct = 0 THEN 1 ELSE 0 END) > 0
                       ORDER BY wrong_count DESC LIMIT 20""",
                    (user_id,),
                )
                rows = cur.fetchall()
        return [dict(r) for r in rows]
