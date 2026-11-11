import re
import secrets
import string
from datetime import datetime, timezone
from uuid import uuid4

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status

from app.core.config import settings
from app.core.domains import DOMAINS, MVP_DOMAIN_ORDER, domain_for_topic
from app.db.mongodb import get_database
from app.models.admin import (
    AdminUserStatus,
    AdminUserUpdate,
    DomainUpdate,
    ExerciseItemCreate,
    ExerciseItemUpdate,
    RoleUpdate,
)
from app.models.lesson import LessonCreate, LessonUpdate
from app.models.vocabulary import VocabularyCreate, VocabularyUpdate
from app.services import (
    domain_service,
    exercise_service,
    lesson_service,
    learning_service,
    progress_service,
    vocabulary_service,
)
from app.services.auth_service import hash_password, normalize_role, require_admin

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)

# Collections that store per-user learning data and must follow the account
# when it is renamed (email = _id) or deleted.
USER_DATA_COLLECTIONS = [
    "user_word_states",
    "answer_attempts",
    "learning_sessions",
    "fsrs_review_logs",
    "lesson_progress",
    "quiz_questions",
]

VALID_INTERESTS = {
    "technology",
    "business",
    "travel",
    "science",
    "academic",
    "daily-life",
    "general",
}


def _clean_user(doc: dict) -> dict:
    doc.pop("password_hash", None)
    doc["id"] = str(doc.pop("_id"))
    doc["role"] = normalize_role(doc.get("role"))
    doc["interests"] = doc.get("interests") or []
    doc["onboarded"] = bool(doc.get("onboarded"))
    doc["xp"] = int(doc.get("xp", 0) or 0)
    doc["streak"] = int(doc.get("streak", 0) or 0)
    doc["daily_goal"] = int(doc.get("daily_goal", 10) or 10)
    doc["is_active"] = doc.get("is_active", True) is not False
    return doc


