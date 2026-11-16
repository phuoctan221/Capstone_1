from tests.support import ApiTestCase


class AuthTests(ApiTestCase):
    async def test_register_login_and_me(self):
        payload = await self.register()
        self.assertTrue(payload["access_token"])
        self.assertEqual(payload["user"]["role"], "user")
        self.assertEqual(payload["user"]["email"], self.email)

        login = await self.client.post(
            "/auth/login",
            json={"email": self.email, "password": "secret123"},
        )
        self.assertEqual(login.status_code, 200, login.text)
        token = login.json()["access_token"]

        me = await self.client.get(
            "/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(me.status_code, 200, me.text)
        self.assertEqual(me.json()["email"], self.email)

    async def test_duplicate_email_is_rejected(self):
        await self.register()
        response = await self.client.post(
            "/auth/register",
            json={"email": self.email, "username": "other", "password": "secret123"},
        )
        self.assertEqual(response.status_code, 409)

    async def test_wrong_password_is_rejected(self):
        await self.register()
        response = await self.client.post(
            "/auth/login",
            json={"email": self.email, "password": "wrong-password"},
        )
        self.assertEqual(response.status_code, 401)

    async def test_me_requires_token(self):
        response = await self.client.get("/auth/me")
        self.assertEqual(response.status_code, 401)

    async def test_client_cannot_choose_admin_role(self):
        response = await self.client.post(
            "/auth/register",
            json={
                "email": self.email,
                "username": "tester",
                "password": "secret123",
                "role": "admin",
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["user"]["role"], "user")

    async def test_admin_role_is_not_derived_from_email(self):
        payload = await self.register(email="admin@example.com")
        self.assertEqual(payload["user"]["role"], "user")

    async def test_email_is_normalized_on_register_and_login(self):
        payload = await self.register(email="User.Mixed@Example.com")
        self.assertEqual(payload["user"]["email"], "user.mixed@example.com")
        login = await self.client.post(
            "/auth/login",
            json={"email": "USER.MIXED@example.com", "password": "secret123"},
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.assertEqual(login.json()["user"]["role"], "user")

    async def test_onboarding_updates_profile(self):
        headers = await self.auth_headers()
        response = await self.client.post(
            "/auth/onboarding",
            json={"learning_level": "A2", "interests": ["technology", "business"]},
            headers=headers,
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["learning_level"], "A2")
        self.assertTrue(body["onboarded"])
        self.assertIsNotNone(body["profile_completed_at"])
