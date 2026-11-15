from datetime import datetime, timezone
from fastapi import HTTPException
from app.db.mongodb import get_database


async def limit(user_id):
    # Shared by all backend workers; deterministic bucket avoids concurrent upsert duplicates.
    bucket = int(datetime.now(timezone.utc).timestamp()) // 60
    doc = await get_database()["ai_rate_limits"].find_one_and_update(
        {"_id": f"{user_id}:{bucket}"},
        {"$inc": {"count": 1}, "$set": {"expires_at": datetime.now(timezone.utc)}},
        upsert=True, return_document=True)
    if doc["count"] > 10:
        raise HTTPException(429, "Tối đa 10 yêu cầu AI/phút. Vui lòng đợi một chút.")
