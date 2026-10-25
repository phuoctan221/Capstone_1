"""Chan doan ket noi MongoDB theo tung lop va chi ra nguyen nhan cu the.

Chay tu thu muc backend/:

    .venv\\Scripts\\python.exe scripts/check_mongo.py
"""

from __future__ import annotations

import asyncio
import socket
import ssl
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402
from pymongo.errors import OperationFailure  # noqa: E402

from app.core.config import settings  # noqa: E402

OK = "[ OK ]"
FAIL = "[FAIL]"
INFO = "[INFO]"


def section(step: str, title: str) -> None:
    print(f"\n{step} {title}")
    print("-" * 62)


def parse_uri(uri: str) -> tuple[str, str, str, str]:
    parsed = urlparse(uri)
    username = unquote(parsed.username or "")
    password = unquote(parsed.password or "")
    host = parsed.hostname or ""
    db = (parsed.path or "/").lstrip("/")
    return username, password, host, db


def check_dns(host: str, is_srv: bool) -> list[tuple[str, int]]:
    if not is_srv:
        return [(host, 27017)]
    try:
        import dns.resolver
    except ImportError:
        print(f"{INFO} thu vien 'dnspython' chua cai -> bo qua kiem tra SRV chi tiet")
        return [(host, 27017)]
    try:
        answers = dns.resolver.resolve(f"_mongodb._tcp.{host}", "SRV")
    except Exception as exc:
        print(f"{FAIL} Phan giai SRV that bai: {exc}")
        return []
    targets = []
    for record in answers:
        print(f"{OK} SRV {record.target} port {record.port}")
        targets.append((str(record.target).rstrip("."), record.port))
    return targets


def check_tcp_tls(host: str, port: int, use_tls: bool) -> bool:
    try:
        raw = socket.create_connection((host, port), timeout=10)
    except Exception as exc:
        print(f"{FAIL} TCP {host}:{port} - {exc}")
        return False
    if not use_tls:
        raw.close()
        print(f"{OK} TCP {host}:{port} (khong dung TLS - MongoDB local)")
        return True
    try:
        context = ssl.create_default_context()
        with context.wrap_socket(raw, server_hostname=host) as tls:
            print(f"{OK} TCP + TLS {host}:{port} ({tls.version()})")
            return True
    except Exception as exc:
        raw.close()
        print(f"{FAIL} TLS {host}:{port} - {exc}")
        return False


async def main() -> int:
    uri = settings.MONGO_URI
    username, password, host, uri_db = parse_uri(uri)
    is_srv = uri.startswith("mongodb+srv://")

    section("[1/6]", "Cau hinh")
    print(f"{INFO} URI : {settings.mongo_target}")
    print(f"{INFO} User: {username or '(khong co)'}")
    print(f"{INFO} DB   : {settings.MONGO_DB_NAME}")
    if uri_db and uri_db != settings.MONGO_DB_NAME:
        print(
            f"{INFO} Luu y: ten DB trong URI ('{uri_db}') khac MONGO_DB_NAME "
            f"('{settings.MONGO_DB_NAME}') - app se dung MONGO_DB_NAME."
        )

    section("[2/6]", "Phan giai DNS / SRV")
    targets = check_dns(host, is_srv)
    if not targets:
        print("\n=> KHONG THE ket noi. DNS/SRV khong resolve duoc.")
        return 1

    section("[3/6]", "Ket noi TCP + TLS")
    reachable = [t for t in targets if check_tcp_tls(t[0], t[1], is_srv)]
    if not reachable:
        print(
            "\n=> KHONG THE ket noi. Hay kiem tra:\n"
            "  - 'Network Access > IP Access List' tren Atlas phai chua IP cua ban\n"
            "  - Firewall/VPN cua may co chan port 27017 khong"
        )
        return 1

    section("[4/6]", "Xac thuc (SCRAM)")
    client = AsyncIOMotorClient(
        uri, serverSelectionTimeoutMS=settings.MONGO_TIMEOUT_MS, tz_aware=True
    )
    try:
        await client.admin.command("ping")
        print(f"{OK} Da xac thuc thanh cong")
    except OperationFailure as exc:
        print(f"{FAIL} Xac thuc that bai (code {exc.code}): {exc}")
        print(
            "\n=> NGUON GOC: thong tin dang nhap sai. Kiem tra tren Atlas UI:\n"
            "  1. 'Database Access' -> user 'phuoctan1824_db_user' da ton tai chua?\n"
            "  2. 'Edit' -> 'Reset Password' -> copy mat khau MOI (Atlas an mat khau sau khi tao)\n"
            "  3. 'Database Privileges' -> user phai co role tren database 'capstone1'\n"
            "     (readWrite cho database nay, hoac readWriteAnyDatabase)\n"
            "  4. Mat khau chua ky tu dac biet: %40 : / ? # [ ] & = + +"
        )
        client.close()
        return 1
    except Exception as exc:
        print(f"{FAIL} Loi khac: {type(exc).__name__}: {exc}")
        client.close()
        return 1

    section("[5/6]", "Truy cap database")
    db = client[settings.MONGO_DB_NAME]
    try:
        names = await db.list_collection_names()
        print(f"{OK} Truy cap '{settings.MONGO_DB_NAME}' thanh cong")
        print(f"{INFO} Collections: {names or '(chua co collection nao)'}")
    except OperationFailure as exc:
        print(f"{FAIL} Khong co quyen tren database '{settings.MONGO_DB_NAME}': {exc}")
        client.close()
        return 1

    section("[6/6]", "Index & du lieu")
    for collection in ("vocabularies", "users", "flashcard_progress", "lesson_progress"):
        indexes = [i["name"] async for i in db[collection].list_indexes()]
        count = await db[collection].count_documents({})
        print(f"{OK} {collection:<20} documents={count:<6} indexes={indexes}")

    print("\n=> TAT CA OK. Backend co the chay binh thuong.\n")
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
