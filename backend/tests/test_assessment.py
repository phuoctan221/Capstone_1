from datetime import datetime, timezone

from bson import ObjectId

from app.db import mongodb
from tests.support import ApiTestCase


class AssessmentTests(ApiTestCase):
    async def add_a2_words(self):
        now = datetime.now(timezone.utc)
        docs = []
        for index in range(3):
            word = f"assessment-a2-{index}"
            docs.append({
                "_id": ObjectId(), "word": word, "word_key": word, "phonetic": "",
                "part_of_speech": "noun", "meaning": f"meaning a2 {index}",
                "meaning_key": f"meaning a2 {index}", "example": f"This is {word}.",
                "synonyms": [], "antonyms": [], "topic": "general", "domain": "general",
                "level": "A2", "created_at": now, "updated_at": now,
            })
        await mongodb.get_database().vocabularies.insert_many(docs)

    async def test_assessment_pass_unlocks_next_level_and_is_idempotent(self):
        await self.add_a2_words()
        headers = await self.auth_headers()
        user_id = (await self.client.get("/auth/me", headers=headers)).json()["id"]
        await mongodb.get_database().lesson_progress.insert_one({
            "user_id": user_id, "lesson_id": "general-a1", "completed": True,
        })
        blocked = await self.client.get("/lessons/general-a2", headers=headers)
        self.assertEqual(blocked.status_code, 400, blocked.text)

        attempt = await self.client.post("/assessments", json={"domain": "general", "level": "A1"}, headers=headers)
        self.assertEqual(attempt.status_code, 201, attempt.text)
        data = attempt.json()
        answers = []
        for question in data["questions"]:
            vocab = next(doc for doc in self.vocab if str(doc["_id"]) == question["vocabulary_id"])
            answer = vocab["meaning"] if question["skill"] == "meaning" else vocab["word"]
            answers.append({"exercise_item_id": question["exercise_item_id"], "answer": answer})
        submitted = await self.client.post(f"/assessments/attempts/{data['attempt_id']}/submit", json={"answers": answers}, headers=headers)
        self.assertEqual(submitted.status_code, 200, submitted.text)
        self.assertTrue(submitted.json()["passed"])
        replay = await self.client.post(f"/assessments/attempts/{data['attempt_id']}/submit", json={"answers": answers}, headers=headers)
        self.assertEqual(replay.status_code, 200, replay.text)
        self.assertEqual(replay.json()["percent"], submitted.json()["percent"])
        unlocked = await self.client.get("/lessons/general-a2", headers=headers)
        self.assertEqual(unlocked.status_code, 200, unlocked.text)

    async def test_assessment_requires_completed_level(self):
        headers = await self.auth_headers()
        response = await self.client.post("/assessments", json={"domain": "general", "level": "A1"}, headers=headers)
        self.assertEqual(response.status_code, 400, response.text)

    async def test_skip_learning_assessment_can_unlock_next_level(self):
        await self.add_a2_words()
        headers = await self.auth_headers()
        attempt = await self.client.post(
            "/assessments",
            json={"domain": "general", "level": "A1", "skip_learning": True},
            headers=headers,
        )
        self.assertEqual(attempt.status_code, 201, attempt.text)
        data = attempt.json()
        self.assertTrue(data["skip_learning"])
        answers = []
        for question in data["questions"]:
            vocab = next(doc for doc in self.vocab if str(doc["_id"]) == question["vocabulary_id"])
            answer = vocab["meaning"] if question["skill"] == "meaning" else vocab["word"]
            answers.append({"exercise_item_id": question["exercise_item_id"], "answer": answer})
        submitted = await self.client.post(
            f"/assessments/attempts/{data['attempt_id']}/submit",
            json={"answers": answers}, headers=headers,
        )
        self.assertEqual(submitted.status_code, 200, submitted.text)
        self.assertTrue(submitted.json()["passed"])
        unlocked = await self.client.get("/lessons/general-a2", headers=headers)
        self.assertEqual(unlocked.status_code, 200, unlocked.text)

    async def test_placement_assessment_opens_its_target_level_directly(self):
        await self.add_a2_words()
        now = datetime.now(timezone.utc)
        b1_docs = []
        for index in range(3):
            word = f"placement-b1-{index}"
            b1_docs.append({
                "_id": ObjectId(), "word": word, "word_key": word, "phonetic": "",
                "part_of_speech": "noun", "meaning": f"meaning b1 {index}",
                "meaning_key": f"meaning b1 {index}", "example": f"This is {word}.",
                "synonyms": [], "antonyms": [], "topic": "general", "domain": "general",
                "level": "B1", "created_at": now, "updated_at": now,
            })
        await mongodb.get_database().vocabularies.insert_many(b1_docs)
        headers = await self.auth_headers()
        attempt = await self.client.post(
            "/assessments",
            json={"domain": "general", "level": "B1", "skip_learning": True, "placement_target": "B1"},
            headers=headers,
        )
        self.assertEqual(attempt.status_code, 201, attempt.text)
        data = attempt.json()
        answers = []
        vocabulary = self.vocab + b1_docs
        for question in data["questions"]:
            vocab = next(doc for doc in vocabulary if str(doc["_id"]) == question["vocabulary_id"])
            answer = vocab["meaning"] if question["skill"] == "meaning" else vocab["word"]
            answers.append({"exercise_item_id": question["exercise_item_id"], "answer": answer})
        submitted = await self.client.post(
            f"/assessments/attempts/{data['attempt_id']}/submit", json={"answers": answers}, headers=headers
        )
        self.assertEqual(submitted.status_code, 200, submitted.text)
        self.assertTrue(submitted.json()["passed"])
        self.assertEqual(submitted.json()["opened_level"], "B1")

        lessons = await self.client.get("/lessons", headers=headers)
        by_id = {item["id"]: item for item in lessons.json()}
        self.assertTrue(by_id["general-b1"]["unlocked"])

    async def test_assessment_status_keeps_passed_levels_in_their_domain(self):
        headers = await self.auth_headers()
        user_id = (await self.client.get("/auth/me", headers=headers)).json()["id"]
        db = mongodb.get_database()
        now = datetime.now(timezone.utc)
        technology_word = {
            "_id": ObjectId(), "word": "assessment-tech-a1", "word_key": "assessment-tech-a1",
            "phonetic": "", "part_of_speech": "noun", "meaning": "technology meaning",
            "meaning_key": "technology meaning", "example": "Technology example.",
            "synonyms": [], "antonyms": [], "topic": "technology", "domain": "technology",
            "level": "A1", "created_at": now, "updated_at": now,
        }
        await db.vocabularies.insert_one(technology_word)
        await db.lesson_progress.insert_many([
            {"user_id": user_id, "lesson_id": "general-a1", "completed": True},
            {"user_id": user_id, "lesson_id": "technology-a1", "completed": True},
        ])
        await db.level_assessment_results.insert_one({
            "user_id": user_id, "domain": "general", "level": "A1", "passed_at": now,
        })

        response = await self.client.get("/progress/assessment-status", headers=headers)
        self.assertEqual(response.status_code, 200, response.text)
        domains = {item["id"]: item for item in response.json()["domains"]}
        general_a1 = next(item for item in domains["general"]["levels"] if item["level"] == "A1")
        technology_a1 = next(item for item in domains["technology"]["levels"] if item["level"] == "A1")
        self.assertEqual(general_a1["status"], "passed")
        self.assertEqual(technology_a1["status"], "ready")