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
            raise ValueError("问题不能为空。")

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
            raise ValueError("请先输入你的想法。")

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
            raise KeyError("没有找到对应的学习会话。")
        return session

    def _generate_plan(self, question: str) -> LearningPlan:
        developer_prompt = (
            "你是一个面向儿童的启发式导师。"
            "你的任务不是直接把答案讲完，而是把问题拆成 2 到 6 个可互动的小步骤。"
            "每一步都要让孩子先思考再作答。"
            "语言要温柔、具体、鼓励，但不能幼稚。"
            "不要在 child_prompt 里泄露最终答案。"
            "success_criteria 要描述这一小步答对时应包含的关键信息。"
            "hint_ladder 要从轻提示到更具体提示逐渐增强。"
            "ideal_student_answer 要简洁，方便后续判题。"
        )
        user_payload = {
            "learner_question": question,
            "requirements": [
                "适合中文场景",
                "一步只问一个核心点",
                "鼓励孩子自己发现规律",
                "最终要能汇总完整思路和答案",
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
            "你在给儿童学习产品做逐步判题。"
            "请根据当前步骤的 success_criteria 判断孩子是否已经答到位。"
            "如果语义正确、表达不完整但核心对了，可以判为正确。"
            "如果错误，不要直接公布完整答案，优先给轻量提示。"
            "第 1 次答错时使用 hint_ladder 的前一个提示。"
            "连续答错时可以给更具体提示，但依然要鼓励思考。"
            "feedback_to_child 要直接对孩子说话，简短、积极、明确。"
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
            "你在给孩子做学习总结。"
            "请先庆祝努力，再用简洁语言回顾步骤，最后给出完整答案和改进建议。"
            "step_recap 中 learner_answered 要概括孩子在该步的表现。"
            "feedback 要指出这一小步做得好的地方或还需巩固的地方。"
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

