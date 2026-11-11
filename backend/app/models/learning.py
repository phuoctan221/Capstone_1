from datetime import datetime
from pydantic import BaseModel, Field


class FlashcardProgress(BaseModel):
    user_id: str
    vocabulary_id: str
    box: int = Field(1, ge=1, le=5)
    correct_count: int = 0
    wrong_count: int = 0
    next_review: datetime
    last_reviewed: datetime | None = None


class ReviewRequest(BaseModel):
    vocabulary_id: str
    remembered: bool


class ReviewStats(BaseModel):
    total_words: int
    mastered: int
    learning: int
    due_today: int


# New Core/MVP schemas; legacy FlashcardProgress is intentionally retained.
from typing import Literal
from uuid import uuid4


class MasteryScores(BaseModel):
    meaning: float = Field(0, ge=0, le=100)
    spelling: float = Field(0, ge=0, le=100)
    context: float = Field(0, ge=0, le=100)


class FSRSState(BaseModel):
    card_json: str | None = None
    card_id: int | None = None
    state: int | None = None
    step: int | None = None
    difficulty: float | None = None
    stability: float | None = None
    due_at: datetime | None = None
    last_reviewed_at: datetime | None = None


class UserWordState(BaseModel):
    user_id: str
    vocabulary_id: str
    mastery: MasteryScores = Field(default_factory=MasteryScores)
    fsrs: FSRSState = Field(default_factory=FSRSState)
    review_count: int = 0
    started_at: datetime | None = None
    updated_at: datetime | None = None


class FSRSReviewRequest(BaseModel):
    vocabulary_id: str
    rating: Literal[1, 2, 3, 4] | None = None
    # Backwards compatible with the existing two-button flashcard UI.
    remembered: bool | None = None
    review_id: str = Field(default_factory=lambda: str(uuid4()))
