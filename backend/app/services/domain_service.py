from datetime import datetime, timezone

from app.core.domains import DOMAINS, MVP_DOMAIN_ORDER, domain_doc
from app.db.mongodb import get_database
from app.services.lesson_service import domain_query, lesson_slug

EDITABLE_FIELDS = ("name", "name_vi", "description", "order", "active")


async def ensure_domains() -> int:
    """Seed defaults without overwriting administrator customisations."""
    db = get_database()
    now = datetime.now(timezone.utc)
    count = 0
    for slug in MVP_DOMAIN_ORDER:
        await db.domains.update_one(
            {"_id": slug},
            {
                "$setOnInsert": {
                    **domain_doc(slug),
                    "created_at": now,
                    "updated_at": now,
                }
            },
            upsert=True,
        )
        count += 1
    return count


async def _domain_payload(slug: str) -> dict:
    db = get_database()
    meta = DOMAINS[slug]
    stored = await db.domains.find_one({"_id": slug}) or {}
    vocab_count = await db.vocabularies.count_documents(domain_query(slug))
    levels = await db.vocabularies.distinct("level", domain_query(slug))
    payload = {
        **meta,
        **{key: stored[key] for key in EDITABLE_FIELDS if key in stored},
        "slug": slug,
        "active": bool(stored.get("active", True)),
        "vocabulary_count": vocab_count,
        "lesson_count": len(levels),
        "lessons": [lesson_slug(slug, lv) for lv in sorted(levels)],
        "created_at": stored.get("created_at"),
        "updated_at": stored.get("updated_at"),
    }
    return payload


async def list_domains(include_inactive: bool = False) -> list[dict]:
    result = []
    for slug in MVP_DOMAIN_ORDER:
        payload = await _domain_payload(slug)
        if payload["active"] or include_inactive:
            result.append(payload)
    return result


async def update_domain(slug: str, data: dict) -> dict | None:
    if slug not in DOMAINS:
        return None
    updates = {key: data[key] for key in EDITABLE_FIELDS if key in data}
    if not updates:
        return await _domain_payload(slug)
    now = datetime.now(timezone.utc)
    updates["updated_at"] = now
    db = get_database()
    stored = await db.domains.find_one({"_id": slug})
    if stored:
        await db.domains.update_one({"_id": slug}, {"$set": updates})
    else:
        await db.domains.insert_one(
            {**domain_doc(slug), **updates, "created_at": now}
        )
    return await _domain_payload(slug)
