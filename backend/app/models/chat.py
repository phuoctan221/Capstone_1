from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatHistoryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=1000)


class ChatContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: str = Field("dashboard", min_length=1, max_length=80)


class ChatMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(..., min_length=1, max_length=1200)
    history: list[ChatHistoryItem] = Field(default_factory=list, max_length=8)
    context: ChatContext = Field(default_factory=ChatContext)


class ChatMessageResponse(BaseModel):
    message: str
    suggestions: list[str] = Field(default_factory=list)