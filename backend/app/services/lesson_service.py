"""Lesson listing/detail derived from the vocabulary catalogue.

Lessons are grouped by MVP domain + CEFR level. Progress is computed from
``user_word_states`` Mastery (never from the legacy Leitner ``box``).
"""
from datetime import datetime, timezone

from app.core.config import settings
from app.core.domains import DOMAINS, MVP_DOMAIN_ORDER, domain_for_topic
from app.db.mongodb import get_database

VOCAB = "vocabularies"
LESSON_PROGRESS = "lesson_progress"
STATES = "user_word_states"

LEVEL_ORDER = {"A1": 0, "A2": 1, "B1": 2, "B2": 3, "C1": 4, "C2": 5}
VALID_LEVELS = set(LEVEL_ORDER)

# Legacy topics that map to a canonical domain.
LEGACY_TOPICS = {
    "general": ["general", "academic", "science", "daily-life", "daily life", "travel"],
    "technology": ["technology", "tech", "it"],
    "business": ["business"],
}


def lesson_slug(domain: str, level: str | None = None) -> str:
    base = domain.strip().lower().replace(" ", "-")
    return f"{base}-{level.lower()}" if level else base


def parse_lesson_id(lesson_id: str) -> tuple[str, str | None]:
    if "-" in lesson_id:
        head, tail = lesson_id.rsplit("-", 1)
        level = tail.upper()
        if level in VALID_LEVELS:
            return head, level
    return lesson_id, None


def domain_query(domain: str) -> dict:
    """Match canonical domain, with a fallback for not-yet-migrated docs."""
    domain = domain_for_topic(domain)
    return {
        "$or": [
            {"domain": domain},
            {
                "domain": {"$exists": False},
                "topic": {"$in": LEGACY_TOPICS.get(domain, [domain])},
            },
        ]
    }


def _word_out(v: dict) -> dict:
    domain = domain_for_topic(v.get("domain") or v.get("topic"))
    return {
        "id": str(v["_id"]),
        "word": v.get("word", ""),
        "phonetic": v.get("phonetic", ""),
        "part_of_speech": v.get("part_of_speech", ""),
        "meaning": v.get("meaning", ""),
        "example": v.get("example", ""),
        "synonyms": v.get("synonyms", []),
        "antonyms": v.get("antonyms", []),
        "topic": v.get("topic", domain),
        "domain": domain,
        "level": v.get("level", "A1"),
    }


async def _state_maps(user_id: str) -> tuple[set[str], set[str]]:
    db = get_database()
    learned: set[str] = set()
    mastered: set[str] = set()
    async for state in db[STATES].find({"user_id": user_id}):
        mastery = state.get("mastery") or {}
        values = [float(mastery.get(s, 0) or 0) for s in ("meaning", "spelling", "context")]
        if any(v > 0 for v in values):
            learned.add(state["vocabulary_id"])
        if all(v >= settings.MASTERY_THRESHOLD for v in values):
            mastered.add(state["vocabulary_id"])
    return learned, mastered


async def _completed_lessons(user_id: str) -> set[str]:
    db = get_database()
    done: set[str] = set()
    async for p in db[LESSON_PROGRESS].find(
        {"user_id": user_id, "completed": True}
    ):
        if p.get("lesson_id"):
            done.add(p["lesson_id"])
    return done


def _interest_set(user: dict) -> set[str]:
    interests = user.get("interests") or []
    if isinstance(interests, str):
        interests = [interests]
    return {domain_for_topic(str(i).strip().lower()) for i in interests if i}


async def get_lesson_words(domain: str, level: str) -> list[dict]:
    db = get_database()
    query = {"$and": [domain_query(domain), {"level": level}]}
    return [doc async for doc in db[VOCAB].find(query).sort("word", 1)]


