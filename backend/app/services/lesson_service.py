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

LEVEL_ORDER = {"A1": 0, "A2": 1, "B1": 2, "B2": 3, "C1": 4, "C2": 5}
VALID_LEVELS = set(LEVEL_ORDER)


def _slug(topic: str, level: str | None = None) -> str:
    base = topic.strip().lower().replace(" ", "-")
    if level:
        return f"{base}-{level.lower()}"
    return base


def _parse_lesson_id(lesson_id: str) -> tuple[str, str | None]:
    if "-" in lesson_id:
        parts = lesson_id.rsplit("-", 1)
        level_cand = parts[-1].upper()
        if level_cand in VALID_LEVELS:
            return parts[0], level_cand
    return lesson_id, None


def _topic_title(topic: str) -> str:
    return TOPIC_LABELS.get(topic, topic.replace("-", " ").title())


def _word_out(v: dict) -> dict:
    return {
        "id": str(v["_id"]),
        "word": v["word"],
        "phonetic": v.get("phonetic", ""),
        "part_of_speech": v.get("part_of_speech", ""),
        "meaning": v["meaning"],
        "example": v.get("example", ""),
        "level": v.get("level", "A1"),
    }


async def _learned_ids(user_id: str) -> set[str]:
    db = get_database()
    ids: set[str] = set()
    async for p in db[PROGRESS].find({"user_id": user_id, "box": {"$gte": 3}}):
        ids.add(p["vocabulary_id"])
    return ids


def _interest_set(user: dict) -> set[str]:
    interests = user.get("interests") or []
    if isinstance(interests, str):
        interests = [interests]
    return {str(i).strip().lower() for i in interests if i}


async def list_lessons(user_id: str) -> list[dict]:
    db = get_database()

    user = await db["users"].find_one({"_id": user_id}) or {}
    interest_set = _interest_set(user)
    user_level = user.get("learning_level")

    pipeline = [
        {
            "$group": {
                "_id": {"topic": "$topic", "level": "$level"},
                "count": {"$sum": 1},
            }
        },
        {"$sort": {"_id.topic": 1, "_id.level": 1}},
    ]
    groups = [g async for g in db[VOCAB].aggregate(pipeline)]

    learned_ids = await _learned_ids(user_id)

    # Gom nhóm theo topic, mỗi topic gồm các level đã có dữ liệu
    by_topic: dict[str, list[dict]] = {}
    for g in groups:
        topic = g["_id"].get("topic") or "general"
        if interest_set and topic.lower() not in interest_set:
            continue
        level = g["_id"].get("level") or "A1"
        total = g["count"]
        word_ids = [
            str(v["_id"])
            async for v in db[VOCAB].find(
                {"topic": topic, "level": level}, {"_id": 1}
            )
        ]
        learned = sum(1 for wid in word_ids if wid in learned_ids)
        by_topic.setdefault(topic, []).append(
            {
                "topic": topic,
                "level": level,
                "total": total,
                "learned": learned,
                "completed": total > 0 and learned >= total,
            }
        )

    lessons: list[dict] = []
    for topic, items in by_topic.items():
        items.sort(key=lambda x: LEVEL_ORDER.get(x["level"], 99))

        # Bắt đầu từ trình độ của người học (nếu có trong topic), nếu không thì từ thấp nhất
        levels = [i["level"] for i in items]
        start = 0
        if user_level in levels:
            start = levels.index(user_level)

        ordered = items[start:] + items[:start]

        prev_completed = True if start == 0 else items[start - 1]["completed"]
        for idx, item in enumerate(ordered):
            level = item["level"]
            is_current = user_level == level
            if idx == 0:
                unlocked = True if start == 0 else prev_completed
            else:
                unlocked = ordered[idx - 1]["completed"]
            lessons.append(
                {
                    "id": _slug(topic, level),
                    "slug": _slug(topic, level),
                    "title": f"{_topic_title(topic)} - {level}",
                    "topic": topic,
                    "topic_title": _topic_title(topic),
                    "level": level,
                    "description": f"{item['total']} từ vựng {_topic_title(topic)} cấp độ {level}",
                    "word_count": item["total"],
                    "order": 0,
                    "learned_count": item["learned"],
                    "progress_percent": round(item["learned"] / item["total"] * 100)
                    if item["total"]
                    else 0,
                    "completed": item["completed"],
                    "recommended": is_current,
                    "unlocked": unlocked,
                }
            )

    for i, l in enumerate(lessons):
        l["order"] = i
    return lessons


async def get_lesson(lesson_id: str, user_id: str) -> dict | None:
    db = get_database()
    topic_slug, level = _parse_lesson_id(lesson_id)

    # Tìm topic thật trong dữ liệu (hỗ trợ cả "daily-life" và "daily life")
    topic_options = [topic_slug, topic_slug.replace("-", " ")]
    match = None
    for candidate in topic_options:
        query = {"topic": candidate}
        if level:
            query["level"] = level
        match = await db[VOCAB].find_one(query)
        if match:
            break
    if not match:
        return None

    topic = match["topic"]
    level = match.get("level", level or "A1")

    words = []
    async for v in db[VOCAB].find({"topic": topic, "level": level}).sort("word", 1):
        words.append(_word_out(v))

    learned_ids = await _learned_ids(user_id)
    learned = sum(1 for w in words if w["id"] in learned_ids)

    return {
        "id": _slug(topic, level),
        "slug": _slug(topic, level),
        "title": f"{_topic_title(topic)} - {level}",
        "topic": topic,
        "topic_title": _topic_title(topic),
        "level": level,
        "description": f"{len(words)} từ vựng {_topic_title(topic)} cấp độ {level}",
        "word_count": len(words),
        "order": 0,
        "learned_count": learned,
        "progress_percent": round(learned / len(words) * 100) if words else 0,
        "words": words,
    }


async def seed_lessons() -> int:
    db = get_database()
    pipeline = [
        {"$group": {"_id": {"topic": "$topic", "level": "$level"}}},
        {"$sort": {"_id.topic": 1, "_id.level": 1}},
    ]
    groups = [g async for g in db[VOCAB].aggregate(pipeline)]
    now = datetime.now(timezone.utc)
    count = 0
    for g in groups:
        topic = g["_id"].get("topic") or "general"
        level = g["_id"].get("level") or "A1"
        await db["lessons"].update_one(
            {"slug": _slug(topic, level)},
            {
                "$setOnInsert": {
                    "slug": _slug(topic, level),
                    "topic": topic,
                    "level": level,
                    "created_at": now,
                }
            },
            upsert=True,
        )
        count += 1
    return count
