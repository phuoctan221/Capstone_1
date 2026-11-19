from unittest.mock import AsyncMock, patch

from app.db import mongodb
from tests.support import ApiTestCase


class PasswordResetTests(ApiTestCase):
    async def test_reset_updates_password_and_invalidates_old_token(self):
        payload = await self.register(password="oldpass123")
        old_headers = {"Authorization": f"Bearer {payload['access_token']}"}
        sent = []

        async def capture(email, otp):
            sent.append((email, otp))

        with patch("app.services.email_service.send_password_reset_email", new=AsyncMock(side_effect=capture)):
            requested = await self.client.post("/auth/password-reset/request", json={"email": self.email})
        self.assertEqual(requested.status_code, 200, requested.text)
        self.assertEqual(len(sent), 1)
        otp = sent[0][1]
        verified = await self.client.post("/auth/password-reset/verify", json={"email": self.email, "otp": otp})
        self.assertEqual(verified.status_code, 200, verified.text)
        confirmed = await self.client.post("/auth/password-reset/confirm", json={"email": self.email, "otp": otp, "new_password": "newpass123"})
        self.assertEqual(confirmed.status_code, 200, confirmed.text)
        self.assertEqual((await self.client.get("/auth/me", headers=old_headers)).status_code, 401)
        old_login = await self.client.post("/auth/login", json={"email": self.email, "password": "oldpass123"})
        self.assertEqual(old_login.status_code, 401)
        new_login = await self.client.post("/auth/login", json={"email": self.email, "password": "newpass123"})
        self.assertEqual(new_login.status_code, 200, new_login.text)
        reused = await self.client.post("/auth/password-reset/confirm", json={"email": self.email, "otp": otp, "new_password": "another123"})
        self.assertEqual(reused.status_code, 400)

    async def test_unknown_email_receives_neutral_response_without_sending(self):
        with patch("app.services.email_service.send_password_reset_email", new=AsyncMock()) as sender:
            response = await self.client.post("/auth/password-reset/request", json={"email": "nobody@example.com"})
        self.assertEqual(response.status_code, 200)
        sender.assert_not_awaited()