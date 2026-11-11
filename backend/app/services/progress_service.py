"""Answer evaluation, Mastery updates, XP/streak and progress dashboards.

Each ``attempt_id`` is unique, so retries never award XP/Mastery twice. Writes
run in a transaction on replica sets/Atlas; see ``db_tx`` for the standalone
fallback. An answer attempt is deliberately *not* an FSRS review event.
"""
from __future__ import annotations

from datetime import datetime, timezone

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.core.config import settings
from app.core.domains import MVP_DOMAIN_ORDER, domain_for_topic
from app.db.mongodb import get_database
from app.services.db_tx import run_in_transaction
from app.services.exercise_service import grade as grade_exercise
from app.services.fsrs_service import new_card_state
from app.services.mastery_service import (
    DEFAULT_MASTERY,
    SKILLS,
    SKILLS_SET,
    update_skill,
)

USERS = "users"
VOCAB = "vocabularies"
STATES = "user_word_states"
ATTEMPTS = "answer_attempts"
REVIEWS = "fsrs_review_logs"
LESSON_PROGRESS = "lesson_progress"

XP_PER_CORRECT = 10
XP_PER_WRONG = 2
XP_PER_LESSON_BONUS = 50
LEVEL_THRESHOLDS = [0, 100, 250, 500, 900, 1400, 2000, 2800, 3800, 5000]


def level_from_xp(xp: int) -> int:
    level = 1
    for i, threshold in enumerate(LEVEL_THRESHOLDS):
        if xp >= threshold:
            level = i + 1
    return level


def normalize_answer(value: str) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def evaluate_answer(vocabulary: dict, skill: str, answer: str) -> tuple[bool, str]:
    """Legacy fallback used by /progress/study-answer without an exercise item."""
    if skill not in (*SKILLS_SET, "listening"):
        raise ValueError("Invalid exercise skill")
    expected = (
        vocabulary.get("meaning", "")
        if skill == "meaning"
        else vocabulary.get("word", "")
    )
    if skill == "context":
        from app.services.exercise_service import build_cloze

        if not build_cloze(str(vocabulary.get("example") or ""), expected):
            raise ValueError("No validated cloze context for this word")
    return (
        bool(expected) and normalize_answer(answer) == normalize_answer(expected),
        expected,
    )


def _new_streak(user: dict, now: datetime) -> int:
    last = user.get("last_study_date")
    streak = int(user.get("streak", 0))
    if not last:
        return 1
    last_date = last.date() if isinstance(last, datetime) else last
    delta = (now.date() - last_date).days
    return streak + 1 if delta == 1 else (1 if delta > 1 else max(streak, 1))


def _attempt_result(doc: dict) -> dict:
    if doc.get("result"):
        return doc["result"]
    return {
        "attempt_id": doc.get("attempt_id"),
        "session_id": doc.get("session_id"),
        "exercise_item_id": doc.get("exercise_item_id"),
        "vocabulary_id": doc.get("vocabulary_id"),
        "skill": doc.get("skill"),
        "is_correct": bool(doc.get("is_correct")),
        "correct": bool(doc.get("is_correct")),
        "correct_answer": doc.get("correct_answer"),
        "submitted_answer": doc.get("submitted_answer"),
        "response_time_ms": doc.get("response_time_ms", 0),
        "hint_used": bool(doc.get("hint_used")),
        "error_type": doc.get("error_type"),
        "answered_at": doc.get("answered_at"),
    }


