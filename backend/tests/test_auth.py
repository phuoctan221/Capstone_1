from tests.support import ApiTestCase

PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\x0dIDAT\x08\xd7c\xf8\xff\xff?\x00\x05\xfe\x02\xfe"
    b"\xdc\xccY\xe7\x00\x00\x00\x00IEND\xaeB`\x82"
)


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

    async def test_onboarding_b1_opens_b1_and_marks_lower_levels_as_review(self):
        headers = await self.auth_headers()
        response = await self.client.post(
            "/auth/onboarding",
            json={"learning_level": "B1", "interests": ["general"]},
            headers=headers,
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["placement_levels"], {"general": "B1"})

        lessons = await self.client.get("/lessons", headers=headers)
        self.assertEqual(lessons.status_code, 200, lessons.text)
        by_id = {lesson["id"]: lesson for lesson in lessons.json()}
        self.assertTrue(by_id["general-a1"]["review_only"])
        self.assertTrue(by_id["general-a2"]["review_only"])

    async def test_user_can_upload_png_avatar(self):
        headers = await self.auth_headers()
        response = await self.client.post(
            "/auth/me/avatar",
            files={"avatar": ("profile.png", PNG_1X1, "image/png")},
            headers=headers,
        )
        self.assertEqual(response.status_code, 200, response.text)
        avatar_url = response.json()["avatar_url"]
        self.assertRegex(avatar_url, r"^/api/uploads/avatars/[a-f0-9]{32}\.png$")

        image = await self.client.get(avatar_url.removeprefix("/api"))
        self.assertEqual(image.status_code, 200)
        self.assertEqual(image.headers["content-type"], "image/png")

    async def test_avatar_rejects_non_image_upload(self):
        headers = await self.auth_headers()
        response = await self.client.post(
            "/auth/me/avatar",
            files={"avatar": ("not-an-image.txt", b"not an image", "text/plain")},
            headers=headers,
        )
        self.assertEqual(response.status_code, 415, response.text)
