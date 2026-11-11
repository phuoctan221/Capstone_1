"""Seed the three MVP domains, vocabulary, lessons and exercise bank.

Chay tu thu muc backend/:

    .venv\\Scripts\\python.exe scripts/seed_mvp.py            # dry-run
    .venv\\Scripts\\python.exe scripts/seed_mvp.py --apply
    .venv\\Scripts\\python.exe scripts/seed_mvp.py --apply --allow-shared

The operation is idempotent: re-running never creates duplicate words and never
overwrites a word that already has the same (word, domain, meaning) key.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings  # noqa: E402
from app.core.domains import MVP_DOMAIN_ORDER, domain_for_topic  # noqa: E402
from app.db.mongodb import close_mongo_connection, connect_to_mongo, get_database  # noqa: E402
from app.services.domain_service import ensure_domains  # noqa: E402
from app.services.exercise_service import ensure_exercise_bank  # noqa: E402
from app.services.lesson_service import (  # noqa: E402
    VALID_LEVELS,
    get_lesson_words,
    seed_lessons,
)
from app.services.vocabulary_service import create_vocabularies_bulk  # noqa: E402

DEFAULT_SOURCE = BACKEND_DIR / "data" / "vocabulary_seed.json"


def load_records(path: Path) -> list[dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise SystemExit("[LOI] vocabulary_seed.json phai la mot mang JSON")
    records = []
    for item in raw:
        if not isinstance(item, dict) or not item.get("word") or not item.get("meaning"):
            continue
        record = dict(item)
        record["domain"] = domain_for_topic(
            record.get("domain") or record.get("topic")
        )
        records.append(record)
    return records


async def run_seed(apply: bool, source: Path = DEFAULT_SOURCE) -> dict:
    db = get_database()
    records = load_records(source)
    report = {"source_records": len(records), "applied": apply}

    if not apply:
        report["vocabulary_in_db"] = await db.vocabularies.count_documents({})
        return report

    report["domains"] = await ensure_domains()
    report["vocabulary"] = await create_vocabularies_bulk(records)
    report["lessons"] = await seed_lessons()

    exercises = 0
    lessons_with_bank = 0
    for domain in MVP_DOMAIN_ORDER:
        for level in sorted(VALID_LEVELS):
            words = await get_lesson_words(domain, level)
            if len(words) < settings.MIN_LESSON_WORDS:
                continue
            exercises += await ensure_exercise_bank(words, domain=domain, level=level)
            lessons_with_bank += 1
    report["exercise_items"] = exercises
    report["lessons_with_bank"] = lessons_with_bank
    report["vocabulary_in_db"] = await db.vocabularies.count_documents({})
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed SmartVocab AI MVP data")
    parser.add_argument("--apply", action="store_true", help="write to MongoDB")
    parser.add_argument(
        "--allow-shared",
        action="store_true",
        help="allow writing to a database whose name does not contain 'test'",
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    return parser.parse_args()


async def main() -> int:
    args = parse_args()
    db_name = settings.MONGO_DB_NAME
    if args.apply and "test" not in db_name.lower() and not args.allow_shared:
        print(
            f"[LOI] Database '{db_name}' khong phai test DB. "
            "Dung --allow-shared neu that su muon ghi vao DB dung chung."
        )
        return 2

    print(f"Database: {settings.mongo_target}")
    await connect_to_mongo()
    try:
        report = await run_seed(args.apply, args.source)
    finally:
        await close_mongo_connection()

    print("Ket qua seed:")
    for key, value in report.items():
        print(f"  {key}: {value}")
    if not args.apply:
        print("Dry-run: chua ghi gi. Them --apply de ap dung.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
