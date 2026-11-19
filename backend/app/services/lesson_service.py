"""Lesson listing/detail derived from the vocabulary catalogue.

Lessons are grouped by MVP domain + CEFR level. Each lesson is split into
stable, ordered units of ``UNIT_SIZE`` words. Progress is computed from
``user_word_states`` Mastery (never from the legacy Leitner ``box``).
"""
import asyncio
from datetime import datetime, timezone

from app.core.config import settings
from app.core.domains import DOMAINS, MVP_DOMAIN_ORDER, domain_for_topic
from app.db.mongodb import get_database

VOCAB = "vocabularies"
LESSON_PROGRESS = "lesson_progress"
STATES = "user_word_states"

LEVEL_ORDER = {"A1": 0, "A2": 1, "B1": 2, "B2": 3, "C1": 4, "C2": 5}
VALID_LEVELS = set(LEVEL_ORDER)

UNIT_SIZE = 15

# Legacy topics that map to a canonical domain.
LEGACY_TOPICS = {
    "general": ["general", "academic", "science", "daily-life", "daily life", "travel"],
    "technology": ["technology", "tech", "it"],
    "business": ["business"],
}


def _legacy_domain_of(topic: str | None) -> str | None:
    key = str(topic or "").strip().lower()
    for domain, topics in LEGACY_TOPICS.items():
        if key in topics:
            return domain
    return None


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


def unit_count(total: int) -> int:
    if total <= 0:
        return 0
    return (total + UNIT_SIZE - 1) // UNIT_SIZE


def chunk_bounds(total: int, unit: int) -> tuple[int, int]:
    count = unit_count(total)
    if count == 0:
        raise ValueError("Lesson has no words")
    if unit < 1 or unit > count:
        raise ValueError(f"unit must be between 1 and {count}")
    start = (unit - 1) * UNIT_SIZE
    return start, min(start + UNIT_SIZE, total)


def parse_unit(raw) -> int | None:
    if raw is None:
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ValueError("unit must be a positive integer") from None
    if value < 1:
        raise ValueError("unit must be a positive integer")
    return value


def placement_levels_for_user(user: dict, domains: list[str] | tuple[str, ...]) -> dict[str, str]:
    """Return each domain's confirmed/declared starting level.

    Older users do not have ``placement_levels`` yet. Their existing
    ``learning_level`` remains a backwards-compatible fallback rather than
    making them start from A1 again.
    """
    raw = user.get("placement_levels")
    raw = raw if isinstance(raw, dict) else {}
    fallback = str(user.get("learning_level") or "A1").upper()
    fallback = fallback if fallback in VALID_LEVELS else "A1"
    result: dict[str, str] = {}
    for domain in domains:
        candidate = str(raw.get(domain) or fallback).upper()
        result[domain] = candidate if candidate in VALID_LEVELS else "A1"
    return result


def placement_levels_for_interests(interests: list[str], level: str) -> dict[str, str]:
    """Build a domain-specific placement map from selected user interests."""
    normalized = {domain_for_topic(item) for item in interests if item}
    normalized = normalized or {"general"}
    target = str(level).upper()
    target = target if target in VALID_LEVELS else "A1"
    return {domain: target for domain in normalized}


def _unit_words(words: list[dict], unit: int) -> list[dict]:
    start, end = chunk_bounds(len(words), unit)
    return words[start:end]


def domain_query(domain: str) -> dict:
    """Match canonical domain, with a fallback for not-yet-migrated docs."""
    domain = domain_for_topic(domain)
    return {
        "$or": [
            {"domain": domain},
            {
                "domain": None,
                "topic": {"$in": LEGACY_TOPICS.get(domain, [domain])},
            },
        ]
    }


