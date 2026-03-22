from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(slots=True)
class TutorStep:
    title: str
    goal: str
    child_prompt: str
    success_criteria: list[str]
    hint_ladder: list[str]
    ideal_student_answer: str
    encouragement_if_correct: str
    mini_explanation: str


@dataclass(slots=True)
class LearningPlan:
    problem_reframed: str
    encouraging_intro: str
    final_answer: str
    big_picture: str
    celebration: str
    steps: list[TutorStep]


@dataclass(slots=True)
class AttemptRecord:
    step_index: int
    answer: str
    is_correct: bool
    feedback: str
    hint: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass(slots=True)
class TutorSession:
    session_id: str
    question: str
    plan: LearningPlan
    current_step_index: int = 0
    history: list[AttemptRecord] = field(default_factory=list)
    is_complete: bool = False
    final_feedback: dict | None = None

    def attempts_for_step(self, step_index: int) -> int:
        return sum(1 for item in self.history if item.step_index == step_index)

