import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from bson import ObjectId

from app.db import mongodb
from tests.support import ApiTestCase, reset_database

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR / "scripts") not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR / "scripts"))

import migrate_mvp  # noqa: E402
import seed_mvp  # noqa: E402


class MigrationTests(ApiTestCase):
    async def test_legacy_data_migrates_idempotently(self):
        db = mongodb.get_database()
        now = datetime.now(timezone.utc)

        legacy_vocab_id = ObjectId()
        await db.vocabularies.insert_one(
            {
                "_id": legacy_vocab_id,
                "word": "Gravity",
                "meaning": "trọng lực",
                "example": "Gravity keeps us on the ground.",
                "topic": "science",
                "level": "A1",
                "created_at": now,
                "updated_at": now,
            }
        )
        await db.users.insert_one(
            {
                "_id": "legacy@example.com",
                "email": "legacy@example.com",
                "username": "legacy",
                "password_hash": "x",
                "created_at": now,
            }
        )
        await db.flashcard_progress.insert_one(
            {
                "user_id": "legacy@example.com",
                "vocabulary_id": str(legacy_vocab_id),
                "box": 3,
                "correct_count": 2,
                "wrong_count": 1,
                "next_review": now - timedelta(days=1),
                "last_reviewed": now - timedelta(days=2),
            }
        )
        await db.lesson_progress.insert_one(
            {"user_id": "legacy@example.com", "topic": "science", "completed": True}
        )

        first = await migrate_mvp.run_migration(True)
        self.assertEqual(first["vocabularies_backfilled"], 1)
        self.assertEqual(first["users_backfilled"], 1)
        self.assertEqual(first["flashcard_progress"]["created"], 1)
        self.assertEqual(first["lesson_progress_backfilled"], 1)

        vocab = await db.vocabularies.find_one({"_id": legacy_vocab_id})
        self.assertEqual(vocab["domain"], "general")
        self.assertEqual(vocab["word_key"], "gravity")
        self.assertEqual(vocab["meaning_key"], "trọng lực")

        user = await db.users.find_one({"_id": "legacy@example.com"})
        self.assertEqual(user["role"], "user")
        self.assertEqual(user["xp"], 0)
        self.assertEqual(user["streak"], 0)

        state = await db.user_word_states.find_one(
            {"user_id": "legacy@example.com", "vocabulary_id": str(legacy_vocab_id)}
        )
        self.assertIsNotNone(state)
        self.assertIsNone(state["fsrs"]["difficulty"])
        self.assertIsNone(state["fsrs"]["stability"])
        self.assertEqual(state["legacy_leitner_box"], 3)
        self.assertEqual(state["mastery"], {"meaning": 0.0, "spelling": 0.0, "context": 0.0})
        self.assertIsNotNone(state["fsrs"]["due_at"].tzinfo)

        progress = await db.lesson_progress.find_one(
            {"user_id": "legacy@example.com"}
        )
        self.assertEqual(progress["lesson_id"], "general")
        self.assertEqual(progress["domain"], "general")

        second = await migrate_mvp.run_migration(True)
        self.assertEqual(second["vocabularies_backfilled"], 0)
        self.assertEqual(second["users_backfilled"], 0)
        self.assertEqual(second["flashcard_progress"]["created"], 0)
        self.assertEqual(second["flashcard_progress"]["skipped"], 1)
        self.assertEqual(second["lesson_progress_backfilled"], 0)

    async def test_seed_is_idempotent(self):
        await reset_database()
        words = [
            {"word": "alpha", "meaning": "anpha", "example": "The alpha value is one.", "domain": "general", "level": "A1"},
            {"word": "bravo", "meaning": "bravo", "example": "He shouted bravo loudly.", "domain": "general", "level": "A1"},
            {"word": "charlie", "meaning": "charlie", "example": "Charlie is a name.", "domain": "general", "level": "A1"},
            {"word": "delta", "meaning": "delta", "example": "The delta is small.", "domain": "general", "level": "A1"},
            {"word": "echo", "meaning": "tiếng vang", "example": "We heard an echo.", "domain": "general", "level": "A1"},
            {"word": "foxtrot", "meaning": "foxtrot", "example": "Foxtrot is a dance.", "domain": "general", "level": "A1"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "seed.json"
            source.write_text(json.dumps(words), encoding="utf-8")

            first = await seed_mvp.run_seed(True, source)
            self.assertEqual(first["vocabulary"]["created"], 6)
            self.assertEqual(first["exercise_items"], 18)

            second = await seed_mvp.run_seed(True, source)
            self.assertEqual(second["vocabulary"]["created"], 0)
            self.assertEqual(second["vocabulary_in_db"], 6)

        db = mongodb.get_database()
        self.assertEqual(await db.vocabularies.count_documents({}), 6)
        self.assertEqual(
            await db.vocabularies.count_documents({"word": "alpha"}), 1
        )


if __name__ == "__main__":
    unittest.main()