async def list_lessons(user_id: str) -> list[dict]:
    db = get_database()
    user = await db.users.find_one({"_id": user_id}) or {}
    interest_set = _interest_set(user)
    user_level = user.get("learning_level")

    learned_ids, mastered_ids = await _state_maps(user_id)
    completed = await _completed_lessons(user_id)

    lessons: list[dict] = []
    order = 0
    for domain in MVP_DOMAIN_ORDER:
        if interest_set and domain not in interest_set:
            continue
        meta = DOMAINS[domain]
        counts: dict[str, int] = {}
        async for row in db[VOCAB].aggregate(
            [
                {"$match": domain_query(domain)},
                {"$group": {"_id": "$level", "count": {"$sum": 1}}},
            ]
        ):
            counts[row["_id"] or "A1"] = row["count"]

        real_levels = sorted(counts, key=lambda lv: LEVEL_ORDER.get(lv, 99))
        lowest = real_levels[0] if real_levels else None
        for level in LEVEL_ORDER:
            total = counts.get(level, 0)
            words = await get_lesson_words(domain, level) if total else []
            ids = [str(w["_id"]) for w in words]
            learned = sum(1 for wid in ids if wid in learned_ids)
            mastered = sum(1 for wid in ids if wid in mastered_ids)
            slug = lesson_slug(domain, level)
            is_done = slug in completed or (total > 0 and learned >= total)
            prev_level = None
            for candidate in reversed(real_levels):
                if LEVEL_ORDER[candidate] < LEVEL_ORDER[level]:
                    prev_level = candidate
                    break
            unlocked = (
                level == lowest
                or user_level == level
                or (
                    prev_level is not None
                    and (
                        lesson_slug(domain, prev_level) in completed
                        or (
                            counts.get(prev_level, 0) > 0
                            and all(
                                wid in learned_ids
                                for wid in [
                                    str(w["_id"])
                                    for w in await get_lesson_words(domain, prev_level)
                                ]
                            )
                        )
                    )
                )
            )
            lessons.append(
                {
                    "id": slug,
                    "slug": slug,
                    "title": f"{meta['name']} - {level}",
                    "topic": domain,
                    "domain": domain,
                    "topic_title": meta["name"],
                    "level": level,
                    "description": (
                        f"{total} từ vựng {meta['name']} cấp độ {level}"
                        if total
                        else f"Nội dung {meta['name']} cấp độ {level} đang được cập nhật"
                    ),
                    "word_count": total,
                    "order": order,
                    "learned_count": learned,
                    "mastered_count": mastered,
                    "progress_percent": round(learned / total * 100) if total else 0,
                    "completed": is_done,
                    "recommended": user_level == level,
                    "unlocked": unlocked or total > 0,
                    "has_exercises": total >= settings.MIN_LESSON_WORDS,
                }
            )
            order += 1
    return lessons


async def get_lesson(lesson_id: str, user_id: str) -> dict | None:
    domain_slug, level = parse_lesson_id(lesson_id)
    domain = domain_for_topic(domain_slug)
    if level is None:
        return None

    words = await get_lesson_words(domain, level)
    if not words:
        return None

    learned_ids, mastered_ids = await _state_maps(user_id)
    completed = await _completed_lessons(user_id)
    ids = [str(w["_id"]) for w in words]
    learned = sum(1 for wid in ids if wid in learned_ids)
    mastered = sum(1 for wid in ids if wid in mastered_ids)
    slug = lesson_slug(domain, level)
    meta = DOMAINS[domain]

    return {
        "id": slug,
        "slug": slug,
        "title": f"{meta['name']} - {level}",
        "topic": domain,
        "domain": domain,
        "topic_title": meta["name"],
        "level": level,
        "description": f"{len(words)} từ vựng {meta['name']} cấp độ {level}",
        "word_count": len(words),
        "order": 0,
        "learned_count": learned,
        "mastered_count": mastered,
        "progress_percent": round(learned / len(words) * 100) if words else 0,
        "completed": slug in completed or (bool(words) and learned >= len(words)),
        "has_exercises": len(words) >= settings.MIN_LESSON_WORDS,
        "words": [_word_out(w) for w in words],
    }


async def seed_lessons() -> int:
    db = get_database()
    now = datetime.now(timezone.utc)
    count = 0
    for domain in MVP_DOMAIN_ORDER:
        async for row in db[VOCAB].aggregate(
            [
                {"$match": domain_query(domain)},
                {"$group": {"_id": "$level"}},
            ]
        ):
            level = row["_id"] or "A1"
            slug = lesson_slug(domain, level)
            meta = DOMAINS[domain]
            await db.lessons.update_one(
                {"slug": slug},
                {
                    "$setOnInsert": {
                        "slug": slug,
                        "domain": domain,
                        "topic": domain,
                        "level": level,
                        "title": f"{meta['name']} - {level}",
                        "description": f"{meta['name']} {level}",
                        "created_at": now,
                    },
                    "$set": {"updated_at": now},
                },
                upsert=True,
            )
            count += 1
    return count
