from unittest.mock import AsyncMock, patch

from app.db import mongodb
from app.routers import lesson_router
from tests.support import ApiTestCase


class QuizTests(ApiTestCase):
    async def test_submit_returns_server_graded_wrong_answer_details(self):
        headers = await self.auth_headers()
        created = await self.client.get(
            "/lessons/general-a1/quiz", params={"count": 3}, headers=headers
        )
        self.assertEqual(created.status_code, 200, created.text)
        questions = created.json()["questions"]

        rows = []
        db = mongodb.get_database()
        for question in questions:
            stored = await db.quiz_questions.find_one(
                {"question_id": question["question_token"]}
            )
            wrong_answer = next(
                option for option in question["options"]
                if option != stored["correct_answer"]
            )
            rows.append(
                {
                    "vocabulary_id": question["vocabulary_id"],
                    "question_token": question["question_token"],
                    "user_answer": wrong_answer,
                }
            )

        submitted = await self.client.post(
            "/lessons/general-a1/quiz/submit",
            json={"lesson_id": "general-a1", "results": rows},
            headers=headers,
        )
        self.assertEqual(submitted.status_code, 200, submitted.text)
        body = submitted.json()
        self.assertEqual(body["correct"], 0)
        self.assertEqual(body["wrong_count"], 3)
        self.assertEqual(len(body["results"]), 3)
        self.assertTrue(all(not item["correct"] for item in body["results"]))
        self.assertTrue(all(item["question"] for item in body["results"]))
        self.assertTrue(all(item["correct_answer"] for item in body["results"]))

    async def test_batch_analysis_returns_null_for_one_ai_failure(self):
        headers = await self.auth_headers()
        analyses = [
            {
                "error_type": "Meaning",
                "what_went_wrong": "Bạn chọn nghĩa khác.",
                "explanation": "Hãy đối chiếu lại nghĩa của từ.",
                "correct_answer": "quả táo",
                "example": "I eat an apple.",
                "tip": "Ôn lại bằng flashcard.",
            }
        ]
        payload = {
            "mistakes": [
                {
                    "vocabulary_id": self.vocab_id("apple"),
                    "question": 'Từ "apple" có nghĩa là gì?',
                    "correct_answer": "quả táo",
                    "user_answer": "quyển sách",
                },
                {
                    "question": 'Từ "book" có nghĩa là gì?',
                    "correct_answer": "quyển sách",
                    "user_answer": "nước",
                },
            ]
        }
        with patch.object(lesson_router, "limit", AsyncMock()), patch.object(
            lesson_router.ai_service,
            "generate_error_analysis",
            AsyncMock(side_effect=[analyses[0], RuntimeError("AI unavailable")]),
        ):
            response = await self.client.post(
                "/lessons/quiz/analyze-all-mistakes", json=payload, headers=headers
            )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["analyses"], [analyses[0], None])