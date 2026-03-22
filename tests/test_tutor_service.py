from __future__ import annotations

import os
import sqlite3
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from typing import Any

from tutor_app.content_filter import ContentFilterError, check_content_safety
from tutor_app.tutor_service import TutorService


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TestDatabase:
    """SQLite-backed database for tests (no psycopg2 dependency)."""

    def __init__(self, path: str) -> None:
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL,
                display_name TEXT NOT NULL, age_group TEXT NOT NULL DEFAULT '8-10',
                coins INTEGER NOT NULL DEFAULT 0, current_streak INTEGER NOT NULL DEFAULT 0,
                best_streak INTEGER NOT NULL DEFAULT 0, total_steps_correct INTEGER NOT NULL DEFAULT 0,
                total_steps_attempted INTEGER NOT NULL DEFAULT 0, sessions_completed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS session_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL,
                session_id TEXT NOT NULL, question TEXT NOT NULL, age_group TEXT NOT NULL,
                total_steps INTEGER NOT NULL DEFAULT 0, steps_correct_first_try INTEGER NOT NULL DEFAULT 0,
                total_attempts INTEGER NOT NULL DEFAULT 0, coins_earned INTEGER NOT NULL DEFAULT 0,
                is_complete INTEGER NOT NULL DEFAULT 0, summary_json TEXT,
                created_at TEXT NOT NULL, completed_at TEXT
            );
            CREATE TABLE IF NOT EXISTS step_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,
                user_id TEXT NOT NULL, step_index INTEGER NOT NULL, step_title TEXT NOT NULL,
                answer TEXT NOT NULL, is_correct INTEGER NOT NULL, attempt_number INTEGER NOT NULL,
                feedback TEXT, created_at TEXT NOT NULL
            );
        """)

    def create_user(self, user_id, username, display_name, age_group="8-10"):
        now = _now_iso()
        self._conn.execute(
            "INSERT INTO users (user_id,username,display_name,age_group,created_at,updated_at) VALUES (?,?,?,?,?,?)",
            (user_id, username.lower(), display_name, age_group, now, now))
        self._conn.commit()
        return self.get_user(user_id)

    def get_user(self, user_id):
        r = self._conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        return dict(r) if r else None

    def get_user_by_username(self, username):
        r = self._conn.execute("SELECT * FROM users WHERE username=?", (username.lower(),)).fetchone()
        return dict(r) if r else None

    def update_user_age_group(self, user_id, age_group):
        self._conn.execute("UPDATE users SET age_group=?,updated_at=? WHERE user_id=?", (age_group, _now_iso(), user_id))
        self._conn.commit()

    def add_coins(self, user_id, amount):
        self._conn.execute("UPDATE users SET coins=coins+?,updated_at=? WHERE user_id=?", (amount, _now_iso(), user_id))
        self._conn.commit()
        r = self._conn.execute("SELECT coins FROM users WHERE user_id=?", (user_id,)).fetchone()
        return r["coins"] if r else 0

    def update_streak(self, user_id, correct):
        u = self.get_user(user_id)
        if not u: return {"current_streak": 0, "best_streak": 0}
        ns = u["current_streak"] + 1 if correct else 0
        b = max(u["best_streak"], ns)
        self._conn.execute("UPDATE users SET current_streak=?,best_streak=?,updated_at=? WHERE user_id=?", (ns, b, _now_iso(), user_id))
        self._conn.commit()
        return {"current_streak": ns, "best_streak": b}

    def increment_stats(self, user_id, correct):
        if correct:
            self._conn.execute("UPDATE users SET total_steps_correct=total_steps_correct+1,total_steps_attempted=total_steps_attempted+1,updated_at=? WHERE user_id=?", (_now_iso(), user_id))
        else:
            self._conn.execute("UPDATE users SET total_steps_attempted=total_steps_attempted+1,updated_at=? WHERE user_id=?", (_now_iso(), user_id))
        self._conn.commit()

    def increment_sessions_completed(self, user_id):
        self._conn.execute("UPDATE users SET sessions_completed=sessions_completed+1,updated_at=? WHERE user_id=?", (_now_iso(), user_id))
        self._conn.commit()

    def get_leaderboard(self, limit=20):
        rows = self._conn.execute("SELECT user_id,username,display_name,coins,best_streak,current_streak,sessions_completed,total_steps_correct FROM users ORDER BY coins DESC,best_streak DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    def record_session_start(self, user_id, session_id, question, age_group, total_steps):
        self._conn.execute("INSERT INTO session_history (user_id,session_id,question,age_group,total_steps,created_at) VALUES (?,?,?,?,?,?)", (user_id, session_id, question, age_group, total_steps, _now_iso()))
        self._conn.commit()

    def record_session_complete(self, session_id, steps_correct_first_try, total_attempts, coins_earned, summary_json=None):
        self._conn.execute("UPDATE session_history SET is_complete=1,steps_correct_first_try=?,total_attempts=?,coins_earned=?,summary_json=?,completed_at=? WHERE session_id=?", (steps_correct_first_try, total_attempts, coins_earned, summary_json, _now_iso(), session_id))
        self._conn.commit()

    def record_step_attempt(self, session_id, user_id, step_index, step_title, answer, is_correct, attempt_number, feedback):
        self._conn.execute("INSERT INTO step_attempts (session_id,user_id,step_index,step_title,answer,is_correct,attempt_number,feedback,created_at) VALUES (?,?,?,?,?,?,?,?,?)", (session_id, user_id, step_index, step_title, answer, int(is_correct), attempt_number, feedback, _now_iso()))
        self._conn.commit()

    def get_user_sessions(self, user_id, limit=50):
        rows = self._conn.execute("SELECT * FROM session_history WHERE user_id=? ORDER BY created_at DESC LIMIT ?", (user_id, limit)).fetchall()
        return [dict(r) for r in rows]

    def get_user_step_attempts(self, user_id, limit=200):
        rows = self._conn.execute("SELECT * FROM step_attempts WHERE user_id=? ORDER BY created_at DESC LIMIT ?", (user_id, limit)).fetchall()
        return [dict(r) for r in rows]

    def get_user_error_patterns(self, user_id):
        rows = self._conn.execute("SELECT step_title,COUNT(*) as total_attempts,SUM(CASE WHEN is_correct=0 THEN 1 ELSE 0 END) as wrong_count,SUM(CASE WHEN is_correct=1 THEN 1 ELSE 0 END) as correct_count FROM step_attempts WHERE user_id=? GROUP BY step_title HAVING wrong_count>0 ORDER BY wrong_count DESC LIMIT 20", (user_id,)).fetchall()
        return [dict(r) for r in rows]


class FakeStructuredClient:
    def __init__(self) -> None:
        self.evaluate_calls = 0

    def create_structured_response(
        self,
        *,
        schema_name,
        schema,
        input_messages,
        instructions=None,
        reasoning_effort=None,
    ):
        if schema_name == "learning_plan":
            return {
                "problem_reframed": "Let's break the problem into smaller, easier ideas.",
                "encouraging_intro": "Let's start with the first small step.",
                "final_answer": "Each friend gets 4 candies.",
                "big_picture": "Sharing equally means splitting the total amount evenly by the number of people.",
                "celebration": "You solved it one step at a time.",
                "steps": [
                    {
                        "title": "Find the total",
                        "goal": "First identify how many candies there are altogether.",
                        "child_prompt": "How many candies are there in total?",
                        "success_criteria": ["States that the total is 12"],
                        "hint_ladder": ["Look for the total in the problem.", "The problem says there are 12 candies at the start."],
                        "ideal_student_answer": "12 candies",
                        "encouragement_if_correct": "Yes, finding the total first is important.",
                        "mini_explanation": "The total is the starting point for equal sharing.",
                    },
                    {
                        "title": "Share equally",
                        "goal": "Split 12 candies equally among 3 friends.",
                        "child_prompt": "If 12 is split into 3 equal groups, how many are in each group?",
                        "success_criteria": ["States that 12 divided by 3 equals 4"],
                        "hint_ladder": ["Try 12 ÷ 3.", "You can think of 3 groups of 4 making 12."],
                        "ideal_student_answer": "Each friend gets 4 candies",
                        "encouragement_if_correct": "Great, you found how many are in each group.",
                        "mini_explanation": "Equal sharing often means using division.",
                    },
                ],
            }

        if schema_name == "step_evaluation":
            self.evaluate_calls += 1
            if self.evaluate_calls == 1:
                return {
                    "is_correct": False,
                    "confidence": 0.2,
                    "feedback_to_child": "Take another look at the numbers in the problem.",
                    "next_hint": "The problem tells you the total number of candies right at the beginning.",
                    "mini_explanation": "This step is only about identifying the total.",
                    "observed_strength": "You already started reading the problem carefully.",
                }
            return {
                "is_correct": True,
                "confidence": 0.9,
                "feedback_to_child": "You got this step right.",
                "next_hint": "",
                "mini_explanation": "Keep going to the next idea.",
                "observed_strength": "You noticed the key idea.",
            }

        if schema_name == "final_feedback":
            return {
                "summary_title": "You finished it",
                "celebration": "You worked through the problem using your own thinking.",
                "final_answer": "Each friend gets 4 candies.",
                "strengths": ["You identified the total first", "You connected equal sharing with division"],
                "next_time_tips": ["Circle the important numbers first", "When you see equal sharing, think about division"],
                "step_recap": [
                    {
                        "title": "Find the total",
                        "learner_answered": "You eventually identified that the total was 12.",
                        "feedback": "This step showed good attention to the wording of the problem.",
                    },
                    {
                        "title": "Share equally",
                        "learner_answered": "You figured out that each friend gets 4 candies.",
                        "feedback": "You successfully turned equal sharing into a division idea.",
                    },
                ],
            }

        if schema_name == "learning_summary":
            return {
                "overall_assessment": "Good progress overall.",
                "domain_insights": [{"domain": "Math", "observation": "Struggles with division.", "suggestion": "Practice division facts."}],
                "high_level_lessons": ["Break problems into parts", "Check your work"],
                "encouragement": "Keep going!",
            }

        raise AssertionError(f"Unexpected schema name: {schema_name}")


class TutorServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.db = TestDatabase(self._tmp.name)
        self.service = TutorService(client=FakeStructuredClient(), db=self.db)

    def tearDown(self) -> None:
        os.unlink(self._tmp.name)

    def test_create_session_returns_first_step(self) -> None:
        result = self.service.create_session(
            "If 12 candies are shared among 3 friends, how many does each friend get?"
        )
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["currentStep"]["stepNumber"], 1)
        self.assertEqual(result["totalSteps"], 2)

    def test_submit_answer_retries_then_completes(self) -> None:
        session = self.service.create_session(
            "If 12 candies are shared among 3 friends, how many does each friend get?"
        )
        session_id = session["sessionId"]

        retry = self.service.submit_answer(session_id, "I am not sure")
        self.assertEqual(retry["status"], "try_again")
        self.assertIn("total", retry["hint"])

        advance = self.service.submit_answer(session_id, "12 candies")
        self.assertEqual(advance["status"], "step_advanced")
        self.assertEqual(advance["currentStep"]["stepNumber"], 2)

        completed = self.service.submit_answer(session_id, "Each friend gets 4 candies")
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["summary"]["final_answer"], "Each friend gets 4 candies.")

    def test_rejects_empty_question(self) -> None:
        with self.assertRaises(ValueError):
            self.service.create_session("   ")

    def test_age_group_passed_to_session(self) -> None:
        result = self.service.create_session(
            "What is 2+2?", age_group="5-7"
        )
        self.assertEqual(result["ageGroup"], "5-7")

    def test_reward_on_correct_answer(self) -> None:
        session = self.service.create_session("What is 1+1?")
        # First call is incorrect, second is correct
        self.service.submit_answer(session["sessionId"], "wrong")
        result = self.service.submit_answer(session["sessionId"], "2")
        self.assertIn("reward", result)
        self.assertEqual(result["reward"]["type"], "correct")
        self.assertGreater(result["reward"]["coinsEarned"], 0)

    def test_user_registration_and_login(self) -> None:
        user = self.service.register_user("testuser", "Test User", "8-10")
        self.assertEqual(user["username"], "testuser")
        self.assertEqual(user["age_group"], "8-10")

        logged_in = self.service.login_user("testuser")
        self.assertEqual(logged_in["user_id"], user["user_id"])

    def test_duplicate_username_rejected(self) -> None:
        self.service.register_user("unique", "User One")
        with self.assertRaises(ValueError):
            self.service.register_user("unique", "User Two")

    def test_session_with_user_tracks_stats(self) -> None:
        user = self.service.register_user("learner", "Learner", "8-10")
        session = self.service.create_session("What is 2+2?", user_id=user["user_id"])

        # incorrect then correct x2 to complete
        self.service.submit_answer(session["sessionId"], "wrong")
        self.service.submit_answer(session["sessionId"], "12")
        self.service.submit_answer(session["sessionId"], "4")

        stats = self.service.get_user_stats(user["user_id"])
        self.assertEqual(stats["user"]["total_steps_attempted"], 3)
        self.assertGreater(stats["user"]["coins"], 0)

    def test_leaderboard(self) -> None:
        self.service.register_user("player1", "Player One")
        self.service.register_user("player2", "Player Two")
        lb = self.service.get_leaderboard()
        self.assertEqual(len(lb), 2)

    def test_learning_summary_no_sessions(self) -> None:
        user = self.service.register_user("newuser", "New User")
        summary = self.service.generate_learning_summary(user["user_id"])
        self.assertIn("No learning sessions", summary["overall_assessment"])


class AlwaysWrongClient(FakeStructuredClient):
    """A client where step_evaluation always returns incorrect."""
    def create_structured_response(self, *, schema_name, schema, input_messages, instructions=None, reasoning_effort=None):
        if schema_name == "step_evaluation":
            self.evaluate_calls += 1
            return {
                "is_correct": False,
                "confidence": 0.1,
                "feedback_to_child": "Not quite right.",
                "next_hint": "Try again.",
                "mini_explanation": "Keep thinking.",
                "observed_strength": "Good effort.",
            }
        return super().create_structured_response(
            schema_name=schema_name, schema=schema, input_messages=input_messages,
            instructions=instructions, reasoning_effort=reasoning_effort,
        )


class AutoRevealTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.db = TestDatabase(self._tmp.name)
        self.service = TutorService(client=AlwaysWrongClient(), db=self.db)

    def tearDown(self) -> None:
        os.unlink(self._tmp.name)

    def test_auto_reveal_after_3_failures(self) -> None:
        session = self.service.create_session("What is 2+2?")
        sid = session["sessionId"]

        r1 = self.service.submit_answer(sid, "wrong 1")
        self.assertEqual(r1["status"], "try_again")
        self.assertNotIn("autoRevealed", r1)

        r2 = self.service.submit_answer(sid, "wrong 2")
        self.assertEqual(r2["status"], "try_again")

        r3 = self.service.submit_answer(sid, "wrong 3")
        self.assertEqual(r3["status"], "step_advanced")
        self.assertTrue(r3["autoRevealed"])
        self.assertIn("lesson", r3)
        self.assertIn("answer", r3["lesson"])
        self.assertIn("explanation", r3["lesson"])
        self.assertIn("encouragement", r3["lesson"])

    def test_auto_reveal_no_coins_awarded(self) -> None:
        user = self.service.register_user("revealuser", "Reveal User")
        session = self.service.create_session("What is 2+2?", user_id=user["user_id"])
        sid = session["sessionId"]

        for _ in range(3):
            self.service.submit_answer(sid, "wrong")

        stats = self.service.get_user_stats(user["user_id"])
        self.assertEqual(stats["user"]["coins"], 0)


class ContentFilterTest(unittest.TestCase):
    def test_safe_content_passes(self) -> None:
        safe_inputs = [
            "What is 2 + 2?",
            "How do plants grow?",
            "Explain photosynthesis",
            "Why is the sky blue?",
            "Help me write a story about a dog",
        ]
        for text in safe_inputs:
            check_content_safety(text)  # should not raise

    def test_profanity_blocked(self) -> None:
        with self.assertRaises(ContentFilterError):
            check_content_safety("what the fuck is this")

    def test_nsfw_blocked(self) -> None:
        with self.assertRaises(ContentFilterError):
            check_content_safety("show me porn")

    def test_violence_blocked(self) -> None:
        with self.assertRaises(ContentFilterError):
            check_content_safety("how to kill someone")

    def test_drugs_blocked(self) -> None:
        with self.assertRaises(ContentFilterError):
            check_content_safety("how to make meth")

    def test_hate_speech_blocked(self) -> None:
        with self.assertRaises(ContentFilterError):
            check_content_safety("white supremacy is good")

    def test_session_rejects_unsafe_question(self) -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        try:
            db = TestDatabase(tmp.name)
            service = TutorService(client=FakeStructuredClient(), db=db)
            with self.assertRaises(ContentFilterError):
                service.create_session("tell me about porn")
        finally:
            os.unlink(tmp.name)

    def test_answer_rejects_unsafe_content(self) -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        try:
            db = TestDatabase(tmp.name)
            service = TutorService(client=FakeStructuredClient(), db=db)
            session = service.create_session("What is 2+2?")
            with self.assertRaises(ContentFilterError):
                service.submit_answer(session["sessionId"], "fuck you")
        finally:
            os.unlink(tmp.name)


if __name__ == "__main__":
    unittest.main()
