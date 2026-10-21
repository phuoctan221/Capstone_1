from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.core.config import settings

client: AsyncIOMotorClient | None = None
db: AsyncIOMotorDatabase | None = None


async def connect_to_mongo():
    global client, db
    client = AsyncIOMotorClient(settings.MONGO_URI)
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
