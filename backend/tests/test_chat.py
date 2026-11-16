from unittest.mock import AsyncMock, patch

from app.routers import chat_router
from app.services import ai_service
from tests.support import ApiTestCase


class ChatTests(ApiTestCase):
    async def test_chat_requires_authentication(self):
        response = await self.client.post("/chat/messages", json={"message": "Hello"})
        self.assertEqual(response.status_code, 401)

    async def test_chat_validates_message_and_returns_ai_response(self):
        headers = await self.auth_headers()
        with patch.object(chat_router, "limit", AsyncMock()), patch(
            "app.services.chat_service.ai_service._call_ai",
            AsyncMock(return_value="Bạn có thể dùng **say** khi tập trung vào nội dung lời nói."),
        ) as call_ai:
            response = await self.client.post(
                "/chat/messages",
                json={
                    "message": "Phân biệt say và tell",
                    "context": {"page": "vocabulary"},
                    "history": [{"role": "user", "content": "Mình đang học từ vựng."}],
                },
                headers=headers,
            )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertIn("say", body["message"])
        self.assertEqual(len(body["suggestions"]), 3)
        self.assertFalse(call_ai.await_args.kwargs["expect_json"])

    async def test_chat_unwraps_legacy_response_json_without_showing_response_label(self):
        headers = await self.auth_headers()
        with patch.object(chat_router, "limit", AsyncMock()), patch(
            "app.services.chat_service.ai_service._call_ai",
            AsyncMock(return_value='{"response":"Nội dung trả lời dành cho người học."}'),
        ):
            response = await self.client.post(
                "/chat/messages", json={"message": "Giải thích thì hiện tại"}, headers=headers
            )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["message"], "Nội dung trả lời dành cho người học.")

    async def test_chat_maps_ai_quota_to_429(self):
        headers = await self.auth_headers()
        with patch.object(chat_router, "limit", AsyncMock()), patch(
            "app.services.chat_service.ai_service._call_ai",
            AsyncMock(side_effect=ai_service.AIQuotaError("quota")),
        ):
            response = await self.client.post(
                "/chat/messages", json={"message": "Giúp mình học"}, headers=headers
            )
        self.assertEqual(response.status_code, 429, response.text)

    async def test_chat_hides_provider_failure_behind_safe_503(self):
        headers = await self.auth_headers()
        with patch.object(chat_router, "limit", AsyncMock()), patch(
            "app.services.chat_service.ai_service._call_ai",
            AsyncMock(side_effect=ai_service.AIServiceError("provider token must stay private")),
        ):
            response = await self.client.post(
                "/chat/messages", json={"message": "Giúp mình học"}, headers=headers
            )
        self.assertEqual(response.status_code, 503, response.text)
        self.assertNotIn("token", response.json()["detail"].lower())