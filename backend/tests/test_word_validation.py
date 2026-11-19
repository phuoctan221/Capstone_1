import unittest
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import HTTPException

from app.services import word_validation_service as words, speaking_service
from app.models.speaking import SpeakingRequest


class WordValidationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        words._verified.clear()

    async def check_with(self, raw, handler):
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        with patch.object(words.httpx, "AsyncClient", return_value=client):
            return await words.check_word(raw)

    def entry(self, word):
        return [{"word": word, "meanings": [{"definitions": [{"definition": "A dictionary definition."}]}]}]

    async def test_valid_word_normalized_and_cached(self):
        result = await self.check_with(" Invoice ", lambda request: httpx.Response(200, json=self.entry("invoice")))
        self.assertTrue(result["valid"])
        self.assertEqual(result["word"], "invoice")
        self.assertIn("invoice", words._verified)

    async def test_typo_suggestions_are_verified(self):
        def handler(request):
            if request.url.host == "api.datamuse.com":
                return httpx.Response(200, json=[{"word": "invoice"}, {"word": "invocee"}, {"word": "invoice"}])
            if request.url.path.endswith("/invoice"):
                return httpx.Response(200, json=self.entry("invoice"))
            return httpx.Response(404)
        result = await self.check_with("invoce", handler)
        self.assertFalse(result["valid"])
        self.assertEqual([s["word"] for s in result["suggestions"]], ["invoice"])

    async def test_unknown_word_and_outage_are_different(self):
        result = await self.check_with("qzxqzx", lambda r: httpx.Response(200, json=[]) if r.url.host == "api.datamuse.com" else httpx.Response(404))
        self.assertFalse(result["valid"])
        self.assertEqual(result["suggestions"], [])
        with self.assertRaises(HTTPException) as error:
            await self.check_with("hello", lambda r: httpx.Response(503))
        self.assertEqual(error.exception.status_code, 503)
        self.assertNotIn("hello", words._verified)

    async def test_dictionary_must_match_requested_word(self):
        result = await self.check_with("invoce", lambda r: httpx.Response(200, json=self.entry("invoice")) if r.url.host != "api.datamuse.com" else httpx.Response(200, json=[]))
        self.assertFalse(result["valid"])

    async def test_invalid_input_never_reaches_dictionary(self):
        for value in ["<script>", "hello123", "hello world", "https://example.com", ""]:
            with self.subTest(value=value), patch.object(words, "lookup", AsyncMock()) as lookup:
                with self.assertRaises(HTTPException):
                    await words.check_word(value)
                lookup.assert_not_awaited()

    async def test_direct_create_cannot_bypass_validation(self):
        with patch.object(words, "check_word", AsyncMock(return_value={"word": "qzxqzx", "valid": False})), patch.object(speaking_service, "get_database") as database:
            with self.assertRaises(HTTPException) as error:
                await speaking_service.create_exercise("me", SpeakingRequest(custom_words=["qzxqzx"]))
        self.assertEqual(error.exception.status_code, 422)
        database.assert_not_called()
