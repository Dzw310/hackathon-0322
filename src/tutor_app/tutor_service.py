from __future__ import annotations

import json
import threading
import uuid
from dataclasses import asdict
from typing import Any, Protocol

from tutor_app.models import AttemptRecord, LearningPlan, TutorSession, TutorStep
from tutor_app.openai_client import OpenAIResponsesClient
from tutor_app.schemas import (
    FINAL_FEEDBACK_SCHEMA,
    LEARNING_PLAN_SCHEMA,
    STEP_EVALUATION_SCHEMA,
)


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
    def __init__(self, client: StructuredLLMClient | None = None) -> None:
        self._client = client or OpenAIResponsesClient.from_env()
        self._sessions: dict[str, TutorSession] = {}
        self._lock = threading.Lock()

    def create_session(self, question: str) -> dict[str, Any]:
        clean_question = question.strip()
        if not clean_question:
            raise ValueError("Question cannot be empty.")

        plan = self._generate_plan(clean_question)
        session = TutorSession(
            session_id=uuid.uuid4().hex,
            question=clean_question,
            plan=plan,
        )

        with self._lock:
            self._sessions[session.session_id] = session

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
        }

    def submit_answer(self, session_id: str, answer: str) -> dict[str, Any]:
        clean_answer = answer.strip()
        if not clean_answer:
            raise ValueError("Please enter your answer or idea first.")

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

        if evaluation["is_correct"]:
            session.current_step_index += 1
            if session.current_step_index >= len(session.plan.steps):
                session.is_complete = True
                summary = self._generate_final_feedback(session)
                session.final_feedback = summary
                return {
                    "status": "completed",
                    "sessionId": session.session_id,
                    "message": evaluation["feedback_to_child"],
                    "miniExplanation": evaluation["mini_explanation"],
                    "summary": summary,
                    "history": self._serialize_history(session),
                }

            next_index = session.current_step_index
            next_step = session.plan.steps[next_index]
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
            }

        return {
            "status": "try_again",
            "sessionId": session.session_id,
            "message": evaluation["feedback_to_child"],
            "hint": evaluation["next_hint"],
            "miniExplanation": evaluation["mini_explanation"],
            "currentStepIndex": step_index,
            "currentStep": self._serialize_step(step, step_index, len(session.plan.steps)),
            "history": self._serialize_history(session),
        }

    def _get_session(self, session_id: str) -> TutorSession:
        with self._lock:
            session = self._sessions.get(session_id)
        if not session:
            raise KeyError("No matching learning session was found.")
        return session

    def _generate_plan(self, question: str) -> LearningPlan:
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
        )
        user_payload = {
            "learner_question": question,
            "requirements": [
                "Use English throughout the response",
                "Ask only one core idea per step",
                "Encourage the child to discover the pattern independently",
                "The final result should include the full reasoning path and answer",
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
    ) -> dict[str, Any]:
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
