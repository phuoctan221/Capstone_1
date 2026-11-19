from tests.support import ApiTestCase


class DashboardTests(ApiTestCase):
    async def test_dashboard_returns_all_learner_sections(self):
        headers = await self.auth_headers()

        response = await self.client.get(
            "/learning/dashboard", params={"tz_offset": 420}, headers=headers
        )

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(set(body), {"progress", "stats", "lessons", "daily"})
        self.assertEqual(body["progress"]["words_learned"], 0)
        self.assertEqual(body["stats"]["due_today"], 0)
        self.assertTrue(body["lessons"])
        self.assertEqual(body["daily"]["goal"], 10)

    async def test_dashboard_requires_authentication(self):
        response = await self.client.get("/learning/dashboard")
        self.assertEqual(response.status_code, 401)