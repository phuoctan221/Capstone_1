import copy
import json
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from bson import ObjectId
from fastapi import HTTPException
from pydantic import ValidationError

from app.models.story import StoryRequest, StoryAnswers, GeneratedStory
from app.services import story_service as stories
from app.routers import story_router
from app.services.auth_service import get_current_user
from app.main import app


class StoryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.collection = SimpleNamespace(insert_one=AsyncMock(return_value=SimpleNamespace(inserted_id=ObjectId())),
            find_one=AsyncMock(), update_one=AsyncMock(return_value=SimpleNamespace(modified_count=1)))
        self.db_patch = patch.object(stories, "get_database", return_value=SimpleNamespace(story_games=self.collection))
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)

    def doc(self):
        return {**copy.deepcopy(stories.DEMO), "_id": ObjectId(), "user_id": "me", "words": stories.DEMO_WORDS,
                "topic": "travel", "tone": "warm", "source": "demo", "created_at": datetime.now(timezone.utc), "result": None}

    def test_input_limits(self):
        for ids in [[], [str(i) for i in range(8)], ["same", "same"]]:
            with self.assertRaises(ValidationError):
                StoryRequest(vocabulary_ids=ids)
        with self.assertRaises(ValidationError):
            StoryAnswers(answers=[0, 1, 4])
        with self.assertRaises(ValidationError):
            StoryRequest(vocabulary_ids=["one"], topic="unknown")

    async def test_demo_has_all_words_and_hides_answers(self):
        GeneratedStory.model_validate(stories.DEMO)
        result = await stories.create_demo("me")
        self.assertEqual(result["source"], "demo")
        self.assertEqual(len(result["questions"]), 3)
        self.assertTrue(all("answer" not in q and "explanation" not in q for q in result["questions"]))
        self.assertIsNone(result["result"])
        for word in stories.DEMO_WORDS:
            self.assertIn(word["word"], " ".join(result["paragraphs"]))
        self.assertEqual(self.collection.insert_one.call_args.args[0]["user_id"], "me")

    async def test_foreign_vocabulary_is_rejected_before_ai(self):
        with patch.object(stories, "learned_words", AsyncMock(return_value=[])), patch.object(stories.mistral_service, "generate_json", AsyncMock()) as ai:
            with self.assertRaises(HTTPException) as error:
                await stories.create_story({"id": "me"}, StoryRequest(vocabulary_ids=["foreign"]))
        self.assertEqual(error.exception.status_code, 400)
        ai.assert_not_awaited()
        self.collection.insert_one.assert_not_awaited()

    async def test_generated_story_is_checked_and_saved(self):
        with patch.object(stories, "learned_words", AsyncMock(return_value=[{"id": "one", "word": "ticket", "meaning": "vé"}])), patch.object(stories.mistral_service, "generate_json", AsyncMock(return_value=json.dumps(stories.DEMO))):
            result = await stories.create_story({"id": "me", "learning_level": "A2"}, StoryRequest(vocabulary_ids=["one"]))
        self.assertEqual(result["source"], "ai")
        self.assertEqual(result["words"][0]["word"], "ticket")

    async def test_missing_words_or_ai_failure_never_saved(self):
        for response in [json.dumps(stories.DEMO), "not json"]:
            with patch.object(stories, "learned_words", AsyncMock(return_value=[{"id": "one", "word": "invoice"}])), patch.object(stories.mistral_service, "generate_json", AsyncMock(return_value=response)):
                with self.assertRaises(HTTPException) as error:
                    await stories.create_story({"id": "me"}, StoryRequest(vocabulary_ids=["one"]))
            self.assertEqual(error.exception.status_code, 503)
        self.collection.insert_one.assert_not_awaited()

    async def test_story_ownership_filter(self):
        self.collection.find_one.return_value = None
        story_id = str(ObjectId())
        with self.assertRaises(HTTPException) as error:
            await stories.owned_story("other-user", story_id)
        self.assertEqual(error.exception.status_code, 404)
        self.assertEqual(self.collection.find_one.call_args.args[0], {"_id": ObjectId(story_id), "user_id": "other-user"})

    async def test_grading_is_server_side_and_repeat_safe(self):
        doc = self.doc()
        self.collection.find_one.return_value = doc
        result = await stories.submit_answers("me", str(doc["_id"]), [1, 2, 3])
        self.assertEqual(result["score"], 2)
        self.assertEqual(result["feedback"][2]["answer"], 0)
        self.assertEqual(self.collection.update_one.call_args.args[0]["result"], None)
        doc["result"] = result
        repeated = await stories.submit_answers("me", str(doc["_id"]), [1, 2, 0])
        self.assertEqual(repeated["score"], 2)
        self.collection.update_one.assert_awaited_once()

    async def test_api_auth_and_demo_quiz_flow(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/games/story/stories")
            self.assertEqual(response.status_code, 401)
            app.dependency_overrides[get_current_user] = lambda: {"id": "me"}
            try:
                with patch.object(story_router, "limit", AsyncMock()):
                    response = await client.post("/games/story/demo")
                self.assertEqual(response.status_code, 201)
                saved = self.collection.insert_one.call_args.args[0]
                self.collection.find_one.return_value = saved
                response = await client.post(f"/games/story/stories/{saved['_id']}/answers", json={"answers": [1, 2, 0]})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["score"], 3)
            finally:
                app.dependency_overrides.pop(get_current_user, None)
