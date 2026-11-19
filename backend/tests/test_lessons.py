from datetime import datetime, timezone

from bson import ObjectId

from tests.support import ApiTestCase

from app.db import mongodb
from app.services import progress_service


class LessonTests(ApiTestCase):
    async def add_general_words(self, count: int, level: str = "A1"):
        now = datetime.now(timezone.utc)
        docs = []
        for index in range(count):
            word = f"{level.lower()}-extra-{index:02d}"
            docs.append(
                {
                    "_id": ObjectId(),
                    "word": word,
                    "word_key": word,
                    "phonetic": "",
                    "part_of_speech": "noun",
                    "meaning": f"nghĩa {index}",
                    "meaning_key": f"nghĩa {index}",
                    "example": f"This is {word}.",
                    "synonyms": [],
                    "antonyms": [],
                    "topic": "general",
                    "domain": "general",
                    "level": level,
                    "created_at": now,
                    "updated_at": now,
                }
            )
        await mongodb.get_database().vocabularies.insert_many(docs)

    async def test_list_lessons(self):
        headers = await self.auth_headers()
        response = await self.client.get("/lessons", headers=headers)
        self.assertEqual(response.status_code, 200, response.text)
        lessons = response.json()
        general = next(item for item in lessons if item["id"] == "general-a1")
        self.assertEqual(general["word_count"], 6)
        self.assertTrue(general["has_exercises"])
        self.assertEqual(general["domain"], "general")

    async def test_higher_level_requires_lower_completion(self):
        await self.add_general_words(2, level="A2")
        headers = await self.auth_headers()

        listed = await self.client.get("/lessons", headers=headers)
        self.assertEqual(listed.status_code, 200, listed.text)
        lessons = {item["id"]: item for item in listed.json()}
        self.assertTrue(lessons["general-a1"]["unlocked"])
        self.assertFalse(lessons["general-a2"]["unlocked"])
        self.assertEqual(
            lessons["general-a2"]["unlock_requirement"]["level"], "A1"
        )

        blocked = await self.client.get("/lessons/general-a2", headers=headers)
        self.assertEqual(blocked.status_code, 400, blocked.text)

        me = await self.client.get("/auth/me", headers=headers)
        await mongodb.get_database().lesson_progress.insert_one(
            {
                "user_id": me.json()["id"],
                "lesson_id": "general-a1",
                "completed": True,
            }
        )

        await mongodb.get_database().level_assessment_results.insert_one(
            {"user_id": me.json()["id"], "domain": "general", "level": "A1"}
        )

        listed = await self.client.get("/lessons", headers=headers)
        lessons = {item["id"]: item for item in listed.json()}
        self.assertTrue(lessons["general-a2"]["unlocked"])
        self.assertIsNone(lessons["general-a2"]["unlock_requirement"])

        unlocked = await self.client.get("/lessons/general-a2", headers=headers)
        self.assertEqual(unlocked.status_code, 200, unlocked.text)

    async def test_declared_b1_placement_opens_b1_without_lower_level_completion(self):
        await self.add_general_words(2, level="A2")
        await self.add_general_words(2, level="B1")
        headers = await self.auth_headers()
        me = await self.client.post(
            "/auth/onboarding",
            json={"learning_level": "B1", "interests": ["general"]},
            headers=headers,
        )
        self.assertEqual(me.status_code, 200, me.text)

        listed = await self.client.get("/lessons", headers=headers)
        self.assertEqual(listed.status_code, 200, listed.text)
        lessons = {item["id"]: item for item in listed.json()}
        self.assertTrue(lessons["general-b1"]["unlocked"])
        self.assertTrue(lessons["general-a1"]["review_only"])
        self.assertTrue(lessons["general-a2"]["review_only"])

        opened = await self.client.get("/lessons/general-b1", headers=headers)
        self.assertEqual(opened.status_code, 200, opened.text)

    async def test_lesson_detail_contains_words(self):
        headers = await self.auth_headers()
        response = await self.client.get("/lessons/general-a1", headers=headers)
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(len(body["words"]), 6)
        self.assertEqual(body["word_count"], 6)

    async def test_empty_lesson_and_unknown_lesson(self):
        headers = await self.auth_headers()
        empty = await self.client.get("/lessons/general-b2", headers=headers)
        self.assertEqual(empty.status_code, 404)

        unknown = await self.client.get("/lessons/does-not-exist", headers=headers)
        self.assertEqual(unknown.status_code, 404)

    async def test_units_are_sliced_and_listed(self):
        await self.add_general_words(15)
        headers = await self.auth_headers()

        listed = await self.client.get("/lessons", headers=headers)
        self.assertEqual(listed.status_code, 200, listed.text)
        general = next(item for item in listed.json() if item["id"] == "general-a1")
        self.assertEqual(general["total_words"], 21)
        self.assertEqual(general["unit_count"], 2)
        self.assertEqual(len(general["units"]), 2)
        self.assertEqual(general["units"][0]["word_count"], 15)
        self.assertEqual(general["units"][1]["word_count"], 6)
        self.assertEqual(general["next_unit"], 1)

        me = await self.client.get("/auth/me", headers=headers)
        await mongodb.get_database().lesson_progress.insert_one(
            {"user_id": me.json()["id"], "lesson_id": "general-a1", "unit": 1, "completed": True}
        )

        second = await self.client.get(
            "/lessons/general-a1", params={"unit": 2}, headers=headers
        )
        self.assertEqual(second.status_code, 200, second.text)
        body = second.json()
        self.assertEqual(body["unit"], 2)
        self.assertEqual(body["unit_count"], 2)
        self.assertEqual(body["total_words"], 21)
        self.assertEqual(body["word_count"], 6)
        self.assertEqual(len(body["words"]), 6)

    async def test_default_unit_is_first_incomplete(self):
        await self.add_general_words(15)
        headers = await self.auth_headers()
        me = await self.client.get("/auth/me", headers=headers)
        user_id = me.json()["id"]
        await mongodb.get_database().lesson_progress.insert_one(
            {
                "user_id": user_id,
                "lesson_id": "general-a1",
                "unit": 1,
                "completed": True,
            }
        )

        response = await self.client.get("/lessons/general-a1", headers=headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["unit"], 2)

        listed = await self.client.get("/lessons", headers=headers)
        general = next(item for item in listed.json() if item["id"] == "general-a1")
        self.assertEqual(general["next_unit"], 2)
        self.assertTrue(general["units"][0]["completed"])
        self.assertFalse(general["completed"])

    async def test_unit_out_of_range_is_rejected(self):
        headers = await self.auth_headers()
        response = await self.client.get(
            "/lessons/general-a1", params={"unit": 99}, headers=headers
        )
        self.assertEqual(response.status_code, 400, response.text)

    async def test_cannot_complete_a_unit_when_the_previous_unit_is_incomplete(self):
        await self.add_general_words(24)
        headers = await self.auth_headers()
        user_id = (await self.client.get("/auth/me", headers=headers)).json()["id"]
        with self.assertRaisesRegex(ValueError, "Complete Unit 1"):
            await progress_service.complete_lesson(
                user_id, "general-a1", "general", True, unit=2
            )
        missing = await mongodb.get_database().lesson_progress.find_one(
            {"user_id": user_id, "lesson_id": "general-a1", "unit": 2}
        )
        self.assertIsNone(missing)

    async def test_lesson_requires_auth(self):
        response = await self.client.get("/lessons")
        self.assertEqual(response.status_code, 401)
