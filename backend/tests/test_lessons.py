from tests.support import ApiTestCase


class LessonTests(ApiTestCase):
    async def test_list_lessons(self):
        headers = await self.auth_headers()
        response = await self.client.get("/lessons", headers=headers)
        self.assertEqual(response.status_code, 200, response.text)
        lessons = response.json()
        general = next(item for item in lessons if item["id"] == "general-a1")
        self.assertEqual(general["word_count"], 6)
        self.assertTrue(general["has_exercises"])
        self.assertEqual(general["domain"], "general")

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

    async def test_lesson_requires_auth(self):
        response = await self.client.get("/lessons")
        self.assertEqual(response.status_code, 401)
