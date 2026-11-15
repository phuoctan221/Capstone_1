import re

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SpeakingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    vocabulary_ids: list[str] = Field(default_factory=list, max_length=20)
    custom_words: list[str] = Field(default_factory=list, max_length=20)
    auto_select: bool = False

    @field_validator("custom_words")
    @classmethod
    def validate_words(cls, words):
        result = []
        for word in words:
            word = " ".join(word.strip().split()).replace("’", "'")
            if not re.fullmatch(r"[A-Za-z]+(?:[ '-][A-Za-z]+)*", word) or len(word) > 80:
                raise ValueError("Nhập từ/cụm từ tiếng Anh, tối đa 80 ký tự mỗi mục.")
            if word.lower() not in {w.lower() for w in result}:
                result.append(word)
        return result

