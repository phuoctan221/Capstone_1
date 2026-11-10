from datetime import datetime
from pydantic import BaseModel, Field
from typing import Literal
from uuid import uuid4


class Lesson(BaseModel):
    id: str
    slug: str
    title: str
    topic: str
    level: str
    description: str = ""
    word_count: int = 0
    order: int = 0


class LessonDetail(Lesson):
    words: list[dict] = []


class LessonSummary(Lesson):
    learned_count: int = 0
    progress_percent: int = 0
    completed: bool = False


class LessonCreate(BaseModel):
    domain: str = Field(..., pattern="^(general|technology|business)$")
    level: str = Field(..., pattern="^(A1|A2|B1|B2|C1|C2)$")
    title: str | None = None
    description: str | None = None
    order: int = 0


class LessonUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    order: int | None = None


class UserProgressOut(BaseModel):
    xp: int = 0
    level: int = 1
    streak: int = 0
    last_study_date: datetime | None = None
    words_learned: int = 0
    words_mastered: int = 0
    lessons_completed: int = 0


class StudyMode(BaseModel):
    mode: str = Field(..., pattern="^(quiz|typing|listening|flashcard)$")


class StudyAnswer(BaseModel):
    vocabulary_id: str
    answer: str = ""
    skill: Literal["meaning", "spelling", "context", "listening"] = "meaning"
    attempt_id: str = Field(default_factory=lambda: str(uuid4()))
    response_time_ms: int = Field(0, ge=0, le=600000)
    hint_used: bool = False
    # Legacy clients may still send correct; backend ignores it.
    correct: bool | None = None


class QuizQuestion(BaseModel):
    vocabulary_id: str
    question: str
    question_type: str
    options: list[str]
    answer: str


class QuizResultItem(BaseModel):
    vocabulary_id: str
    question_token: str
    user_answer: str = ""
    response_time_ms: int = Field(0, ge=0, le=600000)
    hint_used: bool = False

class QuizSubmit(BaseModel):
    lesson_id: str | None = None
    results: list[QuizResultItem]


class QuizResultDetailItem(BaseModel):
    vocabulary_id: str
    question: str = ""
    options: list[str] = []
    correct: bool
    correct_answer: str
    user_answer: str = ""
    word: str | None = None
    phonetic: str | None = None
    meaning: str | None = None
    example: str | None = None


class QuizResultOut(BaseModel):
    correct: int
    total: int
    percent: int
    xp_gained: int
    passed: bool
    new_level: int
    new_xp: int
    streak: int
    results: list[QuizResultDetailItem] = []
    wrong_count: int = 0


class MistakeAnalysisRequest(BaseModel):
    vocabulary_id: str | None = None
    question: str
    correct_answer: str
    user_answer: str


class MistakeAnalysisOut(BaseModel):
    error_type: str
    what_went_wrong: str
    explanation: str
    correct_answer: str
    example: str | None = None
    tip: str | None = None


class BatchMistakeAnalysisRequest(BaseModel):
    mistakes: list[MistakeAnalysisRequest]
