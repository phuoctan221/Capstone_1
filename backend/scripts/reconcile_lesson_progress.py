"""Repair historical gaps in per-unit lesson progress safely.

Only a missing unit *between* completed units is repaired. For example,
completed units ``1, 2, 3, 5, 6`` receive a synthetic completion for Unit 4.
This does not mark a merely studied unit as complete and does not fill trailing
units. Run without ``--apply`` first to inspect proposed changes.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.mongodb import close_mongo_connection, connect_to_mongo, get_database
from app.services.lesson_service import get_lesson_words, parse_lesson_id, unit_count


async def find_repairs() -> list[dict]:
    db = get_database()
    groups: dict[tuple[str, str], set[int]] = {}
    async for row in db.lesson_progress.find(
        {"completed": True, "unit": {"$type": "int"}},
        {"user_id": 1, "lesson_id": 1, "unit": 1},
    ):
        user_id = row.get("user_id")
        lesson_id = row.get("lesson_id")
        unit = row.get("unit")
        if isinstance(user_id, str) and isinstance(lesson_id, str) and isinstance(unit, int) and unit > 0:
            groups.setdefault((user_id, lesson_id), set()).add(unit)

    repairs: list[dict] = []
    for (user_id, lesson_id), completed in groups.items():
        domain, level = parse_lesson_id(lesson_id)
        if level is None or len(completed) < 2:
            continue
        words = await get_lesson_words(domain, level)
        total_units = unit_count(len(words))
        if total_units < 2:
            continue
        highest = min(max(completed), total_units)
        for unit in range(min(completed) + 1, highest):
            if unit not in completed:
                repairs.append(
                    {
                        "user_id": user_id,
                        "lesson_id": lesson_id,
                        "unit": unit,
                        "topic": domain,
                    }
                )
    return repairs


async def main(apply: bool) -> int:
    await connect_to_mongo()
    try:
        repairs = await find_repairs()
        print(f"Found {len(repairs)} historical progress gap(s).")
        for item in repairs:
            print(f"- {item['user_id']} :: {item['lesson_id']} :: Unit {item['unit']}")
        if not apply:
            print("Dry run only. Re-run with --apply to write these repairs.")
            return 0

        db = get_database()
        now = datetime.now(timezone.utc)
        repaired = 0
        for item in repairs:
            result = await db.lesson_progress.update_one(
                {
                    "user_id": item["user_id"],
                    "lesson_id": item["lesson_id"],
                    "unit": item["unit"],
                },
                {
                    "$setOnInsert": {
                        **item,
                        "completed": True,
                        "completion_source": "legacy_reconciled",
                        "completed_at": now,
                        "created_at": now,
                        "updated_at": now,
                        "learned_count": 0,
                        "mastered_count": 0,
                    }
                },
                upsert=True,
            )
            repaired += int(bool(result.upserted_id))
        print(f"Applied {repaired} repair(s).")
        return 0
    finally:
        await close_mongo_connection()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write repair records")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.apply)))