async def process_answer(
    user_id: str,
    vocabulary_id: str,
    skill: str,
    submitted_answer: str,
    attempt_id: str,
    *,
    session_id: str | None = None,
    exercise_item_id: str | None = None,
    response_time_ms: int = 0,
    hint_used: bool = False,
    exercise_item: dict | None = None,
) -> dict:
    if not ObjectId.is_valid(vocabulary_id):
        raise ValueError("Invalid vocabulary id")
    if not attempt_id or len(attempt_id) > 100:
        raise ValueError("Invalid attempt id")
    if skill not in (*SKILLS_SET, "listening"):
        raise ValueError("Invalid exercise skill")

    db = get_database()
    earlier = await db[ATTEMPTS].find_one({"attempt_id": attempt_id})
    if earlier:
        if (
            earlier.get("user_id") != user_id
            or earlier.get("vocabulary_id") != vocabulary_id
            or earlier.get("skill") != skill
        ):
            raise ValueError("Attempt ID was used for a different answer")
        return _attempt_result(earlier)

    vocabulary = await db[VOCAB].find_one({"_id": ObjectId(vocabulary_id)})
    if not vocabulary:
        raise ValueError("Vocabulary not found")

    if exercise_item is not None:
        correct, expected, error_type = grade_exercise(exercise_item, submitted_answer)
    else:
        correct, expected = evaluate_answer(vocabulary, skill, submitted_answer)
        error_type = (
            None
            if correct
            else ("spelling_error" if skill in ("spelling", "context") else "meaning_error")
        )

    now = datetime.now(timezone.utc)
    domain = domain_for_topic(
        vocabulary.get("domain") or vocabulary.get("topic")
    )

    async def work(session):
        selector = {"user_id": user_id, "vocabulary_id": vocabulary_id}
        state = await db[STATES].find_one(selector, session=session)
        old_mastery = (state or {}).get("mastery", DEFAULT_MASTERY)
        mastery = (
            update_skill(
                old_mastery,
                skill,
                correct,
                response_time_ms=response_time_ms,
                hint_used=hint_used,
            )
            if skill in SKILLS_SET
            else {name: float(old_mastery.get(name, 0) or 0) for name in SKILLS}
        )
        fsrs_state = (
            (state or {}).get("fsrs")
            or new_card_state(now)
        )
        await db[STATES].update_one(
            selector,
            {
                "$set": {
                    "mastery": mastery,
                    "updated_at": now,
                    "last_attempt_at": now,
                    "last_skill": skill,
                },
                "$setOnInsert": {
                    "user_id": user_id,
                    "vocabulary_id": vocabulary_id,
                    "fsrs": fsrs_state,
                    "review_count": 0,
                    "started_at": now,
                },
            },
            upsert=True,
            session=session,
        )

        user = await db[USERS].find_one({"_id": user_id}, session=session)
        if not user:
            raise ValueError("User not found")
        xp_gain = XP_PER_CORRECT if correct else XP_PER_WRONG
        xp = int(user.get("xp", 0)) + xp_gain
        streak = _new_streak(user, now)
        await db[USERS].update_one(
            {"_id": user_id},
            {
                "$set": {
                    "xp": xp,
                    "streak": streak,
                    "last_study_date": now,
                    "updated_at": now,
                }
            },
            session=session,
        )

        result = {
            "attempt_id": attempt_id,
            "session_id": session_id,
            "exercise_item_id": exercise_item_id,
            "vocabulary_id": vocabulary_id,
            "skill": skill,
            "is_correct": correct,
            "correct": correct,
            "correct_answer": expected,
            "submitted_answer": submitted_answer,
            "response_time_ms": response_time_ms,
            "hint_used": hint_used,
            "error_type": error_type,
            "mastery": mastery,
            "xp_gained": xp_gain,
            "xp": xp,
            "level": level_from_xp(xp),
            "streak": streak,
            "answered_at": now,
        }
        await db[ATTEMPTS].insert_one(
            {
                "attempt_id": attempt_id,
                "user_id": user_id,
                "session_id": session_id,
                "exercise_item_id": exercise_item_id,
                "vocabulary_id": vocabulary_id,
                "domain": domain,
                "skill": skill,
                "submitted_answer": submitted_answer,
                "correct_answer": expected,
                "is_correct": correct,
                "response_time_ms": response_time_ms,
                "hint_used": hint_used,
                "error_type": error_type,
                "answered_at": now,
                "result": result,
            },
            session=session,
        )
        return result

    try:
        return await run_in_transaction(db, work)
    except DuplicateKeyError:
        earlier = await db[ATTEMPTS].find_one({"attempt_id": attempt_id})
        if (
            not earlier
            or earlier.get("user_id") != user_id
            or earlier.get("vocabulary_id") != vocabulary_id
        ):
            raise
        return _attempt_result(earlier)


async def process_study_answer(
    user_id: str,
    vocabulary_id: str,
    answer: str,
    skill: str,
    attempt_id: str,
    response_time_ms: int = 0,
    hint_used: bool = False,
) -> dict:
    """Backwards-compatible entry point for the legacy study-answer API."""
    return await process_answer(
        user_id,
        vocabulary_id,
        skill,
        answer,
        attempt_id,
        response_time_ms=response_time_ms,
        hint_used=hint_used,
    )


