from tests.support import ApiTestCase


class AdminTests(ApiTestCase):
    async def test_admin_endpoints_require_admin(self):
        headers = await self.auth_headers()
        for method, path in (
            ("get", "/admin/vocabularies"),
            ("get", "/admin/users"),
            ("get", "/admin/lessons"),
            ("get", "/admin/exercises"),
            ("get", "/admin/stats"),
            ("get", "/admin/domains"),
        ):
            response = await getattr(self.client, method)(path, headers=headers)
            self.assertEqual(response.status_code, 403, path)

    async def test_admin_vocabulary_list(self):
        headers = await self.make_admin()
        response = await self.client.get("/admin/vocabularies", headers=headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["total"], 10)

    async def test_lesson_crud_and_exercise_regeneration(self):
        headers = await self.make_admin()

        created = await self.client.post(
            "/admin/lessons",
            json={"domain": "general", "level": "B1", "title": "General B1"},
            headers=headers,
        )
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.json()["id"], "general-b1")

        listing = await self.client.get("/admin/lessons", headers=headers)
        self.assertIn("general-b1", [item["id"] for item in listing.json()])

        updated = await self.client.put(
            "/admin/lessons/general-b1",
            json={"title": "General B1 updated"},
            headers=headers,
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["title"], "General B1 updated")

        regenerated = await self.client.post(
            "/admin/exercises/regenerate",
            params={"lesson_id": "general-a1"},
            headers=headers,
        )
        self.assertEqual(regenerated.status_code, 200, regenerated.text)
        self.assertEqual(regenerated.json()["items"], 18)

        exercises = await self.client.get(
            "/admin/exercises",
            params={"lesson_id": "general-a1"},
            headers=headers,
        )
        self.assertEqual(exercises.status_code, 200, exercises.text)
        self.assertEqual(exercises.json()["total"], 18)

        deleted = await self.client.delete("/admin/lessons/general-b1", headers=headers)
        self.assertEqual(deleted.status_code, 204)

    async def test_users_and_role_management(self):
        admin_email = "admin@example.com"
        headers = await self.make_admin(admin_email)

        users = await self.client.get("/admin/users", headers=headers)
        self.assertEqual(users.status_code, 200, users.text)
        self.assertGreaterEqual(users.json()["total"], 1)
        for item in users.json()["items"]:
            self.assertNotIn("password_hash", item)

        last_admin = await self.client.put(
            f"/admin/users/{admin_email}/role",
            params={"role": "user"},
            headers=headers,
        )
        self.assertEqual(last_admin.status_code, 400)

        other_email = "second@example.com"
        await self.register(other_email)
        promoted = await self.client.put(
            f"/admin/users/{other_email}/role",
            params={"role": "admin"},
            headers=headers,
        )
        self.assertEqual(promoted.status_code, 200, promoted.text)
        self.assertEqual(promoted.json()["role"], "admin")

        demoted = await self.client.put(
            f"/admin/users/{other_email}/role",
            params={"role": "user"},
            headers=headers,
        )
        self.assertEqual(demoted.status_code, 200, demoted.text)

        invalid = await self.client.put(
            f"/admin/users/{other_email}/role",
            params={"role": "owner"},
            headers=headers,
        )
        self.assertEqual(invalid.status_code, 400)
