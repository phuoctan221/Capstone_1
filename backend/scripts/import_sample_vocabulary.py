"""Nhap du lieu mau tu data/sample_vocabulary.json vao MongoDB.

Chay tu thu muc backend/:

    .venv\\Scripts\\python.exe scripts/import_sample_vocabulary.py
    .venv\\Scripts\\python.exe scripts/import_sample_vocabulary.py --dry-run
    .venv\\Scripts\\python.exe scripts/import_sample_vocabulary.py --mode replace

Cac che do:
    upsert       (mac dinh) - them moi, cap nhat ban da co (khop theo `word`, khong phan biet hoa thuong)
    insert-only  - chi them moi, bo qua cac tu da ton tai
    replace      - xoa toan bo collection `vocabularies` roi nhap lai tu dau
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402
from pymongo import InsertOne, UpdateOne  # noqa: E402
from pydantic import ValidationError  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.models.vocabulary import VocabularyBase  # noqa: E402

DEFAULT_SOURCE = BACKEND_DIR.parent / "data" / "sample_vocabulary.json"
COLLECTION = "vocabularies"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import du lieu mau vocabulary vao MongoDB")
    parser.add_argument("--file", type=Path, default=DEFAULT_SOURCE, help="duong dan toi file JSON")
    parser.add_argument(
        "--mode",
        choices=["upsert", "insert-only", "replace"],
        default="upsert",
        help="cach xu ly du lieu da ton tai",
    )
    parser.add_argument("--dry-run", action="store_true", help="chi kiem tra, khong ghi vao database")
    return parser.parse_args()


def load_records(path: Path) -> tuple[list[dict], list[str]]:
    if not path.exists():
        raise SystemExit(f"[LOI] Khong tim thay file du lieu: {path}")

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise SystemExit("[LOI] File JSON phai chua mot mang (mongoimport --jsonArray).")

    records: list[dict] = []
    errors: list[str] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            errors.append(f"[{index}] Phan tu khong phai object")
            continue
        try:
            model = VocabularyBase(**item)
        except ValidationError as exc:
            detail = "; ".join(
                f"{'.'.join(str(p) for p in err['loc']) or 'root'} = {err['msg']}" for err in exc.errors()
            )
            errors.append(f"[{index}] {detail}")
            continue
        records.append(model.model_dump())

    return records, errors


async def import_records(db, records: list[dict], mode: str, dry_run: bool) -> dict:
    now = datetime.now(timezone.utc)

    existing: dict[str, dict] = {}
    if mode != "replace":
        async for doc in db[COLLECTION].find({}, {"word": 1}):
            key = (doc.get("word") or "").strip().lower()
            existing.setdefault(key, doc)

    if mode == "replace" and not dry_run:
        await db[COLLECTION].drop()
        print("[INFO] Da xoa collection 'vocabularies' (che do replace)")

    inserted = updated = skipped = 0
    seen: set[str] = set()
    ops_insert: list[InsertOne] = []
    ops_update: list[UpdateOne] = []

    for record in records:
        key = record["word"].strip().lower()
        if key in seen:
            skipped += 1
            continue
        seen.add(key)

        payload = {**record, "updated_at": now}
        current = existing.get(key)

        if current is None:
            ops_insert.append(InsertOne({**payload, "created_at": now}))
            inserted += 1
        elif mode == "insert-only":
            skipped += 1
        else:
            ops_update.append(
                UpdateOne(
                    {"_id": current["_id"]},
                    {"$set": payload, "$setOnInsert": {"created_at": now}},
                )
            )
            updated += 1

    if not dry_run:
        if ops_insert:
            await db[COLLECTION].bulk_write(ops_insert, ordered=False)
        if ops_update:
            await db[COLLECTION].bulk_write(ops_update, ordered=False)
        await db[COLLECTION].create_index([("word", "text"), ("meaning", "text")])

    return {"inserted": inserted, "updated": updated, "skipped": skipped}


async def report(db) -> None:
    total = await db[COLLECTION].count_documents({})
    print(f"\nTong so tu trong collection '{COLLECTION}': {total}")

    for field, label in (("topic", "Topic"), ("level", "Level")):
        pipeline = [{"$group": {"_id": f"${field}", "count": {"$sum": 1}}}, {"$sort": {"_id": 1}}]
        rows = [row async for row in db[COLLECTION].aggregate(pipeline)]
        if rows:
            detail = ", ".join(f"{row['_id']}={row['count']}" for row in rows)
            print(f"  {label:<6}: {detail}")

    missing_ts = await db[COLLECTION].count_documents({"created_at": {"$exists": False}})
    if missing_ts:
        print(f"  [!] {missing_ts} document thieu 'created_at' (se duoc gan lai khi import lai)")


async def main() -> None:
    args = parse_args()

    print(f"File du lieu : {args.file}")
    print(f"Database     : {settings.MONGO_DB_NAME}")
    print(f"Che do       : {args.mode}{' (dry-run)' if args.dry_run else ''}")

    records, errors = load_records(args.file)
    for message in errors:
        print(f"[LOI] {message}")
    if errors:
        print(f"\n[LOI] {len(errors)} ban ghi khong hop le -> khong nhap.")
        raise SystemExit(1)

    print(f"Doc duoc     : {len(records)} ban ghi hop le")

    client = AsyncIOMotorClient(settings.MONGO_URI, serverSelectionTimeoutMS=15000)
    try:
        await client.admin.command("ping")
        db = client[settings.MONGO_DB_NAME]

        stats = await import_records(db, records, args.mode, args.dry_run)
        print(
            f"\nKet qua      : them moi={stats['inserted']} | cap nhat={stats['updated']} "
            f"| bo qua={stats['skipped']}"
        )

        await report(db)
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())
