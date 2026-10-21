from datetime import datetime, timezone

from app.db.mongodb import get_database

VOCAB = "vocabularies"
PROGRESS = "flashcard_progress"
LESSON_PROGRESS = "lesson_progress"

TOPIC_LABELS = {
    "general": "Từ vựng tổng quát",
    "academic": "Học thuật",
    "business": "Kinh doanh",
    "technology": "Công nghệ",
    "science": "Khoa học",
    "daily-life": "Đời sống hằng ngày",
    "travel": "Du lịch",
}


def _slug(topic: str) -> str:
    return topic.strip().lower().replace(" ", "-")


async def list_lessons(user_id: str) -> list[dict]:
    db = get_database()

    pipeline = [
        {"$group": {"_id": "$topic", "count": {"$sum": 1}, "level": {"$first": "$level"}}},
        {"$sort": {"_id": 1}},
    ]
    topics = [t async for t in db[VOCAB].aggregate(pipeline)]

    learned_ids: set[str] = set()
    async for p in db[PROGRESS].find({"user_id": user_id, "box": {"$gte": 3}}):
        learned_ids.add(p["vocabulary_id"])

    done_lessons = set()
    async for lp in db[LESSON_PROGRESS].find({"user_id": user_id, "completed": True}):
        done_lessons.add(lp["topic"])

    lessons = []
    for order, t in enumerate(topics):
        topic = t["_id"] or "general"
        total = t["count"]
        word_ids = [
            str(v["_id"])
            async for v in db[VOCAB].find({"topic": topic}, {"_id": 1})
        ]
        learned = sum(1 for wid in word_ids if wid in learned_ids)
        lessons.append(
            {
                "id": _slug(topic),
                "slug": _slug(topic),
                "title": TOPIC_LABELS.get(topic, topic.replace("-", " ").title()),
                "topic": topic,
                "level": t["level"] or "A1",
                "description": f"{total} từ vựng chủ đề {TOPIC_LABELS.get(topic, topic)}",
                "word_count": total,
                "order": order,
                "learned_count": learned,
                "progress_percent": round(learned / total * 100) if total else 0,
                "completed": topic in done_lessons,
            }
        )
    return lessons


async def get_lesson(lesson_id: str, user_id: str) -> dict | None:
    db = get_database()
    topic = lesson_id.replace("-", " ")
    match = await db[VOCAB].find_one({"topic": lesson_id})
    if not match:
        match = await db[VOCAB].find_one({"topic": topic})
    if not match:
        return None
    topic = match["topic"]

    words = []
    async for v in db[VOCAB].find({"topic": topic}).sort("word", 1):
        words.append(
            {
                "id": str(v["_id"]),
                "word": v["word"],
                "phonetic": v.get("phonetic", ""),
                "part_of_speech": v.get("part_of_speech", ""),
                "meaning": v["meaning"],
                "example": v.get("example", ""),
                "level": v.get("level", "A1"),
            }
        )

    learned_ids = set()
    async for p in db[PROGRESS].find({"user_id": user_id, "box": {"$gte": 3}}):
        learned_ids.add(p["vocabulary_id"])
    learned = sum(1 for w in words if w["id"] in learned_ids)

    return {
        "id": _slug(topic),
        "slug": _slug(topic),
        "title": TOPIC_LABELS.get(topic, topic.replace("-", " ").title()),
        "topic": topic,
        "level": words[0]["level"] if words else "A1",
        "description": f"{len(words)} từ vựng chủ đề {TOPIC_LABELS.get(topic, topic)}",
        "word_count": len(words),
        "order": 0,
        "learned_count": learned,
        "progress_percent": round(learned / len(words) * 100) if words else 0,
        "words": words,
    }


async def seed_lessons() -> int:
    db = get_database()
    topics = await db[VOCAB].distinct("topic")
    now = datetime.now(timezone.utc)
    count = 0
    for topic in topics:
        await db["lessons"].update_one(
            {"slug": _slug(topic or "general")},
            {
                "$setOnInsert": {
                    "slug": _slug(topic or "general"),
                    "topic": topic or "general",
                    "created_at": now,
                }
            },
            upsert=True,
        )
        count += 1
    return count