async def _catalog_word_ids(domains: list[str]) -> dict[str, dict[str, list[str]]]:
    """Load only the word ids needed to build lesson lists, in one query."""
    db = get_database()
    catalog = {domain: {level: [] for level in LEVEL_ORDER} for domain in domains}
    clauses: list[dict] = []
    for domain in domains:
        clauses.extend(domain_query(domain)["$or"])
    if not clauses:
        return catalog

    query = {"$or": clauses, "level": {"$in": list(LEVEL_ORDER)}}
    docs = [
        doc
        async for doc in db[VOCAB].find(
            query, {"domain": 1, "topic": 1, "level": 1, "word": 1}
        )
    ]
    docs.sort(key=lambda doc: str(doc.get("word") or ""))
    for doc in docs:
        domain = doc.get("domain")
        if domain not in catalog:
            domain = _legacy_domain_of(doc.get("topic"))
        if domain not in catalog:
            continue
        catalog[domain][doc["level"]].append(str(doc["_id"]))
    return catalog


async def _passed_assessments(
    user_id: str, domains: list[str]
) -> dict[str, set[str]]:
    db = get_database()
    passed = {domain: set() for domain in domains}
    async for row in db.level_assessment_results.find(
        {"user_id": user_id, "domain": {"$in": domains}}, {"domain": 1, "level": 1}
    ):
        domain = row.get("domain")
        if domain in passed and row.get("level"):
            passed[domain].add(row["level"])
    return passed


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


async def _lesson_progress(user_id: str) -> dict[str, dict]:
    """Completed unit numbers per lesson.

    Legacy progress documents (created before units existed) have no ``unit``
    field and count as the whole lesson being complete.
    """
    db = get_database()
    progress: dict[str, dict] = {}
    async for p in db[LESSON_PROGRESS].find(
        {"user_id": user_id, "completed": True}
    ):
        lesson_id = p.get("lesson_id")
        if not lesson_id:
            continue
        entry = progress.setdefault(lesson_id, {"units": set(), "legacy": False})
        unit = p.get("unit")
        if isinstance(unit, int) and unit > 0:
            entry["units"].add(unit)
        else:
            entry["legacy"] = True
    return progress


def _unit_completed(
    words: list[dict],
    learned_ids: set[str],
    entry: dict | None,
    unit: int,
) -> bool:
    if not words:
        return False
    if entry and entry.get("legacy"):
        return True
    if entry and unit in entry.get("units", set()):
        return True
    return False


def _lesson_completed(
    words: list[dict], learned_ids: set[str], entry: dict | None
) -> bool:
    if not words:
        return False
    if entry and entry.get("legacy"):
        return True
    count = unit_count(len(words))
    if entry and count and all(
        unit in entry.get("units", set()) for unit in range(1, count + 1)
    ):
        return True
    return False


def _first_incomplete_unit(
    words: list[dict], learned_ids: set[str], entry: dict | None
) -> int:
    count = unit_count(len(words))
    if count == 0:
        return 1
    if entry and entry.get("legacy"):
        return 1
    for unit in range(1, count + 1):
        if not _unit_completed(
            _unit_words(words, unit), learned_ids, entry, unit
        ):
            return unit
    return 1


def _unlock_requirement(
    domain: str,
    level: str,
    real_levels: list[str],
    words_by_level: dict[str, list[dict]],
    learned_ids: set[str],
    progress: dict[str, dict],
    passed_assessments: set[str],
    placement_level: str,
) -> str | None:
    """Return the immediate prerequisite unless placement opens this level."""
    if LEVEL_ORDER[level] <= LEVEL_ORDER[placement_level]:
        return None
    lower_levels = [item for item in real_levels if LEVEL_ORDER[item] < LEVEL_ORDER[level]]
    if not lower_levels:
        return None
    lower = lower_levels[-1]
    if lower in passed_assessments:
        return None
    return lower


async def _lesson_unlock_requirement(
    user_id: str,
    domain: str,
    level: str,
    learned_ids: set[str],
    progress: dict[str, dict],
    placement_level: str,
) -> str | None:
    db = get_database()
    passed_assessments = {
        result["level"]
        async for result in db.level_assessment_results.find(
            {"user_id": user_id, "domain": domain}, {"level": 1}
        )
    }
    catalog = await _catalog_word_ids([domain])
    if LEVEL_ORDER[level] <= LEVEL_ORDER[placement_level]:
        return None
    lower_levels = [
        candidate
        for candidate in LEVEL_ORDER
        if LEVEL_ORDER[candidate] < LEVEL_ORDER.get(level, 99)
        and catalog[domain][candidate]
    ]
    if not lower_levels:
        return None
    lower = lower_levels[-1]
    if lower in passed_assessments:
        return None
    return lower


