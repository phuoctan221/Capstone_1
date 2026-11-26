"""Server-owned level assessment attempts and promotion rules."""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from pymongo import ReturnDocument

from app.core.config import settings
from app.core.domains import domain_for_topic
from app.db.mongodb import get_database
from app.services import exercise_service, lesson_service

ATTEMPTS = "level_assessment_attempts"
RESULTS = "level_assessment_results"
ASSESSMENT_SKILLS = ("meaning", "spelling")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _public_attempt(attempt: dict) -> dict:
    """Remove MongoDB-only fields before returning an attempt through the API."""
    return {key: value for key, value in attempt.items() if key != "_id"}


def _normalize_domains(domain: str, domains: list[str] | None) -> list[str]:
    raw = domains if domains else [domain]
    ordered: list[str] = []
    for entry in raw:
        norm = domain_for_topic(entry)
        if norm not in ordered:
            ordered.append(norm)
    return ordered or [domain_for_topic(domain)]


def _serialize_assessment_question(item: dict) -> dict:
    question = exercise_service.serialize_question(item)
    if len(question.get("options") or []) > 1:
        options = list(question["options"])
        random.shuffle(options)
        question["options"] = options
    return question


def _select_questions(items: list[dict], limit: int) -> list[dict]:
    """Pick up to ``limit`` items, maximizing unique words and avoiding consecutive repeats."""
    by_vocab: dict[str, list[dict]] = {}
    for item in items:
        by_vocab.setdefault(str(item.get("vocabulary_id")), []).append(item)

    vocab_ids = list(by_vocab)
    random.shuffle(vocab_ids)

    selected: list[dict] = []
    # Round 1: at most 1 question per unique word.
    for vid in vocab_ids:
        if len(selected) >= limit:
            break
        pool = by_vocab[vid]
        random.shuffle(pool)
        selected.append(pool.pop())

    # Round 2 (only if unique words < limit): fill from leftovers without adjacent duplicates.
    while len(selected) < limit:
        leftovers = [
            (vid, pool) for vid, pool in by_vocab.items() if pool
        ]
        if not leftovers:
            break
        random.shuffle(leftovers)
        last_vid = str(selected[-1].get("vocabulary_id")) if selected else None
        leftovers.sort(key=lambda pair: 1 if pair[0] == last_vid else 0)
        _, pool = leftovers[0]
        selected.append(pool.pop())

    return selected


async def _level_words(domain: str, level: str) -> list[dict]:
    return await lesson_service.get_lesson_words(domain, level)


async def _gather_assessment_words(
    domains: list[str], level: str, supplement_to_target: bool
) -> list[dict]:
    db = get_database()
    collected: list[dict] = []
    seen_ids: set[str] = set()

    def _add_words(docs: list[dict]) -> None:
        for doc in docs:
            wid = str(doc["_id"])
            if wid not in seen_ids:
                seen_ids.add(wid)
                collected.append(doc)

    for d in domains:
        _add_words(await _level_words(d, level))

    target_count = settings.ASSESSMENT_QUESTION_COUNT
    if (supplement_to_target and len(collected) < target_count) or len(collected) < 3:
        for fallback_domain in lesson_service.MVP_DOMAIN_ORDER:
            if fallback_domain not in domains:
                _add_words(await _level_words(fallback_domain, level))
                if len(collected) >= target_count:
                    break

    if (supplement_to_target and len(collected) < target_count) or len(collected) < 3:
        extra = [doc async for doc in db.vocabularies.find({"level": level}).sort("word", 1)]
        _add_words(extra)

    return collected


async def _completed_level(user_id: str, domain: str, level: str) -> bool:
    words = await _level_words(domain, level)
    if not words:
        return False
    progress = await lesson_service._lesson_progress(user_id)
    return lesson_service._lesson_completed(
        words, set(), progress.get(lesson_service.lesson_slug(domain, level))
    )


