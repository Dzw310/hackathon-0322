from __future__ import annotations

import unittest

from tutor_app.tutor_service import TutorService


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
                "problem_reframed": "先把题目拆成容易想的小块。",
                "encouraging_intro": "我们先从第一小步开始。",
                "final_answer": "每人 4 颗。",
                "big_picture": "平均分就是把总数按人数均匀分开。",
                "celebration": "你一步一步完成了。",
                "steps": [
                    {
                        "title": "看清总数",
                        "goal": "先找到一共有多少颗糖。",
                        "child_prompt": "题目里总共有多少颗糖？",
                        "success_criteria": ["说出总数是 12"],
                        "hint_ladder": ["去题目里找总数。", "一开始写着 12 颗糖。"],
                        "ideal_student_answer": "12 颗糖",
                        "encouragement_if_correct": "对，先找到总数很重要。",
                        "mini_explanation": "总数是后面平均分的起点。",
                    },
                    {
                        "title": "平均分",
                        "goal": "把 12 平均分给 3 个朋友。",
                        "child_prompt": "12 平均分成 3 份，每份是多少？",
                        "success_criteria": ["说出 12 除以 3 等于 4"],
                        "hint_ladder": ["试试看 12 ÷ 3。", "可以想 3 个 4 加起来是 12。"],
                        "ideal_student_answer": "每人 4 颗",
                        "encouragement_if_correct": "很好，你算出了每份是多少。",
                        "mini_explanation": "平均分常常就是用除法。",
                    },
                ],
            }

        if schema_name == "step_evaluation":
            self.evaluate_calls += 1
            if self.evaluate_calls == 1:
                return {
                    "is_correct": False,
                    "confidence": 0.2,
                    "feedback_to_child": "先再看看题目里的数字。",
                    "next_hint": "题目一开始就告诉了糖的总数。",
                    "mini_explanation": "这一步只要先确认总数。",
                    "observed_strength": "你已经开始读题了。",
                }
            return {
                "is_correct": True,
                "confidence": 0.9,
                "feedback_to_child": "这一步答对了。",
                "next_hint": "",
                "mini_explanation": "继续往下想。",
                "observed_strength": "你抓住了关键点。",
            }

        if schema_name == "final_feedback":
            return {
                "summary_title": "完成啦",
                "celebration": "你通过自己的思考完成了这道题。",
                "final_answer": "每人 4 颗。",
                "strengths": ["会先找总数", "能把平均分和除法联系起来"],
                "next_time_tips": ["先圈出题目数字", "看到平均分时先想除法"],
                "step_recap": [
                    {
                        "title": "看清总数",
                        "learner_answered": "最后说出了总数是 12。",
                        "feedback": "这一步抓住了读题重点。",
                    },
                    {
                        "title": "平均分",
                        "learner_answered": "算出每人 4 颗。",
                        "feedback": "能够把平均分转成除法。",
                    },
                ],
            }

        raise AssertionError(f"Unexpected schema name: {schema_name}")


class TutorServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = TutorService(client=FakeStructuredClient())

    def test_create_session_returns_first_step(self) -> None:
        result = self.service.create_session("12 颗糖分给 3 个朋友，每人几颗？")
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["currentStep"]["stepNumber"], 1)
        self.assertEqual(result["totalSteps"], 2)

    def test_submit_answer_retries_then_completes(self) -> None:
        session = self.service.create_session("12 颗糖分给 3 个朋友，每人几颗？")
        session_id = session["sessionId"]

        retry = self.service.submit_answer(session_id, "我不知道")
        self.assertEqual(retry["status"], "try_again")
        self.assertIn("总数", retry["hint"])

        advance = self.service.submit_answer(session_id, "12 颗")
        self.assertEqual(advance["status"], "step_advanced")
        self.assertEqual(advance["currentStep"]["stepNumber"], 2)

        completed = self.service.submit_answer(session_id, "每人 4 颗")
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["summary"]["final_answer"], "每人 4 颗。")

    def test_rejects_empty_question(self) -> None:
        with self.assertRaises(ValueError):
            self.service.create_session("   ")


if __name__ == "__main__":
    unittest.main()
