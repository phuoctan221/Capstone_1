from typing import Literal

from pydantic import BaseModel, Field

from app.models.exercise import SkillName


class RoleUpdate(BaseModel):
    role: Literal["user", "admin"]


class AdminUserUpdate(BaseModel):
    username: str | None = Field(None, min_length=3, max_length=30)
    email: str | None = Field(None, pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")
    learning_level: str | None = Field(None, pattern="^(A1|A2|B1|B2|C1|C2)$")
    interests: list[str] | None = None
    daily_goal: int | None = Field(None, ge=5, le=100)


class AdminUserStatus(BaseModel):
    is_active: bool


class DomainUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=80)
    name_vi: str | None = Field(None, min_length=1, max_length=80)
    description: str | None = Field(None, max_length=300)
    order: int | None = Field(None, ge=0, le=999)
    active: bool | None = None


class ExerciseItemCreate(BaseModel):
    vocabulary_id: str = Field(..., min_length=1)
    skill: SkillName
    prompt: str = Field(..., min_length=1, max_length=500)
    correct_answer: str = Field(..., min_length=1, max_length=300)
    options: list[str] = Field(default_factory=list)
    accepted_answers: list[str] = Field(default_factory=list)
    cloze: str | None = None
    hint: str | None = None
    active: bool = True
    exercise_item_id: str | None = Field(None, min_length=1, max_length=200)


class ExerciseItemUpdate(BaseModel):
    prompt: str | None = Field(None, min_length=1, max_length=500)
    correct_answer: str | None = Field(None, min_length=1, max_length=300)
    options: list[str] | None = None
    accepted_answers: list[str] | None = None
    cloze: str | None = None
    hint: str | None = None
    active: bool | None = None
