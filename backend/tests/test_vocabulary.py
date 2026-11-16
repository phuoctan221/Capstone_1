from tests.support import ApiTestCase


class VocabularyTests(ApiTestCase):
    async def test_list_and_filters(self):
        headers = await self.auth_headers()
        response = await self.client.get("/vocabularies", headers=headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["total"], 10)

        tech = await self.client.get(
            "/vocabularies", params={"domain": "technology"}, headers=headers
        )
        self.assertEqual(tech.json()["total"], 2)

        search = await self.client.get(
            "/vocabularies", params={"search": "apple"}, headers=headers
        )
        self.assertEqual(search.json()["total"], 1)
        self.assertEqual(search.json()["items"][0]["word"], "apple")

    async def test_get_by_id_and_missing(self):
        headers = await self.auth_headers()
        vocab_id = self.vocab_id("apple")
        response = await self.client.get(f"/vocabularies/{vocab_id}", headers=headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["meaning"], "quả táo")

        missing = await self.client.get("/vocabularies/not-an-id", headers=headers)
        self.assertEqual(missing.status_code, 404)

    async def test_writes_require_admin(self):
        headers = await self.auth_headers()
        payload = {"word": "novel", "meaning": "tiểu thuyết", "domain": "general", "level": "A2"}
        response = await self.client.post("/vocabulary", json=payload, headers=headers)
        self.assertEqual(response.status_code, 403)

    async def test_admin_crud_and_dedup(self):
        headers = await self.make_admin()
        payload = {
            "word": "novel",
            "meaning": "tiểu thuyết",
            "domain": "general",
            "level": "A2",
            "example": "She is reading a novel.",
        }
        created = await self.client.post("/vocabulary", json=payload, headers=headers)
        self.assertEqual(created.status_code, 201, created.text)
        vocab_id = created.json()["id"]
        self.assertEqual(created.json()["domain"], "general")

        again = await self.client.post("/vocabulary", json=payload, headers=headers)
        self.assertEqual(again.status_code, 201)
        self.assertEqual(again.json()["id"], vocab_id)

        updated = await self.client.put(
            f"/vocabulary/{vocab_id}",
            json={"meaning": "cuốn tiểu thuyết"},
            headers=headers,
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["meaning"], "cuốn tiểu thuyết")

        deleted = await self.client.delete(f"/vocabulary/{vocab_id}", headers=headers)
        self.assertEqual(deleted.status_code, 204)
        gone = await self.client.get(f"/vocabularies/{vocab_id}", headers=headers)
        self.assertEqual(gone.status_code, 404)
