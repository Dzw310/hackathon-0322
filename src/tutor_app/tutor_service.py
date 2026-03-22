from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from typing import Any, Protocol

from tutor_app.content_filter import check_content_safety
from tutor_app.database import Database
from tutor_app.models import AttemptRecord, LearningPlan, TutorSession, TutorStep
from tutor_app.openai_client import OpenAIResponsesClient
from tutor_app.schemas import (
    FINAL_FEEDBACK_SCHEMA,
    LEARNING_PLAN_SCHEMA,
    LEARNING_SUMMARY_SCHEMA,
    STEP_EVALUATION_SCHEMA,
)
from tutor_app.session_store import InMemoryStore, SessionStore


AGE_GROUP_CONFIG = {
    "5-7": {
        "label": "Early learners (5-7)",
        "strategy": "full_scaffolding",
        "step_range": (3, 6),
        "prompt_style": (
            " The learner is a young child aged 5-7."
            " Break the problem into many small, concrete steps."
            " Use simple vocabulary and short sentences."
            " Each step should ask only one tiny question."
            " Be very warm, playful, and encouraging."
        ),
        "eval_style": (
            " The learner is a young child aged 5-7."
            " Be very generous in accepting answers — partial or approximate answers are fine."
            " Give enthusiastic, playful feedback."
            " Hints should be very concrete and direct."
        ),
        "coins_per_correct": 10,
        "coins_completion_bonus": 30,
    },
    "8-10": {
        "label": "Elementary (8-10)",
        "strategy": "partial_scaffolding",
        "step_range": (2, 5),
        "prompt_style": (
            " The learner is an elementary student aged 8-10."
            " Break the problem into clear steps, but allow some thinking gaps."
            " Use age-appropriate language."
            " Encourage the child to connect ideas between steps."
        ),
        "eval_style": (
            " The learner is an elementary student aged 8-10."
            " Accept correct meaning even if phrasing is imperfect."
            " Give clear, positive feedback."
        ),
        "coins_per_correct": 15,
        "coins_completion_bonus": 40,
    },
    "11-14": {
        "label": "Middle school (11-14)",
        "strategy": "hint_only",
        "step_range": (2, 4),
        "prompt_style": (
            " The learner is a middle school student aged 11-14."
            " Use fewer steps — only guide at key decision points."
            " child_prompt should hint at the direction without spelling it out."
            " Encourage the student to reason independently."
            " Use slightly more sophisticated language."
        ),
        "eval_style": (
            " The learner is a middle school student aged 11-14."
            " Expect more precise answers."
            " Feedback should be constructive and treat the student as capable."
            " Hints should be directional, not revealing."
        ),
        "coins_per_correct": 20,
        "coins_completion_bonus": 50,
    },
    "15-18": {
        "label": "High school (15-18)",
        "strategy": "challenge_mode",
        "step_range": (2, 3),
        "prompt_style": (
            " The learner is a high school student aged 15-18."
            " Use minimal steps — focus on key strategic decisions."
            " child_prompt should ask about approach and strategy, not specific calculations."
            " Encourage metacognition: ask WHY and HOW, not just WHAT."
            " Use mature, respectful language."
        ),
        "eval_style": (
            " The learner is a high school student aged 15-18."
            " Expect precise, well-reasoned answers."
            " Feedback should be concise and respect the student's intelligence."
            " Hints should be subtle and strategic."
        ),
        "coins_per_correct": 25,
        "coins_completion_bonus": 60,
    },
}

REWARD_MESSAGES = {
    "correct": [
        "Well done!",
        "Excellent thinking!",
        "You nailed it!",
        "Great job!",
        "Fantastic!",
        "You're on fire!",
        "Brilliant!",
        "Nice work!",
        "That's exactly right!",
        "Keep it up!",
    ],
    "streak_3": "Amazing! 3 correct in a row!",
    "streak_5": "Incredible! 5 correct streak! You're unstoppable!",
    "streak_10": "LEGENDARY! 10 correct streak! You're a thinking champion!",
    "completion": "You completed the entire challenge! That takes real determination.",
}


