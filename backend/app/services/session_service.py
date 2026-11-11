"""Learning sessions: question delivery, answer submission and finishing."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from pymongo.errors import DuplicateKeyError

from app.core.config import settings
from app.db.mongodb import get_database
from app.services import exercise_service, learning_service, lesson_service, progress_service
from app.services.mastery_service import SKILLS_SET

SESSIONS = "learning_sessions"
ATTEMPTS = "answer_attempts"
PASS_PERCENT = 70


def serialize_session(doc: dict) -> dict:
    return {
        "session_id": doc["session_id"],
        "user_id": doc["user_id"],
        "lesson_id": doc["lesson_id"],
        "domain": doc.get("domain", "general"),
        "level": doc.get("level", "A1"),
        "skills": list(doc.get("skills") or []),
        "status": doc.get("status", "active"),
        "question_count": int(doc.get("question_count", 0)),
        "answered_count": int(doc.get("answered_count", 0)),
        "correct_count": int(doc.get("correct_count", 0)),
        "started_at": doc.get("started_at"),
        "finished_at": doc.get("finished_at"),
    }


async def _select_items(
    words: list[dict], skills: list[str], count: int
) -> list[dict]:
    domain = None
    level = None
    if words:
        domain = words[0].get("domain") or words[0].get("topic")
        level = words[0].get("level")
    await exercise_service.ensure_exercise_bank(words, domain=domain, level=level)
    vocab_ids = [str(w["_id"]) for w in words]
    db = get_database()
    items = [
        doc
        async for doc in db.exercise_items.find(
            {
                "vocabulary_id": {"$in": vocab_ids},
                "skill": {"$in": skills},
                "active": True,
            }
        ).sort("vocabulary_id", 1)
    ]
    by_skill: dict[str, list[dict]] = {skill: [] for skill in skills}
    for item in items:
        if item["skill"] in by_skill:
            by_skill[item["skill"]].append(item)

    selected: list[dict] = []
    seen: set[str] = set()

    # First pass: guarantee one item per available skill.
    for skill in skills:
        if by_skill[skill]:
            item = by_skill[skill][0]
            selected.append(item)
            seen.add(item["exercise_item_id"])

    # Then round-robin through the remaining bank until count is reached.
    while len(selected) < count:
        progressed = False
        for skill in skills:
            for item in by_skill[skill]:
                if item["exercise_item_id"] in seen:
                    continue
                selected.append(item)
                seen.add(item["exercise_item_id"])
                progressed = True
                break
            if len(selected) >= count:
                break
        if not progressed:
            break
    return selected[:count]


async def create_session(
    user_id: str, lesson_id: str, skills: list[str], count: int
) -> dict:
    lesson = await lesson_service.get_lesson(lesson_id, user_id)
    if not lesson:
        raise ValueError("Lesson not found")
    domain_slug, level = lesson_service.parse_lesson_id(lesson_id)
    if level is None:
        raise ValueError("Lesson not found")

    requested = [skill for skill in skills if skill in SKILLS_SET]
    if not requested:
        raise ValueError("At least one valid skill is required")

    words = await lesson_service.get_lesson_words(lesson["domain"], level)
    if len(words) < settings.MIN_LESSON_WORDS:
        raise ValueError("Lesson does not have enough words for exercises")

    items = await _select_items(words, requested, count)
    if not items:
        raise ValueError("No exercise items available for this lesson")

    # Starting a word initialises its FSRS state; it does not schedule a review.
    for vocab_id in {item["vocabulary_id"] for item in items}:
        await learning_service.ensure_state(user_id, vocab_id)

    now = datetime.now(timezone.utc)
    session = {
        "session_id": str(uuid4()),
        "user_id": user_id,
        "lesson_id": lesson_id,
        "domain": lesson["domain"],
        "level": level,
        "skills": requested,
        "exercise_item_ids": [item["exercise_item_id"] for item in items],
        "attempt_ids": [],
        "status": "active",
        "question_count": len(items),
        "answered_count": 0,
        "correct_count": 0,
        "started_at": now,
        "finished_at": None,
    }
    db = get_database()
    await db[SESSIONS].insert_one(session)
    return {
        **serialize_session(session),
        "exercises": [exercise_service.serialize_question(item) for item in items],
    }


async def get_session(user_id: str, session_id: str) -> dict | None:
    db = get_database()
    return await db[SESSIONS].find_one(
        {"session_id": session_id, "user_id": user_id}
    )


async def get_session_exercises(user_id: str, session_id: str) -> dict | None:
    session = await get_session(user_id, session_id)
    if not session:
        return None
    items = await exercise_service.get_items_for_ids(
        list(session.get("exercise_item_ids") or [])
    )
    return {
        **serialize_session(session),
        "exercises": [exercise_service.serialize_question(item) for item in items],
    }


async def submit_answer(
    user_id: str,
    session_id: str,
    exercise_item_id: str,
    answer: str,
    attempt_id: str,
    response_time_ms: int = 0,
    hint_used: bool = False,
) -> dict:
    db = get_database()
    session = await get_session(user_id, session_id)
    if not session:
        raise ValueError("Session not found")
    if session.get("status") != "active":
        raise ValueError("Session is already finished")
    if exercise_item_id not in (session.get("exercise_item_ids") or []):
        raise ValueError("Exercise item does not belong to this session")

    item = await db.exercise_items.find_one(
        {"exercise_item_id": exercise_item_id}
    )
    if not item:
        raise ValueError("Exercise item not found")

    result = await progress_service.process_answer(
        user_id=user_id,
        vocabulary_id=item["vocabulary_id"],
        skill=item["skill"],
        submitted_answer=answer,
        attempt_id=attempt_id,
        session_id=session_id,
        exercise_item_id=exercise_item_id,
        response_time_ms=response_time_ms,
        hint_used=hint_used,
        exercise_item=item,
    )

    # Guarded by attempt_ids so a retried attempt never increments twice.
    await db[SESSIONS].update_one(
        {
            "session_id": session_id,
            "user_id": user_id,
            "attempt_ids": {"$ne": attempt_id},
        },
        {
            "$inc": {
                "answered_count": 1,
                "correct_count": 1 if result.get("is_correct") else 0,
            },
            "$push": {"attempt_ids": attempt_id},
        },
    )
    return result


async def finish_session(user_id: str, session_id: str) -> dict:
    db = get_database()
    session = await get_session(user_id, session_id)
    if not session:
        raise ValueError("Session not found")

    if session.get("status") == "finished":
        return session.get("finish_result") or _finish_payload(session)

    total = int(session.get("question_count", 0))
    answered = int(session.get("answered_count", 0))
    correct = int(session.get("correct_count", 0))
    percent = round(correct / total * 100) if total else 0
    passed = percent >= PASS_PERCENT
    now = datetime.now(timezone.utc)

    lesson_completed = False
    xp_gained = 0
    if passed:
        lesson = await lesson_service.get_lesson(session["lesson_id"], user_id)
        learned_count = int((lesson or {}).get("learned_count", 0))
        mastered_count = int((lesson or {}).get("mastered_count", 0))
        lesson_completed = await progress_service.complete_lesson(
            user_id,
            session["lesson_id"],
            session.get("domain", "general"),
            True,
            learned_count,
            mastered_count,
        )
        if lesson_completed:
            bonus = await progress_service.add_xp(
                user_id, progress_service.XP_PER_LESSON_BONUS
            )
            xp_gained = int(bonus.get("gained", 0))

    payload = {
        "session_id": session_id,
        "status": "finished",
        "total": total,
        "answered": answered,
        "correct": correct,
        "percent": percent,
        "passed": passed,
        "xp_gained": xp_gained,
        "lesson_completed": lesson_completed,
        "finished_at": now,
    }
    try:
        await db[SESSIONS].update_one(
            {"session_id": session_id, "user_id": user_id, "status": "active"},
            {
                "$set": {
                    "status": "finished",
                    "finished_at": now,
                    "finish_result": payload,
                }
            },
        )
    except DuplicateKeyError:
        pass
    return payload


def _finish_payload(session: dict) -> dict:
    total = int(session.get("question_count", 0))
    correct = int(session.get("correct_count", 0))
    return {
        "session_id": session["session_id"],
        "status": "finished",
        "total": total,
        "answered": int(session.get("answered_count", 0)),
        "correct": correct,
        "percent": round(correct / total * 100) if total else 0,
        "passed": (round(correct / total * 100) if total else 0) >= PASS_PERCENT,
        "xp_gained": 0,
        "lesson_completed": False,
        "finished_at": session.get("finished_at"),
    }
