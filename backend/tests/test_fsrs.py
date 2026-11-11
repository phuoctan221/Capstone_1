import unittest
from datetime import datetime, timedelta, timezone

from app.db import mongodb
from app.services.fsrs_service import (
    current_retrievability,
    new_card_state,
    schedule_review,
)
from tests.support import ApiTestCase


class FsrsUnitTests(unittest.TestCase):
    def test_new_card_state_is_utc_aware(self):
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        state = new_card_state(now)
        self.assertIsNotNone(state["card_json"])
        self.assertEqual(state["due_at"], now)
        self.assertIsNone(state["stability"])

    def test_naive_datetime_is_rejected(self):
        with self.assertRaises(ValueError):
            new_card_state(datetime(2026, 1, 1))

    def test_review_updates_due_and_schedules(self):
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        easy = schedule_review(None, 4, now)
        again = schedule_review(None, 1, now)
        self.assertGreater(easy["state"]["due_at"], now)
        self.assertGreater(again["state"]["due_at"], now)
        self.assertGreater(easy["state"]["due_at"], again["state"]["due_at"])
        self.assertGreater(easy["state"]["stability"], 0)
        self.assertGreater(easy["retrievability"], 0)

    def test_invalid_rating_is_rejected(self):
        with self.assertRaises(ValueError):
            schedule_review(None, 5, datetime.now(timezone.utc))

    def test_missing_card_has_zero_retrievability(self):
        self.assertEqual(current_retrievability(None), 0.0)


class FsrsApiTests(ApiTestCase):
    async def test_review_is_idempotent_and_schedules(self):
        headers = await self.auth_headers()
        vocab_id = self.vocab_id("apple")
        payload = {"vocabulary_id": vocab_id, "rating": 4, "review_id": "review-1"}
        first = await self.client.post("/learning/review", json=payload, headers=headers)
        self.assertEqual(first.status_code, 200, first.text)
        body = first.json()
        self.assertEqual(body["review_count"], 1)
        self.assertIsNotNone(body["fsrs"]["stability"])
        self.assertGreater(body["retrievability"], 0)

        duplicate = await self.client.post(
            "/learning/review", json=payload, headers=headers
        )
        self.assertEqual(duplicate.status_code, 200, duplicate.text)
        self.assertEqual(duplicate.json()["review_count"], 1)

        second = await self.client.post(
            "/learning/review",
            json={"vocabulary_id": vocab_id, "rating": 1, "review_id": "review-2"},
            headers=headers,
        )
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(second.json()["review_count"], 2)

        await mongodb.get_database().user_word_states.update_one(
            {"user_id": self.email, "vocabulary_id": vocab_id},
            {"$set": {"fsrs.due_at": datetime.now(timezone.utc) - timedelta(minutes=1)}},
        )
        due = await self.client.get("/learning/due", headers=headers)
        self.assertEqual(due.status_code, 200, due.text)
        self.assertEqual([card["vocabulary_id"] for card in due.json()], [vocab_id])

    async def test_invalid_vocabulary_is_rejected(self):
        headers = await self.auth_headers()
        response = await self.client.post(
            "/learning/review",
            json={"vocabulary_id": "not-an-object-id", "rating": 3},
            headers=headers,
        )
        self.assertEqual(response.status_code, 400)

    async def test_due_queue_does_not_create_states(self):
        headers = await self.auth_headers()
        response = await self.client.get("/learning/due", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])
