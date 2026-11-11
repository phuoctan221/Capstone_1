"""Per-user word state: Mastery + FSRS review queue.

A state is created when a learner actually starts a word (learning session or
an explicit review/migration). ``GET /learning/due`` never creates states for
the whole catalogue; it only returns already-started words that are due.
"""
from __future__ import annotations

from datetime import datetime, timezone

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.core.config import settings
from app.db.mongodb import get_database
from app.services.db_tx import run_in_transaction
from app.services.fsrs_service import (
    current_retrievability,
    new_card_state,
    schedule_review,
)
from app.services.mastery_service import DEFAULT_MASTERY

COLLECTION = "user_word_states"
VALID_TOPICS = ("general", "technology", "business")


def _new_state(user_id: str, vocabulary_id: str, now: datetime) -> dict:
    return {
        "user_id": user_id,
        "vocabulary_id": vocabulary_id,
        "mastery": dict(DEFAULT_MASTERY),
        "fsrs": new_card_state(now),
        "review_count": 0,
        "started_at": now,
        "updated_at": now,
    }


def _serialize(doc: dict) -> dict:
    result = dict(doc)
    result["id"] = str(result.pop("_id"))
    return result


async def ensure_state(user_id: str, vocabulary_id: str) -> dict:
    """Create the initial state if the learner has not started this word."""
    db = get_database()
    now = datetime.now(timezone.utc)
    try:
        await db[COLLECTION].update_one(
            {"user_id": user_id, "vocabulary_id": vocabulary_id},
            {"$setOnInsert": _new_state(user_id, vocabulary_id, now)},
            upsert=True,
        )
    except DuplicateKeyError:
        pass
    doc = await db[COLLECTION].find_one(
        {"user_id": user_id, "vocabulary_id": vocabulary_id}
    )
    return _serialize(doc)


async def get_or_create_progress(user_id: str, vocabulary_id: str) -> dict:
    return await ensure_state(user_id, vocabulary_id)


async def review_card(
    user_id: str, vocabulary_id: str, rating: int, review_id: str
) -> dict:
    if not ObjectId.is_valid(vocabulary_id):
        raise ValueError("Invalid vocabulary id")
    if rating not in (1, 2, 3, 4):
        raise ValueError("Invalid FSRS rating")
    if not review_id or len(review_id) > 100:
        raise ValueError("Invalid review id")

    db = get_database()
    vocabulary = await db.vocabularies.find_one({"_id": ObjectId(vocabulary_id)})
    if not vocabulary:
        raise ValueError("Vocabulary not found")

    earlier = await db.fsrs_review_logs.find_one({"review_id": review_id})
    if earlier:
        if (
            earlier.get("user_id") != user_id
            or earlier.get("vocabulary_id") != vocabulary_id
        ):
            raise ValueError("Review ID was used for another review")
        current = await db[COLLECTION].find_one(
            {"user_id": user_id, "vocabulary_id": vocabulary_id}
        )
        return _with_retrievability(current)

    now = datetime.now(timezone.utc)

    async def work(session):
        selector = {"user_id": user_id, "vocabulary_id": vocabulary_id}
        doc = await db[COLLECTION].find_one(selector, session=session)
        old = doc or _new_state(user_id, vocabulary_id, now)
        calculated = schedule_review(old["fsrs"].get("card_json"), rating, now)
        await db[COLLECTION].update_one(
            selector,
            {
                "$set": {"fsrs": calculated["state"], "updated_at": now},
                "$setOnInsert": {
                    "mastery": dict(DEFAULT_MASTERY),
                    "user_id": user_id,
                    "vocabulary_id": vocabulary_id,
                    "started_at": now,
                },
                "$inc": {"review_count": 1},
            },
            upsert=True,
            session=session,
        )
        await db.fsrs_review_logs.insert_one(
            {
                "review_id": review_id,
                "user_id": user_id,
                "vocabulary_id": vocabulary_id,
                "rating": rating,
                "reviewed_at": now,
                "review_log_json": calculated["log_json"],
                "retrievability": calculated["retrievability"],
            },
            session=session,
        )

    try:
        await run_in_transaction(db, work)
    except DuplicateKeyError:
        existing = await db.fsrs_review_logs.find_one({"review_id": review_id})
        if (
            not existing
            or existing.get("user_id") != user_id
            or existing.get("vocabulary_id") != vocabulary_id
        ):
            raise

    latest = await db[COLLECTION].find_one(
        {"user_id": user_id, "vocabulary_id": vocabulary_id}
    )
    return _with_retrievability(latest)


def _with_retrievability(doc: dict | None) -> dict:
    if not doc:
        return {}
    result = _serialize(doc)
    result["retrievability"] = current_retrievability(
        doc.get("fsrs", {}).get("card_json")
    )
    return result


async def get_due_cards(user_id: str, limit: int = 100) -> list[dict]:
    """Only already-started words whose FSRS due date has passed."""
    db = get_database()
    now = datetime.now(timezone.utc)
    cursor = (
        db[COLLECTION]
        .find({"user_id": user_id, "fsrs.due_at": {"$lte": now}})
        .sort("fsrs.due_at", 1)
        .limit(limit)
    )
    states = [doc async for doc in cursor]
    if not states:
        return []

    vocab_ids = [
        ObjectId(doc["vocabulary_id"])
        for doc in states
        if ObjectId.is_valid(doc.get("vocabulary_id", ""))
    ]
    vocab_map = {
        str(v["_id"]): v
        async for v in db.vocabularies.find({"_id": {"$in": vocab_ids}})
    }

    cards = []
    for doc in states:
        result = _with_retrievability(doc)
        vocab = vocab_map.get(doc["vocabulary_id"], {})
        result.update(
            {
                "word": vocab.get("word", ""),
                "meaning": vocab.get("meaning", ""),
                "phonetic": vocab.get("phonetic", ""),
                "example": vocab.get("example", ""),
                "domain": vocab.get("domain") or vocab.get("topic", "general"),
                "level": vocab.get("level", "A1"),
            }
        )
        cards.append(result)
    return cards


async def get_stats(user_id: str) -> dict:
    db = get_database()
    now = datetime.now(timezone.utc)
    total = await db[COLLECTION].count_documents({"user_id": user_id})
    mastered = await db[COLLECTION].count_documents(
        {
            "user_id": user_id,
            "mastery.meaning": {"$gte": settings.MASTERY_THRESHOLD},
            "mastery.spelling": {"$gte": settings.MASTERY_THRESHOLD},
            "mastery.context": {"$gte": settings.MASTERY_THRESHOLD},
        }
    )
    due = await db[COLLECTION].count_documents(
        {"user_id": user_id, "fsrs.due_at": {"$lte": now}}
    )
    return {
        "total_words": total,
        "mastered": mastered,
        "learning": total - mastered,
        "due_today": due,
    }
