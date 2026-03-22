from __future__ import annotations


LEARNING_PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "problem_reframed": {"type": "string"},
        "encouraging_intro": {"type": "string"},
        "final_answer": {"type": "string"},
        "big_picture": {"type": "string"},
        "celebration": {"type": "string"},
        "steps": {
            "type": "array",
            "minItems": 2,
            "maxItems": 6,
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "goal": {"type": "string"},
                    "child_prompt": {"type": "string"},
                    "success_criteria": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 4,
                        "items": {"type": "string"},
                    },
                    "hint_ladder": {
                        "type": "array",
                        "minItems": 2,
                        "maxItems": 3,
                        "items": {"type": "string"},
                    },
                    "ideal_student_answer": {"type": "string"},
                    "encouragement_if_correct": {"type": "string"},
                    "mini_explanation": {"type": "string"},
                },
                "required": [
                    "title",
                    "goal",
                    "child_prompt",
                    "success_criteria",
                    "hint_ladder",
                    "ideal_student_answer",
                    "encouragement_if_correct",
                    "mini_explanation",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": [
        "problem_reframed",
        "encouraging_intro",
        "final_answer",
        "big_picture",
        "celebration",
        "steps",
    ],
    "additionalProperties": False,
}


STEP_EVALUATION_SCHEMA = {
    "type": "object",
    "properties": {
        "is_correct": {"type": "boolean"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "feedback_to_child": {"type": "string"},
        "next_hint": {"type": "string"},
        "mini_explanation": {"type": "string"},
        "observed_strength": {"type": "string"},
    },
    "required": [
        "is_correct",
        "confidence",
        "feedback_to_child",
        "next_hint",
        "mini_explanation",
        "observed_strength",
    ],
    "additionalProperties": False,
}


LEARNING_SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "overall_assessment": {"type": "string"},
        "domain_insights": {
            "type": "array",
            "minItems": 1,
            "maxItems": 5,
            "items": {
                "type": "object",
                "properties": {
                    "domain": {"type": "string"},
                    "observation": {"type": "string"},
                    "suggestion": {"type": "string"},
                },
                "required": ["domain", "observation", "suggestion"],
                "additionalProperties": False,
            },
        },
        "high_level_lessons": {
            "type": "array",
            "minItems": 2,
            "maxItems": 5,
            "items": {"type": "string"},
        },
        "encouragement": {"type": "string"},
    },
    "required": [
        "overall_assessment",
        "domain_insights",
        "high_level_lessons",
        "encouragement",
    ],
    "additionalProperties": False,
}


FINAL_FEEDBACK_SCHEMA = {
    "type": "object",
    "properties": {
        "summary_title": {"type": "string"},
        "celebration": {"type": "string"},
        "final_answer": {"type": "string"},
        "strengths": {
            "type": "array",
            "minItems": 2,
            "maxItems": 4,
            "items": {"type": "string"},
        },
        "next_time_tips": {
            "type": "array",
            "minItems": 2,
            "maxItems": 4,
            "items": {"type": "string"},
        },
        "step_recap": {
            "type": "array",
            "minItems": 2,
            "maxItems": 6,
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "learner_answered": {"type": "string"},
                    "feedback": {"type": "string"},
                },
                "required": ["title", "learner_answered", "feedback"],
                "additionalProperties": False,
            },
        },
    },
    "required": [
        "summary_title",
        "celebration",
        "final_answer",
        "strengths",
        "next_time_tips",
        "step_recap",
    ],
    "additionalProperties": False,
}

