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

        raise AssertionError(f"Unexpected schema name: {schema_name}")


class TutorServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = TutorService(client=FakeStructuredClient())

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


if __name__ == "__main__":
    unittest.main()