async def complete_lesson(
    user_id: str,
    lesson_id: str,
    domain: str,
    passed: bool,
    learned_count: int = 0,
    mastered_count: int = 0,
) -> bool:
    """Mark a lesson complete once. Returns True only on first completion."""
    if not passed:
        return False
    db = get_database()
    now = datetime.now(timezone.utc)
    try:
        result = await db[LESSON_PROGRESS].update_one(
            {"user_id": user_id, "lesson_id": lesson_id},
            {
                "$set": {
                    "user_id": user_id,
                    "lesson_id": lesson_id,
                    "topic": domain_for_topic(domain),
                    "completed": True,
                    "completed_at": now,
                    "learned_count": learned_count,
                    "mastered_count": mastered_count,
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )
        return bool(result.modified_count or result.upserted_id)
    except DuplicateKeyError:
        return False


async def _states_with_vocab(user_id: str) -> list[tuple[dict, dict]]:
    db = get_database()
    states = [doc async for doc in db[STATES].find({"user_id": user_id})]
    ids = [
        ObjectId(doc["vocabulary_id"])
        for doc in states
        if ObjectId.is_valid(doc.get("vocabulary_id", ""))
    ]
    vocab_map = {
        str(v["_id"]): v
        async for v in db[VOCAB].find({"_id": {"$in": ids}})
    }
    return [
        (doc, vocab_map.get(doc["vocabulary_id"], {}))
        for doc in states
        if doc["vocabulary_id"] in vocab_map
    ]


def _is_learned(mastery: dict) -> bool:
    return any(float(mastery.get(skill, 0) or 0) > 0 for skill in SKILLS)


def _is_mastered(mastery: dict, threshold: float | None = None) -> bool:
    limit = settings.MASTERY_THRESHOLD if threshold is None else threshold
    return all(float(mastery.get(skill, 0) or 0) >= limit for skill in SKILLS)


async def get_user_progress(user_id: str) -> dict:
    db = get_database()
    user = await db[USERS].find_one({"_id": user_id}) or {}
    pairs = await _states_with_vocab(user_id)
    learned = sum(1 for state, _ in pairs if _is_learned(state.get("mastery") or {}))
    mastered = sum(1 for state, _ in pairs if _is_mastered(state.get("mastery") or {}))
    lessons_completed = await db[LESSON_PROGRESS].count_documents(
        {"user_id": user_id, "completed": True}
    )
    xp = int(user.get("xp", 0))
    return {
        "xp": xp,
        "level": level_from_xp(xp),
        "streak": user.get("streak", 0),
        "last_study_date": user.get("last_study_date"),
        "words_learned": learned,
        "words_mastered": mastered,
        "lessons_completed": lessons_completed,
    }


async def get_summary(user_id: str) -> dict:
    db = get_database()
    now = datetime.now(timezone.utc)
    user = await db[USERS].find_one({"_id": user_id}) or {}
    pairs = await _states_with_vocab(user_id)

    started = 0
    mastered = 0
    due = 0
    by_domain: dict[str, dict] = {
        domain: {"domain": domain, "started": 0, "mastered": 0, "total": 0}
        for domain in MVP_DOMAIN_ORDER
    }
    for state, vocab in pairs:
        mastery = state.get("mastery") or {}
        domain = domain_for_topic(vocab.get("domain") or vocab.get("topic"))
        bucket = by_domain.setdefault(
            domain, {"domain": domain, "started": 0, "mastered": 0, "total": 0}
        )
        bucket["total"] += 1
        if _is_learned(mastery):
            started += 1
            bucket["started"] += 1
        if _is_mastered(mastery):
            mastered += 1
            bucket["mastered"] += 1
        due_at = (state.get("fsrs") or {}).get("due_at")
        if due_at and due_at <= now:
            due += 1

    correct = await db[ATTEMPTS].count_documents(
        {"user_id": user_id, "is_correct": True}
    )
    wrong = await db[ATTEMPTS].count_documents(
        {"user_id": user_id, "is_correct": False}
    )
    lessons_completed = await db[LESSON_PROGRESS].count_documents(
        {"user_id": user_id, "completed": True}
    )
    xp = int(user.get("xp", 0))
    return {
        "xp": xp,
        "level": level_from_xp(xp),
        "streak": user.get("streak", 0),
        "last_study_date": user.get("last_study_date"),
        "words_started": started,
        "words_learned": started,
        "words_mastered": mastered,
        "due_today": due,
        "lessons_completed": lessons_completed,
        "correct_answers": correct,
        "wrong_answers": wrong,
        "accuracy": round(correct / (correct + wrong) * 100) if (correct + wrong) else 0,
        "domains": list(by_domain.values()),
    }


async def get_mastery_breakdown(user_id: str) -> dict:
    pairs = await _states_with_vocab(user_id)
    skills = {
        skill: {"started": 0, "mastered": 0, "total_score": 0.0, "average": 0.0}
        for skill in SKILLS
    }
    per_lesson: dict[str, dict] = {}
    for state, vocab in pairs:
        mastery = state.get("mastery") or {}
        domain = domain_for_topic(vocab.get("domain") or vocab.get("topic"))
        level = vocab.get("level", "A1")
        lesson_id = f"{domain}-{str(level).lower()}"
        bucket = per_lesson.setdefault(
            lesson_id,
            {
                "lesson_id": lesson_id,
                "domain": domain,
                "level": level,
                "words": 0,
                "mastered": 0,
            },
        )
        bucket["words"] += 1
        if _is_mastered(mastery):
            bucket["mastered"] += 1
        for skill in SKILLS:
            score = float(mastery.get(skill, 0) or 0)
            skills[skill]["total_score"] += score
            if score > 0:
                skills[skill]["started"] += 1
            if score >= settings.MASTERY_THRESHOLD:
                skills[skill]["mastered"] += 1

    total_states = len(pairs)
    for skill in SKILLS:
        skills[skill]["average"] = (
            round(skills[skill]["total_score"] / total_states, 2)
            if total_states
            else 0.0
        )
        skills[skill].pop("total_score", None)

    return {
        "threshold": settings.MASTERY_THRESHOLD,
        "skills": skills,
        "lessons": sorted(per_lesson.values(), key=lambda x: (x["domain"], x["level"])),
    }


async def get_history(user_id: str, limit: int = 50) -> dict:
    db = get_database()
    items: list[dict] = []
    async for attempt in (
        db[ATTEMPTS]
        .find({"user_id": user_id})
        .sort("answered_at", -1)
        .limit(limit)
    ):
        items.append(
            {
                "type": "answer",
                "id": attempt.get("attempt_id"),
                "session_id": attempt.get("session_id"),
                "vocabulary_id": attempt.get("vocabulary_id"),
                "skill": attempt.get("skill"),
                "is_correct": bool(attempt.get("is_correct")),
                "submitted_answer": attempt.get("submitted_answer"),
                "answered_at": attempt.get("answered_at"),
            }
        )
    async for review in (
        db[REVIEWS]
        .find({"user_id": user_id})
        .sort("reviewed_at", -1)
        .limit(limit)
    ):
        items.append(
            {
                "type": "review",
                "id": review.get("review_id"),
                "vocabulary_id": review.get("vocabulary_id"),
                "rating": review.get("rating"),
                "reviewed_at": review.get("reviewed_at"),
            }
        )
    items.sort(key=lambda x: x.get("answered_at") or x.get("reviewed_at"), reverse=True)
    return {"items": items[:limit], "limit": limit}


async def add_xp(user_id: str, amount: int) -> dict:
    """Award a one-off bonus; per-answer XP is handled transactionally."""
    db = get_database()
    now = datetime.now(timezone.utc)
    user = await db[USERS].find_one({"_id": user_id}) or {}
    streak = _new_streak(user, now)
    from pymongo import ReturnDocument

    updated = await db[USERS].find_one_and_update(
        {"_id": user_id},
        {
            "$inc": {"xp": amount},
            "$set": {"streak": streak, "last_study_date": now},
        },
        return_document=ReturnDocument.AFTER,
    )
    if updated is None:
        raise ValueError("User not found")
    new_xp = int(updated.get("xp", 0))
    return {
        "xp": new_xp,
        "level": level_from_xp(new_xp),
        "streak": streak,
        "gained": amount,
    }
