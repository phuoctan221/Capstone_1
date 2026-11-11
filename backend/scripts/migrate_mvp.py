"""Idempotent migration for the Multi-skill Mastery + FSRS MVP.

Chay tu thu muc backend/:

    .venv\\Scripts\\python.exe scripts/migrate_mvp.py              # dry-run
    .venv\\Scripts\\python.exe scripts/migrate_mvp.py --apply
    .venv\\Scripts\\python.exe scripts/migrate_mvp.py --apply --allow-shared

Backfills:
  * vocabularies.word_key / meaning_key / domain (legacy topic -> domain)
  * users.role / xp / streak
  * flashcard_progress -> user_word_states (Leitner box is preserved as
    legacy_leitner_box; it is NOT converted into FSRS difficulty/stability)
  * lesson_progress.lesson_id / domain
  * indexes (legacy user_id_1_topic_1 is dropped by connect_to_mongo)
  * lessons + exercise bank

Running it twice produces no duplicate documents.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from pymongo import UpdateOne  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.domains import MVP_DOMAIN_ORDER, domain_for_topic  # noqa: E402
from app.db.mongodb import close_mongo_connection, connect_to_mongo, get_database  # noqa: E402
from app.services.domain_service import ensure_domains  # noqa: E402
from app.services.exercise_service import ensure_exercise_bank  # noqa: E402
from app.services.lesson_service import (  # noqa: E402
    VALID_LEVELS,
    get_lesson_words,
    lesson_slug,
    seed_lessons,
)
from app.services.mastery_service import DEFAULT_MASTERY  # noqa: E402


def _as_utc(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return value


def _legacy_state(fp: dict, now: datetime) -> dict:
    due = _as_utc(fp.get("next_review")) or now
    last = _as_utc(fp.get("last_reviewed"))
    return {
        "user_id": fp["user_id"],
        "vocabulary_id": fp["vocabulary_id"],
        "mastery": dict(DEFAULT_MASTERY),
        "fsrs": {
            "card_json": None,
            "card_id": None,
            "state": None,
            "step": None,
            "difficulty": None,
            "stability": None,
            "due_at": due,
            "last_reviewed_at": last,
        },
        "review_count": 0,
        "started_at": last or due,
        "updated_at": now,
        "legacy_leitner_box": fp.get("box"),
        "migrated_from": "flashcard_progress",
    }


async def _migrate_vocabularies(db, apply: bool, now: datetime) -> int:
    ops: list[UpdateOne] = []
    changed = 0
    async for doc in db.vocabularies.find({}):
        domain = domain_for_topic(doc.get("domain") or doc.get("topic"))
        word_key = (doc.get("word") or "").strip().lower()
        meaning_key = (doc.get("meaning") or "").strip().lower()
        if (
            doc.get("domain") == domain
            and doc.get("word_key") == word_key
            and doc.get("meaning_key") == meaning_key
        ):
            continue
        changed += 1
        if apply:
            ops.append(
                UpdateOne(
                    {"_id": doc["_id"]},
                    {
                        "$set": {
                            "domain": domain,
                            "word_key": word_key,
                            "meaning_key": meaning_key,
                            "updated_at": now,
                        }
                    },
                )
            )
    if apply and ops:
        await db.vocabularies.bulk_write(ops, ordered=False)
    return changed


async def _migrate_users(db, apply: bool, now: datetime) -> int:
    changed = 0
    async for user in db.users.find({}):
        updates = {}
        if not user.get("role"):
            updates["role"] = "user"
        if user.get("xp") is None:
            updates["xp"] = 0
        if user.get("streak") is None:
            updates["streak"] = 0
        if not updates:
            continue
        changed += 1
        if apply:
            updates["updated_at"] = now
            await db.users.update_one({"_id": user["_id"]}, {"$set": updates})
    return changed


async def _migrate_flashcards(db, apply: bool, now: datetime) -> dict:
    created = skipped = 0
    async for fp in db.flashcard_progress.find({}):
        user_id = fp.get("user_id")
        vocabulary_id = fp.get("vocabulary_id")
        if not user_id or not vocabulary_id:
            skipped += 1
            continue
        exists = await db.user_word_states.find_one(
            {"user_id": user_id, "vocabulary_id": vocabulary_id}, {"_id": 1}
        )
        if exists:
            skipped += 1
            continue
        created += 1
        if apply:
            await db.user_word_states.update_one(
                {"user_id": user_id, "vocabulary_id": vocabulary_id},
                {"$setOnInsert": _legacy_state(fp, now)},
                upsert=True,
            )
    return {"created": created, "skipped": skipped}


async def _migrate_lesson_progress(db, apply: bool, now: datetime) -> int:
    changed = 0
    async for doc in db.lesson_progress.find({}):
        domain = domain_for_topic(doc.get("domain") or doc.get("topic"))
        lesson_id = doc.get("lesson_id")
        if not lesson_id:
            level = doc.get("level")
            lesson_id = lesson_slug(domain, level) if level else domain
        if doc.get("lesson_id") == lesson_id and doc.get("domain") == domain:
            continue
        changed += 1
        if apply:
            await db.lesson_progress.update_one(
                {"_id": doc["_id"]},
                {"$set": {"lesson_id": lesson_id, "domain": domain, "updated_at": now}},
            )
    return changed


async def _rebuild_exercise_bank(db, apply: bool) -> int:
    total = 0
    if not apply:
        return total
    for domain in MVP_DOMAIN_ORDER:
        for level in sorted(VALID_LEVELS):
            words = await get_lesson_words(domain, level)
            if words:
                total += await ensure_exercise_bank(words, domain=domain, level=level)
    return total


async def run_migration(apply: bool) -> dict:
    db = get_database()
    now = datetime.now(timezone.utc)
    report = {"applied": apply}

    report["vocabularies_backfilled"] = await _migrate_vocabularies(db, apply, now)
    report["users_backfilled"] = await _migrate_users(db, apply, now)
    report["flashcard_progress"] = await _migrate_flashcards(db, apply, now)
    report["lesson_progress_backfilled"] = await _migrate_lesson_progress(db, apply, now)

    if apply:
        report["domains"] = await ensure_domains()
        report["lessons"] = await seed_lessons()
        report["exercise_items"] = await _rebuild_exercise_bank(db, apply)

    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate SmartVocab AI to Mastery + FSRS MVP")
    parser.add_argument("--apply", action="store_true", help="write changes to MongoDB")
    parser.add_argument(
        "--allow-shared",
        action="store_true",
        help="allow writing to a database whose name does not contain 'test'",
    )
    return parser.parse_args()


async def main() -> int:
    args = parse_args()
    db_name = settings.MONGO_DB_NAME
    if args.apply and "test" not in db_name.lower() and not args.allow_shared:
        print(
            f"[LOI] Database '{db_name}' khong phai test DB. "
            "Dung --allow-shared neu that su muon migrate DB dung chung."
        )
        return 2

    print(f"Database: {settings.mongo_target}")
    await connect_to_mongo()
    try:
        report = await run_migration(args.apply)
    finally:
        await close_mongo_connection()

    print("Ket qua migration:")
    for key, value in report.items():
        print(f"  {key}: {value}")
    if not args.apply:
        print("Dry-run: chua ghi gi. Them --apply de ap dung.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
