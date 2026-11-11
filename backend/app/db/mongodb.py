from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import OperationFailure

from app.core.config import settings

client: AsyncIOMotorClient | None = None
db: AsyncIOMotorDatabase | None = None

# Legacy unique index that prevented more than one lesson per topic/user.
LEGACY_LESSON_PROGRESS_INDEX = "user_id_1_topic_1"


def is_auth_error(exc: Exception) -> bool:
    """Auth failures should not be retried as if they were network errors."""
    if isinstance(exc, OperationFailure):
        text = str(exc).lower()
        return exc.code in (18, 13) or "auth" in text or "not authorized" in text
    return False


async def _drop_index_if_exists(collection, name: str) -> None:
    """Remove a known legacy index. Indexes hold no user data."""
    try:
        info = await collection.index_information()
    except Exception:
        return
    if name in info:
        try:
            await collection.drop_index(name)
        except OperationFailure:
            # Already dropped by a concurrent process.
            pass


async def ensure_indexes() -> None:
    if db is None:
        raise RuntimeError("Database is not initialized")

    # --- users ---------------------------------------------------------
    await db.users.create_index([("email", 1)], unique=True, sparse=True)
    await db.users.create_index([("role", 1)])

    # --- domains / lessons --------------------------------------------
    await db.domains.create_index([("order", 1)])
    await db.lessons.create_index([("slug", 1)], unique=True)
    await db.lessons.create_index([("domain", 1), ("level", 1)])

    # --- vocabularies --------------------------------------------------
    await db.vocabularies.create_index([("word", "text"), ("meaning", "text")])
    await db.vocabularies.create_index([("domain", 1), ("level", 1)])
    await db.vocabularies.create_index([("word_key", 1)])
    # Same word may exist with a different meaning or in another domain.
    await db.vocabularies.create_index(
        [("word_key", 1), ("domain", 1), ("meaning_key", 1)],
        unique=True,
        partialFilterExpression={
            "word_key": {"$type": "string"},
            "domain": {"$type": "string"},
            "meaning_key": {"$type": "string"},
        },
        name="uniq_word_domain_meaning",
    )

    # --- exercise bank -------------------------------------------------
    await db.exercise_items.create_index(
        [("exercise_item_id", 1)], unique=True,
        partialFilterExpression={"exercise_item_id": {"$type": "string"}},
    )
    await db.exercise_items.create_index([("vocabulary_id", 1), ("skill", 1)])
    await db.exercise_items.create_index(
        [("domain", 1), ("level", 1), ("skill", 1), ("active", 1)]
    )

    # --- learning sessions --------------------------------------------
    await db.learning_sessions.create_index(
        [("session_id", 1)], unique=True,
        partialFilterExpression={"session_id": {"$type": "string"}},
    )
    await db.learning_sessions.create_index([("user_id", 1), ("started_at", -1)])

    # --- answer attempts ----------------------------------------------
    await db.answer_attempts.create_index([("user_id", 1), ("answered_at", -1)])
    await db.answer_attempts.create_index([("session_id", 1)])
    # Partial index does not conflict with legacy attempts without an ID.
    await db.answer_attempts.create_index(
        [("attempt_id", 1)],
        unique=True,
        partialFilterExpression={"attempt_id": {"$type": "string"}},
    )

    # --- per-user word state (Mastery + FSRS) -------------------------
    await db.user_word_states.create_index(
        [("user_id", 1), ("vocabulary_id", 1)], unique=True
    )
    await db.user_word_states.create_index([("user_id", 1), ("fsrs.due_at", 1)])

    # --- lesson progress ----------------------------------------------
    # Legacy docs only had (user_id, topic). New docs are per lesson.
    await _drop_index_if_exists(db.lesson_progress, LEGACY_LESSON_PROGRESS_INDEX)
    await db.lesson_progress.create_index(
        [("user_id", 1), ("lesson_id", 1)],
        unique=True,
        partialFilterExpression={"lesson_id": {"$type": "string"}},
        name="uniq_user_lesson",
    )
    await db.lesson_progress.create_index([("user_id", 1), ("topic", 1)])

    # --- FSRS review history ------------------------------------------
    await db.fsrs_review_logs.create_index(
        [("review_id", 1)], unique=True,
        partialFilterExpression={"review_id": {"$type": "string"}},
    )
    await db.fsrs_review_logs.create_index([("user_id", 1), ("reviewed_at", -1)])

    # --- legacy quiz questions ----------------------------------------
    await db.quiz_questions.create_index([("question_id", 1)], unique=True)
    await db.quiz_questions.create_index(
        [("expires_at", 1)], expireAfterSeconds=0
    )

    # --- preserved legacy collection ----------------------------------
    await db.flashcard_progress.create_index(
        [("user_id", 1), ("vocabulary_id", 1)], unique=True
    )


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
    try:
        await client.admin.command("ping")
        await ensure_indexes()
    except Exception:
        # The lifespan retry loop can call this method again.
        client.close()
        client = None
        db = None
        raise


async def close_mongo_connection():
    global client, db
    if client is not None:
        client.close()
    client = None
    db = None


def get_database() -> AsyncIOMotorDatabase:
    if db is None:
        raise RuntimeError("Database is not initialized")
    return db
