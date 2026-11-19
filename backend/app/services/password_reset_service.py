from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from pymongo import ReturnDocument

from app.core.config import settings
from app.db.mongodb import get_database
from app.services import auth_service, email_service

OTPS = "password_reset_otps"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash_otp(email: str, otp: str) -> str:
    return hmac.new(
        settings.JWT_SECRET.encode(), f"{email}:{otp}".encode(), hashlib.sha256
    ).hexdigest()


def _valid(record: dict, otp: str) -> bool:
    return hmac.compare_digest(record.get("otp_hash", ""), _hash_otp(record["email"], otp))


async def request_reset(email: str) -> None:
    """Deliberately returns no account-existence signal to the caller."""
    db = get_database()
    email = email.strip().lower()
    now = _now()
    latest = await db[OTPS].find_one({"email": email}, sort=[("created_at", -1)])
    if latest and (now - latest.get("created_at", now)).total_seconds() < settings.PASSWORD_RESET_SEND_COOLDOWN_SECONDS:
        return
    since = now - timedelta(hours=1)
    if await db[OTPS].count_documents({"email": email, "created_at": {"$gte": since}}) >= settings.PASSWORD_RESET_MAX_SENDS_PER_HOUR:
        return
    if not await db.users.find_one({"email": email, "is_active": {"$ne": False}}):
        return
    otp = f"{secrets.randbelow(1_000_000):06d}"
    await db[OTPS].update_many({"email": email, "used_at": None}, {"$set": {"invalidated_at": now}})
    inserted = await db[OTPS].insert_one({
        "email": email, "otp_hash": _hash_otp(email, otp), "attempts": 0,
        "created_at": now, "expires_at": now + timedelta(minutes=settings.PASSWORD_RESET_OTP_TTL_MINUTES),
        "used_at": None, "invalidated_at": None,
    })
    try:
        await email_service.send_password_reset_email(email, otp)
    except Exception:
        # Do not leave a cooldown-producing OTP behind if delivery failed.
        await db[OTPS].delete_one({"_id": inserted.inserted_id})
        raise


async def verify_reset(email: str, otp: str) -> bool:
    db = get_database()
    now = _now()
    record = await db[OTPS].find_one({"email": email.strip().lower()}, sort=[("created_at", -1)])
    if not record or record.get("used_at") or record.get("invalidated_at") or record.get("expires_at") <= now:
        return False
    if int(record.get("attempts", 0)) >= settings.PASSWORD_RESET_OTP_MAX_ATTEMPTS:
        return False
    if not _valid(record, otp):
        await db[OTPS].update_one({"_id": record["_id"]}, {"$inc": {"attempts": 1}})
        return False
    return True


async def confirm_reset(email: str, otp: str, new_password: str) -> bool:
    db = get_database()
    email = email.strip().lower()
    now = _now()
    record = await db[OTPS].find_one_and_update(
        {"email": email, "used_at": None, "invalidated_at": None, "expires_at": {"$gt": now}, "attempts": {"$lt": settings.PASSWORD_RESET_OTP_MAX_ATTEMPTS}},
        {"$set": {"used_at": now}}, sort=[("created_at", -1)], return_document=ReturnDocument.AFTER,
    )
    if not record or not _valid(record, otp):
        if record:
            await db[OTPS].update_one({"_id": record["_id"]}, {"$set": {"used_at": None}, "$inc": {"attempts": 1}})
        return False
    user = await db.users.find_one({"email": email, "is_active": {"$ne": False}})
    if not user:
        return False
    await db.users.update_one({"_id": user["_id"]}, {"$set": {
        "password_hash": auth_service.hash_password(new_password),
        "token_version": auth_service.token_version_of(user) + 1, "updated_at": now,
    }})
    return True