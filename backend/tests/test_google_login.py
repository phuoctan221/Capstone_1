import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException, Response
from pymongo.errors import DuplicateKeyError

from app.routers import oauth_router as oauth
from app.services.auth_service import verify_password


class GoogleLoginTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db = SimpleNamespace(
            oauth_states=SimpleNamespace(insert_one=AsyncMock(), find_one_and_delete=AsyncMock()),
            users=SimpleNamespace(find_one=AsyncMock(return_value=None), insert_one=AsyncMock()),
        )
        self.credentials = patch.object(oauth, "credentials", return_value=("client", "secret"))
        self.database = patch.object(oauth, "get_database", return_value=self.db)
        self.credentials.start()
        self.database.start()
        self.addCleanup(self.credentials.stop)
        self.addCleanup(self.database.stop)

    async def test_start_binds_browser_and_pkce(self):
        result = await oauth.start("google", Response())
        record = self.db.oauth_states.insert_one.call_args.args[0]
        self.assertEqual(record["browser_hash"], oauth.digest(result["browser_secret"]))
        self.assertIn("code_challenge_method=S256", result["authorization_url"])
        self.assertNotIn(record["verifier"], result["authorization_url"])
        self.assertLess(record["expires_at"], datetime.now(timezone.utc) + timedelta(minutes=11))

    async def test_invalid_state_never_calls_google(self):
        self.db.oauth_states.find_one_and_delete.return_value = None
        with patch.object(oauth, "provider_identity", new_callable=AsyncMock) as identity:
            with self.assertRaises(HTTPException) as error:
                await oauth.exchange("google", oauth.ExchangeRequest(code="x", state="bad", browser_secret="s" * 32), Response())
            self.assertEqual(error.exception.status_code, 400)
            identity.assert_not_awaited()
        query = self.db.oauth_states.find_one_and_delete.call_args.args[0]
        self.assertIn("$gt", query["expires_at"])
        self.assertEqual(query["browser_hash"], oauth.digest("s" * 32))

    async def test_new_google_account_gets_session_and_onboarding(self):
        with patch.object(oauth, "provider_identity", new_callable=AsyncMock, return_value=("123", "google@example.com", "Google User")):
            result = await oauth.exchange("google", oauth.ExchangeRequest(code="x", state="state", browser_secret="s" * 32), Response())
        self.assertTrue(result.access_token)
        self.assertFalse(result.user.onboarded)
        self.assertEqual(self.db.users.insert_one.call_args.args[0]["oauth_identity"], "google:123")

    async def test_existing_password_account_is_not_silently_linked(self):
        self.db.users.insert_one.side_effect = DuplicateKeyError("duplicate")
        with patch.object(oauth, "provider_identity", new_callable=AsyncMock, return_value=("123", "existing@example.com", "User")):
            with self.assertRaises(HTTPException) as error:
                await oauth.exchange("google", oauth.ExchangeRequest(code="x", state="state", browser_secret="s" * 32), Response())
            self.assertEqual(error.exception.status_code, 409)

    def test_passwordless_user_rejects_password(self):
        self.assertFalse(verify_password("anything", ""))


if __name__ == "__main__":
    unittest.main()
