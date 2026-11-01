from datetime import datetime, timezone

from bson import ObjectId
from pymongo import ReturnDocument, UpdateOne

from app.db.mongodb import get_database
from app.models.vocabulary import VocabularyCreate, VocabularyUpdate

COLLECTION = "vocabularies"


def _serialize(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    return doc


async def list_vocabularies(
    topic: str | None = None,
    level: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    db = get_database()
    query: dict = {}
    if topic:
        query["topic"] = topic
    if level:
        query["level"] = level
    if search:
        query["$or"] = [
            {"word": {"$regex": search, "$options": "i"}},
            {"meaning": {"$regex": search, "$options": "i"}},
        ]

    total = await db[COLLECTION].count_documents(query)
    cursor = (
        db[COLLECTION]
        .find(query)
        .sort("created_at", -1)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    items = [_serialize(doc) async for doc in cursor]
    return {"total": total, "page": page, "page_size": page_size, "items": items}


async def get_vocabulary(vocab_id: str) -> dict | None:
    db = get_database()
    doc = await db[COLLECTION].find_one({"_id": ObjectId(vocab_id)})
    return _serialize(doc) if doc else None


async def create_vocabulary(data: VocabularyCreate) -> dict:
    db = get_database()
    now = datetime.now(timezone.utc)
    doc = data.model_dump()
    doc["word"] = doc["word"].strip()
    doc["word_key"] = doc["word"].lower()
    doc["updated_at"] = now
    saved = await db[COLLECTION].find_one_and_update(
        {"word_key": doc["word_key"]},
        {"$set": doc, "$setOnInsert": {"created_at": now}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return _serialize(saved)


async def update_vocabulary(vocab_id: str, data: VocabularyUpdate) -> dict | None:
    db = get_database()
    update = {k: v for k, v in data.model_dump(exclude_none=True).items()}
    if not update:
        return await get_vocabulary(vocab_id)
    if "word" in update:
        update["word"] = update["word"].strip()
        update["word_key"] = update["word"].lower()
    update["updated_at"] = datetime.now(timezone.utc)
    doc = await db[COLLECTION].find_one_and_update(
        {"_id": ObjectId(vocab_id)},
        {"$set": update},
        return_document=ReturnDocument.AFTER,
    )
    return _serialize(doc) if doc else None


async def delete_vocabulary(vocab_id: str) -> bool:
    db = get_database()
    result = await db[COLLECTION].delete_one({"_id": ObjectId(vocab_id)})
    return result.deleted_count > 0


async def create_vocabularies_bulk(items: list[dict]) -> dict:
    """Ghi mot loat tu vung trong 1 lan bulk_write.

    Khop theo `word` khong phan biet hoa thuong nen chay lai nhieu lan
    van khong sinh ban ghi trung.
    """
    db = get_database()
    if not items:
        return {"saved": 0, "created": 0, "updated": 0}

    now = datetime.now(timezone.utc)

    items_by_key: dict[str, dict] = {}
    for item in items:
        word = (item.get("word") or "").strip()
        key = word.lower()
        if not word or key in items_by_key:
            continue
        items_by_key[key] = {**item, "word": word}

    if not items_by_key:
        return {"saved": 0, "created": 0, "updated": 0}

    # Chi quet nhung tu trong batch (khong scan ca collection)
    existing: dict[str, ObjectId] = {}
    async for doc in db[COLLECTION].find(
        {"word_key": {"$in": list(items_by_key)}}, {"word_key": 1}
    ):
        existing[doc["word_key"]] = doc["_id"]

    operations = []
    created = updated = 0
    for key, item in items_by_key.items():
        payload = {**item, "word_key": key, "updated_at": now}
        current_id = existing.get(key)
        if current_id is not None:
            operations.append(
                UpdateOne(
                    {"_id": current_id},
                    {"$set": payload, "$setOnInsert": {"created_at": now}},
                )
            )
            updated += 1
        else:
            operations.append(
                UpdateOne(
                    {"word_key": key},
                    {"$set": payload, "$setOnInsert": {"created_at": now}},
                    upsert=True,
                )
            )
            created += 1

    if operations:
        await db[COLLECTION].bulk_write(operations, ordered=False)

    return {"saved": len(operations), "created": created, "updated": updated}
