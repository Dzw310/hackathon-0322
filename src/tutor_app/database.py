from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


_SCHEMA_SQL = """
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
);
CREATE TABLE IF NOT EXISTS session_history (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
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
);
CREATE TABLE IF NOT EXISTS step_attempts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    TEXT NOT NULL,
    user_id       TEXT NOT NULL,
    step_index    INTEGER NOT NULL,
    step_title    TEXT NOT NULL,
    answer        TEXT NOT NULL,
    is_correct    INTEGER NOT NULL,
    attempt_number INTEGER NOT NULL,
    feedback      TEXT,
    created_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_session_history_user ON session_history(user_id);
CREATE INDEX IF NOT EXISTS idx_step_attempts_session ON step_attempts(session_id);
CREATE INDEX IF NOT EXISTS idx_step_attempts_user ON step_attempts(user_id);
"""


class Database:
    """Unified database layer.

    Uses PostgreSQL when DATABASE_URL is set (production/Vercel),
    falls back to SQLite for local development.
    """

    def __init__(self, sqlite_path: str | Path | None = None) -> None:
        self._use_pg = "DATABASE_URL" in os.environ and sqlite_path is None
        if not self._use_pg:
            path = str(sqlite_path or Path(__file__).resolve().parent.parent.parent / "thinkstep.db")
            self._sqlite_conn = sqlite3.connect(path, check_same_thread=False)
            self._sqlite_conn.row_factory = sqlite3.Row
            self._sqlite_conn.execute("PRAGMA journal_mode=WAL")
            self._sqlite_conn.execute("PRAGMA foreign_keys=ON")
            self._sqlite_conn.executescript(_SCHEMA_SQL)
        else:
            self._sqlite_conn = None
            self._pg_init_schema()

    # ---- Connection helpers ----

    def _pg_conn(self):
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(os.environ["DATABASE_URL"], cursor_factory=psycopg2.extras.RealDictCursor)
        conn.autocommit = False
        return conn

    def _pg_init_schema(self) -> None:
        pg_schema = _SCHEMA_SQL.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
        with self._pg_conn() as conn:
            with conn.cursor() as cur:
                for stmt in pg_schema.split(";"):
                    stmt = stmt.strip()
                    if stmt:
                        cur.execute(stmt)
            conn.commit()

    def _execute(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        if self._use_pg:
            pg_sql = sql.replace("?", "%s")
            with self._pg_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(pg_sql, params)
                    if cur.description:
                        rows = cur.fetchall()
                        conn.commit()
                        return [dict(r) for r in rows]
                    conn.commit()
                    return []
        else:
            cur = self._sqlite_conn.execute(sql, params)
            if cur.description:
                rows = cur.fetchall()
                self._sqlite_conn.commit()
                return [dict(r) for r in rows]
            self._sqlite_conn.commit()
            return []

    # ---- User operations ----

    def create_user(self, user_id: str, username: str, display_name: str, age_group: str = "8-10") -> dict[str, Any]:
        now = _now_iso()
        self._execute(
            "INSERT INTO users (user_id, username, display_name, age_group, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, username.lower(), display_name, age_group, now, now),
        )
        return self.get_user(user_id)  # type: ignore[return-value]

    def get_user(self, user_id: str) -> dict[str, Any] | None:
        rows = self._execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return rows[0] if rows else None

    def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        rows = self._execute("SELECT * FROM users WHERE username = ?", (username.lower(),))
        return rows[0] if rows else None

    def update_user_age_group(self, user_id: str, age_group: str) -> None:
        self._execute("UPDATE users SET age_group = ?, updated_at = ? WHERE user_id = ?", (age_group, _now_iso(), user_id))

    def add_coins(self, user_id: str, amount: int) -> int:
        self._execute("UPDATE users SET coins = coins + ?, updated_at = ? WHERE user_id = ?", (amount, _now_iso(), user_id))
        rows = self._execute("SELECT coins FROM users WHERE user_id = ?", (user_id,))
        return rows[0]["coins"] if rows else 0

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
        self._execute(
            "UPDATE users SET current_streak = ?, best_streak = ?, updated_at = ? WHERE user_id = ?",
            (new_streak, best, _now_iso(), user_id),
        )
        return {"current_streak": new_streak, "best_streak": best}

    def increment_stats(self, user_id: str, correct: bool) -> None:
        if correct:
            self._execute(
                "UPDATE users SET total_steps_correct = total_steps_correct + 1, total_steps_attempted = total_steps_attempted + 1, updated_at = ? WHERE user_id = ?",
                (_now_iso(), user_id),
            )
        else:
            self._execute(
                "UPDATE users SET total_steps_attempted = total_steps_attempted + 1, updated_at = ? WHERE user_id = ?",
                (_now_iso(), user_id),
            )

    def increment_sessions_completed(self, user_id: str) -> None:
        self._execute(
            "UPDATE users SET sessions_completed = sessions_completed + 1, updated_at = ? WHERE user_id = ?",
            (_now_iso(), user_id),
        )

    # ---- Leaderboard ----

    def get_leaderboard(self, limit: int = 20) -> list[dict[str, Any]]:
        return self._execute(
            "SELECT user_id, username, display_name, coins, best_streak, current_streak, sessions_completed, total_steps_correct "
            "FROM users ORDER BY coins DESC, best_streak DESC LIMIT ?",
            (limit,),
        )

    # ---- Session history ----

    def record_session_start(self, user_id: str, session_id: str, question: str, age_group: str, total_steps: int) -> None:
        self._execute(
            "INSERT INTO session_history (user_id, session_id, question, age_group, total_steps, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, session_id, question, age_group, total_steps, _now_iso()),
        )

    def record_session_complete(self, session_id: str, steps_correct_first_try: int, total_attempts: int, coins_earned: int, summary_json: str | None = None) -> None:
        self._execute(
            "UPDATE session_history SET is_complete = 1, steps_correct_first_try = ?, total_attempts = ?, coins_earned = ?, summary_json = ?, completed_at = ? WHERE session_id = ?",
            (steps_correct_first_try, total_attempts, coins_earned, summary_json, _now_iso(), session_id),
        )

    def record_step_attempt(self, session_id: str, user_id: str, step_index: int, step_title: str, answer: str, is_correct: bool, attempt_number: int, feedback: str) -> None:
        self._execute(
            "INSERT INTO step_attempts (session_id, user_id, step_index, step_title, answer, is_correct, attempt_number, feedback, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (session_id, user_id, step_index, step_title, answer, int(is_correct), attempt_number, feedback, _now_iso()),
        )

    def get_user_sessions(self, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        return self._execute(
            "SELECT * FROM session_history WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        )

    def get_user_step_attempts(self, user_id: str, limit: int = 200) -> list[dict[str, Any]]:
        return self._execute(
            "SELECT * FROM step_attempts WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        )

    def get_user_error_patterns(self, user_id: str) -> list[dict[str, Any]]:
        return self._execute(
            """SELECT step_title, COUNT(*) as total_attempts,
                      SUM(CASE WHEN is_correct = 0 THEN 1 ELSE 0 END) as wrong_count,
                      SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) as correct_count
               FROM step_attempts WHERE user_id = ?
               GROUP BY step_title
               HAVING SUM(CASE WHEN is_correct = 0 THEN 1 ELSE 0 END) > 0
               ORDER BY wrong_count DESC LIMIT 20""",
            (user_id,),
        )
