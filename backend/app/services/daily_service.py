"""Daily learning plan: goal progress, FSRS due cards, new words and weekly activity.

The plan is advisory: it never writes data and never changes scheduling. It only
aggregates what the learner already has so the dashboard can answer "what should
I study today?". Dates are bucketed in the learner's local timezone using the
``tz_offset`` argument (minutes east of UTC, i.e. ``-getTimezoneOffset()``).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from bson import ObjectId

from app.core.domains import DOMAINS, MVP_DOMAIN_ORDER, domain_for_topic
from app.db.mongodb import get_database
from app.services import learning_service
from app.services.lesson_service import domain_query

USERS = "users"
VOCAB = "vocabularies"
STATES = "user_word_states"
ATTEMPTS = "answer_attempts"
REVIEWS = "fsrs_review_logs"

LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]
PREVIEW_LIMIT = 5
DEFAULT_NEW_LIMIT = 10
DEFAULT_REVIEW_LIMIT = 30
DEFAULT_GOAL = 10


def _offset(tz_offset: int) -> timedelta:
    return timedelta(minutes=int(tz_offset or 0))


def _local_date(value: datetime, tz_offset: int) -> date:
    return (value + _offset(tz_offset)).date()


def _day_start(now: datetime, tz_offset: int) -> datetime:
    """UTC instant of the learner's local midnight for *now*."""
    offset = _offset(tz_offset)
    local = now + offset
    return local.replace(hour=0, minute=0, second=0, microsecond=0) - offset


def _interest_domains(user: dict) -> list[str]:
    interests = user.get("interests") or []
    if isinstance(interests, str):
        interests = [interests]
    domains: list[str] = []
    for interest in interests:
        domain = domain_for_topic(str(interest).strip().lower())
        if domain not in domains:
            domains.append(domain)
    return domains or list(MVP_DOMAIN_ORDER)


async def _started_ids(user_id: str) -> set[str]:
    db = get_database()
    return set(await db[STATES].distinct("vocabulary_id", {"user_id": user_id}))


async def _new_word_candidates(user: dict, limit: int) -> list[dict]:
    """Vocabulary the learner has never started, preferring their CEFR level."""
    if limit <= 0:
        return []
    db = get_database()
    started = await _started_ids(user["_id"])
    exclude = [ObjectId(value) for value in started if ObjectId.is_valid(value)]
    clauses: list[dict] = []
    for domain in _interest_domains(user):
        clauses.extend(domain_query(domain)["$or"])
    query: dict = {"$or": clauses}
    if exclude:
        query["_id"] = {"$nin": exclude}

    pipeline = [
        {"$match": query},
        {"$addFields": {"_level_rank": {"$indexOfArray": [LEVELS, "$level"]}}},
        {"$match": {"_level_rank": {"$gte": 0}}},
        {"$sort": {"_level_rank": 1, "word": 1}},
        {"$limit": max(limit * 3, 30)},
    ]
    rows = [doc async for doc in db[VOCAB].aggregate(pipeline)]
    level = user.get("learning_level")
    if level in LEVELS:
        same_level = [doc for doc in rows if doc.get("level") == level]
        if same_level:
            rows = same_level
    return rows[:limit]


def _preview(doc: dict) -> dict:
    raw_id = doc.get("_id") or doc.get("vocabulary_id") or doc.get("id")
    return {
        "vocabulary_id": str(raw_id) if raw_id is not None else "",
        "word": doc.get("word", ""),
        "phonetic": doc.get("phonetic", ""),
        "meaning": doc.get("meaning", ""),
        "level": doc.get("level", "A1"),
        "domain": domain_for_topic(doc.get("domain") or doc.get("topic")),
    }


async def _activity(user_id: str, now: datetime, tz_offset: int) -> dict:
    """Answered/reviewed counts for the last 7 local days (oldest first)."""
    db = get_database()
    today = _local_date(now, tz_offset)
    buckets: dict[str, dict] = {}
    for index in range(6, -1, -1):
        day = (today - timedelta(days=index)).isoformat()
        buckets[day] = {
            "date": day,
            "answered": 0,
            "correct": 0,
            "xp": 0,
            "words": set(),
        }

    week_start = _day_start(now, tz_offset) - timedelta(days=6)
    async for attempt in db[ATTEMPTS].find(
        {"user_id": user_id, "answered_at": {"$gte": week_start, "$lte": now}}
    ):
        answered_at = attempt.get("answered_at")
        if not answered_at:
            continue
        bucket = buckets.get(_local_date(answered_at, tz_offset).isoformat())
        if bucket is None:
            continue
        bucket["answered"] += 1
        if attempt.get("is_correct"):
            bucket["correct"] += 1
        bucket["xp"] += int((attempt.get("result") or {}).get("xp_gained") or 0)
        vocabulary_id = attempt.get("vocabulary_id")
        if vocabulary_id:
            bucket["words"].add(vocabulary_id)

    async for review in db[REVIEWS].find(
        {"user_id": user_id, "reviewed_at": {"$gte": week_start, "$lte": now}}
    ):
        reviewed_at = review.get("reviewed_at")
        if not reviewed_at:
            continue
        bucket = buckets.get(_local_date(reviewed_at, tz_offset).isoformat())
        if bucket is None:
            continue
        vocabulary_id = review.get("vocabulary_id")
        if vocabulary_id:
            bucket["words"].add(vocabulary_id)

    week = []
    for bucket in buckets.values():
        studied = len(bucket.pop("words"))
        week.append({**bucket, "studied": studied, "studied_flag": studied > 0})

    today_bucket = next(item for item in week if item["date"] == today.isoformat())
    return {"today": today_bucket, "week": week}


