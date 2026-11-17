from fastapi import APIRouter, Depends

from app.models.story import StoryRequest, StoryAnswers
from app.services.auth_service import get_current_user
from app.services.ai_rate_limit import limit
from app.services import story_service
from app.services.speaking_service import learned_words

router = APIRouter(prefix="/games/story", tags=["story-game"])


@router.get("/words")
async def words(user=Depends(get_current_user)):
    return await learned_words(user["id"])


@router.get("/stories")
async def history(user=Depends(get_current_user)):
    return await story_service.history(user["id"])


@router.post("/stories", status_code=201)
async def create(data: StoryRequest, user=Depends(get_current_user)):
    await limit(f"story:{user['id']}", max_requests=5)
    return await story_service.create_story(user, data)


@router.post("/demo", status_code=201)
async def demo(user=Depends(get_current_user)):
    await limit(f"story:{user['id']}", max_requests=5)
    return await story_service.create_demo(user["id"])


@router.get("/stories/{story_id}")
async def get(story_id: str, user=Depends(get_current_user)):
    return story_service.public_story(await story_service.owned_story(user["id"], story_id))


@router.post("/stories/{story_id}/answers")
async def answer(story_id: str, data: StoryAnswers, user=Depends(get_current_user)):
    return await story_service.submit_answers(user["id"], story_id, data.answers)
