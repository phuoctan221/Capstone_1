from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import OperationFailure

from app.core.config import settings

client: AsyncIOMotorClient | None = None
db: AsyncIOMotorDatabase | None = None


def is_auth_error(exc: Exception) -> bool:
    """Loi xac thuc / phan quyen la loi 'vinh vien' - thu lai 10 lan cung vo ich."""
    if isinstance(exc, OperationFailure):
        text = str(exc).lower()
        return exc.code in (18, 13) or "auth" in text or "not authorized" in text
    return False


async def connect_to_mongo():
    global client, db
    client = AsyncIOMotorClient(
        settings.MONGO_URI,
        serverSelectionTimeoutMS=settings.MONGO_TIMEOUT_MS,
        connectTimeoutMS=settings.MONGO_TIMEOUT_MS,
        socketTimeoutMS=settings.MONGO_TIMEOUT_MS * 3,
        retryWrites=True,
        appname="smartvocab-backend",
        tz_aware=True,
    )
    db = client[settings.MONGO_DB_NAME]
    await client.admin.command("ping")
    await db.flashcard_progress.create_index(
        [("user_id", 1), ("vocabulary_id", 1)], unique=True
    )
    await db.vocabularies.create_index([("word", "text"), ("meaning", "text")])
    await db.lesson_progress.create_index(
        [("user_id", 1), ("topic", 1)], unique=True
    )


async def close_mongo_connection():
    global client
    if client is not None:
        client.close()


def get_database() -> AsyncIOMotorDatabase:
    if db is None:
        raise RuntimeError("Database is not initialized")
    return db
