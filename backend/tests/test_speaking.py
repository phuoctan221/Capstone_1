import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from bson import ObjectId
from fastapi import HTTPException
from pydantic import ValidationError

from app.models.speaking import SpeakingRequest
from app.services import speaking_service as speaking
from app.routers import speaking_router as router


class SpeakingTests(unittest.IsolatedAsyncioTestCase):
    async def test_auto_selection_only_uses_learned_words_and_fills_twenty(self):
        from app.services import ai_service, progress_service
        available = {str(i): {"word": f"word{i}"} for i in range(25)}
        with patch.object(progress_service, "_states_with_vocab", AsyncMock(return_value=[])), patch.object(
            ai_service, "_call_ai", AsyncMock(return_value='{"ids": ["outside", "3", "3", null, "2"]}')
        ):
            result = await speaking.select_practice_words("me", available)
        self.assertEqual(len(result), 20)
        self.assertEqual(len(set(result)), 20)
        self.assertEqual(result[:2], ["3", "2"])
        self.assertTrue(set(result) <= set(available))

    async def test_auto_selection_handles_small_and_empty_vocabulary(self):
        result = await speaking.select_practice_words("me", {"1": {"word": "hello"}, "2": {"word": "Hello"}})
        self.assertEqual(result, ["1"])
        with self.assertRaises(HTTPException) as error:
            await speaking.select_practice_words("me", {})
        self.assertEqual(error.exception.status_code, 400)

    async def test_auto_selection_uses_progress_when_ai_fails(self):
        from app.services import ai_service, progress_service
        available = {str(i): {"word": f"word{i}"} for i in range(25)}
        with patch.object(progress_service, "_states_with_vocab", AsyncMock(return_value=[])), patch.object(
            ai_service, "_call_ai", AsyncMock(side_effect=ai_service.AIServiceError("private"))
        ):
            result = await speaking.select_practice_words("me", available)
        self.assertEqual(len(result), 20)
        self.assertTrue(set(result) <= set(available))

    async def test_auto_selection_fallback_prioritizes_low_mastery(self):
        from app.services import ai_service, progress_service
        available = {str(i): {"word": f"word{i}"} for i in range(25)}
        pairs = [({"mastery": {"meaning": 100 if i < 5 else 10}}, {"_id": str(i)}) for i in range(25)]
        for failure in [ai_service.AIServiceError("offline"), TimeoutError(), httpx.ConnectError("offline")]:
            with self.subTest(failure=type(failure).__name__), patch.object(
                progress_service, "_states_with_vocab", AsyncMock(return_value=pairs)
            ), patch.object(ai_service, "_call_ai", AsyncMock(side_effect=failure)):
                result = await speaking.select_practice_words("me", available)
            self.assertEqual(set(result), {str(i) for i in range(5, 25)})

    async def test_auto_exercise_is_saved_with_learned_source(self):
        collection = SimpleNamespace(insert_one=AsyncMock(return_value=SimpleNamespace(inserted_id=ObjectId())))
        with patch.object(speaking, "get_database", return_value={"speaking_exercises": collection}), patch.object(
            speaking, "learned_words", AsyncMock(return_value=[{"id": "one", "word": "hello"}])
        ):
            result = await speaking.create_exercise("me", SpeakingRequest(auto_select=True))
        self.assertEqual(result["items"], [{"text": "hello", "source": "learned"}])



    async def test_learned_words_uses_current_mastery_and_reviews(self):
        from app.services import progress_service
        words = [{"_id": ObjectId(), "word": word} for word in ["apple", "banana", "unused"]]
        pairs = [({"mastery": {"meaning": 10}}, words[0]),
                 ({"review_count": 1}, words[1]),
                 ({"mastery": {}, "review_count": 0}, words[2])]
        with patch.object(progress_service, "_states_with_vocab", AsyncMock(return_value=pairs)) as states:
            result = await speaking.learned_words("me")
        states.assert_awaited_once_with("me")
        self.assertEqual([word["word"] for word in result], ["apple", "banana"])

    def test_normalize_and_deduplicate_custom_words(self):
        data = SpeakingRequest(custom_words=[" Interview ", "interview", "good   morning"])
        self.assertEqual(data.custom_words, ["Interview", "good morning"])

    def test_reject_markup_and_extra_parameters(self):
        for args in [{"custom_words": ["<script>"]}, {"custom_words": ["hello"], "user_id": "other"}]:
            with self.assertRaises(ValidationError):
                SpeakingRequest(**args)

    async def test_reject_other_users_vocabulary(self):
        with patch.object(speaking, "learned_words", AsyncMock(return_value=[])):
            with self.assertRaises(HTTPException) as e:
                await speaking.create_exercise("me", SpeakingRequest(vocabulary_ids=[str(ObjectId())]))
            self.assertEqual(e.exception.status_code, 400)

    async def test_custom_words_do_not_modify_learning_progress(self):
        collection = SimpleNamespace(insert_one=AsyncMock(return_value=SimpleNamespace(inserted_id=ObjectId())))
        db = {"speaking_exercises": collection}
        with patch.object(speaking, "get_database", return_value=db), patch.object(speaking, "learned_words", AsyncMock(return_value=[])):
            result = await speaking.create_exercise("me", SpeakingRequest(custom_words=["hello"]))
        self.assertEqual(result["items"], [{"text": "hello", "source": "custom"}])
        self.assertEqual(collection.insert_one.call_args.args[0]["user_id"], "me")


    async def test_score_uses_provider_value_and_decodes_key_once(self):
        response = httpx.Response(200, json={"status": "success", "text_score": {"speechace_score": {"pronunciation": 71}, "word_score_list": []}})
        client = AsyncMock()
        client.post.return_value = response
        with patch.object(speaking.settings, "SPEECHACE_API_KEY", "abc%2Fdef"), patch.object(speaking.httpx, "AsyncClient") as factory:
            factory.return_value.__aenter__.return_value = client
            result = await speaking.score_speechace("hello", b"x" * 100, "audio/webm;codecs=opus")
        self.assertEqual(result["pronunciation"], 71)
        self.assertEqual(client.post.call_args.kwargs["params"]["key"], "abc/def")
        self.assertEqual(client.post.call_args.kwargs["data"]["text"], "hello")

    async def test_speechace_errors_do_not_expose_credentials(self):
        client = AsyncMock()
        client.post.side_effect = httpx.ConnectError("url?key=SECRET")
        with patch.object(speaking.settings, "SPEECHACE_API_KEY", "SECRET"), patch.object(speaking.httpx, "AsyncClient") as factory:
            factory.return_value.__aenter__.return_value = client
            with self.assertRaises(HTTPException) as e:
                await speaking.score_speechace("hello", b"x" * 100, "audio/webm")
        self.assertNotIn("SECRET", e.exception.detail)





if __name__ == "__main__":
    unittest.main()
