"""Shared test harness.

The test database is selected *before* importing the application so the app can
never touch the shared/production database. Tests are skipped (not failed) when
MongoDB is unreachable, because CI may not have Atlas credentials.
"""
from __future__ import annotations

import os
import unittest
import uuid
from datetime import datetime, timezone

os.environ["MONGO_DB_NAME"] = "capstone1_mvp_test"
os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-production")
os.environ.setdefault("JWT_ALGORITHM", "HS256")

import httpx  # noqa: E402
from bson import ObjectId  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db import mongodb  # noqa: E402
from app.main import app  # noqa: E402
from app.services.domain_service import ensure_domains  # noqa: E402

COLLECTIONS = (
    "users",
    "domains",
    "lessons",
    "vocabularies",
    "exercise_items",
    "learning_sessions",
    "answer_attempts",
    "user_word_states",
    "lesson_progress",
    "fsrs_review_logs",
    "quiz_questions",
    "flashcard_progress",
)

async def ensure_connection() -> None:
    if "test" not in settings.MONGO_DB_NAME.lower():
        raise unittest.SkipTest(
            f"Refusing to run tests against non-test database {settings.MONGO_DB_NAME!r}"
        )
    if mongodb.db is not None:
        return
    try:
        await mongodb.connect_to_mongo()
    except Exception as exc:  # pragma: no cover - environment dependent
        raise unittest.SkipTest(f"MongoDB is not reachable: {exc}") from exc


async def reset_database() -> None:
    await ensure_connection()
    db = mongodb.get_database()
    for name in COLLECTIONS:
        await db[name].delete_many({})
    await ensure_domains()


SAMPLE_WORDS = [
    ("apple", "quả táo", "She eats an apple every morning.", "general", "A1"),
    ("book", "quyển sách", "I read a book before bed.", "general", "A1"),
    ("chair", "cái ghế", "Please sit on this chair.", "general", "A1"),
    ("water", "nước", "Drink more water every day.", "general", "A1"),
    ("family", "gia đình", "My family lives in Hanoi.", "general", "A1"),
    ("school", "trường học", "The children walk to school together.", "general", "A1"),
    ("browser", "trình duyệt", "Open the link in your browser.", "technology", "A2"),
    ("keyboard", "bàn phím", "She typed the code on a new keyboard.", "technology", "A2"),
    ("invoice", "hóa đơn", "Please send the invoice to the client.", "business", "A2"),
    ("receipt", "biên lai", "Keep the receipt for your expense report.", "business", "A2"),
]


async def seed_vocabulary() -> list[dict]:
    await ensure_connection()
    db = mongodb.get_database()
    now = datetime.now(timezone.utc)
    docs = []
    for word, meaning, example, domain, level in SAMPLE_WORDS:
        docs.append(
            {
                "_id": ObjectId(),
                "word": word,
                "word_key": word.casefold(),
                "phonetic": "",
                "part_of_speech": "noun",
                "meaning": meaning,
                "meaning_key": meaning.casefold(),
                "example": example,
                "synonyms": [],
                "antonyms": [],
                "topic": domain,
                "domain": domain,
                "level": level,
                "created_at": now,
                "updated_at": now,
            }
        )
    await db.vocabularies.insert_many(docs)
    return docs


class ApiTestCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        await reset_database()
        self.vocab = await seed_vocabulary()
        transport = httpx.ASGITransport(app=app)
        self.client = httpx.AsyncClient(transport=transport, base_url="http://test")
        self.email = f"user-{uuid.uuid4().hex[:10]}@example.com"

    async def asyncTearDown(self) -> None:
        if getattr(self, "client", None) is not None:
            await self.client.aclose()
        await mongodb.close_mongo_connection()

    async def register(self, email: str | None = None, password: str = "secret123"):
        email = email or self.email
        response = await self.client.post(
            "/auth/register",
            json={"email": email, "username": "tester", "password": password},
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    async def auth_headers(self, email: str | None = None) -> dict:
        payload = await self.register(email)
        return {"Authorization": f"Bearer {payload['access_token']}"}

    async def make_admin(self, email: str | None = None) -> dict:
        email = email or self.email
        payload = await self.register(email)
        await mongodb.get_database().users.update_one(
            {"_id": email}, {"$set": {"role": "admin"}}
        )
        return {"Authorization": f"Bearer {payload['access_token']}"}

    def vocab_id(self, word: str) -> str:
        for doc in self.vocab:
            if doc["word"] == word:
                return str(doc["_id"])
        raise KeyError(word)