def next_level(domain: str, level: str) -> str | None:
    ordered = sorted(VALID_LEVELS, key=lambda item: LEVEL_ORDER[item])
    try:
        return ordered[ordered.index(level) + 1]
    except (ValueError, IndexError):
        return None


def _interest_set(user: dict) -> set[str]:
    interests = user.get("interests") or []
    if isinstance(interests, str):
        interests = [interests]
    return {domain_for_topic(str(i).strip().lower()) for i in interests if i}


async def get_lesson_words(
    domain: str, level: str, unit: int | None = None
) -> list[dict]:
    db = get_database()
    query = {"$and": [domain_query(domain), {"level": level}]}
    words = [doc async for doc in db[VOCAB].find(query).sort("word", 1)]
    if unit is None:
        return words
    return _unit_words(words, parse_unit(unit))


async def list_lessons(user_id: str, user: dict | None = None) -> list[dict]:
    db = get_database()
    if user is None:
        user = await db.users.find_one({"_id": user_id}) or {}
    interest_set = _interest_set(user)
    user_level = user.get("learning_level")
    domains = [
        domain
        for domain in MVP_DOMAIN_ORDER
        if not interest_set or domain in interest_set
    ]
    if not domains:
        return []
    placement_levels = placement_levels_for_user(user, domains)

    states, progress, catalog, passed = await asyncio.gather(
        _state_maps(user_id),
        _lesson_progress(user_id),
        _catalog_word_ids(domains),
        _passed_assessments(user_id, domains),
    )
    learned_ids, mastered_ids = states

    lessons: list[dict] = []
    order = 0
    for domain in domains:
        meta = DOMAINS[domain]
        passed_assessments = passed[domain]
        placement_level = placement_levels[domain]
        words_by_level = catalog[domain]
        real_levels = [
            level for level in LEVEL_ORDER if words_by_level[level]
        ]

        for level in LEVEL_ORDER:
            words = words_by_level[level]
            total = len(words)
            ids = words
            learned = sum(1 for wid in ids if wid in learned_ids)
            mastered = sum(1 for wid in ids if wid in mastered_ids)
            slug = lesson_slug(domain, level)
            entry = progress.get(slug)
            count = unit_count(total)
            is_done = _lesson_completed(words, learned_ids, entry)
            unlock_requirement = _unlock_requirement(
                domain,
                level,
                real_levels,
                words_by_level,
                learned_ids,
                progress,
                passed_assessments,
                placement_level,
            )
            unlocked = total > 0 and unlock_requirement is None

            units: list[dict] = []
            next_unit: int | None = None
            for unit in range(1, count + 1):
                segment = _unit_words(words, unit)
                segment_ids = segment
                unit_learned = sum(
                    1 for wid in segment_ids if wid in learned_ids
                )
                unit_mastered = sum(
                    1 for wid in segment_ids if wid in mastered_ids
                )
                unit_done = _unit_completed(
                    segment, learned_ids, entry, unit
                )
                if next_unit is None and not unit_done:
                    next_unit = unit
                units.append(
                    {
                        "index": unit,
                        "unit": unit,
                        "word_count": len(segment),
                        "learned": unit_learned,
                        "mastered": unit_mastered,
                        "progress_percent": round(
                            unit_learned / len(segment) * 100
                        )
                        if segment
                        else 0,
                        "completed": unit_done,
                        "unlocked": unit == 1 or units[-1]["completed"],
                    }
                )
            if next_unit is None:
                next_unit = 1 if count else None
            next_unit_info = (
                units[next_unit - 1] if next_unit and units else None
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
                        f" · {count} unit"
                        if total
                        else f"Nội dung {meta['name']} cấp độ {level} đang được cập nhật"
                    ),
                    "word_count": total,
                    "total_words": total,
                    "unit_count": count,
                    "units": units,
                    "next_unit": next_unit,
                    "next_unit_word_count": (
                        next_unit_info["word_count"] if next_unit_info else 0
                    ),
                    "order": order,
                    "learned_count": learned,
                    "mastered_count": mastered,
                    "progress_percent": round(learned / total * 100) if total else 0,
                    "completed": is_done,
                    "units_completed": sum(1 for unit in units if unit["completed"]),
                    "recommended": user_level == level,
                    "review_only": LEVEL_ORDER[level] < LEVEL_ORDER[placement_level],
                    "placement_level": placement_level,
                    "unlocked": unlocked,
                    "unlock_requirement": (
                        {
                            "lesson_id": lesson_slug(domain, unlock_requirement),
                            "level": unlock_requirement,
                        }
                        if unlock_requirement
                        else None
                    ),
                    "has_exercises": total >= settings.MIN_LESSON_WORDS,
                    "assessment_required": is_done and level not in passed_assessments,
                    "assessment_status": "passed" if level in passed_assessments else ("required" if is_done else "locked"),
                    "next_level": next_level(domain, level),
                }
            )
            order += 1
    return lessons


