import unittest

from app.core.domains import domain_for_topic, normalize_domain
from tests.support import ApiTestCase


class DomainMappingTests(unittest.TestCase):
    def test_legacy_topics_map_to_mvp_domains(self):
        self.assertEqual(domain_for_topic("daily-life"), "general")
        self.assertEqual(domain_for_topic("academic"), "general")
        self.assertEqual(domain_for_topic("science"), "general")
        self.assertEqual(domain_for_topic("travel"), "general")
        self.assertEqual(domain_for_topic("technology"), "technology")
        self.assertEqual(domain_for_topic("business"), "business")

    def test_unknown_domain_falls_back_to_general(self):
        self.assertEqual(normalize_domain("unknown"), "general")
        self.assertEqual(domain_for_topic(None), "general")


class DomainApiTests(ApiTestCase):
    async def test_list_domains(self):
        headers = await self.auth_headers()
        response = await self.client.get("/domains", headers=headers)
        self.assertEqual(response.status_code, 200, response.text)
        domains = response.json()
        self.assertEqual([item["slug"] for item in domains], ["general", "technology", "business"])

    async def test_only_admin_can_ensure_domains(self):
        user_headers = await self.auth_headers()
        denied = await self.client.post("/admin/domains/ensure", headers=user_headers)
        self.assertEqual(denied.status_code, 403)

        admin_headers = await self.make_admin("admin@example.com")
        allowed = await self.client.post("/admin/domains/ensure", headers=admin_headers)
        self.assertEqual(allowed.status_code, 200, allowed.text)
        self.assertEqual(allowed.json()["domains"], 3)