def _clean_exercise(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    doc["options"] = list(doc.get("options") or [])
    doc["accepted_answers"] = list(doc.get("accepted_answers") or [])
    doc["active"] = bool(doc.get("active", True))
    return doc


def _validate_exercise(skill: str, options: list[str], correct: str) -> None:
    if skill == "meaning":
        cleaned = [str(option).strip() for option in options if str(option).strip()]
        if len(cleaned) < exercise_service.MIN_OPTIONS:
            raise HTTPException(
                status_code=400,
                detail="Meaning questions need at least two options",
            )
        if correct.strip().casefold() not in {option.casefold() for option in cleaned}:
            raise HTTPException(
                status_code=400,
                detail="The correct answer must be one of the options",
            )


def _accepted_answers(correct: str, provided: list[str] | None) -> list[str]:
    result: list[str] = []
    for value in [correct, *(provided or [])]:
        cleaned = str(value).strip()
        if cleaned and cleaned.casefold() not in {item.casefold() for item in result}:
            result.append(cleaned)
    return result


def _parse_vocab_id(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=400, detail="Invalid vocabulary id")


# --- dashboard ---------------------------------------------------------


@router.get("/stats")
async def admin_stats():
    db = get_database()

    users_total = await db.users.count_documents({})
    admins = await db.users.count_documents({"role": "admin"})

    vocab_by_domain: dict[str, int] = {}
    for slug in MVP_DOMAIN_ORDER:
        vocab_by_domain[slug] = await db.vocabularies.count_documents(
            lesson_service.domain_query(slug)
        )

    vocab_by_level: dict[str, int] = {}
    async for row in db.vocabularies.aggregate(
        [{"$group": {"_id": "$level", "count": {"$sum": 1}}}]
    ):
        vocab_by_level[row["_id"] or "A1"] = row["count"]

    derived_lessons = 0
    for slug in MVP_DOMAIN_ORDER:
        async for _row in db.vocabularies.aggregate(
            [
                {"$match": lesson_service.domain_query(slug)},
                {"$group": {"_id": "$level"}},
            ]
        ):
            derived_lessons += 1
    metadata_lessons = await db.lessons.count_documents({})

    exercises_total = await db.exercise_items.count_documents({})
    exercises_active = await db.exercise_items.count_documents({"active": {"$ne": False}})
    exercises_by_skill = {"meaning": 0, "spelling": 0, "context": 0}
    async for row in db.exercise_items.aggregate(
        [{"$group": {"_id": "$skill", "count": {"$sum": 1}}}]
    ):
        if row["_id"] in exercises_by_skill:
            exercises_by_skill[row["_id"]] = row["count"]
    exercises_by_domain: dict[str, int] = {}
    async for row in db.exercise_items.aggregate(
        [{"$group": {"_id": "$domain", "count": {"$sum": 1}}}]
    ):
        key = domain_for_topic(row["_id"])
        exercises_by_domain[key] = exercises_by_domain.get(key, 0) + row["count"]
    lessons_with_exercises = len(await _exercise_counts())

    recent_users = []
    async for doc in db.users.find({}, {"password_hash": 0}).sort("created_at", -1).limit(5):
        recent_users.append(_clean_user(doc))

    return {
        "users": {
            "total": users_total,
            "admins": admins,
            "regular": max(users_total - admins, 0),
            "recent": recent_users,
        },
        "vocabularies": {
            "total": sum(vocab_by_domain.values()),
            "by_domain": vocab_by_domain,
            "by_level": vocab_by_level,
        },
        "lessons": {
            "total": derived_lessons,
            "metadata": metadata_lessons,
            "with_exercises": lessons_with_exercises,
        },
        "exercises": {
            "total": exercises_total,
            "active": exercises_active,
            "by_skill": exercises_by_skill,
            "by_domain": exercises_by_domain,
        },
    }


# --- shared vocabulary -------------------------------------------------


@router.get("/vocabularies")
async def admin_list_vocabularies(
    domain: str | None = None,
    level: str | None = None,
    search: str | None = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    return await vocabulary_service.list_vocabularies(
        domain=domain,
        level=level,
        search=search,
        page=page,
        page_size=page_size,
    )


@router.post("/vocabularies", status_code=status.HTTP_201_CREATED)
async def admin_create_vocabulary(data: VocabularyCreate):
    return await vocabulary_service.create_vocabulary(data)


@router.put("/vocabularies/{vocab_id}")
async def admin_update_vocabulary(vocab_id: str, data: VocabularyUpdate):
    vocab = await vocabulary_service.update_vocabulary(vocab_id, data)
    if not vocab:
        raise HTTPException(status_code=404, detail="Vocabulary not found")
    return vocab


@router.delete("/vocabularies/{vocab_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_vocabulary(vocab_id: str):
    deleted = await vocabulary_service.delete_vocabulary(vocab_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Vocabulary not found")


# --- lessons -----------------------------------------------------------


async def _lesson_counts() -> dict[tuple[str, str], int]:
    db = get_database()
    counts: dict[tuple[str, str], int] = {}
    for slug in MVP_DOMAIN_ORDER:
        async for row in db.vocabularies.aggregate(
            [
                {"$match": lesson_service.domain_query(slug)},
                {"$group": {"_id": "$level", "count": {"$sum": 1}}},
            ]
        ):
            counts[(slug, row["_id"] or "A1")] = row["count"]
    return counts


async def _exercise_counts() -> dict[tuple[str, str], int]:
    db = get_database()
    counts: dict[tuple[str, str], int] = {}
    async for row in db.exercise_items.aggregate(
        [
            {
                "$group": {
                    "_id": {"domain": "$domain", "level": "$level"},
                    "count": {"$sum": 1},
                }
            }
        ]
    ):
        key = (
            domain_for_topic((row["_id"] or {}).get("domain")),
            (row["_id"] or {}).get("level") or "A1",
        )
        counts[key] = counts.get(key, 0) + row["count"]
    return counts


@router.get("/lessons")
async def admin_list_lessons():
    db = get_database()
    counts = await _lesson_counts()
    exercise_counts = await _exercise_counts()

    metadata: dict[str, dict] = {}
    async for doc in db.lessons.find({}):
        slug = doc.get("slug")
        if slug:
            metadata[slug] = doc
        else:
            domain_slug, level = lesson_service.parse_lesson_id(str(doc.get("_id", "")))
            if level:
                metadata[lesson_service.lesson_slug(domain_slug, level)] = doc

    levels: dict[str, set[str]] = {slug: set() for slug in MVP_DOMAIN_ORDER}
    for domain_slug, level in counts:
        levels.setdefault(domain_slug, set()).add(level)
    for slug, doc in metadata.items():
        domain_slug, level = lesson_service.parse_lesson_id(slug)
        if domain_slug in DOMAINS and level:
            levels.setdefault(domain_slug, set()).add(level)

    lessons = []
    order = 0
    for domain_slug in MVP_DOMAIN_ORDER:
        meta = DOMAINS[domain_slug]
        for level in sorted(
            levels.get(domain_slug, set()),
            key=lambda value: lesson_service.LEVEL_ORDER.get(value, 99),
        ):
            slug = lesson_service.lesson_slug(domain_slug, level)
            doc = metadata.get(slug, {})
            word_count = counts.get((domain_slug, level), 0)
            exercise_count = exercise_counts.get((domain_slug, level), 0)
            lessons.append(
                {
                    "id": slug,
                    "slug": slug,
                    "domain": domain_slug,
                    "topic": domain_slug,
                    "topic_title": meta["name"],
                    "level": level,
                    "title": doc.get("title") or f"{meta['name']} - {level}",
                    "description": doc.get("description")
                    or f"{word_count} từ vựng {meta['name']} cấp độ {level}",
                    "order": doc.get("order", order),
                    "word_count": word_count,
                    "exercise_count": exercise_count,
                    "has_exercises": word_count >= settings.MIN_LESSON_WORDS,
                    "metadata_exists": slug in metadata,
                    "created_at": doc.get("created_at"),
                    "updated_at": doc.get("updated_at"),
                }
            )
            order += 1

    return lessons


@router.post("/lessons", status_code=status.HTTP_201_CREATED)
async def admin_create_lesson(data: LessonCreate):
    db = get_database()
    slug = lesson_service.lesson_slug(data.domain, data.level)
    meta = DOMAINS[data.domain]
    now = datetime.now(timezone.utc)
    doc = {
        "slug": slug,
        "domain": data.domain,
        "topic": data.domain,
        "level": data.level,
        "title": data.title or f"{meta['name']} - {data.level}",
        "description": data.description or f"{meta['name']} {data.level}",
        "order": data.order,
        "updated_at": now,
    }
    await db.lessons.update_one(
        {"slug": slug},
        {"$set": doc, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    return {**doc, "id": slug, "word_count": 0, "exercise_count": 0}


@router.put("/lessons/{lesson_id}")
async def admin_update_lesson(lesson_id: str, data: LessonUpdate):
    domain_slug, level = lesson_service.parse_lesson_id(lesson_id)
    if domain_slug not in DOMAINS or level is None:
        raise HTTPException(status_code=400, detail="Invalid lesson id")

    db = get_database()
    updates = data.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    meta = DOMAINS[domain_slug]
    now = datetime.now(timezone.utc)
    updates["updated_at"] = now
    existing = await db.lessons.find_one({"slug": lesson_id})
    if existing:
        await db.lessons.update_one({"slug": lesson_id}, {"$set": updates})
    else:
        words = await lesson_service.get_lesson_words(domain_slug, level)
        if not words:
            raise HTTPException(status_code=404, detail="Lesson not found")
        await db.lessons.insert_one(
            {
                "slug": lesson_id,
                "domain": domain_slug,
                "topic": domain_slug,
                "level": level,
                "title": f"{meta['name']} - {level}",
                "description": f"{meta['name']} {level}",
                "created_at": now,
                **updates,
            }
        )

    doc = await db.lessons.find_one({"slug": lesson_id})
    raw_id = doc.pop("_id", None)
    doc["id"] = doc.get("slug") or str(raw_id)
    return doc


@router.delete("/lessons/{lesson_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_lesson(lesson_id: str):
    domain_slug, level = lesson_service.parse_lesson_id(lesson_id)
    if domain_slug not in DOMAINS or level is None:
        raise HTTPException(status_code=400, detail="Invalid lesson id")

    db = get_database()
    word_count = await db.vocabularies.count_documents(
        {
            "$and": [
                lesson_service.domain_query(domain_slug),
                {"level": level},
            ]
        }
    )
    if word_count:
        raise HTTPException(
            status_code=409,
            detail=(
                "Bài học còn từ vựng. Hãy chuyển hoặc xoá từ vựng trước khi xoá bài học."
            ),
        )
    result = await db.lessons.delete_one({"slug": lesson_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Lesson not found")


@router.get("/lessons/{lesson_id}/words")
async def admin_lesson_words(
    lesson_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    domain_slug, level = lesson_service.parse_lesson_id(lesson_id)
    if domain_slug not in DOMAINS or level is None:
        raise HTTPException(status_code=400, detail="Invalid lesson id")
    words = await lesson_service.get_lesson_words(domain_slug, level)
    total = len(words)
    start = (page - 1) * page_size
    page_words = words[start : start + page_size]
    return {
        "lesson_id": lesson_service.lesson_slug(domain_slug, level),
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [lesson_service._word_out(word) for word in page_words],
    }


# --- exercises ---------------------------------------------------------


def _exercise_query(
    lesson_id: str | None,
    domain: str | None,
    level: str | None,
    skill: str | None,
    active: bool | None,
    search: str | None,
) -> dict:
    query: dict = {}
    if lesson_id:
        domain_slug, parsed_level = lesson_service.parse_lesson_id(lesson_id)
        domain = domain_slug
        level = parsed_level
    if domain:
        query["domain"] = domain_for_topic(domain)
    if level:
        query["level"] = level
    if skill:
        query["skill"] = skill
    if active is not None:
        query["active"] = active
    if search:
        pattern = re.escape(search.strip())
        query["$or"] = [
            {"word": {"$regex": pattern, "$options": "i"}},
            {"prompt": {"$regex": pattern, "$options": "i"}},
        ]
    return query


@router.post("/exercises/regenerate")
async def admin_regenerate_exercises(lesson_id: str = Query(...)):
    domain_slug, level = lesson_service.parse_lesson_id(lesson_id)
    if level is None:
        raise HTTPException(status_code=400, detail="Invalid lesson id")
    domain = domain_for_topic(domain_slug)
    words = await lesson_service.get_lesson_words(domain, level)
    if not words:
        raise HTTPException(status_code=404, detail="Lesson has no words")
    count = await exercise_service.ensure_exercise_bank(words, domain=domain, level=level)
    return {"lesson_id": lesson_service.lesson_slug(domain, level), "items": count}


@router.get("/exercises")
async def admin_list_exercises(
    lesson_id: str | None = None,
    domain: str | None = None,
    level: str | None = None,
    skill: str | None = None,
    active: bool | None = None,
    search: str | None = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    db = get_database()
    query = _exercise_query(lesson_id, domain, level, skill, active, search)
    total = await db.exercise_items.count_documents(query)
    cursor = (
        db.exercise_items.find(query)
        .sort([("domain", 1), ("level", 1), ("exercise_item_id", 1)])
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    items = []
    async for doc in cursor:
        items.append(_clean_exercise(doc))
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.post("/exercises", status_code=status.HTTP_201_CREATED)
async def admin_create_exercise(data: ExerciseItemCreate):
    db = get_database()
    vocab = await db.vocabularies.find_one({"_id": _parse_vocab_id(data.vocabulary_id)})
    if not vocab:
        raise HTTPException(status_code=404, detail="Vocabulary not found")

    item_id = data.exercise_item_id or f"custom:{uuid4().hex}"
    if await db.exercise_items.find_one({"exercise_item_id": item_id}):
        raise HTTPException(status_code=409, detail="Exercise item already exists")

    correct = data.correct_answer.strip()
    options = [str(option).strip() for option in data.options if str(option).strip()]
    _validate_exercise(data.skill, options, correct)
    domain = domain_for_topic(vocab.get("domain") or vocab.get("topic"))
    now = datetime.now(timezone.utc)
    doc = {
        "exercise_item_id": item_id,
        "vocabulary_id": data.vocabulary_id,
        "skill": data.skill,
        "domain": domain,
        "level": vocab.get("level") or "A1",
        "word": vocab.get("word", ""),
        "meaning": vocab.get("meaning", ""),
        "prompt": data.prompt.strip(),
        "options": options,
        "correct_answer": correct,
        "accepted_answers": _accepted_answers(correct, data.accepted_answers),
        "cloze": data.cloze,
        "hint": data.hint,
        "active": data.active,
        "created_at": now,
        "updated_at": now,
    }
    result = await db.exercise_items.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _clean_exercise(doc)


@router.get("/exercises/{item_id}")
async def admin_get_exercise(item_id: str):
    db = get_database()
    doc = await db.exercise_items.find_one({"exercise_item_id": item_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Exercise item not found")
    return _clean_exercise(doc)


@router.put("/exercises/{item_id}")
async def admin_update_exercise(item_id: str, data: ExerciseItemUpdate):
    db = get_database()
    existing = await db.exercise_items.find_one({"exercise_item_id": item_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Exercise item not found")

    updates = data.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    if "prompt" in updates:
        updates["prompt"] = updates["prompt"].strip()
    if "correct_answer" in updates:
        updates["correct_answer"] = updates["correct_answer"].strip()
    if "options" in updates:
        updates["options"] = [
            str(option).strip() for option in updates["options"] if str(option).strip()
        ]

    correct = updates.get("correct_answer", existing.get("correct_answer", ""))
    options = updates.get("options", list(existing.get("options") or []))
    _validate_exercise(existing.get("skill", ""), options, correct)
    if "correct_answer" in updates or "accepted_answers" in updates:
        updates["accepted_answers"] = _accepted_answers(
            correct,
            updates.get("accepted_answers", existing.get("accepted_answers")),
        )

    updates["updated_at"] = datetime.now(timezone.utc)
    await db.exercise_items.update_one(
        {"exercise_item_id": item_id}, {"$set": updates}
    )
    doc = await db.exercise_items.find_one({"exercise_item_id": item_id})
    return _clean_exercise(doc)


@router.delete("/exercises/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_exercise(item_id: str):
    db = get_database()
    result = await db.exercise_items.delete_one({"exercise_item_id": item_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Exercise item not found")


# --- users -------------------------------------------------------------


@router.get("/users")
async def admin_list_users(
    search: str | None = Query(None, max_length=100),
    role: str | None = Query(None, pattern="^(user|admin)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    db = get_database()
    query: dict = {}
    if role == "admin":
        query["role"] = "admin"
    elif role == "user":
        query["$or"] = [{"role": "user"}, {"role": {"$exists": False}}]
    if search:
        pattern = re.escape(search.strip())
        search_query = {
            "$or": [
                {"email": {"$regex": pattern, "$options": "i"}},
                {"username": {"$regex": pattern, "$options": "i"}},
            ]
        }
        if "$or" in query:
            query = {"$and": [query, search_query]}
        else:
            query.update(search_query)
    total = await db.users.count_documents(query)
    cursor = (
        db.users.find(query, {"password_hash": 0})
        .sort("created_at", -1)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    items = []
    async for doc in cursor:
        items.append(_clean_user(doc))
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.put("/users/{user_id}/role")
async def admin_set_role(
    user_id: str,
    role: str | None = Query(None),
    payload: RoleUpdate | None = Body(None),
    admin: dict = Depends(require_admin),
):
    value = payload.role if payload is not None else role
    if value not in ("user", "admin"):
        raise HTTPException(status_code=400, detail="Role must be user or admin")

    db = get_database()
    user = await db.users.find_one({"_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    current_role = normalize_role(user.get("role"))
    if value == "user" and current_role == "admin":
        if user_id == admin["id"]:
            raise HTTPException(
                status_code=400, detail="You cannot remove your own admin role"
            )
        admin_count = await db.users.count_documents({"role": "admin"})
        if admin_count <= 1:
            raise HTTPException(
                status_code=400, detail="Cannot demote the last admin"
            )
    await db.users.update_one(
        {"_id": user_id},
        {"$set": {"role": value, "updated_at": datetime.now(timezone.utc)}},
    )
    return {"id": user_id, "role": value}


@router.get("/users/{user_id}")
async def admin_user_detail(user_id: str):
    db = get_database()
    user = await db.users.find_one({"_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    summary = await progress_service.get_summary(user_id)
    mastery = await progress_service.get_mastery_breakdown(user_id)
    history = await progress_service.get_history(user_id, limit=20)
    fsrs = await learning_service.get_stats(user_id)

    # Attach the word text to each history item so the admin sees what was
    # answered/reviewed without extra round-trips from the client.
    vocab_ids = {
        item["vocabulary_id"]
        for item in history.get("items", [])
        if item.get("vocabulary_id")
    }
    words: dict[str, str] = {}
    object_ids = []
    for value in vocab_ids:
        try:
            object_ids.append(ObjectId(value))
        except (InvalidId, TypeError):
            continue
    if object_ids:
        cursor = db.vocabularies.find({"_id": {"$in": object_ids}}, {"word": 1})
        async for doc in cursor:
            words[str(doc["_id"])] = doc.get("word", "")
    for item in history.get("items", []):
        item["word"] = words.get(str(item.get("vocabulary_id") or "")) or None

    return {
        "user": _clean_user(user),
        "summary": summary,
        "mastery": mastery,
        "history": history,
        "fsrs": fsrs,
    }


def _validate_user_updates(payload: AdminUserUpdate) -> dict:
    updates: dict = {}
    if payload.username is not None:
        username = payload.username.strip()
        if len(username) < 3 or len(username) > 30 or any(ord(c) < 32 for c in username):
            raise HTTPException(
                status_code=400, detail="Tên hiển thị phải từ 3 đến 30 ký tự"
            )
        updates["username"] = username
    if payload.email is not None:
        updates["email"] = payload.email.strip().lower()
    if payload.learning_level is not None:
        updates["learning_level"] = payload.learning_level
    if payload.interests is not None:
        interests: list[str] = []
        for interest in payload.interests:
            value = str(interest or "").strip().lower()
            if value and value not in interests:
                interests.append(value)
        invalid = [value for value in interests if value not in VALID_INTERESTS]
        if invalid:
            raise HTTPException(
                status_code=422,
                detail="Lĩnh vực không hợp lệ: " + ", ".join(invalid),
            )
        if not interests:
            raise HTTPException(
                status_code=422, detail="Vui lòng chọn ít nhất một lĩnh vực"
            )
        updates["interests"] = interests
    if payload.daily_goal is not None:
        updates["daily_goal"] = int(payload.daily_goal)
    return updates


@router.put("/users/{user_id}")
async def admin_update_user(
    user_id: str,
    payload: AdminUserUpdate,
    admin: dict = Depends(require_admin),
):
    db = get_database()
    user = await db.users.find_one({"_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    updates = _validate_user_updates(payload)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    new_email = updates.get("email")
    if new_email is not None and new_email != user_id:
        existing = await db.users.find_one({"_id": new_email})
        if existing:
            raise HTTPException(status_code=409, detail="Email already registered")

    updates["updated_at"] = datetime.now(timezone.utc)
    if new_email is not None and new_email != user_id:
        # Email doubles as the primary key (_id): copy the profile under the
        # new id, migrate every collection referencing the old id, drop old.
        doc = dict(user)
        doc.pop("_id", None)
        doc.update(updates)
        doc["_id"] = new_email
        await db.users.insert_one(doc)
        for collection in USER_DATA_COLLECTIONS:
            await db[collection].update_many(
                {"user_id": user_id}, {"$set": {"user_id": new_email}}
            )
        await db.users.delete_one({"_id": user_id})
        updated = await db.users.find_one({"_id": new_email})
    else:
        await db.users.update_one({"_id": user_id}, {"$set": updates})
        updated = await db.users.find_one({"_id": user_id})
    return _clean_user(updated)


@router.delete("/users/{user_id}")
async def admin_delete_user(
    user_id: str,
    admin: dict = Depends(require_admin),
):
    db = get_database()
    user = await db.users.find_one({"_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")
    if normalize_role(user.get("role")) == "admin":
        admin_count = await db.users.count_documents({"role": "admin"})
        if admin_count <= 1:
            raise HTTPException(
                status_code=400, detail="Cannot delete the last admin"
            )
    deleted: dict[str, int] = {}
    for collection in USER_DATA_COLLECTIONS:
        result = await db[collection].delete_many({"user_id": user_id})
        deleted[collection] = result.deleted_count
    result = await db.users.delete_one({"_id": user_id})
    deleted["users"] = result.deleted_count
    return {"id": user_id, "deleted": deleted}


@router.post("/users/{user_id}/reset-password")
async def admin_reset_password(
    user_id: str,
    admin: dict = Depends(require_admin),
):
    db = get_database()
    user = await db.users.find_one({"_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    alphabet = string.ascii_letters + string.digits
    password = "".join(secrets.choice(alphabet) for _ in range(10))
    await db.users.update_one(
        {"_id": user_id},
        {
            "$set": {
                "password_hash": hash_password(password),
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )
    # Plain password is returned exactly once so the admin can hand it over.
    return {"id": user_id, "email": user.get("email"), "password": password}


@router.put("/users/{user_id}/status")
async def admin_set_user_status(
    user_id: str,
    payload: AdminUserStatus,
    admin: dict = Depends(require_admin),
):
    db = get_database()
    user = await db.users.find_one({"_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not payload.is_active:
        if user_id == admin["id"]:
            raise HTTPException(status_code=400, detail="You cannot lock your own account")
        if normalize_role(user.get("role")) == "admin":
            active_admins = await db.users.count_documents(
                {"role": "admin", "is_active": {"$ne": False}}
            )
            if active_admins <= 1:
                raise HTTPException(
                    status_code=400, detail="Cannot lock the last active admin"
                )
    await db.users.update_one(
        {"_id": user_id},
        {
            "$set": {
                "is_active": bool(payload.is_active),
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )
    return {"id": user_id, "is_active": bool(payload.is_active)}


# --- domains -----------------------------------------------------------


@router.get("/domains")
async def admin_list_domains():
    return await domain_service.list_domains(include_inactive=True)


@router.put("/domains/{slug}")
async def admin_update_domain(slug: str, data: DomainUpdate):
    updates = data.model_dump(exclude_none=True)
    updated = await domain_service.update_domain(slug, updates)
    if updated is None:
        raise HTTPException(status_code=404, detail="Domain not found")
    return updated


@router.post("/domains/ensure")
async def admin_ensure_domains():
    return {"domains": await domain_service.ensure_domains()}
