from datetime import datetime, timezone

from bson import ObjectId

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
    doc["created_at"] = now
    doc["updated_at"] = now
    result = await db[COLLECTION].insert_one(doc)
    doc["_id"] = result.inserted_id
    return _serialize(doc)


async def update_vocabulary(vocab_id: str, data: VocabularyUpdate) -> dict | None:
    db = get_database()
    update = {k: v for k, v in data.model_dump(exclude_none=True).items()}
    if not update:
        return await get_vocabulary(vocab_id)
    update["updated_at"] = datetime.now(timezone.utc)
    doc = await db[COLLECTION].find_one_and_update(
        {"_id": ObjectId(vocab_id)}, {"$set": update}, return_document=True
    )
    return _serialize(doc) if doc else None


async def delete_vocabulary(vocab_id: str) -> bool:
    db = get_database()
    result = await db[COLLECTION].delete_one({"_id": ObjectId(vocab_id)})
    return result.deleted_count > 0
