from datetime import datetime
from pydantic import BaseModel, Field


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
    correct: bool


class QuizQuestion(BaseModel):
    vocabulary_id: str
    question: str
    question_type: str
    options: list[str]
    answer: str


class QuizResultItem(BaseModel):
    vocabulary_id: str
    correct: bool
    correct_answer: str
    user_answer: str = ""


class QuizSubmit(BaseModel):
    lesson_id: str | None = None
    results: list[QuizResultItem]


class QuizResultOut(BaseModel):
    correct: int
    total: int
    percent: int
    xp_gained: int
    passed: bool
    new_level: int
    new_xp: int
    streak: int
