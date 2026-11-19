from datetime import datetime
from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    email: str = Field(..., pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")
    username: str = Field(..., min_length=3, max_length=30)
    password: str = Field(..., min_length=6)


class UserLogin(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: str
    email: str
    username: str
    role: str = "user"
    created_at: datetime
    learning_level: str | None = None
    placement_levels: dict[str, str] = {}
    interests: list[str] = []
    onboarded: bool = False
    daily_goal: int = 10
    daily_new_limit: int = 10
    daily_review_limit: int = 30
    xp: int = 0
    streak: int = 0
    profile_completed_at: datetime | None = None
    updated_at: datetime | None = None
    avatar_url: str | None = None


class UserProfileUpdate(BaseModel):
    username: str | None = Field(None, min_length=3, max_length=30)
    learning_level: str | None = Field(None, pattern="^(A1|A2|B1|B2|C1|C2)$")
    interests: list[str] | None = None
    daily_goal: int | None = Field(None, ge=5, le=100)
    daily_new_limit: int | None = Field(None, ge=1, le=100)
    daily_review_limit: int | None = Field(None, ge=1, le=200)
    onboarded: bool | None = None


class OnboardingRequest(BaseModel):
    learning_level: str = Field(..., pattern="^(A1|A2|B1|B2|C1|C2)$")
    interests: list[str] = Field(default_factory=list)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=6)
    new_password: str = Field(..., min_length=6)


class PasswordResetRequest(BaseModel):
    email: str = Field(..., pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")


class PasswordResetVerify(BaseModel):
    email: str = Field(..., pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")
    otp: str = Field(..., pattern=r"^\d{6}$")


class PasswordResetConfirm(PasswordResetVerify):
    new_password: str = Field(..., min_length=6)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
