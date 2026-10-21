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
