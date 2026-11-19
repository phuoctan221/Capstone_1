from datetime import datetime

from pydantic import BaseModel, Field

from app.models.exercise import ExerciseItemOut


class AssessmentCreate(BaseModel):
    domain: str
    level: str = Field(..., pattern="^(A1|A2|B1|B2|C1|C2)$")
    skip_learning: bool = False
    placement_target: str | None = Field(None, pattern="^(A1|A2|B1|B2|C1|C2)$")


class AssessmentSubmitAnswer(BaseModel):
    exercise_item_id: str
    answer: str = ""


class AssessmentSubmit(BaseModel):
    answers: list[AssessmentSubmitAnswer] = Field(min_length=1, max_length=50)


class AssessmentOut(BaseModel):
    attempt_id: str
    domain: str
    level: str
    question_count: int
    expires_at: datetime
    questions: list[ExerciseItemOut]