async def get_daily_plan(user_id: str, tz_offset: int = 0) -> dict:
    db = get_database()
    now = datetime.now(timezone.utc)
    user = await db[USERS].find_one({"_id": user_id})
    if not user:
        raise ValueError("User not found")

    goal = max(int(user.get("daily_goal") or DEFAULT_GOAL), 1)
    new_limit = max(int(user.get("daily_new_limit") or DEFAULT_NEW_LIMIT), 1)
    review_limit = max(
        int(user.get("daily_review_limit") or DEFAULT_REVIEW_LIMIT), 1
    )
    activity = await _activity(user_id, now, tz_offset)
    today = activity["today"]
    studied_today = today["studied"]

    due_count = await db[STATES].count_documents(
        {
            "user_id": user_id,
            "fsrs.due_at": {"$lte": now},
            **learning_service.STUDIED_FILTER,
        }
    )
    due_cards = await learning_service.get_due_cards(
        user_id, limit=min(review_limit, PREVIEW_LIMIT)
    )

    remaining = max(goal - studied_today, 0)
    candidates = await _new_word_candidates(user, min(remaining, new_limit))
    new_available = len(candidates)
    new_count = min(remaining, new_available)
    new_preview = [_preview(doc) for doc in candidates[: min(new_count, PREVIEW_LIMIT)]]

    next_lesson = None
    if candidates:
        first = candidates[0]
        domain = domain_for_topic(first.get("domain") or first.get("topic"))
        level = first.get("level") or "A1"
        lesson_id = f"{domain}-{level.lower()}"
        next_lesson = {
            "id": lesson_id,
            "slug": lesson_id,
            "title": f"{DOMAINS[domain]['name']} - {level}",
            "domain": domain,
            "level": level,
            "href": f"/lessons/{lesson_id}",
        }

    goal_met = studied_today >= goal
    tasks = []
    if due_count > 0:
        tasks.append(
            {
                "id": "review",
                "title": f"Ôn {due_count} từ đến hạn",
                "count": due_count,
                "href": "/flashcards",
                "done": False,
            }
        )
    else:
        tasks.append(
            {
                "id": "review",
                "title": "Không còn từ đến hạn",
                "count": 0,
                "href": "/flashcards",
                "done": True,
            }
        )
    if new_count > 0:
        tasks.append(
            {
                "id": "new",
                "title": f"Học {new_count} từ mới",
                "count": new_count,
                "href": next_lesson["href"] if next_lesson else "/learn",
                "done": False,
            }
        )
    elif remaining > 0:
        tasks.append(
            {
                "id": "new",
                "title": "Đã học hết kho từ phù hợp",
                "count": 0,
                "href": "/learn",
                "done": True,
            }
        )
    tasks.append(
        {
            "id": "goal",
            "title": "Đạt mục tiêu hôm nay" if goal_met else f"Mục tiêu: {goal} từ",
            "count": studied_today,
            "href": "/progress",
            "done": goal_met,
        }
    )

    return {
        "date": _local_date(now, tz_offset).isoformat(),
        "tz_offset": int(tz_offset or 0),
        "goal": goal,
        "new_limit": new_limit,
        "review_limit": review_limit,
        "studied_today": studied_today,
        "remaining": remaining,
        "goal_met": goal_met,
        "due_count": due_count,
        "new_count": new_count,
        "new_available": new_available,
        "streak": int(user.get("streak", 0) or 0),
        "studied_today_flag": studied_today > 0,
        "answered_today": today["answered"],
        "correct_today": today["correct"],
        "xp_today": today["xp"],
        "tasks": tasks,
        "next_lesson": next_lesson,
        "due_preview": [_preview(card) for card in due_cards],
        "new_preview": new_preview,
        "week": activity["week"],
    }
