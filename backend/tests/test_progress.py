from tests.support import ApiTestCase


class ProgressTests(ApiTestCase):
    def vocab_by_id(self, vocab_id):
        return next(doc for doc in self.vocab if str(doc["_id"]) == vocab_id)

    async def start_and_answer(self, headers, answer_word="apple", attempt_id="a-1"):
        session = await self.client.post(
            "/learning/sessions",
            json={"lesson_id": "general-a1", "skills": ["meaning"], "count": 1},
            headers=headers,
        )
        self.assertEqual(session.status_code, 201, session.text)
        body = session.json()
        exercise = body["exercises"][0]
        vocab = self.vocab_by_id(exercise["vocabulary_id"])
        answer = vocab["meaning"] if answer_word == "apple" else answer_word
        result = await self.client.post(
            f"/learning/sessions/{body['session_id']}/answers",
            json={
                "exercise_item_id": exercise["exercise_item_id"],
                "answer": answer,
                "attempt_id": attempt_id,
            },
            headers=headers,
        )
        self.assertEqual(result.status_code, 200, result.text)
        return body, result.json()

    async def test_summary_mastery_and_history(self):
        headers = await self.auth_headers()
        await self.start_and_answer(headers)

        summary = await self.client.get("/progress/summary", headers=headers)
        self.assertEqual(summary.status_code, 200, summary.text)
        data = summary.json()
        self.assertEqual(data["words_started"], 1)
        self.assertEqual(data["correct_answers"], 1)
        self.assertEqual(data["wrong_answers"], 0)
        self.assertEqual(data["accuracy"], 100)
        self.assertEqual(data["xp"], 10)

        mastery = await self.client.get("/progress/mastery", headers=headers)
        self.assertEqual(mastery.status_code, 200, mastery.text)
        skills = mastery.json()["skills"]
        self.assertGreater(skills["meaning"]["average"], 0)
        self.assertEqual(skills["spelling"]["average"], 0)
        self.assertEqual(skills["context"]["average"], 0)

        history = await self.client.get("/progress/history", headers=headers)
        self.assertEqual(history.status_code, 200, history.text)
        items = history.json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["type"], "answer")
        self.assertTrue(items[0]["is_correct"])

        legacy = await self.client.get("/progress", headers=headers)
        self.assertEqual(legacy.status_code, 200, legacy.text)
        self.assertEqual(legacy.json()["words_learned"], 1)
        self.assertEqual(legacy.json()["xp"], 10)

    async def test_attempt_id_is_idempotent_for_xp(self):
        headers = await self.auth_headers()
        session = await self.client.post(
            "/learning/sessions",
            json={"lesson_id": "general-a1", "skills": ["meaning"], "count": 1},
            headers=headers,
        )
        exercise = session.json()["exercises"][0]
        vocab = self.vocab_by_id(exercise["vocabulary_id"])
        payload = {
            "exercise_item_id": exercise["exercise_item_id"],
            "answer": vocab["meaning"],
            "attempt_id": "same-attempt",
        }
        first = await self.client.post(
            f"/learning/sessions/{session.json()['session_id']}/answers",
            json=payload,
            headers=headers,
        )
        second = await self.client.post(
            f"/learning/sessions/{session.json()['session_id']}/answers",
            json=payload,
            headers=headers,
        )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        progress = await self.client.get("/progress", headers=headers)
        self.assertEqual(progress.json()["xp"], 10)

    async def test_legacy_study_answer_and_wrong_answer(self):
        headers = await self.auth_headers()
        vocab = self.vocab_by_id(self.vocab_id("book"))

        correct = await self.client.post(
            "/progress/study-answer",
            json={
                "vocabulary_id": str(vocab["_id"]),
                "answer": vocab["meaning"],
                "skill": "meaning",
                "attempt_id": "legacy-1",
            },
            headers=headers,
        )
        self.assertEqual(correct.status_code, 200, correct.text)
        self.assertTrue(correct.json()["is_correct"])

        wrong_vocab = self.vocab_by_id(self.vocab_id("chair"))
        wrong = await self.client.post(
            "/progress/study-answer",
            json={
                "vocabulary_id": str(wrong_vocab["_id"]),
                "answer": "definitely-wrong",
                "skill": "meaning",
                "attempt_id": "legacy-2",
            },
            headers=headers,
        )
        self.assertEqual(wrong.status_code, 200, wrong.text)
        self.assertFalse(wrong.json()["is_correct"])

        summary = await self.client.get("/progress/summary", headers=headers)
        data = summary.json()
        self.assertEqual(data["correct_answers"], 1)
        self.assertEqual(data["wrong_answers"], 1)
        self.assertEqual(data["xp"], 12)
        self.assertEqual(data["accuracy"], 50)