async def get_lesson(
    lesson_id: str, user_id: str, unit: int | None = None
) -> dict | None:
    domain_slug, level = parse_lesson_id(lesson_id)
    domain = domain_for_topic(domain_slug)
    if level is None:
        return None

    full_words = await get_lesson_words(domain, level)
    if not full_words:
        return None

    db = get_database()
    user = await db.users.find_one({"_id": user_id}) or {}
    placement_level = placement_levels_for_user(user, [domain])[domain]
    learned_ids, mastered_ids = await _state_maps(user_id)
    progress = await _lesson_progress(user_id)
    blocked_by = await _lesson_unlock_requirement(
        user_id, domain, level, learned_ids, progress, placement_level
    )
    if blocked_by:
        raise ValueError(
            f"Bạn cần hoàn thành cấp độ {blocked_by} trước khi học {level}."
        )
    slug = lesson_slug(domain, level)
    entry = progress.get(slug)

    count = unit_count(len(full_words))
    requested = parse_unit(unit)
    resolved = requested or _first_incomplete_unit(
        full_words, learned_ids, entry
    )
    if resolved < 1 or resolved > count:
        raise ValueError(f"unit must be between 1 and {count}")

    if resolved > 1 and not _unit_completed(
        _unit_words(full_words, resolved - 1), learned_ids, entry, resolved - 1
    ):
        raise ValueError(f"Complete Unit {resolved - 1} before opening Unit {resolved}")

    words = _unit_words(full_words, resolved)
    ids = [str(w["_id"]) for w in words]
    learned = sum(1 for wid in ids if wid in learned_ids)
    mastered = sum(1 for wid in ids if wid in mastered_ids)
    unit_done = _unit_completed(words, learned_ids, entry, resolved)
    lesson_done = _lesson_completed(full_words, learned_ids, entry)
    meta = DOMAINS[domain]

    return {
        "id": slug,
        "slug": slug,
        "title": f"{meta['name']} - {level}",
        "topic": domain,
        "domain": domain,
        "topic_title": meta["name"],
        "level": level,
        "review_only": LEVEL_ORDER[level] < LEVEL_ORDER[placement_level],
        "placement_level": placement_level,
        "description": (
            f"Unit {resolved}/{count} · {len(words)} từ vựng "
            f"{meta['name']} cấp độ {level}"
        ),
        "unit": resolved,
        "unit_count": count,
        "word_count": len(words),
        "total_words": len(full_words),
        "order": 0,
        "learned_count": learned,
        "mastered_count": mastered,
        "progress_percent": round(learned / len(words) * 100) if words else 0,
        "completed": unit_done,
        "next_unit_unlocked": resolved >= count or unit_done,
        "lesson_completed": lesson_done,
        "units_completed": sum(
            1 for item in range(1, count + 1)
            if _unit_completed(_unit_words(full_words, item), learned_ids, entry, item)
        ),
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
