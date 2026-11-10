from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(BASE_DIR / ".env"), str(BASE_DIR / ".env.local")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "SmartVOCAB AI"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    MONGO_URI: str = ""
    MONGO_DB_NAME: str = "capstone1"
    MONGO_TIMEOUT_MS: int = 10000

    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.8-flash"
    GEMINI_RPM: int = 10

    CF_ACCOUNT_ID: str = ""
    CF_API_TOKEN: str = ""
    CF_MODEL: str = "@cf/meta/llama-3.1-8b-instruct"
    CF_RPM: int = 30

    DICTIONARY_RPM: int = 30

    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:5174",
    ]

    MASTERY_CORRECT_GAIN: float = 10.0
    MASTERY_WRONG_PENALTY: float = 5.0
    MASTERY_HINT_FACTOR: float = 0.5
    MASTERY_FAST_BONUS: float = 2.0
    MASTERY_FAST_MS: int = 4000
    MASTERY_THRESHOLD: float = 80.0

    SESSION_MAX_QUESTIONS: int = 20
    MIN_LESSON_WORDS: int = 4

    @model_validator(mode="after")
    def _require_mongo_uri(self) -> "Settings":
        uri = self.MONGO_URI.strip()

        if not uri:
            raise ValueError(
                "Chua cau hinh MONGO_URI. Hay dien connection string "
                "trong backend/.env."
            )

        if "<" in uri or ">" in uri:
            raise ValueError(
                "MONGO_URI van con placeholder. Hay thay bang URI that."
            )

        return self

    @property
    def mongo_target(self) -> str:
        return f"{mask_mongo_uri(self.MONGO_URI)} | db={self.MONGO_DB_NAME}"


def mask_mongo_uri(uri: str) -> str:
    if "@" not in uri:
        return uri

    scheme, rest = uri.split("://", 1)
    credentials, host = rest.rsplit("@", 1)
    user = credentials.split(":", 1)[0]

    return f"{scheme}://{user}:***@{host}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()