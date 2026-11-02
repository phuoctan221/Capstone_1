from datetime import datetime, timedelta, timezone

from bson import ObjectId

from app.db.mongodb import get_database

COLLECTION = "flashcard_progress"

BOX_INTERVALS = {
    1: timedelta(minutes=10),
    2: timedelta(hours=1),
    3: timedelta(days=1),
    4: timedelta(days=3),
    5: timedelta(days=7),
}


async def get_or_create_progress(user_id: str, vocabulary_id: str) -> dict:
    db = get_database()
    doc = await db[COLLECTION].find_one(
        {"user_id": user_id, "vocabulary_id": vocabulary_id}
    )
    if doc is None:
        now = datetime.now(timezone.utc)
        doc = {
            "user_id": user_id,
            "vocabulary_id": vocabulary_id,
            "box": 1,
            "correct_count": 0,
            "wrong_count": 0,
            "next_review": now,
            "last_reviewed": None,
        }
        await db[COLLECTION].insert_one(doc)
    doc["id"] = str(doc.pop("_id"))
    return doc


async def review_card(user_id: str, vocabulary_id: str, remembered: bool) -> dict:
    db = get_database()
    now = datetime.now(timezone.utc)

    doc = await db[COLLECTION].find_one(
        {"user_id": user_id, "vocabulary_id": vocabulary_id}
    )
    box = (doc or {}).get("box", 1)

    if remembered:
        box = min(box + 1, 5)
        inc = {"correct_count": 1}
    else:
        box = max(box - 1, 1)
        inc = {"wrong_count": 1}

    result = await db[COLLECTION].find_one_and_update(
        {"user_id": user_id, "vocabulary_id": vocabulary_id},
        {
            "$set": {
                "box": box,
                "next_review": now + BOX_INTERVALS[box],
                "last_reviewed": now,
            },
            "$inc": inc,
        },
        upsert=True,
        return_document=True,
    )
    result["id"] = str(result.pop("_id"))
    return result


async def get_due_cards(user_id: str) -> list[dict]:
    from pymongo.errors import DuplicateKeyError

    db = get_database()
    now = datetime.now(timezone.utc)

    # Auto-enroll vocabularies that user hasn't started yet
    started = {
        doc["vocabulary_id"]
        async for doc in db[COLLECTION].find({"user_id": user_id})
    }
    new_words = []
    async for v in db["vocabularies"].find({}, {"_id": 1}).sort("created_at", -1):
        vid = str(v["_id"])
        if vid not in started:
            new_words.append(vid)

    for vid in new_words:
        try:
            await db[COLLECTION].update_one(
                {"user_id": user_id, "vocabulary_id": vid},
                {
                    "$setOnInsert": {
                        "box": 1,
                        "correct_count": 0,
                        "wrong_count": 0,
                        "next_review": now,
                        "last_reviewed": None,
                    }
                },
                upsert=True,
            )
        except DuplicateKeyError:
            pass

    cursor = db[COLLECTION].find(
        {"user_id": user_id, "next_review": {"$lte": now}}
    )
    cards = []
    async for doc in cursor:
        doc["id"] = str(doc.pop("_id"))
        cards.append(doc)
    return cards


async def get_stats(user_id: str) -> dict:
    db = get_database()
    now = datetime.now(timezone.utc)
    total = await db[COLLECTION].count_documents({"user_id": user_id})
    mastered = await db[COLLECTION].count_documents(
        {"user_id": user_id, "box": 5}
    )
    due_today = await db[COLLECTION].count_documents(
        {"user_id": user_id, "next_review": {"$lte": now}}
    )
    return {
        "total_words": total,
        "mastered": mastered,
        "learning": total - mastered,
        "due_today": due_today,
    }
