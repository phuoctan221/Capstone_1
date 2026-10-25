from datetime import datetime
from pydantic import BaseModel, Field


class VocabularyBase(BaseModel):
    word: str = Field(..., min_length=1, max_length=100)
    phonetic: str = ""
    part_of_speech: str = ""
    meaning: str = Field(..., min_length=1)
    example: str = ""
    synonyms: list[str] = []
    antonyms: list[str] = []
    topic: str = "general"
    level: str = Field("A1", pattern="^(A1|A2|B1|B2|C1|C2)$")


class VocabularyCreate(VocabularyBase):
    pass


class VocabularyUpdate(BaseModel):
    word: str | None = None
    phonetic: str | None = None
    part_of_speech: str | None = None
    meaning: str | None = None
    example: str | None = None
    synonyms: list[str] | None = None
    antonyms: list[str] | None = None
    topic: str | None = None
    level: str | None = None


class VocabularyOut(VocabularyBase):
    id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AIGenerateRequest(BaseModel):
    word: str
    target_language: str = "vi"


class AIGenerateResponse(BaseModel):
    word: str
    phonetic: str
    part_of_speech: str
    meaning: str
    example: str
    synonyms: list[str]
    antonyms: list[str]
    topic: str
    level: str


class AIBatchRequest(BaseModel):
    words: list[str] = Field(default_factory=list, max_length=30)
    topic: str = "general"
    level: str = Field("B1", pattern="^(A1|A2|B1|B2|C1|C2)$")
    count: int = Field(10, ge=1, le=30)
    save: bool = True
    target_language: str = "vi"


class AIBatchItem(BaseModel):
    word: str
    ok: bool
    saved: bool = False
    data: AIGenerateResponse | None = None
    error: str | None = None


class AIBatchResponse(BaseModel):
    requested: int
    succeeded: int
    failed: int
    saved: int
    items: list[AIBatchItem]
