from datetime import datetime, timezone

from bson import ObjectId
from pymongo import ReturnDocument, UpdateOne

from app.core.domains import domain_for_topic
from app.db.mongodb import get_database
from app.models.vocabulary import VocabularyCreate, VocabularyUpdate

COLLECTION = "vocabularies"


def _normalize_text(value: str | None) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _serialize(doc: dict) -> dict:
    result = dict(doc)
    result["id"] = str(result.pop("_id"))
    result["domain"] = domain_for_topic(result.get("domain") or result.get("topic"))
    # Internal dedup keys are not part of the public contract.
    result.pop("word_key", None)
    result.pop("meaning_key", None)
    return result


def _prepare(data: dict) -> dict:
    doc = dict(data)
    word = str(doc.get("word") or "").strip()
    doc["word"] = word
    doc["word_key"] = word.casefold()
    doc["meaning"] = str(doc.get("meaning") or "").strip()
    doc["meaning_key"] = _normalize_text(doc.get("meaning"))
    doc["domain"] = domain_for_topic(doc.get("domain") or doc.get("topic"))
    doc.setdefault("topic", doc["domain"])
    return doc


def _unique_selector(doc: dict) -> dict:
    return {
        "word_key": doc["word_key"],
        "domain": doc["domain"],
        "meaning_key": doc["meaning_key"],
    }


async def list_vocabularies(
    topic: str | None = None,
    level: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
    domain: str | None = None,
) -> dict:
    db = get_database()
    query: dict = {}
    selected_domain = domain or topic
    if selected_domain:
        canonical = domain_for_topic(selected_domain)
        query["$or"] = [
            {"domain": canonical},
            {"domain": {"$exists": False}, "topic": selected_domain},
        ]
    if level:
        query["level"] = level
    if search:
        query["$and"] = [
            {
                "$or": [
                    {"word": {"$regex": search, "$options": "i"}},
                    {"meaning": {"$regex": search, "$options": "i"}},
                ]
            }
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
    if not ObjectId.is_valid(vocab_id):
        return None
    doc = await db[COLLECTION].find_one({"_id": ObjectId(vocab_id)})
    return _serialize(doc) if doc else None


async def create_vocabulary(data: VocabularyCreate) -> dict:
    db = get_database()
    now = datetime.now(timezone.utc)
    doc = _prepare(data.model_dump())
    doc["updated_at"] = now
    saved = await db[COLLECTION].find_one_and_update(
        _unique_selector(doc),
        {"$set": doc, "$setOnInsert": {"created_at": now}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return _serialize(saved)


async def update_vocabulary(vocab_id: str, data: VocabularyUpdate) -> dict | None:
    db = get_database()
    if not ObjectId.is_valid(vocab_id):
        return None
    update = data.model_dump(exclude_none=True)
    if not update:
        return await get_vocabulary(vocab_id)
    if "word" in update:
        update["word"] = update["word"].strip()
        update["word_key"] = update["word"].casefold()
    if "meaning" in update:
        update["meaning"] = update["meaning"].strip()
        update["meaning_key"] = _normalize_text(update["meaning"])
    if "domain" in update or "topic" in update:
        update["domain"] = domain_for_topic(update.get("domain") or update.get("topic"))
    update["updated_at"] = datetime.now(timezone.utc)
    doc = await db[COLLECTION].find_one_and_update(
        {"_id": ObjectId(vocab_id)},
        {"$set": update},
        return_document=ReturnDocument.AFTER,
    )
    return _serialize(doc) if doc else None


async def delete_vocabulary(vocab_id: str) -> bool:
    """Delete a shared word and cascade dependent per-word records."""
    db = get_database()
    if not ObjectId.is_valid(vocab_id):
        return False
    result = await db[COLLECTION].delete_one({"_id": ObjectId(vocab_id)})
    if result.deleted_count == 0:
        return False
    await db.exercise_items.delete_many({"vocabulary_id": vocab_id})
    await db.user_word_states.delete_many({"vocabulary_id": vocab_id})
    await db.flashcard_progress.delete_many({"vocabulary_id": vocab_id})
    await db.quiz_questions.delete_many({"vocabulary_id": vocab_id})
    return True


async def create_vocabularies_bulk(items: list[dict]) -> dict:
    """Bulk upsert keyed by (word, domain, meaning) so re-runs are safe.

    The same word may legitimately appear with a different meaning or domain.
    """
    db = get_database()
    if not items:
        return {"saved": 0, "created": 0, "updated": 0}

    now = datetime.now(timezone.utc)
    prepared: dict[tuple[str, str, str], dict] = {}
    for item in items:
        doc = _prepare(item)
        if not doc["word"] or not doc["meaning"]:
            continue
        key = (doc["word_key"], doc["domain"], doc["meaning_key"])
        prepared[key] = doc

    if not prepared:
        return {"saved": 0, "created": 0, "updated": 0}

    word_keys = {key[0] for key in prepared}
    existing: dict[tuple[str, str, str], ObjectId] = {}
    async for doc in db[COLLECTION].find(
        {"word_key": {"$in": list(word_keys)}},
        {"word_key": 1, "domain": 1, "meaning_key": 1, "topic": 1},
    ):
        existing[
            (
                doc.get("word_key"),
                domain_for_topic(doc.get("domain") or doc.get("topic")),
                doc.get("meaning_key"),
            )
        ] = doc["_id"]

    operations = []
    created = updated = 0
    for key, doc in prepared.items():
        payload = {**doc, "updated_at": now}
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
                    {
                        "word_key": key[0],
                        "domain": key[1],
                        "meaning_key": key[2],
                    },
                    {"$set": payload, "$setOnInsert": {"created_at": now}},
                    upsert=True,
                )
            )
            created += 1

    if operations:
        await db[COLLECTION].bulk_write(operations, ordered=False)
    return {"saved": len(operations), "created": created, "updated": updated}
