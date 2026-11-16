from datetime import datetime, timedelta, timezone

from tests.support import ApiTestCase

from app.db import mongodb


class DailyPlanTests(ApiTestCase):
    async def test_new_user_plan_defaults(self):
        headers = await self.auth_headers()

        response = await self.client.get(
            "/learning/daily", params={"tz_offset": 420}, headers=headers
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()

        self.assertEqual(data["goal"], 10)
        self.assertEqual(data["studied_today"], 0)
        self.assertFalse(data["goal_met"])
        self.assertEqual(data["remaining"], 10)
        self.assertEqual(data["due_count"], 0)
        self.assertEqual(len(data["week"]), 7)
        self.assertEqual(data["week"][-1]["date"], data["date"])
        self.assertTrue(data["week"][-1]["studied_flag"] is False)
        self.assertGreaterEqual(data["new_count"], 1)
        self.assertIsNotNone(data["next_lesson"])
        self.assertTrue(data["next_lesson"]["href"].startswith("/lessons/"))
        self.assertEqual({task["id"] for task in data["tasks"]}, {"review", "new", "goal"})

    async def test_answered_today_updates_plan(self):
        headers = await self.auth_headers()

        session = await self.client.post(
            "/learning/sessions",
            json={"lesson_id": "general-a1", "skills": ["meaning"], "count": 1},
            headers=headers,
        )
        self.assertEqual(session.status_code, 201, session.text)
        body = session.json()
        exercise = body["exercises"][0]
        vocab = next(
            doc for doc in self.vocab if str(doc["_id"]) == exercise["vocabulary_id"]
        )

        answer = await self.client.post(
            f"/learning/sessions/{body['session_id']}/answers",
            json={
                "exercise_item_id": exercise["exercise_item_id"],
                "answer": vocab["meaning"],
                "attempt_id": "daily-attempt-1",
            },
            headers=headers,
        )
        self.assertEqual(answer.status_code, 200, answer.text)

        response = await self.client.get(
            "/learning/daily", params={"tz_offset": 420}, headers=headers
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()

        self.assertEqual(data["studied_today"], 1)
        self.assertEqual(data["answered_today"], 1)
        self.assertEqual(data["correct_today"], 1)
        self.assertEqual(data["xp_today"], 10)
        self.assertEqual(data["remaining"], 9)
        self.assertFalse(data["goal_met"])
        today = data["week"][-1]
        self.assertEqual(today["studied"], 1)
        self.assertEqual(today["answered"], 1)
        self.assertEqual(today["correct"], 1)
        self.assertEqual(today["xp"], 10)

    async def test_due_word_appears_in_plan(self):
        headers = await self.auth_headers()
        me = await self.client.get("/auth/me", headers=headers)
        user_id = me.json()["id"]
        vocab_id = self.vocab_id("apple")

        now = datetime.now(timezone.utc)
        await mongodb.get_database().user_word_states.insert_one(
            {
                "user_id": user_id,
                "vocabulary_id": vocab_id,
                "fsrs": {"due_at": now - timedelta(minutes=5), "card_json": None},
                "mastery": {},
                "review_count": 0,
                "started_at": now,
                "updated_at": now,
            }
        )

        response = await self.client.get(
            "/learning/daily", params={"tz_offset": 420}, headers=headers
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()

        self.assertEqual(data["due_count"], 1)
        self.assertEqual([item["word"] for item in data["due_preview"]], ["apple"])
        review_task = next(task for task in data["tasks"] if task["id"] == "review")
        self.assertFalse(review_task["done"])
        self.assertEqual(review_task["count"], 1)

    async def test_legacy_topic_without_domain_is_offered(self):
        headers = await self.auth_headers()
        now = datetime.now(timezone.utc)
        await mongodb.get_database().vocabularies.insert_one(
            {
                "word": "aardvark",
                "word_key": "aardvark",
                "phonetic": "",
                "part_of_speech": "noun",
                "meaning": "thú ăn kiến",
                "meaning_key": "thú ăn kiến",
                "example": "The aardvark digs at night.",
                "synonyms": [],
                "antonyms": [],
                "topic": "academic",
                "level": "A1",
                "created_at": now,
                "updated_at": now,
            }
        )

        response = await self.client.get(
            "/learning/daily", params={"tz_offset": 420}, headers=headers
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()

        first = data["new_preview"][0]
        self.assertEqual(first["word"], "aardvark")
        self.assertEqual(first["domain"], "general")

    async def test_timezone_offset_is_validated(self):
        headers = await self.auth_headers()

        response = await self.client.get(
            "/learning/daily", params={"tz_offset": 2000}, headers=headers
        )
        self.assertEqual(response.status_code, 422)