async def status(user_id: str, domain: str, level: str) -> dict:
    domain = domain_for_topic(domain)
    db = get_database()
    passed = await db[RESULTS].find_one({"user_id": user_id, "domain": domain, "level": level})
    completed = await _completed_level(user_id, domain, level)
    latest = await db[ATTEMPTS].find_one(
        {"user_id": user_id, "domain": domain, "level": level}, sort=[("created_at", -1)]
    )
    retry_at = None
    if latest and latest.get("submitted_at") and not latest.get("passed"):
        retry_at = latest["submitted_at"] + timedelta(minutes=settings.ASSESSMENT_RETRY_COOLDOWN_MINUTES)
    words = await _level_words(domain, level)
    progress = await lesson_service._lesson_progress(user_id)
    entry = progress.get(lesson_service.lesson_slug(domain, level))
    total_units = lesson_service.unit_count(len(words))
    completed_units = sum(
        1 for unit in range(1, total_units + 1)
        if lesson_service._unit_completed(lesson_service._unit_words(words, unit), set(), entry, unit)
    )
    return {
        "units_completed": completed_units,
        "units_total": total_units,
        "completed": completed, "passed": bool(passed),
        "assessment_required": completed and not bool(passed),
        "retry_at": retry_at,
    }


async def create_attempt(
    user_id: str,
    domain: str,
    level: str,
    skip_learning: bool = False,
    placement_target: str | None = None,
    domains: list[str] | None = None,
) -> dict:
    requested_domains = _normalize_domains(domain, domains)
    domain = requested_domains[0]
    level = level.upper()
    placement_target = (placement_target or "").upper() or None
    if placement_target and (
        placement_target not in lesson_service.VALID_LEVELS
        or placement_target != level
    ):
        raise ValueError("Placement target must match the assessment level")
    state = await status(user_id, domain, level)
    if state["passed"] and not placement_target:
        raise ValueError("Level assessment has already been passed")
    if not state["completed"] and not skip_learning and not placement_target:
        raise ValueError("Complete every unit in this level before taking the assessment")
    now = _now()
    if state["retry_at"] and state["retry_at"] > now:
        raise ValueError("Assessment retry cooldown is still active")

    supplement = bool(placement_target or skip_learning or len(requested_domains) > 1)
    words = await _gather_assessment_words(requested_domains, level, supplement)
    await exercise_service.ensure_exercise_bank(words, domain=None, level=level)
    vocab_ids = [str(word["_id"]) for word in words]
    db = get_database()
    items = [
        doc
        async for doc in db.exercise_items.find(
            {
                "vocabulary_id": {"$in": vocab_ids},
                "active": True,
                "skill": {"$in": list(ASSESSMENT_SKILLS)},
            }
        )
    ]
    if len(items) < 3:
        raise ValueError("Not enough assessment questions are available")
    selected = _select_questions(items, settings.ASSESSMENT_QUESTION_COUNT)
    attempt = {
        "attempt_id": uuid4().hex,
        "user_id": user_id,
        "domain": domain,
        "domains": requested_domains,
        "level": level,
        "item_ids": [item["exercise_item_id"] for item in selected],
        "skip_learning": skip_learning,
        "placement_target": placement_target,
        "status": "active",
        "created_at": now,
        "expires_at": now + timedelta(minutes=settings.ASSESSMENT_EXPIRE_MINUTES),
    }
    await db[ATTEMPTS].insert_one(attempt)
    return {
        **_public_attempt(attempt),
        "questions": [_serialize_assessment_question(item) for item in selected],
        "question_count": len(selected),
    }


async def get_attempt(user_id: str, attempt_id: str) -> dict | None:
    db = get_database()
    attempt = await db[ATTEMPTS].find_one({"attempt_id": attempt_id, "user_id": user_id})
    if not attempt or attempt.get("status") != "active" or attempt.get("expires_at") <= _now():
        return None
    items = await exercise_service.get_items_for_ids(attempt.get("item_ids") or [])
    if len(items) != len(attempt.get("item_ids") or []):
        return None
    return {
        **_public_attempt(attempt),
        "questions": [_serialize_assessment_question(item) for item in items],
        "question_count": len(items),
    }


