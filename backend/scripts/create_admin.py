"""Create or promote an admin account without hardcoding credentials.

Chay tu thu muc backend/:

    .venv\\Scripts\\python.exe scripts/create_admin.py --email admin@example.com
    .venv\\Scripts\\python.exe scripts/create_admin.py --email admin@example.com --promote-only
    .venv\\Scripts\\python.exe scripts/create_admin.py --email admin@example.com --reset-password

Mat khau duoc nhap an (getpass) hoac lay tu bien moi truong
SMARTVOCAB_ADMIN_PASSWORD. Khong truyen mat khau qua tham so dong lenh.
"""
from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings  # noqa: E402
from app.db.mongodb import close_mongo_connection, connect_to_mongo, get_database  # noqa: E402
from app.services.auth_service import hash_password  # noqa: E402


def _read_password() -> str:
    value = os.environ.get("SMARTVOCAB_ADMIN_PASSWORD")
    if value:
        return value
    first = getpass.getpass("Mat khau admin: ")
    second = getpass.getpass("Nhap lai mat khau: ")
    if first != second:
        raise SystemExit("[LOI] Mat khau nhap lai khong khop")
    return first


def _username_from_email(email: str) -> str:
    base = email.split("@", 1)[0].strip().lower()
    cleaned = "".join(ch for ch in base if ch.isalnum() or ch in "._-") or "admin"
    return cleaned[:30]


async def main() -> int:
    parser = argparse.ArgumentParser(description="Create/promote a SmartVocab admin")
    parser.add_argument("--email", required=True)
    parser.add_argument("--promote-only", action="store_true")
    parser.add_argument("--reset-password", action="store_true")
    args = parser.parse_args()

    email = args.email.strip().lower()
    if "@" not in email:
        print("[LOI] Email khong hop le")
        return 2

    print(f"Database: {settings.mongo_target}")
    await connect_to_mongo()
    try:
        db = get_database()
        now = datetime.now(timezone.utc)
        user = await db.users.find_one({"email": email})

        if user and args.promote_only:
            await db.users.update_one(
                {"_id": user["_id"]},
                {"$set": {"role": "admin", "updated_at": now}},
            )
            print(f"[OK] Da nang quyen admin cho {email}")
            return 0

        if user:
            updates = {"role": "admin", "updated_at": now}
            if args.reset_password:
                password = _read_password()
                if len(password) < 6:
                    print("[LOI] Mat khau phai co it nhat 6 ky tu")
                    return 2
                updates["password_hash"] = hash_password(password)
            await db.users.update_one({"_id": user["_id"]}, {"$set": updates})
            print(f"[OK] Da cap nhat admin {email}")
            return 0

        password = _read_password()
        if len(password) < 6:
            print("[LOI] Mat khau phai co it nhat 6 ky tu")
            return 2

        username = _username_from_email(email)
        doc = {
            "_id": email,
            "email": email,
            "username": username,
            "password_hash": hash_password(password),
            "role": "admin",
            "learning_level": None,
            "interests": [],
            "onboarded": True,
            "daily_goal": 10,
            "xp": 0,
            "streak": 0,
            "created_at": now,
            "updated_at": now,
        }
        await db.users.insert_one(doc)
        print(f"[OK] Da tao admin {email} (username={username})")
        return 0
    finally:
        await close_mongo_connection()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
