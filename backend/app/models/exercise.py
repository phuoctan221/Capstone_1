from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


SkillName = Literal["meaning", "spelling", "context"]


class ExerciseItemOut(BaseModel):
    """Question payload shown to the learner. Never contains the answer."""

    exercise_item_id: str
    vocabulary_id: str
    skill: SkillName
    prompt: str
    options: list[str] = []
    cloze: str | None = None
    hint: str | None = None
    level: str = "A1"
    domain: str = "general"


class SessionCreate(BaseModel):
    lesson_id: str
    skills: list[SkillName] = Field(
        default_factory=lambda: ["meaning", "spelling", "context"]
    )
    count: int = Field(10, ge=1, le=50)


class SessionOut(BaseModel):
    session_id: str
    user_id: str
    lesson_id: str
    domain: str
    level: str
    skills: list[str]
    status: str
    question_count: int
    answered_count: int = 0
    correct_count: int = 0
    started_at: datetime
    finished_at: datetime | None = None


class SessionExerciseOut(SessionOut):
    exercises: list[ExerciseItemOut]


class AnswerSubmit(BaseModel):
    exercise_item_id: str
    answer: str = ""
    attempt_id: str
    response_time_ms: int = Field(0, ge=0, le=600000)
    hint_used: bool = False
    # Explicitly rejected/ignored if a client sends these; kept out of grading.
    correct: bool | None = None
    correct_answer: str | None = None


class AnswerResult(BaseModel):
    attempt_id: str
    session_id: str
    exercise_item_id: str
    vocabulary_id: str
    skill: SkillName
    is_correct: bool
    correct_answer: str
    submitted_answer: str
    response_time_ms: int
    hint_used: bool
    error_type: str | None = None
    mastery: dict[str, float]
    xp_gained: int
    answered_at: datetime


class SessionFinishOut(BaseModel):
    session_id: str
    status: str
    total: int
    answered: int
    correct: int
    percent: int
    passed: bool
    xp_gained: int
    lesson_completed: bool
    finished_at: datetime
