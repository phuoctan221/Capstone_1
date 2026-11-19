import json
import unittest
from unittest.mock import patch

import httpx

from app.services import mistral_service as mistral
from app.services.ai_service import AIServiceError


class MistralTests(unittest.IsolatedAsyncioTestCase):
    async def call_with(self, handler):
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        with patch.object(mistral.settings, "MISTRAL_API_KEY", "test-secret"), patch.object(mistral.httpx, "AsyncClient", return_value=client):
            return await mistral.generate_json("Write a story as JSON")

    async def test_json_request_and_auth(self):
        def handler(request):
            self.assertEqual(str(request.url), "https://api.mistral.ai/v1/chat/completions")
            self.assertEqual(request.headers["Authorization"], "Bearer test-secret")
            body = json.loads(request.content)
            self.assertEqual(body["response_format"], {"type": "json_object"})
            self.assertEqual(body["model"], mistral.settings.MISTRAL_MODEL)
            return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": '{"title":"A story"}'}}]})
        self.assertEqual(await self.call_with(handler), '{"title":"A story"}')

    async def test_rejects_failed_and_incomplete_responses_without_leaking_details(self):
        cases = [
            httpx.Response(401, json={"message": "test-secret"}),
            httpx.Response(429, json={"message": "test-secret"}),
            httpx.Response(200, json={"choices": []}),
            httpx.Response(200, json={"choices": [{"finish_reason": "length", "message": {"content": "partial"}}]}),
            httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": ""}}]}),
        ]
        for response in cases:
            with self.subTest(status=response.status_code), self.assertRaises(AIServiceError) as error:
                await self.call_with(lambda request: response)
            self.assertNotIn("test-secret", str(error.exception))

    async def test_missing_key_does_not_send_request(self):
        with patch.object(mistral.settings, "MISTRAL_API_KEY", ""), patch.object(mistral.httpx, "AsyncClient") as client:
            with self.assertRaises(AIServiceError):
                await mistral.generate_json("story")
            client.assert_not_called()
