from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StoryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic: Literal["daily", "work", "travel", "school", "technology"] = "daily"
    tone: Literal["warm", "funny", "serious", "adventure"] = "warm"
    vocabulary_ids: list[str] = Field(min_length=1, max_length=7)

    @field_validator("vocabulary_ids")
    @classmethod
    def unique_ids(cls, value):
        if len(set(value)) != len(value):
            raise ValueError("Mỗi từ chỉ được chọn một lần.")
        return value


class StoryQuestion(BaseModel):
    question: str = Field(min_length=5, max_length=400)
    options: list[str] = Field(min_length=4, max_length=4)
    answer: int = Field(ge=0, le=3)
    explanation: str = Field(min_length=5, max_length=600)

    @field_validator("options")
    @classmethod
    def valid_options(cls, values):
        if any(not v.strip() or len(v) > 300 for v in values) or len(set(values)) != 4:
            raise ValueError("Question options must be distinct and nonempty")
        return values


class GeneratedStory(BaseModel):
    title: str = Field(min_length=3, max_length=150)
    paragraphs: list[str] = Field(min_length=2, max_length=6)
    translation: list[str] = Field(min_length=2, max_length=6)
    questions: list[StoryQuestion] = Field(min_length=3, max_length=3)

    @field_validator("paragraphs", "translation")
    @classmethod
    def valid_paragraphs(cls, values):
        if any(not value.strip() or len(value) > 2000 for value in values):
            raise ValueError("Invalid paragraph")
        return values


class StoryAnswers(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answers: list[int] = Field(min_length=3, max_length=3)

    @field_validator("answers")
    @classmethod
    def valid_answers(cls, values):
        if any(value not in range(4) for value in values):
            raise ValueError("Chọn một đáp án cho mỗi câu hỏi.")
        return values
