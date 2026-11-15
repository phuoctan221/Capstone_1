from tests.support import ApiTestCase

SECRET_KEYS = {"correct_answer", "accepted_answers"}


class SessionTests(ApiTestCase):
    async def create_session(self, headers, count=5):
        response = await self.client.post(
            "/learning/sessions",
            json={
                "lesson_id": "general-a1",
                "skills": ["meaning", "spelling", "context"],
                "count": count,
            },
            headers=headers,
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def answer_for(self, exercise):
        vocab = next(
            doc for doc in self.vocab if str(doc["_id"]) == exercise["vocabulary_id"]
        )
        if exercise["skill"] == "meaning":
            return vocab["meaning"]
        return vocab["word"]

    async def test_questions_never_leak_answers(self):
        headers = await self.auth_headers()
        session = await self.create_session(headers)
        self.assertEqual(len(session["exercises"]), 5)
        for exercise in session["exercises"]:
            self.assertFalse(SECRET_KEYS & set(exercise.keys()))

        fetched = await self.client.get(
            f"/learning/sessions/{session['session_id']}/exercises", headers=headers
        )
        self.assertEqual(fetched.status_code, 200, fetched.text)
        for exercise in fetched.json()["exercises"]:
            self.assertFalse(SECRET_KEYS & set(exercise.keys()))

    async def test_answer_is_idempotent_and_session_completes(self):
        headers = await self.auth_headers()
        session = await self.create_session(headers)
        session_id = session["session_id"]

        first = session["exercises"][0]
        attempt_id = "attempt-1"
        payload = {
            "exercise_item_id": first["exercise_item_id"],
            "answer": self.answer_for(first),
            "attempt_id": attempt_id,
        }
        correct = await self.client.post(
            f"/learning/sessions/{session_id}/answers", json=payload, headers=headers
        )
        self.assertEqual(correct.status_code, 200, correct.text)
        self.assertTrue(correct.json()["is_correct"])

        duplicate = await self.client.post(
            f"/learning/sessions/{session_id}/answers", json=payload, headers=headers
        )
        self.assertEqual(duplicate.status_code, 200, duplicate.text)
        self.assertEqual(duplicate.json()["attempt_id"], attempt_id)

        state = await self.client.get(
            f"/learning/sessions/{session_id}", headers=headers
        )
        self.assertEqual(state.json()["answered_count"], 1)

        for index, exercise in enumerate(session["exercises"][1:], start=2):
            response = await self.client.post(
                f"/learning/sessions/{session_id}/answers",
                json={
                    "exercise_item_id": exercise["exercise_item_id"],
                    "answer": self.answer_for(exercise),
                    "attempt_id": f"attempt-{index}",
                },
                headers=headers,
            )
            self.assertEqual(response.status_code, 200, response.text)

        finished = await self.client.post(
            f"/learning/sessions/{session_id}/finish", headers=headers
        )
        self.assertEqual(finished.status_code, 200, finished.text)
        result = finished.json()
        self.assertTrue(result["passed"])
        self.assertEqual(result["percent"], 100)
        self.assertTrue(result["lesson_completed"])

        again = await self.client.post(
            f"/learning/sessions/{session_id}/finish", headers=headers
        )
        self.assertEqual(again.status_code, 200, again.text)
        self.assertEqual(again.json()["percent"], 100)

        late = await self.client.post(
            f"/learning/sessions/{session_id}/answers",
            json={
                "exercise_item_id": first["exercise_item_id"],
                "answer": "late",
                "attempt_id": "attempt-late",
            },
            headers=headers,
        )
        self.assertEqual(late.status_code, 400)

    async def test_session_is_scoped_to_owner(self):
        headers = await self.auth_headers()
        session = await self.create_session(headers)

        other = await self.auth_headers(f"other-{self.email}")
        response = await self.client.get(
            f"/learning/sessions/{session['session_id']}", headers=other
        )
        self.assertEqual(response.status_code, 404)

    async def test_invalid_lesson_is_rejected(self):
        headers = await self.auth_headers()
        response = await self.client.post(
            "/learning/sessions",
            json={"lesson_id": "general-b2", "skills": ["meaning"], "count": 5},
            headers=headers,
        )
        self.assertEqual(response.status_code, 400)
