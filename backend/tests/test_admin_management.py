from datetime import datetime, timezone

from app.db import mongodb
from tests.support import ApiTestCase


class AdminManagementTests(ApiTestCase):
    async def test_stats_and_users_are_real_and_safe(self):
        headers = await self.make_admin("admin@example.com")
        await self.register("regular@example.com")

        stats = await self.client.get("/admin/stats", headers=headers)
        self.assertEqual(stats.status_code, 200, stats.text)
        body = stats.json()
        self.assertEqual(body["users"]["total"], 2)
        self.assertEqual(body["users"]["admins"], 1)
        self.assertEqual(body["users"]["regular"], 1)
        self.assertEqual(body["vocabularies"]["total"], 10)
        self.assertEqual(body["vocabularies"]["by_domain"]["general"], 6)
        self.assertEqual(body["vocabularies"]["by_domain"]["technology"], 2)
        self.assertEqual(body["vocabularies"]["by_domain"]["business"], 2)
        self.assertEqual(body["lessons"]["total"], 3)
        self.assertEqual(body["exercises"]["total"], 0)
        for item in body["users"]["recent"]:
            self.assertNotIn("password_hash", item)

        found = await self.client.get(
            "/admin/users", params={"search": "regular"}, headers=headers
        )
        self.assertEqual(found.status_code, 200, found.text)
        self.assertEqual(found.json()["total"], 1)
        self.assertEqual(found.json()["items"][0]["email"], "regular@example.com")
        self.assertNotIn("password_hash", found.json()["items"][0])

        admins = await self.client.get(
            "/admin/users", params={"role": "admin"}, headers=headers
        )
        self.assertEqual(admins.json()["total"], 1)

    async def test_domain_customisation_survives_ensure(self):
        headers = await self.make_admin()
        updated = await self.client.put(
            "/admin/domains/general",
            json={"name": "General English Updated", "order": 9, "active": True},
            headers=headers,
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["name"], "General English Updated")

        await self.client.post("/admin/domains/ensure", headers=headers)
        domains = await self.client.get("/admin/domains", headers=headers)
        self.assertEqual(domains.status_code, 200, domains.text)
        general = next(item for item in domains.json() if item["slug"] == "general")
        self.assertEqual(general["name"], "General English Updated")
        self.assertEqual(general["order"], 9)

        missing = await self.client.put(
            "/admin/domains/unknown", json={"name": "X"}, headers=headers
        )
        self.assertEqual(missing.status_code, 404)

    async def test_lesson_words_and_delete_guard(self):
        headers = await self.make_admin()
        words = await self.client.get(
            "/admin/lessons/general-a1/words", headers=headers
        )
        self.assertEqual(words.status_code, 200, words.text)
        self.assertEqual(words.json()["total"], 6)
        self.assertTrue(words.json()["items"][0]["word"])

        blocked = await self.client.delete(
            "/admin/lessons/general-a1", headers=headers
        )
        self.assertEqual(blocked.status_code, 409, blocked.text)

        created = await self.client.post(
            "/admin/lessons",
            json={"domain": "general", "level": "C1", "title": "Empty C1"},
            headers=headers,
        )
        self.assertEqual(created.status_code, 201, created.text)
        deleted = await self.client.delete(
            "/admin/lessons/general-c1", headers=headers
        )
        self.assertEqual(deleted.status_code, 204, deleted.text)

    async def test_exercise_crud(self):
        headers = await self.make_admin()
        regenerated = await self.client.post(
            "/admin/exercises/regenerate",
            params={"lesson_id": "general-a1"},
            headers=headers,
        )
        self.assertEqual(regenerated.status_code, 200, regenerated.text)
        self.assertEqual(regenerated.json()["items"], 18)

        listing = await self.client.get(
            "/admin/exercises",
            params={"lesson_id": "general-a1", "skill": "meaning", "page_size": 5},
            headers=headers,
        )
        self.assertEqual(listing.status_code, 200, listing.text)
        item = listing.json()["items"][0]

        fetched = await self.client.get(
            f"/admin/exercises/{item['exercise_item_id']}", headers=headers
        )
        self.assertEqual(fetched.status_code, 200, fetched.text)

        updated = await self.client.put(
            f"/admin/exercises/{item['exercise_item_id']}",
            json={
                "prompt": "Chọn nghĩa đúng",
                "hint": "gợi ý mới",
                "options": item["options"],
                "correct_answer": item["correct_answer"],
            },
            headers=headers,
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["prompt"], "Chọn nghĩa đúng")
        self.assertEqual(updated.json()["hint"], "gợi ý mới")

        bad_meaning = await self.client.put(
            f"/admin/exercises/{item['exercise_item_id']}",
            json={"options": ["only-one"]},
            headers=headers,
        )
        self.assertEqual(bad_meaning.status_code, 400)

        custom = await self.client.post(
            "/admin/exercises",
            json={
                "exercise_item_id": "custom:test",
                "vocabulary_id": self.vocab_id("apple"),
                "skill": "spelling",
                "prompt": 'Nhập từ tiếng Anh có nghĩa: "quả táo"',
                "correct_answer": "apple",
            },
            headers=headers,
        )
        self.assertEqual(custom.status_code, 201, custom.text)
        self.assertEqual(custom.json()["accepted_answers"], ["apple"])
        self.assertEqual(custom.json()["domain"], "general")

        duplicate = await self.client.post(
            "/admin/exercises",
            json={
                "exercise_item_id": "custom:test",
                "vocabulary_id": self.vocab_id("apple"),
                "skill": "spelling",
                "prompt": "dup",
                "correct_answer": "apple",
            },
            headers=headers,
        )
        self.assertEqual(duplicate.status_code, 409)

        deleted = await self.client.delete(
            f"/admin/exercises/{item['exercise_item_id']}", headers=headers
        )
        self.assertEqual(deleted.status_code, 204)

    async def test_user_cannot_mutate_admin_resources(self):
        headers = await self.auth_headers()
        cases = [
            ("post", "/admin/exercises", {"json": {}}),
            ("put", "/admin/domains/general", {"json": {"name": "X"}}),
            ("post", "/admin/lessons", {"json": {"domain": "general", "level": "A1"}}),
        ]
        for method, path, kwargs in cases:
            response = await getattr(self.client, method)(
                path, headers=headers, **kwargs
            )
            self.assertEqual(response.status_code, 403, path)

    async def test_tokens_and_db_role_are_validated(self):
        self.assertEqual((await self.client.get("/admin/stats")).status_code, 401)
        self.assertEqual(
            (
                await self.client.get(
                    "/admin/stats", headers={"Authorization": "Bearer invalid"}
                )
            ).status_code,
            401,
        )

        headers = await self.auth_headers()
        await mongodb.get_database().users.update_one(
            {"_id": self.email},
            {"$set": {"role": "owner", "updated_at": datetime.now(timezone.utc)}},
        )
        me = await self.client.get("/auth/me", headers=headers)
        self.assertEqual(me.status_code, 200, me.text)
        self.assertEqual(me.json()["role"], "user")
        self.assertEqual(
            (await self.client.get("/admin/stats", headers=headers)).status_code,
            403,
        )