class StructuredLLMClient(Protocol):
    def create_structured_response(
        self,
        *,
        schema_name: str,
        schema: dict[str, Any],
        input_messages: list[dict[str, Any]],
        instructions: str | None = None,
        reasoning_effort: str | None = None,
    ) -> dict[str, Any]:
        ...


class TutorService:
    def __init__(
        self,
        client: StructuredLLMClient | None = None,
        store: SessionStore | None = None,
        db: Database | None = None,
    ) -> None:
        self._client = client or OpenAIResponsesClient.from_env()
        self._store = store or InMemoryStore()
        self._db = db or Database()

    def create_session(self, question: str, user_id: str | None = None, age_group: str = "8-10") -> dict[str, Any]:
        clean_question = question.strip()
        if not clean_question:
            raise ValueError("Question cannot be empty.")

        check_content_safety(clean_question)

        if age_group not in AGE_GROUP_CONFIG:
            age_group = "8-10"

        plan = self._generate_plan(clean_question, age_group)
        session = TutorSession(
            session_id=uuid.uuid4().hex,
            question=clean_question,
            plan=plan,
            user_id=user_id,
            age_group=age_group,
        )

        self._store.set(session)

        if user_id:
            self._db.record_session_start(
                user_id=user_id,
                session_id=session.session_id,
                question=clean_question,
                age_group=age_group,
                total_steps=len(plan.steps),
            )

        return {
            "status": "ready",
            "sessionId": session.session_id,
            "question": session.question,
            "intro": plan.encouraging_intro,
            "problemReframed": plan.problem_reframed,
            "totalSteps": len(plan.steps),
            "currentStepIndex": 0,
            "currentStep": self._serialize_step(plan.steps[0], 0, len(plan.steps)),
            "history": [],
            "ageGroup": age_group,
        }

    def submit_answer(self, session_id: str, answer: str) -> dict[str, Any]:
        clean_answer = answer.strip()
        if not clean_answer:
            raise ValueError("Please enter your answer or idea first.")

        check_content_safety(clean_answer)

        session = self._get_session(session_id)
        if session.is_complete:
            return {
                "status": "completed",
                "sessionId": session.session_id,
                "summary": session.final_feedback,
            }

        step_index = session.current_step_index
        step = session.plan.steps[step_index]
        attempt_count = session.attempts_for_step(step_index)
        evaluation = self._evaluate_step(
            question=session.question,
            step=step,
            learner_answer=clean_answer,
            attempt_count=attempt_count,
            age_group=session.age_group,
        )

        session.history.append(
            AttemptRecord(
                step_index=step_index,
                answer=clean_answer,
                is_correct=evaluation["is_correct"],
                feedback=evaluation["feedback_to_child"],
                hint=evaluation["next_hint"],
            )
        )

        is_correct = evaluation["is_correct"]
        reward = self._calculate_reward(session, is_correct)

        if session.user_id:
            self._db.record_step_attempt(
                session_id=session.session_id,
                user_id=session.user_id,
                step_index=step_index,
                step_title=step.title,
                answer=clean_answer,
                is_correct=is_correct,
                attempt_number=attempt_count + 1,
                feedback=evaluation["feedback_to_child"],
            )
            self._db.increment_stats(session.user_id, is_correct)
            self._db.update_streak(session.user_id, is_correct)

        if is_correct:
            if session.user_id:
                config = AGE_GROUP_CONFIG[session.age_group]
                self._db.add_coins(session.user_id, config["coins_per_correct"])

            session.current_step_index += 1
            if session.current_step_index >= len(session.plan.steps):
                session.is_complete = True
                summary = self._generate_final_feedback(session)
                session.final_feedback = summary

                if session.user_id:
                    config = AGE_GROUP_CONFIG[session.age_group]
                    self._db.add_coins(session.user_id, config["coins_completion_bonus"])
                    self._db.increment_sessions_completed(session.user_id)
                    steps_first_try = self._count_first_try_correct(session)
                    self._db.record_session_complete(
                        session_id=session.session_id,
                        steps_correct_first_try=steps_first_try,
                        total_attempts=len(session.history),
                        coins_earned=config["coins_per_correct"] * len(session.plan.steps) + config["coins_completion_bonus"],
                        summary_json=json.dumps(summary, ensure_ascii=False),
                    )

                self._store.set(session)
                return {
                    "status": "completed",
                    "sessionId": session.session_id,
                    "message": evaluation["feedback_to_child"],
                    "miniExplanation": evaluation["mini_explanation"],
                    "summary": summary,
                    "history": self._serialize_history(session),
                    "reward": reward,
                }

            next_index = session.current_step_index
            next_step = session.plan.steps[next_index]
            self._store.set(session)
            return {
                "status": "step_advanced",
                "sessionId": session.session_id,
                "message": evaluation["feedback_to_child"],
                "miniExplanation": evaluation["mini_explanation"],
                "currentStepIndex": next_index,
                "currentStep": self._serialize_step(
                    next_step, next_index, len(session.plan.steps)
                ),
                "history": self._serialize_history(session),
                "reward": reward,
            }

        self._store.set(session)
        return {
            "status": "try_again",
            "sessionId": session.session_id,
            "message": evaluation["feedback_to_child"],
            "hint": evaluation["next_hint"],
            "miniExplanation": evaluation["mini_explanation"],
            "currentStepIndex": step_index,
            "currentStep": self._serialize_step(step, step_index, len(session.plan.steps)),
            "history": self._serialize_history(session),
            "reward": reward,
        }

    def get_leaderboard(self) -> list[dict[str, Any]]:
        return self._db.get_leaderboard()

    def get_user_stats(self, user_id: str) -> dict[str, Any]:
        user = self._db.get_user(user_id)
        if not user:
            raise KeyError("User not found.")
        sessions = self._db.get_user_sessions(user_id)
        return {
            "user": user,
            "sessions": sessions,
            "totalSessions": len(sessions),
            "completedSessions": sum(1 for s in sessions if s["is_complete"]),
        }

    def generate_learning_summary(self, user_id: str) -> dict[str, Any]:
        sessions = self._db.get_user_sessions(user_id, limit=20)
        error_patterns = self._db.get_user_error_patterns(user_id)
        attempts = self._db.get_user_step_attempts(user_id, limit=100)

        if not sessions:
            return {
                "overall_assessment": "No learning sessions yet. Start your first question to begin!",
                "domain_insights": [],
                "high_level_lessons": ["Try asking your first question to get started!"],
                "encouragement": "Your learning journey is about to begin!",
            }

        developer_prompt = (
            "You are an educational analyst reviewing a child's learning history."
            " Analyze their error patterns and session performance to provide actionable insights."
            " Identify which domains or types of reasoning steps they struggle with most."
            " Provide high-level lessons — general thinking strategies they can apply next time."
            " Be encouraging and constructive. Write all output in English."
        )

        summary_payload = {
            "sessions": [
                {
                    "question": s["question"],
                    "total_steps": s["total_steps"],
                    "steps_correct_first_try": s["steps_correct_first_try"],
                    "total_attempts": s["total_attempts"],
                    "is_complete": bool(s["is_complete"]),
                }
                for s in sessions
            ],
            "error_patterns": error_patterns,
            "recent_attempts": [
                {
                    "step_title": a["step_title"],
                    "is_correct": bool(a["is_correct"]),
                    "attempt_number": a["attempt_number"],
                }
                for a in attempts[:50]
            ],
        }

        return self._client.create_structured_response(
            schema_name="learning_summary",
            schema=LEARNING_SUMMARY_SCHEMA,
            input_messages=[
                {"role": "developer", "content": developer_prompt},
                {"role": "user", "content": json.dumps(summary_payload, ensure_ascii=False)},
            ],
        )

    def register_user(self, username: str, display_name: str, age_group: str = "8-10") -> dict[str, Any]:
        existing = self._db.get_user_by_username(username)
        if existing:
            raise ValueError(f"Username '{username}' is already taken.")
        if age_group not in AGE_GROUP_CONFIG:
            age_group = "8-10"
        user_id = uuid.uuid4().hex
        return self._db.create_user(user_id, username, display_name, age_group)

    def login_user(self, username: str) -> dict[str, Any]:
        user = self._db.get_user_by_username(username)
        if not user:
            raise KeyError("User not found. Please register first.")
        return user

    def _calculate_reward(self, session: TutorSession, is_correct: bool) -> dict[str, Any]:
        reward: dict[str, Any] = {"type": "none", "message": "", "coinsEarned": 0}

        if not is_correct:
            reward["type"] = "encouragement"
            reward["message"] = "Keep trying! You're getting closer."
            return reward

        config = AGE_GROUP_CONFIG[session.age_group]
        coins = config["coins_per_correct"]
        reward["type"] = "correct"
        reward["coinsEarned"] = coins

        import hashlib
        idx = int(hashlib.md5(session.session_id.encode()).hexdigest(), 16) % len(REWARD_MESSAGES["correct"])
        step_offset = session.current_step_index
        msg_index = (idx + step_offset) % len(REWARD_MESSAGES["correct"])
        reward["message"] = REWARD_MESSAGES["correct"][msg_index]

        if session.user_id:
            user = self._db.get_user(session.user_id)
            if user:
                streak = user["current_streak"] + 1
                if streak >= 10:
                    reward["streakMessage"] = REWARD_MESSAGES["streak_10"]
                elif streak >= 5:
                    reward["streakMessage"] = REWARD_MESSAGES["streak_5"]
                elif streak >= 3:
                    reward["streakMessage"] = REWARD_MESSAGES["streak_3"]
                reward["currentStreak"] = streak

        is_last_step = session.current_step_index + 1 >= len(session.plan.steps)
        if is_last_step:
            reward["completionMessage"] = REWARD_MESSAGES["completion"]
            reward["coinsEarned"] += config["coins_completion_bonus"]

        return reward

    def _count_first_try_correct(self, session: TutorSession) -> int:
        step_first_attempts: dict[int, bool] = {}
        for record in session.history:
            if record.step_index not in step_first_attempts:
                step_first_attempts[record.step_index] = record.is_correct
        return sum(1 for v in step_first_attempts.values() if v)

    def _get_session(self, session_id: str) -> TutorSession:
        session = self._store.get(session_id)
        if not session:
            raise KeyError("No matching learning session was found.")
        return session

    def _generate_plan(self, question: str, age_group: str = "8-10") -> LearningPlan:
        config = AGE_GROUP_CONFIG.get(age_group, AGE_GROUP_CONFIG["8-10"])

        developer_prompt = (
            "You are a supportive tutor for children."
            " Your job is not to reveal the full answer immediately."
            " Break the problem into 2 to 6 interactive micro-steps."
            " Each step should invite the child to think before answering."
            " Use warm, specific, encouraging language without sounding childish."
            " Do not leak the final answer inside child_prompt."
            " success_criteria should describe the key ideas needed for a correct response."
            " hint_ladder should move from a gentle hint to a more specific hint."
            " ideal_student_answer should stay concise so later evaluation is easier."
            + config["prompt_style"]
        )
        user_payload = {
            "learner_question": question,
            "age_group": age_group,
            "scaffolding_strategy": config["strategy"],
            "requirements": [
                "Use English throughout the response",
                "Ask only one core idea per step",
                "Encourage the child to discover the pattern independently",
                "The final result should include the full reasoning path and answer",
                f"Target {config['step_range'][0]} to {config['step_range'][1]} steps for this age group",
            ],
        }
        raw = self._client.create_structured_response(
            schema_name="learning_plan",
            schema=LEARNING_PLAN_SCHEMA,
            input_messages=[
                {"role": "developer", "content": developer_prompt},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
        )
        steps = [TutorStep(**step_data) for step_data in raw["steps"]]
        return LearningPlan(
            problem_reframed=raw["problem_reframed"],
            encouraging_intro=raw["encouraging_intro"],
            final_answer=raw["final_answer"],
            big_picture=raw["big_picture"],
            celebration=raw["celebration"],
            steps=steps,
        )

    def _evaluate_step(
        self,
        *,
        question: str,
        step: TutorStep,
        learner_answer: str,
        attempt_count: int,
        age_group: str = "8-10",
    ) -> dict[str, Any]:
        config = AGE_GROUP_CONFIG.get(age_group, AGE_GROUP_CONFIG["8-10"])

        developer_prompt = (
            "You are evaluating one step in a child-focused tutoring product."
            " Use the current step's success_criteria to decide whether the child answered sufficiently."
            " If the meaning is correct but phrasing is incomplete, mark it correct."
            " If the answer is incorrect, do not reveal the full solution."
            " Prefer a light hint first."
            " On the first incorrect attempt, use the earlier hint from hint_ladder."
            " After repeated incorrect attempts, you may use a more specific hint while still encouraging thinking."
            " feedback_to_child should speak directly to the child and stay short, positive, and clear."
            " Write all output in English."
            + config["eval_style"]
        )
        judge_payload = {
            "original_question": question,
            "step": asdict(step),
            "attempt_count_before_this_answer": attempt_count,
            "learner_answer": learner_answer,
        }
        return self._client.create_structured_response(
            schema_name="step_evaluation",
            schema=STEP_EVALUATION_SCHEMA,
            input_messages=[
                {"role": "developer", "content": developer_prompt},
                {"role": "user", "content": json.dumps(judge_payload, ensure_ascii=False)},
            ],
        )

    def _generate_final_feedback(self, session: TutorSession) -> dict[str, Any]:
        developer_prompt = (
            "You are writing the final learning summary for a child."
            " First celebrate the effort, then recap the steps in clear language,"
            " and finally provide the complete answer and practical improvement tips."
            " In step_recap, learner_answered should summarize how the child performed on that step."
            " feedback should point out what the child did well or what still needs reinforcement."
            " Write all output in English."
        )
        history_payload = []
        for record in session.history:
            step = session.plan.steps[record.step_index]
            history_payload.append(
                {
                    "step_title": step.title,
                    "answer": record.answer,
                    "is_correct": record.is_correct,
                    "feedback": record.feedback,
                }
            )

        final_payload = {
            "question": session.question,
            "problem_reframed": session.plan.problem_reframed,
            "final_answer_reference": session.plan.final_answer,
            "big_picture": session.plan.big_picture,
            "steps": [asdict(step) for step in session.plan.steps],
            "history": history_payload,
        }
        return self._client.create_structured_response(
            schema_name="final_feedback",
            schema=FINAL_FEEDBACK_SCHEMA,
            input_messages=[
                {"role": "developer", "content": developer_prompt},
                {"role": "user", "content": json.dumps(final_payload, ensure_ascii=False)},
            ],
        )

    def _serialize_step(
        self, step: TutorStep, step_index: int, total_steps: int
    ) -> dict[str, Any]:
        return {
            "title": step.title,
            "goal": step.goal,
            "prompt": step.child_prompt,
            "stepNumber": step_index + 1,
            "totalSteps": total_steps,
        }

    def _serialize_history(self, session: TutorSession) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for record in session.history:
            items.append(
                {
                    "stepIndex": record.step_index,
                    "answer": record.answer,
                    "isCorrect": record.is_correct,
                    "feedback": record.feedback,
                    "hint": record.hint,
                    "timestamp": record.timestamp,
                }
            )
        return items
