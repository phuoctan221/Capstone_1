import unittest
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import HTTPException

from app.services import chivox_service as chivox, speaking_service as speaking
from app.routers import speaking_router as router
from bson import ObjectId
from types import SimpleNamespace


class ChivoxTests(unittest.IsolatedAsyncioTestCase):
    def test_valid_scores_remain_distinct_and_auth_metadata_is_not_returned(self):
        result = chivox.normalize("hello", {"app": {"sig": "private"}, "tokenId": "private", "result": {
            "overall": 89, "pron": 87, "wavetime": 1300, "forceout": 0,
            "details": {"word": [{"name": "hello", "phone": [{"lab": "hh", "rec": "hh", "is_err": 0}]}]}}})
        self.assertEqual(result["overall"], 89)
        self.assertEqual(result["pronunciation"], 87)
        self.assertIsNone(result["words"][0]["quality_score"])
        self.assertNotIn("private", str(result))

    def test_failed_alignment_is_retry_even_when_provider_returns_high_score(self):
        result = chivox.normalize("abandon", {"result": {"overall": 74, "pron": 74, "forceout": 1, "wavetime": 1300}})
        self.assertEqual(result["status"], "retry")
        self.assertIsNone(result["overall"])
        self.assertIsNone(result["pronunciation"])

    def test_no_score_is_not_invented(self):
        with self.assertRaises(HTTPException):
            chivox.normalize("hello", {"result": {"details": {}}})

    def test_warning_is_preserved(self):
        result = chivox.normalize("hello", {"result": {"overall": 89, "info": {"tipId": 10006}}})
        self.assertIn("Chưa nghe rõ", result["warning"])
        self.assertNotIn("10006", result["warning"])

    def test_rpc_errors_never_expose_upstream_message(self):
        with self.assertRaises(HTTPException) as error:
            chivox.rpc_body(httpx.Response(403, json={"error": "secret"}))
        self.assertNotIn("secret", error.exception.detail)

    async def test_provider_dispatch_does_not_fallback_to_speechace(self):
        with patch.object(speaking.settings, "PRONUNCIATION_PROVIDER", "chivox"), patch.object(chivox, "score_audio", AsyncMock(side_effect=HTTPException(502, "offline"))), patch.object(speaking, "score_speechace", AsyncMock()) as other:
            with self.assertRaises(HTTPException):
                await speaking.score_audio("hello", b"audio", "audio/wav")
            other.assert_not_awaited()

    async def test_retry_result_is_saved(self):
        async def chunks():
            yield b"audio"
        request = SimpleNamespace(stream=chunks, headers={"content-type": "audio/webm"})
        collection = SimpleNamespace(update_one=AsyncMock())
        retry = {"provider": "chivox", "status": "retry", "warning": "Read again", "overall": None}
        with patch.object(router, "limit", AsyncMock()), patch.object(router, "get_database", return_value={"speaking_exercises": collection}), patch.object(speaking, "get_exercise", AsyncMock(return_value={"items": [{"text": "hello"}]})), patch.object(speaking, "score_audio", AsyncMock(return_value=retry)):
            result = await router.score(str(ObjectId()), 0, request, {"id": "me"})
        collection.update_one.assert_awaited_once()
        self.assertEqual(result["warning"], "Read again")
