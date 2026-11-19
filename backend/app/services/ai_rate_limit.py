from datetime import datetime, timezone
from fastapi import HTTPException
from app.db.mongodb import get_database


async def limit(user_id, max_requests=10):
    # Shared by all backend workers; deterministic bucket avoids concurrent upsert duplicates.
    bucket = int(datetime.now(timezone.utc).timestamp()) // 60
    doc = await get_database()["ai_rate_limits"].find_one_and_update(
        {"_id": f"{user_id}:{bucket}"},
        {"$inc": {"count": 1}, "$set": {"expires_at": datetime.now(timezone.utc)}},
        upsert=True, return_document=True)
    if doc["count"] > max_requests:
        raise HTTPException(429, "Bạn thao tác hơi nhanh. Vui lòng đợi một chút rồi thử lại.")
