from datetime import datetime, timezone, date

from app.db.mongodb import get_database
from app.services.lesson_service import LESSON_PROGRESS, PROGRESS

USERS = "users"

XP_PER_CORRECT = 10
XP_PER_LESSON_BONUS = 50

LEVEL_THRESHOLDS = [0, 100, 250, 500, 900, 1400, 2000, 2800, 3800, 5000]


def level_from_xp(xp: int) -> int:
    level = 1
    for i, threshold in enumerate(LEVEL_THRESHOLDS):
        if xp >= threshold:
            level = i + 1
    return level


async def get_user_progress(user_id: str) -> dict:
    db = get_database()
    user = await db[USERS].find_one({"_id": user_id}) or {}

    words_learned = await db[PROGRESS].count_documents(
        {"user_id": user_id, "box": {"$gte": 3}}
    )
    words_mastered = await db[PROGRESS].count_documents(
        {"user_id": user_id, "box": 5}
    )
    lessons_completed = await db[LESSON_PROGRESS].count_documents(
        {"user_id": user_id, "completed": True}
    )

    xp = user.get("xp", 0)
    return {
        "xp": xp,
        "level": level_from_xp(xp),
        "streak": user.get("streak", 0),
        "last_study_date": user.get("last_study_date"),
        "words_learned": words_learned,
        "words_mastered": words_mastered,
        "lessons_completed": lessons_completed,
    }


async def add_xp(user_id: str, amount: int) -> dict:
    db = get_database()
    user = await db[USERS].find_one({"_id": user_id}) or {}
    old_xp = user.get("xp", 0)
    new_xp = old_xp + amount

    today = date.today()
    last = user.get("last_study_date")
    streak = user.get("streak", 0)
    if last is None:
        streak = 1
    else:
        last_date = last.date() if isinstance(last, datetime) else last
        delta = (today - last_date).days
        if delta == 1:
            streak += 1
        elif delta > 1:
            streak = 1

    await db[USERS].update_one(
        {"_id": user_id},
        {
            "$set": {
                "xp": new_xp,
                "streak": streak,
                "last_study_date": datetime.now(timezone.utc),
            }
        },
    )
    return {
        "xp": new_xp,
        "level": level_from_xp(new_xp),
        "streak": streak,
        "gained": amount,
    }


async def mark_word_correct(user_id: str, vocabulary_id: str) -> None:
    from app.services import learning_service

    await learning_service.review_card(user_id, vocabulary_id, True)


async def mark_word_wrong(user_id: str, vocabulary_id: str) -> None:
    from app.services import learning_service

    await learning_service.review_card(user_id, vocabulary_id, False)


async def complete_lesson(user_id: str, topic: str, passed: bool) -> None:
    db = get_database()
    await db[LESSON_PROGRESS].update_one(
        {"user_id": user_id, "topic": topic},
        {
            "$set": {
                "completed": passed,
                "completed_at": datetime.now(timezone.utc),
            }
        },
        upsert=True,
    )