async def submit_attempt(user_id: str, attempt_id: str, answers: list[dict]) -> dict:
    db = get_database()
    existing = await db[ATTEMPTS].find_one({"attempt_id": attempt_id, "user_id": user_id})
    if not existing:
        raise ValueError("Assessment attempt not found")
    if existing.get("status") == "submitted":
        return existing["result"]
    now = _now()
    if existing.get("expires_at") <= now:
        await db[ATTEMPTS].update_one({"_id": existing["_id"]}, {"$set": {"status": "expired"}})
        raise ValueError("Assessment attempt has expired")
    expected_ids = existing.get("item_ids") or []
    submitted = {answer["exercise_item_id"]: answer.get("answer", "") for answer in answers}
    if len(answers) != len(expected_ids) or set(submitted) != set(expected_ids) or len(submitted) != len(expected_ids):
        raise ValueError("Submit exactly the assessment questions that were issued")
    items = await exercise_service.get_items_for_ids(expected_ids)
    if len(items) != len(expected_ids):
        raise ValueError("Assessment question data is unavailable")
    details = []
    correct = 0
    for item in items:
        is_correct, correct_answer, _ = exercise_service.grade(item, submitted[item["exercise_item_id"]])
        correct += int(is_correct)
        details.append(
            {
                "exercise_item_id": item["exercise_item_id"],
                "vocabulary_id": item.get("vocabulary_id"),
                "skill": item.get("skill"),
                "prompt": item.get("prompt", ""),
                "cloze": item.get("cloze"),
                "options": list(item.get("options") or []),
                "correct": is_correct,
                "correct_answer": correct_answer,
                "user_answer": submitted[item["exercise_item_id"]],
            }
        )
    total = len(items)
    percent = round(correct / total * 100) if total else 0
    passed = percent >= settings.ASSESSMENT_PASS_PERCENT
    placement_target = existing.get("placement_target")
    next_level = lesson_service.next_level(existing["domain"], existing["level"])
    opened_level = placement_target or next_level
    result = {
        "attempt_id": attempt_id,
        "domain": existing["domain"],
        "domains": existing.get("domains") or [existing["domain"]],
        "level": existing["level"],
        "correct": correct,
        "total": total,
        "percent": percent,
        "passed": passed,
        "next_level": next_level,
        "opened_level": opened_level,
        "placement_target": placement_target,
        "results": details,
        "submitted_at": now,
    }
    updated = await db[ATTEMPTS].find_one_and_update(
        {"_id": existing["_id"], "status": "active"},
        {"$set": {"status": "submitted", "submitted_at": now, "passed": passed, "result": result}},
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
        replay = await db[ATTEMPTS].find_one({"_id": existing["_id"]})
        return replay["result"]
    if passed:
        if placement_target:
            user = await db.users.find_one({"_id": user_id}) or {}
            placements = lesson_service.placement_levels_for_user(
                user, list(lesson_service.MVP_DOMAIN_ORDER)
            )
            target_domains = existing.get("domains") or [existing["domain"]]
            for target_domain in target_domains:
                norm_domain = domain_for_topic(target_domain)
                current = placements.get(norm_domain, "A1")
                if lesson_service.LEVEL_ORDER[placement_target] > lesson_service.LEVEL_ORDER.get(current, 0):
                    placements[norm_domain] = placement_target
            learning_level = str(user.get("learning_level") or "A1").upper()
            if lesson_service.LEVEL_ORDER[placement_target] > lesson_service.LEVEL_ORDER.get(learning_level, 0):
                learning_level = placement_target
            await db.users.update_one(
                {"_id": user_id},
                {"$set": {"placement_levels": placements, "learning_level": learning_level, "updated_at": now}},
            )
        else:
            await db[RESULTS].update_one(
                {"user_id": user_id, "domain": existing["domain"], "level": existing["level"]},
                {"$set": {"passed_at": now, "attempt_id": attempt_id}}, upsert=True,
            )
            if next_level:
                await db.users.update_one({"_id": user_id}, {"$set": {"learning_level": next_level, "updated_at": now}})
    return result
